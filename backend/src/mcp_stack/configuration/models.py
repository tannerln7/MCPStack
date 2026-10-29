from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from mcp_stack.domain.configuration import StackConfiguration

ValidationStage = Literal["discovery", "parsing", "schema", "domain"]


@dataclass(frozen=True)
class ConfigurationIssue:
    stage: ValidationStage
    message: str
    path: str = "/"
    code: str | None = None
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True)
class ConfigurationSource:
    path: str
    format: Literal["yaml"]
    revision: str
    size_bytes: int
    modified_at: datetime


@dataclass(frozen=True)
class ParsedConfiguration:
    source: ConfigurationSource
    path: Path
    document: str
    data: dict[str, Any]


@dataclass(frozen=True)
class ConfigurationDiagnostic:
    issues: tuple[ConfigurationIssue, ...]
    source: ConfigurationSource | None = None
    source_path: str | None = None


@dataclass(frozen=True)
class StackRecord:
    configuration: StackConfiguration
    source: ConfigurationSource
    source_path: Path
    document: str

    @property
    def revision(self) -> str:
        return self.source.revision


@dataclass(frozen=True)
class RepositorySnapshot:
    records: tuple[StackRecord, ...]
    diagnostics: tuple[ConfigurationDiagnostic, ...]
    scanned_source_count: int


@dataclass(frozen=True)
class CandidateValidation:
    revision: str
    configuration: StackConfiguration | None
    issues: tuple[ConfigurationIssue, ...]

    @property
    def valid(self) -> bool:
        return self.configuration is not None and not self.issues
