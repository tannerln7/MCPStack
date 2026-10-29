from __future__ import annotations

import os
import re
import secrets
import stat
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from .models import SecretMetadata, SecretStoreError

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]{0,79}$")
_MAX_SECRET_BYTES = 64 * 1024


class ControlPlaneSecretStore:
    """Service-owned write-only secret slots.

    The public boundary exposes metadata and mutations. ``resolve`` is reserved
    for trusted execution services and deliberately returns no metadata object
    that could be serialized accidentally.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.absolute()

    def metadata(self, scope: str, secret_id: str) -> SecretMetadata:
        path = self._path(scope, secret_id)
        try:
            metadata = path.lstat()
            self._validate_file(metadata)
            return SecretMetadata(
                scope=scope,
                secret_id=secret_id,
                state="configured" if metadata.st_size else "missing",
                updated_at=datetime.fromtimestamp(metadata.st_mtime, tz=UTC),
            )
        except FileNotFoundError:
            return SecretMetadata(scope=scope, secret_id=secret_id, state="missing")
        except (OSError, SecretStoreError):
            return SecretMetadata(scope=scope, secret_id=secret_id, state="inaccessible")

    def write(self, scope: str, secret_id: str, value: str) -> SecretMetadata:
        payload = value.encode("utf-8")
        if not payload or len(payload) > _MAX_SECRET_BYTES or b"\x00" in payload:
            raise SecretStoreError("secret-invalid", "Secret value is invalid")
        path = self._path(scope, secret_id)
        if path.exists() or path.is_symlink():
            existing = self.metadata(scope, secret_id)
            if existing.state == "inaccessible":
                raise SecretStoreError("secret-inaccessible", "Secret slot is inaccessible")
        directory = path.parent
        self._ensure_private_directory(directory)
        temporary = directory / f".{path.name}.{secrets.token_hex(12)}.tmp"
        descriptor: int | None = None
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("secret write made no progress")
                view = view[written:]
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.replace(temporary, path)
            directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except SecretStoreError:
            raise
        except (OSError, UnicodeError) as error:
            raise SecretStoreError("secret-write-failed", "Secret could not be stored") from error
        finally:
            if descriptor is not None:
                os.close(descriptor)
            with suppress(OSError):
                temporary.unlink(missing_ok=True)
        result = self.metadata(scope, secret_id)
        if result.state != "configured":
            raise SecretStoreError("secret-write-uncertain", "Secret storage could not be verified")
        return result

    def delete(self, scope: str, secret_id: str) -> SecretMetadata:
        path = self._path(scope, secret_id)
        current = self.metadata(scope, secret_id)
        if current.state == "inaccessible":
            raise SecretStoreError("secret-inaccessible", "Secret slot is inaccessible")
        if current.state == "missing":
            return current
        try:
            path.unlink()
            directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as error:
            raise SecretStoreError("secret-delete-failed", "Secret could not be deleted") from error
        return SecretMetadata(scope=scope, secret_id=secret_id, state="missing")

    def resolve(self, scope: str, secret_id: str) -> str | None:
        path = self._path(scope, secret_id)
        descriptor: int | None = None
        try:
            descriptor = os.open(
                path,
                os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
            )
            metadata = os.fstat(descriptor)
            self._validate_file(metadata)
            if metadata.st_size > _MAX_SECRET_BYTES:
                raise SecretStoreError("secret-inaccessible", "Secret slot is inaccessible")
            payload = os.read(descriptor, _MAX_SECRET_BYTES + 1)
            if len(payload) > _MAX_SECRET_BYTES:
                raise SecretStoreError("secret-inaccessible", "Secret slot is inaccessible")
            return payload.decode("utf-8") or None
        except FileNotFoundError:
            return None
        except SecretStoreError:
            raise
        except (OSError, UnicodeError) as error:
            raise SecretStoreError("secret-inaccessible", "Secret slot is inaccessible") from error
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def _path(self, scope: str, secret_id: str) -> Path:
        self._validate_identifier(scope)
        self._validate_identifier(secret_id)
        return self.root / "scopes" / scope / f"{secret_id}.secret"

    @staticmethod
    def _validate_identifier(value: str) -> None:
        if _IDENTIFIER.fullmatch(value) is None:
            raise SecretStoreError("secret-identity-invalid", "Secret identity is invalid")

    @staticmethod
    def _validate_file(metadata: os.stat_result) -> None:
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise SecretStoreError("secret-inaccessible", "Secret slot is inaccessible")

    def _ensure_private_directory(self, directory: Path) -> None:
        try:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(self.root, 0o700)
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(self.root / "scopes", 0o700)
            os.chmod(directory, 0o700)
            for candidate in (self.root, self.root / "scopes", directory):
                metadata = candidate.lstat()
                if (
                    not stat.S_ISDIR(metadata.st_mode)
                    or stat.S_ISLNK(metadata.st_mode)
                    or metadata.st_uid != os.geteuid()
                    or stat.S_IMODE(metadata.st_mode) & 0o077
                ):
                    raise SecretStoreError(
                        "secret-workspace-unsupported", "Secret workspace is inaccessible"
                    )
        except SecretStoreError:
            raise
        except OSError as error:
            raise SecretStoreError(
                "secret-workspace-unsupported", "Secret workspace is inaccessible"
            ) from error
