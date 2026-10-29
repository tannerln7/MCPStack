from __future__ import annotations

from pathlib import Path

from mcp_stack.broker.server import BrokerServer


class CapturingSocket:
    def __init__(self) -> None:
        self.bound_address: str | None = None

    def bind(self, address) -> None:
        assert isinstance(address, str)
        self.bound_address = address

    def listen(self, backlog: int) -> None:
        assert backlog > 0

    def close(self) -> None:
        pass


def test_broker_converts_path_to_unix_socket_address(tmp_path: Path, monkeypatch) -> None:
    socket_path = tmp_path / "runtime" / "broker.sock"
    listener = CapturingSocket()
    monkeypatch.setattr("mcp_stack.broker.server.socket.socket", lambda *_args: listener)
    monkeypatch.setattr("mcp_stack.broker.server.os.chmod", lambda *_args: None)
    server = BrokerServer(
        socket_path,
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
    )
    server._stop.set()

    server.serve_forever()

    assert listener.bound_address == str(socket_path)
