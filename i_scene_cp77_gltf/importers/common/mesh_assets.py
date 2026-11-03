import hashlib
import json
import os
import re
<<<<<<< Updated upstream
import traceback
import time
from array import array
=======
import time
from array import array
from collections import deque
from concurrent.futures import ThreadPoolExecutor
>>>>>>> Stashed changes
from functools import lru_cache

import bpy

<<<<<<< Updated upstream
from ...addon_identity import get_addon_preferences
from ...materials.blender.cache import material_cache_counters, material_cache_stats

from ..mesh import (
    ensure_collection_material_coverage,
    import_cyberpunk_glb,
)

=======
from ...assetio.catalog import ResourceKind
from ...assetio.paths import local_path_key, material_sidecar_path
from ...assetio.values import json_array
from ...blender.identity import authored_material_name, rna_is_live
from ...blender.naming import fit_id_name
from ...blender.transactions import (
    current_import_transaction,
    rollback_import_child,
    track_created_datablock,
)
from ...core.log import debug_exception, get_logger, is_enabled, log_once
from ...gltf.submesh import submesh_index_from_name
from ...materials.blender.builder import (
    material_handler_timing_stats,
    material_organization_phase_timing_stats,
    material_template_timing_stats,
)
from ...materials.blender.bulk import bulk_material_import_scope
from ...materials.blender.cache import material_cache_counters, material_cache_stats
from ...materials.blender.multilayer import override_palette_batched
from ...materials.blender.profiling import (
    detailed_material_profiling_requested,
    finish_material_profiling,
    material_profile_details,
    material_profile_phase,
    material_profile_total,
    start_material_profiling,
)
from ...meshes.repository import (
    MESH_COOKED_NAME_SUFFIXES,
    MeshRepository,
    is_physical_scene,
)
from ..mesh.document import decode_mesh_glb
from ..mesh.orchestration import (
    ensure_collection_material_coverage,
    import_cyberpunk_glb,
)
>>>>>>> Stashed changes
from .cache import (
    acquire_material_cache,
    release_material_cache,
)
<<<<<<< Updated upstream
from ...meshes import MESH_COOKED_NAME_SUFFIXES, MeshRepository
from ...blender.transactions import current_import_transaction, track_created_datablock
=======
from .collections import (
    link_collection_once,
    preserve_world_parent,
    remap_copied_object_references,
)
>>>>>>> Stashed changes
from .material_appearances import (
    is_source_default_appearance,
    resolve_appearance_materials,
    wrapped_string,
)

<<<<<<< Updated upstream
from .collections import (
    _link_collection_once,
    _preserve_world_parent,
    _remap_copied_object_references,
    _unlink_collection_once,
)

NAME_MAX_LEN = 256
SUBMESH_PATTERN = re.compile(r"submesh_(\d+)", re.IGNORECASE)
BLENDER_NUMERIC_SUFFIX_PATTERN = re.compile(r"\.\d{3,}$")
APPEARANCE_ASSIGNMENT_VERSION = 4

_SUBMESH_INDEX_CACHE = {}
=======
_LOG = get_logger(__name__)

# Blender 5 stores ID names of at most 255 UTF-8 bytes.
_MASTER_BASE_KEY = "cp77_master_base"
BLENDER_NUMERIC_SUFFIX_PATTERN = re.compile(r"\.\d{3,}$")
APPEARANCE_ASSIGNMENT_VERSION = 5
_MATERIAL_JSON_PREFETCH_WINDOW = 96
_MATERIAL_JSON_PREFETCH_WORKERS = 4

>>>>>>> Stashed changes
_JSON_APPS_CACHE = {}


_DATA_COLLECTION_BY_OBJECT_TYPE = {
    "MESH": "meshes",
    "CURVE": "curves",
    "ARMATURE": "armatures",
    "LATTICE": "lattices",
    "LIGHT": "lights",
    "CAMERA": "cameras",
}


<<<<<<< Updated upstream
def _copy_object_for_transaction(source_obj):
    obj = track_created_datablock("objects", source_obj.copy())
    source_data = getattr(source_obj, "data", None)
    if source_data is None:
        return obj
    copied_data = source_data.copy()
    collection_name = _DATA_COLLECTION_BY_OBJECT_TYPE.get(
        getattr(obj, "type", "")
    )
=======
def _copy_object_for_transaction(source_obj, *, copy_data=True):
    obj = track_created_datablock("objects", source_obj.copy())
    source_data = getattr(source_obj, "data", None)
    if source_data is None or not copy_data:
        return obj
    copied_data = source_data.copy()
    collection_name = _DATA_COLLECTION_BY_OBJECT_TYPE.get(getattr(obj, "type", ""))
>>>>>>> Stashed changes
    if collection_name:
        track_created_datablock(collection_name, copied_data)
    obj.data = copied_data
    return obj


<<<<<<< Updated upstream
def clear_submesh_index_cache():
    _SUBMESH_INDEX_CACHE.clear()
=======
@lru_cache(maxsize=4096)
def _submesh_index_from_names(object_name, material_names):
    index = submesh_index_from_name(object_name, None)
    if index is not None:
        return index
    for material_name in material_names:
        index = submesh_index_from_name(material_name, None)
        if index is not None:
            return index
    return None


def clear_submesh_index_cache():
    _submesh_index_from_names.cache_clear()
>>>>>>> Stashed changes
    _JSON_APPS_CACHE.clear()


def submesh_index_for_object(obj):
    try:
<<<<<<< Updated upstream
        explicit_index = int(obj.get('cp77_submesh_index', -1))
    except (AttributeError, ReferenceError, TypeError, ValueError):
=======
        explicit_index = int(obj.get("cp77_submesh_index", -1))
    except (AttributeError, ReferenceError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("submesh_index_for_object 1", type(error).__name__),
            "submesh index for object: fell back after %s",
            error,
            exc_info=True,
        )
>>>>>>> Stashed changes
        explicit_index = -1
    if explicit_index >= 0:
        return explicit_index

<<<<<<< Updated upstream
    name = getattr(obj, 'name', '')
    cached = _SUBMESH_INDEX_CACHE.get(name)
    if cached is not None:
        return None if cached < 0 else cached
    match = SUBMESH_PATTERN.search(name)
    if match:
        index = int(match.group(1))
        _SUBMESH_INDEX_CACHE[name] = index
        return index
    data = getattr(obj, 'data', None)
    for mat in getattr(data, 'materials', ()) if data is not None else ():
        mat_name = getattr(mat, 'name', '') if mat else ''
        match = SUBMESH_PATTERN.search(mat_name) if mat_name else None
        if match:
            index = int(match.group(1))
            _SUBMESH_INDEX_CACHE[name] = index
            return index
    _SUBMESH_INDEX_CACHE[name] = -1
    return None
=======
    try:
        object_name = str(getattr(obj, "name", "") or "")
        data = getattr(obj, "data", None)
        materials = getattr(data, "materials", ()) if data is not None else ()
        material_names = tuple(
            str(getattr(material, "name", "") or "")
            for material in materials
            if material is not None
        )
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("submesh_index_for_object 2", type(error).__name__),
            "submesh index for object: fell back after %s",
            error,
            exc_info=True,
        )
        object_name = str(getattr(obj, "name", "") or "")
        material_names = ()
    return _submesh_index_from_names(object_name, material_names)
>>>>>>> Stashed changes


def _appearance_name(mesh_appearance):
    if isinstance(mesh_appearance, dict):
<<<<<<< Updated upstream
        mesh_appearance = mesh_appearance.get('$value', '')
    return str(mesh_appearance or '')
=======
        mesh_appearance = mesh_appearance.get("$value", "")
    return str(mesh_appearance or "")
>>>>>>> Stashed changes


@lru_cache(maxsize=8192)
def _groupname_cached(meshname, appearance):
    groupname = os.path.splitext(os.path.basename(meshname))[0]
<<<<<<< Updated upstream
    if 'intersection' in meshname:
        groupname = os.path.basename(os.path.dirname(meshname)) + '_' + groupname
    if appearance:
        groupname += '@' + appearance
    return groupname[:NAME_MAX_LEN]
=======
    if "intersection" in meshname:
        groupname = os.path.basename(os.path.dirname(meshname)) + "_" + groupname
    if appearance:
        groupname += "@" + appearance
    return fit_id_name(groupname)
>>>>>>> Stashed changes


def get_groupname(meshname, meshAppearance):
    return _groupname_cached(meshname, _appearance_name(meshAppearance))


@lru_cache(maxsize=8192)
def _asset_source_key(meshpath):
<<<<<<< Updated upstream
    return os.path.normcase(os.path.normpath(meshpath)) if meshpath else ''
=======
    return local_path_key(meshpath) if meshpath else ""
>>>>>>> Stashed changes


@lru_cache(maxsize=8192)
def _source_suffix(source_key):
<<<<<<< Updated upstream
    return '~' + hashlib.sha1(source_key.encode('utf-8')).hexdigest()[:8]


def _hashed_groupname(meshname, meshAppearance, source_key):
    base = get_groupname(meshname, '')
    suffix = _source_suffix(source_key)
    name = base[:NAME_MAX_LEN - len(suffix)] + suffix
    appearance = _appearance_name(meshAppearance)
    if appearance:
        name += '@' + appearance
    return name[:NAME_MAX_LEN]
=======
    return "~" + hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:8]


def _hashed_groupname(meshname, meshAppearance, source_key):
    base = get_groupname(meshname, "")
    suffix = _source_suffix(source_key)
    name = fit_id_name(base, suffix)
    appearance = _appearance_name(meshAppearance)
    if appearance:
        name += "@" + appearance
    return fit_id_name(name)
>>>>>>> Stashed changes


def _collection_matches_source(collection, source_key):
    if not source_key:
        return True
<<<<<<< Updated upstream
    stored = collection.get('source_glb', '')
    # An untagged legacy master cannot safely prove source identity. Rebuild it
=======
    stored = collection.get("sourcePath", "")
    # An untagged master cannot safely prove source identity. Rebuild it
>>>>>>> Stashed changes
    # under the hashed name instead of risking a same-basename asset collision.
    return bool(stored) and _asset_source_key(stored) == source_key


<<<<<<< Updated upstream
def get_group(meshname, meshAppearance, Masters, source_glb=''):
=======
def _base_master_index(masters):
    """Map source keys to base masters, independent of their display names"""
    index = {}
    for collection in masters.children:
        try:
            if not collection.get(_MASTER_BASE_KEY, False):
                continue
            source = collection.get("sourcePath", "")
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_base_master_index", type(error).__name__),
                "base master index: fell back after %s",
                error,
                exc_info=True,
            )
            continue
        if source:
            index.setdefault(_asset_source_key(source), collection)
    return index


def _find_base_master(masters, meshpath, source_key, base_index):
    master = base_index.get(source_key)
    if master is not None and rna_is_live(master):
        return master, master.name
    # Masters created before the base-master tag are found by display name.
    groupname = get_groupname(meshpath, "")
    existing_master = masters.children.get(groupname)
    if existing_master is not None and not _collection_matches_source(
        existing_master, source_key
    ):
        # Use a source hash when another asset owns the display name.
        groupname = _hashed_groupname(meshpath, "", source_key)
        existing_master = masters.children.get(groupname)
        if existing_master is not None and not _collection_matches_source(
            existing_master, source_key
        ):
            existing_master = None
    return existing_master, groupname


