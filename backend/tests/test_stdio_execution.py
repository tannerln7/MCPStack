from __future__ import annotations

import io
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mcp_stack import cli
from mcp_stack.broker import BrokerClientError
from mcp_stack.configuration import (
    ConfigurationSource,
    FilesystemStackRepository,
    RepositorySnapshot,
    StackRecord,
)
from mcp_stack.domain.configuration import SecretSource, StackConfiguration
from mcp_stack.execution import (
    EnvironmentComposer,
    ExecutionTarget,
    StdioExecutionError,
    StdioExecutionPlanner,
    StdioTargetResolver,
)


class StubRepository:
    def __init__(self, *records: StackRecord) -> None:
        self._snapshot = RepositorySnapshot(
            records=records,
            diagnostics=(),
            scanned_source_count=len(records),
        )

    def discover(self) -> RepositorySnapshot:
        return self._snapshot


class StubEnvironmentProvider:
    def __init__(
        self,
        *,
        inherited: Mapping[str, str] | None = None,
        environment: Mapping[str, str] | None = None,
        secrets: Mapping[str, str | None] | None = None,
    ) -> None:
        self.inherited = dict(inherited or {})
        self.environment = dict(environment or {})
        self.secrets = dict(secrets or {})

    def inherited_environment(self) -> Mapping[str, str]:
        return self.inherited

    def environment_value(self, name: str) -> str | None:
        return self.environment.get(name)

    def secret_value(self, stack_id: str, source: SecretSource) -> str | None:
        del stack_id
        return self.secrets.get(source.id)

    def expand_path(self, path: str) -> str:
        return path.replace("~", "/home/example", 1)


def test_example_stack_plans_service_owned_stdio_session(repository_root: Path) -> None:
    repository = FilesystemStackRepository(repository_root / "config" / "stacks")
    planner = StdioExecutionPlanner(
        repository,
        environment_composer=EnvironmentComposer(
            StubEnvironmentProvider(secrets={"api-key": "fixture-only"})
        ),
    )

    plan = planner.plan("example-stdio")

    assert plan.argv == ("mise", "exec", "--", "npx", "-y", "@example/docs-mcp@1.0.0")
    assert plan.target == ExecutionTarget(
        stack_id="example-stdio",
        component_id="mcp",
        mcp_server_id="docs-mcp",
        command_id="mcp-command",
    )
    assert plan.working_directory == "/var/lib/mcp-stack/environments/example-stdio"
    assert plan.environment == {"EXAMPLE_API_KEY": "fixture-only"}


def _record(
    tmp_path: Path,
    *,
    stack_id: str = "example",
    component_id: str = "server",
    component_name: str = "Example server",
    server_id: str = "server-mcp",
    transport_kind: str = "stdio",
    enabled: bool = True,
    ownership: str = "session-owned",
    activation: str = "on-demand",
    executable: dict | None = None,
    args: list[str] | None = None,
    working_directory: str | None = None,
    environment: list[dict] | None = None,
    environment_sources: list[dict] | None = None,
    secret_sources: list[dict] | None = None,
) -> StackRecord:
    transport = (
        {"id": "server-transport", "kind": "stdio", "commandRef": "server-command"}
        if transport_kind == "stdio"
        else {
            "id": "server-transport",
            "kind": "streamable-http",
            "endpointRef": "server-endpoint",
        }
    )
    data = {
        "modelVersion": "0.1",
        "id": stack_id,
        "name": stack_id.title(),
        "runtimes": [{"id": "host", "kind": "host"}],
        "commands": [
            {
                "id": "server-command",
                "runtimeRef": "host",
                "executable": executable or {"kind": "path-name", "name": "server-bin"},
                "args": args or [],
                **({"workingDirectory": working_directory} if working_directory else {}),
                "environment": environment or [],
            }
        ],
        "environmentSources": environment_sources or [],
        "secretSources": secret_sources or [],
        "endpoints": (
            [
                {
                    "id": "server-endpoint",
                    "origin": "configured",
                    "url": "http://127.0.0.1:9000/mcp",
                }
            ]
            if transport_kind != "stdio"
            else []
        ),
        "transports": [transport],
        "mcpServers": [
            {"id": server_id, "name": "Example MCP", "transportRef": "server-transport"}
        ],
        "lifecyclePolicies": [
            {
                "id": "session-policy",
                "ownership": ownership,
                "activation": activation,
                **({"provider": "direct-child"} if ownership == "control-plane-managed" else {}),
            }
        ],
        "components": [
            {
                "id": component_id,
                "name": component_name,
                "enabled": enabled,
                "subject": {"mcpServerRef": server_id},
                "lifecyclePolicyRef": "session-policy",
            }
        ],
    }
    configuration = StackConfiguration.model_validate(data)
    return StackRecord(
        configuration=configuration,
        source=ConfigurationSource(
            path=f"{stack_id}.yaml",
            format="yaml",
            revision=f"revision-{stack_id}",
            size_bytes=0,
            modified_at=datetime(2026, 8, 22, tzinfo=UTC),
        ),
        source_path=tmp_path / f"{stack_id}.yaml",
        document="",
    )


def _planner(
    record: StackRecord,
    *,
    environment_provider: StubEnvironmentProvider | None = None,
) -> StdioExecutionPlanner:
    return StdioExecutionPlanner(
        StubRepository(record),
        environment_composer=EnvironmentComposer(environment_provider or StubEnvironmentProvider()),
    )


def test_resolves_stack_component_and_mcp_id(tmp_path: Path) -> None:
    record = _record(tmp_path)
    resolver = StdioTargetResolver()
    snapshot = StubRepository(record).discover()

    assert resolver.resolve(snapshot, "example").component.id == "server"
    assert resolver.resolve(snapshot, "server").mcp_server.id == "server-mcp"
    assert resolver.resolve(snapshot, "example/server-mcp").component.id == "server"


