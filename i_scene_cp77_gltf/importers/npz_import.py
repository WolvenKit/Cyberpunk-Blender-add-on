import os
from collections import defaultdict

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from ..main.common import get_char_dir

MAGIC_MESH = b"MSHZ"
VERSION_MESH = 1
MAGIC_SK = b"SKNZ"
VERSION_SK = 2


def _decode_bytes(val):
    """Decode bytes/numpy bytes to string."""
    if hasattr(val, "item"):
        val = val.item()
    if isinstance(val, (bytes, np.bytes_)):
        return val.decode("utf8", "ignore").rstrip("\x00")
    return str(val)


_HEAD_FEATURES = {
    'eyes': ('1', 'eyes', 25),
    'nose': ('2', 'nose', 25),
    'mouth': ('3', 'mouth', 25),
    'jaw': ('4', 'jaw', 25),
    'ears': ('5', 'ear', 25),
    }


def _get_max_feature_variant(props, feature_attr):
    """Calculates the highest variant index available across all loaded head meshes for a given feature."""
    if not props.head_mesh_names:
        return 0

    code, suffix, _ = _HEAD_FEATURES[feature_attr]
    tag = f"_{suffix}"
    max_val = 0

    for obj_name in props.head_mesh_names.split(";"):
        head_obj = bpy.data.objects.get(obj_name)
        if not head_obj or not head_obj.data.shape_keys:
            continue

        for kb in head_obj.data.shape_keys.key_blocks:
            if kb.name.endswith(tag):
                try:
                    prefix = kb.name.split('_')[0]
                    if prefix.startswith('h') and prefix.endswith(code):
                        val_str = prefix[1:-len(code)]
                        val = int(val_str)
                        if val > max_val:
                            max_val = val
                except (ValueError, IndexError):
                    continue

    return max_val


def _update_head_feature(props, feature_attr):
    """Synchronizes the active shape key variant with the provided feature attribute."""
    if getattr(props, "is_updating", False):
        return

    props.is_updating = True

    try:
        max_val = _get_max_feature_variant(props, feature_attr)
        val = getattr(props, feature_attr)

        new_val = val
        if max_val == 0:
            new_val = 0
        elif val > max_val:
            new_val = 0
        elif val < 0:
            new_val = max_val

        if new_val != val:
            setattr(props, feature_attr, new_val)
            val = new_val

        if not props.head_mesh_names:
            return

        code, suffix, _ = _HEAD_FEATURES[feature_attr]
        tag = f"_{suffix}"
        key_name = f"h{val:02d}{code}_{suffix}" if val > 0 else ""

        for obj_name in props.head_mesh_names.split(";"):
            head_obj = bpy.data.objects.get(obj_name)
            if not head_obj or not head_obj.data.shape_keys:
                continue

            for kb in head_obj.data.shape_keys.key_blocks:
                if kb.name.endswith(tag):
                    kb.value = 1.0 if (key_name and kb.name == key_name) else 0.0

    finally:
        props.is_updating = False


def _update_body_breasts(props):
    """Toggles breast shape keys on the body mesh and cycles slider values if out of range."""
    if getattr(props, "is_updating", False):
        return

    props.is_updating = True

    try:
        val = props.breasts
        body_obj = bpy.data.objects.get(props.body_mesh_name)

        max_val = 0
        if body_obj and body_obj.data.shape_keys:
            present = [k for k, name in _BREAST_KEYS.items() if name in body_obj.data.shape_keys.key_blocks]
            max_val = max(present) if present else 0

        new_val = val
        if max_val == 0:
            new_val = 0
        elif val > max_val:
            new_val = 0
        elif val < 0:
            new_val = max_val

        if new_val != val:
            props.breasts = new_val
            val = new_val

        if body_obj and body_obj.data.shape_keys:
            sk = body_obj.data.shape_keys
            for k_val, key_name in _BREAST_KEYS.items():
                kb = sk.key_blocks.get(key_name)
                if kb:
                    kb.value = 1.0 if val == k_val else 0.0

    finally:
        props.is_updating = False