def get_group(meshname, meshAppearance, Masters, source_glb=""):
>>>>>>> Stashed changes
    # Verify source identity to avoid same-name asset collisions.
    source_key = _asset_source_key(source_glb)
    candidates = [get_groupname(meshname, meshAppearance)]
    if source_key:
        candidates.append(_hashed_groupname(meshname, meshAppearance, source_key))
    for groupname in candidates:
        group = Masters.children.get(groupname)
        if group is not None and _collection_matches_source(group, source_key):
            return group, groupname
    if source_key:
        requested_appearance = _appearance_name(meshAppearance)
        for group in Masters.children:
            if not _collection_matches_source(group, source_key):
                continue
<<<<<<< Updated upstream
            stored_appearance = _appearance_name(
                group.get('appearance', '')
            )
            if requested_appearance:
                if stored_appearance != requested_appearance:
                    continue
            elif stored_appearance not in ('', 'default'):
=======
            stored_appearance = _appearance_name(group.get("appearance", ""))
            if requested_appearance:
                if stored_appearance != requested_appearance:
                    continue
            elif stored_appearance not in ("", "default"):
>>>>>>> Stashed changes
                continue
            return group, group.name
    return None, candidates[0]


<<<<<<< Updated upstream


def _armature_bind_signature(armature):
    data = getattr(armature, 'data', None)
    bones = getattr(data, 'bones', None)
    if data is None or bones is None:
        return ''
=======
def _armature_bind_signature(armature):
    data = getattr(armature, "data", None)
    bones = getattr(data, "bones", None)
    if data is None or bones is None:
        return ""
>>>>>>> Stashed changes
    payload = []
    try:
        for bone in bones:
            matrix = tuple(
                round(float(component), 8)
                for row in bone.matrix_local
                for component in row
            )
<<<<<<< Updated upstream
            payload.append((bone.name, bone.parent.name if bone.parent else '', matrix))
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        return ''
    encoded = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.blake2b(encoded, digest_size=20).hexdigest()




=======
            payload.append((bone.name, bone.parent.name if bone.parent else "", matrix))
    except (
        AttributeError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_armature_bind_signature", type(error).__name__),
            "armature bind signature: fell back after %s",
            error,
            exc_info=True,
        )
        return ""
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return hashlib.blake2b(encoded, digest_size=20).hexdigest()


>>>>>>> Stashed changes
def _redirect_master_armature(collection, source, target):
    redirected = 0
    for obj in tuple(collection.all_objects):
        if obj is source:
            continue
        changed = False
<<<<<<< Updated upstream
        for modifier in getattr(obj, 'modifiers', ()):
            if getattr(modifier, 'type', None) == 'ARMATURE' and modifier.object is source:
                modifier.object = target
                changed = True
        if getattr(obj, 'parent', None) is source:
            _preserve_world_parent(obj, target)
=======
        for modifier in getattr(obj, "modifiers", ()):
            if (
                getattr(modifier, "type", None) == "ARMATURE"
                and modifier.object is source
            ):
                modifier.object = target
                changed = True
        if getattr(obj, "parent", None) is source:
            preserve_world_parent(obj, target)
>>>>>>> Stashed changes
            changed = True
        redirected += int(changed)
    return redirected


<<<<<<< Updated upstream
def _deduplicate_master_source_armatures(master_collection, masters):
    """Share source-rest armatures only when complete bind signatures match."""
    imported = [
        obj for obj in tuple(master_collection.all_objects)
        if getattr(obj, 'type', None) == 'ARMATURE'
    ]
    if not imported:
        return []

    existing_by_signature = {}
    for obj in tuple(masters.all_objects):
        if obj in imported or getattr(obj, 'type', None) != 'ARMATURE':
            continue
        signature = str(obj.get('cp77_master_bind_signature', '') or '')
        if signature:
            existing_by_signature.setdefault(signature, obj)
=======
def _master_armature_signature_index(masters, *, exclude=()):
    excluded = set(exclude)
    existing_by_signature = {}
    for obj in tuple(masters.all_objects):
        if obj in excluded or getattr(obj, "type", None) != "ARMATURE":
            continue
        signature = str(obj.get("cp77_master_bind_signature", "") or "")
        if signature:
            existing_by_signature.setdefault(signature, obj)
    return existing_by_signature


def _deduplicate_master_source_armatures(
    master_collection,
    masters,
    existing_by_signature=None,
    *,
    source_armatures=None,
):
    """Share source-rest armatures only when complete bind signatures match"""
    imported = source_armatures
    if imported is None:
        imported = [
            obj
            for obj in tuple(master_collection.all_objects)
            if getattr(obj, "type", None) == "ARMATURE"
        ]
    if not imported:
        return []

    if existing_by_signature is None:
        existing_by_signature = _master_armature_signature_index(masters)
    for source in imported:
        signature = str(source.get("cp77_master_bind_signature", "") or "")
        if signature and existing_by_signature.get(signature) is source:
            existing_by_signature.pop(signature, None)
>>>>>>> Stashed changes

    authoritative = []
    for source in imported:
        signature = _armature_bind_signature(source)
        if not signature:
            authoritative.append(source)
            continue
<<<<<<< Updated upstream
        source['cp77_master_bind_signature'] = signature
=======
        source["cp77_master_bind_signature"] = signature
>>>>>>> Stashed changes
        target = existing_by_signature.get(signature)
        if target is None:
            existing_by_signature[signature] = source
            authoritative.append(source)
            continue

        _redirect_master_armature(master_collection, source, target)
        if master_collection.objects.get(target.name) is not target:
            master_collection.objects.link(target)
<<<<<<< Updated upstream
        source_data = getattr(source, 'data', None)
        bpy.data.objects.remove(source, do_unlink=True)
        if source_data is not None and getattr(source_data, 'users', 0) == 0:
=======
        source_data = getattr(source, "data", None)
        bpy.data.objects.remove(source, do_unlink=True)
        if source_data is not None and getattr(source_data, "users", 0) == 0:
>>>>>>> Stashed changes
            try:
                bpy.data.armatures.remove(source_data)
            except (ReferenceError, RuntimeError, TypeError):
                pass
<<<<<<< Updated upstream
        target['cp77_master_source_armature'] = True
        target['cp77_master_bind_signature'] = signature
=======
        target["cp77_master_bind_signature"] = signature
>>>>>>> Stashed changes
        authoritative.append(target)
    unique = []
    seen_ids = set()
    for armature in authoritative:
        key = id(armature)
        if key in seen_ids:
            continue
        seen_ids.add(key)
        unique.append(armature)
    return unique


<<<<<<< Updated upstream


def _json_apps_for_collection(collection, mesh_key):
    json_apps_raw = collection.get('json_apps')
    if not json_apps_raw:
        print(f'No material json found for - {mesh_key}')
=======
def _rollback_failed_master(
    state, mesh_key, source_key, base_index, armature_preparation
):
    """Remove everything one mesh master created since state and forget the indexes that may point into it"""
    rollback_import_child(state, f"mesh master {mesh_key}")
    master = base_index.get(source_key)
    if master is not None and not rna_is_live(master):
        base_index.pop(source_key, None)
    armature_preparation.by_signature = None


class _MasterArmaturePreparation:
    def __init__(self, masters):
        self.masters = masters
        self.by_signature = None
        self.index_seconds = 0.0
        self.index_builds = 0
        self.static_sources = 0
        self.skinned_sources = 0

    def deduplicate(self, collection):
        sources = tuple(
            obj
            for obj in collection.all_objects
            if getattr(obj, "type", None) == "ARMATURE"
        )
        if not sources:
            self.static_sources += 1
            return []
        self.skinned_sources += 1
        if self.by_signature is None:
            started = time.perf_counter()
            # The current source is already linked; it cannot be its own reuse target.
            self.by_signature = _master_armature_signature_index(
                self.masters,
                exclude=sources,
            )
            self.index_seconds += time.perf_counter() - started
            self.index_builds += 1
        return _deduplicate_master_source_armatures(
            collection,
            self.masters,
            self.by_signature,
            source_armatures=sources,
        )


def _json_apps_for_collection(collection, mesh_key):
    json_apps_raw = collection.get("cp77_json_apps")
    if not json_apps_raw:
        _LOG.debug("No Material.json metadata on mesh master %s", mesh_key)
>>>>>>> Stashed changes
        return None

    cache_key = collection.as_pointer()
    cached = _JSON_APPS_CACHE.get(cache_key)
    if cached is not None and cached[0] == json_apps_raw:
        return cached[1]

    try:
        json_apps = json.loads(json_apps_raw)
    except json.JSONDecodeError:
<<<<<<< Updated upstream
        print(f'Invalid material json found for - {mesh_key}')
        return None
    if not json_apps:
        print(f'No material json found for - {mesh_key}')
=======
        _LOG.warning(
            "Invalid Material.json metadata on mesh master %s", mesh_key, exc_info=True
        )
        return None
    if not json_apps:
        _LOG.debug("No Material.json metadata on mesh master %s", mesh_key)
>>>>>>> Stashed changes
        return json_apps

    _JSON_APPS_CACHE[cache_key] = (json_apps_raw, json_apps)
    return json_apps


<<<<<<< Updated upstream
def _authored_material_name(material):
    if material is None:
        return ''
    try:
        metadata = material.get('m')
    except (AttributeError, TypeError):
        metadata = None
    if metadata is not None:
        try:
            name = metadata.get('Name')
        except (AttributeError, TypeError):
            name = None
        if name:
            return wrapped_string(name)
    for key in ('sourceMaterialName', 'cp77MaterialName'):
        try:
            name = material.get(key)
        except (AttributeError, TypeError):
            name = None
        if name:
            return wrapped_string(name)
    return ''


def _blender_material_name(material):
    return str(getattr(material, 'name', '') or '')


def _without_blender_numeric_suffix(name):
    return BLENDER_NUMERIC_SUFFIX_PATTERN.sub('', str(name or ''))
=======
def _blender_material_name(material):
    return str(getattr(material, "name", "") or "")


def _without_blender_numeric_suffix(name):
    return BLENDER_NUMERIC_SUFFIX_PATTERN.sub("", str(name or ""))
>>>>>>> Stashed changes


def _unique_materials(materials):
    unique = []
    seen = set()
    for material in materials or ():
        if material is None:
            continue
        try:
<<<<<<< Updated upstream
            key = ('POINTER', material.as_pointer())
        except (AttributeError, TypeError):
            key = ('OBJECT', id(material))
=======
            key = ("POINTER", material.as_pointer())
        except (AttributeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_unique_materials", type(error).__name__),
                "unique materials: fell back after %s",
                error,
                exc_info=True,
            )
            key = ("OBJECT", id(material))
>>>>>>> Stashed changes
        if key in seen:
            continue
        seen.add(key)
        unique.append(material)
    return unique


