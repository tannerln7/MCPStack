import os
import stat
import subprocess
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from mcp_stack.configuration import FilesystemStackRepository
from mcp_stack.execution import EnvironmentComposer
from mcp_stack.lifecycle import (
    LifecycleError,
    LifecycleService,
    SystemdUserLifecycleProvider,
)
from mcp_stack.lifecycle.systemd import unit_name
from mcp_stack.main import create_app
from mcp_stack.tunnels import TunnelProfileCreate


class EmptyEnvironment:
    def inherited_environment(self):
        return {"PATH": "/usr/bin"}

    def environment_value(self, name):
        return None

    def secret_value(self, stack_id, source):
        return None

    def expand_path(self, path):
        return str(Path(path).expanduser())


def _service(provider) -> LifecycleService:
    return LifecycleService(provider, EnvironmentComposer(EmptyEnvironment()))


def _managed_document() -> dict:
    return {
        "modelVersion": "0.1",
        "id": "managed-demo",
        "name": "Managed demo",
        "runtimes": [{"id": "host", "kind": "host"}],
        "commands": [
            {
                "id": "app-command",
                "runtimeRef": "host",
                "executable": {"kind": "local-path", "path": "/bin/sleep"},
                "args": ["30"],
            },
            {
                "id": "tunnel-command",
                "runtimeRef": "host",
                "executable": {"kind": "local-path", "path": "/bin/sleep"},
                "args": ["30"],
            },
        ],
        "secretSources": [
            {
                "id": "managed-token",
                "kind": "secret-reference",
                "provider": "control-plane-store",
            }
        ],
        "endpoints": [
            {"id": "local-endpoint", "origin": "configured", "url": "http://127.0.0.1:9"}
        ],
        "applications": [{"id": "app", "name": "App", "processCommandRef": "app-command"}],
        "tunnels": [
            {
                "id": "tunnel",
                "name": "Tunnel",
                "targetEndpointRef": "local-endpoint",
                "clientCommandRef": "tunnel-command",
                "lifecyclePolicyRef": "managed",
            }
        ],
        "lifecyclePolicies": [
            {
                "id": "managed",
                "ownership": "control-plane-managed",
                "activation": "persistent",
                "provider": "system-service",
                "restart": "on-failure",
                "stopTimeoutSeconds": 7,
            }
        ],
        "components": [
            {
                "id": "app-component",
                "name": "App",
                "enabled": True,
                "subject": {"applicationRef": "app"},
                "lifecyclePolicyRef": "managed",
            },
            {
                "id": "tunnel-component",
                "name": "Tunnel",
                "enabled": True,
                "subject": {"tunnelRef": "tunnel"},
                "lifecyclePolicyRef": "managed",
            },
        ],
    }


def _record(repository_root: Path, tmp_path: Path):
    tmp_path.mkdir(parents=True)
    (tmp_path / "managed.yaml").write_text(yaml.safe_dump(_managed_document()))
    return FilesystemStackRepository(
        tmp_path, repository_root / "schemas/domain/stack-config.schema.json"
    ).get("managed-demo")


class FakeSystemd:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.active = False
        self.description = "MCPStack managed managed-demo/app-component"
        self.log_output = "first\n\x1b[31msecond\x1b[0m\n"

    def __call__(self, argv, **_kwargs):
        self.calls.append(argv)
        if argv[0] == "systemd-run":
            self.active = True
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:3] == ["systemctl", "--user", "stop"]:
            self.active = False
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[:3] == ["systemctl", "--user", "restart"]:
            self.active = True
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[0] == "journalctl":
            return subprocess.CompletedProcess(argv, 0, self.log_output, "")
        payload = {
            "LoadState": "loaded" if self.active else "not-found",
            "ActiveState": "active" if self.active else "inactive",
            "SubState": "running" if self.active else "dead",
            "Result": "success",
            "UnitFileState": "transient" if self.active else "",
            "Description": self.description,
        }
        output = "\n".join(f"{key}={value}" for key, value in payload.items())
        return subprocess.CompletedProcess(argv, 0, output, "")


def test_unit_identity_is_namespaced_and_derived() -> None:
    assert unit_name("managed-demo", "app-component").startswith(
        "mcp-stack-managed-demo-app-component-"
    )
    assert unit_name("managed-demo", "app-component") == unit_name("managed-demo", "app-component")
    assert "../../" not in unit_name("../../escape", "unit.service")


