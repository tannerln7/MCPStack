import hashlib
import json
import tomllib
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from mcp_stack.configuration import (
    FilesystemStackRepository,
    packaged_stack_schema_text,
)


def _example(repository_root: Path) -> dict:
    return yaml.safe_load(
        (repository_root / "schemas" / "examples" / "local-development.yaml").read_text()
    )


def _repository(repository_root: Path, config_dir: Path) -> FilesystemStackRepository:
    return FilesystemStackRepository(config_dir)


def test_packaged_schema_matches_shared_contract(repository_root: Path) -> None:
    shared = (repository_root / "schemas" / "domain" / "stack-config.schema.json").read_text()

    assert packaged_stack_schema_text() == shared


def test_example_conforms_to_shared_schema(repository_root: Path) -> None:
    schema = json.loads(
        (repository_root / "schemas" / "domain" / "stack-config.schema.json").read_text()
    )
    fixture = yaml.safe_load(
        (repository_root / "schemas" / "examples" / "local-development.yaml").read_text()
    )

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(fixture)


def test_loader_preserves_domain_identities(repository_root: Path) -> None:
    repository = FilesystemStackRepository(
        repository_root / "schemas" / "examples",
        repository_root / "schemas" / "domain" / "stack-config.schema.json",
    )

    record = repository.get("local-development")

    assert record is not None
    assert record.configuration.components[0].subject_kind == "mcp-server"
    assert record.configuration.applications[0].id == "docs-app"
    assert record.configuration.tunnels[0].id == "public-tunnel"
    assert len(record.revision) == 64


def test_checked_in_examples_discover_supported_configuration_types(repository_root: Path) -> None:
    snapshot = _repository(repository_root, repository_root / "config" / "stacks").discover()

    assert sorted(record.configuration.id for record in snapshot.records) == [
        "example-application",
        "example-composite",
        "example-http",
        "example-stdio",
    ]
    assert snapshot.scanned_source_count == 4
    assert snapshot.diagnostics == ()
    records = {record.configuration.id: record.configuration for record in snapshot.records}
    assert records["example-stdio"].transports[0].kind == "stdio"
    assert records["example-stdio"].secret_sources[0].provider == "control-plane-store"
    assert records["example-http"].transports[0].kind == "streamable-http"
    assert records["example-application"].lifecycle_policies[0].provider == "system-service"
    composite = records["example-composite"]
    assert {component.subject_kind for component in composite.components} == {
        "application",
        "mcp-server",
    }
    assert composite.dependencies[0].depends_on_ref == "server"
    assert composite.mcp_servers[0].controls_application_ref == "server"


def test_example_environment_is_non_secret(repository_root: Path) -> None:
    environment = tomllib.loads(
        (repository_root / "config/environments/example-stdio/mise.toml").read_text()
    )
    assert environment == {"tools": {"node": "24"}}


def test_discovers_multiple_stacks_and_preserves_valid_sources(
    repository_root: Path, tmp_path: Path
) -> None:
    first = _example(repository_root)
    second = _example(repository_root)
    second["id"] = "second-stack"
    second["name"] = "Second Stack"
    (tmp_path / "first.yaml").write_text(yaml.safe_dump(first))
    (tmp_path / "second.yml").write_text(yaml.safe_dump(second))
    (tmp_path / "broken.yaml").write_text("name: [unterminated")
    (tmp_path / "ignored.txt").write_text("not configuration")

    snapshot = _repository(repository_root, tmp_path).discover()

    assert [record.configuration.id for record in snapshot.records] == [
        "local-development",
        "second-stack",
    ]
    assert snapshot.scanned_source_count == 3
    assert snapshot.diagnostics[0].source is not None
    assert snapshot.diagnostics[0].source.path == "broken.yaml"
    assert snapshot.diagnostics[0].issues[0].stage == "parsing"
    assert snapshot.diagnostics[0].issues[0].line == 1


def test_reports_schema_and_domain_validation_stages(repository_root: Path, tmp_path: Path) -> None:
    schema_invalid = _example(repository_root)
    schema_invalid.pop("id")
    domain_invalid = _example(repository_root)
    domain_invalid["id"] = "domain-invalid"
    domain_invalid["commands"][0]["runtimeRef"] = "missing-runtime"
    (tmp_path / "schema.yaml").write_text(yaml.safe_dump(schema_invalid))
    (tmp_path / "domain.yaml").write_text(yaml.safe_dump(domain_invalid))

    snapshot = _repository(repository_root, tmp_path).discover()
    issues = {
        diagnostic.source.path: diagnostic.issues
        for diagnostic in snapshot.diagnostics
        if diagnostic.source is not None
    }

    assert snapshot.records == ()
    assert issues["schema.yaml"][0].stage == "schema"
    assert issues["schema.yaml"][0].path == "/"
    assert issues["domain.yaml"][0].stage == "domain"
    assert issues["domain.yaml"][0].message == (
        "configuration contains a reference to an unknown resource"
    )
    assert "missing-runtime" not in issues["domain.yaml"][0].message


