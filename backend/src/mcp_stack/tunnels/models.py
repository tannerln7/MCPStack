from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class TunnelTarget:
    kind: Literal["stdio", "http"]
    channel: str
    command: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class TunnelProfile:
    id: str
    path: str
    revision: str
    tunnel_id: str
    base_url: str
    target: TunnelTarget
    health_listen_addr: str
    log_level: str
    log_format: str

    @property
    def associated_stack_id(self) -> str | None:
        if self.target.kind != "stdio" or not self.target.command:
            return None
        try:
            parts = shlex.split(self.target.command)
        except ValueError:
            return None
        if len(parts) == 3 and Path(parts[0]).name == "mcpctl" and parts[1] == "stdio":
            return parts[2].split("/", 1)[0]
        return None


@dataclass(frozen=True)
class TunnelProfileSummary:
    profile: TunnelProfile | None
    path: str
    valid: bool
    diagnostic: str | None = None


@dataclass(frozen=True)
class TunnelProfileCreate:
    id: str
    tunnel_id: str
    target_kind: Literal["stdio", "http"]
    channel: str = "main"
    stack_target: str | None = None
    url: str | None = None
    base_url: str = "https://api.openai.com"
    health_listen_addr: str = "127.0.0.1:0"
    restart: Literal["never", "on-failure"] = "on-failure"


@dataclass(frozen=True)
class TunnelClientStatus:
    installed: bool
    executable: str
    version: str | None
    profile_directory: str
    credential_state: Literal["configured", "missing", "inaccessible"]