<<<<<<< Updated upstream
def _resolve_matching_material(materials, mat_name):
    expected = wrapped_string(mat_name)
    if not expected:
        return None, 'empty_material_name', ()

    candidates = _unique_materials(materials)
    expected_folded = expected.casefold()
    records = []
    for material in candidates:
        authored = _authored_material_name(material)
        datablock = _blender_material_name(material)
        stripped = _without_blender_numeric_suffix(datablock)
        records.append((
            material,
            authored,
            authored.casefold(),
            datablock,
            datablock.casefold(),
            stripped,
            stripped.casefold(),
        ))

    matchers = (
        ('authored_exact', 1, expected),
        ('authored_casefold', 2, expected_folded),
        ('datablock_exact', 3, expected),
        ('datablock_casefold', 4, expected_folded),
        ('datablock_suffix_exact', 5, expected),
        ('datablock_suffix_casefold', 6, expected_folded),
    )
    for match_kind, field_index, match_value in matchers:
        matches = [record[0] for record in records if record[field_index] == match_value]
        if len(matches) == 1:
            return matches[0], match_kind, ()
        if len(matches) > 1:
            names = tuple(
                _authored_material_name(material)
                or _blender_material_name(material)
                for material in matches
            )
            return None, f'ambiguous_{match_kind}', names
    return None, 'missing_material', tuple(
        record[1] or record[3]
        for record in records
    )


def _reset_polygon_material_indices(obj):
    polygons = getattr(getattr(obj, 'data', None), 'polygons', None)
    if polygons:
        polygons.foreach_set('material_index', array('i', [0]) * len(polygons))


def _clear_material_assignment(obj):
    if obj.type != 'MESH' or not obj.data:
=======
class _MaterialNameResolver:
    """Snapshot one stable source material table for an appearance-creation batch"""

    def __init__(self, materials):
        self.materials = tuple(_unique_materials(materials))
        self._indices = tuple({} for _ in range(6))
        self._names = []
        self.calls = 0
        for material in self.materials:
            authored = authored_material_name(material)
            datablock = _blender_material_name(material)
            stripped = _without_blender_numeric_suffix(datablock)
            display = authored or datablock
            self._names.append(display)
            fields = (
                authored,
                authored.casefold(),
                datablock,
                datablock.casefold(),
                stripped,
                stripped.casefold(),
            )
            for index, value in zip(self._indices, fields):
                index.setdefault(value, []).append((material, display))
        self._names = tuple(self._names)

    def resolve(self, mat_name):
        self.calls += 1
        expected = wrapped_string(mat_name)
        if not expected:
            return None, "empty_material_name", ()
        folded = expected.casefold()
        kinds = (
            "authored_exact",
            "authored_casefold",
            "datablock_exact",
            "datablock_casefold",
            "datablock_suffix_exact",
            "datablock_suffix_casefold",
        )
        for index, kind, value in zip(self._indices, kinds, (expected, folded) * 3):
            matches = index.get(value, ())
            if len(matches) == 1:
                return matches[0][0], kind, ()
            if matches:
                return (
                    None,
                    "ambiguous_" + kind,
                    tuple(display for _, display in matches),
                )
        return None, "missing_material", self._names


def _uses_object_material_overrides(obj):
    try:
        return bool(obj.get("cp77_linked_variant_data", False))
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_uses_object_material_overrides", type(error).__name__),
            "uses object material overrides: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def _assigned_material_slot_count(obj):
    if _uses_object_material_overrides(obj):
        return sum(
            1
            for slot in getattr(obj, "material_slots", ())
            if getattr(slot, "material", None) is not None
        )
    return len(getattr(getattr(obj, "data", None), "materials", ()))


def _reset_polygon_material_indices(obj):
    try:
        if bool(obj.get("cp77_single_material_submesh", False)):
            return
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_reset_polygon_material_indices", type(error).__name__),
            "reset polygon material indices: fell back after %s",
            error,
            exc_info=True,
        )
    polygons = getattr(getattr(obj, "data", None), "polygons", None)
    if polygons:
        polygons.foreach_set("material_index", array("i", [0]) * len(polygons))


def _clear_material_assignment(obj):
    if obj.type != "MESH" or not obj.data:
        return
    if _uses_object_material_overrides(obj):
        for slot in obj.material_slots:
            slot.link = "OBJECT"
            slot.material = None
>>>>>>> Stashed changes
        return
    obj.data.materials.clear()
    _reset_polygon_material_indices(obj)


def _assign_single_material(obj, material):
<<<<<<< Updated upstream
=======
    if _uses_object_material_overrides(obj):
        slots = tuple(obj.material_slots)
        if not slots:
            raise RuntimeError(
                f"Variant mesh {obj.name!r} has no material slot to override"
            )
        for index, slot in enumerate(slots):
            slot.link = "OBJECT"
            slot.material = material if index == 0 else None
        return
>>>>>>> Stashed changes
    obj.data.materials.clear()
    obj.data.materials.append(material)
    _reset_polygon_material_indices(obj)


def _keep_only_material(
<<<<<<< Updated upstream
        obj,
        mat_name,
        ):
    result = {
        'status': 'not_a_mesh',
        'matchKind': '',
        'expectedMaterial': wrapped_string(mat_name),
        'assignedMaterial': '',
        'assignedBlenderMaterial': '',
        'candidates': (),
    }
    if obj.type != 'MESH' or not obj.data:
        return result
    material, match_kind, candidates = _resolve_matching_material(
        obj.data.materials,
        mat_name,
    )
    result['matchKind'] = match_kind
    result['candidates'] = candidates
    if material is None:
        result['status'] = match_kind
        return result
    _assign_single_material(obj, material)
    result['status'] = 'assigned'
    result['assignedMaterial'] = (
        _authored_material_name(material)
        or _blender_material_name(material)
    )
    result['assignedBlenderMaterial'] = _blender_material_name(material)
=======
    obj,
    mat_name,
    *,
    material_resolver=None,
):
    result = {
        "status": "not_a_mesh",
        "matchKind": "",
        "expectedMaterial": wrapped_string(mat_name),
        "assignedMaterial": "",
        "assignedBlenderMaterial": "",
        "candidates": (),
    }
    if obj.type != "MESH" or not obj.data:
        return result
    resolver = (
        material_resolver
        if material_resolver is not None
        else _MaterialNameResolver(obj.data.materials)
    )
    material, match_kind, candidates = resolver.resolve(mat_name)
    result["matchKind"] = match_kind
    result["candidates"] = candidates
    if material is None:
        result["status"] = match_kind
        return result
    _assign_single_material(obj, material)
    result["status"] = "assigned"
    result["assignedMaterial"] = authored_material_name(
        material
    ) or _blender_material_name(material)
    result["assignedBlenderMaterial"] = _blender_material_name(material)
>>>>>>> Stashed changes
    return result


def _source_default_material_name(source_obj):
    try:
<<<<<<< Updated upstream
        value = source_obj.get('cp77_material_name')
    except (AttributeError, ReferenceError, TypeError):
=======
        value = source_obj.get("cp77_material_name")
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_source_default_material_name", type(error).__name__),
            "source default material name: fell back after %s",
            error,
            exc_info=True,
        )
>>>>>>> Stashed changes
        value = None
    return wrapped_string(value)


<<<<<<< Updated upstream
def _object_json_string_list(obj, key):
    try:
        raw = obj.get(key, '')
    except (AttributeError, ReferenceError, TypeError):
        raw = ''
    if not raw:
        return ()
    try:
        values = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ()
    if not isinstance(values, list):
        return ()
    result = []
    for value in values:
        name = wrapped_string(value)
        if name:
            result.append(name)
    return tuple(result)


def _prepared_material_names(source_obj):
    prepared = _object_json_string_list(source_obj, 'cp77_material_candidates')
    if prepared:
        return prepared
    return tuple(
        _authored_material_name(material) or _blender_material_name(material)
        for material in _unique_materials(
            getattr(getattr(source_obj, 'data', None), 'materials', ())
=======
def _prepared_material_names(source_obj):
    return tuple(
        authored_material_name(material) or _blender_material_name(material)
        for material in _unique_materials(
            getattr(getattr(source_obj, "data", None), "materials", ())
>>>>>>> Stashed changes
        )
    )


def _source_default_assignment(
<<<<<<< Updated upstream
        obj,
        source_obj,
        *,
        status,
        ):
=======
    obj,
    source_obj,
    *,
    status,
    material_resolver=None,
):
    resolver = (
        material_resolver
        if material_resolver is not None
        else _MaterialNameResolver(obj.data.materials)
    )
>>>>>>> Stashed changes
    expected = _source_default_material_name(source_obj)
    if expected:
        result = _keep_only_material(
            obj,
            expected,
<<<<<<< Updated upstream
        )
        if result['status'] == 'assigned':
            result['status'] = status
            result['matchKind'] = (
                'source_default_' + result.get('matchKind', '')
            )
            return result

    candidates = _unique_materials(obj.data.materials)
=======
            material_resolver=resolver,
        )
        if result["status"] == "assigned":
            result["status"] = status
            result["matchKind"] = "source_default_" + result.get("matchKind", "")
            return result

    candidates = resolver.materials
