from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import ConfigurationIssue, ConfigurationSource, ParsedConfiguration


class ConfigurationParseFailure(Exception):
    def __init__(self, issues: tuple[ConfigurationIssue, ...]) -> None:
        self.issues = issues
        super().__init__(issues[0].message)


class YamlConfigurationParser:
    def parse(
        self, path: Path, source: ConfigurationSource, raw_bytes: bytes
    ) -> ParsedConfiguration:
        try:
            document = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ConfigurationParseFailure(
                (
                    ConfigurationIssue(
                        stage="parsing",
                        code="invalid-text-encoding",
                        message="configuration source must be UTF-8 text",
                    ),
                )
            ) from error
        try:
            parsed: Any = yaml.safe_load(document)
        except yaml.MarkedYAMLError as error:
            mark = error.problem_mark
            raise ConfigurationParseFailure(
                (
                    ConfigurationIssue(
                        stage="parsing",
                        code="invalid-yaml",
                        message=error.problem or str(error),
                        line=mark.line + 1 if mark else None,
                        column=mark.column + 1 if mark else None,
                    ),
                )
            ) from error
        except yaml.YAMLError as error:
            raise ConfigurationParseFailure(
                (
                    ConfigurationIssue(
                        stage="parsing",
                        code="source-unreadable",
                        message=str(error),
                    ),
                )
            ) from error
        if not isinstance(parsed, dict):
            raise ConfigurationParseFailure(
                (
                    ConfigurationIssue(
                        stage="parsing",
                        code="invalid-document-root",
                        message="document root must be an object",
                    ),
                )
            )
        return ParsedConfiguration(source=source, path=path, document=document, data=parsed)
