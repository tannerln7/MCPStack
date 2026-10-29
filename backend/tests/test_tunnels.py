import os
import stat
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from mcp_stack.lifecycle import LifecycleObservation
from mcp_stack.main import create_app
from mcp_stack.secrets import ControlPlaneSecretStore
from mcp_stack.tunnels import (
    TunnelLifecycleService,
    TunnelProfileCreate,
    TunnelProfileError,
    TunnelProfileRepository,
)


class CapturingLifecycleProvider:
    def __init__(self) -> None:
        self.plan = None
        self.log_lines: list[str] = []

    def act(self, _action, plan):
        self.plan = plan
        return LifecycleObservation(
            component_id=plan.component_id,
            provider="systemd-user",
            unit_id="test.service",
            state="active",
            observed_at=datetime.now(UTC),
            detail="active",
            intentionally_active=True,
            boot_enabled=False,
        )

    def recent_logs(self, _stack_id, _component_id, limit):
        return self.log_lines[-limit:]


def _stack_document(stack_id: str = "created-stack") -> str:
    return yaml.safe_dump(
        {
            "modelVersion": "0.1",
            "id": stack_id,
            "name": "Created Stack",
            "endpoints": [
                {
                    "id": "remote",
                    "origin": "configured",
                    "url": "https://example.com/mcp",
                }
            ],
            "transports": [{"id": "http", "kind": "streamable-http", "endpointRef": "remote"}],
            "mcpServers": [{"id": "mcp", "name": "MCP", "transportRef": "http"}],
            "components": [
                {
                    "id": "mcp-component",
                    "name": "MCP",
                    "enabled": True,
                    "subject": {"mcpServerRef": "mcp"},
                }
            ],
        },
        sort_keys=False,
    )


def _client(repository_root: Path, tmp_path: Path) -> TestClient:
    config_dir = tmp_path / "stacks"
    config_dir.mkdir(mode=0o700)
    app = create_app(
        config_dir=config_dir,
        schema_path=repository_root / "schemas/domain/stack-config.schema.json",
        runtime_dir=tmp_path / "runtime",
        tunnel_profile_dir=tmp_path / "profiles",
        tunnel_client_executable=tmp_path / "managed/tunnel-client",
        secret_dir=tmp_path / "secrets",
        allowed_hosts=("testserver",),
        allowed_mutation_origins=("http://testserver",),
    )
    return TestClient(
        app,
        headers={"Origin": "http://testserver", "X-MCP-Stack-Mutation": "1"},
    )


def test_creates_new_stack_exclusively(repository_root: Path, tmp_path: Path) -> None:
    client = _client(repository_root, tmp_path)
    document = _stack_document()

    preview = client.post(
        "/api/v1/stacks/validation-previews",
        json={"stackId": "created-stack", "document": document},
    )
    created = client.post("/api/v1/stacks", json={"stackId": "created-stack", "document": document})
    duplicate = client.post(
        "/api/v1/stacks", json={"stackId": "created-stack", "document": document}
    )

    assert preview.status_code == 200
    assert preview.json()["valid"] is True
    assert created.status_code == 201
    assert created.json()["source"]["path"] == "created-stack.yaml"
    assert stat.S_IMODE((tmp_path / "stacks/created-stack.yaml").stat().st_mode) == 0o600
    assert duplicate.status_code == 422


def test_profile_creation_uses_fixed_secret_reference(tmp_path: Path) -> None:
    repository = TunnelProfileRepository(tmp_path / "profiles")

    profile = repository.create(
        TunnelProfileCreate(
            id="docs-tunnel",
            tunnel_id="tunnel_example",
            target_kind="stdio",
            stack_target="docs",
        )
    )
    source = (tmp_path / "profiles/docs-tunnel.yaml").read_text()

    assert profile.associated_stack_id == "docs"
    assert "env:CONTROL_PLANE_API_KEY" in source
    assert stat.S_IMODE((tmp_path / "profiles/docs-tunnel.yaml").stat().st_mode) == 0o600


