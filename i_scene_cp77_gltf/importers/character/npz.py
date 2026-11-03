import os
import uuid

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from ...assetio.files import binary_reader
from ...assetio.mesh_npz import (
    MAGIC_MESH,
    npz_int,
    npz_text,
    require_count,
    require_indices,
)
from ...assetio.resources import BASE_CHARACTERS, get_char_dir, get_rig_dir
from ...blender.custom_normals import set_custom_normals_from_corners
from ...blender.identity import rna_is_live
from ...blender.transactions import (
    track_created_datablock,
    track_mutation,
    transactional,
)
from ...core.log import get_logger
from ...core.notifications import import_operation, report
from ..entity.skinning import bind_skinned_objects_to_rig
from ..rig.bundled import import_bundled_metarig

_LOG = get_logger(__name__)

MAGIC_SK = b"SKNZ"

# Loaded character parts carry their role and the load they came from, so the shape sliders find them after a rename.
CHARACTER_ROLE_KEY = "cp77_character_role"
CHARACTER_LOAD_KEY = "cp77_character_load"


_HEAD_FEATURES = {
    "eyes": ("1", "eyes", 25),
    "nose": ("2", "nose", 25),
    "mouth": ("3", "mouth", 25),
    "jaw": ("4", "jaw", 25),
    "ears": ("5", "ear", 25),
}

_BREAST_KEYS = {
    1: "t0_000_wa_base__full_breast_small_breast",
    2: "t0_000_wa_base__full_breast_big_breast",
}

_ROLE_FIELDS = {
    "HEAD": ("head_mesh_names", "head_load_token"),
    "BODY": ("body_mesh_name", "body_load_token"),
}


def character_objects(props, role):
    """The loaded objects of role"""
    names_field, token_field = _ROLE_FIELDS[role]
    names = [name for name in getattr(props, names_field).split(";") if name]
    token = getattr(props, token_field)

    def belongs(obj):
        return not token or (
            obj.get(CHARACTER_LOAD_KEY) == token and obj.get(CHARACTER_ROLE_KEY) == role
        )

    found = [
        obj
        for obj in (bpy.data.objects.get(name) for name in names)
        if obj is not None and belongs(obj)
    ]
    if token and len(found) < len(names):
        found = [
            obj
            for obj in bpy.data.objects
            if obj.get(CHARACTER_LOAD_KEY) == token
            and obj.get(CHARACTER_ROLE_KEY) == role
        ]
    return found


def _get_max_feature_variant(props, feature_attr):
    """Calculates the highest variant index available across all loaded head meshes for a given feature"""
    code, suffix, _ = _HEAD_FEATURES[feature_attr]
    tag = f"_{suffix}"
    max_val = 0

    for head_obj in character_objects(props, "HEAD"):
        if not head_obj.data.shape_keys:
            continue

        for kb in head_obj.data.shape_keys.key_blocks:
            if kb.name.endswith(tag):
                try:
                    prefix = kb.name.split("_")[0]
                    if prefix.startswith("h") and prefix.endswith(code):
                        val_str = prefix[1 : -len(code)]
                        val = int(val_str)
                        max_val = max(max_val, val)
                except (ValueError, IndexError):
                    continue

    return max_val


def _wrapped_slider(value, highest):
    """A variant slider's value wrapped within 0..highest"""
    if highest == 0 or value > highest:
        return 0
    return highest if value < 0 else value


def _update_head_feature(props, feature_attr):
    """Synchronizes the active shape key variant with the provided feature attribute"""
    if getattr(props, "is_updating", False):
        return

    props.is_updating = True

    try:
        max_val = _get_max_feature_variant(props, feature_attr)
        val = getattr(props, feature_attr)
        new_val = _wrapped_slider(val, max_val)
        if new_val != val:
            setattr(props, feature_attr, new_val)
            val = new_val

        code, suffix, _ = _HEAD_FEATURES[feature_attr]
        tag = f"_{suffix}"
        key_name = f"h{val:02d}{code}_{suffix}" if val > 0 else ""

        for head_obj in character_objects(props, "HEAD"):
            if not head_obj.data.shape_keys:
                continue

            for kb in head_obj.data.shape_keys.key_blocks:
                if kb.name.endswith(tag):
                    kb.value = 1.0 if (key_name and kb.name == key_name) else 0.0

    finally:
        props.is_updating = False


