from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from mcp_stack.domain.configuration import (
    Command,
    EnvironmentSourceValue,
    LiteralEnvironmentValue,
    SecretSource,
    SecretSourceValue,
    StackConfiguration,
)
from mcp_stack.secrets import ControlPlaneSecretStore, SecretStoreError

from .errors import StdioExecutionError


class EnvironmentProvider(Protocol):
    def inherited_environment(self) -> Mapping[str, str]: ...

    def environment_value(self, name: str) -> str | None: ...

    def secret_value(self, stack_id: str, source: SecretSource) -> str | None: ...

    def expand_path(self, path: str) -> str: ...


class ServiceEnvironmentProvider:
    """Compose a bounded service environment and resolve service-owned secrets."""

    _INHERITED_NAMES = (
        "HOME",
        "LANG",
        "LC_ALL",
        "MISE_DATA_DIR",
        "PATH",
        "TMPDIR",
        "TZ",
    )

    def __init__(
        self,
        secret_store: ControlPlaneSecretStore,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        selected = dict(os.environ if environment is None else environment)
        self._environment = {
            name: selected[name] for name in self._INHERITED_NAMES if selected.get(name)
        }
        self._secret_store = secret_store

    def inherited_environment(self) -> Mapping[str, str]:
        return self._environment

    def environment_value(self, name: str) -> str | None:
        return self._environment.get(name)

    def secret_value(self, stack_id: str, source: SecretSource) -> str | None:
        if source.provider != "control-plane-store":
            raise StdioExecutionError(
                "secret-provider-unsupported",
                f"Secret source '{source.id}' is not available through the service store",
            )
        try:
            return self._secret_store.resolve(stack_id, source.id)
        except SecretStoreError as error:
            raise StdioExecutionError(
                "secret-source-unavailable", f"Secret source '{source.id}' is unavailable"
            ) from error

    def expand_path(self, path: str) -> str:
        return str(Path(path).expanduser())


class EnvironmentComposer:
    def __init__(self, provider: EnvironmentProvider) -> None:
        self._provider = provider

    def compose(self, configuration: StackConfiguration, command: Command) -> dict[str, str]:
        environment = dict(self._provider.inherited_environment())
        environment_sources = {source.id: source for source in configuration.environment_sources}
        secret_sources = {source.id: source for source in configuration.secret_sources}
        seen_names: set[str] = set()

        for binding in command.environment:
            if binding.name in seen_names:
                raise StdioExecutionError(
                    "environment-binding-duplicate",
                    (
                        f"Command '{command.id}' binds environment variable "
                        f"'{binding.name}' more than once"
                    ),
                )
            seen_names.add(binding.name)
            value_from = binding.value_from
            if isinstance(value_from, LiteralEnvironmentValue):
                value = value_from.literal
            elif isinstance(value_from, EnvironmentSourceValue):
                source = environment_sources[value_from.environment_source_ref]
                value = self._provider.environment_value(source.variable)
            elif isinstance(value_from, SecretSourceValue):
                source = secret_sources[value_from.secret_source_ref]
                value = self._provider.secret_value(configuration.id, source)
            else:
                raise AssertionError("unsupported environment binding")

            if value is None:
                environment.pop(binding.name, None)
                if binding.required:
                    source_id = next(iter(value_from.model_dump(by_alias=True).values()))
                    raise StdioExecutionError(
                        "environment-binding-missing",
                        (
                            f"Required environment binding '{binding.name}' from "
                            f"'{source_id}' is unavailable"
                        ),
                    )
                continue
            environment[binding.name] = value
        return environment

    def working_directory(self, command: Command) -> str | None:
        return (
            self._provider.expand_path(command.working_directory)
            if command.working_directory is not None
            else None
        )

    def local_path(self, path: str) -> str:
        return self._provider.expand_path(path)