def test_reports_ambiguous_and_missing_targets(tmp_path: Path) -> None:
    first = _record(tmp_path, stack_id="first", component_id="shared")
    second = _record(tmp_path, stack_id="second", component_id="shared")
    resolver = StdioTargetResolver()
    snapshot = StubRepository(first, second).discover()

    with pytest.raises(StdioExecutionError, match="not unique") as ambiguous:
        resolver.resolve(snapshot, "shared")
    with pytest.raises(StdioExecutionError, match="no configured") as missing:
        resolver.resolve(snapshot, "missing")

    assert ambiguous.value.code == "target-ambiguous"
    assert missing.value.code == "target-not-found"


def test_enforces_stdio_transport_and_session_owned_lifecycle(tmp_path: Path) -> None:
    http = _record(tmp_path, transport_kind="streamable-http")
    managed = _record(tmp_path, ownership="control-plane-managed", activation="persistent")

    with pytest.raises(StdioExecutionError) as transport_error:
        StdioTargetResolver().resolve(StubRepository(http).discover(), "example")
    with pytest.raises(StdioExecutionError) as lifecycle_error:
        StdioTargetResolver().resolve(StubRepository(managed).discover(), "example")

    assert transport_error.value.code == "transport-unsupported"
    assert lifecycle_error.value.code == "lifecycle-unsupported"


def test_execution_plan_preserves_argv_working_directory_and_target(tmp_path: Path) -> None:
    args = ["exec", "--", "npx", "-y", "@scope/server", "--flag=two words", ""]
    record = _record(
        tmp_path,
        executable={"kind": "path-name", "name": "mise"},
        args=args,
        working_directory="~/.config/example",
    )
    plan = _planner(
        record,
    ).plan("example")

    assert plan.argv == ("mise", *args)
    assert plan.working_directory == "/home/example/.config/example"
    assert plan.target == ExecutionTarget("example", "server", "server-mcp", "server-command")


def test_environment_inheritance_and_binding_composition(tmp_path: Path) -> None:
    record = _record(
        tmp_path,
        environment=[
            {"name": "LITERAL", "valueFrom": {"literal": "configured"}},
            {"name": "COPIED", "valueFrom": {"environmentSourceRef": "host-source"}},
            {"name": "TOKEN", "valueFrom": {"secretSourceRef": "token-source"}},
        ],
        environment_sources=[
            {"id": "host-source", "kind": "host-environment", "variable": "SOURCE_VALUE"}
        ],
        secret_sources=[
            {
                "id": "token-source",
                "kind": "secret-reference",
                "provider": "control-plane-store",
            }
        ],
    )
    provider = StubEnvironmentProvider(
        inherited={"INHERITED": "yes", "LITERAL": "old"},
        environment={"SOURCE_VALUE": "from-host"},
        secrets={"token-source": "private-value"},
    )
    plan = _planner(
        record,
        environment_provider=provider,
    ).plan("example")

    assert plan.environment == {
        "INHERITED": "yes",
        "LITERAL": "configured",
        "COPIED": "from-host",
        "TOKEN": "private-value",
    }
    assert "private-value" not in repr(plan)


def test_required_binding_fails_and_optional_binding_is_omitted(tmp_path: Path) -> None:
    source = {"id": "host-source", "kind": "host-environment", "variable": "MISSING"}
    required = _record(
        tmp_path,
        environment=[{"name": "VALUE", "valueFrom": {"environmentSourceRef": "host-source"}}],
        environment_sources=[source],
    )
    optional = _record(
        tmp_path,
        environment=[
            {
                "name": "VALUE",
                "required": False,
                "valueFrom": {"environmentSourceRef": "host-source"},
            }
        ],
        environment_sources=[source],
    )
    provider = StubEnvironmentProvider(inherited={"VALUE": "ambient"})

    with pytest.raises(StdioExecutionError) as required_error:
        _planner(required, environment_provider=provider).plan("example")
    optional_plan = _planner(optional, environment_provider=provider).plan("example")

    assert required_error.value.code == "environment-binding-missing"
    assert "VALUE" not in optional_plan.environment


def test_secret_resolution_does_not_disclose_values_on_failure(tmp_path: Path) -> None:
    marker = "must-never-appear"
    record = _record(
        tmp_path,
        environment=[{"name": "TOKEN", "valueFrom": {"secretSourceRef": "token-source"}}],
        secret_sources=[
            {
                "id": "token-source",
                "kind": "secret-reference",
                "provider": "control-plane-store",
            }
        ],
    )
    provider = StubEnvironmentProvider(secrets={"token-source": None})

    with pytest.raises(StdioExecutionError) as error:
        _planner(record, environment_provider=provider).plan("example")

    assert error.value.code == "environment-binding-missing"
    assert marker not in error.value.message


def test_cli_failure_is_concise_on_stderr(capsys) -> None:
    class FailingBroker:
        def launch_stdio(self, target, stdin, stdout, stderr):
            raise BrokerClientError("target-not-found", "No configured target", 2)

    stderr = io.StringIO()

    status = cli.run(
        ["stdio", "missing"],
        stderr=stderr,
        stdin_buffer=io.BytesIO(),
        stdout_buffer=io.BytesIO(),
        stderr_buffer=io.BytesIO(),
        broker_client=FailingBroker(),  # type: ignore[arg-type]
    )
    captured = capsys.readouterr()

    assert status != 0
    assert "target-not-found" in stderr.getvalue()
    assert captured.out == ""
