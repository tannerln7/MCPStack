from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


class SecretStoreError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class SecretMetadata:
    scope: str
    secret_id: str
    state: Literal["configured", "missing", "inaccessible"]
    updated_at: datetime | None = None
