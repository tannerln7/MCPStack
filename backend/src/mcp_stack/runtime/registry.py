from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

if TYPE_CHECKING:
    from mcp_stack.execution.models import StdioExecutionPlan

_MAX_DESCRIPTOR_BYTES = 16 * 1024


class RuntimeRegistryError(Exception):
    """A safe transient session registration could not be created or read."""


class ProcessIdentityReader(Protocol):
    def start_ticks(self, pid: int) -> int | None: ...


class LocalProcessIdentityReader:
    """Read Linux process start ticks, which remain stable across exec()."""

    def start_ticks(self, pid: int) -> int | None:
        try:
            stat_line = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            return None
        closing_parenthesis = stat_line.rfind(")")
        if closing_parenthesis < 0:
            return None
        fields_after_name = stat_line[closing_parenthesis + 2 :].split()
        try:
            # Field 3 is first after the process name; process start time is field 22.
            return int(fields_after_name[19])
        except (IndexError, ValueError):
            return None


class SessionRegistration(BaseModel):
    """Safe identity metadata written immediately before process replacement."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    registry_version: Literal[1] = 1
    session_id: UUID
    stack_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    component_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    mcp_server_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    command_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    transport: Literal["stdio"] = "stdio"
    configuration_revision: str = Field(min_length=1, max_length=256)
    pid: int = Field(gt=0)
    process_start_ticks: int = Field(gt=0)
    launched_at: AwareDatetime


def default_session_directory(
    *, environment: dict[str, str] | None = None, uid: int | None = None
) -> Path:
    selected_environment = environment if environment is not None else os.environ
    configured = selected_environment.get("MCP_STACK_RUNTIME_DIR")
    if configured:
        base = Path(configured).expanduser()
        if not base.is_absolute():
            raise RuntimeRegistryError("MCP_STACK_RUNTIME_DIR must be an absolute path")
        return base / "sessions"
    return Path("/run/mcp-stack/sessions")


class SessionRegistry:
    def __init__(
        self,
        root: Path | None = None,
        *,
        identity_reader: ProcessIdentityReader | None = None,
        uid: int | None = None,
    ) -> None:
        self.root = root or default_session_directory()
        self._identity_reader = identity_reader or LocalProcessIdentityReader()
        self._uid = os.geteuid() if uid is None else uid

    def create(self, plan: StdioExecutionPlan) -> tuple[SessionRegistration, Path]:
        return self.create_for_process(plan, os.getpid())

    def create_for_process(
        self, plan: StdioExecutionPlan, pid: int
    ) -> tuple[SessionRegistration, Path]:
        self._ensure_directory()
        start_ticks = self._identity_reader.start_ticks(pid)
        if start_ticks is None:
            raise RuntimeRegistryError("the launcher process identity could not be established")
        registration = SessionRegistration(
            session_id=uuid4(),
            stack_id=plan.target.stack_id,
            component_id=plan.target.component_id,
            mcp_server_id=plan.target.mcp_server_id,
            command_id=plan.target.command_id,
            configuration_revision=plan.configuration_revision,
            pid=pid,
            process_start_ticks=start_ticks,
            launched_at=datetime.now(UTC),
        )
        path = self.root / f"{registration.session_id}.json"
        payload = registration.model_dump_json(by_alias=True).encode("utf-8")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o600)
            try:
                remaining = memoryview(payload)
                while remaining:
                    written = os.write(descriptor, remaining)
                    if written == 0:
                        raise OSError("session descriptor write returned zero bytes")
                    remaining = remaining[written:]
            finally:
                os.close(descriptor)
        except OSError as error:
            self.remove(path)
            raise RuntimeRegistryError("the execution session could not be registered") from error
        return registration, path

    def remove(self, path: Path) -> None:
        with suppress(OSError):
            path.unlink(missing_ok=True)

    def registrations(self) -> Iterator[tuple[SessionRegistration, Path]]:
        try:
            self._validate_directory()
            paths = sorted(self.root.glob("*.json"))
        except (RuntimeRegistryError, OSError):
            return
        for path in paths:
            registration = self._read(path)
            if registration is None:
                self.remove(path)
                continue
            yield registration, path

    def process_is_current(self, registration: SessionRegistration) -> bool:
        return (
            self._identity_reader.start_ticks(registration.pid) == registration.process_start_ticks
        )

    def _ensure_directory(self) -> None:
        try:
            self.root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.root.mkdir(mode=0o700, exist_ok=True)
        except OSError as error:
            raise RuntimeRegistryError("the runtime session directory is unavailable") from error
        self._validate_directory()

    def _validate_directory(self) -> None:
        self._validate_private_directory(self.root)

    def _validate_private_directory(self, path: Path) -> None:
        try:
            metadata = path.lstat()
        except OSError as error:
            raise RuntimeRegistryError("the runtime session directory is unavailable") from error
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_uid != self._uid
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise RuntimeRegistryError("the runtime session directory is not private")

    def _read(self, path: Path) -> SessionRegistration | None:
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
            try:
                metadata = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_uid != self._uid
                    or stat.S_IMODE(metadata.st_mode) & 0o077
                    or metadata.st_size > _MAX_DESCRIPTOR_BYTES
                ):
                    return None
                payload = os.read(descriptor, _MAX_DESCRIPTOR_BYTES + 1)
            finally:
                os.close(descriptor)
            if len(payload) > _MAX_DESCRIPTOR_BYTES:
                return None
            registration = SessionRegistration.model_validate_json(payload)
            if path.name != f"{registration.session_id}.json":
                return None
            return registration
        except (OSError, ValidationError, ValueError):
            return None
