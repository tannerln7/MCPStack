from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import BinaryIO

from .protocol import BrokerProtocolError, receive_message, send_launch_request


class BrokerClientError(Exception):
    def __init__(self, code: str, message: str, exit_status: int = 126) -> None:
        self.code = code
        self.message = message
        self.exit_status = exit_status
        super().__init__(message)


class BrokerClient:
    def __init__(self, socket_path: Path) -> None:
        self.socket_path = socket_path

    def launch_stdio(
        self,
        target: str,
        stdin: BinaryIO,
        stdout: BinaryIO,
        stderr: BinaryIO,
    ) -> int:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.connect(os.fspath(self.socket_path))
                send_launch_request(
                    connection,
                    target,
                    (stdin.fileno(), stdout.fileno(), stderr.fileno()),
                )
                started = receive_message(connection)
                if started.get("status") != "started":
                    raise self._error(started)
                completed = receive_message(connection)
                if completed.get("status") != "exited":
                    raise self._error(completed)
                exit_status = completed.get("exitStatus")
                if not isinstance(exit_status, int) or not 0 <= exit_status <= 255:
                    raise BrokerClientError("broker-response-invalid", "broker response is invalid")
                return exit_status
        except BrokerClientError:
            raise
        except (OSError, BrokerProtocolError) as error:
            raise BrokerClientError(
                "broker-unavailable", "the MCPStack execution broker is unavailable"
            ) from error

    @staticmethod
    def _error(payload: dict) -> BrokerClientError:
        code = payload.get("code")
        message = payload.get("message")
        return BrokerClientError(
            code if isinstance(code, str) else "broker-request-failed",
            (
                message
                if isinstance(message, str)
                else "the configured MCP target could not be launched"
            ),
            payload.get("exitStatus") if isinstance(payload.get("exitStatus"), int) else 126,
        )