def breast_shape_objects(props):
    """The loaded body submeshes that carry breast shape keys"""
    return [
        obj
        for obj in character_objects(props, "BODY")
        if obj.type == "MESH"
        and obj.data.shape_keys
        and any(
            name in obj.data.shape_keys.key_blocks for name in _BREAST_KEYS.values()
        )
    ]


def _update_body_breasts(props):
    """Toggles breast shape keys on the body meshes and cycles slider values if out of range"""
    if getattr(props, "is_updating", False):
        return

    props.is_updating = True

    try:
        val = props.breasts
        bodies = breast_shape_objects(props)

        present = [
            k
            for k, name in _BREAST_KEYS.items()
            if any(name in body.data.shape_keys.key_blocks for body in bodies)
        ]
        max_val = max(present) if present else 0
        new_val = _wrapped_slider(val, max_val)
        if new_val != val:
            props.breasts = new_val
            val = new_val

        for body in bodies:
            for k_val, key_name in _BREAST_KEYS.items():
                kb = body.data.shape_keys.key_blocks.get(key_name)
                if kb:
                    kb.value = 1.0 if val == k_val else 0.0

    finally:
        props.is_updating = False


class CP77CharacterShapeProps(bpy.types.PropertyGroup):
    """Defines UI sliders that drive head and body shape-key variants"""

    is_updating: BoolProperty(default=False, options={"HIDDEN"})

    head_mesh_names: StringProperty(
        name="Head Meshes",
        description="Semicolon-separated names of loaded head mesh objects",
    )

    body_mesh_name: StringProperty(
        name="Body Meshes",
        description="Semicolon-separated names of the loaded body mesh objects",
    )

    head_load_token: StringProperty(options={"HIDDEN"})
    body_load_token: StringProperty(options={"HIDDEN"})

    eyes: IntProperty(
        name="Eyes",
        min=-1,
        max=100,
        default=0,
        description="Eye shape variant (0 = none)",
        update=lambda s, c: _update_head_feature(s, "eyes"),
    )

    nose: IntProperty(
        name="Nose",
        min=-1,
        max=100,
        default=0,
        description="Nose shape variant (0 = none)",
        update=lambda s, c: _update_head_feature(s, "nose"),
    )

    mouth: IntProperty(
        name="Mouth",
        min=-1,
        max=100,
        default=0,
        description="Mouth shape variant (0 = none)",
        update=lambda s, c: _update_head_feature(s, "mouth"),
    )

    jaw: IntProperty(
        name="Jaw",
        min=-1,
        max=100,
        default=0,
        description="Jaw shape variant (0 = none)",
        update=lambda s, c: _update_head_feature(s, "jaw"),
    )

    ears: IntProperty(
        name="Ears",
        min=-1,
        max=100,
        default=0,
        description="Ear shape variant (0 = none)",
        update=lambda s, c: _update_head_feature(s, "ears"),
    )

    breasts: IntProperty(
        name="Breasts",
        min=-1,
        max=10,
        default=0,
        description="Breast shape (0 = default, 1 = small, 2 = big)",
        update=lambda s, c: _update_body_breasts(s),
    )


