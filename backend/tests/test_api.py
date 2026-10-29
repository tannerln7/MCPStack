import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from mcp_stack.configuration import FilesystemStackRepository
from mcp_stack.execution import ExecutionTarget, StdioExecutionPlan
from mcp_stack.main import create_app
from mcp_stack.runtime import SessionRegistry


def test_api_uses_public_brand_without_changing_contract_identifiers(client: TestClient) -> None:
    assert client.get("/openapi.json").json()["info"]["title"] == "MCPStack API"


def test_lists_configured_stacks(client: TestClient) -> None:
    response = client.get("/api/v1/stacks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stacks"][0]["id"] == "local-development"
    assert payload["stacks"][0]["componentCount"] == 3
    assert payload["stacks"][0]["source"]["path"] == "local-development.yaml"
    assert payload["stacks"][0]["source"]["format"] == "yaml"
    assert payload["invalidSources"] == []
    assert payload["scannedSourceCount"] == 1


def test_stack_view_separates_configuration_and_observations(client: TestClient) -> None:
    response = client.get("/api/v1/stacks/local-development")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configuration"]["components"][0]["id"] == "filesystem-mcp"
    assert payload["source"]["path"] == "local-development.yaml"
    assert payload["source"]["revision"] == payload["observations"]["configurationRevision"]
    assert payload["observations"]["components"][0]["status"] == "not-observed"
    assert "processInstances" in payload["observations"]
    assert "processInstances" not in payload["configuration"]


def test_discovery_exposes_invalid_sources_without_hiding_valid_stacks(
    repository_root: Path, tmp_path: Path
) -> None:
    valid = yaml.safe_load(
        (repository_root / "schemas" / "examples" / "local-development.yaml").read_text()
    )
    (tmp_path / "valid.yaml").write_text(yaml.safe_dump(valid))
    (tmp_path / "invalid.yaml").write_text("components: [")
    app = create_app(
        config_dir=tmp_path,
        schema_path=repository_root / "schemas" / "domain" / "stack-config.schema.json",
        allowed_hosts=("testserver",),
    )

    response = TestClient(app).get("/api/v1/stacks")

    assert response.status_code == 200
    payload = response.json()
    assert [stack["id"] for stack in payload["stacks"]] == ["local-development"]
    assert payload["invalidSources"][0]["sourcePath"] == "invalid.yaml"
    assert payload["invalidSources"][0]["issues"][0]["stage"] == "parsing"
    assert str(tmp_path) not in response.text


def test_unknown_stack_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/stacks/missing")

    assert response.status_code == 404


def test_stack_secret_boundary_is_write_only(client: TestClient) -> None:
    marker = "must-never-return-from-the-web-boundary"

    stored = client.put(
        "/api/v1/stacks/local-development/secrets/docs-token",
        json={"value": marker},
    )
    listed = client.get("/api/v1/stacks/local-development/secrets")
    cleared = client.delete(
        "/api/v1/stacks/local-development/secrets/docs-token",
        headers={"Content-Type": "application/json"},
    )

    assert stored.status_code == 200
    assert stored.json()["state"] == "configured"
    assert listed.json()[0]["state"] == "configured"
    assert cleared.json()["state"] == "missing"
    assert marker not in stored.text
    assert marker not in listed.text
    assert marker not in cleared.text


