from __future__ import annotations

from dataclasses import dataclass

from mcp_stack.configuration import StackRecord, TrustedWorkspaceWriter
from mcp_stack.lifecycle import LifecycleError, LifecycleService
from mcp_stack.secrets import ControlPlaneSecretStore, SecretStoreError
from mcp_stack.tunnels import (
    TunnelLifecycleService,
    TunnelProfileError,
    TunnelProfileRepository,
)


@dataclass(frozen=True)
class StackDeletionOutcome:
    stack_id: str
    component_ids: tuple[str, ...]
    stopped_component_ids: tuple[str, ...]
    deleted_tunnel_profile_ids: tuple[str, ...]
    deleted_secret_source_ids: tuple[str, ...]


class StackDeletionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class StackDeletionService:
    """Remove one Stack authority after stopping only its owned resources."""

    def __init__(
        self,
        writer: TrustedWorkspaceWriter,
        lifecycle: LifecycleService,
        tunnel_profiles: TunnelProfileRepository,
        tunnel_lifecycle: TunnelLifecycleService,
        secret_store: ControlPlaneSecretStore,
    ) -> None:
        self._writer = writer
        self._lifecycle = lifecycle
        self._tunnel_profiles = tunnel_profiles
        self._tunnel_lifecycle = tunnel_lifecycle
        self._secret_store = secret_store

    def delete(self, record: StackRecord, original_revision: str) -> StackDeletionOutcome:
        associated_profiles = tuple(
            summary.profile
            for summary in self._tunnel_profiles.list()
            if summary.profile is not None
            and summary.profile.associated_stack_id == record.configuration.id
        )
        try:
            self._writer.verify_deletion(record, original_revision)
            for source in record.configuration.secret_sources:
                if (
                    self._secret_store.metadata(record.configuration.id, source.id).state
                    == "inaccessible"
                ):
                    raise StackDeletionError(
                        "secret-cleanup-failed",
                        "A Stack secret slot is inaccessible; the Stack was not deleted",
                    )
            for profile in associated_profiles:
                self._tunnel_profiles.verify_deletion(profile.id, profile.revision)

            stopped_components = tuple(
                component.id
                for component in record.configuration.components
                if self._lifecycle.stop_for_deletion(record, component.id)
            )
            for profile in associated_profiles:
                self._tunnel_lifecycle.act(profile.id, "stop")
            for profile in associated_profiles:
                self._tunnel_profiles.delete(profile.id, profile.revision)
            self._writer.delete(record, original_revision)
            for source in record.configuration.secret_sources:
                self._secret_store.delete(record.configuration.id, source.id)
        except (LifecycleError, SecretStoreError, TunnelProfileError) as error:
            raise StackDeletionError(
                getattr(error, "code", "stack-delete-failed"), str(error)
            ) from error

        return StackDeletionOutcome(
            stack_id=record.configuration.id,
            component_ids=tuple(component.id for component in record.configuration.components),
            stopped_component_ids=stopped_components,
            deleted_tunnel_profile_ids=tuple(profile.id for profile in associated_profiles),
            deleted_secret_source_ids=tuple(
                source.id for source in record.configuration.secret_sources
            ),
        )
