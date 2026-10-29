from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port_text = os.environ.get("MCP_STACK_API_PORT", "8000")
    try:
        port = int(port_text)
    except ValueError as error:
        raise SystemExit("MCP_STACK_API_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise SystemExit("MCP_STACK_API_PORT must be between 1 and 65535")
    uvicorn.run(
        "mcp_stack.main:app",
        host="127.0.0.1",
        port=port,
        proxy_headers=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
