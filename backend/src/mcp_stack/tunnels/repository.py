from __future__ import annotations

import hashlib
import os
import re
import secrets
import stat
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from .models import TunnelProfile, TunnelProfileCreate, TunnelProfileSummary, TunnelTarget

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]{0,79}$")
_MAX_PROFILE_BYTES = 256 * 1024


class TunnelProfileError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class TunnelProfileRepository:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().absolute()

    def list(self) -> list[TunnelProfileSummary]:
        if not self.root.is_dir():
            return []
        summaries: list[TunnelProfileSummary] = []
        for path in sorted(self.root.iterdir()):
            if path.suffix.lower() not in {".yaml", ".yml"}:
                continue
            try:
                summaries.append(
                    TunnelProfileSummary(profile=self._read(path), path=path.name, valid=True)
                )
            except TunnelProfileError as error:
                summaries.append(
                    TunnelProfileSummary(
                        profile=None,
                        path=path.name,
                        valid=False,
                        diagnostic=str(error),
                    )
                )
        return summaries

    def get(self, profile_id: str) -> TunnelProfile | None:
        self._validate_id(profile_id)
        for suffix in (".yaml", ".yml"):
            path = self.root / f"{profile_id}{suffix}"
            if path.exists() or path.is_symlink():
                return self._read(path)
        return None

    def create(self, candidate: TunnelProfileCreate) -> TunnelProfile:
        raw = self._candidate_bytes(candidate)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root_fd = self._open_root()
        temporary = f".{candidate.id}.{secrets.token_hex(8)}.tmp"
        destination = f"{candidate.id}.yaml"
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=root_fd,
            )
            try:
                self._write_all(descriptor, raw)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            try:
                os.link(
                    temporary,
                    destination,
                    src_dir_fd=root_fd,
                    dst_dir_fd=root_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as error:
                raise TunnelProfileError(
                    "profile-exists", "Tunnel profile already exists"
                ) from error
            os.unlink(temporary, dir_fd=root_fd)
            temporary = ""
            os.fsync(root_fd)
        finally:
            if temporary:
                with suppress(OSError):
                    os.unlink(temporary, dir_fd=root_fd)
            os.close(root_fd)
        profile = self.get(candidate.id)
        if profile is None:
            raise TunnelProfileError(
                "uncertain-write", "Tunnel profile creation could not be verified"
            )
        return profile

    def update(
        self, profile_id: str, original_revision: str, candidate: TunnelProfileCreate
    ) -> TunnelProfile:
        if candidate.id != profile_id:
            raise TunnelProfileError("profile-id-mismatch", "Tunnel profile identity cannot change")
        raw = self._candidate_bytes(candidate)
        current = self.get(profile_id)
        if current is None:
            raise TunnelProfileError("profile-not-found", "Tunnel profile was not found")
        root_fd = self._open_root()
        temporary = f".{profile_id}.{secrets.token_hex(8)}.tmp"
        try:
            original_bytes, source_stat = self._read_entry(root_fd, current.path)
            self._require_revision(original_bytes, original_revision)
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=root_fd,
            )
            try:
                self._write_all(descriptor, raw)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            final_bytes, final_stat = self._read_entry(root_fd, current.path)
            if (final_stat.st_dev, final_stat.st_ino) != (
                source_stat.st_dev,
                source_stat.st_ino,
            ):
                raise TunnelProfileError(
                    "profile-revision-conflict", "Tunnel profile changed on disk"
                )
            self._require_revision(final_bytes, original_revision)
            os.replace(temporary, current.path, src_dir_fd=root_fd, dst_dir_fd=root_fd)
            temporary = ""
            os.fsync(root_fd)
        except TunnelProfileError:
            raise
        except OSError as error:
            raise TunnelProfileError(
                "profile-write-failed", "Tunnel profile could not be safely replaced"
            ) from error
        finally:
            if temporary:
                with suppress(OSError):
                    os.unlink(temporary, dir_fd=root_fd)
            os.close(root_fd)
        profile = self.get(profile_id)
        if profile is None or profile.revision != hashlib.sha256(raw).hexdigest():
            raise TunnelProfileError(
                "uncertain-write", "Tunnel profile replacement could not be verified"
            )
        return profile

    def verify_deletion(self, profile_id: str, original_revision: str) -> TunnelProfile:
        current = self.get(profile_id)
        if current is None:
            raise TunnelProfileError("profile-not-found", "Tunnel profile was not found")
        root_fd = self._open_root()
        try:
            raw, _ = self._read_entry(root_fd, current.path)
            self._require_revision(raw, original_revision)
        finally:
            os.close(root_fd)
        return current

    def delete(self, profile_id: str, original_revision: str) -> TunnelProfile:
        current = self.verify_deletion(profile_id, original_revision)
        root_fd = self._open_root()
        try:
            raw, _ = self._read_entry(root_fd, current.path)
            self._require_revision(raw, original_revision)
            os.unlink(current.path, dir_fd=root_fd)
            os.fsync(root_fd)
        except TunnelProfileError:
            raise
        except OSError as error:
            raise TunnelProfileError(
                "profile-delete-failed", "Tunnel profile could not be safely deleted"
            ) from error
        finally:
            os.close(root_fd)
        if self.get(profile_id) is not None:
            raise TunnelProfileError(
                "uncertain-delete", "Tunnel profile deletion could not be verified"
            )
        return current

    def _candidate_bytes(self, candidate: TunnelProfileCreate) -> bytes:
        self._validate_id(candidate.id)
        self._validate_base_url(candidate.base_url)
        self._validate_health_listener(candidate.health_listen_addr)
        if candidate.target_kind == "stdio":
            if not candidate.stack_target or candidate.url:
                raise TunnelProfileError("invalid-target", "A configured Stack target is required")
            target = {
                "commands": [
                    {
                        "channel": candidate.channel,
                        "command": f"mcpctl stdio {candidate.stack_target}",
                    }
                ]
            }
        else:
            if not candidate.url or candidate.stack_target:
                raise TunnelProfileError("invalid-target", "A valid HTTP MCP URL is required")
            self._validate_base_url(candidate.url)
            target = {"server_urls": [{"channel": candidate.channel, "url": candidate.url}]}
        document = {
            "config_version": 1,
            "control_plane": {
                "base_url": candidate.base_url,
                "tunnel_id": candidate.tunnel_id,
                "api_key": "env:CONTROL_PLANE_API_KEY",
            },
            "health": {"listen_addr": candidate.health_listen_addr},
            "admin_ui": {"open_browser": False},
            "log": {"level": "info", "format": "json"},
            "mcp": target,
        }
        raw = yaml.safe_dump(document, sort_keys=False).encode("utf-8")
        if len(raw) > _MAX_PROFILE_BYTES:
            raise TunnelProfileError("profile-too-large", "Tunnel profile is too large")
        return raw

    def _open_root(self) -> int:
        root_stat = self.root.lstat()
        if (
            stat.S_ISLNK(root_stat.st_mode)
            or not stat.S_ISDIR(root_stat.st_mode)
            or root_stat.st_uid != os.getuid()
        ):
            raise TunnelProfileError(
                "unsupported-workspace", "Tunnel profile workspace is unsupported"
            )
        os.chmod(self.root, 0o700)
        return os.open(
            self.root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        )

    def _read_entry(self, root_fd: int, name: str) -> tuple[bytes, os.stat_result]:
        if Path(name).name != name or Path(name).suffix.lower() not in {".yaml", ".yml"}:
            raise TunnelProfileError("unsupported-profile", "Tunnel profile path is unsupported")
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=root_fd,
        )
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.geteuid()
                or metadata.st_nlink != 1
                or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                raise TunnelProfileError(
                    "unsupported-profile", "Tunnel profile ownership or permissions are unsupported"
                )
            chunks: list[bytes] = []
            remaining = _MAX_PROFILE_BYTES + 1
            while remaining:
                chunk = os.read(descriptor, min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            if len(raw) > _MAX_PROFILE_BYTES:
                raise TunnelProfileError("profile-too-large", "Tunnel profile is too large")
            return raw, metadata
        finally:
            os.close(descriptor)

    @staticmethod
    def _require_revision(raw: bytes, original_revision: str) -> None:
        if hashlib.sha256(raw).hexdigest() != original_revision:
            raise TunnelProfileError("profile-revision-conflict", "Tunnel profile changed on disk")

    @staticmethod
    def _write_all(descriptor: int, raw: bytes) -> None:
        written = 0
        while written < len(raw):
            count = os.write(descriptor, raw[written:])
            if count == 0:
                raise OSError("short tunnel profile write")
            written += count

    def _read(self, path: Path) -> TunnelProfile:
        try:
            source_stat = path.lstat()
        except OSError as error:
            raise TunnelProfileError(
                "profile-unreadable", "Tunnel profile is unavailable"
            ) from error
        if stat.S_ISLNK(source_stat.st_mode) or not stat.S_ISREG(source_stat.st_mode):
            raise TunnelProfileError("unsupported-profile", "Tunnel profile must be a regular file")
        if source_stat.st_nlink != 1 or source_stat.st_uid != os.getuid():
            raise TunnelProfileError(
                "unsupported-profile", "Tunnel profile ownership is unsupported"
            )
        if stat.S_IMODE(source_stat.st_mode) & 0o077:
            raise TunnelProfileError("unsupported-profile", "Tunnel profile must have mode 0600")
        try:
            raw = path.read_bytes()
            if len(raw) > _MAX_PROFILE_BYTES:
                raise TunnelProfileError("profile-too-large", "Tunnel profile is too large")
            data = yaml.safe_load(raw)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
            raise TunnelProfileError(
                "profile-invalid", "Tunnel profile could not be parsed"
            ) from error
        try:
            if not isinstance(data, dict) or data.get("config_version") != 1:
                raise ValueError
            control = data["control_plane"]
            if control.get("api_key") != "env:CONTROL_PLANE_API_KEY":
                raise TunnelProfileError(
                    "unsafe-credential-reference",
                    "Tunnel profile must use env:CONTROL_PLANE_API_KEY",
                )
            mcp = data["mcp"]
            commands = mcp.get("commands", [])
            urls = mcp.get("server_urls", [])
            if (len(commands) == 1) == (len(urls) == 1):
                raise ValueError
            if commands:
                item = commands[0]
                target = TunnelTarget("stdio", item["channel"], command=item["command"])
            else:
                item = urls[0]
                target = TunnelTarget("http", item["channel"], url=item["url"])
            health = data.get("health", {})
            logging = data.get("log", {})
            profile_id = path.stem
            self._validate_id(profile_id)
            return TunnelProfile(
                id=profile_id,
                path=path.name,
                revision=hashlib.sha256(raw).hexdigest(),
                tunnel_id=str(control["tunnel_id"]),
                base_url=str(control.get("base_url", "https://api.openai.com")),
                target=target,
                health_listen_addr=str(health.get("listen_addr", "127.0.0.1:0")),
                log_level=str(logging.get("level", "info")),
                log_format=str(logging.get("format", "json")),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise TunnelProfileError(
                "profile-invalid", "Tunnel profile structure is invalid"
            ) from error

    @staticmethod
    def _validate_id(profile_id: str) -> None:
        if not _IDENTIFIER.fullmatch(profile_id):
            raise TunnelProfileError("invalid-profile-id", "Tunnel profile ID is invalid")

    @staticmethod
    def _validate_base_url(value: str) -> None:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise TunnelProfileError(
                "invalid-target", "Tunnel URL must be an HTTP(S) URL without credentials"
            )

    @staticmethod
    def _validate_health_listener(value: str) -> None:
        try:
            host, port_text = value.rsplit(":", 1)
            port = int(port_text)
        except ValueError as error:
            raise TunnelProfileError(
                "invalid-health-listener", "Health listener must be a loopback host and port"
            ) from error
        if host not in {"127.0.0.1", "localhost", "::1", "[::1]"} or not 0 <= port <= 65535:
            raise TunnelProfileError(
                "invalid-health-listener", "Health listener must use a loopback address"
            )
