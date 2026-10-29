from pathlib import Path

import yaml
from test_lifecycle import FakeSystemd, _managed_document, _service

from mcp_stack.configuration import FilesystemStackRepository
from mcp_stack.domain.observations import ComponentObservation, RuntimeSnapshot
from mcp_stack.execution import EnvironmentComposer
from mcp_stack.health import HealthService
from mcp_stack.lifecycle import LifecycleService, SystemdUserLifecycleProvider
from mcp_stack.logging import LogService


def _record(repository_root: Path, tmp_path: Path):
    document = _managed_document()
    document["healthChecks"] = [
        {
            "id": "process-health",
            "name": "Process",
            "target": {"componentRef": "app-component"},
            "probe": "process-running",
            "role": "liveness",
        },
        {
            "id": "http-health",
            "name": "HTTP",
            "target": {"endpointRef": "local-endpoint"},
            "probe": "http",
            "role": "readiness",
            "expectedStatus": 200,
            "timeoutSeconds": 1,
        },
    ]
    document["components"][0]["healthCheckRefs"] = ["process-health", "http-health"]
    document["logSources"] = [
        {
            "id": "journal",
            "name": "Journal",
            "target": {"commandRef": "app-command", "stream": "stderr"},
            "encoding": "utf-8",
            "framing": "lines",
        }
    ]
    document["components"][0]["logSourceRefs"] = ["journal"]
    tmp_path.mkdir()
    (tmp_path / "managed.yaml").write_text(yaml.safe_dump(document))
    return FilesystemStackRepository(
        tmp_path, repository_root / "schemas/domain/stack-config.schema.json"
    ).get("managed-demo")


def _runtime(record, status: str) -> RuntimeSnapshot:
    from datetime import UTC, datetime

    observed_at = datetime.now(UTC)
    return RuntimeSnapshot(
        stack_id=record.configuration.id,
        configuration_revision=record.revision,
        observed_at=observed_at,
        components=[
            ComponentObservation(
                component_id="app-component", status=status, observed_at=observed_at
            )
        ],
    )


class Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_health_process_and_http_success_are_distinct_observations(
    repository_root: Path, tmp_path: Path, monkeypatch
) -> None:
    record = _record(repository_root, tmp_path / "config")
    assert record is not None
    lifecycle = _service(SystemdUserLifecycleProvider(tmp_path / "runtime", FakeSystemd()))
    monkeypatch.setattr(
        "mcp_stack.health.service._http_opener.open",
        lambda *_args, **_kwargs: Response(),
    )

    observations = HealthService(lifecycle).observations_for(record, _runtime(record, "running"))

    assert [item.status for item in observations] == ["passing", "passing"]
    assert all(item.latency_ms is not None for item in observations)


def test_health_http_failure_is_safe_and_logs_are_bounded_and_ansi_free(
    repository_root: Path, tmp_path: Path, monkeypatch
) -> None:
    record = _record(repository_root, tmp_path / "config")
    assert record is not None
    fake = FakeSystemd()
    lifecycle = _service(SystemdUserLifecycleProvider(tmp_path / "runtime", fake))

    def fail(*_args, **_kwargs):
        raise TimeoutError

    monkeypatch.setattr("mcp_stack.health.service._http_opener.open", fail)
    observations = HealthService(lifecycle).observations_for(record, _runtime(record, "stopped"))
    logs = LogService(lifecycle).recent(record, "app-component", 1)

    assert [item.status for item in observations] == ["failing", "failing"]
    assert all("http://" not in (item.reason or "") for item in observations)
    assert logs.lines == ("second",)
    assert "\x1b" not in logs.lines[0]


def test_secret_bearing_component_logs_are_redacted_before_api_boundary(
    repository_root: Path, tmp_path: Path
) -> None:
    marker = "private-component-token"
    document = _managed_document()
    document["commands"][0]["environment"] = [
        {"name": "TOKEN", "valueFrom": {"secretSourceRef": "token"}}
    ]
    document["secretSources"] = [
        {"id": "token", "kind": "secret-reference", "provider": "control-plane-store"}
    ]
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "managed.yaml").write_text(yaml.safe_dump(document))
    record = FilesystemStackRepository(
        config_dir, repository_root / "schemas/domain/stack-config.schema.json"
    ).get("managed-demo")
    assert record is not None

    class SecretEnvironment:
        def inherited_environment(self):
            return {"PATH": "/usr/bin"}

        def environment_value(self, _name):
            return None

        def secret_value(self, _stack_id, _source):
            return marker

        def expand_path(self, path):
            return path

    fake = FakeSystemd()
    fake.log_output = f"connecting with {marker}\nready\n"
    lifecycle = LifecycleService(
        SystemdUserLifecycleProvider(tmp_path / "runtime", fake),
        EnvironmentComposer(SecretEnvironment()),
    )

    logs = LogService(lifecycle).recent(record, "app-component", 100)

    assert logs.lines == ("connecting with [REDACTED]", "ready")
    assert marker not in repr(logs)