def test_log_query_uses_explicit_service_identity_and_derived_unit(tmp_path: Path) -> None:
    fake = FakeSystemd()
    provider = SystemdUserLifecycleProvider(tmp_path / "runtime", fake)

    provider.recent_logs("managed-demo", "app-component", 25)

    argv = fake.calls[-1]
    assert argv[0] == "journalctl"
    assert f"_UID={os.geteuid()}" in argv
    assert f"_SYSTEMD_USER_UNIT={unit_name('managed-demo', 'app-component')}" in argv
    assert "--user-unit" not in argv


def test_managed_application_start_restart_stop_is_manual_and_private(
    repository_root: Path, tmp_path: Path
) -> None:
    record = _record(repository_root, tmp_path / "config")
    assert record is not None
    fake = FakeSystemd()
    provider = SystemdUserLifecycleProvider(tmp_path / "runtime", fake)
    service = _service(provider)

    inactive = service.observation_for(record, "app-component")
    started = service.act(record, "app-component", "start")
    environment_files = list((tmp_path / "runtime/managed-environments").glob("*.env"))
    assert len(environment_files) == 1
    assert stat.S_IMODE(environment_files[0].stat().st_mode) == 0o600
    restarted = service.act(record, "app-component", "restart")
    stopped = service.act(record, "app-component", "stop")

    assert inactive is not None and inactive.state == "inactive"
    assert started.state == "active" and not started.boot_enabled
    assert restarted.state == "active"
    assert stopped.state == "inactive" and not stopped.intentionally_active
    start_argv = next(call for call in fake.calls if call[0] == "systemd-run")
    assert "enable" not in start_argv
    assert "--property=Restart=on-failure" in start_argv
    assert start_argv[-3:] == ["--", "/bin/sleep", "30"]
    assert list((tmp_path / "runtime/managed-environments").glob("*.env")) == []


def test_tunnel_has_an_independent_unit_and_plan(repository_root: Path, tmp_path: Path) -> None:
    record = _record(repository_root, tmp_path / "config")
    assert record is not None
    fake = FakeSystemd()
    service = _service(SystemdUserLifecycleProvider(tmp_path / "runtime", fake))

    app_plan = service.plan_for(record, "app-component")
    tunnel_plan = service.plan_for(record, "tunnel-component")

    assert app_plan is not None and tunnel_plan is not None
    assert app_plan.subject_kind == "application"
    assert tunnel_plan.subject_kind == "tunnel"
    assert unit_name(app_plan.stack_id, app_plan.component_id) != unit_name(
        tunnel_plan.stack_id, tunnel_plan.component_id
    )


def test_managed_local_path_executable_is_expanded(repository_root: Path, tmp_path: Path) -> None:
    document = _managed_document()
    document["commands"][0]["executable"]["path"] = "~/.local/bin/demo-app"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "managed.yaml").write_text(yaml.safe_dump(document))
    record = FilesystemStackRepository(
        config_dir, repository_root / "schemas/domain/stack-config.schema.json"
    ).get("managed-demo")
    assert record is not None
    plan = _service(SystemdUserLifecycleProvider(tmp_path / "runtime", FakeSystemd())).plan_for(
        record, "app-component"
    )

    assert plan is not None
    assert plan.argv[0] == str(Path.home() / ".local/bin/demo-app")


def test_existing_derived_unit_requires_verified_ownership(
    repository_root: Path, tmp_path: Path
) -> None:
    record = _record(repository_root, tmp_path / "config")
    assert record is not None
    fake = FakeSystemd()
    fake.active = True
    fake.description = "Unrelated user service"
    service = _service(SystemdUserLifecycleProvider(tmp_path / "runtime", fake))

    observation = service.observation_for(record, "app-component")
    assert observation is not None
    assert observation.state == "unknown"
    assert observation.result == "ownership-mismatch"
    with pytest.raises(LifecycleError, match="not owned"):
        service.act(record, "app-component", "stop")


