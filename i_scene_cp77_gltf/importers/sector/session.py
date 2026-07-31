from __future__ import annotations

from dataclasses import dataclass, field
import json
import os

from ...animation.rig import RigRepository
from ...assetio.documents import DocumentSession
from ...assetio.index import IndexPolicy, build_asset_index, indexed_files
from ...materials import MaterialResourceRepository
from ...materials.resources import material_resource_scope
from ...meshes import MESH_GLB_EXTENSIONS, MeshRepository
from ..common.cache import acquire_material_cache, release_material_cache
from ..common.paths import absolute_path_key
from ..entity.repository import EntityRepository
from .planner import compile_sector_plan
from .repository import SectorRepository
from .services.acoustics import AcousticSectorService
from .services.buffers import TransformBufferService
from .services.collision_metadata import CollisionMetadataService
from .services.decal import DecalService
from .services.deformation import DeformationService
from .services.effects import EffectResourceService
from .services.foliage import FoliageResourceService
from .services.gi import GIResourceService
from .services.lighting import StaticLightingService
from .services.masters import MasterAssetServices
from .services.minimap import MinimapResourceService
from .services.primitives import PrimitiveMeshService
from .services.probes import ReflectionProbeService
from .services.resources import IndexedResourceResolver
from .services.semantic import SemanticMarkerService
from .services.splines import SplineService
from .services.world_metadata import WorldMetadataService


class SectorFileSet:
    __slots__ = ("asset_index", "_cache")

    def __init__(self, asset_index):
        self.asset_index = asset_index
        self._cache = {}

    def _files(self, key, *extensions):
        cached = self._cache.get(key)
        if cached is None:
            cached = indexed_files(self.asset_index, *extensions)
            self._cache[key] = cached
        return cached

    @property
    def sectors(self):
        return self._files("sectors", ".streamingsector.json")

    @property
    def mesh_jsons(self):
        return self._files("mesh_jsons", ".mesh.json")

    @property
    def animation_glbs(self):
        return self._files("animation_glbs", ".anims.glb")

    @property
    def appearance_jsons(self):
        return self._files("appearance_jsons", ".app.json")

    @property
    def rig_jsons(self):
        return self._files("rig_jsons", ".rig.json")

    @property
    def mesh_glbs(self):
        return self._files("mesh_glbs", *MESH_GLB_EXTENSIONS)


@dataclass(slots=True)
class SectorImportCaches:
    planned_sectors: dict[str, object] = field(default_factory=dict)
    entity_masters: dict[tuple, object] = field(default_factory=dict)
    entity_resolutions: dict[tuple, str] = field(default_factory=dict)
    mesh_masters: dict[tuple, object] = field(default_factory=dict)
    proxy_masters: dict[tuple, object] = field(default_factory=dict)
    foliage_resources: dict[str, object] = field(default_factory=dict)
    materials: dict[tuple, object] = field(default_factory=dict)
    resource_resolutions: dict[tuple, object] = field(default_factory=dict)
    primitive_meshes: dict[tuple, object] = field(default_factory=dict)
    decal_meshes: dict[tuple, object] = field(default_factory=dict)
    serialized_json: dict[int, tuple[object, str]] = field(default_factory=dict)


_path_key = absolute_path_key


_SERVICE_FACTORIES = (
    ("resource_resolver", lambda session: IndexedResourceResolver(session), None),
    ("primitive_meshes", lambda session: PrimitiveMeshService(session), None),
    ("master_assets", lambda session: MasterAssetServices(session), None),
    ("transform_buffers", lambda _session: TransformBufferService(), None),
    (
        "foliage_assets",
        lambda session: FoliageResourceService(session),
        "import_foliage",
    ),
    ("deformation_assets", lambda _session: DeformationService(), None),
    (
        "world_metadata_assets",
        lambda _session: WorldMetadataService(),
        None,
    ),
    ("decal_assets", lambda session: DecalService(session), None),
    (
        "lighting_assets",
        lambda session: StaticLightingService(session),
        "with_lights",
    ),
    (
        "probe_assets",
        lambda session: ReflectionProbeService(session),
        "import_environment_probes",
    ),
    (
        "effect_assets",
        lambda session: EffectResourceService(session),
        "import_effects",
    ),
    (
        "acoustic_assets",
        lambda session: AcousticSectorService(session),
        "import_acoustics",
    ),
    (
        "minimap_assets",
        lambda session: MinimapResourceService(session),
        "import_minimap",
    ),
    ("semantic_assets", lambda session: SemanticMarkerService(session), None),
    ("spline_assets", lambda _session: SplineService(), None),
    ("gi_assets", lambda session: GIResourceService(session), "import_gi"),
    (
        "collision_metadata_assets",
        lambda session: CollisionMetadataService(session),
        "import_collisions",
    ),
)
_SERVICE_ATTRIBUTES = tuple(name for name, _factory, _option in _SERVICE_FACTORIES)


