# Contributing

Small, focused improvements are welcome. For larger changes, discuss the problem
before building a new subsystem.

1. Read the [installation](docs/installation.md) and [usage](docs/usage.md) guides.
2. Make one focused change and add tests for changed behavior.
3. Update the relevant user guide if a workflow or command changes.
4. Run `./scripts/validate.sh`.
5. Describe the change and how you tested it in your pull request.

Use conventional commit subjects such as `fix: preserve configured public origins`.
Keep unrelated refactors out of bug fixes. Do not commit build output, local
deployment settings, service-specific installation scripts, or real Stack files.

## Before sharing logs or examples

- Replace domains, usernames, tunnel IDs, and private paths with examples.
- Use fake credentials in tests; never include real secret values.
- Keep examples generic and do not make them part of an automatic live install.
- Check `git diff --check` and review every staged file.

## Architecture boundaries

The frontend presents explicit APIs; the backend owns files and execution.
Filesystem configuration is authoritative. Runtime/health observations remain
separate. New persistence or execution/security boundaries need an architecture
discussion before implementation.

## Build and test

Use the same Python, Node.js, uv, and pnpm requirements listed in the
[installation guide](docs/installation.md). From the repository root:

```bash
pnpm install --frozen-lockfile
uv sync --project backend --frozen
./scripts/validate.sh
```

Validation checks backend lint/tests, installer helpers, packaged schemas,
generated API types, frontend lint/types/tests, and the production build.
The installer builds and installs from source; it is not needed to run tests.

After changing contracts, run:

```bash
./scripts/sync-packaged-resources.sh
pnpm --filter frontend contracts:generate
```

Keep tests isolated from live configuration and service state. Use disposable
files and fake credentials, and never run experimental lifecycle commands
against unrelated services.

Report suspected vulnerabilities through the [security policy](SECURITY.md),
not a public issue with reproduction credentials.
