from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

_ANSI = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_REDACTED = "[REDACTED]"


def safe_log_lines(lines: Sequence[str], secret_values: Iterable[str] = ()) -> tuple[str, ...]:
    """Remove terminal control sequences and exact configured secret values.

    Redaction happens before the lines cross the API boundary. Joining first also
    protects a configured value that contains a newline and was split by the
    journal output format.
    """

    payload = "\n".join(lines)
    values = sorted({value for value in secret_values if value}, key=len, reverse=True)
    for value in values:
        payload = payload.replace(value, _REDACTED)
    if not payload:
        return ()
    return tuple(_ANSI.sub("", line) for line in payload.splitlines())