def _write_weights(
    obj, vg_names, vertex_indices, group_indices, weights, vertex_count, label, warnings
):
    """Create the vertex groups and write every influence, one VertexGroup.add per (group, weight) run"""
    vertex_indices = np.asarray(vertex_indices, dtype=np.int64).reshape(-1)
    group_indices = np.asarray(group_indices, dtype=np.int64).reshape(-1)
    weights = np.asarray(weights, dtype=np.float32).reshape(-1)
    require_count(group_indices, len(vertex_indices), f"{label} weight group indices")
    require_count(weights, len(vertex_indices), f"{label} weight values")

    valid = (
        (vertex_indices >= 0)
        & (vertex_indices < vertex_count)
        & (group_indices >= 0)
        & (group_indices < len(vg_names))
        & np.isfinite(weights)
    )
    dropped = int(len(valid) - np.count_nonzero(valid))
    if dropped:
        if warnings is not None:
            warnings.append(
                f"{label}: skipped {dropped} weight(s) with an invalid vertex, group or value"
            )
        vertex_indices, group_indices, weights = (
            vertex_indices[valid],
            group_indices[valid],
            weights[valid],
        )

    groups = [obj.vertex_groups.new(name=name) for name in vg_names]
    if not len(weights):
        return

    # A repeated (vertex, group) pair keeps its last weight, as successive REPLACE writes would.
    pairs = group_indices * vertex_count + vertex_indices
    reversed_first = np.unique(pairs[::-1], return_index=True)[1]
    keep = np.sort(len(pairs) - 1 - reversed_first)
    vertex_indices, group_indices, weights = (
        vertex_indices[keep],
        group_indices[keep],
        weights[keep],
    )

    order = np.lexsort((vertex_indices, weights, group_indices))
    vertex_indices, group_indices, weights = (
        vertex_indices[order],
        group_indices[order],
        weights[order],
    )
    boundaries = (
        np.flatnonzero((np.diff(group_indices) != 0) | (np.diff(weights) != 0)) + 1
    )
    starts = np.concatenate(([0], boundaries))
    ends = np.concatenate((boundaries, [len(weights)]))
    for start, end in zip(starts.tolist(), ends.tolist()):
        groups[int(group_indices[start])].add(
            vertex_indices[start:end].tolist(), float(weights[start]), "REPLACE"
        )


