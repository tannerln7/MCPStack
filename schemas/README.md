# Shared contracts

These files define what the backend and frontend agree on:

- `domain/stack-config.schema.json` — durable Stack configuration.
- `api/mcp-stack.openapi.yaml` — HTTP API requests and responses.
- `api/runtime-snapshot.schema.json` — transient runtime observations.
- `examples/` — synthetic test configurations with no secret values.

JSON Schema Draft 2020-12 owns configuration. OpenAPI owns the HTTP boundary.
Generated Python/TypeScript representations are not independent authorities.

Live configuration is service-owned under `/var/lib/mcp-stack/`.
Repository examples are test inputs, not a mirror of that directory.

Edits submit complete source documents for validation. Saves require the original
revision, validate the repository, and preserve submitted bytes exactly. Secret
values are handled through separate write-only endpoints.

## Updating contracts

The Python wheel includes a derived copy of the Stack schema using
`importlib.resources`; runtime discovery does not depend on a source checkout.

After a schema/API change, run:

```bash
./scripts/sync-packaged-resources.sh
pnpm --filter frontend contracts:generate
./scripts/validate.sh
```

Tests check packaged-schema freshness and generated API types.
