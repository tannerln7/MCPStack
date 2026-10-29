from fastapi import APIRouter, HTTPException, Query, Request, status

from mcp_stack.api.models import (
    ComponentLifecycleView,
    ConfigurationDiagnosticView,
    ConfigurationIssueView,
    ConfigurationSourceView,
    ConfigurationValidationPreview,
    ConfigurationValidationPreviewRequest,
    ConfigurationWriteRequest,
    ConfigurationWriteResult,
    DeleteRequest,
    EditableStackSource,
    LifecycleActionRequest,
    LifecycleObservationView,
    RecentLogsView,
    SecretMetadataView,
    SecretValueRequest,
    StackCreateRequest,
    StackCreateResult,
    StackDeleteResult,
    StackDiscovery,
    StackSummary,
    StackView,
    TunnelClientView,
    TunnelCredentialRequest,
    TunnelProfileCreateRequest,
    TunnelProfileDeleteResult,
    TunnelProfileUpdateRequest,
    TunnelProfileView,
    TunnelTargetView,
)
from mcp_stack.configuration import (
    ConfigurationRevisionConflict,
    ConfigurationValidationRejected,
    ConfigurationWriteError,
    FilesystemStackRepository,
    RepositoryConflict,
    UncertainWriteOutcome,
)
from mcp_stack.domain.observations import RuntimeSnapshot
from mcp_stack.lifecycle import LifecycleError, LifecycleService
from mcp_stack.logging import LogService
from mcp_stack.secrets import SecretStoreError
from mcp_stack.services.configuration_mutation import ConfigurationPostSaveCleanupError
from mcp_stack.services.deletion import StackDeletionError
from mcp_stack.services.observations import ObservationService
from mcp_stack.tunnels import TunnelProfileCreate, TunnelProfileError

router = APIRouter(prefix="/api/v1")


def _repository(request: Request) -> FilesystemStackRepository:
    return request.app.state.stack_repository


def _observations(request: Request) -> ObservationService:
    return request.app.state.observation_service


def _lifecycle(request: Request) -> LifecycleService:
    return request.app.state.lifecycle_service


def _logs(request: Request) -> LogService:
    return request.app.state.log_service


def _secret_source(stack_id: str, secret_source_id: str, request: Request):
    record = _repository(request).get(stack_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Stack not found")
    source = next(
        (item for item in record.configuration.secret_sources if item.id == secret_source_id),
        None,
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Secret source not found")
    return source


def _secret_metadata_view(stack_id: str, secret_source_id: str, request: Request):
    metadata = request.app.state.secret_store.metadata(stack_id, secret_source_id)
    return SecretMetadataView(
        secret_source_id=secret_source_id,
        state=metadata.state,
        updated_at=metadata.updated_at,
    )


def _require_mutation_boundary(request: Request) -> None:
    origin = request.headers.get("origin")
    if (
        request.headers.get("x-mcp-stack-mutation") != "1"
        or origin not in request.app.state.allowed_mutation_origins
        or request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json"
        or request.headers.get("content-encoding")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "mutation-boundary-rejected",
                "message": "Mutation request was rejected",
            },
        )


def _validate_tunnel_target(candidate: TunnelProfileCreateRequest, request: Request) -> None:
    if candidate.target_kind != "stdio":
        return
    stack_id = (candidate.stack_target or "").split("/", 1)[0]
    record = _repository(request).get(stack_id)
    if record is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "stack-not-found",
                "message": "Configured Stack target was not found",
            },
        )
    configured = record.configuration
    stdio_servers = []
    for component in configured.components:
        if component.subject_kind != "mcp-server":
            continue
        server = next(
            (
                item
                for item in configured.mcp_servers
                if item.id == component.subject.mcp_server_ref
            ),
            None,
        )
        transport = next(
            (item for item in configured.transports if server and item.id == server.transport_ref),
            None,
        )
        if transport and transport.kind == "stdio":
            stdio_servers.append((component, server))
    explicit_id = (candidate.stack_target or "").split("/", 1)[1:]
    if explicit_id:
        selected = explicit_id[0]
        if not any(
            component.id == selected or server.id == selected for component, server in stdio_servers
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "unsupported-target",
                    "message": "Configured stdio target was not found",
                },
            )
    elif len(stdio_servers) != 1:
        raise HTTPException(
            status_code=422,
            detail={"code": "ambiguous-target", "message": "Stack target is ambiguous"},
        )