def _build_mesh_object(
    context, data, prefix="", obj_name=None, link_to_collection=None, warnings=None
):
    """Build a single mesh object from NPZ data. *prefix* selects sub-keys for collection format"""
    p = prefix
    if obj_name is None:
        obj_name = npz_text(data[f"{p}name"])
    label = f"NPZ mesh {obj_name!r}"

    verts = np.asarray(data[f"{p}verts"], dtype=np.float32)
    if verts.size % 3:
        raise ValueError(
            f"{label}: vertex array length {verts.size} is not a multiple of 3"
        )
    verts = verts.reshape(-1, 3)
    if not np.all(np.isfinite(verts)):
        raise ValueError(f"{label}: vertex positions must be finite")
    loop_starts = np.asarray(data[f"{p}loop_starts"], dtype=np.int64).reshape(-1)
    loop_totals = np.asarray(data[f"{p}loop_totals"], dtype=np.int64).reshape(-1)
    loop_v_indices = np.asarray(data[f"{p}loop_v_indices"], dtype=np.int64).reshape(-1)
    vertex_count, loop_count, face_count = (
        len(verts),
        len(loop_v_indices),
        len(loop_starts),
    )

    require_count(loop_totals, face_count, f"{label} face sizes")
    require_indices(loop_v_indices, vertex_count, f"{label} corner vertex indices")
    if face_count and (
        int(loop_totals.min()) < 3
        or int(loop_starts.min()) < 0
        or int((loop_starts + loop_totals).max()) > loop_count
    ):
        raise ValueError(
            f"{label}: faces must have at least 3 corners inside the {loop_count} corners"
        )

    mesh = track_created_datablock("meshes", bpy.data.meshes.new(obj_name))
    obj = track_created_datablock("objects", bpy.data.objects.new(obj_name, mesh))

    coll = link_to_collection or context.collection
    coll.objects.link(obj)
    context.view_layer.objects.active = obj
    obj.select_set(True)

    mesh.vertices.add(vertex_count)
    mesh.loops.add(loop_count)
    mesh.polygons.add(face_count)

    mesh.vertices.foreach_set("co", verts.ravel())
    mesh.loops.foreach_set("vertex_index", loop_v_indices.astype(np.int32))
    mesh.polygons.foreach_set("loop_start", loop_starts.astype(np.int32))
    mesh.polygons.foreach_set("loop_total", loop_totals.astype(np.int32))

    mesh.update(calc_edges=True)

    uv_names = [npz_text(x) for x in data.get(f"{p}uv_names", [])]
    for name in uv_names:
        key = f"{p}uv_{name}"
        if key in data:
            uv = np.asarray(data[key], dtype=np.float32).reshape(-1)
            require_count(uv, loop_count * 2, f"{label} UV layer {name!r} values")
            uv_layer = mesh.uv_layers.new(name=name)
            if uv_layer:
                uv_layer.uv.foreach_set("vector", uv)

    col_names = [npz_text(x) for x in data.get(f"{p}col_names", [])]
    col_meta = data.get(f"{p}col_meta", np.array([]))
    if len(col_meta) > 0:
        for i, name in enumerate(col_names):
            key = f"{p}col_{name}"
            if key in data:
                domain = "POINT" if col_meta[i][0] == 1 else "CORNER"
                colors = np.asarray(data[key], dtype=np.float32).reshape(-1)
                element_count = vertex_count if domain == "POINT" else loop_count
                require_count(
                    colors, element_count * 4, f"{label} color {name!r} values"
                )
                col_layer = mesh.color_attributes.new(
                    name=name, type="FLOAT_COLOR", domain=domain
                )
                if col_layer:
                    col_layer.data.foreach_set("color", colors)

    mat_names = [npz_text(x) for x in data.get(f"{p}mat_names", [])]
    for m_name in mat_names:
        mat = bpy.data.materials.get(m_name) or track_created_datablock(
            "materials", bpy.data.materials.new(name=m_name)
        )
        obj.data.materials.append(mat)

    mat_indices = data.get(f"{p}mat_indices")
    if mat_indices is not None:
        mat_indices = np.asarray(mat_indices, dtype=np.int64).reshape(-1)
        require_count(mat_indices, face_count, f"{label} face material indices")
        slot_count = max(1, len(mat_names))
        outside = int(np.count_nonzero((mat_indices < 0) | (mat_indices >= slot_count)))
        if outside:
            if warnings is not None:
                warnings.append(
                    f"{label}: {outside} face(s) named a missing material slot and use slot 0"
                )
            mat_indices = np.where(
                (mat_indices < 0) | (mat_indices >= slot_count), 0, mat_indices
            )
        mesh.polygons.foreach_set("material_index", mat_indices.astype(np.int32))

    vg_names = [npz_text(x) for x in data.get(f"{p}vg_names", [])]
    w_values = data.get(f"{p}w_values", np.array([], dtype=np.float32))
    if len(vg_names) > 0 and len(w_values) > 0:
        _write_weights(
            obj,
            vg_names,
            data.get(f"{p}w_v_indices", np.array([], dtype=np.int32)),
            data.get(f"{p}w_g_indices", np.array([], dtype=np.int32)),
            w_values,
            vertex_count,
            label,
            warnings,
        )

    normals = data.get(f"{p}normals")
    if normals is not None:
        normals = normals.reshape(-1, 3)
        if len(normals) == len(mesh.loops):
            set_custom_normals_from_corners(
                mesh,
                normals,
                label=label,
            )
            mesh.update()

    if mesh.validate(verbose=False, clean_customdata=False) and warnings is not None:
        warnings.append(
            f"{label}: Blender repaired invalid geometry (duplicate or degenerate elements)"
        )

    return obj


def _load_mesh_npz_data(context, data, link_to_collection=None, warnings=None):
    """Import a mesh from NPZ data and return (collection, objects)"""
    if npz_text(data["magic"]) != MAGIC_MESH.decode():
        raise ValueError("Not a valid MSHZ file")

    version = npz_int(data, "version", 1)

    if version >= 2 and "submesh_count" in data:
        coll_name = npz_text(data["collection_name"])
        count = npz_int(data, "submesh_count")
        sub_names = [npz_text(n) for n in data["submesh_names"]]
        require_count(sub_names, count, "NPZ submesh names")

        coll = track_created_datablock(
            "collections", bpy.data.collections.new(coll_name)
        )
        parent = link_to_collection or context.scene.collection
        parent.children.link(coll)

        objects = []
        for i in range(count):
            obj = _build_mesh_object(
                context,
                data,
                prefix=f"sub{i}_",
                obj_name=sub_names[i],
                link_to_collection=coll,
                warnings=warnings,
            )
            objects.append(obj)

        return coll, objects

    obj = _build_mesh_object(
        context, data, link_to_collection=link_to_collection, warnings=warnings
    )
    return None, [obj]


