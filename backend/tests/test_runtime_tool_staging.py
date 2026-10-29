from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest


def executable(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nset -eu\n" + body + "\n")
    path.chmod(0o755)
    return path


def stage_tools(repository_root: Path, tmp_path: Path, environment: dict[str, str]):
    stage = tmp_path / "stage"
    stage.mkdir()
    result = subprocess.run(
        ["bash", str(repository_root / "scripts/runtime/stage-service-tools.sh"), str(stage)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result, stage


def tools(tmp_path: Path):
    native = tmp_path / "native tools"
    uv = executable(native / "uv", "printf 'uv 0.9.0\\n'")
    node = executable(native / "node", "printf 'v24.0.0\\n'")
    return native, uv, node


def test_stages_standalone_tools_without_asking_mise(repository_root: Path, tmp_path: Path):
    native, uv, node = tools(tmp_path)
    executable(native / "mise", "echo 'standalone tools must not invoke mise' >&2; exit 99")
    result, stage = stage_tools(repository_root, tmp_path, {"PATH": f"{native}:/usr/bin:/bin"})
    assert result.returncode == 0, result.stderr
    for original in (uv, node):
        copy = stage / original.name
        assert copy.read_bytes() == original.read_bytes()
        assert copy.stat().st_mode & 0o777 == 0o755


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "script"])
def test_stages_real_mise_tools_not_shims(repository_root: Path, tmp_path: Path, kind: str):
    _, uv, node = tools(tmp_path)
    bin_dir = tmp_path / "bin"
    mise = executable(
        bin_dir / "mise",
        'if [ "$1" = which ]; then\n'
        '  case "$2" in uv) printf "%s\\n" "$REAL_UV";; '
        'node) printf "%s\\n" "$REAL_NODE";; esac\n'
        'else printf "mise 2026.10.19\\n"; fi',
    )
    shims = tmp_path / "mise/shims" if kind == "script" else bin_dir
    shims.mkdir(parents=True, exist_ok=True)
    for tool in ("uv", "node"):
        shim = shims / tool
        if kind == "symlink":
            shim.symlink_to(mise)
        elif kind == "hardlink":
            os.link(mise, shim)
        else:
            executable(shim, f'exec {shlex.quote(str(mise))} {tool} "$@"')
    result, stage = stage_tools(
        repository_root,
        tmp_path,
        {
            "PATH": f"{shims}:{bin_dir}:/usr/bin:/bin",
            "REAL_UV": str(uv),
            "REAL_NODE": str(node),
        },
    )
    assert result.returncode == 0, result.stderr
    assert (stage / "uv").read_bytes() == uv.read_bytes()
    assert (stage / "node").read_bytes() == node.read_bytes()


def test_refuses_unresolved_mise_shim(repository_root: Path, tmp_path: Path):
    bin_dir = tmp_path / "bin"
    mise = executable(bin_dir / "mise", "exit 1")
    (bin_dir / "uv").symlink_to(mise)
    result, stage = stage_tools(repository_root, tmp_path, {"PATH": f"{bin_dir}:/usr/bin:/bin"})
    assert result.returncode != 0
    assert "Could not resolve the mise-managed uv" in result.stderr
    assert not (stage / "uv").exists()


@pytest.mark.parametrize("fallback_version", ["0.9.0", "0.8.0"])
def test_inactive_mise_shim_uses_matching_path_fallback(
    repository_root: Path, tmp_path: Path, fallback_version: str
):
    native, uv, node = tools(tmp_path)
    executable(uv, f"printf 'uv {fallback_version}\\n'")
    bin_dir = tmp_path / "bin"
    mise = executable(
        bin_dir / "mise",
        'if [ "$1" = which ]; then\n'
        '  echo "uv is a mise bin however it is not currently active" >&2; exit 1\n'
        'fi\nprintf "uv 0.9.0\\n"',
    )
    (bin_dir / "uv").symlink_to(mise)
    result, stage = stage_tools(
        repository_root, tmp_path, {"PATH": f"{bin_dir}:{native}:/usr/bin:/bin"}
    )
    if fallback_version == "0.9.0":
        assert result.returncode == 0, result.stderr
        assert (stage / "uv").read_bytes() == uv.read_bytes()
        assert (stage / "node").read_bytes() == node.read_bytes()
    else:
        assert result.returncode != 0
        assert "does not match the mise shim" in result.stderr
        assert not (stage / "uv").exists()


@pytest.mark.parametrize(
    "body,diagnostic",
    [
        ('test "${USER_TOOL_ENV:-}" = available; printf "uv 0.9.0\\n"', "cannot run independently"),
        ('printf "mise 2026.10.19\\n"', "unexpected version"),
    ],
)
def test_refuses_context_dependent_or_wrong_tool(
    repository_root: Path, tmp_path: Path, body: str, diagnostic: str
):
    native, uv, _ = tools(tmp_path)
    executable(uv, body)
    result, _ = stage_tools(
        repository_root,
        tmp_path,
        {"PATH": f"{native}:/usr/bin:/bin", "USER_TOOL_ENV": "available"},
    )
    assert result.returncode != 0
    assert diagnostic in result.stderr


def test_installer_stages_and_checks_tools_before_sudo(repository_root: Path):
    installer = (repository_root / "scripts/install-service.sh").read_text()
    assert installer.index('bash "${repo_root}/scripts/runtime/stage-service-tools.sh"') < (
        installer.index("  sudo ")
    )
    assert 'install -m 0755 "$(command -v uv)"' not in installer
