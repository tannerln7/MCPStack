from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import CandidateValidation, ConfigurationSource
from .parsing import ConfigurationParseFailure, YamlConfigurationParser
from .validation import DomainConfigurationValidator, SchemaConfigurationValidator


class ConfigurationValidationPipeline:
    """Validate source bytes without reading or mutating filesystem state."""

    def __init__(self, schema: dict[str, Any]) -> None:
        self._parser = YamlConfigurationParser()
        self._schema_validator = SchemaConfigurationValidator(schema)
        self._domain_validator = DomainConfigurationValidator()

    def validate(
        self, path: Path, source: ConfigurationSource, raw_bytes: bytes
    ) -> CandidateValidation:
        try:
            parsed = self._parser.parse(path, source, raw_bytes)
        except ConfigurationParseFailure as error:
            return CandidateValidation(
                revision=source.revision,
                configuration=None,
                issues=error.issues,
            )

        schema_issues = self._schema_validator.validate(parsed.data)
        if schema_issues:
            return CandidateValidation(
                revision=source.revision,
                configuration=None,
                issues=schema_issues,
            )

        configuration, domain_issues = self._domain_validator.validate(parsed.data)
        return CandidateValidation(
            revision=source.revision,
            configuration=configuration,
            issues=domain_issues,
        )
