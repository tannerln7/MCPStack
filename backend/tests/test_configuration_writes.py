import hashlib
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from fastapi.testclient import TestClient

from mcp_stack.configuration import (
    ConfigurationRevisionConflict,
    ConfigurationValidationRejected,
    FilesystemStackRepository,
    RepositoryConflict,
    TrustedWorkspaceWriter,
)
from mcp_stack.lifecycle import LifecycleService
from mcp_stack.main import create_app


def _install_example(repository_root: Path, target: Path) -> Path:
    target.mkdir(mode=0o700)
    path = target / "stack.yaml"
    path.write_bytes((repository_root / "schemas/examples/local-development.yaml").read_bytes())
    os.chmod(path, 0o600)
    return path


def _repository(repository_root: Path, root: Path) -> FilesystemStackRepository:
    return FilesystemStackRepository(
        root, repository_root / "schemas/domain/stack-config.schema.json"
    )


def test_exact_candidate_bytes_are_saved_and_stale_revision_is_refused(
    repository_root: Path, tmp_path: Path
) -> None:
    path = _install_example(repository_root, tmp_path / "stacks")
    repository = _repository(repository_root, path.parent)
    record = repository.get("local-development")
    assert record is not None
    candidate = (
        record.document.replace("Local Development", "Saved exactly") + "# retained ending\n"
    )

    result = TrustedWorkspaceWriter(repository, path.parent).write(
        record, record.revision, candidate
    )

    assert path.read_bytes() == candidate.encode()
    assert result.source.revision == hashlib.sha256(candidate.encode()).hexdigest()
    try:
        TrustedWorkspaceWriter(repository, path.parent).write(record, record.revision, candidate)
    except ConfigurationRevisionConflict as error:
        assert error.current_revision == result.source.revision
    else:
        raise AssertionError("stale write was not refused")


def test_invalid_candidate_and_unsafe_metadata_are_refused(
    repository_root: Path, tmp_path: Path
) -> None:
    path = _install_example(repository_root, tmp_path / "stacks")
    repository = _repository(repository_root, path.parent)
    record = repository.get("local-development")
    assert record is not None
    original = path.read_bytes()

    try:
        TrustedWorkspaceWriter(repository, path.parent).write(
            record, record.revision, "components: ["
        )
    except ConfigurationValidationRejected:
        pass
    else:
        raise AssertionError("invalid candidate was accepted")
    assert path.read_bytes() == original

    os.link(path, path.parent / "alias.yaml")
    try:
        TrustedWorkspaceWriter(repository, path.parent).write(
            record, record.revision, record.document
        )
    except Exception as error:
        assert getattr(error, "code", None) == "unsupported-source"
    else:
        raise AssertionError("multiply-linked source was accepted")


def test_symbolic_link_source_is_refused(repository_root: Path, tmp_path: Path) -> None:
    path = _install_example(repository_root, tmp_path / "stacks")
    repository = _repository(repository_root, path.parent)
    record = repository.get("local-development")
    assert record is not None
    original = path.parent / "original.yaml"
    path.rename(original)
    path.symlink_to(original.name)

    try:
        TrustedWorkspaceWriter(repository, path.parent).write(
            record, record.revision, record.document
        )
    except Exception as error:
        assert getattr(error, "code", None) == "filesystem-error"
    else:
        raise AssertionError("symbolic-link source was accepted")


def test_repository_manifest_change_during_validation_conflicts(
    repository_root: Path, tmp_path: Path, monkeypatch
) -> None:
    path = _install_example(repository_root, tmp_path / "stacks")
    repository = _repository(repository_root, path.parent)
    record = repository.get("local-development")
    assert record is not None
    original_validate = repository.validate_candidate

    def changing_validate(stack_id: str, document: str):
        result = original_validate(stack_id, document)
        (path.parent / "concurrent.yaml").write_text("not: a stack\n")
        os.chmod(path.parent / "concurrent.yaml", 0o600)
        return result

    monkeypatch.setattr(repository, "validate_candidate", changing_validate)
    try:
        TrustedWorkspaceWriter(repository, path.parent).write(
            record, record.revision, record.document.replace("Local Development", "Changed")
        )
    except RepositoryConflict:
        pass
    else:
        raise AssertionError("repository change was not detected")


def test_stack_deletion_is_revision_checked(repository_root: Path, tmp_path: Path) -> None:
    path = _install_example(repository_root, tmp_path / "stacks")
    repository = _repository(repository_root, path.parent)
    record = repository.get("local-development")
    assert record is not None
    writer = TrustedWorkspaceWriter(repository, path.parent)

    with pytest.raises(ConfigurationRevisionConflict):
        writer.delete(record, "0" * 64)

    outcome = writer.delete(record, record.revision)

    assert outcome.source_path == "stack.yaml"
    assert not path.exists()
    assert repository.get("local-development") is None


