from __future__ import annotations

from mcp_stack.configuration import StackRecord
from mcp_stack.domain.configuration import (
    ApplicationSubject,
    SecretSourceValue,
    TunnelSubject,
)
from mcp_stack.execution.environment import EnvironmentComposer
from mcp_stack.execution.errors import StdioExecutionError
from mcp_stack.log_safety import safe_log_lines

from .models import LifecycleAction, LifecycleError, LifecycleObservation, ManagedExecutionPlan
from .systemd import SystemdUserLifecycleProvider


class LifecycleService:
    def __init__(
        self,
        provider: SystemdUserLifecycleProvider,
        composer: EnvironmentComposer,
    ) -> None:
        self._provider = provider
        self._composer = composer

    def observation_for(
        self, record: StackRecord, component_id: str
    ) -> LifecycleObservation | None:
        plan = self.plan_for(record, component_id)
        if plan is None:
            return None
        return self._provider.observe(record.configuration.id, component_id)

    def act(
        self, record: StackRecord, component_id: str, action: LifecycleAction
    ) -> LifecycleObservation:
        plan = self.plan_for(record, component_id)
        if plan is None:
            raise LifecycleError(
                "component-lifecycle-ineligible",
                "Component is not eligible for control-plane-managed persistent lifecycle",
            )
        return self._provider.act(action, plan)

    def logs_for(self, record: StackRecord, component_id: str, limit: int) -> list[str]:
        plan = self.plan_for(record, component_id)
        if plan is None:
            raise LifecycleError("logs-unsupported", "Component has no managed systemd log source")
        secret_names = self._secret_binding_names(record, component_id)
        secret_values = (
            value for name in secret_names if (value := plan.environment.get(name)) is not None
        )
        lines = self._provider.recent_logs(record.configuration.id, component_id, limit)
        return list(safe_log_lines(lines, secret_values))

    def has_secret_bindings(self, record: StackRecord, component_id: str) -> bool:
        return bool(self._secret_binding_names(record, component_id))

    @staticmethod
    def _secret_binding_names(record: StackRecord, component_id: str) -> set[str]:
        configuration = record.configuration
        component = next(
            (item for item in configuration.components if item.id == component_id), None
        )
        if component is None:
            return set()
        command_id: str | None = None
        if isinstance(component.subject, ApplicationSubject):
            application = next(
                (
                    item
                    for item in configuration.applications
                    if item.id == component.subject.application_ref
                ),
                None,
            )
            command_id = application.process_command_ref if application else None
        elif isinstance(component.subject, TunnelSubject):
            tunnel = next(
                (item for item in configuration.tunnels if item.id == component.subject.tunnel_ref),
                None,
            )
            command_id = tunnel.client_command_ref if tunnel else None
        command = next((item for item in configuration.commands if item.id == command_id), None)
        if command is None:
            return set()
        return {
            binding.name
            for binding in command.environment
            if isinstance(binding.value_from, SecretSourceValue)
        }

    def stop_for_deletion(self, record: StackRecord, component_id: str) -> bool:
        if not self._durably_managed(record, component_id):
            return False
        self._provider.stop(record.configuration.id, component_id)
        return True

    @staticmethod
    def _durably_managed(record: StackRecord, component_id: str) -> bool:
        configuration = record.configuration
        component = next(
            (item for item in configuration.components if item.id == component_id), None
        )
        if component is None or not component.enabled or component.lifecycle_policy_ref is None:
            return False
        policy = next(
            (
                item
                for item in configuration.lifecycle_policies
                if item.id == component.lifecycle_policy_ref
            ),
            None,
        )
        return bool(
            policy
            and policy.ownership == "control-plane-managed"
            and policy.activation == "persistent"
            and policy.provider == "system-service"
            and isinstance(component.subject, (ApplicationSubject, TunnelSubject))
        )

    def plan_for(self, record: StackRecord, component_id: str) -> ManagedExecutionPlan | None:
        configuration = record.configuration
        component = next(
            (item for item in configuration.components if item.id == component_id), None
        )
        if component is None or not component.enabled or component.lifecycle_policy_ref is None:
            return None
        policy = next(
            (
                item
                for item in configuration.lifecycle_policies
                if item.id == component.lifecycle_policy_ref
            ),
            None,
        )
        if (
            policy is None
            or policy.ownership != "control-plane-managed"
            or policy.activation != "persistent"
            or policy.provider != "system-service"
        ):
            return None
        if isinstance(component.subject, ApplicationSubject):
            subject = next(
                (
                    item
                    for item in configuration.applications
                    if item.id == component.subject.application_ref
                ),
                None,
            )
            command_id = subject.process_command_ref if subject else None
            kind = "application"
            subject_id = component.subject.application_ref
        elif isinstance(component.subject, TunnelSubject):
            subject = next(
                (item for item in configuration.tunnels if item.id == component.subject.tunnel_ref),
                None,
            )
            command_id = subject.client_command_ref if subject else None
            kind = "tunnel"
            subject_id = component.subject.tunnel_ref
        else:
            return None
        command = next((item for item in configuration.commands if item.id == command_id), None)
        if command is None or command.executable.kind == "image-entrypoint":
            return None
        executable = (
            command.executable.name
            if command.executable.kind == "path-name"
            else self._composer.local_path(command.executable.path)
        )
        try:
            environment = self._composer.compose(configuration, command)
            working_directory = self._composer.working_directory(command)
        except StdioExecutionError as error:
            raise LifecycleError(error.code, str(error)) from error
        return ManagedExecutionPlan(
            stack_id=configuration.id,
            component_id=component.id,
            subject_kind=kind,
            subject_id=subject_id,
            command_id=command.id,
            argv=(executable, *command.args),
            working_directory=working_directory,
            environment=environment,
            restart=policy.restart or "never",
            stop_timeout_seconds=policy.stop_timeout_seconds or 15,
        )
