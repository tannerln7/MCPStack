from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from mcp_stack.api.routes import router
from mcp_stack.configuration import (
    FilesystemStackRepository,
    TrustedWorkspaceWriter,
    default_config_directory,
    default_runtime_directory,
    default_secret_directory,
    default_tunnel_client_executable,
    default_tunnel_profile_directory,
)
from mcp_stack.configuration.settings import (
    allowed_mutation_origins as configured_mutation_origins,
)
from mcp_stack.execution import EnvironmentComposer, ServiceEnvironmentProvider
from mcp_stack.health import HealthService
from mcp_stack.lifecycle import LifecycleService, SystemdUserLifecycleProvider
from mcp_stack.logging import LogService
from mcp_stack.runtime import SessionRegistry
from mcp_stack.secrets import ControlPlaneSecretStore
from mcp_stack.services.configuration_mutation import ConfigurationMutationService
from mcp_stack.services.deletion import StackDeletionService
from mcp_stack.services.observations import ObservationService
from mcp_stack.tunnels import (
    TunnelLifecycleService,
    TunnelProfileRepository,
)


def create_app(
    *,
    config_dir: Path | None = None,
    schema_path: Path | None = None,
    runtime_dir: Path | None = None,
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "[::1]"),
    allowed_mutation_origins: tuple[str, ...] | None = None,
    lifecycle_service: LifecycleService | None = None,
    tunnel_profile_dir: Path | None = None,
    tunnel_client_executable: Path | None = None,
    secret_dir: Path | None = None,
) -> FastAPI:
    selected_config_dir = config_dir or default_config_directory()

    application = FastAPI(
        title="MCPStack API",
        version="0.1.0",
        description=("Local configuration, observation, and managed-component API for MCPStack."),
    )
    repository = FilesystemStackRepository(selected_config_dir, schema_path)
    selected_runtime_root = runtime_dir or default_runtime_directory()
    selected_secret_store = ControlPlaneSecretStore(secret_dir or default_secret_directory())
    systemd_provider = SystemdUserLifecycleProvider(selected_runtime_root)
    lifecycle = lifecycle_service or LifecycleService(
        systemd_provider,
        EnvironmentComposer(ServiceEnvironmentProvider(selected_secret_store)),
    )
    health_service = HealthService(lifecycle)
    application.state.stack_repository = repository
    application.state.configuration_writer = TrustedWorkspaceWriter(repository, selected_config_dir)
    application.state.configuration_mutation_service = ConfigurationMutationService(
        repository,
        application.state.configuration_writer,
        selected_secret_store,
        lifecycle,
    )
    application.state.lifecycle_service = lifecycle
    application.state.log_service = LogService(lifecycle)
    application.state.observation_service = ObservationService(
        SessionRegistry(selected_runtime_root / "sessions"), lifecycle, health_service
    )
    tunnel_profiles = TunnelProfileRepository(
        tunnel_profile_dir or default_tunnel_profile_directory()
    )
    application.state.tunnel_profile_repository = tunnel_profiles
    application.state.secret_store = selected_secret_store
    application.state.tunnel_service = TunnelLifecycleService(
        tunnel_profiles,
        selected_secret_store,
        tunnel_client_executable or default_tunnel_client_executable(),
        systemd_provider,
        selected_runtime_root,
    )
    application.state.stack_deletion_service = StackDeletionService(
        application.state.configuration_writer,
        lifecycle,
        tunnel_profiles,
        application.state.tunnel_service,
        selected_secret_store,
    )
    application.state.allowed_mutation_origins = frozenset(
        allowed_mutation_origins
        if allowed_mutation_origins is not None
        else configured_mutation_origins()
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(allowed_hosts),
        www_redirect=False,
    )
    application.include_router(router)

    @application.middleware("http")
    async def bound_mutation_requests(request: Request, call_next):
        if request.method in {"PUT", "POST", "PATCH", "DELETE"} and request.url.path.startswith(
            "/api/v1/"
        ):
            length = request.headers.get("content-length")
            transfer_encoding = request.headers.get("transfer-encoding")
            if (
                (length is None and transfer_encoding is not None)
                or (length is not None and not length.isdigit())
                or (length is not None and int(length) > 1_100_000)
            ):
                return JSONResponse(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    content={
                        "detail": {
                            "code": "request-too-large",
                            "message": "Mutation request is too large",
                        }
                    },
                )
        return await call_next(request)

    @application.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        # Source documents may contain sensitive literals. Pydantic's full error
        # objects include rejected input, so expose only stable diagnostic fields.
        issues = [
            {
                "type": issue["type"],
                "location": list(issue["loc"]),
                "message": issue["msg"],
            }
            for issue in error.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": issues},
        )

    @application.get("/healthz", include_in_schema=False)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