def load_mesh_npz(context, filepath, link_to_collection=None, warnings=None):
    """Import a mesh NPZ and close the archive before returning"""
    with binary_reader(filepath) as stream, np.load(stream, allow_pickle=False) as data:
        return _load_mesh_npz_data(
            context, data, link_to_collection=link_to_collection, warnings=warnings
        )


def _shape_key_payload(obj, data, prefix):
    """The validated (names, values, coordinate rows) a shape-key archive holds for obj"""
    p = prefix
    names = [npz_text(n) for n in data[f"{p}names"]]
    values = np.asarray(data[f"{p}values"], dtype=np.float32).reshape(-1)
    coords = np.asarray(data[f"{p}coords"], dtype=np.float32)
    n_verts_stored = npz_int(data, f"{p}n_verts")

    if len(obj.data.vertices) != n_verts_stored:
        raise ValueError(
            f"Vertex count mismatch on {obj.name}: {len(obj.data.vertices)} vs {n_verts_stored}"
        )
    require_count(values, len(names), f"{obj.name} shape key values")
    coords = (
        coords.reshape(len(names), -1)
        if len(names)
        else coords.reshape(0, n_verts_stored * 3)
    )
    if coords.shape[1] != n_verts_stored * 3:
        raise ValueError(
            f"{obj.name}: shape key rows hold {coords.shape[1]} values, expected {n_verts_stored * 3}"
        )
    if not np.all(np.isfinite(coords)):
        raise ValueError(f"{obj.name}: shape key coordinates must be finite")
    return names, values, coords


def _track_shape_keys(obj, names):
    """Register a rollback that removes the keys an import adds to obj and restores the ones it overwrites"""
    shape_keys = obj.data.shape_keys
    had_keys = shape_keys is not None
    existing = {}
    if had_keys:
        for name in names:
            kb = shape_keys.key_blocks.get(name)
            if kb is not None:
                coords = np.empty(len(kb.data) * 3, dtype=np.float32)
                kb.data.foreach_get("co", coords)
                existing[name] = (coords, kb.value)
        kept = {kb.name for kb in shape_keys.key_blocks}
    else:
        kept = set()

    def restore():
        if not rna_is_live(obj):
            return
        if not had_keys:
            obj.shape_key_clear()
            return
        blocks = obj.data.shape_keys.key_blocks
        for kb in [kb for kb in blocks if kb.name not in kept]:
            obj.shape_key_remove(kb)
        for name, (coords, value) in existing.items():
            kb = blocks.get(name)
            if kb is not None:
                kb.data.foreach_set("co", coords)
                kb.value = value

    track_mutation(
        ("npz_shape_keys", obj.as_pointer()), restore, label=f"shape keys of {obj.name}"
    )


def _apply_shapekeys_to_object(obj, payload, replace_values=True):
    """Apply validated shape keys to a single object"""
    names, values, coords = payload
    if not obj.data.shape_keys:
        obj.shape_key_add(name="Basis", from_mix=False)

    sk = obj.data.shape_keys

    for i, name in enumerate(names):
        kb = sk.key_blocks.get(name)
        if not kb:
            kb = obj.shape_key_add(name=name, from_mix=False)
        kb.data.foreach_set("co", coords[i])
        if replace_values:
            kb.value = float(values[i])


