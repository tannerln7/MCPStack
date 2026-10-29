"""Keep installable names, resource identifiers, and runtime defaults in sync."""

import tomllib
from pathlib import Path

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


def test_package_entry_points_and_schema_namespace(repository_root: Path) -> None:
    project = tomllib.loads((repository_root / "backend/pyproject.toml").read_text())
    assert project["project"]["name"] == "mcp-stack-backend"
    assert project["project"]["scripts"] == {
        "mcpctl": "mcp_stack.cli:main",
        "mcp-stack-api": "mcp_stack.server:main",
        "mcp-stack-broker": "mcp_stack.broker.server:main",
    }
    assert project["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/mcp_stack"]
    assert load_stack_schema()["$id"] == (
        "https://mcp-stack.local/schemas/domain/stack-config.schema.json"
    )


def test_all_runtime_locations_support_the_new_environment_prefix(tmp_path: Path) -> None:
    locations = {
        "CONFIG_DIR": default_config_directory,
        "SECRET_DIR": default_secret_directory,
        "TUNNEL_PROFILE_DIR": default_tunnel_profile_directory,
        "TUNNEL_CLIENT": default_tunnel_client_executable,
        "RUNTIME_DIR": default_runtime_directory,
        "BROKER_SOCKET": default_broker_socket,
    }
    for setting, resolve in locations.items():
        target = tmp_path / setting.lower()
        assert resolve({f"MCP_STACK_{setting}": str(target)}) == target
    assert default_broker_socket({"MCP_STACK_RUNTIME_DIR": str(tmp_path)}) == (
        tmp_path / "broker.sock"
    )
    assert "https://mcp.example.com" in allowed_mutation_origins(
        {"MCP_STACK_PUBLIC_ORIGINS": "https://mcp.example.com"}
    )


def test_old_environment_names_do_not_create_a_second_authority(tmp_path: Path) -> None:
    old_prefix = "MCP_" + "CONTROL_PLANE_"
    environment = {
        old_prefix + "CONFIG_DIR": str(tmp_path / "old"),
        old_prefix + "RUNTIME_DIR": str(tmp_path / "old-runtime"),
        old_prefix + "PUBLIC_ORIGINS": "https://old.example.com",
    }
    assert default_config_directory(environment) == Path("/var/lib/mcp-stack/stacks")
    assert default_runtime_directory(environment) == Path("/run/mcp-stack")
    assert "https://old.example.com" not in allowed_mutation_origins(environment)
