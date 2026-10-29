from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ObservationModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class ComponentObservation(ObservationModel):
    component_id: str
    status: Literal[
        "not-observed", "starting", "running", "available", "degraded", "unavailable", "stopped"
    ]
    observed_at: datetime
    detail: str | None = None


class ProcessInstance(ObservationModel):
    instance_id: str
    component_id: str
    command_ref: str
    phase: Literal["starting", "running", "stopping", "exited", "failed"]
    observed_at: datetime
    pid: int | None = None


class ExecutionSessionObservation(ObservationModel):
    execution_id: str
    component_id: str
    mcp_server_ref: str
    transport: Literal["stdio"]
    state: Literal["active", "stale"]
    configuration_revision: str
    configuration_revision_matches: bool
    configuration_identity_matches: bool
    launched_at: datetime
    observed_at: datetime
    pid: int | None = None


class McpSession(ObservationModel):
    session_id: str
    mcp_server_ref: str
    transport_ref: str
    phase: Literal["connecting", "connected", "closing", "closed", "failed"]
    observed_at: datetime
    process_instance_ref: str | None = None
    protocol_revision: str | None = None


class EndpointObservation(ObservationModel):
    endpoint_ref: str
    reachable: bool
    observed_at: datetime
    resolved_address: str | None = None


class HealthObservation(ObservationModel):
    health_check_ref: str
    status: Literal["unknown", "passing", "failing"]
    observed_at: datetime
    reason: str | None = None
    latency_ms: float | None = None
    expires_at: datetime | None = None


class LogStream(ObservationModel):
    stream_id: str
    log_source_ref: str
    phase: Literal["open", "closed", "failed"]
    observed_at: datetime


class RuntimeSnapshot(ObservationModel):
    stack_id: str
    configuration_revision: str
    observed_at: datetime
    components: list[ComponentObservation]
    execution_sessions: list[ExecutionSessionObservation] = Field(default_factory=list)
    process_instances: list[ProcessInstance] = Field(default_factory=list)
    mcp_sessions: list[McpSession] = Field(default_factory=list)
    endpoint_observations: list[EndpointObservation] = Field(default_factory=list)
    health_observations: list[HealthObservation] = Field(default_factory=list)
    log_streams: list[LogStream] = Field(default_factory=list)