class CP77CharacterShapeProps(bpy.types.PropertyGroup):
    """Defines UI sliders that drive head and body shape-key variants."""

    is_updating: BoolProperty(default=False, options={'HIDDEN'})

    head_mesh_names: StringProperty(
            name="Head Meshes",
            description="Semicolon-separated names of loaded head mesh objects",
            )

    body_mesh_name: StringProperty(
            name="Body Mesh",
            description="Name of the loaded body mesh object",
            )

    eyes: IntProperty(
            name="Eyes", min=-1, max=100, default=0,
            description="Eye shape variant (0 = none)",
            update=lambda s, c: _update_head_feature(s, 'eyes'),
            )

    nose: IntProperty(
            name="Nose", min=-1, max=100, default=0,
            description="Nose shape variant (0 = none)",
            update=lambda s, c: _update_head_feature(s, 'nose'),
            )

    mouth: IntProperty(
            name="Mouth", min=-1, max=100, default=0,
            description="Mouth shape variant (0 = none)",
            update=lambda s, c: _update_head_feature(s, 'mouth'),
            )

    jaw: IntProperty(
            name="Jaw", min=-1, max=100, default=0,
            description="Jaw shape variant (0 = none)",
            update=lambda s, c: _update_head_feature(s, 'jaw'),
            )

    ears: IntProperty(
            name="Ears", min=-1, max=100, default=0,
            description="Ear shape variant (0 = none)",
            update=lambda s, c: _update_head_feature(s, 'ears'),
            )

    breasts: IntProperty(
            name="Breasts", min=-1, max=10, default=0,
            description="Breast shape (0 = default, 1 = small, 2 = big)",
            update=lambda s, c: _update_body_breasts(s),
            )


_BREAST_KEYS = {
    1: "t0_000_wa_base__full_breast_small_breast",
    2: "t0_000_wa_base__full_breast_big_breast",
    }


def _update_body_breasts(props):
    """Toggle breast shape keys on the body mesh."""
    body_obj = bpy.data.objects.get(props.body_mesh_name)
    if not body_obj or not body_obj.data.shape_keys:
        return

    sk = body_obj.data.shape_keys
    for val, key_name in _BREAST_KEYS.items():
        kb = sk.key_blocks.get(key_name)
        if kb:
            kb.value = 1.0 if props.breasts == val else 0.0


# MESH IMPORT

def _build_mesh_object(context, data, prefix="", obj_name=None, link_to_collection=None):
    """Build a single mesh object from NPZ data. *prefix* selects sub-keys for collection format."""
    p = prefix
    if obj_name is None:
        obj_name = _decode_bytes(data[f"{p}name"])

    mesh = bpy.data.meshes.new(obj_name)
    obj = bpy.data.objects.new(obj_name, mesh)

    coll = link_to_collection or context.collection
    coll.objects.link(obj)
    context.view_layer.objects.active = obj
    obj.select_set(True)

    # GEOMETRY
    verts = data[f"{p}verts"].reshape(-1, 3)
    loop_starts = data[f"{p}loop_starts"]
    loop_totals = data[f"{p}loop_totals"]
    loop_v_indices = data[f"{p}loop_v_indices"]

    mesh.vertices.add(len(verts))
    mesh.loops.add(len(loop_v_indices))
    mesh.polygons.add(len(loop_starts))

    mesh.vertices.foreach_set("co", verts.ravel())
    mesh.loops.foreach_set("vertex_index", loop_v_indices)
    mesh.polygons.foreach_set("loop_start", loop_starts)
    mesh.polygons.foreach_set("loop_total", loop_totals)

    mesh.update(calc_edges=True)

    # UVS
    uv_names = [_decode_bytes(x) for x in data.get(f"{p}uv_names", [])]
    for name in uv_names:
        key = f"{p}uv_{name}"
        if key in data:
            uv_layer = mesh.uv_layers.new(name=name)
            if uv_layer:
                uv_layer.data.foreach_set("uv", data[key])

    # COLORS
    col_names = [_decode_bytes(x) for x in data.get(f"{p}col_names", [])]
    col_meta = data.get(f"{p}col_meta", np.array([]))
    if len(col_meta) > 0:
        for i, name in enumerate(col_names):
            key = f"{p}col_{name}"
            if key in data:
                domain = 'POINT' if col_meta[i][0] == 1 else 'CORNER'
                col_layer = mesh.color_attributes.new(name=name, type='FLOAT_COLOR', domain=domain)
                if col_layer:
                    col_layer.data.foreach_set("color", data[key])

    # MATERIALS
    mat_names = [_decode_bytes(x) for x in data.get(f"{p}mat_names", [])]
    for m_name in mat_names:
        mat = bpy.data.materials.get(m_name) or bpy.data.materials.new(name=m_name)
        obj.data.materials.append(mat)

    mat_indices = data.get(f"{p}mat_indices")
    if mat_indices is not None:
        mesh.polygons.foreach_set("material_index", mat_indices)

    # WEIGHTS
    vg_names = [_decode_bytes(x) for x in data.get(f"{p}vg_names", [])]
    w_v_indices = data.get(f"{p}w_v_indices", np.array([], dtype=np.int32))
    w_g_indices = data.get(f"{p}w_g_indices", np.array([], dtype=np.int32))
    w_values = data.get(f"{p}w_values", np.array([], dtype=np.float32))

    if len(vg_names) > 0 and len(w_values) > 0:
        groups = [obj.vertex_groups.new(name=name) for name in vg_names]

        vert_weights = defaultdict(list)
        for v_idx, g_idx, val in zip(w_v_indices, w_g_indices, w_values):
            vert_weights[int(v_idx)].append((int(g_idx), float(val)))

        for v_idx, weights in vert_weights.items():
            for g_idx, val in weights:
                if g_idx < len(groups):
                    groups[g_idx].add([v_idx], val, 'REPLACE')

    # NORMALS
    normals = data.get(f"{p}normals")
    if normals is not None:
        normals = normals.reshape(-1, 3)
        if len(normals) == len(mesh.loops):
            mesh.normals_split_custom_set(normals)

    return obj


