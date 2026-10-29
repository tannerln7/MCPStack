from __future__ import annotations

from collections import deque
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class ContractModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class HostRuntime(ContractModel):
    id: str
    kind: Literal["host"]


class ContainerRuntime(ContractModel):
    id: str
    kind: Literal["container"]
    engine: Literal["docker"]
    image: str
    version: str


Runtime = Annotated[HostRuntime | ContainerRuntime, Field(discriminator="kind")]


class PathNameExecutable(ContractModel):
    kind: Literal["path-name"]
    name: str


class LocalPathExecutable(ContractModel):
    kind: Literal["local-path"]
    path: str


class ImageEntrypointExecutable(ContractModel):
    kind: Literal["image-entrypoint"]


Executable = Annotated[
    PathNameExecutable | LocalPathExecutable | ImageEntrypointExecutable,
    Field(discriminator="kind"),
]


class LiteralEnvironmentValue(ContractModel):
    literal: str


class EnvironmentSourceValue(ContractModel):
    environment_source_ref: str


class SecretSourceValue(ContractModel):
    secret_source_ref: str


EnvironmentValue = LiteralEnvironmentValue | EnvironmentSourceValue | SecretSourceValue


class EnvironmentBinding(ContractModel):
    name: str
    value_from: EnvironmentValue
    required: bool = True


class Command(ContractModel):
    id: str
    runtime_ref: str
    executable: Executable
    args: list[str] = Field(default_factory=list)
    working_directory: str | None = None
    environment: list[EnvironmentBinding] = Field(default_factory=list)


class EnvironmentSource(ContractModel):
    id: str
    kind: Literal["host-environment"]
    variable: str


class SecretSource(ContractModel):
    id: str
    kind: Literal["secret-reference"]
    provider: Literal["control-plane-store"]


class Listener(ContractModel):
    scheme: Literal["http", "https"]
    host: str
    port: int
    path: str


class ConfiguredEndpoint(ContractModel):
    id: str
    origin: Literal["configured"]
    url: str


class ApplicationEndpoint(ContractModel):
    id: str
    origin: Literal["application-provided"]
    application_ref: str
    listener: Listener


class TunnelEndpoint(ContractModel):
    id: str
    origin: Literal["tunnel-provided"]
    tunnel_ref: str


Endpoint = Annotated[
    ConfiguredEndpoint | ApplicationEndpoint | TunnelEndpoint,
    Field(discriminator="origin"),
]


class StdioTransport(ContractModel):
    id: str
    kind: Literal["stdio"]
    command_ref: str


class StreamableHttpTransport(ContractModel):
    id: str
    kind: Literal["streamable-http"]
    endpoint_ref: str


Transport = Annotated[StdioTransport | StreamableHttpTransport, Field(discriminator="kind")]


class McpServer(ContractModel):
    id: str
    name: str
    transport_ref: str
    provided_by_application_ref: str | None = None
    controls_application_ref: str | None = None


class Application(ContractModel):
    id: str
    name: str
    process_command_ref: str | None = None
    provided_endpoint_refs: list[str] = Field(default_factory=list)


class Tunnel(ContractModel):
    id: str
    name: str
    target_endpoint_ref: str | None = None
    target_mcp_server_ref: str | None = None
    client_command_ref: str | None = None
    client_profile_ref: str | None = None
    lifecycle_policy_ref: str
    public_endpoint_ref: str | None = None

    @model_validator(mode="after")
    def validate_target_and_client(self) -> Tunnel:
        if (self.target_endpoint_ref is None) == (self.target_mcp_server_ref is None):
            raise ValueError("Tunnel requires exactly one endpoint or MCP server target")
        if (self.client_command_ref is None) == (self.client_profile_ref is None):
            raise ValueError("Tunnel requires exactly one command or profile client")
        return self


class LifecyclePolicy(ContractModel):
    id: str
    ownership: Literal["session-owned", "control-plane-managed", "externally-managed"]
    activation: Literal["on-demand", "persistent"]
    provider: Literal["direct-child", "system-service"] | None = None
    restart: Literal["never", "on-failure"] | None = None
    stop_timeout_seconds: int | None = None


