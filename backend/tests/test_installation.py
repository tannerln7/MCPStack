from __future__ import annotations

import io
import subprocess
from pathlib import Path

from mcp_stack import cli
from mcp_stack.configuration import (
    allowed_mutation_origins,
    default_broker_socket,
    default_config_directory,
    default_runtime_directory,
    default_secret_directory,
    default_tunnel_client_executable,
    default_tunnel_profile_directory,
    load_stack_schema,
)


class CapturingBroker:
    def __init__(self, status: int = 0) -> None:
        self.target: str | None = None
        self.status = status

    def launch_stdio(self, target, stdin, stdout, stderr) -> int:
        self.target = target
        return self.status


def test_packaged_schema_is_available_without_a_filesystem_path() -> None:
    schema = load_stack_schema()

    assert schema["$id"].endswith("/stack-config.schema.json")
    assert schema["properties"]["components"]["minItems"] == 1


def test_service_paths_are_stable_and_overridable(tmp_path: Path) -> None:
    assert default_config_directory({}) == Path("/var/lib/mcp-stack/stacks")
    assert default_secret_directory({}) == Path("/var/lib/mcp-stack/secrets")
    assert default_tunnel_profile_directory({}) == Path("/var/lib/mcp-stack/tunnel-profiles")
    assert default_tunnel_client_executable({}) == Path(
        "/opt/mcp-stack/tunnel-client/current/bin/tunnel-client"
    )
    assert default_runtime_directory({}) == Path("/run/mcp-stack")
    assert default_broker_socket({}) == Path("/run/mcp-stack/broker.sock")

    assert (
        default_config_directory({"MCP_STACK_CONFIG_DIR": str(tmp_path / "stacks")})
        == tmp_path / "stacks"
    )
    assert (
        default_secret_directory({"MCP_STACK_SECRET_DIR": str(tmp_path / "secrets")})
        == tmp_path / "secrets"
    )
    assert (
        default_broker_socket({"MCP_STACK_BROKER_SOCKET": str(tmp_path / "broker.sock")})
        == tmp_path / "broker.sock"
    )


def test_public_mutation_origins_are_exact_and_additive() -> None:
    origins = allowed_mutation_origins({"MCP_STACK_PUBLIC_ORIGINS": "https://mcp.example.com"})

    assert "http://127.0.0.1:3100" in origins
    assert "https://mcp.example.com" in origins
    assert "https://attacker.example" not in origins


def test_cli_delegates_to_service_broker_without_loading_local_configuration() -> None:
    broker = CapturingBroker()

    status = cli.run(
        ["stdio", "markitdown"],
        stderr=io.StringIO(),
        stdin_buffer=io.BytesIO(),
        stdout_buffer=io.BytesIO(),
        stderr_buffer=io.BytesIO(),
        broker_client=broker,  # type: ignore[arg-type]
    )

    assert status == 0
    assert broker.target == "markitdown"


def test_service_installer_keeps_python_entrypoint_prefix_stable(
    repository_root: Path,
) -> None:
    installer = (repository_root / "scripts/install-service.sh").read_text()

    assert "/opt/mcp-stack/backend-releases/" in installer
    assert "backend.next" not in installer
    assert "systemctl reset-failed" in installer
    assert "systemctl is-active --quiet" in installer
    assert "SupplementaryGroups=systemd-journal" in installer
    assert "GHIDRA" not in installer
    assert "ghidra" not in installer


def test_base_installer_uses_shared_non_secret_settings(repository_root: Path) -> None:
    installer = (repository_root / "scripts/install-service.sh").read_text()
    assert installer.count("EnvironmentFile=/etc/mcp-stack/deployment.env") == 2
    assert "deployment-settings.py" in installer
    assert '"${repo_root}"/config/stacks/*.yaml' not in installer
    syntax = subprocess.run(
        ["bash", "-n", str(repository_root / "scripts/install-service.sh")],
        capture_output=True,
        timeout=5,
    )
    assert syntax.returncode == 0
