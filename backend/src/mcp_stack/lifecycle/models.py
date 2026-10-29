from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

LifecycleAction = Literal["start", "stop", "restart"]
LifecycleState = Literal["active", "activating", "deactivating", "failed", "inactive", "unknown"]


@dataclass(frozen=True)
class ManagedExecutionPlan:
    stack_id: str
    component_id: str
    subject_kind: Literal["application", "tunnel"]
    subject_id: str
    command_id: str
    argv: tuple[str, ...]
    working_directory: str | None
    environment: Mapping[str, str] = field(repr=False)
    restart: Literal["never", "on-failure"] = "never"
    stop_timeout_seconds: int = 15


@dataclass(frozen=True)
class LifecycleObservation:
    component_id: str
    provider: Literal["systemd-user"]
    unit_id: str
    state: LifecycleState
    observed_at: datetime
    detail: str
    intentionally_active: bool
    boot_enabled: bool
    result: str | None = None


class LifecycleError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)
