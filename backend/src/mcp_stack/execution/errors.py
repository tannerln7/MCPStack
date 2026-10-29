from __future__ import annotations


class StdioExecutionError(Exception):
    def __init__(self, code: str, message: str, *, exit_status: int = 2) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_status = exit_status
