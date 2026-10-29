from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from mcp_stack.domain.configuration import StackConfiguration

from .models import ConfigurationIssue


def _pointer(parts: Iterable[object]) -> str:
    encoded = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return f"/{'/'.join(encoded)}" if encoded else "/"


class SchemaConfigurationValidator:
    def __init__(self, schema: dict[str, Any]) -> None:
        Draft202012Validator.check_schema(schema)
        self._validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def validate(self, data: dict[str, Any]) -> tuple[ConfigurationIssue, ...]:
        return tuple(
            ConfigurationIssue(
                stage="schema",
                code=str(error.validator) if error.validator else None,
                path=_pointer(error.absolute_path),
                message=self._safe_message(error.validator, error.message),
            )
            for error in sorted(self._validator.iter_errors(data), key=lambda item: list(item.path))
        )

    @staticmethod
    def _safe_message(validator: object, original: str) -> str:
        # Schema errors can embed rejected values. Source documents are sensitive,
        # so retain useful structure without reflecting candidate data.
        if validator == "required":
            return "object is missing one or more required properties"
        if validator == "additionalProperties":
            return "object contains unsupported properties"
        messages = {
            "type": "value has the wrong type",
            "enum": "value is not one of the allowed options",
            "const": "value does not match the required constant",
            "pattern": "value does not match the required pattern",
            "oneOf": "value does not match exactly one supported shape",
            "anyOf": "value does not match a supported shape",
            "minLength": "value is shorter than the minimum length",
            "maxLength": "value exceeds the maximum length",
            "minimum": "value is below the allowed minimum",
            "maximum": "value exceeds the allowed maximum",
        }
        return messages.get(str(validator), "value does not satisfy the configuration contract")


class DomainConfigurationValidator:
    def validate(
        self, data: dict[str, Any]
    ) -> tuple[StackConfiguration | None, tuple[ConfigurationIssue, ...]]:
        try:
            return StackConfiguration.model_validate(data), ()
        except ValidationError as error:
            return None, tuple(
                ConfigurationIssue(
                    stage="domain",
                    code=str(issue["type"]),
                    path=_pointer(issue["loc"]),
                    message=self._safe_message(str(issue["type"]), str(issue["msg"])),
                )
                for issue in error.errors(include_url=False)
            )

    @staticmethod
    def _safe_message(code: str, original: str) -> str:
        if "references unknown" in original:
            return "configuration contains a reference to an unknown resource"
        if "duplicate environment binding names" in original:
            return "command contains duplicate environment binding names"
        if original.startswith("duplicate "):
            return "configuration contains duplicate resource identities"
        messages = {
            "missing": "required value is missing",
            "literal_error": "value is not one of the allowed options",
            "string_pattern_mismatch": "value does not match the required pattern",
            "string_too_short": "value is shorter than the minimum length",
            "string_too_long": "value exceeds the maximum length",
            "extra_forbidden": "object contains unsupported properties",
        }
        return messages.get(code, "value does not satisfy the domain contract")
