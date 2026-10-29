#!/usr/bin/env python3
"""Allowlisted deployment settings shared by the installer and systemd."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

KEYS = ("MCP_STACK_PUBLIC_ORIGINS", "MCP_STACK_TUNNEL_BUNDLE")
INSTALLED = Path("/etc/mcp-stack/deployment.env")


def read_settings(path: Path) -> dict[str, str]:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        if path.is_symlink():
            raise ValueError("Settings file must not be a symlink") from None
        return {}
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Settings file must be a regular file")
        if os.fstat(stream.fileno()).st_size > 16_384:
            raise ValueError("Settings file exceeds 16 KiB")
        content = stream.read(16_385)
    result: dict[str, str] = {}
    for number, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, raw = line.partition("=")
        key = key.strip()
        if not separator or key not in KEYS or key in result:
            raise ValueError(f"Unsupported or repeated setting at line {number}")
        try:
            parts = shlex.split(raw, comments=False)
        except ValueError:
            raise ValueError(f"Invalid quoting at line {number}") from None
        if len(parts) > 1:
            raise ValueError(f"Quote values containing spaces at line {number}")
        result[key] = parts[0] if parts else ""
    return result


def validate(settings: Mapping[str, str]) -> None:
    for key, value in settings.items():
        if key not in KEYS or any(ord(character) < 32 for character in value):
            raise ValueError("Unsupported deployment setting or control character")
    origins = settings.get(KEYS[0], "")
    for origin in origins.split(",") if origins else []:
        try:
            parsed = urlsplit(origin)
            valid = (
                parsed.scheme in {"http", "https"}
                and parsed.hostname
                and not parsed.username
                and not parsed.password
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
                and parsed.port != 0
                and (parsed.scheme, parsed.port) not in {("http", 80), ("https", 443)}
                and re.fullmatch(r"https?://[A-Za-z0-9._:\[\]-]+", origin)
                and not any(character.isspace() for character in origin)
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError(
                "Public origins must be comma-separated exact HTTP(S) origins"
            )
    bundle = settings.get(KEYS[1], "")
    if bundle and not Path(bundle).is_absolute():
        raise ValueError("Tunnel bundle must be an absolute path or empty")


def legacy_origin() -> str:
    try:
        result = subprocess.run(
            [
                "systemctl",
                "show",
                "mcp-stack-api.service",
                "--property=Environment",
                "--value",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            for assignment in shlex.split(result.stdout):
                key, _, value = assignment.partition("=")
                if key == KEYS[0]:
                    return value
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return ""


def resolve(
    repo: Path, environment: Mapping[str, str], installed: Path = INSTALLED
) -> dict[str, str]:
    settings = read_settings(installed)
    local = Path(environment.get("MCP_STACK_DEPLOYMENT_ENV", str(repo / ".env")))
    if "MCP_STACK_DEPLOYMENT_ENV" in environment and not local.exists():
        raise ValueError("Explicit deployment settings file is missing")
    settings.update(read_settings(local))
    settings.update({key: environment[key] for key in KEYS if key in environment})
    if KEYS[0] not in settings:
        settings[KEYS[0]] = legacy_origin()
    settings.setdefault(KEYS[1], "")
    validate(settings)
    return settings


def write_settings(path: Path, settings: Mapping[str, str]) -> None:
    validate(settings)
    if path.is_symlink():
        raise ValueError("Settings destination must not be a symlink")
    lines = ["# Non-secret MCPStack deployment settings. No API keys here.\n"]
    for key in KEYS:
        escaped = settings.get(key, "").replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{key}="{escaped}"\n')
    descriptor, temporary = tempfile.mkstemp(prefix=".deployment-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.writelines(lines)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), 0o644)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("resolve", "install", "get"))
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--key", choices=KEYS)
    args = parser.parse_args()
    try:
        if args.action == "resolve":
            if args.repo is None:
                parser.error("resolve requires --repo")
            write_settings(args.file, resolve(args.repo, os.environ))
        elif args.action == "install":
            if not args.file.is_file():
                raise ValueError("Prepared deployment settings file is missing")
            settings = read_settings(args.file)
            if set(settings) != set(KEYS):
                raise ValueError("Prepared deployment settings are incomplete")
            write_settings(INSTALLED, settings)
        else:
            if args.key is None:
                parser.error("get requires --key")
            settings = read_settings(args.file)
            validate(settings)
            print(settings.get(args.key, ""))
    except (OSError, UnicodeError, ValueError):
        # Do not include input values or parser exceptions in installer diagnostics.
        print(
            "Deployment settings are invalid or inaccessible; check the allowed keys and format.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
