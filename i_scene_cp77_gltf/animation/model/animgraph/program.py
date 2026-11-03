from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PoseProgramNode:
    """One evaluation step"""

    kind: str
    handle: str
    node_type: str
    path: str
    data: Mapping[str, Any]
    children: tuple[PoseProgramNode, ...] = ()


@dataclass(frozen=True)
class PoseProgramPlan:
    """The compiled root, the dangle and drag operations in order, the blend handles and any preview boundaries"""

    root: PoseProgramNode | None
    operations: tuple[tuple[str, str, str], ...]
    blend_handles: tuple[str, ...]
    boundaries: tuple[str, ...]
