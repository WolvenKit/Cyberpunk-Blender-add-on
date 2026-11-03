from dataclasses import dataclass
from typing import Any

from ..blender.mesh_validation import MeshValidationOptions


@dataclass(frozen=True, slots=True)
class MeshToolResult:
    ok: bool
    message: str = ""
    severity: str = "INFO"
    payload: Any = None
    warnings: tuple[str, ...] = ()

    @property
    def blender_status(self):
        return {"FINISHED"} if self.ok else {"CANCELLED"}

    @classmethod
    def success(cls, message="", payload=None):
        return cls(True, message, "INFO", payload, ())

    @classmethod
    def warning(cls, message, payload=None):
        return cls(True, message, "WARNING", payload, ())

    @classmethod
    def failure(cls, message="", payload=None):
        return cls(False, message, "ERROR", payload, ())


@dataclass(frozen=True, slots=True)
class ShrinkwrapRequest:
    target_collection_name: str
    offset: float
    wrap_method: str
    as_garment_support: bool = True
    apply_immediately: bool = True
    vertex_group: str | None = None


@dataclass(frozen=True, slots=True)
class AutofitRequest:
    base_choice: str
    addon_choice: str | None
    use_addon: bool
    fbx_rotation: bool
    try_auto_apply: bool


@dataclass(frozen=True, slots=True)
class MeshValidationRequest:
    is_skinned: bool
    options: MeshValidationOptions


@dataclass(frozen=True, slots=True)
class MeshValidationSummary:
    mesh_names: tuple[str, ...]
    issues: tuple
    remaining_issues: tuple = ()
    fixes_applied: tuple = ()
    report: str = ""

    @property
    def issue_count(self):
        return len(self.issues)

    @property
    def remaining_count(self):
        return len(self.remaining_issues)

    @property
    def fix_count(self):
        return sum(len(fixes) for _name, fixes in self.fixes_applied)