@router.get("/contracts/stack-configuration", response_model=dict)
def get_stack_configuration_contract(request: Request) -> dict:
    return _repository(request).schema


@router.get("/stacks", response_model=StackDiscovery)
def list_stacks(request: Request) -> StackDiscovery:
    snapshot = _repository(request).discover()
    return StackDiscovery(
        stacks=[
            StackSummary(
                id=record.configuration.id,
                name=record.configuration.name,
                description=record.configuration.description,
                component_count=len(record.configuration.components),
                configuration_revision=record.revision,
                source=ConfigurationSourceView.from_source(record.source),
            )
            for record in snapshot.records
        ],
        invalid_sources=[
            ConfigurationDiagnosticView.from_diagnostic(diagnostic)
            for diagnostic in snapshot.diagnostics
        ],
        scanned_source_count=snapshot.scanned_source_count,
    )


@router.post("/stacks/validation-previews", response_model=ConfigurationValidationPreview)
def preview_new_stack_configuration(
    candidate: StackCreateRequest, request: Request
) -> ConfigurationValidationPreview:
    _require_mutation_boundary(request)
    result = _repository(request).validate_new_candidate(candidate.stack_id, candidate.document)
    return ConfigurationValidationPreview(
        valid=result.valid,
        candidate_revision=result.revision,
        issues=[ConfigurationIssueView.from_issue(issue) for issue in result.issues],
        configuration=result.configuration,
    )


@router.post("/stacks", response_model=StackCreateResult, status_code=201)
def create_stack(candidate: StackCreateRequest, request: Request) -> StackCreateResult:
    _require_mutation_boundary(request)
    try:
        outcome = request.app.state.configuration_writer.create(
            candidate.stack_id, candidate.document
        )
    except ConfigurationValidationRejected as error:
        raise HTTPException(
            status_code=422,
            detail={
                "code": error.code,
                "message": str(error),
                "issues": [
                    ConfigurationIssueView.from_issue(issue).model_dump(by_alias=True)
                    for issue in error.validation.issues
                ],
            },
        ) from error
    except RepositoryConflict as error:
        raise HTTPException(
            status_code=409, detail={"code": error.code, "message": str(error)}
        ) from error
    except ConfigurationWriteError as error:
        raise HTTPException(
            status_code=422, detail={"code": error.code, "message": str(error)}
        ) from error
    return StackCreateResult(
        stack_id=candidate.stack_id,
        source=ConfigurationSourceView.from_source(outcome.source),
        bytes_written=outcome.bytes_written,
    )


