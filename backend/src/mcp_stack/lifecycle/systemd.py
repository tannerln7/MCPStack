from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from .models import LifecycleAction, LifecycleError, LifecycleObservation, ManagedExecutionPlan

Runner = Callable[..., subprocess.CompletedProcess[str]]
_SAFE_IDENTIFIER = re.compile(r"[^a-zA-Z0-9_.-]+")


def unit_name(stack_id: str, component_id: str) -> str:
    readable = _SAFE_IDENTIFIER.sub("-", f"{stack_id}-{component_id}").strip("-.")[:48]
    digest = hashlib.sha256(f"{stack_id}\0{component_id}".encode()).hexdigest()[:12]
    return f"mcp-stack-{readable or 'component'}-{digest}.service"


class SystemdUserLifecycleProvider:
    """Realize only derived MCPStack targets as transient user units."""

    def __init__(self, runtime_dir: Path, runner: Runner = subprocess.run) -> None:
        self._runtime_dir = runtime_dir / "managed-environments"
        self._runner = runner

    def observe(self, stack_id: str, component_id: str) -> LifecycleObservation:
        name = unit_name(stack_id, component_id)
        result = self._run(
            [
                "systemctl",
                "--user",
                "show",
                name,
                "--property=LoadState,ActiveState,SubState,Result,UnitFileState,Description",
            ],
            check=False,
        )
        properties: dict[str, str] = {}
        if result.returncode == 0:
            properties = {
                key: value
                for line in result.stdout.splitlines()
                if "=" in line
                for key, value in [line.split("=", 1)]
            }
        active = properties.get("ActiveState", "unknown")
        state = {
            "active": "active",
            "activating": "activating",
            "deactivating": "deactivating",
            "failed": "failed",
            "inactive": "inactive",
        }.get(active, "unknown")
        loaded = properties.get("LoadState") not in {None, "not-found"}
        # Unit identity and description must agree before lifecycle actions are allowed.
        expected_description = f"MCPStack managed {stack_id}/{component_id}"
        owned = not loaded or properties.get("Description") == expected_description
        if not owned:
            state = "unknown"
        detail = (
            "The derived systemd unit exists but MCPStack ownership could not be verified."
            if not owned
            else f"systemd user unit is {active}/{properties.get('SubState', 'unknown')}."
            if loaded
            else "No active MCPStack systemd user unit is loaded."
        )
        if state in {"inactive", "unknown"}:
            self._environment_path(name).unlink(missing_ok=True)
        return LifecycleObservation(
            component_id=component_id,
            provider="systemd-user",
            unit_id=name,
            state=state,
            observed_at=datetime.now(UTC),
            detail=detail,
            intentionally_active=state in {"active", "activating"},
            boot_enabled=properties.get("UnitFileState") in {"enabled", "enabled-runtime"},
            result="ownership-mismatch" if not owned else properties.get("Result") or None,
        )

    def act(self, action: LifecycleAction, plan: ManagedExecutionPlan) -> LifecycleObservation:
        name = unit_name(plan.stack_id, plan.component_id)
        if action == "start":
            self._start(name, plan)
        elif action == "stop":
            self.stop(plan.stack_id, plan.component_id)
        elif action == "restart":
            current = self.observe(plan.stack_id, plan.component_id)
            if current.result == "ownership-mismatch":
                raise LifecycleError(
                    "lifecycle-unit-not-owned",
                    "Derived systemd unit is not owned by MCPStack",
                )
            if current.state == "unknown":
                self._start(name, plan)
            else:
                self._write_environment(name, plan.environment)
                self._run(["systemctl", "--user", "restart", name])
        else:
            raise LifecycleError("lifecycle-action-unsupported", "Unsupported lifecycle action")
        return self.observe(plan.stack_id, plan.component_id)

    def stop(self, stack_id: str, component_id: str) -> LifecycleObservation:
        name = unit_name(stack_id, component_id)
        current = self.observe(stack_id, component_id)
        if current.result == "ownership-mismatch":
            raise LifecycleError(
                "lifecycle-unit-not-owned",
                "Derived systemd unit is not owned by MCPStack",
            )
        self._run(["systemctl", "--user", "stop", name], check=False)
        self._environment_path(name).unlink(missing_ok=True)
        return self.observe(stack_id, component_id)

    def recent_logs(self, stack_id: str, component_id: str, limit: int) -> list[str]:
        name = unit_name(stack_id, component_id)
        result = self._run(
            [
                "journalctl",
                f"_UID={os.geteuid()}",
                f"_SYSTEMD_USER_UNIT={name}",
                "--no-pager",
                "--output=cat",
                f"--lines={limit}",
            ],
            check=False,
        )
        if result.returncode not in {0, 1}:
            raise LifecycleError(
                "logs-unavailable", "Recent managed-component logs are unavailable"
            )
        return result.stdout.splitlines()[-limit:]

    def _start(self, name: str, plan: ManagedExecutionPlan) -> None:
        environment_path = self._write_environment(name, plan.environment)
        command: list[str] = [
            "systemd-run",
            "--user",
            f"--unit={name}",
            "--collect",
            "--service-type=exec",
            f"--property=Description=MCPStack managed {plan.stack_id}/{plan.component_id}",
            f"--property=EnvironmentFile={environment_path}",
            f"--property=Restart={'on-failure' if plan.restart == 'on-failure' else 'no'}",
            f"--property=TimeoutStopSec={plan.stop_timeout_seconds}",
        ]
        if plan.working_directory:
            command.append(f"--property=WorkingDirectory={plan.working_directory}")
        command.extend(["--", *plan.argv])
        try:
            self._run(command)
        except LifecycleError:
            environment_path.unlink(missing_ok=True)
            raise

    def _write_environment(self, name: str, environment: Mapping[str, str]) -> Path:
        self._runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self._runtime_dir, 0o700)
        path = self._environment_path(name)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                for key, value in environment.items():
                    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                    stream.write(f'{key}="{escaped}"\n')
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path

    def _environment_path(self, name: str) -> Path:
        return self._runtime_dir / f"{name}.env"

    def _run(self, argv: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        try:
            result = self._runner(argv, capture_output=True, text=True, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise LifecycleError(
                "lifecycle-provider-unavailable", "systemd user provider is unavailable"
            ) from error
        if check and result.returncode != 0:
            raise LifecycleError("lifecycle-action-failed", "systemd user lifecycle action failed")
        return result