>>>>>>> Stashed changes
    if len(candidates) == 1:
        material = candidates[0]
        _assign_single_material(obj, material)
        return {
<<<<<<< Updated upstream
            'status': status,
            'matchKind': 'source_default_single_slot',
            'expectedMaterial': expected,
            'assignedMaterial': (
                _authored_material_name(material)
                or _blender_material_name(material)
            ),
            'assignedBlenderMaterial': _blender_material_name(material),
            'candidates': (),
        }

    return {
        'status': (
            'source_default_ambiguous'
            if candidates
            else 'source_default_missing'
        ),
        'matchKind': (
            'source_default_multiple_slots'
            if candidates
            else 'source_default_missing'
        ),
        'expectedMaterial': expected,
        'assignedMaterial': '',
        'assignedBlenderMaterial': '',
        'candidates': tuple(
            _authored_material_name(material)
            or _blender_material_name(material)
=======
            "status": status,
            "matchKind": "source_default_single_slot",
            "expectedMaterial": expected,
            "assignedMaterial": (
                authored_material_name(material) or _blender_material_name(material)
            ),
            "assignedBlenderMaterial": _blender_material_name(material),
            "candidates": (),
        }

    return {
        "status": (
            "source_default_ambiguous" if candidates else "source_default_missing"
        ),
        "matchKind": (
            "source_default_multiple_slots" if candidates else "source_default_missing"
        ),
        "expectedMaterial": expected,
        "assignedMaterial": "",
        "assignedBlenderMaterial": "",
        "candidates": tuple(
            authored_material_name(material) or _blender_material_name(material)
>>>>>>> Stashed changes
            for material in candidates
        ),
    }


<<<<<<< Updated upstream
def _record_object_material_assignment(
        obj,
        *,
        requested_appearance,
        resolved_appearance,
        submesh_index,
        result,
        ):
    obj['cp77_requested_appearance'] = requested_appearance
    obj['cp77_resolved_appearance'] = resolved_appearance
    obj['cp77_submesh_index'] = (
        int(submesh_index) if submesh_index is not None else -1
    )
    obj['cp77_expected_material'] = result.get('expectedMaterial', '')
    obj['cp77_assigned_material'] = result.get('assignedMaterial', '')
    obj['cp77_assigned_blender_material'] = result.get(
        'assignedBlenderMaterial',
        '',
    )
    obj['cp77_material_assignment_status'] = result.get('status', '')
    obj['cp77_material_match_source'] = result.get('matchKind', '')


def _copy_collection_objects(source_collection, target_collection, appearance, mesh_key, json_apps):
    copied_objects = []
    object_map = {}
    source_armatures = []
=======
def _copy_collection_objects(
    source_collection,
    target_collection,
    appearance,
    mesh_key,
    json_apps,
    *,
    source_objects=None,
    material_resolvers=None,
):
    copied_objects = []
    object_map = {}
>>>>>>> Stashed changes
    requested_appearance = wrapped_string(appearance)
    (
        resolved_appearance,
        appearance_materials,
        appearance_status,
    ) = resolve_appearance_materials(json_apps, requested_appearance)
<<<<<<< Updated upstream
    # Sidewalk meshes retain their imported materials.
    preserve_sidewalk_materials = (
        'sidewalk' in wrapped_string(mesh_key).casefold()
    )
    diagnostics = {
        'version': APPEARANCE_ASSIGNMENT_VERSION,
        'mesh': mesh_key,
        'requestedAppearance': requested_appearance,
        'resolvedAppearance': resolved_appearance,
        'appearanceResolution': appearance_status,
        'meshObjects': 0,
        'assigned': 0,
        'sourceDefaultAssigned': 0,
        'materialless': 0,
        'unresolvedAppearance': 0,
        'missingSubmeshIndex': 0,
        'missingSubmeshMapping': 0,
        'emptyMaterialMapping': 0,
        'missingMaterials': 0,
        'requestedMaterialNotPrepared': 0,
        'ambiguousMaterials': 0,
        'multipleSlots': 0,
        'sidewalkPreserved': 0,
        'issues': [],
        'objects': [],
    }
    # Reuse the master's rest armature across appearance variants.
    for source_obj in source_collection.all_objects:
        if getattr(source_obj, 'type', None) == 'ARMATURE':
            source_armatures.append(source_obj.name)
            continue
        obj = _copy_object_for_transaction(source_obj)
        object_map[source_obj] = obj
        copied_objects.append(obj)

        if obj.type == 'MESH':
            diagnostics['meshObjects'] += 1
            # Use authored submesh indices instead of collection order.
            submesh_index = submesh_index_for_object(source_obj)
            if preserve_sidewalk_materials:
                result = {
                    'status': 'sidewalk_materials_preserved',
                    'matchKind': 'policy',
                    'expectedMaterial': '',
                    'assignedMaterial': '',
                    'assignedBlenderMaterial': '',
                }
                diagnostics['sidewalkPreserved'] += 1
            elif not resolved_appearance:
                fallback_status = (
                    'source_default_assigned'
                    if is_source_default_appearance(requested_appearance)
                    else 'missing_appearance_source_default'
=======
    if appearance_status == "missing_appearance_default":
        _LOG.debug(
            "%s has no appearance %s; using its default appearance",
            mesh_key,
            requested_appearance,
        )
    # Sidewalk meshes retain their imported materials.
    preserve_sidewalk_materials = "sidewalk" in wrapped_string(mesh_key).casefold()
    diagnostics = {
        "version": APPEARANCE_ASSIGNMENT_VERSION,
        "mesh": mesh_key,
        "requestedAppearance": requested_appearance,
        "resolvedAppearance": resolved_appearance,
        "appearanceResolution": appearance_status,
        "meshObjects": 0,
        "assigned": 0,
        "sourceDefaultAssigned": 0,
        "materialless": 0,
        "unresolvedAppearance": 0,
        "missingSubmeshIndex": 0,
        "missingSubmeshMapping": 0,
        "emptyMaterialMapping": 0,
        "missingMaterials": 0,
        "requestedMaterialNotPrepared": 0,
        "ambiguousMaterials": 0,
        "multipleSlots": 0,
        "sidewalkPreserved": 0,
        "materiallessSource": 0,
        "issues": [],
    }
    if source_objects is None:
        source_objects = tuple(source_collection.all_objects)
    if material_resolvers is None:
        material_resolvers = {}
    # Reuse the master's rest armature across appearance variants.
    for source_obj in source_objects:
        if getattr(source_obj, "type", None) == "ARMATURE":
            continue
        share_mesh_data = getattr(source_obj, "type", None) == "MESH"
        obj = _copy_object_for_transaction(
            source_obj,
            copy_data=not share_mesh_data,
        )
        if share_mesh_data:
            obj["cp77_linked_variant_data"] = True
        object_map[source_obj] = obj
        copied_objects.append(obj)

        if obj.type == "MESH":
            resolver = None
            if not preserve_sidewalk_materials:
                resolver = material_resolvers.get(source_obj.data)
                if resolver is None:
                    resolver = _MaterialNameResolver(source_obj.data.materials)
                    material_resolvers[source_obj.data] = resolver
            diagnostics["meshObjects"] += 1
            # Use authored submesh indices instead of collection order.
            submesh_index = submesh_index_for_object(source_obj)
            prepared_names = None
            if preserve_sidewalk_materials:
                result = {
                    "status": "sidewalk_materials_preserved",
                    "matchKind": "policy",
                    "expectedMaterial": "",
                    "assignedMaterial": "",
                    "assignedBlenderMaterial": "",
                }
                diagnostics["sidewalkPreserved"] += 1
            elif not resolved_appearance:
                fallback_status = (
                    "source_default_assigned"
                    if is_source_default_appearance(requested_appearance)
                    else "missing_appearance_source_default"
>>>>>>> Stashed changes
                )
                result = _source_default_assignment(
                    obj,
                    source_obj,
                    status=fallback_status,
<<<<<<< Updated upstream
                )
                if result['status'] == fallback_status:
                    diagnostics['sourceDefaultAssigned'] += 1
                if appearance_status != 'source_default':
                    diagnostics['unresolvedAppearance'] += 1
=======
                    material_resolver=resolver,
                )
                if result["status"] == fallback_status:
                    diagnostics["sourceDefaultAssigned"] += 1
                if appearance_status != "source_default":
                    diagnostics["unresolvedAppearance"] += 1
>>>>>>> Stashed changes
            elif submesh_index is None:
                result = _source_default_assignment(
                    obj,
                    source_obj,
<<<<<<< Updated upstream
                    status='missing_submesh_index_source_default',
                )
                if result['status'] == 'missing_submesh_index_source_default':
                    diagnostics['sourceDefaultAssigned'] += 1
                diagnostics['missingSubmeshIndex'] += 1
=======
                    status="missing_submesh_index_source_default",
                    material_resolver=resolver,
                )
                if result["status"] == "missing_submesh_index_source_default":
                    diagnostics["sourceDefaultAssigned"] += 1
                diagnostics["missingSubmeshIndex"] += 1
>>>>>>> Stashed changes
            elif submesh_index >= len(appearance_materials):
                result = _source_default_assignment(
                    obj,
                    source_obj,
<<<<<<< Updated upstream
                    status='missing_submesh_mapping_source_default',
                )
                if (
                    result['status']
                    == 'missing_submesh_mapping_source_default'
                ):
                    diagnostics['sourceDefaultAssigned'] += 1
                diagnostics['missingSubmeshMapping'] += 1
            else:
                mat_name = wrapped_string(
                    appearance_materials[submesh_index]
                )
=======
                    status="missing_submesh_mapping_source_default",
                    material_resolver=resolver,
                )
                if result["status"] == "missing_submesh_mapping_source_default":
                    diagnostics["sourceDefaultAssigned"] += 1
                diagnostics["missingSubmeshMapping"] += 1
            else:
                mat_name = wrapped_string(appearance_materials[submesh_index])
>>>>>>> Stashed changes
                if not mat_name:
                    result = _source_default_assignment(
                        obj,
                        source_obj,
<<<<<<< Updated upstream
                        status='empty_material_mapping_source_default',
                    )
                    if (
                        result['status']
                        == 'empty_material_mapping_source_default'
                    ):
                        diagnostics['sourceDefaultAssigned'] += 1
                    diagnostics['emptyMaterialMapping'] += 1
=======
                        status="empty_material_mapping_source_default",
                        material_resolver=resolver,
                    )
                    if result["status"] == "empty_material_mapping_source_default":
                        diagnostics["sourceDefaultAssigned"] += 1
                    diagnostics["emptyMaterialMapping"] += 1
>>>>>>> Stashed changes
                else:
                    result = _keep_only_material(
                        obj,
                        mat_name,
<<<<<<< Updated upstream
                    )
                    if result['status'] == 'assigned':
                        diagnostics['assigned'] += 1
                    else:
                        prepared_names = _prepared_material_names(source_obj)
                        prepared_match, _, _ = _resolve_matching_material(
                            getattr(source_obj.data, 'materials', ()),
                            mat_name,
                        )
                        if prepared_match is None:
                            diagnostics['requestedMaterialNotPrepared'] += 1
                        if 'ambiguous_' in result['status']:
                            diagnostics['ambiguousMaterials'] += 1
                        else:
                            diagnostics['missingMaterials'] += 1
                        _clear_material_assignment(obj)
                        result['preparedMaterials'] = prepared_names

            result.setdefault(
                'preparedMaterials',
                _prepared_material_names(source_obj),
            )
            _record_object_material_assignment(
                obj,
                requested_appearance=requested_appearance,
                resolved_appearance=resolved_appearance,
                submesh_index=submesh_index,
                result=result,
            )
            if len(obj.data.materials) > 1:
                diagnostics['multipleSlots'] += 1
            if len(obj.data.materials) == 0:
                diagnostics['materialless'] += 1
            diagnostics['objects'].append({
                'object': obj.name,
                'submeshIndex': (
                    int(submesh_index)
                    if submesh_index is not None
                    else -1
                ),
                'status': result['status'],
                'matchKind': result.get('matchKind', ''),
                'expectedMaterial': result.get('expectedMaterial', ''),
                'assignedMaterial': result.get('assignedMaterial', ''),
                'assignedBlenderMaterial': result.get(
                    'assignedBlenderMaterial',
                    '',
                ),
                'preparedMaterials': list(
                    result.get('preparedMaterials', ())
                ),
                'materialSlots': len(obj.data.materials),
            })
            if result['status'] not in {
                    'assigned',
                    'source_default_assigned',
                    'sidewalk_materials_preserved',
                    }:
                diagnostics['issues'].append({
                    'object': obj.name,
                    'submeshIndex': (
                        int(submesh_index)
                        if submesh_index is not None
                        else -1
                    ),
                    'status': result['status'],
                    'expectedMaterial': result.get(
                        'expectedMaterial',
                        '',
                    ),
                    'candidates': list(result.get('candidates', ())),
                    'preparedMaterials': list(
                        result.get('preparedMaterials', ())
                    ),
                })

        target_collection.objects.link(obj)

    _remap_copied_object_references(copied_objects, object_map)
    if source_armatures:
        target_collection['cp77_source_armatures'] = json.dumps(source_armatures)
        target_collection['cp77_source_armature_policy'] = 'master_reference'
    target_collection['cp77_material_assignment_version'] = (
        APPEARANCE_ASSIGNMENT_VERSION
    )
    target_collection['cp77_requested_appearance'] = requested_appearance
    target_collection['cp77_resolved_appearance'] = resolved_appearance
    target_collection['cp77_appearance_resolution'] = appearance_status
    collection_diagnostics = dict(diagnostics)
    collection_diagnostics.pop('objects', None)
    target_collection['cp77_material_assignment_summary'] = json.dumps(
        collection_diagnostics,
        separators=(',', ':'),
    )
    issue_count = len(diagnostics['issues'])
    if issue_count:
        print(
            f'Appearance assignment warning for '
            f'{mesh_key}@{requested_appearance}: {issue_count} unresolved '
            f'submesh material mapping(s).'
        )
    return diagnostics


