#!/usr/bin/env bash
set -euo pipefail

# Run only during unprivileged preparation, never resolve user tools as root.
if [[ "$#" -ne 1 || ! -d "$1" ]]; then
  printf 'Usage: bash %s existing-stage-directory\n' "$0" >&2
  exit 2
fi
stage="$1"

resolve_executable() {
  local tool="$1" candidate resolved mise_executable expected_version="" actual_version
  mise_executable="$(command -v mise || true)"
  while IFS= read -r candidate; do
    # Inactive mise shims may successfully fall through to another PATH entry
    # even though "mise which" fails. Never select an arbitrary inactive install.
    if [[ -n "${mise_executable}" ]] && \
      { [[ "${candidate}" -ef "${mise_executable}" ]] || [[ "${candidate}" == */mise/shims/* ]]; }; then
      if resolved="$("${mise_executable}" which "${tool}" 2>/dev/null)"; then
        candidate="${resolved}"
      else
        if [[ -z "${expected_version}" ]]; then
          expected_version="$("${candidate}" --version)" || {
            printf 'Could not resolve the mise-managed %s executable.\n' "${tool}" >&2
            return 1
          }
        fi
        continue
      fi
    fi
    if [[ "${candidate}" != /* || ! -f "${candidate}" || ! -x "${candidate}" ]]; then
      printf 'Resolved %s is not an absolute executable file.\n' "${tool}" >&2
      return 1
    fi
    if [[ -n "${expected_version}" ]]; then
      actual_version="$("${candidate}" --version)"
      if [[ "${actual_version}" != "${expected_version}" ]]; then
        printf 'PATH fallback for %s does not match the mise shim; refusing installation.\n' "${tool}" >&2
        return 1
      fi
    fi
    printf '%s\n' "${candidate}"
    return 0
  done < <(type -a -p "${tool}")
  printf 'Could not resolve a standalone %s executable from PATH.\n' "${tool}" >&2
  return 1
}

for tool in uv node; do
  executable="$(resolve_executable "${tool}")"
  install -m 0755 "${executable}" "${stage}/${tool}"
  # Prove the copied file works without mise settings, shims or shell activation.
  if ! version="$(env -i PATH=/usr/bin:/bin "${stage}/${tool}" --version)"; then
    printf 'Staged %s cannot run independently; refusing privileged installation.\n' "${tool}" >&2
    exit 1
  fi
  if { [[ "${tool}" == uv && ! "${version}" =~ ^uv\ [0-9] ]]; } || \
    { [[ "${tool}" == node && ! "${version}" =~ ^v[0-9] ]]; }; then
    printf 'Staged %s returned an unexpected version; refusing privileged installation.\n' "${tool}" >&2
    exit 1
  fi
done
