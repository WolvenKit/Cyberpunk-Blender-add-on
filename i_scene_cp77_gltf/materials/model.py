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
    resource_kind: ResourceKind
    payload: dict
    root: dict


@dataclass(frozen=True, slots=True)
class ResolvedMaterialChain:
    documents: tuple[MaterialDocument, ...]

    @property
    def leaf(self):
        return self.documents[0] if self.documents else None
