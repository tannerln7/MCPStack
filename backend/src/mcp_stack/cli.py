from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import BinaryIO, TextIO

from mcp_stack.broker import BrokerClient, BrokerClientError
from mcp_stack.configuration import default_broker_socket


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcpctl",
        description="Launch configured MCP resources from the local control-plane repository.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    stdio = commands.add_parser(
        "stdio", help="request one session-owned stdio MCP server from the local broker"
    )
    stdio.add_argument("target", help="Stack, Component, or <stack>/<component> identity")
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    stderr: TextIO | None = None,
    stdin_buffer: BinaryIO | None = None,
    stdout_buffer: BinaryIO | None = None,
    stderr_buffer: BinaryIO | None = None,
    broker_client: BrokerClient | None = None,
) -> int:
    diagnostic_stream = stderr or sys.stderr
    args = _parser().parse_args(argv)
    try:
        return (broker_client or BrokerClient(default_broker_socket())).launch_stdio(
            args.target,
            stdin_buffer or sys.stdin.buffer,
            stdout_buffer or sys.stdout.buffer,
            stderr_buffer or sys.stderr.buffer,
        )
    except BrokerClientError as error:
        print(f"mcpctl: error [{error.code}]: {error.message}", file=diagnostic_stream)
        return error.exit_status


def main() -> int:
    return run()
