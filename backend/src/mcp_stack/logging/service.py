from __future__ import annotations

from dataclasses import dataclass

from mcp_stack.configuration import StackRecord
from mcp_stack.lifecycle import LifecycleService


@dataclass(frozen=True)
class RecentLogs:
    component_id: str
    lines: tuple[str, ...]
    truncated: bool


class LogService:
    def __init__(self, lifecycle: LifecycleService) -> None:
        self._lifecycle = lifecycle

    def recent(self, record: StackRecord, component_id: str, limit: int) -> RecentLogs:
        bounded = max(1, min(limit, 500))
        lines = self._lifecycle.logs_for(record, component_id, bounded)
        return RecentLogs(
            component_id=component_id,
            lines=tuple(lines),
            truncated=len(lines) >= bounded,
        )