def test_save_api_requires_mutation_boundary_and_returns_conflict(
    repository_root: Path, tmp_path: Path
) -> None:
    path = _install_example(repository_root, tmp_path / "stacks")
    app = create_app(
        config_dir=path.parent,
        schema_path=repository_root / "schemas/domain/stack-config.schema.json",
        runtime_dir=tmp_path / "runtime/sessions",
        allowed_hosts=("testserver",),
        allowed_mutation_origins=("http://testserver",),
    )
    client = TestClient(app)
    source = client.get("/api/v1/stacks/local-development/source").json()
    request = {
        "originalRevision": source["source"]["revision"],
        "document": source["document"].replace("Local Development", "API saved"),
    }

    assert client.put("/api/v1/stacks/local-development/source", json=request).status_code == 403
    headers = {"Origin": "http://testserver", "X-MCP-Stack-Mutation": "1"}
    wrong_origin = {
        "Origin": "http://attacker.invalid",
        "X-MCP-Stack-Mutation": "1",
    }
    assert (
        client.put(
            "/api/v1/stacks/local-development/source", json=request, headers=wrong_origin
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/api/v1/stacks/local-development/source",
            content=b"{}",
            headers={**headers, "Content-Type": "application/json", "Content-Length": "1100001"},
        ).status_code
        == 413
    )
    saved = client.put("/api/v1/stacks/local-development/source", json=request, headers=headers)
    conflict = client.put("/api/v1/stacks/local-development/source", json=request, headers=headers)

    assert saved.status_code == 200
    assert saved.json()["status"] == "saved"
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "source-revision-conflict"
    assert request["document"] not in conflict.text


def test_save_removes_only_secret_slots_no_longer_declared(
    repository_root: Path, tmp_path: Path
) -> None:
    path = _install_example(repository_root, tmp_path / "stacks")
    secret_dir = tmp_path / "secrets"
    app = create_app(
        config_dir=path.parent,
        schema_path=repository_root / "schemas/domain/stack-config.schema.json",
        runtime_dir=tmp_path / "runtime",
        secret_dir=secret_dir,
        allowed_hosts=("testserver",),
        allowed_mutation_origins=("http://testserver",),
    )
    client = TestClient(
        app,
        headers={"Origin": "http://testserver", "X-MCP-Stack-Mutation": "1"},
    )
    stored = client.put(
        "/api/v1/stacks/local-development/secrets/docs-token",
        json={"value": "never-return-this-value"},
    )
    assert stored.status_code == 200
    source = client.get("/api/v1/stacks/local-development/source").json()
    candidate = yaml.safe_load(source["document"])
    command = next(item for item in candidate["commands"] if item["id"] == "docs-app-command")
    command["environment"] = [
        item for item in command["environment"] if "secretSourceRef" not in item["valueFrom"]
    ]
    candidate.pop("secretSources")

    saved = client.put(
        "/api/v1/stacks/local-development/source",
        json={
            "originalRevision": source["source"]["revision"],
            "document": yaml.safe_dump(candidate, sort_keys=False),
        },
    )

    assert saved.status_code == 200, saved.text
    assert saved.json()["deletedSecretSourceIds"] == ["docs-token"]
    assert app.state.secret_store.metadata("local-development", "docs-token").state == "missing"
    assert "never-return-this-value" not in saved.text


def test_save_stops_a_removed_managed_application(repository_root: Path, tmp_path: Path) -> None:
    config_dir = tmp_path / "stacks"
    config_dir.mkdir(mode=0o700)
    path = config_dir / "example-composite.yaml"
    path.write_bytes((repository_root / "config/stacks/composite.yaml").read_bytes())
    path.chmod(0o600)
    lifecycle = Mock(spec=LifecycleService)
    lifecycle.stop_for_deletion.return_value = True
    app = create_app(
        config_dir=config_dir,
        schema_path=repository_root / "schemas/domain/stack-config.schema.json",
        runtime_dir=tmp_path / "runtime",
        secret_dir=tmp_path / "secrets",
        lifecycle_service=lifecycle,
        allowed_hosts=("testserver",),
        allowed_mutation_origins=("http://testserver",),
    )
    client = TestClient(
        app,
        headers={"Origin": "http://testserver", "X-MCP-Stack-Mutation": "1"},
    )
    source = client.get("/api/v1/stacks/example-composite/source").json()
    candidate = yaml.safe_load(source["document"])
    candidate["commands"] = [
        item for item in candidate["commands"] if item["id"] != "server-command"
    ]
    candidate.pop("endpoints")
    candidate.pop("applications")
    candidate["mcpServers"][0].pop("controlsApplicationRef")
    candidate["lifecyclePolicies"] = [
        item for item in candidate["lifecyclePolicies"] if item["id"] != "managed"
    ]
    candidate.pop("healthChecks")
    candidate.pop("logSources")
    candidate["components"] = [item for item in candidate["components"] if item["id"] != "server"]
    candidate.pop("dependencies")

    saved = client.put(
        "/api/v1/stacks/example-composite/source",
        json={
            "originalRevision": source["source"]["revision"],
            "document": yaml.safe_dump(candidate, sort_keys=False),
        },
    )

    assert saved.status_code == 200, saved.text
    assert saved.json()["stoppedComponentIds"] == ["server"]
    lifecycle.stop_for_deletion.assert_called_once()
