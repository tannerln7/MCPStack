from __future__ import annotations

import array
import json
import socket
import struct
from dataclasses import dataclass
from typing import Any, Literal

_MAX_MESSAGE_BYTES = 16 * 1024


class BrokerProtocolError(Exception):
    pass


@dataclass(frozen=True)
class LaunchRequest:
    version: Literal[1]
    action: Literal["stdio"]
    target: str


def encode_message(payload: dict[str, Any]) -> bytes:
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if len(encoded) > _MAX_MESSAGE_BYTES:
        raise BrokerProtocolError("broker message is too large")
    return struct.pack("!I", len(encoded)) + encoded


def send_message(connection: socket.socket, payload: dict[str, Any]) -> None:
    connection.sendall(encode_message(payload))


def receive_message(connection: socket.socket) -> dict[str, Any]:
    header = _receive_exact(connection, 4)
    length = struct.unpack("!I", header)[0]
    if length <= 0 or length > _MAX_MESSAGE_BYTES:
        raise BrokerProtocolError("broker message size is invalid")
    try:
        value = json.loads(_receive_exact(connection, length))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise BrokerProtocolError("broker message is invalid") from error
    if not isinstance(value, dict):
        raise BrokerProtocolError("broker message is invalid")
    return value


def send_launch_request(
    connection: socket.socket,
    target: str,
    descriptors: tuple[int, int, int],
) -> None:
    payload = encode_message({"version": 1, "action": "stdio", "target": target})
    ancillary = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", descriptors))]
    sent = connection.sendmsg([payload], ancillary)
    if sent < len(payload):
        connection.sendall(payload[sent:])


def receive_launch_request(connection: socket.socket) -> tuple[LaunchRequest, tuple[int, int, int]]:
    data, ancillary, _flags, _address = connection.recvmsg(
        _MAX_MESSAGE_BYTES + 4,
        socket.CMSG_SPACE(3 * array.array("i").itemsize),
    )
    if len(data) < 4:
        raise BrokerProtocolError("launch request is incomplete")
    length = struct.unpack("!I", data[:4])[0]
    if length <= 0 or length > _MAX_MESSAGE_BYTES:
        raise BrokerProtocolError("launch request size is invalid")
    body = data[4:]
    if len(body) < length:
        body += _receive_exact(connection, length - len(body))
    try:
        value = json.loads(body[:length])
    except (UnicodeError, json.JSONDecodeError) as error:
        raise BrokerProtocolError("launch request is invalid") from error
    if not isinstance(value, dict):
        raise BrokerProtocolError("launch request is invalid")
    if value.get("version") != 1 or value.get("action") != "stdio":
        raise BrokerProtocolError("launch request is unsupported")
    target = value.get("target")
    if not isinstance(target, str) or not target or len(target) > 240:
        raise BrokerProtocolError("launch target is invalid")
    received: list[int] = []
    for level, kind, payload in ancillary:
        if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
            values = array.array("i")
            values.frombytes(payload[: len(payload) - (len(payload) % values.itemsize)])
            received.extend(values)
    if len(received) != 3:
        for descriptor in received:
            try:
                import os

                os.close(descriptor)
            except OSError:
                pass
        raise BrokerProtocolError("launch request requires stdin, stdout, and stderr")
    return LaunchRequest(version=1, action="stdio", target=target), tuple(received)  # type: ignore[arg-type]


def _receive_exact(connection: socket.socket, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise BrokerProtocolError("broker connection closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
