from __future__ import annotations

import hashlib
import os
import secrets
import stat
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from .models import CandidateValidation, ConfigurationIssue, ConfigurationSource, StackRecord

_MAX_SOURCE_BYTES = 1_048_576


def revision_for(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class WriteOutcome:
    previous_revision: str
    source: ConfigurationSource
    bytes_written: int
    replaced: bool


@dataclass(frozen=True)
class DeleteOutcome:
    source_path: str
    previous_revision: str


class ConfigurationWriteError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class ConfigurationValidationRejected(ConfigurationWriteError):
    def __init__(self, validation: CandidateValidation) -> None:
        self.validation = validation
        super().__init__("candidate-validation-failed", "Candidate configuration is invalid")


class ConfigurationRevisionConflict(ConfigurationWriteError):
    def __init__(self, current_revision: str) -> None:
        self.current_revision = current_revision
        super().__init__("source-revision-conflict", "Configuration changed on disk")


class RepositoryConflict(ConfigurationWriteError):
    def __init__(self) -> None:
        super().__init__(
            "repository-conflict", "Configuration repository changed during validation"
        )


class UncertainWriteOutcome(ConfigurationWriteError):
    def __init__(self) -> None:
        super().__init__(
            "write-outcome-uncertain",
            "Configuration was replaced but durability could not be confirmed",
        )


class TrustedWorkspaceWriter:
    """Exact-byte, optimistic replacement inside one pinned direct-child workspace."""

    def __init__(self, repository: FilesystemStackRepository, root: Path) -> None:
        self._repository = repository
        self._root = root.expanduser().absolute()

    def write(self, record: StackRecord, original_revision: str, document: str) -> WriteOutcome:
        candidate = document.encode("utf-8")
        if len(candidate) > _MAX_SOURCE_BYTES:
            raise ConfigurationWriteError("source-too-large", "Candidate source exceeds one MiB")
        root_fd = self._open_root()
        temporary_name: str | None = None
        try:
            source_name = record.source.path
            if Path(source_name).name != source_name or Path(source_name).suffix.lower() not in {
                ".yaml",
                ".yml",
            }:
                raise ConfigurationWriteError(
                    "unsupported-source", "Source is not a writable direct-child YAML file"
                )
            original_bytes, source_stat = self._read_eligible_source(root_fd, source_name)
            current_revision = revision_for(original_bytes)
            if current_revision != original_revision:
                raise ConfigurationRevisionConflict(current_revision)
            manifest = self._manifest(root_fd)
            validation = self._repository.validate_candidate(record.configuration.id, document)
            if validation is None:
                raise ConfigurationWriteError(
                    "source-not-found", "Stack source is no longer available"
                )
            if not validation.valid:
                raise ConfigurationValidationRejected(validation)
            self._validate_repository_identity(record, validation)
            candidate_revision = revision_for(candidate)
            if candidate == original_bytes:
                return WriteOutcome(
                    previous_revision=current_revision,
                    source=record.source,
                    bytes_written=0,
                    replaced=False,
                )
            temporary_name = f".{source_name}.{secrets.token_hex(12)}.tmp"
            descriptor = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
                stat.S_IMODE(source_stat.st_mode),
                dir_fd=root_fd,
            )
            try:
                os.fchmod(descriptor, stat.S_IMODE(source_stat.st_mode))
                view = memoryview(candidate)
                while view:
                    written = os.write(descriptor, view)
                    if written <= 0:
                        raise OSError("candidate write made no progress")
                    view = view[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            if self._manifest(root_fd, exclude_temporary=temporary_name) != manifest:
                raise RepositoryConflict()
            final_bytes, final_stat = self._read_eligible_source(root_fd, source_name)
            if (final_stat.st_dev, final_stat.st_ino) != (source_stat.st_dev, source_stat.st_ino):
                raise RepositoryConflict()
            final_revision = revision_for(final_bytes)
            if final_revision != original_revision:
                raise ConfigurationRevisionConflict(final_revision)
            os.replace(temporary_name, source_name, src_dir_fd=root_fd, dst_dir_fd=root_fd)
            temporary_name = None
            try:
                os.fsync(root_fd)
            except OSError as error:
                raise UncertainWriteOutcome() from error
            refreshed = self._repository.get(record.configuration.id)
            if refreshed is None or refreshed.revision != candidate_revision:
                raise UncertainWriteOutcome()
            return WriteOutcome(
                previous_revision=current_revision,
                source=refreshed.source,
                bytes_written=len(candidate),
                replaced=True,
            )
        except OSError as error:
            raise ConfigurationWriteError(
                "filesystem-error", "Configuration source could not be safely replaced"
            ) from error
        finally:
            if temporary_name is not None:
                with suppress(OSError):
                    os.unlink(temporary_name, dir_fd=root_fd)
            os.close(root_fd)

    def create(self, stack_id: str, document: str) -> WriteOutcome:
        candidate = document.encode("utf-8")
        if len(candidate) > _MAX_SOURCE_BYTES:
            raise ConfigurationWriteError("source-too-large", "Candidate source exceeds one MiB")
        validation = self._repository.validate_new_candidate(stack_id, document)
        if not validation.valid:
            raise ConfigurationValidationRejected(validation)
        source_name = f"{stack_id}.yaml"
        root_fd = self._open_root()
        temporary_name = f".{source_name}.{secrets.token_hex(12)}.tmp"
        try:
            manifest = self._manifest(root_fd)
            descriptor = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=root_fd,
            )
            try:
                view = memoryview(candidate)
                while view:
                    written = os.write(descriptor, view)
                    if written <= 0:
                        raise OSError("candidate write made no progress")
                    view = view[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            if self._manifest(root_fd, exclude_temporary=temporary_name) != manifest:
                raise RepositoryConflict()
            try:
                os.link(
                    temporary_name,
                    source_name,
                    src_dir_fd=root_fd,
                    dst_dir_fd=root_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as error:
                raise ConfigurationWriteError(
                    "source-exists", "Stack source already exists"
                ) from error
            os.unlink(temporary_name, dir_fd=root_fd)
            temporary_name = ""
            try:
                os.fsync(root_fd)
            except OSError as error:
                raise UncertainWriteOutcome() from error
            refreshed = self._repository.get(stack_id)
            if refreshed is None or refreshed.revision != validation.revision:
                raise UncertainWriteOutcome()
            return WriteOutcome(
                previous_revision="",
                source=refreshed.source,
                bytes_written=len(candidate),
                replaced=False,
            )
        except ConfigurationWriteError:
            raise
        except OSError as error:
            raise ConfigurationWriteError(
                "filesystem-error", "Configuration source could not be safely created"
            ) from error
        finally:
            if temporary_name:
                with suppress(OSError):
                    os.unlink(temporary_name, dir_fd=root_fd)
            os.close(root_fd)

    def verify_deletion(self, record: StackRecord, original_revision: str) -> None:
        root_fd = self._open_root()
        try:
            source_name = self._source_name(record)
            original_bytes, _ = self._read_eligible_source(root_fd, source_name)
            current_revision = revision_for(original_bytes)
            if current_revision != original_revision:
                raise ConfigurationRevisionConflict(current_revision)
        finally:
            os.close(root_fd)

    def delete(self, record: StackRecord, original_revision: str) -> DeleteOutcome:
        root_fd = self._open_root()
        try:
            source_name = self._source_name(record)
            original_bytes, source_stat = self._read_eligible_source(root_fd, source_name)
            current_revision = revision_for(original_bytes)
            if current_revision != original_revision:
                raise ConfigurationRevisionConflict(current_revision)
            manifest = self._manifest(root_fd)
            final_bytes, final_stat = self._read_eligible_source(root_fd, source_name)
            if (final_stat.st_dev, final_stat.st_ino) != (
                source_stat.st_dev,
                source_stat.st_ino,
            ) or revision_for(final_bytes) != original_revision:
                raise RepositoryConflict()
            if self._manifest(root_fd) != manifest:
                raise RepositoryConflict()
            os.unlink(source_name, dir_fd=root_fd)
            try:
                os.fsync(root_fd)
            except OSError as error:
                raise UncertainWriteOutcome() from error
        except ConfigurationWriteError:
            raise
        except OSError as error:
            raise ConfigurationWriteError(
                "filesystem-error", "Configuration source could not be safely deleted"
            ) from error
        finally:
            os.close(root_fd)
        if self._repository.get(record.configuration.id) is not None:
            raise UncertainWriteOutcome()
        return DeleteOutcome(
            source_path=record.source.path,
            previous_revision=original_revision,
        )

    @staticmethod
    def _source_name(record: StackRecord) -> str:
        source_name = record.source.path
        if Path(source_name).name != source_name or Path(source_name).suffix.lower() not in {
            ".yaml",
            ".yml",
        }:
            raise ConfigurationWriteError(
                "unsupported-source", "Source is not a writable direct-child YAML file"
            )
        return source_name

    def _open_root(self) -> int:
        try:
            root_metadata = self._root.lstat()
            if stat.S_ISLNK(root_metadata.st_mode):
                raise ConfigurationWriteError(
                    "unsupported-workspace", "Configuration workspace cannot be a symbolic link"
                )
            flags = (
                os.O_RDONLY
                | os.O_CLOEXEC
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            descriptor = os.open(self._root, flags)
            metadata = os.fstat(descriptor)
            if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o022:
                os.close(descriptor)
                raise ConfigurationWriteError(
                    "unsupported-workspace",
                    "Configuration workspace ownership or permissions are unsupported",
                )
            return descriptor
        except ConfigurationWriteError:
            raise
        except OSError as error:
            raise ConfigurationWriteError(
                "unsupported-workspace", "Configuration workspace is unavailable"
            ) from error

    def _read_eligible_source(self, root_fd: int, name: str) -> tuple[bytes, os.stat_result]:
        descriptor = os.open(
            name, os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0), dir_fd=root_fd
        )
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.geteuid()
                or metadata.st_nlink != 1
                or stat.S_IMODE(metadata.st_mode) & 0o022
                or not stat.S_IMODE(metadata.st_mode) & 0o600 == 0o600
            ):
                raise ConfigurationWriteError(
                    "unsupported-source", "Source ownership, links, or permissions are unsupported"
                )
            if os.listxattr(descriptor):
                raise ConfigurationWriteError(
                    "unsupported-source", "Source has metadata that cannot be safely preserved"
                )
            if metadata.st_size > _MAX_SOURCE_BYTES:
                raise ConfigurationWriteError(
                    "unsupported-source", "Source exceeds the supported size"
                )
            chunks: list[bytes] = []
            while True:
                chunk = os.read(
                    descriptor, min(65536, _MAX_SOURCE_BYTES + 1 - sum(map(len, chunks)))
                )
                if not chunk:
                    break
                chunks.append(chunk)
            content = b"".join(chunks)
            if len(content) > _MAX_SOURCE_BYTES:
                raise ConfigurationWriteError(
                    "unsupported-source", "Source exceeds the supported size"
                )
            return content, metadata
        finally:
            os.close(descriptor)

    def _manifest(
        self, root_fd: int, exclude_temporary: str | None = None
    ) -> tuple[tuple[str, str], ...]:
        values: list[tuple[str, str]] = []
        for name in sorted(os.listdir(root_fd)):
            if name == exclude_temporary or Path(name).suffix.lower() not in {".yaml", ".yml"}:
                continue
            content, _ = self._read_eligible_source(root_fd, name)
            values.append((name, revision_for(content)))
        return tuple(values)

    def _validate_repository_identity(
        self, record: StackRecord, candidate: CandidateValidation
    ) -> None:
        assert candidate.configuration is not None
        for other in self._repository.discover().records:
            if (
                other.source.path != record.source.path
                and other.configuration.id == candidate.configuration.id
            ):
                rejected = CandidateValidation(
                    revision=candidate.revision,
                    configuration=None,
                    issues=(
                        ConfigurationIssue(
                            stage="domain",
                            code="duplicate-stack-id",
                            path="/id",
                            message="Candidate Stack id conflicts with another configured Stack",
                        ),
                    ),
                )
                raise ConfigurationValidationRejected(rejected)


from .filesystem import FilesystemStackRepository  # noqa: E402