def _ensure_appearance_variants(Masters, master_coll, mesh_key, source_key, apps, json_apps):
    for app in apps:
        variant_name = (master_coll.name + '@' + app)[:NAME_MAX_LEN] if app else master_coll.name
        existing = Masters.children.get(variant_name)
        if existing is not None and _collection_matches_source(existing, source_key):
            continue
        if existing is not None:
=======
                        material_resolver=resolver,
                    )
                    if result["status"] == "assigned":
                        diagnostics["assigned"] += 1
                    else:
                        prepared_names = _prepared_material_names(source_obj)
                        prepared_match, _, _ = resolver.resolve(mat_name)
                        if prepared_match is None:
                            diagnostics["requestedMaterialNotPrepared"] += 1
                        if "ambiguous_" in result["status"]:
                            diagnostics["ambiguousMaterials"] += 1
                        else:
                            diagnostics["missingMaterials"] += 1
                        _clear_material_assignment(obj)
                        result["preparedMaterials"] = prepared_names

            if prepared_names is not None:
                result["preparedMaterials"] = prepared_names
            assigned_slot_count = _assigned_material_slot_count(obj)
            if assigned_slot_count > 1:
                diagnostics["multipleSlots"] += 1
            if assigned_slot_count == 0:
                diagnostics["materialless"] += 1
            if resolver is not None and not resolver.materials:
                # Imported without materials: there is nothing to map, and the material import reports its own
                # failures.
                diagnostics["materiallessSource"] += 1
            elif result["status"] not in {
                "assigned",
                "source_default_assigned",
                "sidewalk_materials_preserved",
            }:
                diagnostics["issues"].append(
                    {
                        "object": obj.name,
                        "submeshIndex": (
                            int(submesh_index) if submesh_index is not None else -1
                        ),
                        "status": result["status"],
                        "expectedMaterial": result.get(
                            "expectedMaterial",
                            "",
                        ),
                        "candidates": list(result.get("candidates", ())),
                        "preparedMaterials": list(
                            result.get("preparedMaterials")
                            or _prepared_material_names(source_obj)
                        ),
                    }
                )

        target_collection.objects.link(obj)

    remap_copied_object_references(copied_objects, object_map)
    issue_count = len(diagnostics["issues"])
    if issue_count:
        (_LOG.debug if is_physical_scene(mesh_key) else _LOG.warning)(
            "Appearance assignment warning for %s@%s: %s unresolved submesh "
            "material mapping(s); first reason: %s. Details at DEBUG level.",
            mesh_key,
            requested_appearance,
            issue_count,
            diagnostics["issues"][0]["status"],
        )
        if is_enabled("DEBUG", _LOG):
            for issue in diagnostics["issues"]:
                candidates = issue["candidates"]
                prepared = issue["preparedMaterials"]
                _LOG.debug(
                    "Appearance mapping %s@%s: object=%s, submesh=%s, "
                    "status=%s, expected=%r; candidates=%r (%d total), "
                    "prepared=%r (%d total); lists limited to 8 names/256 characters each",
                    mesh_key,
                    requested_appearance,
                    issue["object"],
                    issue["submeshIndex"],
                    issue["status"],
                    str(issue["expectedMaterial"])[:256],
                    tuple(str(name)[:256] for name in candidates[:8]),
                    len(candidates),
                    tuple(str(name)[:256] for name in prepared[:8]),
                    len(prepared),
                )
    return diagnostics


def ensure_appearance_variants(
    Masters, master_coll, mesh_key, source_key, apps, json_apps, *, timing=None
):
    """Create the appearance variants of master_coll that do not exist yet"""
    source_objects = None
    material_resolvers = {}
    variants = {}
    for app in apps:
        variant_name = (
            fit_id_name(master_coll.name + "@" + app) if app else master_coll.name
        )
        existing = Masters.children.get(variant_name)
        if existing is not None:
            if _collection_matches_source(existing, source_key):
                variants[app] = existing
            else:
                _LOG.warning(
                    "Appearance variant %s already belongs to another mesh; it was not rebuilt",
                    variant_name,
                )
>>>>>>> Stashed changes
            continue
        new_coll = track_created_datablock(
            "collections", bpy.data.collections.new(variant_name)
        )
<<<<<<< Updated upstream
        new_coll['meshpath'] = mesh_key
        new_coll['appearance'] = app
        new_coll['source_glb'] = source_key
        _link_collection_once(Masters, new_coll)
        _copy_collection_objects(master_coll, new_coll, app, mesh_key, json_apps)
=======
        new_coll["meshPath"] = mesh_key
        new_coll["appearance"] = app
        new_coll["sourcePath"] = source_key
        link_collection_once(Masters, new_coll)
        if source_objects is None:
            source_objects = tuple(master_coll.all_objects)
        _copy_collection_objects(
            master_coll,
            new_coll,
            app,
            mesh_key,
            json_apps,
            source_objects=source_objects,
            material_resolvers=material_resolvers,
        )
        variants[app] = new_coll
    if timing is not None:
        timing["variant_material_tables"] = timing.get(
            "variant_material_tables", 0
        ) + len(material_resolvers)
        timing["variant_material_lookups"] = timing.get(
            "variant_material_lookups", 0
        ) + sum(resolver.calls for resolver in material_resolvers.values())
    return variants
>>>>>>> Stashed changes


def _mesh_appearances(mesh_data):
    apps = []
    seen = set()
<<<<<<< Updated upstream
    for mesh_app in mesh_data.get('apps', [[]])[0]:
=======
    for mesh_app in mesh_data.get("apps", [[]])[0]:
>>>>>>> Stashed changes
        appearance = _appearance_name(mesh_app)
        if appearance and appearance not in seen:
            seen.add(appearance)
            apps.append(appearance)
    return apps


def _resolved_meshpath(mesh_data):
    if isinstance(mesh_data, dict):
<<<<<<< Updated upstream
        meshpath = mesh_data.get('meshpath')
        if meshpath:
            return os.path.normpath(meshpath)
    return ''


def _mesh_glb_path(mesh_repository, mesh_key, mesh_data):
    """Resolve an explicit export or depot mesh reference through the active asset index."""
=======
        meshpath = mesh_data.get("meshpath")
        if meshpath:
            return os.path.normpath(meshpath)
    return ""


def _mesh_glb_path(mesh_repository, mesh_key, mesh_data):
    """Resolve an explicit export or depot mesh reference through the active asset index"""
>>>>>>> Stashed changes
    meshpath = _resolved_meshpath(mesh_data)
    if meshpath:
        asset = mesh_repository.resolve(meshpath)
        if asset is not None:
            return asset.local_path
    asset = mesh_repository.resolve(mesh_key)
    return asset.local_path if asset is not None else ""


def _appearance_requests_by_source(prepared_meshes):
    appearances_by_source = {}
    seen_by_source = {}
    for _mesh_key, mesh_data, _meshpath, source_key in prepared_meshes:
        source_apps = appearances_by_source.setdefault(source_key, [])
        seen = seen_by_source.setdefault(source_key, set())
        for appearance in _mesh_appearances(mesh_data):
            if appearance in seen:
                continue
            seen.add(appearance)
            source_apps.append(appearance)
    return appearances_by_source


<<<<<<< Updated upstream
def meshes_from_mesheswapps(
        meshes_w_apps, *, asset_index, from_mesh_no=0, to_mesh_no=10000000,
        with_mats=False, Masters=None, generate_overrides=False, mesh_repository=None,
        document_session=None, material_resources=None, transaction=None,
        ):
    if asset_index is None:
        raise ValueError('meshes_from_mesheswapps requires an AssetIndexSnapshot')
    if Masters is None:
        raise ValueError('meshes_from_mesheswapps requires a master collection')
=======
class _MeshDecodePrefetcher:
    def __init__(self, items):
        self._source_items = tuple(items)
        self._items = iter(self._source_items)
        self._synchronous = len(self._source_items) < 8
        cpu_count = os.cpu_count() or 2
        self._workers = max(1, min(6, cpu_count - 1 if cpu_count > 2 else 2))
        self._window = self._workers * 2
        self._executor = None
        self._pending = deque()

    @staticmethod
    def _decode(item):
        source_key, meshpath = item
        started = time.perf_counter()
        mesh_data = decode_mesh_glb(
            meshpath,
            restore_red_uvs=True,
            build_binding=True,
            import_garment_support=False,
        )
        return source_key, mesh_data, time.perf_counter() - started

    def start(self):
        if self._synchronous:
            return self
        self._executor = ThreadPoolExecutor(
            max_workers=self._workers,
            thread_name_prefix="cp77-glb-decode",
        )
        self._fill()
        return self

    def _fill(self):
        if self._executor is None:
            return
        while len(self._pending) < self._window:
            try:
                item = next(self._items)
            except StopIteration:
                break
            self._pending.append((item[0], self._executor.submit(self._decode, item)))

    def result(self, source_key):
        if self._synchronous:
            try:
                item = next(self._items)
            except StopIteration as error:
                raise RuntimeError(
                    f"No decoded GLB data remains for {source_key}"
                ) from error
            if item[0] != source_key:
                raise RuntimeError(
                    f"GLB decode order mismatch: expected {source_key}, got {item[0]}"
                )
            decoded_key, mesh_data, decode_elapsed = self._decode(item)
            return mesh_data, decode_elapsed, decode_elapsed
        if not self._pending:
            raise RuntimeError(f"No prefetched GLB data remains for {source_key}")
        queued_key, future = self._pending.popleft()
        if queued_key != source_key:
            raise RuntimeError(
                f"GLB prefetch order mismatch: expected {source_key}, got {queued_key}"
            )
        wait_started = time.perf_counter()
        try:
            decoded_key, mesh_data, decode_elapsed = future.result()
        finally:
            self._fill()
        wait_elapsed = time.perf_counter() - wait_started
        if decoded_key != source_key:
            raise RuntimeError(
                f"GLB prefetch result mismatch: expected {source_key}, got {decoded_key}"
            )
        return mesh_data, wait_elapsed, decode_elapsed

    def close(self):
        executor = self._executor
        self._executor = None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)
        self._pending.clear()


def _missing_decode_items(unique_prepared_meshes, masters, base_index):
    items = []
    for _mesh_key, _mesh_data, meshpath, source_key in unique_prepared_meshes:
        existing_master, _groupname = _find_base_master(
            masters,
            meshpath,
            source_key,
            base_index,
        )
        if existing_master is None:
            items.append((source_key, meshpath))
    return tuple(items)


