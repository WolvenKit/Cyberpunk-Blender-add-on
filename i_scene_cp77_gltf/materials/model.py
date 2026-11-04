from dataclasses import dataclass

from ..assetio.catalog import ResourceKind


@dataclass(frozen=True, slots=True)
class MaterialBundle:
    depot_path: str
    appearances: object
    materials: tuple


@dataclass(frozen=True, slots=True)
class MaterialDocument:
    source_path: str
    source_identity: tuple
    resource_kind: ResourceKind
    payload: dict
    root: dict
