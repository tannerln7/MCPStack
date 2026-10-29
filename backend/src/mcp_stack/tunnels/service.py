from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from mcp_stack.lifecycle import (
    LifecycleAction,
    LifecycleError,
    LifecycleObservation,
    ManagedExecutionPlan,
    SystemdUserLifecycleProvider,
)
from mcp_stack.log_safety import safe_log_lines
from mcp_stack.secrets import ControlPlaneSecretStore, SecretStoreError

from .models import TunnelClientStatus, TunnelProfile
from .repository import TunnelProfileError, TunnelProfileRepository


class TunnelLifecycleService:
    def __init__(
        self,
        repository: TunnelProfileRepository,
        secret_store: ControlPlaneSecretStore,
        executable: Path,
        provider: SystemdUserLifecycleProvider,
        runtime_root: Path,
        command_search_path: str | None = None,
    ) -> None:
        self.repository = repository
        self.secret_store = secret_store
        self.executable = executable.expanduser().absolute()
        self.provider = provider
        self.runtime_root = runtime_root / "tunnels"
        self.command_search_path = command_search_path or self._default_command_search_path()

    def status(self) -> TunnelClientStatus:
        installed = self.executable.is_file() and os.access(self.executable, os.X_OK)
        version = None
        if installed:
            try:
                result = subprocess.run(
                    [str(self.executable), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                )
                version = (result.stdout or result.stderr).strip().splitlines()[0][:160]
            except (OSError, subprocess.TimeoutExpired, IndexError):
                version = None
        return TunnelClientStatus(
            installed=installed,
            executable=str(self.executable),
            version=version,
            profile_directory=str(self.repository.root),
            credential_state=self.secret_store.metadata(
                "system", "tunnel-control-plane-api-key"
            ).state,
        )

    def observe(self, profile_id: str) -> LifecycleObservation:
        self._profile(profile_id)
        return self.provider.observe("tunnel-profile", profile_id)

    def act(self, profile_id: str, action: LifecycleAction) -> LifecycleObservation:
        profile = self._profile(profile_id)
        if action == "stop":
            health_url_file = self.runtime_root / f"{profile.id}.health-url"
            observation = self.provider.stop("tunnel-profile", profile.id)
            health_url_file.unlink(missing_ok=True)
            return observation
        if not self.executable.is_file() or not os.access(self.executable, os.X_OK):
            raise LifecycleError("tunnel-client-missing", "Managed tunnel client is not installed")
        try:
            api_key = self.secret_store.resolve("system", "tunnel-control-plane-api-key")
        except SecretStoreError as error:
            raise LifecycleError(error.code, str(error)) from error
        if not api_key:
            raise LifecycleError("credential-missing", "Tunnel client API key is not configured")
        self.runtime_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.runtime_root, 0o700)
        health_url_file = self.runtime_root / f"{profile.id}.health-url"
        if action == "start":
            health_url_file.unlink(missing_ok=True)
        plan = ManagedExecutionPlan(
            stack_id="tunnel-profile",
            component_id=profile.id,
            subject_kind="tunnel",
            subject_id=profile.id,
            command_id="tunnel-client-run",
            argv=(
                str(self.executable),
                "run",
                "--profile",
                profile.id,
                "--profile-dir",
                str(self.repository.root),
                "--health.url-file",
                str(health_url_file),
            ),
            working_directory=None,
            environment={
                "CONTROL_PLANE_API_KEY": api_key,
                "PATH": self.command_search_path,
            },
            restart="on-failure",
            stop_timeout_seconds=20,
        )
        observation = self.provider.act(action, plan)
        return observation

    def logs(self, profile_id: str, limit: int) -> list[str]:
        self._profile(profile_id)
        try:
            api_key = self.secret_store.resolve("system", "tunnel-control-plane-api-key")
        except SecretStoreError as error:
            raise LifecycleError(
                "logs-secret-unavailable",
                "Tunnel logs cannot be safely retrieved while the credential is inaccessible",
            ) from error
        if not api_key:
            raise LifecycleError(
                "logs-secret-unavailable",
                "Tunnel logs cannot be safely retrieved while the credential is unavailable",
            )
        bounded = max(1, min(limit, 500))
        lines = self.provider.recent_logs("tunnel-profile", profile_id, bounded)
        return list(safe_log_lines(lines, (api_key,)))

    def _profile(self, profile_id: str) -> TunnelProfile:
        try:
            profile = self.repository.get(profile_id)
        except TunnelProfileError as error:
            raise LifecycleError(error.code, str(error)) from error
        if profile is None:
            raise LifecycleError("profile-not-found", "Tunnel profile was not found")
        return profile

    @staticmethod
    def _default_command_search_path() -> str:
        """Return a deliberate non-secret PATH for tunnel-owned child commands."""

        candidates = [
            str(Path(sys.executable).resolve().parent),
            "/usr/local/bin",
            "/opt/mcp-stack/bin",
            *os.defpath.split(os.pathsep),
        ]
        return os.pathsep.join(dict.fromkeys(candidate for candidate in candidates if candidate))
