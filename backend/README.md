# Backend

The backend package supplies three installed commands:

- `mcp-stack-api` — loopback FastAPI service;
- `mcp-stack-broker` — Unix-socket stdio execution broker;
- `mcpctl` — unprivileged MCP-client shim.

Production configuration and secrets are service-owned under
`/var/lib/mcp-stack`; transient broker/session state is under
`/run/mcp-stack`. Tests and development may override those roots with
the documented `MCP_STACK_*` environment variables.

The browser can retrieve Stack source and safe secret-slot metadata. It can
replace or clear a secret value, but no model, API, exception, log response, or
form hydration path returns the stored value. Execution is the only trusted
consumer of the internal secret resolver.

Run locally against repository fixtures:

```bash
MCP_STACK_CONFIG_DIR="$PWD/config/stacks" \
MCP_STACK_SECRET_DIR=/tmp/mcp-stack-dev-secrets \
MCP_STACK_RUNTIME_DIR=/tmp/mcp-stack-dev-runtime \
  uv run --project backend mcp-stack-api
```

The runtime JSON Schema is packaged with the wheel and freshness-checked
against `schemas/domain/stack-config.schema.json`.
