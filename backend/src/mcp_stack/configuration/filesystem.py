from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import (
    CandidateValidation,
    ConfigurationDiagnostic,
    ConfigurationIssue,
    ConfigurationSource,
    RepositorySnapshot,
    StackRecord,
)
from .pipeline import ConfigurationValidationPipeline
from .schema import load_stack_schema


class FilesystemStackRepository:
    def __init__(self, config_dir: Path, schema_path: Path | None = None) -> None:
        self._config_dir = config_dir.resolve()
        schema = load_stack_schema(schema_path)
        self._schema = schema
        self._validation_pipeline = ConfigurationValidationPipeline(schema)

    @property
    def schema(self) -> dict[str, Any]:
        return self._schema

    def discover(self) -> RepositorySnapshot:
        if not self._config_dir.is_dir():
            return RepositorySnapshot(
                records=(),
                diagnostics=(
                    ConfigurationDiagnostic(
                        issues=(
                            ConfigurationIssue(
                                stage="discovery",
                                code="configuration-directory-missing",
                                message="configured stack directory does not exist",
                            ),
                        )
                    ),
                ),
                scanned_source_count=0,
            )

        paths = self._candidate_paths()
        records: list[StackRecord] = []
        diagnostics: list[ConfigurationDiagnostic] = []
        for path in paths:
            try:
                source, raw_bytes = self._read_source(path)
            except (OSError, ValueError) as error:
                diagnostics.append(
                    ConfigurationDiagnostic(
                        source_path=path.name,
                        issues=(
                            ConfigurationIssue(
                                stage="discovery",
                                code="source-unreadable",
                                message=str(error),
                            ),
                        ),
                    )
                )
                continue
            validation = self._validation_pipeline.validate(path, source, raw_bytes)
            if not validation.valid or validation.configuration is None:
                diagnostics.append(ConfigurationDiagnostic(source=source, issues=validation.issues))
                continue
            records.append(
                StackRecord(
                    configuration=validation.configuration,
                    source=source,
                    source_path=path.resolve(strict=True),
                    document=raw_bytes.decode("utf-8"),
                )
            )

        records, duplicate_diagnostics = self._remove_duplicate_stack_ids(records)
        diagnostics.extend(duplicate_diagnostics)
        return RepositorySnapshot(
            records=tuple(sorted(records, key=lambda item: item.configuration.name.casefold())),
            diagnostics=tuple(sorted(diagnostics, key=self._diagnostic_sort_key)),
            scanned_source_count=len(paths),
        )

    def list(self) -> list[StackRecord]:
        return list(self.discover().records)

    def get(self, stack_id: str) -> StackRecord | None:
        return next(
            (record for record in self.discover().records if record.configuration.id == stack_id),
            None,
        )

    def validate_candidate(self, stack_id: str, document: str) -> CandidateValidation | None:
        record = self.get(stack_id)
        if record is None:
            return None
        raw_bytes = document.encode("utf-8")
        candidate_source = replace(
            record.source,
            revision=hashlib.sha256(raw_bytes).hexdigest(),
            size_bytes=len(raw_bytes),
        )
        result = self._validation_pipeline.validate(
            record.source_path,
            candidate_source,
            raw_bytes,
        )
        if result.configuration is None or result.configuration.id == stack_id:
            return result
        return CandidateValidation(
            revision=result.revision,
            configuration=None,
            issues=(
                ConfigurationIssue(
                    stage="domain",
                    code="stack-id-mismatch",
                    path="/id",
                    message="candidate Stack identity does not match the edited Stack",
                ),
            ),
        )

    def validate_new_candidate(self, stack_id: str, document: str) -> CandidateValidation:
        raw_bytes = document.encode("utf-8")
        source = ConfigurationSource(
            path=f"{stack_id}.yaml",
            format="yaml",
            revision=hashlib.sha256(raw_bytes).hexdigest(),
            size_bytes=len(raw_bytes),
            modified_at=datetime.now(UTC),
        )
        result = self._validation_pipeline.validate(
            self._config_dir / source.path,
            source,
            raw_bytes,
        )
        if result.configuration is not None and result.configuration.id != stack_id:
            return CandidateValidation(
                revision=result.revision,
                configuration=None,
                issues=(
                    ConfigurationIssue(
                        stage="domain",
                        code="stack-id-mismatch",
                        path="/id",
                        message="candidate Stack identity does not match the requested Stack",
                    ),
                ),
            )
        if result.configuration is not None and any(
            record.configuration.id == stack_id for record in self.discover().records
        ):
            return CandidateValidation(
                revision=result.revision,
                configuration=None,
                issues=(
                    ConfigurationIssue(
                        stage="domain",
                        code="duplicate-stack-id",
                        path="/id",
                        message="Candidate Stack id conflicts with another configured Stack",
                    ),
                ),
            )
        return result

    def _candidate_paths(self) -> list[Path]:
        return [
            path
            for path in sorted(self._config_dir.iterdir())
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}
        ]

    def _read_source(self, path: Path) -> tuple[ConfigurationSource, bytes]:
        resolved = path.resolve(strict=True)
        if resolved.parent != self._config_dir:
            raise ValueError(f"configuration path escapes configured directory: {path.name}")
        raw_bytes = resolved.read_bytes()
        stat = resolved.stat()
        return (
            ConfigurationSource(
                path=path.relative_to(self._config_dir).as_posix(),
                format="yaml",
                revision=hashlib.sha256(raw_bytes).hexdigest(),
                size_bytes=len(raw_bytes),
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            ),
            raw_bytes,
        )

    @staticmethod
    def _remove_duplicate_stack_ids(
        records: list[StackRecord],
    ) -> tuple[list[StackRecord], list[ConfigurationDiagnostic]]:
        by_id: defaultdict[str, list[StackRecord]] = defaultdict(list)
        for record in records:
            by_id[record.configuration.id].append(record)
        duplicate_ids = {stack_id for stack_id, values in by_id.items() if len(values) > 1}
        diagnostics = [
            ConfigurationDiagnostic(
                source=record.source,
                issues=(
                    ConfigurationIssue(
                        stage="domain",
                        code="duplicate-stack-id",
                        path="/id",
                        message="Stack identity is duplicated across configured sources",
                    ),
                ),
            )
            for stack_id in sorted(duplicate_ids)
            for record in by_id[stack_id]
        ]
        valid_records = [
            record for record in records if record.configuration.id not in duplicate_ids
        ]
        return valid_records, diagnostics

    @staticmethod
    def _diagnostic_sort_key(diagnostic: ConfigurationDiagnostic) -> str:
        return diagnostic.source.path if diagnostic.source else diagnostic.source_path or ""
