from __future__ import annotations

from dataclasses import dataclass

from ...assetio.catalog import (
    RESOURCE_SPECS,
    ResourceFormat,
    ResourceKind,
    normalize_extensions,
)
from ...assetio.index import IndexPolicy
from ...assetio.paths import LocalPath
from ...materials.repository import (
    MATERIAL_IMAGE_EXTENSIONS,
    MATERIAL_RESOURCE_KINDS,
)


def _primary_resource_spec(kind: ResourceKind):
    kind = ResourceKind(kind)
    matches = tuple(spec for spec in RESOURCE_SPECS if spec.kind is kind)
    if not matches:
        raise ValueError(f"AssetIO has no resource specification for {kind.value}")
    if len(matches) == 1:
        return matches[0]
    canonical_cooked_suffix = f".{kind.value}"
    for spec in matches:
        if canonical_cooked_suffix in spec.cooked_suffixes:
            return spec
    raise ValueError(
        f"AssetIO has no canonical resource specification for {kind.value}"
    )


def _json_export_extensions(kind: ResourceKind) -> tuple[str, ...]:
    return tuple(
        export.suffix
        for export in _primary_resource_spec(kind).exports
        if export.format is ResourceFormat.JSON
    )


def _canonical_cooked_extension(kind: ResourceKind) -> str:
    spec = _primary_resource_spec(kind)
    canonical = f".{ResourceKind(kind).value}"
    if canonical in spec.cooked_suffixes:
        return canonical
    if len(spec.cooked_suffixes) == 1:
        return spec.cooked_suffixes[0]
    raise ValueError(
        f"AssetIO has no canonical cooked suffix for {ResourceKind(kind).value}"
    )


MATERIAL_TEMPLATE_COOKED_EXTENSION = _canonical_cooked_extension(
    ResourceKind.MATERIAL_TEMPLATE
)
MULTILAYER_TEMPLATE_COOKED_EXTENSION = _canonical_cooked_extension(
    ResourceKind.MLTEMPLATE
)
MATERIAL_TEMPLATE_EXTENSION = _json_export_extensions(ResourceKind.MATERIAL_TEMPLATE)[0]
MULTILAYER_TEMPLATE_EXTENSION = _json_export_extensions(ResourceKind.MLTEMPLATE)[0]
MATERIAL_TOOL_RESOURCE_EXTENSIONS = tuple(
    dict.fromkeys(
        (
            *(
                extension
                for kind in MATERIAL_RESOURCE_KINDS
                for extension in _json_export_extensions(kind)
            ),
            *MATERIAL_IMAGE_EXTENSIONS,
        )
    )
)


@dataclass(frozen=True, slots=True)
class MaterialToolsRequest:
    """Canonical resource-session request for one Material Tools operation"""

    root: str
    extensions: tuple[str, ...] = MATERIAL_TOOL_RESOURCE_EXTENSIONS
    index_policy: IndexPolicy = IndexPolicy.REUSE
    path_contains: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        root = LocalPath.from_value(self.root).value if self.root else ""
        extensions = normalize_extensions(self.extensions)
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "extensions", extensions)
        object.__setattr__(self, "index_policy", IndexPolicy(self.index_policy))