def test_exposes_stack_contract(client: TestClient) -> None:
    response = client.get("/api/v1/contracts/stack-configuration")

    assert response.status_code == 200
    assert response.json()["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "component" in response.json()["$defs"]


def test_runtime_snapshot_conforms_to_shared_schema(
    client: TestClient, repository_root: Path
) -> None:
    schema = json.loads(
        (repository_root / "schemas" / "api" / "runtime-snapshot.schema.json").read_text()
    )
    snapshot = client.get("/api/v1/stacks/local-development").json()["observations"]

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(snapshot)


def test_exposes_active_execution_without_claiming_mcp_connectivity(
    repository_root: Path, tmp_path: Path
) -> None:
    config_dir = repository_root / "schemas" / "examples"
    schema_path = repository_root / "schemas" / "domain" / "stack-config.schema.json"
    record = FilesystemStackRepository(config_dir, schema_path).get("local-development")
    assert record is not None
    runtime_dir = tmp_path / "runtime"
    registry = SessionRegistry(runtime_dir / "sessions")
    _, registration_path = registry.create(
        StdioExecutionPlan(
            target=ExecutionTarget(
                "local-development",
                "filesystem-mcp",
                "filesystem-mcp",
                "filesystem-command",
            ),
            configuration_revision=record.revision,
            argv=("server",),
            working_directory=None,
            environment={"SECRET": "must-not-appear"},
        )
    )
    app = create_app(
        config_dir=config_dir,
        schema_path=schema_path,
        runtime_dir=runtime_dir,
        allowed_hosts=("testserver",),
    )

    response = TestClient(app).get("/api/v1/stacks/local-development/observations")
    registration_path.unlink()

    assert response.status_code == 200
    payload = response.json()
    assert payload["components"][0]["status"] == "running"
    assert payload["executionSessions"][0]["state"] == "active"
    assert payload["executionSessions"][0]["configurationRevisionMatches"] is True
    assert payload["mcpSessions"] == []
    assert "must-not-appear" not in response.text


def test_unknown_stack_observations_return_404(client: TestClient) -> None:
    assert client.get("/api/v1/stacks/missing/observations").status_code == 404


def test_gets_complete_editable_source_without_an_absolute_path(client: TestClient) -> None:
    response = client.get("/api/v1/stacks/local-development/source")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stackId"] == "local-development"
    assert payload["source"]["path"] == "local-development.yaml"
    assert payload["mediaType"] == "application/yaml"
    assert payload["encoding"] == "utf-8"
    assert "id: local-development" in payload["document"]
    assert "/schemas/examples" not in response.text


def test_previews_valid_candidate_without_modifying_source(
    client: TestClient, repository_root: Path
) -> None:
    source_path = repository_root / "schemas" / "examples" / "local-development.yaml"
    original = source_path.read_bytes()
    candidate = yaml.safe_load(original)
    candidate["name"] = "Previewed Stack"
    candidate_document = yaml.safe_dump(candidate)

    response = client.post(
        "/api/v1/stacks/local-development/validation-previews",
        json={"document": candidate_document},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["issues"] == []
    assert payload["configuration"]["name"] == "Previewed Stack"
    assert len(payload["candidateRevision"]) == 64
    assert source_path.read_bytes() == original


def test_preview_returns_structured_candidate_diagnostics(client: TestClient) -> None:
    response = client.post(
        "/api/v1/stacks/local-development/validation-previews",
        json={"document": "components: ["},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["configuration"] is None
    assert payload["issues"][0]["stage"] == "parsing"
    assert payload["issues"][0]["line"] == 1
    assert payload["issues"][0]["column"] is not None


def test_source_and_preview_unknown_stack_return_404(client: TestClient) -> None:
    assert client.get("/api/v1/stacks/missing/source").status_code == 404
    assert (
        client.post(
            "/api/v1/stacks/missing/validation-previews",
            json={"document": "id: missing"},
        ).status_code
        == 404
    )


def test_preview_request_rejects_unknown_fields_and_oversized_documents(
    client: TestClient,
) -> None:
    unknown_field = client.post(
        "/api/v1/stacks/local-development/validation-previews",
        json={"document": "id: local-development", "write": True},
    )
    oversized = client.post(
        "/api/v1/stacks/local-development/validation-previews",
        json={"document": "x" * 1_048_577},
    )

    assert unknown_field.status_code == 422
    assert oversized.status_code == 422


def test_request_validation_does_not_echo_source_content(client: TestClient) -> None:
    marker = "source-secret-must-not-be-echoed"

    response = client.post(
        "/api/v1/stacks/local-development/validation-previews",
        json={"document": marker + ("x" * 1_048_576)},
    )

    assert response.status_code == 422
    assert marker not in response.text
    assert response.json()["detail"][0]["location"] == ["body", "document"]


def test_api_accepts_loopback_and_rejects_untrusted_host_header(
    repository_root: Path,
) -> None:
    app = create_app(
        config_dir=repository_root / "schemas" / "examples",
        schema_path=repository_root / "schemas" / "domain" / "stack-config.schema.json",
    )
    client = TestClient(app, base_url="http://127.0.0.1")

    assert client.get("/api/v1/stacks").status_code == 200
    assert client.get("/api/v1/stacks", headers={"host": "attacker.example"}).status_code == 400
