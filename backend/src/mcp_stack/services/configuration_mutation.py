from __future__ import annotations

from dataclasses import dataclass

from mcp_stack.configuration import (
    ConfigurationValidationRejected,
    FilesystemStackRepository,
    StackRecord,
    TrustedWorkspaceWriter,
    WriteOutcome,
)
from mcp_stack.lifecycle import LifecycleError, LifecycleService
from mcp_stack.secrets import ControlPlaneSecretStore, SecretStoreError


@dataclass(frozen=True)
class ConfigurationMutationOutcome:
    write: WriteOutcome
    deleted_secret_source_ids: tuple[str, ...]
    stopped_component_ids: tuple[str, ...]


class ConfigurationPostSaveCleanupError(Exception):
    code = "configuration-cleanup-failed"


class ConfigurationMutationService:
    """Save exact source bytes and remove only secret slots no longer declared."""

    def __init__(
        self,
        repository: FilesystemStackRepository,
        writer: TrustedWorkspaceWriter,
        secret_store: ControlPlaneSecretStore,
        lifecycle: LifecycleService,
    ) -> None:
        self._repository = repository
        self._writer = writer
        self._secret_store = secret_store
        self._lifecycle = lifecycle

    def write(
        self, record: StackRecord, original_revision: str, document: str
    ) -> ConfigurationMutationOutcome:
        validation = self._repository.validate_candidate(record.configuration.id, document)
        if validation is None:
            return ConfigurationMutationOutcome(
                write=self._writer.write(record, original_revision, document),
                deleted_secret_source_ids=(),
                stopped_component_ids=(),
            )
        if not validation.valid or validation.configuration is None:
            raise ConfigurationValidationRejected(validation)

        current_ids = {source.id for source in record.configuration.secret_sources}
        candidate_ids = {source.id for source in validation.configuration.secret_sources}
        removed_ids = tuple(sorted(current_ids - candidate_ids))
        candidate_component_ids = {
            component.id for component in validation.configuration.components
        }
        removed_application_component_ids = tuple(
            component.id
            for component in record.configuration.components
            if component.id not in candidate_component_ids
            and component.subject_kind == "application"
        )
        for secret_id in removed_ids:
            if (
                self._secret_store.metadata(record.configuration.id, secret_id).state
                == "inaccessible"
            ):
                raise ConfigurationPostSaveCleanupError(
                    "A removed secret slot is inaccessible; configuration was not changed"
                )

        outcome = self._writer.write(record, original_revision, document)
        try:
            stopped_component_ids = tuple(
                component_id
                for component_id in removed_application_component_ids
                if self._lifecycle.stop_for_deletion(record, component_id)
            )
            for secret_id in removed_ids:
                self._secret_store.delete(record.configuration.id, secret_id)
        except (LifecycleError, SecretStoreError) as error:
            raise ConfigurationPostSaveCleanupError(
                "Configuration was saved, but a removed resource could not be fully cleaned up"
            ) from error
        return ConfigurationMutationOutcome(
            write=outcome,
            deleted_secret_source_ids=removed_ids,
            stopped_component_ids=stopped_component_ids,
        )
