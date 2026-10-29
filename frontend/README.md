# Frontend

Next.js App Router presentation layer for MCPStack. It renders Stack
configuration, runtime observations, and health from the backend API
and has no direct access to local files or managed resources.

The Stack collection renders independently discovered backend sources, source
revision metadata, runtime/health indicators, and structured validation
diagnostics. Empty, loading, API error, and invalid-source states use reusable
generic components.

The generic Stack editor hydrates the same authored fields used by New Stack,
regenerates a complete YAML candidate with a round-trip YAML document model,
and submits validation previews and complete-source saves through thin Next.js
Route Handlers. Advanced sections outside the primary edited Component remain
in the candidate. The frontend never receives filesystem authority.

The New Stack wizard is an authored workflow form for common stdio MCP, HTTP
MCP, and managed Application configurations. The Tunnels page lists the
installed tunnel client and configured profiles, accepts a one-way credential
update, and controls deterministic backend-owned profile units. Stack pages
link to or control profiles whose generated target is `mcpctl stdio <stack>`.

Run from the repository root:

```bash
MCP_STACK_API_URL=http://127.0.0.1:8000 pnpm --filter frontend dev
```

Set `MCP_STACK_PUBLIC_ORIGINS` to a comma-separated list of exact HTTPS
origins when the loopback UI is published through an authenticated tunnel.

The normal UI boundary is project-owned shadcn source using one provisional
Base UI primitive layer. `ConfigurationViewer` remains the schema-driven,
read-only adapter; creation and editing use the bounded authored Stack form
rather than introducing a second general-purpose schema-renderer ecosystem.
