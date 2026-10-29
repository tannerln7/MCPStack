from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True)
class ExecutionTarget:
    stack_id: str
    component_id: str
    mcp_server_id: str
    command_id: str

    @property
    def display_name(self) -> str:
        return f"{self.stack_id}/{self.component_id}"


@dataclass(frozen=True)
class StdioExecutionPlan:
    target: ExecutionTarget
    configuration_revision: str
    argv: tuple[str, ...]
    working_directory: str | None
    environment: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        if not self.argv or not self.argv[0]:
            raise ValueError("an execution plan requires a non-empty executable")
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))
