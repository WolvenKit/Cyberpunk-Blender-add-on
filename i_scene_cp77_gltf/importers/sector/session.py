from __future__ import annotations

from dataclasses import dataclass, field
import json
import os

from ...datakrash import DepotAssetIndex
from ...jsontool import JSONTool

from .options import MESH_GLB_EXTENSIONS
from ..common.cache import (
    acquire_json_cache,
    acquire_material_cache,
    release_json_cache,
    release_material_cache,
)
from ..common.paths import absolute_path_key
from ..common.resources import indexed_files
from .planner import compile_sector_plan
from .services import (
    AcousticSectorService,
    CollisionMetadataService,
    DecalService,
    DeformationService,
    EffectResourceService,
    FoliageResourceService,
    GIResourceService,
    IndexedResourceResolver,
    MasterAssetServices,
    MinimapResourceService,
    PrimitiveMeshService,
    ReflectionProbeService,
    SemanticMarkerService,
    SplineService,
    StaticLightingService,
    TransformBufferService,
    WorldMetadataService,
)


@dataclass(slots=True, frozen=True)
class SectorFileSet:
    sectors: tuple[str, ...]
    mesh_jsons: tuple[str, ...]
    animation_glbs: tuple[str, ...]
    appearance_jsons: tuple[str, ...]
    rig_jsons: tuple[str, ...]
    mesh_glbs: tuple[str, ...]


@dataclass(slots=True)
class SectorImportCaches:
    parsed_sectors: dict[str, object] = field(default_factory=dict)
    planned_sectors: dict[str, object] = field(default_factory=dict)
    entity_masters: dict[tuple, object] = field(default_factory=dict)
    entity_documents: dict[str, object] = field(default_factory=dict)
    entity_resolutions: dict[tuple, str] = field(default_factory=dict)
    mesh_masters: dict[tuple, object] = field(default_factory=dict)
    proxy_masters: dict[tuple, object] = field(default_factory=dict)
    foliage_resources: dict[str, object] = field(default_factory=dict)
    materials: dict[tuple, object] = field(default_factory=dict)
    resource_resolutions: dict[tuple, object] = field(
        default_factory=dict
    )
    primitive_meshes: dict[tuple, object] = field(
        default_factory=dict
    )
    decal_meshes: dict[tuple, object] = field(
        default_factory=dict
    )
    serialized_json: dict[int, tuple[object, str]] = field(
        default_factory=dict
    )


_path_key = absolute_path_key


_SERVICE_FACTORIES = (
    ("resource_resolver", lambda session: IndexedResourceResolver(session)),
    ("primitive_meshes", lambda session: PrimitiveMeshService(session)),
    ("master_assets", lambda session: MasterAssetServices(session)),
    ("transform_buffers", lambda _session: TransformBufferService()),
    ("foliage_assets", lambda session: FoliageResourceService(session)),
    ("deformation_assets", lambda _session: DeformationService()),
    ("world_metadata_assets", lambda _session: WorldMetadataService()),
    ("decal_assets", lambda session: DecalService(session)),
    ("lighting_assets", lambda session: StaticLightingService(session)),
    ("probe_assets", lambda session: ReflectionProbeService(session)),
    ("effect_assets", lambda session: EffectResourceService(session)),
    ("acoustic_assets", lambda session: AcousticSectorService(session)),
    ("minimap_assets", lambda session: MinimapResourceService(session)),
    ("semantic_assets", lambda session: SemanticMarkerService(session)),
    ("spline_assets", lambda _session: SplineService()),
    ("gi_assets", lambda session: GIResourceService(session)),
    (
        "collision_metadata_assets",
        lambda session: CollisionMetadataService(session),
    ),
)


class SectorImportSession:
    def __init__(self, project_filepath, options, *, force_refresh=True):
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
        for attribute, _factory in _SERVICE_FACTORIES:
            setattr(self, attribute, None)
        self._owns_json_cache = False
        self._material_cache_acquired = False
        self._entered = False

    def __enter__(self):
        if self._entered:
            return self

        try:
            self._material_cache_acquired = acquire_material_cache(
                self.options.with_materials,
            )
            self._owns_json_cache = acquire_json_cache(JSONTool)
            self.asset_index = DepotAssetIndex.cached(
                self.raw_root,
                self.options.index_extensions,
                force_refresh=self.force_refresh,
            )
            self.files = SectorFileSet(
                sectors=indexed_files(
                    self.asset_index,
                    ".streamingsector.json",
                ),
                mesh_jsons=indexed_files(
                    self.asset_index,
                    ".mesh.json",
                ),
                animation_glbs=indexed_files(
                    self.asset_index,
                    ".anims.glb",
                ),
                appearance_jsons=indexed_files(
                    self.asset_index,
                    ".app.json",
                ),
                rig_jsons=indexed_files(
                    self.asset_index,
                    ".rig.json",
                ),
                mesh_glbs=indexed_files(
                    self.asset_index,
                    *MESH_GLB_EXTENSIONS,
                ),
            )
            for attribute, factory in _SERVICE_FACTORIES:
                setattr(self, attribute, factory(self))
        except Exception:
            try:
                release_json_cache(
                    JSONTool,
                    self._owns_json_cache,
                )
            finally:
                self._owns_json_cache = False
                release_material_cache(self._material_cache_acquired)
                self._material_cache_acquired = False
            for attribute, _factory in _SERVICE_FACTORIES:
                setattr(self, attribute, None)
            self.asset_index = None
            self.files = None
            raise

        self._entered = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            release_json_cache(
                JSONTool,
                self._owns_json_cache,
            )
        finally:
            self._owns_json_cache = False
            release_material_cache(self._material_cache_acquired)
            self._material_cache_acquired = False
        for attribute, _factory in _SERVICE_FACTORIES:
            setattr(self, attribute, None)
        self._entered = False
        return False

    def _require_entered(self):
        services_ready = all(
            getattr(self, attribute, None) is not None
            for attribute, _factory in _SERVICE_FACTORIES
        )
        if (
            not self._entered
            or self.asset_index is None
            or self.files is None
            or not services_ready
        ):
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
        key = _path_key(filepath)
        parsed = self.caches.parsed_sectors.get(key)
        if parsed is None:
            parsed = JSONTool.load_sector(filepath)
            if parsed is None:
                raise ValueError(f"Failed to parse streaming sector: {filepath}")
            self.caches.parsed_sectors[key] = parsed
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
            and "sim_" not in path
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

    def legacy_sector_entries(self):
        return [
            planned.legacy_entry()
            for planned in self.planned_sectors()
        ]
