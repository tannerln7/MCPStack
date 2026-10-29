from __future__ import annotations

from pathlib import Path
from typing import Protocol

from mcp_stack.configuration import RepositorySnapshot
from mcp_stack.domain.configuration import (
    ImageEntrypointExecutable,
    LocalPathExecutable,
    PathNameExecutable,
)

from .environment import EnvironmentComposer
from .errors import StdioExecutionError
from .models import ExecutionTarget, StdioExecutionPlan
from .targets import StdioTargetResolver


class StackRepository(Protocol):
    def discover(self) -> RepositorySnapshot: ...


class StdioExecutionPlanner:
    def __init__(
        self,
        repository: StackRepository,
        *,
        environment_composer: EnvironmentComposer | None = None,
        target_resolver: StdioTargetResolver | None = None,
    ) -> None:
        self._repository = repository
        self._environment_composer = environment_composer or EnvironmentComposer()
        self._target_resolver = target_resolver or StdioTargetResolver()

    def plan(self, selector: str) -> StdioExecutionPlan:
        snapshot = self._repository.discover()
        if any(
            issue.code == "configuration-directory-missing"
            for diagnostic in snapshot.diagnostics
            for issue in diagnostic.issues
        ):
            raise StdioExecutionError(
                "configuration-repository-unavailable",
                "the configured Stack directory is unavailable",
            )
        target = self._target_resolver.resolve(snapshot, selector)
        command = next(
            item
            for item in target.record.configuration.commands
            if item.id == target.transport.command_ref
        )
        executable = command.executable
        if isinstance(executable, PathNameExecutable):
            executable_name = executable.name
        elif isinstance(executable, LocalPathExecutable):
            executable_name = str(Path(executable.path).expanduser())
        elif isinstance(executable, ImageEntrypointExecutable):
            raise StdioExecutionError(
                "execution-form-unsupported",
                "Container image-entrypoint execution lacks a complete invocation policy",
            )
        else:
            raise AssertionError("unsupported executable")

        return StdioExecutionPlan(
            target=ExecutionTarget(
                stack_id=target.record.configuration.id,
                component_id=target.component.id,
                mcp_server_id=target.mcp_server.id,
                command_id=command.id,
            ),
            configuration_revision=target.record.revision,
            argv=(executable_name, *command.args),
            working_directory=self._environment_composer.working_directory(command),
            environment=self._environment_composer.compose(target.record.configuration, command),
        )
