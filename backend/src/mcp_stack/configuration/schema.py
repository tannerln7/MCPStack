from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

_RESOURCE_PACKAGE = "mcp_stack.resources"
_STACK_SCHEMA_NAME = "stack-config.schema.json"


def packaged_stack_schema_text() -> str:
    return files(_RESOURCE_PACKAGE).joinpath(_STACK_SCHEMA_NAME).read_text(encoding="utf-8")


def load_stack_schema(schema_path: Path | None = None) -> dict[str, Any]:
    text = (
        schema_path.resolve().read_text(encoding="utf-8")
        if schema_path is not None
        else packaged_stack_schema_text()
    )
    return json.loads(text)