def load_mesh_npz(context, filepath, link_to_collection=None):
    """Import mesh from NPZ — handles both single (v1) and collection (v2) formats.

    Returns (collection_or_None, [objects]).
    Single-mesh files return (None, [obj]).
    Collection files return (collection, [obj, ...]).
    """
    data = np.load(filepath, allow_pickle=False)

    if _decode_bytes(data["magic"]) != MAGIC_MESH.decode():
        raise ValueError("Not a valid MSHZ file")

    version = int(data["version"]) if "version" in data else 1

    # Collection format
    if version >= 2 and "submesh_count" in data:
        coll_name = _decode_bytes(data["collection_name"])
        count = int(data["submesh_count"])
        sub_names = [_decode_bytes(n) for n in data["submesh_names"]]

        coll = bpy.data.collections.new(coll_name)
        parent = link_to_collection or context.scene.collection
        parent.children.link(coll)

        objects = []
        for i in range(count):
            obj = _build_mesh_object(
                context, data, prefix=f"sub{i}_",
                obj_name=sub_names[i], link_to_collection=coll
                )
            objects.append(obj)

        return coll, objects

    # Single mesh format
    obj = _build_mesh_object(context, data, link_to_collection=link_to_collection)
    return None, [obj]


# SHAPEKEY IMPORT

def _apply_shapekeys_to_object(obj, data, prefix="", replace_values=True):
    """Apply shape keys from NPZ data to a single object. *prefix* selects sub-keys."""
    p = prefix
    names = [_decode_bytes(n) for n in data[f"{p}names"]]
    values = data[f"{p}values"]
    coords = data[f"{p}coords"]
    n_verts_stored = int(data[f"{p}n_verts"])

    if len(obj.data.vertices) != n_verts_stored:
        raise ValueError(f"Vertex count mismatch on {obj.name}: {len(obj.data.vertices)} vs {n_verts_stored}")

    if not obj.data.shape_keys:
        obj.shape_key_add(name='Basis', from_mix=False)

    sk = obj.data.shape_keys

    for i, name in enumerate(names):
        kb = sk.key_blocks.get(name)
        if not kb:
            kb = obj.shape_key_add(name=name, from_mix=False)
        kb.data.foreach_set("co", coords[i])
        if replace_values:
            kb.value = float(values[i])


def load_shapekeys_npz(target, filepath, replace_values=True):
    """Import shape keys from NPZ — handles both single (v2) and collection (v3) formats.

    *target* may be a single mesh object **or** a list of mesh objects.
    Collection format matches submeshes by name.
    Single-object format applies to the first (or only) target.
    """
    data = np.load(filepath, allow_pickle=False)

    if _decode_bytes(data["magic"]) != MAGIC_SK.decode():
        raise ValueError("Not a valid SKNZ file")

    version = int(data["version"]) if "version" in data else 2

    # Collection format
    if version >= 3 and "submesh_count" in data:
        count = int(data["submesh_count"])
        sub_names = [_decode_bytes(n) for n in data["submesh_names"]]

        if isinstance(target, (list, tuple)):
            objects = [o for o in target if o and o.type == 'MESH']

            # If the list length matches, apply positionally — this handles the case
            # where Blender auto-renames submeshes on import due to name collisions.
            if len(objects) == count:
                for i, obj in enumerate(objects):
                    _apply_shapekeys_to_object(obj, data, prefix=f"sub{i}_", replace_values=replace_values)
                return

            # Otherwise fall back to name matching
            obj_map = {obj.name: obj for obj in objects}
        else:
            obj_map = {target.name: target} if target else {}

        for i in range(count):
            name = sub_names[i]
            obj = obj_map.get(name)
            if obj is None:
                print(f"Warning: no matching object for submesh '{name}', skipping")
                continue
            _apply_shapekeys_to_object(obj, data, prefix=f"sub{i}_", replace_values=replace_values)

        return

    # Single object format
    obj = target[0] if isinstance(target, (list, tuple)) else target
    if obj is None or obj.type != 'MESH':
        raise TypeError("Object must be a Mesh")
    _apply_shapekeys_to_object(obj, data, replace_values=replace_values)


