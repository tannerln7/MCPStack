from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic.alias_generators import to_camel

from mcp_stack.configuration import (
    ConfigurationDiagnostic,
    ConfigurationIssue,
    ConfigurationSource,
)
from mcp_stack.domain.configuration import StackConfiguration
from mcp_stack.domain.observations import RuntimeSnapshot
from mcp_stack.lifecycle import LifecycleObservation


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class ConfigurationSourceView(ApiModel):
    path: str
    format: Literal["yaml"]
    revision: str
    size_bytes: int
    modified_at: datetime

    @classmethod
    def from_source(cls, source: ConfigurationSource) -> ConfigurationSourceView:
        return cls(**source.__dict__)


class ConfigurationIssueView(ApiModel):
    stage: Literal["discovery", "parsing", "schema", "domain"]
    message: str
    path: str
    code: str | None = None
    line: int | None = None
    column: int | None = None

    @classmethod
    def from_issue(cls, issue: ConfigurationIssue) -> ConfigurationIssueView:
        return cls(**issue.__dict__)


class ConfigurationDiagnosticView(ApiModel):
    source_path: str
    source: ConfigurationSourceView | None
    issues: list[ConfigurationIssueView]

    @classmethod
    def from_diagnostic(cls, diagnostic: ConfigurationDiagnostic) -> ConfigurationDiagnosticView:
        return cls(
            source_path=(
                diagnostic.source.path
                if diagnostic.source is not None
                else diagnostic.source_path or "Configuration repository"
            ),
            source=(
                ConfigurationSourceView.from_source(diagnostic.source)
                if diagnostic.source is not None
                else None
            ),
            issues=[ConfigurationIssueView.from_issue(issue) for issue in diagnostic.issues],
        )


class StackSummary(ApiModel):
    id: str
    name: str
    description: str | None
    component_count: int
    configuration_revision: str
    source: ConfigurationSourceView


class StackDiscovery(ApiModel):
    stacks: list[StackSummary]
    invalid_sources: list[ConfigurationDiagnosticView]
    scanned_source_count: int


class StackView(ApiModel):
    configuration: StackConfiguration
    source: ConfigurationSourceView
    observations: RuntimeSnapshot


class EditableStackSource(ApiModel):
    stack_id: str
    stack_name: str
    source: ConfigurationSourceView
    media_type: Literal["application/yaml"] = "application/yaml"
    encoding: Literal["utf-8"] = "utf-8"
    document: str


class ConfigurationValidationPreviewRequest(ApiModel):
    document: str = Field(max_length=1_048_576)


class ConfigurationValidationPreview(ApiModel):
    valid: bool
    candidate_revision: str
    issues: list[ConfigurationIssueView]
    configuration: StackConfiguration | None


class ConfigurationWriteRequest(ApiModel):
    original_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    document: str = Field(max_length=1_048_576)


class ConfigurationWriteResult(ApiModel):
    status: Literal["saved"] = "saved"
    previous_revision: str
    source: ConfigurationSourceView
    bytes_written: int
    replaced: bool
    deleted_secret_source_ids: list[str] = Field(default_factory=list)
    stopped_component_ids: list[str] = Field(default_factory=list)


class StackCreateRequest(ApiModel):
    stack_id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,79}$")
    document: str = Field(max_length=1_048_576)


class StackCreateResult(ApiModel):
    status: Literal["created"] = "created"
    stack_id: str
    source: ConfigurationSourceView
    bytes_written: int


class TunnelClientView(ApiModel):
    installed: bool
    executable: str
    version: str | None
    profile_directory: str
    credential_state: Literal["configured", "missing", "inaccessible"]


class TunnelTargetView(ApiModel):
    kind: Literal["stdio", "http"]
    channel: str
    command: str | None = None
    url: str | None = None


class TunnelProfileView(ApiModel):
    id: str | None
    path: str
    valid: bool
    diagnostic: str | None = None
    revision: str | None = None
    tunnel_id: str | None = None
    base_url: str | None = None
    target: TunnelTargetView | None = None
    health_listen_addr: str | None = None
    log_level: str | None = None
    log_format: str | None = None
    associated_stack_id: str | None = None
    lifecycle: LifecycleObservationView | None = None


class TunnelProfileCreateRequest(ApiModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,79}$")
    tunnel_id: str = Field(min_length=1, max_length=256)
    target_kind: Literal["stdio", "http"]
    channel: str = Field(default="main", pattern=r"^[a-z][a-z0-9-]{0,79}$")
    stack_target: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9-]{0,79}(?:/[a-z][a-z0-9-]{0,79})?$",
    )
    url: str | None = Field(default=None, max_length=2048)
    base_url: str = Field(default="https://api.openai.com", max_length=2048)
    health_listen_addr: str = Field(default="127.0.0.1:0", max_length=128)
    restart: Literal["never", "on-failure"] = "on-failure"


class TunnelProfileUpdateRequest(TunnelProfileCreateRequest):
    original_revision: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class DeleteRequest(ApiModel):
    original_revision: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class TunnelProfileDeleteResult(ApiModel):
    status: Literal["deleted"] = "deleted"
    profile_id: str


class StackDeleteResult(ApiModel):
    status: Literal["deleted"] = "deleted"
    stack_id: str
    component_ids: list[str]
    stopped_component_ids: list[str]
    deleted_tunnel_profile_ids: list[str]
    deleted_secret_source_ids: list[str]


class TunnelCredentialRequest(ApiModel):
    api_key: SecretStr = Field(min_length=1, max_length=16_384)


class SecretValueRequest(ApiModel):
    value: SecretStr = Field(min_length=1, max_length=65_536)


class SecretMetadataView(ApiModel):
    secret_source_id: str
    state: Literal["configured", "missing", "inaccessible"]
    updated_at: datetime | None = None


class LifecycleActionRequest(ApiModel):
    action: Literal["start", "stop", "restart"]


class LifecycleObservationView(ApiModel):
    component_id: str
    provider: Literal["systemd-user"]
    unit_id: str
    state: Literal["active", "activating", "deactivating", "failed", "inactive", "unknown"]
    observed_at: datetime
    detail: str
    intentionally_active: bool
    boot_enabled: bool
    result: str | None = None

    @classmethod
    def from_observation(cls, observation: LifecycleObservation) -> LifecycleObservationView:
        return cls(**observation.__dict__)


class ComponentLifecycleView(ApiModel):
    eligible: bool
    actions: list[Literal["start", "stop", "restart"]]
    observation: LifecycleObservationView | None


class RecentLogsView(ApiModel):
    component_id: str
    lines: list[str]
    truncated: bool
