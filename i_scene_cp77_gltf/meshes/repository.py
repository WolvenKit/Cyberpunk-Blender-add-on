import os

from ..assetio.paths import DepotPath
from ..assetio.repository import ResourceLoadError
from ..assetio.diagnostics import IssueSeverity, ResourceIssue
from .model import MeshRepresentation, ResolvedMeshAsset


MESH_GLB_EXTENSIONS = (".glb", ".physicalscene.glb", ".w2mesh.glb")
MESH_JSON_EXTENSIONS = (".mesh.json", ".physicalscene.json", ".w2mesh.json")
MESH_INDEX_EXTENSIONS = (*MESH_GLB_EXTENSIONS, *MESH_JSON_EXTENSIONS)
MESH_COOKED_EXTENSIONS = (".mesh", ".physicalscene", ".w2mesh")
MESH_COOKED_NAME_SUFFIXES = tuple(value.lstrip(".") for value in MESH_COOKED_EXTENSIONS)


def _representation(reference, resolved):
    value = f"{reference} {resolved}".replace("\\", "/").casefold()
    if ".physicalscene" in value:
        return MeshRepresentation.PHYSICAL_SCENE
    if ".w2mesh" in value:
        return MeshRepresentation.W2MESH
    return MeshRepresentation.MESH


class MeshRepository:
    def __init__(self, asset_index):
        self.asset_index = asset_index
        self._cache = {}
        self._sidecar_cache = {}
        self._issues = []
        self._hits = 0
        self._misses = 0

    @property
    def issues(self):
        return tuple(self._issues)

    @property
    def stats(self):
        return {"hits": self._hits, "misses": self._misses, "entries": len(self._cache)}

    def clear(self):
        self._cache.clear()
        self._sidecar_cache.clear()
        self._issues.clear()
        self._hits = 0
        self._misses = 0

    def resolve_sidecar(self, reference, *, required=False):
        value = os.fspath(reference) if reference else ""
        if not value:
            return ""
        local_file = os.path.isfile(value)
        key = os.path.normcase(os.path.abspath(value)) if local_file else DepotPath.from_value(value).key
        cached = self._sidecar_cache.get(key)
        if cached is not None:
            self._hits += 1
            return cached
        self._misses += 1
        sidecar = self.asset_index.resolve_export(value, MESH_JSON_EXTENSIONS) or ""
        if not sidecar and required:
            issue = ResourceIssue(
                IssueSeverity.ERROR,
                "mesh.sidecar.resolve",
                value,
                f"{value}: mesh JSON sidecar could not be resolved",
                "mesh",
            )
            self._issues.append(issue)
            raise ResourceLoadError(value, "mesh", (issue,))
        resolved = os.path.abspath(sidecar) if sidecar else ""
        self._sidecar_cache[key] = resolved
        return resolved

    def resolve(self, reference, *, required=False, include_sidecar=True):
        value = os.fspath(reference) if reference else ""
        if not value:
            return None
        local_file = os.path.isfile(value)
        key = os.path.normcase(os.path.abspath(value)) if local_file else DepotPath.from_value(value).key
        cached = self._cache.get(key)
        if cached is not None:
            self._hits += 1
            if include_sidecar and not cached.material_sidecar:
                sidecar = self.resolve_sidecar(value)
                if sidecar:
                    cached = ResolvedMeshAsset(
                        cached.depot_path,
                        cached.local_path,
                        cached.representation,
                        sidecar,
                    )
                    self._cache[key] = cached
            return cached
        self._misses += 1
        resolved = value if local_file else self.asset_index.resolve_export(value, MESH_GLB_EXTENSIONS)
        if not resolved:
            issue = ResourceIssue(
                IssueSeverity.ERROR,
                "mesh.resolve",
                value,
                f"{value}: mesh export could not be resolved",
                "mesh",
            )
            self._issues.append(issue)
            if required:
                raise ResourceLoadError(value, "mesh", (issue,))
            return None
        representation = _representation(value, resolved)
        sidecar = self.resolve_sidecar(value) if include_sidecar else ""
        asset = ResolvedMeshAsset(
            depot_path=value,
            local_path=os.path.abspath(resolved),
            representation=representation,
            material_sidecar=sidecar,
        )
        self._cache[key] = asset
        return asset