# OPERATORS

class CP77_OT_NpzImportMesh(bpy.types.Operator, ImportHelper):
    """Import Mesh from NPZ format"""
    bl_idname = "cp77.npz_import_mesh"
    bl_label = "Import Mesh (.npz)"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".npz"
    filter_glob: StringProperty(default="*.npz", options={'HIDDEN'})

    def execute(self, context):
        try:
            coll, objects = load_mesh_npz(context, self.filepath)
            names = [o.name for o in objects]
            self.report({'INFO'}, f"Imported: {', '.join(names)}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class CP77_OT_NpzImportShapeKeys(bpy.types.Operator, ImportHelper):
    """Import Shape Keys from NPZ format"""
    bl_idname = "cp77.npz_import_shapekeys"
    bl_label = "Import ShapeKeys (.npz)"
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = ".npz"
    filter_glob: StringProperty(default="*.npz", options={'HIDDEN'})
    replace_values: BoolProperty(name="Restore Values", default=True)

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'MESH'

    def execute(self, context):
        try:
            load_shapekeys_npz(context.object, self.filepath, replace_values=self.replace_values)
            self.report({'INFO'}, f"Loaded shape keys: {self.filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


# BASE CHARACTER RESOURCES

_BASE_CHAR_RESOURCES = {
    'MASC': {
        'body_mesh': "t0_000_ma_base__full_hql.npz",
        'body_sk': "ma_base_shapekeys.npz",
        'head_parts': [
            ("h0_000_ma_c__basehead.npz", "h0_000_pma__morphs.npz"),
            ("he_000_ma_c__basehead.npz", "he_000_ma_morphs.npz"),
            ("ht_000_ma_c__basehead.npz", "ht_000_ma_morphs.npz"),
            ("heb_000_ma_c__basehead.npz", "heb_000_ma_morphs.npz"),
            ],
        },
    'FEM': {
        'body_mesh': "t0_000_wa_base__full_hql.npz",
        'body_sk': "wa_base_shapekeys.npz",
        'head_parts': [
            ("h0_000_wa_c__basehead.npz", "wa_basehead__shapekeys.npz"),
            ("he_000_wa_c__basehead.npz", "he_000_wa__morphs.npz"),
            ("ht_000_wa_c__basehead.npz", "ht_000_wa__morphs.npz"),
            ("heb_000_wa_c__basehead.npz", "heb_000_wa__morphs.npz"),
            ],
        },
    }


class CP77_OT_LoadBaseCharacter(bpy.types.Operator):
    """Load a CP77 base character mesh with shape keys"""
    bl_idname = "cp77.load_base_character"
    bl_label = "Load Base Character"
    bl_options = {'REGISTER', 'UNDO'}

    gender: EnumProperty(
            name="Character",
            items=[
                ('MASC', "Masculine", "Male body base"),
                ('FEM', "Feminine", "Female body base"),
                ],
            default='FEM'
            )

    load_head: BoolProperty(name="Head", default=True)
    load_body: BoolProperty(name="Body", default=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if not self.load_head and not self.load_body:
            self.report({'WARNING'}, "Nothing selected to load")
            return {'CANCELLED'}

        resources_dir = get_char_dir()
        res = _BASE_CHAR_RESOURCES[self.gender]
        loaded = []
        char_props = context.scene.cp77_character_shape

        try:
            if self.load_body:
                _coll, body_objects = load_mesh_npz(context, os.path.join(resources_dir, res['body_mesh']))
                load_shapekeys_npz(body_objects, os.path.join(resources_dir, res['body_sk']))
                loaded.extend(o.name for o in body_objects)

                # Track first body mesh for breast slider
                char_props.body_mesh_name = body_objects[0].name if body_objects else ""
                char_props.breasts = 0

            if self.load_head:
                head_names = []
                for mesh_file, sk_file in res['head_parts']:
                    _coll, objects = load_mesh_npz(context, os.path.join(resources_dir, mesh_file))
                    load_shapekeys_npz(objects, os.path.join(resources_dir, sk_file))
                    head_names.extend(o.name for o in objects)
                    loaded.extend(o.name for o in objects)

                char_props.head_mesh_names = ";".join(head_names)
                char_props.eyes = 0
                char_props.nose = 0
                char_props.mouth = 0
                char_props.jaw = 0
                char_props.ears = 0

        except FileNotFoundError as e:
            self.report({'ERROR'}, f"Resource file not found: {e.filename}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        self.report({'INFO'}, f"Loaded: {', '.join(loaded)}")
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "gender", expand=True)
        row = layout.row(align=True)
        row.prop(self, "load_head")
        row.prop(self, "load_body")
