from __future__ import annotations

import argparse
import os
import signal
import socket
import struct
import subprocess
import threading
from contextlib import suppress
from pathlib import Path

from mcp_stack.configuration import (
    FilesystemStackRepository,
    default_broker_socket,
    default_config_directory,
    default_runtime_directory,
    default_secret_directory,
)
from mcp_stack.execution import (
    EnvironmentComposer,
    ServiceEnvironmentProvider,
    StdioExecutionError,
    StdioExecutionPlanner,
)
from mcp_stack.runtime import RuntimeRegistryError, SessionRegistry
from mcp_stack.secrets import ControlPlaneSecretStore

from .protocol import BrokerProtocolError, receive_launch_request, send_message


class BrokerServer:
    def __init__(
        self,
        socket_path: Path,
        repository: FilesystemStackRepository,
        secret_store: ControlPlaneSecretStore,
        registry: SessionRegistry,
        *,
        allowed_uids: set[int] | None = None,
    ) -> None:
        self.socket_path = socket_path
        self.repository = repository
        self.secret_store = secret_store
        self.registry = registry
        self.allowed_uids = allowed_uids
        self._listener: socket.socket | None = None
        self._stop = threading.Event()

    def serve_forever(self) -> None:
        self._prepare_socket_directory()
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._listener = listener
        try:
            if self.socket_path.exists() or self.socket_path.is_symlink():
                self.socket_path.unlink()
            listener.bind(os.fspath(self.socket_path))
            os.chmod(self.socket_path, 0o660)
            listener.listen(64)
            while not self._stop.is_set():
                try:
                    connection, _ = listener.accept()
                except OSError:
                    if self._stop.is_set():
                        break
                    raise
                threading.Thread(
                    target=self._handle_connection,
                    args=(connection,),
                    daemon=True,
                ).start()
        finally:
            listener.close()
            with suppress(OSError):
                self.socket_path.unlink(missing_ok=True)

    def shutdown(self) -> None:
        self._stop.set()
        if self._listener is not None:
            with suppress(OSError):
                self._listener.shutdown(socket.SHUT_RDWR)
            self._listener.close()

    def _handle_connection(self, connection: socket.socket) -> None:
        descriptors: tuple[int, int, int] | None = None
        registration_path: Path | None = None
        process: subprocess.Popen[bytes] | None = None
        try:
            peer_pid, peer_uid, _peer_gid = struct.unpack(
                "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            )
            del peer_pid
            if self.allowed_uids is not None and peer_uid not in self.allowed_uids:
                send_message(
                    connection,
                    {
                        "status": "error",
                        "code": "broker-peer-forbidden",
                        "message": "the local client is not allowed to launch MCP targets",
                        "exitStatus": 126,
                    },
                )
                return
            request, descriptors = receive_launch_request(connection)
            composer = EnvironmentComposer(ServiceEnvironmentProvider(self.secret_store))
            plan = StdioExecutionPlanner(self.repository, environment_composer=composer).plan(
                request.target
            )
            process = subprocess.Popen(
                plan.argv,
                stdin=descriptors[0],
                stdout=descriptors[1],
                stderr=descriptors[2],
                cwd=plan.working_directory,
                env=dict(plan.environment),
                start_new_session=True,
            )
            for descriptor in descriptors:
                os.close(descriptor)
            descriptors = None
            _, registration_path = self.registry.create_for_process(plan, process.pid)
            send_message(connection, {"status": "started"})
            exit_status = process.wait()
            send_message(connection, {"status": "exited", "exitStatus": exit_status % 256})
        except (StdioExecutionError, RuntimeRegistryError) as error:
            if process is not None and process.poll() is None:
                self._terminate(process)
            with suppress(OSError, BrokerProtocolError):
                send_message(
                    connection,
                    {
                        "status": "error",
                        "code": getattr(error, "code", "session-registration-failed"),
                        "message": getattr(
                            error,
                            "message",
                            "the configured MCP target could not be launched safely",
                        ),
                        "exitStatus": getattr(error, "exit_status", 126),
                    },
                )
        except (BrokerProtocolError, OSError, subprocess.SubprocessError):
            if process is not None and process.poll() is None:
                self._terminate(process)
            with suppress(OSError, BrokerProtocolError):
                send_message(
                    connection,
                    {
                        "status": "error",
                        "code": "broker-launch-failed",
                        "message": "the configured MCP target could not be launched",
                        "exitStatus": 126,
                    },
                )
        finally:
            if descriptors is not None:
                for descriptor in descriptors:
                    with suppress(OSError):
                        os.close(descriptor)
            if registration_path is not None:
                self.registry.remove(registration_path)
            connection.close()

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)

    def _prepare_socket_directory(self) -> None:
        self.socket_path.parent.mkdir(mode=0o2750, parents=True, exist_ok=True)
        os.chmod(self.socket_path.parent, 0o2750)


def _allowed_uids() -> set[int] | None:
    configured = os.environ.get("MCP_STACK_BROKER_ALLOWED_UIDS", "").strip()
    if not configured:
        return None
    try:
        return {int(value) for value in configured.split(",")}
    except ValueError as error:
        raise SystemExit("MCP_STACK_BROKER_ALLOWED_UIDS must contain numeric UIDs") from error


def main() -> None:
    parser = argparse.ArgumentParser(description="MCPStack stdio execution broker")
    parser.add_argument("--config-dir", type=Path, default=default_config_directory())
    parser.add_argument("--socket", type=Path, default=default_broker_socket())
    args = parser.parse_args()
    runtime_root = default_runtime_directory()
    server = BrokerServer(
        args.socket,
        FilesystemStackRepository(args.config_dir),
        ControlPlaneSecretStore(default_secret_directory()),
        SessionRegistry(runtime_root / "sessions"),
        allowed_uids=_allowed_uids(),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