def test_profile_update_and_delete_are_revision_checked(tmp_path: Path) -> None:
    repository = TunnelProfileRepository(tmp_path / "profiles")
    original = repository.create(
        TunnelProfileCreate(
            id="docs-tunnel",
            tunnel_id="tunnel_example",
            target_kind="stdio",
            stack_target="docs",
        )
    )
    candidate = TunnelProfileCreate(
        id="docs-tunnel",
        tunnel_id="tunnel_revised",
        target_kind="stdio",
        stack_target="docs",
        channel="review",
    )

    updated = repository.update("docs-tunnel", original.revision, candidate)

    assert updated.tunnel_id == "tunnel_revised"
    assert updated.target.channel == "review"
    with pytest.raises(TunnelProfileError) as conflict:
        repository.update("docs-tunnel", original.revision, candidate)
    assert conflict.value.code == "profile-revision-conflict"
    with pytest.raises(TunnelProfileError) as delete_conflict:
        repository.delete("docs-tunnel", original.revision)
    assert delete_conflict.value.code == "profile-revision-conflict"

    repository.delete("docs-tunnel", updated.revision)

    assert repository.get("docs-tunnel") is None


def test_absolute_mcpctl_profile_remains_associated_with_stack(tmp_path: Path) -> None:
    repository = TunnelProfileRepository(tmp_path / "profiles")
    profile = repository.create(
        TunnelProfileCreate(
            id="docs-tunnel",
            tunnel_id="tunnel_example",
            target_kind="stdio",
            stack_target="docs",
        )
    )
    absolute_profile = replace(
        profile,
        target=replace(
            profile.target,
            command="/home/example/.local/bin/mcpctl stdio docs",
        ),
    )

    assert absolute_profile.associated_stack_id == "docs"


def test_profile_repository_rejects_unsafe_secret_reference(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    root.mkdir()
    path = root / "unsafe.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "config_version": 1,
                "control_plane": {
                    "base_url": "https://api.openai.com",
                    "tunnel_id": "tunnel_example",
                    "api_key": "literal-secret",
                },
                "mcp": {"commands": [{"channel": "main", "command": "mcpctl stdio docs"}]},
            }
        )
    )
    os.chmod(path, 0o600)

    try:
        TunnelProfileRepository(root).get("unsafe")
    except TunnelProfileError as error:
        assert error.code == "unsafe-credential-reference"
    else:
        raise AssertionError("unsafe credential reference was accepted")


def test_profile_creation_rejects_non_loopback_health_and_credentialed_urls(
    tmp_path: Path,
) -> None:
    repository = TunnelProfileRepository(tmp_path / "profiles")

    with pytest.raises(TunnelProfileError, match="loopback"):
        repository.create(
            TunnelProfileCreate(
                id="unsafe-listener",
                tunnel_id="tunnel_example",
                target_kind="stdio",
                stack_target="docs",
                health_listen_addr="0.0.0.0:8080",
            )
        )
    with pytest.raises(TunnelProfileError, match="without credentials"):
        repository.create(
            TunnelProfileCreate(
                id="unsafe-url",
                tunnel_id="tunnel_example",
                target_kind="http",
                url="https://user:password@example.com/mcp",
            )
        )


def test_secret_store_never_returns_value_in_status(tmp_path: Path) -> None:
    store = ControlPlaneSecretStore(tmp_path / "secrets")
    marker = "must-not-be-disclosed"

    store.write("system", "tunnel-control-plane-api-key", marker)

    metadata = store.metadata("system", "tunnel-control-plane-api-key")
    assert metadata.state == "configured"
    assert marker not in repr(metadata)
    secret_path = tmp_path / "secrets/scopes/system/tunnel-control-plane-api-key.secret"
    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600


def test_tunnel_api_does_not_disclose_credential(repository_root: Path, tmp_path: Path) -> None:
    client = _client(repository_root, tmp_path)
    marker = "private-control-plane-key"

    response = client.put("/api/v1/tunnel-client/credential", json={"apiKey": marker})
    status_response = client.get("/api/v1/tunnel-client")

    assert response.status_code == 200
    assert response.json()["credentialState"] == "configured"
    assert marker not in response.text
    assert marker not in status_response.text