@router.get("/stacks/{stack_id}", response_model=StackView)
def get_stack(stack_id: str, request: Request) -> StackView:
    record = _repository(request).get(stack_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stack not found")
    return StackView(
        configuration=record.configuration,
        source=ConfigurationSourceView.from_source(record.source),
        observations=_observations(request).snapshot_for(record),
    )


@router.get("/stacks/{stack_id}/secrets", response_model=list[SecretMetadataView])
def list_stack_secrets(stack_id: str, request: Request) -> list[SecretMetadataView]:
    record = _repository(request).get(stack_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Stack not found")
    return [
        _secret_metadata_view(stack_id, source.id, request)
        for source in record.configuration.secret_sources
    ]


@router.put("/stacks/{stack_id}/secrets/{secret_source_id}", response_model=SecretMetadataView)
def replace_stack_secret(
    stack_id: str,
    secret_source_id: str,
    candidate: SecretValueRequest,
    request: Request,
) -> SecretMetadataView:
    _require_mutation_boundary(request)
    _secret_source(stack_id, secret_source_id, request)
    try:
        request.app.state.secret_store.write(
            stack_id, secret_source_id, candidate.value.get_secret_value()
        )
    except SecretStoreError as error:
        raise HTTPException(
            status_code=422, detail={"code": error.code, "message": str(error)}
        ) from error
    return _secret_metadata_view(stack_id, secret_source_id, request)


@router.delete("/stacks/{stack_id}/secrets/{secret_source_id}", response_model=SecretMetadataView)
def delete_stack_secret(
    stack_id: str, secret_source_id: str, request: Request
) -> SecretMetadataView:
    _require_mutation_boundary(request)
    _secret_source(stack_id, secret_source_id, request)
    try:
        request.app.state.secret_store.delete(stack_id, secret_source_id)
    except SecretStoreError as error:
        raise HTTPException(
            status_code=422, detail={"code": error.code, "message": str(error)}
        ) from error
    return _secret_metadata_view(stack_id, secret_source_id, request)


@router.get("/stacks/{stack_id}/observations", response_model=RuntimeSnapshot)
def get_stack_observations(stack_id: str, request: Request) -> RuntimeSnapshot:
    record = _repository(request).get(stack_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stack not found")
    return _observations(request).snapshot_for(record)


@router.get("/stacks/{stack_id}/source", response_model=EditableStackSource)
def get_stack_source(stack_id: str, request: Request) -> EditableStackSource:
    record = _repository(request).get(stack_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stack not found")
    return EditableStackSource(
        stack_id=stack_id,
        stack_name=record.configuration.name,
        source=ConfigurationSourceView.from_source(record.source),
        document=record.document,
    )


@router.post(
    "/stacks/{stack_id}/validation-previews",
    response_model=ConfigurationValidationPreview,
)
def preview_stack_configuration(
    stack_id: str,
    candidate: ConfigurationValidationPreviewRequest,
    request: Request,
) -> ConfigurationValidationPreview:
    _require_mutation_boundary(request)
    result = _repository(request).validate_candidate(stack_id, candidate.document)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stack not found")
    return ConfigurationValidationPreview(
        valid=result.valid,
        candidate_revision=result.revision,
        issues=[ConfigurationIssueView.from_issue(issue) for issue in result.issues],
        configuration=result.configuration,
    )


@router.put("/stacks/{stack_id}/source", response_model=ConfigurationWriteResult)
def save_stack_configuration(
    stack_id: str,
    candidate: ConfigurationWriteRequest,
    request: Request,
) -> ConfigurationWriteResult:
    _require_mutation_boundary(request)
    record = _repository(request).get(stack_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail={"code": "source-not-found", "message": "Stack not found"}
        )
    try:
        mutation = request.app.state.configuration_mutation_service.write(
            record, candidate.original_revision, candidate.document
        )
        outcome = mutation.write
    except ConfigurationValidationRejected as error:
        raise HTTPException(
            status_code=422,
            detail={
                "code": error.code,
                "message": str(error),
                "issues": [
                    ConfigurationIssueView.from_issue(issue).model_dump(by_alias=True)
                    for issue in error.validation.issues
                ],
            },
        ) from error
    except (ConfigurationRevisionConflict, RepositoryConflict) as error:
        detail = {"code": error.code, "message": str(error)}
        if isinstance(error, ConfigurationRevisionConflict):
            detail["currentRevision"] = error.current_revision
        raise HTTPException(status_code=409, detail=detail) from error
    except UncertainWriteOutcome as error:
        raise HTTPException(
            status_code=500, detail={"code": error.code, "message": str(error)}
        ) from error
    except ConfigurationPostSaveCleanupError as error:
        raise HTTPException(
            status_code=500, detail={"code": error.code, "message": str(error)}
        ) from error
    except ConfigurationWriteError as error:
        raise HTTPException(
            status_code=422, detail={"code": error.code, "message": str(error)}
        ) from error
    return ConfigurationWriteResult(
        previous_revision=outcome.previous_revision,
        source=ConfigurationSourceView.from_source(outcome.source),
        bytes_written=outcome.bytes_written,
        replaced=outcome.replaced,
        deleted_secret_source_ids=list(mutation.deleted_secret_source_ids),
        stopped_component_ids=list(mutation.stopped_component_ids),
    )


@router.delete("/stacks/{stack_id}", response_model=StackDeleteResult)
def delete_stack(stack_id: str, candidate: DeleteRequest, request: Request) -> StackDeleteResult:
    _require_mutation_boundary(request)
    record = _repository(request).get(stack_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "source-not-found", "message": "Stack not found"},
        )
    try:
        outcome = request.app.state.stack_deletion_service.delete(
            record, candidate.original_revision
        )
    except ConfigurationRevisionConflict as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": error.code,
                "message": str(error),
                "currentRevision": error.current_revision,
            },
        ) from error
    except (RepositoryConflict, StackDeletionError) as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "message": str(error)},
        ) from error
    except UncertainWriteOutcome as error:
        raise HTTPException(
            status_code=500, detail={"code": error.code, "message": str(error)}
        ) from error
    except ConfigurationWriteError as error:
        raise HTTPException(
            status_code=422, detail={"code": error.code, "message": str(error)}
        ) from error
    return StackDeleteResult(
        stack_id=outcome.stack_id,
        component_ids=list(outcome.component_ids),
        stopped_component_ids=list(outcome.stopped_component_ids),
        deleted_tunnel_profile_ids=list(outcome.deleted_tunnel_profile_ids),
        deleted_secret_source_ids=list(outcome.deleted_secret_source_ids),
    )


