from datetime import UTC, datetime

from mcp_stack.configuration import StackRecord
from mcp_stack.domain.configuration import McpServerSubject
from mcp_stack.domain.observations import (
    ComponentObservation,
    ExecutionSessionObservation,
    ProcessInstance,
    RuntimeSnapshot,
)
from mcp_stack.health import HealthService
from mcp_stack.lifecycle import LifecycleError, LifecycleObservation, LifecycleService
from mcp_stack.runtime import SessionRegistry


class ObservationService:
    """Collect verified mcpctl execution registrations without inferring MCP health."""

    def __init__(
        self,
        registry: SessionRegistry | None = None,
        lifecycle: LifecycleService | None = None,
        health: HealthService | None = None,
    ) -> None:
        self._registry = registry or SessionRegistry()
        self._lifecycle = lifecycle
        self._health = health

    def snapshot_for(self, record: StackRecord) -> RuntimeSnapshot:
        observed_at = datetime.now(UTC)
        execution_sessions: list[ExecutionSessionObservation] = []
        process_instances: list[ProcessInstance] = []
        for registration, path in self._registry.registrations():
            is_active = self._registry.process_is_current(registration)
            if not is_active and registration.stack_id != record.configuration.id:
                self._registry.remove(path)
                continue
            if registration.stack_id != record.configuration.id:
                continue
            component = next(
                (
                    item
                    for item in record.configuration.components
                    if item.id == registration.component_id
                ),
                None,
            )
            identity_matches = bool(
                component is not None
                and isinstance(component.subject, McpServerSubject)
                and component.subject.mcp_server_ref == registration.mcp_server_id
            )
            state = "active" if is_active else "stale"
            session = ExecutionSessionObservation(
                execution_id=str(registration.session_id),
                component_id=registration.component_id,
                mcp_server_ref=registration.mcp_server_id,
                transport=registration.transport,
                state=state,
                configuration_revision=registration.configuration_revision,
                configuration_revision_matches=(
                    registration.configuration_revision == record.revision
                ),
                configuration_identity_matches=identity_matches,
                launched_at=registration.launched_at,
                observed_at=observed_at,
                pid=registration.pid,
            )
            execution_sessions.append(session)
            if is_active:
                process_instances.append(
                    ProcessInstance(
                        instance_id=str(registration.session_id),
                        component_id=registration.component_id,
                        command_ref=registration.command_id,
                        phase="running",
                        observed_at=observed_at,
                        pid=registration.pid,
                    )
                )
            else:
                # exec() cannot clean up after normal exit; verified stale entries
                # are surfaced once and then removed lazily.
                self._registry.remove(path)

        sessions_by_component: dict[str, list[ExecutionSessionObservation]] = {}
        for session in execution_sessions:
            sessions_by_component.setdefault(session.component_id, []).append(session)

        lifecycle_by_component: dict[str, LifecycleObservation] = {}
        if self._lifecycle is not None:
            for component in record.configuration.components:
                try:
                    observation = self._lifecycle.observation_for(record, component.id)
                except LifecycleError:
                    observation = None
                if observation is None:
                    continue
                lifecycle_by_component[component.id] = observation
                if observation.state in {"active", "activating", "deactivating", "failed"}:
                    plan = self._lifecycle.plan_for(record, component.id)
                    if plan is not None:
                        process_instances.append(
                            ProcessInstance(
                                instance_id=observation.unit_id,
                                component_id=component.id,
                                command_ref=plan.command_id,
                                phase={
                                    "active": "running",
                                    "activating": "starting",
                                    "deactivating": "stopping",
                                    "failed": "failed",
                                }[observation.state],
                                observed_at=observation.observed_at,
                            )
                        )

        snapshot = RuntimeSnapshot(
            stack_id=record.configuration.id,
            configuration_revision=record.revision,
            observed_at=observed_at,
            components=[
                self._component_observation(
                    component.id,
                    observed_at,
                    sessions_by_component,
                    lifecycle_by_component,
                )
                for component in record.configuration.components
            ],
            execution_sessions=execution_sessions,
            process_instances=process_instances,
        )
        if self._health is not None:
            snapshot = snapshot.model_copy(
                update={"health_observations": self._health.observations_for(record, snapshot)}
            )
        return snapshot

    @staticmethod
    def _component_observation(
        component_id: str,
        observed_at: datetime,
        sessions_by_component: dict[str, list[ExecutionSessionObservation]],
        lifecycle_by_component: dict[str, LifecycleObservation],
    ) -> ComponentObservation:
        lifecycle = lifecycle_by_component.get(component_id)
        if lifecycle is not None:
            status = {
                "active": "running",
                "activating": "starting",
                "deactivating": "stopped",
                "failed": "unavailable",
                "inactive": "stopped",
                "unknown": "not-observed",
            }[lifecycle.state]
            return ComponentObservation(
                component_id=component_id,
                status=status,
                observed_at=lifecycle.observed_at,
                detail=(f"{lifecycle.detail} This is provider process state, not health."),
            )
        sessions = sessions_by_component.get(component_id, [])
        active_count = sum(session.state == "active" for session in sessions)
        stale_count = sum(session.state == "stale" for session in sessions)
        if active_count:
            return ComponentObservation(
                component_id=component_id,
                status="running",
                observed_at=observed_at,
                detail=(
                    f"{active_count} active execution process"
                    f"{'es' if active_count != 1 else ''} registered through mcpctl. "
                    "MCP connectivity and health are not observed."
                ),
            )
        if stale_count:
            return ComponentObservation(
                component_id=component_id,
                status="not-observed",
                observed_at=observed_at,
                detail=(
                    "A stale mcpctl execution registration was found and removed; "
                    "no active process is observed."
                ),
            )
        return ComponentObservation(
            component_id=component_id,
            status="not-observed",
            observed_at=observed_at,
            detail="No active mcpctl-launched execution process is observed.",
        )