def _log_material_profile_details(profile):
    details = material_profile_details(profile)
    for section, label in (
        ("handlers", "handler"),
        ("templates", "template"),
    ):
        rows = sorted(
            details.get(section, {}).items(),
            key=lambda item: float(item[1].get("seconds", 0.0)),
            reverse=True,
        )
        for name, values in rows:
            _LOG.debug(
                "Material %s aggregate: name=%s total=%.3fs/%d, "
                "body=%.3fs, organization=%.3fs, residual=%.3fs, "
                "nodes=%.3fs/%d, links=%.3fs/%d, images=%.3fs, "
                "cold_groups=%.3fs/%d",
                label,
                name,
                float(values.get("seconds", 0.0)),
                int(values.get("count", 0)),
                float(values.get("body_seconds", 0.0)),
                float(values.get("organization_seconds", 0.0)),
                float(values.get("residual_seconds", 0.0)),
                float(values.get("node_seconds", 0.0)),
                int(values.get("nodes_added", 0)),
                float(values.get("link_seconds", 0.0)),
                int(values.get("links_added", 0)),
                float(values.get("image_seconds", 0.0)),
                float(values.get("node_group_seconds", 0.0)),
                int(values.get("node_groups_added", 0)),
            )
    node_groups = sorted(
        details.get("node_groups", {}).items(),
        key=lambda item: float(item[1].get("seconds", 0.0)),
        reverse=True,
    )
    for name, values in node_groups:
        _LOG.debug(
            "Material node-group cold build: name=%s total=%.3fs/%d, maximum=%.3fs",
            name,
            float(values.get("seconds", 0.0)),
            int(values.get("count", 0)),
            float(values.get("maximum", 0.0)),
        )
    slowest = details.get("slowest_builds", ())
    for index, build in enumerate(slowest, start=1):
        _LOG.debug(
            "Slow material build %d/%d: material=%s, template=%s, "
            "handler=%s, total=%.3fs, body=%.3fs, organization=%.3fs, "
            "residual=%.3fs, nodes=%.3fs/%d, links=%.3fs/%d, "
            "images=%.3fs, cold_groups=%.3fs/%d, status=%s",
            index,
            len(slowest),
            build.get("material", ""),
            build.get("template", ""),
            build.get("handler", ""),
            float(build.get("seconds", 0.0)),
            float(build.get("body_seconds", 0.0)),
            float(build.get("organization_seconds", 0.0)),
            float(build.get("residual_seconds", 0.0)),
            float(build.get("node_seconds", 0.0)),
            int(build.get("nodes_added", 0)),
            float(build.get("link_seconds", 0.0)),
            int(build.get("links_added", 0)),
            float(build.get("image_seconds", 0.0)),
            float(build.get("node_group_seconds", 0.0)),
            int(build.get("node_groups_added", 0)),
            "ok" if build.get("succeeded", False) else "failed",
        )


def _log_bulk_debug_timings(timings, material_profile):
    _LOG.debug(
        "Bulk mesh debug timing: glb_decode=%.3fs aggregate worker, "
        "decode_wait=%.3fs, mesh_datablocks=%.3fs, material_json_prefetch=%.3fs, "
        "material_json=%.3fs, material_plan=%.3fs, material_prefetch=%.3fs, "
        "material_setup=%.3fs (build=%.3fs, assignment=%.3fs; "
        "prefetched=%d material-json/%d setup/%d template/%d mask-image, %.2f MiB)",
        timings.get("glb_decode", 0.0),
        timings.get("decode_wait", 0.0),
        timings.get("mesh_datablocks", 0.0),
        timings.get("material_json_prefetch", 0.0),
        timings.get("material_json", 0.0),
        timings.get("material_plan", 0.0),
        timings.get("material_prefetch", 0.0),
        timings.get("material_setup", 0.0),
        timings.get("material_build", 0.0),
        timings.get("material_assignment", 0.0),
        int(timings.get("material_json_prefetch_documents", 0)),
        int(timings.get("material_prefetch_setup_documents", 0)),
        int(timings.get("material_prefetch_template_documents", 0)),
        int(timings.get("material_prefetch_mask_files", 0)),
        (
            float(timings.get("material_json_prefetch_bytes", 0))
            + float(timings.get("material_prefetch_bytes", 0))
            + float(timings.get("material_prefetch_mask_bytes", 0))
        )
        / (1024.0 * 1024.0),
    )
    if timings.get("variant_material_tables"):
        _LOG.debug(
            "Appearance material lookup: %d source table(s), %d indexed resolution(s)",
            timings["variant_material_tables"],
            timings.get("variant_material_lookups", 0),
        )
    if not material_profile:
        return
    signature = material_profile_phase(material_profile, "material.signature")
    cache_lookup = material_profile_phase(material_profile, "material.cache_lookup")
    registry = material_profile_phase(material_profile, "material.registry_lookup")
    factory = material_profile_phase(material_profile, "material.factory")
    handler = material_profile_phase(material_profile, "material.handler_create")
    handler_body = material_profile_phase(material_profile, "material.handler_body")
    organization = material_profile_phase(
        material_profile,
        "material.graph_organization",
    )
    nodes = material_profile_phase(material_profile, "material.node_create")
    links = material_profile_phase(material_profile, "material.link_create")
    node_groups = material_profile_phase(
        material_profile,
        "material.node_group_cold_build",
    )
    image_lookup = material_profile_phase(material_profile, "material.image_lookup")
    image_resolve = material_profile_phase(material_profile, "material.image_resolve")
    image_load = material_profile_phase(material_profile, "material.image_create")
    datablock = material_profile_phase(material_profile, "material.datablock_create")
    clone = material_profile_phase(material_profile, "material.datablock_clone")
    _LOG.debug(
        "Bulk material debug timing: signatures=%.3fs/%d, "
        "cache_lookup=%.3fs/%d, shader_routing=%.3fs/%d, "
        "handler_graph=%.3fs/%d (body=%.3fs, organization=%.3fs, "
        "residual=%.3fs), node_create=%.3fs/%d, "
        "link_create=%.3fs/%d, "
        "node_group_cold=%.3fs/%d, "
        "image_lookup=%.3fs/%d, image_resolve=%.3fs/%d, "
        "image_load=%.3fs/%d, datablock_create=%.3fs/%d, "
        "datablock_clone=%.3fs/%d; maxima handler=%.3fs, "
        "image_load=%.3fs",
        signature[0],
        signature[1],
        cache_lookup[0],
        cache_lookup[1],
        registry[0] + factory[0],
        registry[1] + factory[1],
        handler[0],
        handler[1],
        handler_body[0],
        organization[0],
        material_profile_total(
            material_profile_details(material_profile),
            "residual_seconds",
        ),
        nodes[0],
        nodes[1],
        links[0],
        links[1],
        node_groups[0],
        node_groups[1],
        image_lookup[0],
        image_lookup[1],
        image_resolve[0],
        image_resolve[1],
        image_load[0],
        image_load[1],
        datablock[0],
        datablock[1],
        clone[0],
        clone[1],
        handler[2],
        image_load[2],
    )
    _log_material_profile_details(material_profile)


def _material_timing_delta_rows(before, after):
    body_rows = []
    organization_rows = []
    for name, after_values in after.items():
        before_values = before.get(name, {})
        body_seconds = max(
            0.0,
            float(after_values.get("seconds", 0.0))
            - float(before_values.get("seconds", 0.0)),
        )
        body_count = max(
            0,
            int(after_values.get("count", 0)) - int(before_values.get("count", 0)),
        )
        organization_seconds = max(
            0.0,
            float(after_values.get("organization_seconds", 0.0))
            - float(before_values.get("organization_seconds", 0.0)),
        )
        organization_count = max(
            0,
            int(after_values.get("organization_count", 0))
            - int(before_values.get("organization_count", 0)),
        )
        if body_count:
            body_rows.append((body_seconds, body_count, name))
        if organization_count:
            organization_rows.append((organization_seconds, organization_count, name))
    body_rows.sort(reverse=True)
    organization_rows.sort(reverse=True)
    return body_rows, organization_rows


def _format_material_timing_rows(rows, limit=8):
    return "; ".join(
        f"{name}={seconds:.3f}s/{count}" for seconds, count, name in rows[:limit]
    )


@override_palette_batched
def _reuse_master(
    existing_master,
    mesh_key,
    meshpath,
    source_key,
    apps,
    masters,
    *,
    with_mats,
    remap_depot,
    document_session,
    material_resources,
    failures,
    timing,
):
    """Bring an existing master up to date"""
    if with_mats:
        with bulk_material_import_scope(True):
            coverage = ensure_collection_material_coverage(
                existing_master,
                meshpath,
                apps,
                remap_depot=remap_depot,
                document_session=document_session,
                material_resources=material_resources,
                timing=timing,
            )
        coverage_warnings = coverage.get("warnings", ())
        failures.extend(
            warning for warning in coverage_warnings if warning not in failures
        )
        failed_materials = coverage.get("failures", ())
        if failed_materials:
            failures.append(
                f"Material setup failed for {mesh_key}: {', '.join(failed_materials)}"
            )
        unprepared_materials = coverage.get("unprepared", ())
        if unprepared_materials:
            failures.append(
                "Submesh materials were not prepared for "
                f"{mesh_key}: "
                + ", ".join(f"{index}:{name}" for index, name in unprepared_materials)
            )
    json_apps = _json_apps_for_collection(existing_master, mesh_key)
    variant_started = time.perf_counter()
    ensure_appearance_variants(
        masters,
        existing_master,
        mesh_key,
        source_key,
        apps,
        json_apps,
        timing=timing,
    )
    timing["reuse_variants"] = (
        timing.get("reuse_variants", 0.0) + time.perf_counter() - variant_started
    )


def meshes_from_mesheswapps(
    meshes_w_apps,
    *,
    asset_index,
    from_mesh_no=0,
    to_mesh_no=10000000,
    with_mats=False,
    Masters=None,
    mesh_repository=None,
    document_session=None,
    material_resources=None,
    transaction=None,
    progress=None,
):
    if asset_index is None:
        raise ValueError("meshes_from_mesheswapps requires an AssetIndexSnapshot")
    if Masters is None:
        raise ValueError("meshes_from_mesheswapps requires a master collection")
>>>>>>> Stashed changes
    mesh_repository = mesh_repository or MeshRepository(asset_index)
    transaction = transaction or current_import_transaction()
    failures = []
    prepared_meshes = []
<<<<<<< Updated upstream
    imported_source_count = 0
    bulk_started = time.perf_counter()
    cache_before = material_cache_counters() if with_mats else None

    material_cache_acquired = acquire_material_cache(with_mats)
    try:
        props = bpy.context.scene.cp77_panel_props
        context = bpy.context
        scene_collection = context.scene.collection
=======
    unique_prepared_meshes = ()
    imported_source_count = 0
    reused_source_count = 0
    resolve_elapsed = 0.0
    reuse_elapsed = 0.0
    import_elapsed = 0.0
    import_cpu_elapsed = 0.0
    variant_elapsed = 0.0
    decode_wait_elapsed = 0.0
    decode_prefetcher = None
    debug_timings = {}
    armature_preparation = _MasterArmaturePreparation(Masters)
    base_index = _base_master_index(Masters)
    material_profile = {}
    material_profile_session = None
    bulk_started = time.perf_counter()
    resolve_started = bulk_started
    diagnostics_enabled = with_mats and is_enabled("DEBUG", _LOG)
    cache_before = material_cache_counters() if diagnostics_enabled else None
    handler_timing_before = (
        material_handler_timing_stats() if diagnostics_enabled else {}
    )
    template_timing_before = (
        material_template_timing_stats() if diagnostics_enabled else {}
    )
    organization_phase_before = (
        material_organization_phase_timing_stats() if diagnostics_enabled else {}
    )
    helper_before = (
        material_cache_stats(include_helpers=True) if diagnostics_enabled else None
    )

    material_cache_acquired = acquire_material_cache(with_mats)
    material_profile_session = start_material_profiling(
        diagnostics_enabled and detailed_material_profiling_requested()
    )
    try:
        props = bpy.context.scene.cp77_panel_props
>>>>>>> Stashed changes

        for index, (mesh_key, mesh_data) in enumerate(meshes_w_apps.items()):
            if index < from_mesh_no or index > to_mesh_no:
                continue
