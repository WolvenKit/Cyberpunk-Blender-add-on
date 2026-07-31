import re
from enum import Enum

from .catalog import ResourceKind
from .diagnostics import IssueSeverity, ResourceIssue, ValidationResult
from .rig_validation import rig_array_errors


MIN_WOLVENKIT_VERSION = (8, 17)
MIN_MATERIAL_JSON_VERSION = (1, 0)


class ValidationProfile(str, Enum):
    NONE = "none"
    CR2W = "cr2w"
    MATERIAL_BUNDLE = "material_bundle"


def version_components(value):
    match = re.search(r"\d+(?:\.\d+)*", str(value or ""))
    if match is None:
        return None
    return tuple(int(part) for part in match.group().split("."))


def version_at_least(value, minimum):
    components = version_components(value)
    if components is None:
        return False
    width = max(len(components), len(minimum))
    return components + (0,) * (width - len(components)) >= minimum + (0,) * (width - len(minimum))


def validate_payload(payload, *, path="", kind=None, profile=ValidationProfile.NONE, expected_root_types=()):
    kind = ResourceKind(kind) if kind is not None else None
    profile = ValidationProfile(profile)
    issues = []

    def add(code, message, severity=IssueSeverity.ERROR):
        issues.append(ResourceIssue(
            IssueSeverity(severity),
            code,
            path,
            message,
            kind.value if kind is not None else "",
        ))

    if not isinstance(payload, dict):
        add("json.top_level", f"{path}: expected a JSON object")
        return ValidationResult(tuple(issues))

    if profile is ValidationProfile.NONE:
        return ValidationResult()


    header = payload.get("Header")
    if not isinstance(header, dict):
        add("document.header", f"{path}: missing Header object")
        return ValidationResult(tuple(issues))

    if profile is ValidationProfile.MATERIAL_BUNDLE:
        version = header.get("MaterialJsonVersion")
        if not version_at_least(version, MIN_MATERIAL_JSON_VERSION):
            add(
                "version.material_json",
                f"{path}: MaterialJsonVersion {version!r} is older than 1.0",
            )
        if not isinstance(payload.get("MaterialRepo"), str):
            add("material.repo", f"{path}: MaterialRepo must be a string")
        if not isinstance(payload.get("Appearances"), (dict, list)):
            add("material.appearances", f"{path}: Appearances must be an object or list")
        if not isinstance(payload.get("Materials"), list):
            add("material.materials", f"{path}: Materials must be a list")
        return ValidationResult(tuple(issues))

    version = header.get("WolvenKitVersion")
    if not version_at_least(version, MIN_WOLVENKIT_VERSION):
        add(
            "version.wolvenkit",
            f"{path}: WolvenKitVersion {version!r} is older than 8.17",
        )
    data = payload.get("Data")
    if not isinstance(data, dict):
        add("document.data", f"{path}: missing Data object")
        return ValidationResult(tuple(issues))
    root = data.get("RootChunk")
    if not isinstance(root, dict):
        add("document.root_chunk", f"{path}: missing Data.RootChunk object")
        return ValidationResult(tuple(issues))

    data_type = header.get("DataType")
    if data_type not in (None, "CR2W"):
        add(
            "document.data_type",
            f"{path}: Header.DataType is {data_type!r}, expected 'CR2W'",
            IssueSeverity.WARNING,
        )
    root_type = root.get("$type")
    if expected_root_types and root_type not in tuple(expected_root_types):
        add(
            "document.root_type",
            f"{path}: Data.RootChunk.$type is {root_type!r}, expected one of {tuple(expected_root_types)!r}",
        )

    if kind is ResourceKind.RIG:
        for field in ("boneNames", "boneParentIndexes", "boneTransforms"):
            if not isinstance(root.get(field), list):
                add("rig.field", f"{path}: Data.RootChunk.{field} must be a list")
        for message in rig_array_errors(root):
            add("rig.integrity", f"{path}: {message}")
    elif kind is ResourceKind.ENTITY:
        if "components" in root and not isinstance(root.get("components"), list):
            add("entity.components", f"{path}: components must be a list")
        if "appearances" in root and not isinstance(root.get("appearances"), list):
            add("entity.appearances", f"{path}: appearances must be a list")
    elif kind is ResourceKind.APPEARANCE:
        if not isinstance(root.get("appearances"), list):
            add("appearance.appearances", f"{path}: appearances must be a list")
    elif kind is ResourceKind.PHYSICS:
        if not isinstance(root.get("bodies"), list):
            add("physics.bodies", f"{path}: bodies must be a list")
    elif kind in (ResourceKind.STREAMING_SECTOR, ResourceKind.STREAMING_SECTOR_INPLACE):
        nodes = root.get("nodes")
        node_data = root.get("nodeData", {}).get("Data") if isinstance(root.get("nodeData"), dict) else None
        if not isinstance(nodes, list):
            add("sector.nodes", f"{path}: nodes must be a list")
        if not isinstance(node_data, list):
            add("sector.node_data", f"{path}: nodeData.Data must be a list")

    return ValidationResult(tuple(issues))