@router.get(
    "/stacks/{stack_id}/components/{component_id}/lifecycle", response_model=ComponentLifecycleView
)
def get_component_lifecycle(
    stack_id: str, component_id: str, request: Request
) -> ComponentLifecycleView:
    record = _repository(request).get(stack_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Stack not found")
    try:
        observation = _lifecycle(request).observation_for(record, component_id)
    except LifecycleError as error:
        raise HTTPException(
            status_code=503, detail={"code": error.code, "message": str(error)}
        ) from error
    return ComponentLifecycleView(
        eligible=observation is not None,
        actions=["start", "stop", "restart"] if observation is not None else [],
        observation=LifecycleObservationView.from_observation(observation) if observation else None,
    )


@router.post(
    "/stacks/{stack_id}/components/{component_id}/lifecycle-actions",
    response_model=LifecycleObservationView,
)
def act_on_component_lifecycle(
    stack_id: str,
    component_id: str,
    action: LifecycleActionRequest,
    request: Request,
) -> LifecycleObservationView:
    _require_mutation_boundary(request)
    record = _repository(request).get(stack_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Stack not found")
    try:
        observation = _lifecycle(request).act(record, component_id, action.action)
    except LifecycleError as error:
        raise HTTPException(
            status_code=422, detail={"code": error.code, "message": str(error)}
        ) from error
    return LifecycleObservationView.from_observation(observation)


@router.get("/stacks/{stack_id}/components/{component_id}/logs", response_model=RecentLogsView)
def get_component_logs(
    stack_id: str,
    component_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
) -> RecentLogsView:
    record = _repository(request).get(stack_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Stack not found")
    try:
        logs = _logs(request).recent(record, component_id, limit)
    except LifecycleError as error:
        raise HTTPException(
            status_code=422, detail={"code": error.code, "message": str(error)}
        ) from error
    return RecentLogsView(
        component_id=logs.component_id, lines=list(logs.lines), truncated=logs.truncated
    )


def _tunnel_profile_view(summary, service) -> TunnelProfileView:
    profile = summary.profile
    observation = None
    if profile is not None:
        try:
            observation = service.observe(profile.id)
        except LifecycleError:
            observation = None
    return TunnelProfileView(
        id=profile.id if profile else None,
        path=summary.path,
        valid=summary.valid,
        diagnostic=summary.diagnostic,
        revision=profile.revision if profile else None,
        tunnel_id=profile.tunnel_id if profile else None,
        base_url=profile.base_url if profile else None,
        target=(
            TunnelTargetView(
                kind=profile.target.kind,
                channel=profile.target.channel,
                command=profile.target.command,
                url=profile.target.url,
            )
            if profile
            else None
        ),
        health_listen_addr=profile.health_listen_addr if profile else None,
        log_level=profile.log_level if profile else None,
        log_format=profile.log_format if profile else None,
        associated_stack_id=profile.associated_stack_id if profile else None,
        lifecycle=LifecycleObservationView.from_observation(observation) if observation else None,
    )


@router.get("/tunnel-client", response_model=TunnelClientView)
def get_tunnel_client(request: Request) -> TunnelClientView:
    return TunnelClientView(**request.app.state.tunnel_service.status().__dict__)


@router.get("/tunnel-profiles", response_model=list[TunnelProfileView])
def list_tunnel_profiles(request: Request) -> list[TunnelProfileView]:
    service = request.app.state.tunnel_service
    return [
        _tunnel_profile_view(summary, service)
        for summary in request.app.state.tunnel_profile_repository.list()
    ]


@router.post("/tunnel-profiles", response_model=TunnelProfileView, status_code=201)
def create_tunnel_profile(
    candidate: TunnelProfileCreateRequest, request: Request
) -> TunnelProfileView:
    _require_mutation_boundary(request)
    _validate_tunnel_target(candidate, request)
    try:
        profile = request.app.state.tunnel_profile_repository.create(
            TunnelProfileCreate(**candidate.model_dump())
        )
    except TunnelProfileError as error:
        status_code = 409 if error.code == "profile-exists" else 422
        raise HTTPException(
            status_code=status_code,
            detail={"code": error.code, "message": str(error)},
        ) from error
    summary = next(
        item
        for item in request.app.state.tunnel_profile_repository.list()
        if item.profile and item.profile.id == profile.id
    )
    return _tunnel_profile_view(summary, request.app.state.tunnel_service)


@router.get("/tunnel-profiles/{profile_id}", response_model=TunnelProfileView)
def get_tunnel_profile(profile_id: str, request: Request) -> TunnelProfileView:
    summary = next(
        (
            item
            for item in request.app.state.tunnel_profile_repository.list()
            if item.profile and item.profile.id == profile_id
        ),
        None,
    )
    if summary is None:
        raise HTTPException(status_code=404, detail="Tunnel profile not found")
    return _tunnel_profile_view(summary, request.app.state.tunnel_service)


@router.put("/tunnel-profiles/{profile_id}", response_model=TunnelProfileView)
def update_tunnel_profile(
    profile_id: str, candidate: TunnelProfileUpdateRequest, request: Request
) -> TunnelProfileView:
    _require_mutation_boundary(request)
    _validate_tunnel_target(candidate, request)
    values = candidate.model_dump(exclude={"original_revision"})
    try:
        request.app.state.tunnel_profile_repository.update(
            profile_id,
            candidate.original_revision,
            TunnelProfileCreate(**values),
        )
    except TunnelProfileError as error:
        status_code = 409 if error.code == "profile-revision-conflict" else 422
        raise HTTPException(
            status_code=status_code,
            detail={"code": error.code, "message": str(error)},
        ) from error
    return get_tunnel_profile(profile_id, request)


@router.delete("/tunnel-profiles/{profile_id}", response_model=TunnelProfileDeleteResult)
def delete_tunnel_profile(
    profile_id: str, candidate: DeleteRequest, request: Request
) -> TunnelProfileDeleteResult:
    _require_mutation_boundary(request)
    try:
        repository = request.app.state.tunnel_profile_repository
        repository.verify_deletion(profile_id, candidate.original_revision)
        request.app.state.tunnel_service.act(profile_id, "stop")
        repository.delete(profile_id, candidate.original_revision)
    except (LifecycleError, TunnelProfileError) as error:
        status_code = 409 if error.code == "profile-revision-conflict" else 422
        raise HTTPException(
            status_code=status_code,
            detail={"code": error.code, "message": str(error)},
        ) from error
    return TunnelProfileDeleteResult(profile_id=profile_id)


@router.put("/tunnel-client/credential", response_model=TunnelClientView)
def set_tunnel_credential(candidate: TunnelCredentialRequest, request: Request) -> TunnelClientView:
    _require_mutation_boundary(request)
    try:
        request.app.state.secret_store.write(
            "system",
            "tunnel-control-plane-api-key",
            candidate.api_key.get_secret_value(),
        )
    except SecretStoreError as error:
        code = error.code
        raise HTTPException(
            status_code=422,
            detail={"code": code, "message": "Tunnel client credential could not be stored"},
        ) from error
    return TunnelClientView(**request.app.state.tunnel_service.status().__dict__)


@router.post(
    "/tunnel-profiles/{profile_id}/lifecycle-actions",
    response_model=LifecycleObservationView,
)
def act_on_tunnel_profile(
    profile_id: str,
    action: LifecycleActionRequest,
    request: Request,
) -> LifecycleObservationView:
    _require_mutation_boundary(request)
    try:
        observation = request.app.state.tunnel_service.act(profile_id, action.action)
    except LifecycleError as error:
        raise HTTPException(
            status_code=422, detail={"code": error.code, "message": str(error)}
        ) from error
    return LifecycleObservationView.from_observation(observation)


@router.get("/tunnel-profiles/{profile_id}/logs", response_model=RecentLogsView)
def get_tunnel_profile_logs(
    profile_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
) -> RecentLogsView:
    try:
        lines = request.app.state.tunnel_service.logs(profile_id, limit)
    except LifecycleError as error:
        raise HTTPException(
            status_code=422, detail={"code": error.code, "message": str(error)}
        ) from error
    return RecentLogsView(component_id=profile_id, lines=lines, truncated=False)
