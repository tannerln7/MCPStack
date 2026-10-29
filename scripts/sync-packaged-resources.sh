#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

install -m 0644 \
  "${repo_root}/schemas/domain/stack-config.schema.json" \
  "${repo_root}/backend/src/mcp_stack/resources/stack-config.schema.json"
