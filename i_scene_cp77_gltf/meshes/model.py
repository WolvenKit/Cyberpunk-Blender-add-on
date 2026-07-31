from dataclasses import dataclass
from enum import Enum


class MeshRepresentation(str, Enum):
    MESH = "mesh"
    PHYSICAL_SCENE = "physicalscene"
    W2MESH = "w2mesh"


@dataclass(frozen=True, slots=True)
class ResolvedMeshAsset:
    depot_path: str
    local_path: str
    representation: MeshRepresentation
    material_sidecar: str = ""