def test_lifecycle_api_exposes_only_eligible_targets_and_protects_actions(
    repository_root: Path, tmp_path: Path
) -> None:
    config_dir = tmp_path / "config"
    record = _record(repository_root, config_dir)
    assert record is not None
    service = _service(SystemdUserLifecycleProvider(tmp_path / "runtime", FakeSystemd()))
    app = create_app(
        config_dir=config_dir,
        schema_path=repository_root / "schemas/domain/stack-config.schema.json",
        runtime_dir=tmp_path / "sessions",
        allowed_hosts=("testserver",),
        allowed_mutation_origins=("http://testserver",),
        lifecycle_service=service,
    )
    client = TestClient(app)
    endpoint = "/api/v1/stacks/managed-demo/components/app-component"

    lifecycle = client.get(f"{endpoint}/lifecycle")
    refused = client.post(f"{endpoint}/lifecycle-actions", json={"action": "start"})
    started = client.post(
        f"{endpoint}/lifecycle-actions",
        json={"action": "start"},
        headers={"Origin": "http://testserver", "X-MCP-Stack-Mutation": "1"},
    )

    assert lifecycle.status_code == 200 and lifecycle.json()["eligible"]
    assert refused.status_code == 403
    assert started.status_code == 200 and started.json()["state"] == "active"


def test_lifecycle_api_accepts_an_exact_configured_public_origin(
    repository_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    record = _record(repository_root, config_dir)
    assert record is not None
    service = _service(SystemdUserLifecycleProvider(tmp_path / "runtime", FakeSystemd()))
    monkeypatch.setenv("MCP_STACK_PUBLIC_ORIGINS", "https://mcp.example.com")
    app = create_app(
        config_dir=config_dir,
        schema_path=repository_root / "schemas/domain/stack-config.schema.json",
        runtime_dir=tmp_path / "sessions",
        allowed_hosts=("testserver",),
        lifecycle_service=service,
    )
    client = TestClient(app)
    endpoint = "/api/v1/stacks/managed-demo/components/app-component/lifecycle-actions"
    headers = {
        "Origin": "https://mcp.example.com",
        "X-MCP-Stack-Mutation": "1",
    }

    accepted = client.post(endpoint, json={"action": "start"}, headers=headers)
    rejected = client.post(
        endpoint,
        json={"action": "stop"},
        headers={**headers, "Origin": "https://attacker.example"},
    )

    assert accepted.status_code == 200
    assert rejected.status_code == 403


def test_stack_delete_stops_owned_components_and_associated_tunnels(
    repository_root: Path, tmp_path: Path
) -> None:
    config_dir = tmp_path / "config"
    record = _record(repository_root, config_dir)
    assert record is not None
    config_dir.chmod(0o700)
    config_path = config_dir / "managed.yaml"
    config_path.chmod(0o600)
    fake = FakeSystemd()
    provider = SystemdUserLifecycleProvider(tmp_path / "runtime", fake)
    lifecycle = _service(provider)
    profile_dir = tmp_path / "profiles"
    app = create_app(
        config_dir=config_dir,
        schema_path=repository_root / "schemas/domain/stack-config.schema.json",
        runtime_dir=tmp_path / "sessions",
        tunnel_profile_dir=profile_dir,
        secret_dir=tmp_path / "secrets",
        allowed_hosts=("testserver",),
        allowed_mutation_origins=("http://testserver",),
        lifecycle_service=lifecycle,
    )
    app.state.tunnel_profile_repository.create(
        TunnelProfileCreate(
            id="managed-demo-tunnel",
            tunnel_id="tunnel_example",
            target_kind="stdio",
            stack_target="managed-demo",
        )
    )
    app.state.secret_store.write("managed-demo", "managed-token", "stack-owned-secret")
    app.state.secret_store.write("system", "tunnel-control-plane-api-key", "shared-tunnel-secret")
    app.state.tunnel_service.provider = provider
    client = TestClient(app)
    headers = {"Origin": "http://testserver", "X-MCP-Stack-Mutation": "1"}

    deleted = client.request(
        "DELETE",
        "/api/v1/stacks/managed-demo",
        headers=headers,
        json={"originalRevision": record.revision},
    )

    assert deleted.status_code == 200, deleted.text
    assert set(deleted.json()["componentIds"]) == {"app-component", "tunnel-component"}
    assert set(deleted.json()["stoppedComponentIds"]) == {
        "app-component",
        "tunnel-component",
    }
    assert deleted.json()["deletedTunnelProfileIds"] == ["managed-demo-tunnel"]
    assert deleted.json()["deletedSecretSourceIds"] == ["managed-token"]
    assert app.state.secret_store.metadata("managed-demo", "managed-token").state == "missing"
    assert (
        app.state.secret_store.metadata("system", "tunnel-control-plane-api-key").state
        == "configured"
    )
    assert not config_path.exists()
    assert not (profile_dir / "managed-demo-tunnel.yaml").exists()
    stop_calls = [call for call in fake.calls if call[:3] == ["systemctl", "--user", "stop"]]
    assert len(stop_calls) == 3