class ComponentTarget(ContractModel):
    component_ref: str


class EndpointTarget(ContractModel):
    endpoint_ref: str


class McpServerTarget(ContractModel):
    mcp_server_ref: str


class TunnelTarget(ContractModel):
    tunnel_ref: str


HealthTarget = ComponentTarget | EndpointTarget | McpServerTarget | TunnelTarget


class HealthCheck(ContractModel):
    id: str
    name: str
    target: HealthTarget
    probe: Literal["process-running", "http", "mcp-connect", "tunnel-connected"]
    role: Literal["readiness", "liveness"]
    expected_status: int | None = None
    timeout_seconds: int | None = None


class CommandLogTarget(ContractModel):
    command_ref: str
    stream: Literal["stdout", "stderr"]


class McpLogTarget(ContractModel):
    mcp_server_ref: str


class TunnelLogTarget(ContractModel):
    tunnel_ref: str


LogTarget = CommandLogTarget | McpLogTarget | TunnelLogTarget


class LogSource(ContractModel):
    id: str
    name: str
    target: LogTarget
    encoding: Literal["utf-8"] | None = None
    framing: Literal["lines", "mcp-logging"] | None = None


class McpServerSubject(ContractModel):
    mcp_server_ref: str


class ApplicationSubject(ContractModel):
    application_ref: str


class TunnelSubject(ContractModel):
    tunnel_ref: str


ComponentSubject = McpServerSubject | ApplicationSubject | TunnelSubject


class Component(ContractModel):
    id: str
    name: str
    description: str | None = None
    enabled: bool
    subject: ComponentSubject
    lifecycle_policy_ref: str | None = None
    health_check_refs: list[str] = Field(default_factory=list)
    log_source_refs: list[str] = Field(default_factory=list)

    @property
    def subject_kind(self) -> Literal["mcp-server", "application", "tunnel"]:
        if isinstance(self.subject, McpServerSubject):
            return "mcp-server"
        if isinstance(self.subject, ApplicationSubject):
            return "application"
        return "tunnel"


class Dependency(ContractModel):
    component_ref: str
    depends_on_ref: str
    requirement: Literal["started", "ready", "healthy", "mcp-connected", "completed"]
    strength: Literal["hard", "order-only"]