<<<<<<< Updated upstream
            if not str(mesh_key).casefold().endswith(
                MESH_COOKED_NAME_SUFFIXES
            ):
=======
            if not str(mesh_key).casefold().endswith(MESH_COOKED_NAME_SUFFIXES):
>>>>>>> Stashed changes
                continue

            meshpath = _mesh_glb_path(mesh_repository, mesh_key, mesh_data)
            if not meshpath:
<<<<<<< Updated upstream
                message = f'Mesh export not indexed: {mesh_key}'
                print(message)
=======
                message = f"Mesh export not indexed: {mesh_key}"
>>>>>>> Stashed changes
                failures.append(message)
                continue

            source_key = _asset_source_key(meshpath)
<<<<<<< Updated upstream
            prepared_meshes.append(
                (mesh_key, mesh_data, meshpath, source_key)
            )

        appearances_by_source = _appearance_requests_by_source(
            prepared_meshes
        )

        for mesh_key, mesh_data, meshpath, source_key in prepared_meshes:
            # Merge appearances that resolve to the same GLB.
            apps = appearances_by_source[source_key]
            groupname = get_groupname(meshpath, '')
            existing_master = Masters.children.get(groupname)
            if existing_master is not None and not _collection_matches_source(existing_master, source_key):
                # Use a source hash when another asset owns the display name.
                groupname = _hashed_groupname(meshpath, '', source_key)
                existing_master = Masters.children.get(groupname)
                if existing_master is not None and not _collection_matches_source(existing_master, source_key):
                    existing_master = None
            if existing_master is not None:
                # Add missing materials before creating appearance variants.
                if with_mats:
                    coverage = ensure_collection_material_coverage(
                        existing_master,
                        meshpath,
                        apps,
                        remap_depot=props.remap_depot,
                        document_session=document_session,
                        material_resources=material_resources,
                    )
                    failed_materials = coverage.get("failures", ())
                    if failed_materials:
                        failures.append(
                            "Material setup failed for "
                            f"{mesh_key}: {', '.join(failed_materials)}"
                        )
                    unprepared_materials = coverage.get("unprepared", ())
                    if unprepared_materials:
                        failures.append(
                            "Submesh materials were not prepared for "
                            f"{mesh_key}: "
                            + ", ".join(
                                f"{index}:{name}"
                                for index, name in unprepared_materials
                            )
                        )
                json_apps = _json_apps_for_collection(existing_master, mesh_key)
                _ensure_appearance_variants(
                    Masters,
                    existing_master,
                    mesh_key,
                    source_key,
                    apps,
                    json_apps,
                )
                continue
            try:
                imported_results = import_cyberpunk_glb(
                        with_materials=with_mats,
                        remap_depot=props.remap_depot,
                        filepath=meshpath,
                        appearances=apps,
                        scripting=True,
                        generate_overrides=generate_overrides,
                        document_session=document_session,
                        material_resources=material_resources,
                        transaction=transaction,
                        bulk_import=True,
                        )
=======
            prepared_meshes.append((mesh_key, mesh_data, meshpath, source_key))

        appearances_by_source = _appearance_requests_by_source(prepared_meshes)
        unique_by_source = {}
        for prepared in prepared_meshes:
            unique_by_source.setdefault(prepared[3], prepared)
        unique_prepared_meshes = tuple(unique_by_source.values())
        unique_mesh_count = len(unique_prepared_meshes)
        if progress is not None:
            progress.set(
                0.0,
                f"Preparing mesh masters 0 / {unique_mesh_count:,}",
                force=True,
            )
        resolve_elapsed = time.perf_counter() - resolve_started
        prefetch_documents = document_session or getattr(
            material_resources, "documents", None
        )
        material_json_paths = (
            tuple(
                material_sidecar_path(prepared[2])
                for prepared in unique_prepared_meshes
            )
            if with_mats and prefetch_documents is not None
            else ()
        )

        def prefetch_material_json_window(start_index):
            if not material_json_paths:
                return
            window = material_json_paths[
                start_index : start_index + _MATERIAL_JSON_PREFETCH_WINDOW
            ]
            if not window:
                return
            prefetch_started = time.perf_counter()
            prefetch_stats = prefetch_documents.prefetch(
                window,
                expected_kind=ResourceKind.MATERIAL,
                max_workers=_MATERIAL_JSON_PREFETCH_WORKERS,
            )
            debug_timings["material_json_prefetch"] = debug_timings.get(
                "material_json_prefetch", 0.0
            ) + max(0.0, time.perf_counter() - prefetch_started)
            debug_timings["material_json_prefetch_documents"] = debug_timings.get(
                "material_json_prefetch_documents", 0
            ) + prefetch_stats.get("prefetched", 0)
            debug_timings["material_json_prefetch_bytes"] = debug_timings.get(
                "material_json_prefetch_bytes", 0
            ) + prefetch_stats.get("bytes", 0)

        decode_prefetcher = _MeshDecodePrefetcher(
            _missing_decode_items(unique_prepared_meshes, Masters, base_index)
        ).start()
        prefetch_material_json_window(0)

        for unique_index, (mesh_key, mesh_data, meshpath, source_key) in enumerate(
            unique_prepared_meshes
        ):
            if progress is not None:
                progress.set(
                    100.0 * unique_index / max(1, unique_mesh_count),
                    f"Preparing mesh masters {unique_index + 1:,} / {unique_mesh_count:,} — {os.path.basename(meshpath)}",
                )
            if unique_index and unique_index % _MATERIAL_JSON_PREFETCH_WINDOW == 0:
                prefetch_material_json_window(unique_index)
            # Merge appearances that resolve to the same GLB.
            apps = appearances_by_source[source_key]
            mesh_state = (
                (transaction, transaction.savepoint())
                if transaction is not None
                else (None, None)
            )
            existing_master, groupname = _find_base_master(
                Masters,
                meshpath,
                source_key,
                base_index,
            )
            if existing_master is not None:
                reused_source_count += 1
                reuse_started = time.perf_counter()
                try:
                    _reuse_master(
                        existing_master,
                        mesh_key,
                        meshpath,
                        source_key,
                        apps,
                        Masters,
                        with_mats=with_mats,
                        remap_depot=props.remap_depot,
                        document_session=document_session,
                        material_resources=material_resources,
                        failures=failures,
                        timing=debug_timings,
                    )
                except Exception as error:
                    _LOG.warning(
                        "Mesh master reuse failed: %s: %s: %s",
                        os.path.basename(meshpath),
                        type(error).__name__,
                        error,
                        exc_info=True,
                    )
                    _rollback_failed_master(
                        mesh_state,
                        mesh_key,
                        source_key,
                        base_index,
                        armature_preparation,
                    )
                    failures.append(
                        f"Mesh master update failed for {mesh_key}: {type(error).__name__}: {error}"
                    )
                reused_variants = debug_timings.pop("reuse_variants", 0.0)
                reuse_elapsed += time.perf_counter() - reuse_started - reused_variants
                variant_elapsed += reused_variants
                continue
            import_started = None
            import_cpu_started = None
            try:
                (
                    decoded_mesh_data,
                    decode_wait,
                    decode_elapsed,
                ) = decode_prefetcher.result(source_key)
                decode_wait_elapsed += decode_wait
                debug_timings["glb_decode"] = (
                    debug_timings.get("glb_decode", 0.0) + decode_elapsed
                )
                debug_timings["decode_wait"] = (
                    debug_timings.get("decode_wait", 0.0) + decode_wait
                )
                import_started = time.perf_counter()
                import_cpu_started = time.process_time()
                imported_results = import_cyberpunk_glb(
                    with_materials=with_mats,
                    remap_depot=props.remap_depot,
                    filepath=meshpath,
                    appearances=apps,
                    document_session=document_session,
                    material_resources=material_resources,
                    transaction=transaction,
                    bulk_import=True,
                    collection_parent=Masters,
                    collection_name=groupname,
                    select_objects=False,
                    decoded_mesh_data=decoded_mesh_data,
                    timing=debug_timings,
                    appearance_variants=False,
                )
                import_elapsed += time.perf_counter() - import_started
                import_cpu_elapsed += time.process_time() - import_cpu_started
                import_started = None
                import_cpu_started = None
>>>>>>> Stashed changes
                imported_source_count += 1
                if not imported_results.ok:
                    failures.extend(
                        f"{mesh_key}: {message}"
                        for message in imported_results.failures
                    )
