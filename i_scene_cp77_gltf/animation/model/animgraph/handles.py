from __future__ import annotations

from typing import Any


def normalized_source_handle(value: Any) -> str:
    text = str(value or "")
    return text.split(":", 1)[1] if text.startswith("handle:") else text