def _shape_key_targets(target, data):
    """[(object, prefix)] the archive applies to"""
    if npz_text(data["magic"]) != MAGIC_SK.decode():
        raise ValueError("Not a valid SKNZ file")

    version = npz_int(data, "version", 2)

    if version >= 3 and "submesh_count" in data:
        count = npz_int(data, "submesh_count")
        sub_names = [npz_text(n) for n in data["submesh_names"]]
        require_count(sub_names, count, "NPZ shape key submesh names")

        if isinstance(target, (list, tuple)):
            objects = [o for o in target if o and o.type == "MESH"]

            # Equal lengths apply positionally, which survives Blender renaming colliding submeshes on import.
            if len(objects) == count:
                return [(obj, f"sub{i}_") for i, obj in enumerate(objects)]

            obj_map = {obj.name: obj for obj in objects}
        else:
            obj_map = {target.name: target} if target else {}

        matched = []
        for i in range(count):
            name = sub_names[i]
            obj = obj_map.get(name)
            if obj is None:
                _LOG.warning("No matching object for submesh '%s', skipping", name)
                continue
            matched.append((obj, f"sub{i}_"))
        return matched

    obj = target[0] if isinstance(target, (list, tuple)) else target
    if obj is None or obj.type != "MESH":
        raise TypeError("Object must be a Mesh")
    return [(obj, "")]


def _load_shapekeys_npz_data(target, data, replace_values=True, track_existing=False):
    """Import shape keys from NPZ data onto target"""
    plan = [
        (obj, _shape_key_payload(obj, data, prefix))
        for obj, prefix in _shape_key_targets(target, data)
    ]
    for obj, payload in plan:
        if track_existing:
            _track_shape_keys(obj, payload[0])
        _apply_shapekeys_to_object(obj, payload, replace_values=replace_values)


def load_shapekeys_npz(target, filepath, replace_values=True, track_existing=False):
    """Import shape keys from NPZ and close the archive before returning"""
    with binary_reader(filepath) as stream, np.load(stream, allow_pickle=False) as data:
        return _load_shapekeys_npz_data(
            target, data, replace_values=replace_values, track_existing=track_existing
        )


@transactional("NPZ mesh import")
def import_mesh_npz(context, filepath):
    """Import one mesh archive as a unit"""
    warnings = []
    _coll, objects = load_mesh_npz(context, filepath, warnings=warnings)
    return objects, warnings


@transactional("NPZ shape key import")
def import_shapekeys_npz(obj, filepath, replace_values=True):
    """Apply a shape-key archive to an existing mesh, restoring its keys if any part fails"""
    load_shapekeys_npz(
        obj, filepath, replace_values=replace_values, track_existing=True
    )