<<<<<<< Updated upstream
                    continue
                failures.extend(
                    f"{mesh_key}: {message}"
                    for message in imported_results.warnings
                )

                move_coll = (
                    imported_results[0].get('collection')
=======
                    _rollback_failed_master(
                        mesh_state,
                        mesh_key,
                        source_key,
                        base_index,
                        armature_preparation,
                    )
                    continue
                failures.extend(
                    f"{mesh_key}: {message}" for message in imported_results.warnings
                )

                move_coll = (
                    imported_results[0].get("collection")
>>>>>>> Stashed changes
                    if len(imported_results) == 1
                    else None
                )
                if move_coll is None:
<<<<<<< Updated upstream
                    message = (
                        f'Import produced no collection for: {mesh_key}'
                    )
                    print(message)
                    failures.append(message)
=======
                    message = f"Import produced no collection for: {mesh_key}"
                    _LOG.warning("%s", message)
                    failures.append(message)
                    _rollback_failed_master(
                        mesh_state,
                        mesh_key,
                        source_key,
                        base_index,
                        armature_preparation,
                    )
>>>>>>> Stashed changes
                    continue

                if move_coll.name != groupname:
                    move_coll.name = groupname
<<<<<<< Updated upstream
                move_coll['meshpath'] = mesh_key
                move_coll['appearance'] = 'default'
                move_coll['source_glb'] = source_key
                _unlink_collection_once(scene_collection, move_coll)
                _link_collection_once(Masters, move_coll)
                authoritative_armatures = _deduplicate_master_source_armatures(
                    move_coll,
                    Masters,
                )
                source_armatures = []
                for obj in authoritative_armatures:
                    obj['cp77_master_source_armature'] = True
                    if not obj.get('cp77_master_source_glb'):
                        obj['cp77_master_source_glb'] = source_key
                    sources = []
                    raw_sources = obj.get('cp77_master_source_glbs', '')
                    if raw_sources:
                        try:
                            sources = list(json.loads(raw_sources))
                        except (TypeError, ValueError, json.JSONDecodeError):
                            sources = []
                    if source_key and source_key not in sources:
                        sources.append(source_key)
                    obj['cp77_master_source_glbs'] = json.dumps(sources)
                    source_armatures.append(obj.name)
                if source_armatures:
                    move_coll['cp77_source_armatures'] = json.dumps(source_armatures)
                    move_coll['cp77_source_armature_policy'] = 'authoritative_master'

                json_apps = _json_apps_for_collection(move_coll, mesh_key)
                _ensure_appearance_variants(Masters, move_coll, mesh_key, source_key, apps, json_apps)
            except Exception as error:
                print('failed on ', os.path.basename(meshpath))
                print(traceback.format_exc())
                failures.append(
                    f'Mesh import failed for {mesh_key}: '
                    f'{type(error).__name__}: {error}'
                )
    finally:
        cache_after = (
            material_cache_stats(include_helpers=False)
            if with_mats
            else None
        )
        release_material_cache(material_cache_acquired)
        try:
            verbose = not get_addon_preferences().non_verbose
        except Exception:
            verbose = False
        if verbose and prepared_meshes:
            elapsed = time.perf_counter() - bulk_started
            summary = (
                f"Bulk mesh preparation: {imported_source_count}/"
                f"{len(prepared_meshes)} GLBs in {elapsed:.3f}s"
            )
            if cache_before is not None and cache_after is not None:
                summary += (
                    "; material cache "
                    f"{cache_after['exact_hits'] - cache_before['exact_hits']} exact, "
                    f"{cache_after['prototype_hits'] - cache_before['prototype_hits']} prototype, "
                    f"{cache_after['builds'] - cache_before['builds']} builds, "
                    f"{cache_after['clones'] - cache_before['clones']} clones, "
                    f"{cache_after['entries']} cached entries"
                )
            if failures:
                summary += f"; {len(tuple(dict.fromkeys(failures)))} warning(s)"
            print(summary)
=======
                move_coll["meshPath"] = mesh_key
                move_coll["appearance"] = "default"
                move_coll["sourcePath"] = source_key
                move_coll[_MASTER_BASE_KEY] = True
                base_index[source_key] = move_coll
                link_collection_once(Masters, move_coll)
                source_finalize_started = time.perf_counter()
                authoritative_armatures = armature_preparation.deduplicate(move_coll)
                for obj in authoritative_armatures:
                    sources = json_array(obj.get("cp77_master_source_glbs"))
                    if source_key and source_key not in sources:
                        sources.append(source_key)
                    obj["cp77_master_source_glbs"] = json.dumps(sources)

                debug_timings["source_finalize"] = (
                    debug_timings.get("source_finalize", 0.0)
                    + time.perf_counter()
                    - source_finalize_started
                )
                json_apps = _json_apps_for_collection(move_coll, mesh_key)
                variant_started = time.perf_counter()
                ensure_appearance_variants(
                    Masters,
                    move_coll,
                    mesh_key,
                    source_key,
                    apps,
                    json_apps,
                    timing=debug_timings,
                )
                variant_elapsed += time.perf_counter() - variant_started
            except Exception as error:
                if import_started is not None:
                    import_elapsed += max(
                        0.0,
                        time.perf_counter() - import_started,
                    )
                if import_cpu_started is not None:
                    import_cpu_elapsed += max(
                        0.0,
                        time.process_time() - import_cpu_started,
                    )
                import_started = None
                import_cpu_started = None
                _LOG.error(
                    "Mesh master import failed: %s: %s: %s",
                    os.path.basename(meshpath),
                    type(error).__name__,
                    error,
                    exc_info=True,
                )
                # A master that failed after its GLB imported is removed rather than kept half-built for reuse.
                _rollback_failed_master(
                    mesh_state, mesh_key, source_key, base_index, armature_preparation
                )
                failures.append(
                    f"Mesh import failed for {mesh_key}: "
                    f"{type(error).__name__}: {error}"
                )
    finally:
        _LOG.debug(
            "Master armature preparation: %d static/%d skinned new source(s), "
            "%d hierarchy index scan(s) in %.3fs; source finalization=%.3fs",
            armature_preparation.static_sources,
            armature_preparation.skinned_sources,
            armature_preparation.index_builds,
            armature_preparation.index_seconds,
            debug_timings.get("source_finalize", 0.0),
        )
        if progress is not None:
            progress.set(100.0, "Mesh masters complete", force=True)
        if decode_prefetcher is not None:
            decode_prefetcher.close()
        material_profile = finish_material_profiling(material_profile_session)
        cache_after = (
            material_cache_stats(include_helpers=False)
            if cache_before is not None
            else None
        )
        helper_after = (
            material_cache_stats(include_helpers=True)
            if helper_before is not None
            else None
        )
        handler_timing_after = (
            material_handler_timing_stats() if diagnostics_enabled else {}
        )
        template_timing_after = (
            material_template_timing_stats() if diagnostics_enabled else {}
        )
        organization_phase_after = (
            material_organization_phase_timing_stats() if diagnostics_enabled else {}
        )
        release_material_cache(material_cache_acquired)
        if prepared_meshes and is_enabled("DEBUG", _LOG):
            try:
                elapsed = time.perf_counter() - bulk_started
                summary = (
                    f"Bulk mesh preparation: {imported_source_count}/"
                    f"{len(unique_prepared_meshes)} unique GLBs in {elapsed:.3f}s"
                )
                duplicate_request_count = len(prepared_meshes) - len(
                    unique_prepared_meshes
                )
                if duplicate_request_count:
                    summary += f"; {duplicate_request_count} duplicate depot request(s) collapsed"
                summary += (
                    f"; phases resolve={resolve_elapsed:.3f}s"
                    f", reused={reuse_elapsed:.3f}s/{reused_source_count}"
                    f", import={import_elapsed:.3f}s"
                    f" (cpu={import_cpu_elapsed:.3f}s)"
                    f", decode_wait={decode_wait_elapsed:.3f}s"
                    f", variants={variant_elapsed:.3f}s"
                )
                if cache_before is not None and cache_after is not None:
                    summary += (
                        "; material cache "
                        f"{cache_after['exact_hits'] - cache_before['exact_hits']} exact, "
                        f"{cache_after['prototype_hits'] - cache_before['prototype_hits']} prototype, "
                        f"{cache_after['builds'] - cache_before['builds']} builds, "
                        f"{cache_after['clones'] - cache_before['clones']} clones, "
                        f"{cache_after['entries']} cached entries"
                    )
                    semantic_reduced = cache_after.get(
                        "semantic_reduced_materials", 0
                    ) - cache_before.get("semantic_reduced_materials", 0)
                    if semantic_reduced:
                        summary += (
                            f", semantic identity {semantic_reduced} material(s)/"
                            f"{cache_after.get('semantic_trimmed_keys', 0) - cache_before.get('semantic_trimmed_keys', 0)} ignored key(s)"
                        )
                if failures:
                    summary += f"; {len(tuple(dict.fromkeys(failures)))} warning(s)"
                _LOG.debug("%s", summary)
                if is_enabled("DEBUG", _LOG):
                    _log_bulk_debug_timings(
                        debug_timings,
                        material_profile,
                    )
                    if handler_timing_after:
                        body_rows, organization_rows = _material_timing_delta_rows(
                            handler_timing_before,
                            handler_timing_after,
                        )
                        if body_rows:
                            _LOG.debug(
                                "Material handler hotspots: %s",
                                _format_material_timing_rows(body_rows),
                            )
                        if organization_rows:
                            _LOG.debug(
                                "Material graph organization by handler: %s",
                                _format_material_timing_rows(organization_rows),
                            )
                    if organization_phase_after:
                        phase_order = (
                            "bundle",
                            "bundle_scan",
                            "bundle_nodes",
                            "bundle_items",
                            "bundle_sync",
                            "bundle_sync_fallback",
                            "bundle_rewire",
                            "bundle_rewire_pack",
                            "bundle_rewire_replace",
                            "cleanup",
                            "topology",
                            "placement",
                            "placement_prepare",
                            "placement_write",
                            "placement_write_bulk",
                            "placement_write_scalar",
                            "frames",
                            "metadata",
                        )
                        phase_rows = []
                        for phase_name in phase_order:
                            seconds = max(
                                0.0,
                                float(organization_phase_after.get(phase_name, 0.0))
                                - float(organization_phase_before.get(phase_name, 0.0)),
                            )
                            if seconds > 0.0:
                                phase_rows.append(f"{phase_name}={seconds:.3f}s")
                        if phase_rows:
                            _LOG.debug(
                                "Material graph organization phases: %s",
                                "; ".join(phase_rows),
                            )
                    if template_timing_after:
                        body_rows, organization_rows = _material_timing_delta_rows(
                            template_timing_before,
                            template_timing_after,
                        )
                        if body_rows:
                            _LOG.debug(
                                "Material template hotspots: %s",
                                _format_material_timing_rows(body_rows),
                            )
                        if organization_rows:
                            _LOG.debug(
                                "Material graph organization by template: %s",
                                _format_material_timing_rows(organization_rows),
                            )
                    if helper_before is not None and helper_after is not None:
                        ml_before = helper_before.get("multilayer", {})
                        ml_after = helper_after.get("multilayer", {})
                        perf_before = ml_before.get("build_perf", {})
                        perf_after = ml_after.get("build_perf", {})
                        ml_builds = int(
                            perf_after.get("builds", 0) - perf_before.get("builds", 0)
                        )
                        if ml_builds:

                            def _perf_delta(name):
                                return max(
                                    0.0,
                                    float(perf_after.get(name, 0.0))
                                    - float(perf_before.get(name, 0.0)),
                                )

                            _LOG.debug(
                                "Multilayer build timing: %d build(s); "
                                "setup_load=%.3fs, layer_prepare=%.3fs "
                                "(microblend=%.3fs, template=%.3fs, group=%.3fs), "
                                "mask_resolve=%.3fs, mask_images=%.3fs, "
                                "layer_nodes=%.3fs, surface_setup=%.3fs "
                                "(shell=%.3fs, masks=%.3fs, global_normal=%.3fs, variant=%.3fs); "
                                "setup cache=%d hit/%d miss, template=%d hit/%d miss, "
                                "prepared layers=%d hit/%d miss, layer clones=%d base/%d repatched, "
                                "template groups=%d clone/%d build",
                                ml_builds,
                                _perf_delta("setup_load"),
                                _perf_delta("layer_prepare"),
                                _perf_delta("layer_microblend"),
                                _perf_delta("layer_template"),
                                _perf_delta("layer_group"),
                                _perf_delta("mask_resolve"),
                                _perf_delta("mask_images"),
                                _perf_delta("layer_nodes"),
                                _perf_delta("surface_setup"),
                                _perf_delta("surface_shell"),
                                _perf_delta("surface_masks"),
                                _perf_delta("surface_global_normal"),
                                _perf_delta("surface_variant"),
                                int(
                                    ml_after.get("mlsetup_hits", 0)
                                    - ml_before.get("mlsetup_hits", 0)
                                ),
                                int(
                                    ml_after.get("mlsetup_misses", 0)
                                    - ml_before.get("mlsetup_misses", 0)
                                ),
                                int(
                                    ml_after.get("mltemplate_hits", 0)
                                    - ml_before.get("mltemplate_hits", 0)
                                ),
                                int(
                                    ml_after.get("mltemplate_misses", 0)
                                    - ml_before.get("mltemplate_misses", 0)
                                ),
                                int(
                                    ml_after.get("prepared_layer_hits", 0)
                                    - ml_before.get("prepared_layer_hits", 0)
                                ),
                                int(
                                    ml_after.get("prepared_layer_misses", 0)
                                    - ml_before.get("prepared_layer_misses", 0)
                                ),
                                int(
                                    ml_after.get("layer_group_base_clones", 0)
                                    - ml_before.get("layer_group_base_clones", 0)
                                ),
                                int(
                                    ml_after.get("layer_group_repatched_clones", 0)
                                    - ml_before.get("layer_group_repatched_clones", 0)
                                ),
                                int(
                                    ml_after.get("template_group_clones", 0)
                                    - ml_before.get("template_group_clones", 0)
                                ),
                                int(
                                    ml_after.get("template_group_builds", 0)
                                    - ml_before.get("template_group_builds", 0)
                                ),
                            )
            except Exception:
                debug_exception(_LOG, "Bulk mesh diagnostics failed")
>>>>>>> Stashed changes
    return tuple(dict.fromkeys(failures))