class SectorImportSession:
    def __init__(self, project_filepath, options, *, force_refresh=False):
        self.project_filepath = os.path.abspath(project_filepath)
        self.project_path = os.path.dirname(self.project_filepath)
        self.project_name = os.path.basename(self.project_path)
        self.raw_root = os.path.join(self.project_path, "source", "raw")
        self.base_path = os.path.join(self.raw_root, "base")
        self.options = options
        self.force_refresh = bool(force_refresh)

        self.asset_index = None
        self.files = None
        self.caches = SectorImportCaches()
        self.documents = DocumentSession()
        self.sectors = None
        self.entities = None
        self.rigs = None
        self.meshes = None
        self.material_resources = None
        self._material_scope = None
        self.masters = None
        self._material_cache_acquired = False
        self._entered = False
        for attribute in _SERVICE_ATTRIBUTES:
            setattr(self, attribute, None)

    def __enter__(self):
        if self._entered:
            return self

        try:
            self._material_cache_acquired = acquire_material_cache(
                self.options.with_materials,
            )
            self.asset_index = build_asset_index(
                self.raw_root,
                self.options.index_extensions,
                policy=(
                    IndexPolicy.REFRESH
                    if self.force_refresh
                    else IndexPolicy.REUSE
                ),
            )
            self.sectors = SectorRepository(
                self.documents,
                asset_index=self.asset_index,
            )
            self.entities = EntityRepository(
                self.documents,
                asset_index=self.asset_index,
            )
            self.rigs = RigRepository(
                self.documents,
                asset_index=self.asset_index,
            )
            self.meshes = MeshRepository(self.asset_index)
            self.material_resources = MaterialResourceRepository(
                self.documents,
                asset_index=self.asset_index,
            )
            self._material_scope = material_resource_scope(self.material_resources)
            self._material_scope.__enter__()
            self.files = SectorFileSet(self.asset_index)
            for attribute, factory, option_name in _SERVICE_FACTORIES:
                enabled = (
                    option_name is None
                    or bool(getattr(self.options, option_name))
                )
                setattr(self, attribute, factory(self) if enabled else None)
        except Exception:
            self._reset_runtime_state()
            raise

        self._entered = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._reset_runtime_state()
        return False

    def _reset_runtime_state(self):
        if self.masters is not None:
            try:
                self.masters.hide_viewport = True
            except (AttributeError, ReferenceError, TypeError):
                pass
        if self._material_scope is not None:
            self._material_scope.__exit__(None, None, None)
            self._material_scope = None
        if self.material_resources is not None:
            self.material_resources.clear()
        self.documents.close()
        self.documents = DocumentSession()
        self.sectors = None
        self.entities = None
        self.rigs = None
        self.meshes = None
        self.material_resources = None
        self.masters = None
        for attribute in _SERVICE_ATTRIBUTES:
            setattr(self, attribute, None)
        self.asset_index = None
        self.files = None
        self.caches = SectorImportCaches()
        release_material_cache(self._material_cache_acquired)
        self._material_cache_acquired = False
        self._entered = False

    def _require_entered(self):
        if not self._entered:
            raise RuntimeError(
                "SectorImportSession must be entered before use"
            )

    def safe_json(self, value):
        if isinstance(value, (dict, list, tuple)):
            key = id(value)
            cached = self.caches.serialized_json.get(key)
            if cached is not None and cached[0] is value:
                return cached[1]
            encoded = json.dumps(
                value,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            self.caches.serialized_json[key] = (value, encoded)
            return encoded
        return json.dumps(
            value,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def load_sector(self, filepath):
        self._require_entered()
        parsed = self.sectors.load_sector(filepath, required=True)
        if parsed is None:
            raise ValueError(f"Failed to load streaming sector: {filepath}")
        return parsed

    def sector_paths(self):
        self._require_entered()
        project_sector = os.path.join(
            self.base_path,
            self.project_name + ".streamingsector.json",
        )
        project_key = _path_key(project_sector)
        return tuple(
            path
            for path in sorted(self.files.sectors)
            if _path_key(path) != project_key
            and "sim_" not in path.casefold()
        )

    def planned_sector(self, filepath):
        self._require_entered()
        key = _path_key(filepath)
        planned = self.caches.planned_sectors.get(key)
        if planned is None:
            planned = compile_sector_plan(
                self.load_sector(filepath),
                self.options,
            )
            self.caches.planned_sectors[key] = planned
        return planned

    def planned_sectors(self):
        return tuple(
            self.planned_sector(path)
            for path in self.sector_paths()
        )
