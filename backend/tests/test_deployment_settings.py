from __future__ import annotations

import importlib.util
import stat
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def settings(repository_root: Path):
    spec = importlib.util.spec_from_file_location(
        "deployment_settings", repository_root / "scripts/runtime/deployment-settings.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_setting_precedence_and_explicit_clear(settings, tmp_path: Path, monkeypatch) -> None:
    installed = tmp_path / "installed.env"
    installed.write_text(
        'MCP_STACK_PUBLIC_ORIGINS="https://old.example.com"\n'
        'MCP_STACK_TUNNEL_BUNDLE="/opt/tunnel bundle"\n'
    )
    monkeypatch.setattr(settings, "legacy_origin", lambda: pytest.fail("unexpected fallback"))
    preserved = settings.resolve(tmp_path, {}, installed)
    assert preserved[settings.KEYS[0]] == "https://old.example.com"
    assert preserved[settings.KEYS[1]] == "/opt/tunnel bundle"

    (tmp_path / ".env").write_text(
        "# local override\nMCP_STACK_PUBLIC_ORIGINS=https://local.example.com\n"
    )
    assert settings.resolve(tmp_path, {}, installed)[settings.KEYS[0]] == (
        "https://local.example.com"
    )
    assert settings.resolve(tmp_path, {settings.KEYS[0]: ""}, installed)[settings.KEYS[0]] == ""
    assert (
        settings.resolve(tmp_path, {settings.KEYS[0]: "https://export.example.com"}, installed)[
            settings.KEYS[0]
        ]
        == "https://export.example.com"
    )


def test_legacy_origin_is_preserved_and_new_install_is_local(settings, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "legacy_origin", lambda: "https://existing.example.com")
    assert settings.resolve(tmp_path, {}, tmp_path / "missing")[settings.KEYS[0]] == (
        "https://existing.example.com"
    )
    monkeypatch.setattr(settings, "legacy_origin", lambda: "")
    assert settings.resolve(tmp_path, {}, tmp_path / "missing") == dict.fromkeys(settings.KEYS, "")


def test_legacy_lookup_uses_only_public_origin(settings, monkeypatch):
    def run(argv, **kwargs):
        assert argv[:3] == ["systemctl", "show", "mcp-stack-api.service"]
        return subprocess.CompletedProcess(
            argv,
            0,
            "UNRELATED=fixture-only MCP_STACK_PUBLIC_ORIGINS=https://existing.example.com",
        )

    monkeypatch.setattr(settings.subprocess, "run", run)
    assert settings.legacy_origin() == "https://existing.example.com"


def test_explicit_settings_file_is_used_and_missing_is_rejected(settings, tmp_path: Path):
    override = tmp_path / "custom.env"
    override.write_text('MCP_STACK_PUBLIC_ORIGINS="https://custom.example.com"\n')
    environment = {"MCP_STACK_DEPLOYMENT_ENV": str(override)}
    assert settings.resolve(tmp_path, environment, tmp_path / "absent")[settings.KEYS[0]] == (
        "https://custom.example.com"
    )
    override.unlink()
    with pytest.raises(ValueError, match="missing"):
        settings.resolve(tmp_path, environment, tmp_path / "absent")


@pytest.mark.parametrize(
    "content",
    [
        "SECRET_API_KEY=fixture-only-do-not-echo\n",
        "LD_PRELOAD=/tmp/fixture-only\n",
        "export MCP_STACK_PUBLIC_ORIGINS=\n",
        "MCP_STACK_PUBLIC_ORIGINS=\nMCP_STACK_PUBLIC_ORIGINS=\n",
        'MCP_STACK_PUBLIC_ORIGINS="unterminated\n',
        "MCP_STACK_TUNNEL_BUNDLE=/path with spaces\n",
    ],
)
def test_rejects_unknown_keys_and_unsupported_syntax(settings, tmp_path: Path, content: str):
    path = tmp_path / "input.env"
    path.write_text(content)
    with pytest.raises(ValueError) as error:
        settings.read_settings(path)
    assert "fixture-only" not in str(error.value)


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.com/",
        "https://example.com/path",
        "https://user:pass@example.com",
        "javascript:alert(1)",
        "https://example.com\nOTHER=value",
        "https://example.com:99999",
        "https://example.com:443",
        "http://example.com:80",
        "https://example.com#",
        "https://example.com?",
        "https://example.com\\path",
    ],
)
def test_rejects_unsafe_origins(settings, origin: str):
    with pytest.raises(ValueError):
        settings.validate({settings.KEYS[0]: origin})


def test_literals_are_never_executed(settings, tmp_path: Path):
    marker = tmp_path / "not-created"
    value = f"/tmp/$(touch {marker})"
    path = tmp_path / "input.env"
    path.write_text(f'MCP_STACK_TUNNEL_BUNDLE="{value}"\n')
    settings.validate(settings.read_settings(path))
    assert settings.read_settings(path)[settings.KEYS[1]] == value
    assert not marker.exists()


def test_settings_replacement_preserves_values_and_has_no_secret_fields(settings, tmp_path: Path):
    path = tmp_path / "deployment.env"
    values = {
        settings.KEYS[0]: "https://mcp.example.com,https://other.example.com",
        settings.KEYS[1]: '/opt/tunnel "bundle"',
    }
    settings.write_settings(path, values)
    assert settings.read_settings(path) == values
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    values[settings.KEYS[0]] = ""
    settings.write_settings(path, values)
    assert settings.read_settings(path) == values
    assert list(tmp_path.glob(".deployment-*")) == []


def test_failed_replacement_keeps_old_settings(settings, tmp_path: Path, monkeypatch):
    path = tmp_path / "deployment.env"
    path.write_text("# original\n")

    def fail(*args):
        raise OSError("fixture failure")

    monkeypatch.setattr(settings.os, "replace", fail)
    with pytest.raises(OSError):
        settings.write_settings(path, {})
    assert path.read_text() == "# original\n"
    assert list(tmp_path.glob(".deployment-*")) == []


def test_symlinks_and_oversize_files_are_rejected(settings, tmp_path: Path):
    target = tmp_path / "target.env"
    target.write_text("# example\n")
    link = tmp_path / "linked.env"
    link.symlink_to(target)
    with pytest.raises(OSError):
        settings.read_settings(link)
    with pytest.raises(ValueError):
        settings.write_settings(link, {})
    target.write_text("#" * 16_385)
    with pytest.raises(ValueError, match="16 KiB"):
        settings.read_settings(target)


def test_cli_errors_never_echo_input(settings, tmp_path: Path, monkeypatch, capsys):
    path = tmp_path / "bad.env"
    path.write_text("SECRET_API_KEY=fixture-only-do-not-echo\n")
    monkeypatch.setattr(
        sys, "argv", ["settings", "get", "--file", str(path), "--key", settings.KEYS[0]]
    )
    assert settings.main() == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "invalid or inaccessible" in output.err
    assert "fixture-only" not in output.err


def test_dotenv_template_contains_only_allowed_settings(settings, repository_root: Path):
    values = settings.read_settings(repository_root / ".env.example")
    assert values == dict.fromkeys(settings.KEYS, "")