def test_tunnel_start_refuses_missing_credential_without_500(
    repository_root: Path, tmp_path: Path
) -> None:
    executable = tmp_path / "managed/tunnel-client"
    executable.parent.mkdir()
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o700)
    client = _client(repository_root, tmp_path)
    assert (
        client.post(
            "/api/v1/tunnel-profiles",
            json={
                "id": "docs-tunnel",
                "tunnelId": "tunnel_example",
                "targetKind": "http",
                "url": "https://example.com/mcp",
            },
        ).status_code
        == 201
    )

    response = client.post(
        "/api/v1/tunnel-profiles/docs-tunnel/lifecycle-actions",
        json={"action": "start"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "credential-missing"
    assert "CONTROL_PLANE_API_KEY" not in response.text


def test_tunnel_api_supports_detail_edit_and_delete(repository_root: Path, tmp_path: Path) -> None:
    client = _client(repository_root, tmp_path)
    created = client.post(
        "/api/v1/tunnel-profiles",
        json={
            "id": "docs-tunnel",
            "tunnelId": "tunnel_example",
            "targetKind": "http",
            "url": "https://example.com/mcp",
        },
    ).json()

    detail = client.get("/api/v1/tunnel-profiles/docs-tunnel")
    updated = client.put(
        "/api/v1/tunnel-profiles/docs-tunnel",
        json={
            "id": "docs-tunnel",
            "originalRevision": created["revision"],
            "tunnelId": "tunnel_updated",
            "targetKind": "http",
            "url": "https://example.com/revised-mcp",
        },
    )
    stale = client.request(
        "DELETE",
        "/api/v1/tunnel-profiles/docs-tunnel",
        json={"originalRevision": created["revision"]},
    )
    deleted = client.request(
        "DELETE",
        "/api/v1/tunnel-profiles/docs-tunnel",
        json={"originalRevision": updated.json()["revision"]},
    )

    assert detail.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["tunnelId"] == "tunnel_updated"
    assert stale.status_code == 409
    assert deleted.status_code == 200
    assert client.get("/api/v1/tunnel-profiles/docs-tunnel").status_code == 404


def test_tunnel_unit_receives_safe_command_search_path(tmp_path: Path) -> None:
    executable = tmp_path / "managed/tunnel-client"
    executable.parent.mkdir()
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o700)
    repository = TunnelProfileRepository(tmp_path / "profiles")
    repository.create(
        TunnelProfileCreate(
            id="docs-tunnel",
            tunnel_id="tunnel_example",
            target_kind="stdio",
            stack_target="docs",
        )
    )
    secret_store = ControlPlaneSecretStore(tmp_path / "secrets")
    secret_store.write("system", "tunnel-control-plane-api-key", "test-secret")
    provider = CapturingLifecycleProvider()
    service = TunnelLifecycleService(
        repository,
        secret_store,
        executable,
        provider,  # type: ignore[arg-type]
        tmp_path / "runtime",
        command_search_path="/managed/uv/bin:/home/test/.local/bin:/usr/bin",
    )

    service.act("docs-tunnel", "start")

    assert provider.plan is not None
    assert provider.plan.environment["PATH"] == ("/managed/uv/bin:/home/test/.local/bin:/usr/bin")
    assert provider.plan.environment["CONTROL_PLANE_API_KEY"] == "test-secret"
    assert "test-secret" not in repr(provider.plan)


def test_tunnel_logs_redact_control_plane_credential(tmp_path: Path) -> None:
    executable = tmp_path / "managed/tunnel-client"
    executable.parent.mkdir()
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o700)
    repository = TunnelProfileRepository(tmp_path / "profiles")
    repository.create(
        TunnelProfileCreate(
            id="docs-tunnel",
            tunnel_id="tunnel_example",
            target_kind="stdio",
            stack_target="docs",
        )
    )
    secret_store = ControlPlaneSecretStore(tmp_path / "secrets")
    marker = "private-control-plane-key"
    secret_store.write("system", "tunnel-control-plane-api-key", marker)
    provider = CapturingLifecycleProvider()
    provider.log_lines = [f"credential={marker}", "tunnel stopped"]
    service = TunnelLifecycleService(
        repository,
        secret_store,
        executable,
        provider,  # type: ignore[arg-type]
        tmp_path / "runtime",
    )

    lines = service.logs("docs-tunnel", 100)

    assert lines == ["credential=[REDACTED]", "tunnel stopped"]
    assert marker not in repr(lines)


def test_default_tunnel_search_path_uses_service_tools() -> None:
    entries = TunnelLifecycleService._default_command_search_path().split(os.pathsep)

    assert "/usr/local/bin" in entries
    assert "/opt/mcp-stack/bin" in entries
    assert "/usr/bin" in entries