def test_duplicate_environment_binding_names_fail_domain_validation(
    repository_root: Path, tmp_path: Path
) -> None:
    duplicate = _example(repository_root)
    duplicate["commands"][0]["environment"] = [
        {"name": "DUPLICATE", "valueFrom": {"literal": "first"}},
        {"name": "DUPLICATE", "valueFrom": {"literal": "second"}},
    ]
    (tmp_path / "duplicate.yaml").write_text(yaml.safe_dump(duplicate))

    snapshot = _repository(repository_root, tmp_path).discover()

    assert snapshot.records == ()
    assert snapshot.diagnostics[0].issues[0].stage == "domain"
    assert "duplicate environment binding names" in snapshot.diagnostics[0].issues[0].message


def test_duplicate_stack_ids_are_removed_from_discovery(
    repository_root: Path, tmp_path: Path
) -> None:
    stack = _example(repository_root)
    (tmp_path / "first.yaml").write_text(yaml.safe_dump(stack))
    (tmp_path / "second.yaml").write_text(yaml.safe_dump(stack))

    snapshot = _repository(repository_root, tmp_path).discover()

    assert snapshot.records == ()
    assert len(snapshot.diagnostics) == 2
    assert {item.issues[0].code for item in snapshot.diagnostics} == {"duplicate-stack-id"}


def test_missing_configuration_directory_is_a_discovery_issue(
    repository_root: Path, tmp_path: Path
) -> None:
    snapshot = _repository(repository_root, tmp_path / "missing").discover()

    assert snapshot.records == ()
    assert snapshot.scanned_source_count == 0
    assert snapshot.diagnostics[0].source is None
    assert snapshot.diagnostics[0].issues[0].stage == "discovery"


def test_candidate_validation_uses_pipeline_without_modifying_source(
    repository_root: Path, tmp_path: Path
) -> None:
    source_path = tmp_path / "stack.yaml"
    original = "# retained source comment\n" + yaml.safe_dump(_example(repository_root))
    source_path.write_text(original)
    repository = _repository(repository_root, tmp_path)
    candidate_data = _example(repository_root)
    candidate_data["name"] = "Candidate name"
    candidate = yaml.safe_dump(candidate_data)

    result = repository.validate_candidate("local-development", candidate)

    assert result is not None
    assert result.valid
    assert result.configuration is not None
    assert result.configuration.name == "Candidate name"
    assert result.revision == hashlib.sha256(candidate.encode()).hexdigest()
    assert source_path.read_text() == original


def test_candidate_validation_reports_parsing_schema_and_domain_issues(
    repository_root: Path, tmp_path: Path
) -> None:
    source_path = tmp_path / "stack.yaml"
    source_path.write_text(yaml.safe_dump(_example(repository_root)))
    repository = _repository(repository_root, tmp_path)

    parsing = repository.validate_candidate("local-development", "components: [")
    schema_data = _example(repository_root)
    schema_data.pop("id")
    schema = repository.validate_candidate("local-development", yaml.safe_dump(schema_data))
    domain_data = _example(repository_root)
    domain_data["commands"][0]["runtimeRef"] = "missing-runtime"
    domain = repository.validate_candidate("local-development", yaml.safe_dump(domain_data))

    assert parsing is not None and parsing.issues[0].stage == "parsing"
    assert parsing.issues[0].line == 1
    assert schema is not None and schema.issues[0].stage == "schema"
    assert domain is not None and domain.issues[0].stage == "domain"


def test_candidate_validation_preserves_stack_identity(
    repository_root: Path, tmp_path: Path
) -> None:
    source_path = tmp_path / "stack.yaml"
    source_path.write_text(yaml.safe_dump(_example(repository_root)))
    repository = _repository(repository_root, tmp_path)
    candidate = _example(repository_root)
    candidate["id"] = "renamed-stack"

    result = repository.validate_candidate("local-development", yaml.safe_dump(candidate))

    assert result is not None
    assert not result.valid
    assert result.configuration is None
    assert result.issues[0].code == "stack-id-mismatch"
    assert result.issues[0].path == "/id"


def test_candidate_validation_rejects_hard_dependency_cycles(
    repository_root: Path, tmp_path: Path
) -> None:
    source_path = tmp_path / "stack.yaml"
    source_path.write_text(yaml.safe_dump(_example(repository_root)))
    repository = _repository(repository_root, tmp_path)
    candidate = _example(repository_root)
    candidate["dependencies"] = [
        {
            "componentRef": "filesystem-mcp",
            "dependsOnRef": "docs-app",
            "requirement": "ready",
            "strength": "hard",
        },
        {
            "componentRef": "docs-app",
            "dependsOnRef": "public-tunnel",
            "requirement": "ready",
            "strength": "hard",
        },
        {
            "componentRef": "public-tunnel",
            "dependsOnRef": "filesystem-mcp",
            "requirement": "ready",
            "strength": "hard",
        },
    ]

    result = repository.validate_candidate("local-development", yaml.safe_dump(candidate))

    assert result is not None
    assert not result.valid
    assert result.issues[0].stage == "domain"
    assert result.issues[0].message == "value does not satisfy the domain contract"