class StackConfiguration(ContractModel):
    model_version: Literal["0.1"]
    id: str
    name: str
    description: str | None = None
    runtimes: list[Runtime] = Field(default_factory=list)
    commands: list[Command] = Field(default_factory=list)
    environment_sources: list[EnvironmentSource] = Field(default_factory=list)
    secret_sources: list[SecretSource] = Field(default_factory=list)
    endpoints: list[Endpoint] = Field(default_factory=list)
    transports: list[Transport] = Field(default_factory=list)
    mcp_servers: list[McpServer] = Field(default_factory=list)
    applications: list[Application] = Field(default_factory=list)
    tunnels: list[Tunnel] = Field(default_factory=list)
    lifecycle_policies: list[LifecyclePolicy] = Field(default_factory=list)
    health_checks: list[HealthCheck] = Field(default_factory=list)
    log_sources: list[LogSource] = Field(default_factory=list)
    components: list[Component]
    dependencies: list[Dependency] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph(self) -> StackConfiguration:
        collections: dict[str, list[ContractModel]] = {
            "runtime": self.runtimes,
            "command": self.commands,
            "environment source": self.environment_sources,
            "secret source": self.secret_sources,
            "endpoint": self.endpoints,
            "transport": self.transports,
            "MCP server": self.mcp_servers,
            "application": self.applications,
            "tunnel": self.tunnels,
            "lifecycle policy": self.lifecycle_policies,
            "health check": self.health_checks,
            "log source": self.log_sources,
            "component": self.components,
        }
        ids: dict[str, set[str]] = {}
        for label, values in collections.items():
            value_ids = [value.id for value in values]
            if len(value_ids) != len(set(value_ids)):
                raise ValueError(f"duplicate {label} id")
            ids[label] = set(value_ids)

        def require(reference: str | None, kind: str, owner: str) -> None:
            if reference is not None and reference not in ids[kind]:
                raise ValueError(f"{owner} references unknown {kind} '{reference}'")

        for command in self.commands:
            binding_names = [binding.name for binding in command.environment]
            if len(binding_names) != len(set(binding_names)):
                raise ValueError(
                    f"command '{command.id}' contains duplicate environment binding names"
                )
            require(command.runtime_ref, "runtime", command.id)
            for binding in command.environment:
                value = binding.value_from
                if isinstance(value, EnvironmentSourceValue):
                    require(value.environment_source_ref, "environment source", command.id)
                elif isinstance(value, SecretSourceValue):
                    require(value.secret_source_ref, "secret source", command.id)
        for endpoint in self.endpoints:
            if isinstance(endpoint, ApplicationEndpoint):
                require(endpoint.application_ref, "application", endpoint.id)
            elif isinstance(endpoint, TunnelEndpoint):
                require(endpoint.tunnel_ref, "tunnel", endpoint.id)
        for transport in self.transports:
            if isinstance(transport, StdioTransport):
                require(transport.command_ref, "command", transport.id)
            else:
                require(transport.endpoint_ref, "endpoint", transport.id)
        for server in self.mcp_servers:
            require(server.transport_ref, "transport", server.id)
            require(server.provided_by_application_ref, "application", server.id)
            require(server.controls_application_ref, "application", server.id)
        for application in self.applications:
            require(application.process_command_ref, "command", application.id)
            for reference in application.provided_endpoint_refs:
                require(reference, "endpoint", application.id)
        for tunnel in self.tunnels:
            require(tunnel.target_endpoint_ref, "endpoint", tunnel.id)
            require(tunnel.target_mcp_server_ref, "MCP server", tunnel.id)
            require(tunnel.client_command_ref, "command", tunnel.id)
            require(tunnel.lifecycle_policy_ref, "lifecycle policy", tunnel.id)
            require(tunnel.public_endpoint_ref, "endpoint", tunnel.id)
        for component in self.components:
            subject_reference = next(iter(component.subject.model_dump(exclude_none=True).values()))
            subject_collection = {
                "mcp-server": "MCP server",
                "application": "application",
                "tunnel": "tunnel",
            }[component.subject_kind]
            require(subject_reference, subject_collection, component.id)
            require(component.lifecycle_policy_ref, "lifecycle policy", component.id)
            for reference in component.health_check_refs:
                require(reference, "health check", component.id)
            for reference in component.log_source_refs:
                require(reference, "log source", component.id)
        for dependency in self.dependencies:
            require(dependency.component_ref, "component", "dependency")
            require(dependency.depends_on_ref, "component", "dependency")
            if dependency.component_ref == dependency.depends_on_ref:
                raise ValueError("a component cannot depend on itself")
        self._validate_hard_dependency_graph()
        return self

    def _validate_hard_dependency_graph(self) -> None:
        prerequisite_count = {component.id: 0 for component in self.components}
        dependents: dict[str, list[str]] = {component.id: [] for component in self.components}
        for dependency in self.dependencies:
            if dependency.strength == "hard":
                prerequisite_count[dependency.component_ref] += 1
                dependents[dependency.depends_on_ref].append(dependency.component_ref)

        ready = deque(
            component_id for component_id, count in prerequisite_count.items() if count == 0
        )
        visited_count = 0
        while ready:
            component_id = ready.popleft()
            visited_count += 1
            for dependent_id in dependents[component_id]:
                prerequisite_count[dependent_id] -= 1
                if prerequisite_count[dependent_id] == 0:
                    ready.append(dependent_id)

        if visited_count != len(prerequisite_count):
            raise ValueError("hard component dependency graph contains a cycle")
