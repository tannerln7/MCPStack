from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mcp_stack.configuration import FilesystemStackRepository
from mcp_stack.execution import (
    ExecutionTarget,
    StdioExecutionPlan,
)
from mcp_stack.runtime import (
    RuntimeRegistryError,
    SessionRegistry,
    default_session_directory,
)
from mcp_stack.services.observations import ObservationService


class MutableIdentityReader:
    def __init__(self, start_ticks: int | None = 42) -> None:
        self.value = start_ticks

    def start_ticks(self, pid: int) -> int | None:
        return self.value


def _plan(revision: str = "current-revision") -> StdioExecutionPlan:
    return StdioExecutionPlan(
        target=ExecutionTarget(
            "local-development", "filesystem-mcp", "filesystem-mcp", "filesystem-command"
        ),
        configuration_revision=revision,
        argv=("server", "--stdio"),
        working_directory=None,
        environment={"SECRET_VALUE": "must-never-be-registered"},
    )


def _record(repository_root: Path):
    repository = FilesystemStackRepository(
        repository_root / "schemas" / "examples",
        repository_root / "schemas" / "domain" / "stack-config.schema.json",
    )
    record = repository.get("local-development")
    assert record is not None
    return record


def test_default_runtime_directory_uses_service_location_and_override() -> None:
    assert default_session_directory(environment={}, uid=1234) == Path("/run/mcp-stack/sessions")
    assert default_session_directory(
        environment={"MCP_STACK_RUNTIME_DIR": "/tmp/bounded-runtime"}, uid=1234
    ) == Path("/tmp/bounded-runtime/sessions")


def test_registration_is_private_and_excludes_environment(tmp_path: Path) -> None:
    registry = SessionRegistry(
        tmp_path / "runtime" / "sessions", identity_reader=MutableIdentityReader()
    )

    registration, path = registry.create(_plan())
    payload = path.read_text(encoding="utf-8")

    assert registration.stack_id == "local-development"
    assert path.stat().st_mode & 0o777 == 0o600
    assert registry.root.stat().st_mode & 0o777 == 0o700
    assert "must-never-be-registered" not in payload
    assert "environment" not in json.loads(payload)


def test_registry_rejects_non_private_directory(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    root.mkdir(mode=0o700)
    root.chmod(0o755)

    with pytest.raises(RuntimeRegistryError, match="not private"):
        SessionRegistry(root, identity_reader=MutableIdentityReader()).create(_plan())


def test_registration_write_failure_removes_partial_descriptor(monkeypatch, tmp_path: Path) -> None:
    registry = SessionRegistry(tmp_path / "sessions", identity_reader=MutableIdentityReader())

    def fail_write(descriptor, payload):
        raise OSError("bounded test failure")

    monkeypatch.setattr(os, "write", fail_write)

    with pytest.raises(RuntimeRegistryError):
        registry.create(_plan())

    assert list(registry.root.glob("*.json")) == []


def test_malformed_and_untrusted_descriptors_are_removed(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    root.mkdir(mode=0o700)
    malformed = root / "malformed.json"
    malformed.write_text('{"registryVersion": 1, "secret": "do-not-expose"}')
    malformed.chmod(0o600)
    exposed = root / "exposed.json"
    exposed.write_text("{}")
    exposed.chmod(0o644)
    registry = SessionRegistry(root, identity_reader=MutableIdentityReader())

    assert list(registry.registrations()) == []
    assert not malformed.exists()
    assert not exposed.exists()


def test_observer_handles_concurrent_sessions_and_revision_mismatch(
    repository_root: Path, tmp_path: Path
) -> None:
    identity = MutableIdentityReader()
    registry = SessionRegistry(tmp_path / "sessions", identity_reader=identity)
    record = _record(repository_root)
    registry.create(_plan(record.revision))
    registry.create(_plan("older-revision"))

    snapshot = ObservationService(registry).snapshot_for(record)
    component = next(item for item in snapshot.components if item.component_id == "filesystem-mcp")

    assert component.status == "running"
    assert len(snapshot.execution_sessions) == 2
    assert len(snapshot.process_instances) == 2
    assert {item.configuration_revision_matches for item in snapshot.execution_sessions} == {
        True,
        False,
    }
    assert snapshot.mcp_sessions == []
    assert all(item.state == "active" for item in snapshot.execution_sessions)


def test_pid_reuse_marks_registration_stale_and_removes_it_lazily(
    repository_root: Path, tmp_path: Path
) -> None:
    identity = MutableIdentityReader(42)
    registry = SessionRegistry(tmp_path / "sessions", identity_reader=identity)
    record = _record(repository_root)
    _, path = registry.create(_plan(record.revision))
    identity.value = 99

    first = ObservationService(registry).snapshot_for(record)
    second = ObservationService(registry).snapshot_for(record)

    assert first.execution_sessions[0].state == "stale"
    assert first.components[0].status == "not-observed"
    assert not path.exists()
    assert second.execution_sessions == []
    assert second.components[0].status == "not-observed"
