from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

_STATE_ROOT = Path("/var/lib/mcp-stack")
_INSTALL_ROOT = Path("/opt/mcp-stack")
_RUNTIME_ROOT = Path("/run/mcp-stack")
_LOOPBACK_MUTATION_ORIGINS = (
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://[::1]:3000",
    "http://127.0.0.1:3100",
    "http://localhost:3100",
    "http://[::1]:3100",
)


def default_config_directory(
    environment: Mapping[str, str] | None = None,
    *,
    user_home: Path | None = None,
) -> Path:
    selected_environment = os.environ if environment is None else environment
    override = selected_environment.get("MCP_STACK_CONFIG_DIR")
    if override:
        return Path(override).expanduser()

    return _STATE_ROOT / "stacks"


def default_tunnel_profile_directory(
    environment: Mapping[str, str] | None = None, *, user_home: Path | None = None
) -> Path:
    override = (os.environ if environment is None else environment).get(
        "MCP_STACK_TUNNEL_PROFILE_DIR"
    )
    if override:
        return Path(override).expanduser()
    return _STATE_ROOT / "tunnel-profiles"


def default_secret_directory(
    environment: Mapping[str, str] | None = None, *, user_home: Path | None = None
) -> Path:
    override = (os.environ if environment is None else environment).get("MCP_STACK_SECRET_DIR")
    if override:
        return Path(override).expanduser()
    return _STATE_ROOT / "secrets"


def default_tunnel_client_executable(
    environment: Mapping[str, str] | None = None, *, user_home: Path | None = None
) -> Path:
    override = (os.environ if environment is None else environment).get("MCP_STACK_TUNNEL_CLIENT")
    if override:
        return Path(override).expanduser()
    return _INSTALL_ROOT / "tunnel-client" / "current" / "bin" / "tunnel-client"


def default_runtime_directory(environment: Mapping[str, str] | None = None) -> Path:
    selected_environment = os.environ if environment is None else environment
    override = selected_environment.get("MCP_STACK_RUNTIME_DIR")
    return Path(override).expanduser() if override else _RUNTIME_ROOT


def default_broker_socket(environment: Mapping[str, str] | None = None) -> Path:
    selected_environment = os.environ if environment is None else environment
    override = selected_environment.get("MCP_STACK_BROKER_SOCKET")
    return (
        Path(override).expanduser()
        if override
        else default_runtime_directory(environment) / "broker.sock"
    )


def allowed_mutation_origins(
    environment: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Return exact browser origins accepted for local mutations.

    Public origins are deliberately configured rather than inferred from
    forwarded headers. The FastAPI service remains loopback-bound behind the
    browser-facing Next.js service.
    """

    selected_environment = os.environ if environment is None else environment
    configured = selected_environment.get("MCP_STACK_PUBLIC_ORIGINS", "")
    origins = list(_LOOPBACK_MUTATION_ORIGINS)
    for candidate in configured.split(","):
        origin = candidate.strip()
        if not origin:
            continue
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "MCP_STACK_PUBLIC_ORIGINS must contain comma-separated exact HTTP(S) origins"
            )
        origins.append(origin)
    return tuple(dict.fromkeys(origins))
