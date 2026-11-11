from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from ...animation.services.rig.repository import RigRepository
from ...assetio.documents import DocumentSession
from ...assetio.index import IndexPolicy, build_asset_index, indexed_files
from ...assetio.paths import absolute_local_path_key
from ...assetio.resolver import resolution_scope
from ...blender.physics.world import SectorCollisionService
from ...core.log import get_logger, log_once
from ...materials.repository import MaterialResourceRepository
from ...materials.resources import material_resource_scope
from ...meshes.repository import MeshRepository
from ..common.cache import acquire_material_cache, release_material_cache
from ..entity.repository import EntityRepository
from .options import sector_matches_filter
from .planner import compile_sector_plan
from .repository import SectorRepository
from .services.acoustics import AcousticSectorService
from .services.buffers import TransformBufferService
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

_LOG = get_logger(__name__)


class SectorFileSet:
    __slots__ = ("_cache", "asset_index")

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


@dataclass(slots=True)
class SectorImportCaches:
    planned_sectors: dict[str, object] = field(default_factory=dict)
    sector_paths: tuple[str, ...] | None = None
    planned_sector_sequence: tuple[object, ...] | None = None
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


_SERVICE_FACTORIES = (
    ("resource_resolver", lambda session: IndexedResourceResolver(session), None),
    ("primitive_meshes", lambda session: PrimitiveMeshService(session), None),
    ("master_assets", lambda session: MasterAssetServices(session), None),
    ("transform_buffers", lambda _session: TransformBufferService(), None),
    (
        "foliage_assets",
        lambda session: FoliageResourceService(session),
        frozenset({"foliage"}),
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
        frozenset({"sector_lights"}),
    ),
    (
        "probe_assets",
        lambda session: ReflectionProbeService(session),
        frozenset({"reflection_probes"}),
    ),
    (
        "effect_assets",
        lambda session: EffectResourceService(session),
        frozenset({"effects"}),
    ),
    (
        "acoustic_assets",
        lambda session: AcousticSectorService(session),
        frozenset({"acoustic_data"}),
    ),
    (
        "minimap_assets",
        lambda session: MinimapResourceService(session),
        frozenset({"minimap"}),
    ),
    ("semantic_assets", lambda session: SemanticMarkerService(session), None),
    ("spline_assets", lambda _session: SplineService(), None),
    ("gi_assets", lambda session: GIResourceService(session), frozenset({"gi_data"})),
    (
        "physx_collision_assets",
        lambda session: SectorCollisionService(session),
        frozenset({"terrain_heightfields", "foliage_destruction"}),
    ),
)
_SERVICE_ATTRIBUTES = tuple(name for name, _factory, _choices in _SERVICE_FACTORIES)


class SectorImportSession:
    def __init__(
        self, project_filepath, options, *, force_refresh=False, depot_root=""
    ):
        self.project_filepath = os.path.abspath(project_filepath)
        self.project_path = os.path.dirname(self.project_filepath)
        self.project_name = os.path.basename(self.project_path)
        self.raw_root = os.path.join(self.project_path, "source", "raw")
        self.base_path = os.path.join(self.raw_root, "base")
        self.options = options
        self.force_refresh = bool(force_refresh)
        self.depot_root = os.path.normpath(str(depot_root)) if depot_root else ""

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
        self._resolution_scope = None
        self.masters = None
        self._material_cache_acquired = False
        self._entered = False
        for attribute in _SERVICE_ATTRIBUTES:
            setattr(self, attribute, None)

    def __enter__(self):
        if self._entered:
            return self

        try:
            self._resolution_scope = resolution_scope()
            self._resolution_scope.__enter__()
            self._material_cache_acquired = acquire_material_cache(
                self.options.with_materials,
            )
            self.asset_index = build_asset_index(
                self.raw_root,
                self.options.index_extensions,
                policy=(
                    IndexPolicy.REFRESH if self.force_refresh else IndexPolicy.REUSE
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
                image_index_policy=(
                    IndexPolicy.REFRESH if self.force_refresh else IndexPolicy.REUSE
                ),
            )
            self._material_scope = material_resource_scope(self.material_resources)
            self._material_scope.__enter__()
            self.files = SectorFileSet(self.asset_index)
            for attribute, factory, choices in _SERVICE_FACTORIES:
                enabled = choices is None or bool(choices & self.options.choices)
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
            except (AttributeError, ReferenceError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("SectorImportSession._reset_runtime_state", type(error).__name__),
                    "reset runtime state: fell back after %s",
                    error,
                    exc_info=True,
                )
        if self._material_scope is not None:
            self._material_scope.__exit__(None, None, None)
            self._material_scope = None
        if self._resolution_scope is not None:
            self._resolution_scope.__exit__(None, None, None)
            self._resolution_scope = None
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
            raise RuntimeError("SectorImportSession must be entered before use")

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
        cached = self.caches.sector_paths
        if cached is not None:
            return cached
        project_sector = os.path.join(
            self.base_path,
            self.project_name + ".streamingsector.json",
        )
        project_key = absolute_local_path_key(project_sector)
        cached = tuple(
            path
            for path in sorted(self.files.sectors)
            if absolute_local_path_key(path) != project_key
            and "sim_" not in os.path.basename(path).casefold()
            and sector_matches_filter(path, self.options.sector_filter)
        )
        self.caches.sector_paths = cached
        return cached

    def planned_sector(self, filepath):
        self._require_entered()
        key = absolute_local_path_key(filepath)
        planned = self.caches.planned_sectors.get(key)
        if planned is None:
            planned = compile_sector_plan(
                self.load_sector(filepath),
                self.options,
            )
            self.caches.planned_sectors[key] = planned
        return planned

    def planned_sectors(self):
        self._require_entered()
        cached = self.caches.planned_sector_sequence
        if cached is not None:
            return cached
        cached = tuple(self.planned_sector(path) for path in self.sector_paths())
        self.caches.planned_sector_sequence = cached
        return cached