class CP77_OT_NpzImportMesh(bpy.types.Operator, ImportHelper):
    """Import Mesh from NPZ format"""

    bl_idname = "cp77.npz_import_mesh"
    bl_label = "Import Mesh (.npz)"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".npz"
    filter_glob: StringProperty(default="*.npz", options={"HIDDEN"})

    @import_operation
    def execute(self, context):
        try:
            objects, warnings = import_mesh_npz(context, self.filepath)
        except Exception as error:
            report(
                self,
                "ERROR",
                f"NPZ mesh import failed: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        for warning in warnings:
            report(self, "WARNING", warning, logger=_LOG)
        report(
            self, "INFO", f"Imported: {', '.join(o.name for o in objects)}", logger=_LOG
        )
        return {"FINISHED"}


class CP77_OT_NpzImportShapeKeys(bpy.types.Operator, ImportHelper):
    """Import Shape Keys from NPZ format"""

    bl_idname = "cp77.npz_import_shapekeys"
    bl_label = "Import ShapeKeys (.npz)"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".npz"
    filter_glob: StringProperty(default="*.npz", options={"HIDDEN"})
    replace_values: BoolProperty(name="Restore Values", default=True)

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == "MESH"

    @import_operation
    def execute(self, context):
        try:
            import_shapekeys_npz(
                context.object, self.filepath, replace_values=self.replace_values
            )
        except Exception as error:
            report(
                self,
                "ERROR",
                f"NPZ shape key import failed: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        report(self, "INFO", f"Loaded shape keys: {self.filepath}", logger=_LOG)
        return {"FINISHED"}


_CHARACTER_PROPS = (
    "head_mesh_names",
    "body_mesh_name",
    "head_load_token",
    "body_load_token",
    "eyes",
    "nose",
    "mouth",
    "jaw",
    "ears",
    "breasts",
)


def _track_character_props(props):
    """Restore the shape-slider state without running its update callbacks if the load rolls back"""
    saved = {name: getattr(props, name) for name in _CHARACTER_PROPS}

    def restore():
        props.is_updating = True
        try:
            for name, value in saved.items():
                setattr(props, name, value)
        finally:
            props.is_updating = False

    track_mutation(
        ("cp77_character_shape", props.as_pointer()),
        restore,
        label="character shape sliders",
    )


def _tag_character_parts(objects, role):
    token = uuid.uuid4().hex
    for obj in objects:
        obj[CHARACTER_ROLE_KEY] = role
        obj[CHARACTER_LOAD_KEY] = token
    return token


def _bind_to_rig(objects, rig):
    """Deform the character's meshes with rig as skinned meshes are bound to a MetaRig"""
    for obj in objects:
        obj.modifiers.new("Armature", "ARMATURE").object = rig
    bind_skinned_objects_to_rig(objects, rig)


@transactional("Load Base Character")
def load_base_character(context, gender, *, load_head=True, load_body=True):
    """Load the bundled base body and head with their shape keys, bound to the character's rig"""
    resources_dir = get_char_dir()
    resources = BASE_CHARACTERS[gender]
    warnings = []

    body_objects = []
    if load_body:
        body_path = os.path.join(resources_dir, resources["body_mesh"])
        _coll, body_objects = load_mesh_npz(context, body_path, warnings=warnings)
        load_shapekeys_npz(
            body_objects, os.path.join(resources_dir, resources["body_sk"])
        )

    head_objects = []
    if load_head:
        for mesh_file, sk_file in resources["head_parts"]:
            _coll, objects = load_mesh_npz(
                context, os.path.join(resources_dir, mesh_file), warnings=warnings
            )
            load_shapekeys_npz(objects, os.path.join(resources_dir, sk_file))
            head_objects.extend(objects)

    rig = import_bundled_metarig(os.path.join(get_rig_dir(), resources["rig"]))
    _bind_to_rig(body_objects + head_objects, rig)

    props = context.scene.cp77_character_shape
    _track_character_props(props)
    if load_body:
        props.body_load_token = _tag_character_parts(body_objects, "BODY")
        props.body_mesh_name = ";".join(o.name for o in body_objects)
        props.breasts = 0
    if load_head:
        props.head_load_token = _tag_character_parts(head_objects, "HEAD")
        props.head_mesh_names = ";".join(o.name for o in head_objects)
        props.eyes = 0
        props.nose = 0
        props.mouth = 0
        props.jaw = 0
        props.ears = 0

    return [rig] + body_objects + head_objects, warnings


class CP77_OT_LoadBaseCharacter(bpy.types.Operator):
    """Load a CP77 base character mesh with shape keys, bound to its rig"""

    bl_idname = "cp77.load_base_character"
    bl_label = "Load Base Character"
    bl_options = {"REGISTER", "UNDO"}

    gender: EnumProperty(
        name="Character",
        items=[
            ("MASC", "Masculine", "Male body base"),
            ("FEM", "Feminine", "Female body base"),
        ],
        default="FEM",
    )

    load_head: BoolProperty(name="Head", default=True)
    load_body: BoolProperty(name="Body", default=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    @import_operation
    def execute(self, context):
        if not self.load_head and not self.load_body:
            report(self, "WARNING", "Nothing selected to load", logger=_LOG)
            return {"CANCELLED"}

        try:
            objects, warnings = load_base_character(
                context,
                self.gender,
                load_head=self.load_head,
                load_body=self.load_body,
            )
        except FileNotFoundError as error:
            report(
                self,
                "ERROR",
                f"Resource file not found: {error.filename}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        except Exception as error:
            report(
                self,
                "ERROR",
                f"Load Base Character failed: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}

        for warning in warnings:
            report(self, "WARNING", warning, logger=_LOG)
        report(
            self, "INFO", f"Loaded: {', '.join(o.name for o in objects)}", logger=_LOG
        )
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "gender", expand=True)
        row = layout.row(align=True)
        row.prop(self, "load_head")
        row.prop(self, "load_body")
