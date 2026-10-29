from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mcp_stack.main import create_app


@pytest.fixture
def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def client(repository_root: Path, tmp_path: Path) -> TestClient:
    app = create_app(
        config_dir=repository_root / "schemas" / "examples",
        schema_path=repository_root / "schemas" / "domain" / "stack-config.schema.json",
        runtime_dir=tmp_path / "runtime",
        tunnel_profile_dir=tmp_path / "tunnel-profiles",
        tunnel_client_executable=tmp_path / "bin" / "tunnel-client",
        secret_dir=tmp_path / "secrets",
        allowed_hosts=("testserver",),
        allowed_mutation_origins=("http://testserver",),
    )
    return TestClient(
        app,
        headers={"Origin": "http://testserver", "X-MCP-Stack-Mutation": "1"},
    )
