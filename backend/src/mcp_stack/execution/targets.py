from __future__ import annotations

from dataclasses import dataclass

from mcp_stack.configuration import RepositorySnapshot, StackRecord
from mcp_stack.domain.configuration import (
    Component,
    LifecyclePolicy,
    McpServer,
    McpServerSubject,
    StdioTransport,
)

from .errors import StdioExecutionError


@dataclass(frozen=True)
class ResolvedStdioTarget:
    record: StackRecord
    component: Component
    mcp_server: McpServer
    transport: StdioTransport
    lifecycle_policy: LifecyclePolicy


class StdioTargetResolver:
    """Resolve a CLI selector to one configured session-owned stdio server."""

    def resolve(self, snapshot: RepositorySnapshot, selector: str) -> ResolvedStdioTarget:
        selector = selector.strip()
        if not selector:
            raise StdioExecutionError("target-missing", "a Stack or Component target is required")

        if "/" in selector:
            stack_selector, subject_selector = selector.split("/", 1)
            if not stack_selector or not subject_selector or "/" in subject_selector:
                raise StdioExecutionError(
                    "target-invalid",
                    "explicit targets must use the form <stack>/<component-or-mcp-server>",
                )
            record = self._resolve_stack(snapshot, stack_selector)
            component = self._resolve_component(record, subject_selector)
            return self._validate(record, component)

        stack_matches = self._matching_stacks(snapshot, selector)
        if len(stack_matches) == 1:
            components = self._mcp_components(stack_matches[0])
            if len(components) == 1:
                return self._validate(stack_matches[0], components[0])
            if not components:
                raise StdioExecutionError(
                    "target-unsupported",
                    f"Stack '{stack_matches[0].configuration.id}' has no configured MCP server",
                )
            raise StdioExecutionError(
                "target-ambiguous",
                (
                    f"Stack '{stack_matches[0].configuration.id}' has multiple MCP Components; "
                    "use <stack>/<component-or-mcp-server>"
                ),
            )
        if len(stack_matches) > 1:
            raise StdioExecutionError(
                "target-ambiguous",
                "the Stack target matches more than one configured Stack; use a Stack id",
            )

        component_matches = [
            (record, component)
            for record in snapshot.records
            for component in record.configuration.components
            if self._component_matches(record, component, selector)
        ]
        if len(component_matches) == 1:
            return self._validate(*component_matches[0])
        if len(component_matches) > 1:
            raise StdioExecutionError(
                "target-ambiguous",
                "the Component or MCP server target is not unique; use <stack>/<component>",
            )
        raise StdioExecutionError(
            "target-not-found", f"no configured Stack or Component matches '{selector}'"
        )

    def _resolve_stack(self, snapshot: RepositorySnapshot, selector: str) -> StackRecord:
        matches = self._matching_stacks(snapshot, selector)
        if not matches:
            raise StdioExecutionError(
                "target-not-found", f"no configured Stack matches '{selector}'"
            )
        if len(matches) > 1:
            raise StdioExecutionError(
                "target-ambiguous", "the Stack target is not unique; use a Stack id"
            )
        return matches[0]

    @staticmethod
    def _matching_stacks(snapshot: RepositorySnapshot, selector: str) -> list[StackRecord]:
        exact_id = [record for record in snapshot.records if record.configuration.id == selector]
        if exact_id:
            return exact_id
        folded = selector.casefold()
        return [
            record for record in snapshot.records if record.configuration.name.casefold() == folded
        ]

    def _resolve_component(self, record: StackRecord, selector: str) -> Component:
        matches = [
            component
            for component in record.configuration.components
            if self._component_matches(record, component, selector)
        ]
        if not matches:
            raise StdioExecutionError(
                "target-not-found",
                f"Stack '{record.configuration.id}' has no Component matching '{selector}'",
            )
        if len(matches) > 1:
            raise StdioExecutionError(
                "target-ambiguous",
                f"Stack '{record.configuration.id}' has multiple matching Components",
            )
        return matches[0]

    @staticmethod
    def _mcp_components(record: StackRecord) -> list[Component]:
        return [
            component
            for component in record.configuration.components
            if isinstance(component.subject, McpServerSubject)
        ]

    @staticmethod
    def _component_matches(record: StackRecord, component: Component, selector: str) -> bool:
        folded = selector.casefold()
        if component.id == selector or component.name.casefold() == folded:
            return True
        if not isinstance(component.subject, McpServerSubject):
            return False
        server = next(
            item
            for item in record.configuration.mcp_servers
            if item.id == component.subject.mcp_server_ref
        )
        return server.id == selector or server.name.casefold() == folded

    @staticmethod
    def _validate(record: StackRecord, component: Component) -> ResolvedStdioTarget:
        configuration = record.configuration
        if not component.enabled:
            raise StdioExecutionError(
                "component-disabled", f"Component '{component.id}' is disabled"
            )
        if not isinstance(component.subject, McpServerSubject):
            raise StdioExecutionError(
                "target-unsupported", f"Component '{component.id}' is not an MCP server"
            )
        server = next(
            item
            for item in configuration.mcp_servers
            if item.id == component.subject.mcp_server_ref
        )
        transport = next(
            item for item in configuration.transports if item.id == server.transport_ref
        )
        if not isinstance(transport, StdioTransport):
            raise StdioExecutionError(
                "transport-unsupported",
                f"MCP server '{server.id}' does not use stdio transport",
            )
        if component.lifecycle_policy_ref is None:
            raise StdioExecutionError(
                "lifecycle-unsupported",
                f"Component '{component.id}' has no session-owned lifecycle policy",
            )
        lifecycle = next(
            item
            for item in configuration.lifecycle_policies
            if item.id == component.lifecycle_policy_ref
        )
        if lifecycle.ownership != "session-owned" or lifecycle.activation != "on-demand":
            raise StdioExecutionError(
                "lifecycle-unsupported",
                f"Component '{component.id}' is not configured for an on-demand client session",
            )
        return ResolvedStdioTarget(record, component, server, transport, lifecycle)
