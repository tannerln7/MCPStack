#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

uv run --project "${repo_root}/backend" ruff check \
  "${repo_root}/backend" \
  "${repo_root}/scripts/runtime/deployment-settings.py"
uv run --project "${repo_root}/backend" ruff format --check \
  "${repo_root}/backend" \
  "${repo_root}/scripts/runtime/deployment-settings.py"
uv run --project "${repo_root}/backend" pytest

generated_contract="$(mktemp "${repo_root}/frontend/src/lib/contracts/api.generated.XXXXXX.ts")"
trap 'rm -f -- "${generated_contract}"' EXIT
pnpm --dir "${repo_root}/frontend" exec openapi-typescript \
  "${repo_root}/schemas/api/mcp-stack.openapi.yaml" \
  -o "${generated_contract}"
pnpm --dir "${repo_root}/frontend" exec biome format --write "${generated_contract}"
if ! cmp -s "${generated_contract}" "${repo_root}/frontend/src/lib/contracts/api.generated.ts"; then
  printf "Generated frontend API types are stale. Run: pnpm --filter frontend contracts:generate\n" >&2
  exit 1
fi

pnpm --dir "${repo_root}/frontend" lint
pnpm --dir "${repo_root}/frontend" typecheck
pnpm --dir "${repo_root}/frontend" test
pnpm --dir "${repo_root}/frontend" build

printf "\nAll configured repository checks passed.\n"
