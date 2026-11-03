from hashlib import blake2b

import numpy as np

from ..assetio.values import json_object
from .identity import authored_material_name

_UV_EPSILON = 1.0e-12
SOURCE_SHADING_SIGNATURE_KEY = "cp77_source_shading_signature"

SOURCE_NORMAL_ATTRIBUTE = ".cp77_source_normal"
SOURCE_TANGENT_ATTRIBUTE = ".cp77_source_tangent"
SOURCE_TANGENT_SIGN_ATTRIBUTE = ".cp77_source_tangent_sign"
SOURCE_GEOMETRY_SIGNATURE_KEY = "cp77_source_geometry_signature"
SOURCE_TANGENT_FRAME_SIGNATURE_KEY = "cp77_source_tangent_frame_signature"
SOURCE_MESH_EXTRAS_KEY = "cp77_direct_mesh_extras"
SOURCE_SKIN_EXTRAS_KEY = "cp77_direct_skin_extras"
SOURCE_SKIN_BINDING_KEY = "cp77_direct_mesh_skin_binding"
MESH_SOURCE_REST_SNAPSHOT_KEY = "cp77_direct_mesh_source_rest_json"
SOURCE_VERTEX_INDEX_ATTRIBUTE = ".cp77_source_vertex_index"
SOURCE_VERTEX_SIGNATURE_KEY = "cp77_source_vertex_signature"
# Shading tangent-frame attributes the importer writes and the material graphs read.
TANGENT_SIGN_ATTRIBUTE = "CP77_TangentSign"
TANGENT_SIGN_VALID_ATTRIBUTE = "CP77_TangentSignValid"
SOURCE_FRAME_VALID_ATTRIBUTE = "CP77_SourceFrameValid"
# Set on a Geometry Nodes group that only previews the mesh in Blender; exporters drop modifiers using it.
PREVIEW_ONLY_FLAG = "cp77_preview_only"


def store_source_vertex_indices(mesh, indices):
    """Record aliases introduced to keep repeated source faces editable in Blender"""
    values = np.asarray(indices, dtype=np.int32)
    if values.shape != (len(mesh.vertices),):
        raise ValueError("Source vertex identities must match the mesh vertex count.")
    attribute = mesh.attributes.new(
        name=SOURCE_VERTEX_INDEX_ATTRIBUTE, type="INT", domain="POINT"
    )
    attribute.data.foreach_set("value", values)
    mesh[SOURCE_VERTEX_SIGNATURE_KEY] = geometry_signature(mesh)


def source_vertex_indices(mesh, current_geometry_signature):
    """Reuse source identities only while the imported positions and topology match"""
    if mesh.get(SOURCE_VERTEX_SIGNATURE_KEY, "") != current_geometry_signature:
        return None
    attribute = mesh.attributes.get(SOURCE_VERTEX_INDEX_ATTRIBUTE)
    if (
        attribute is None
        or attribute.data_type != "INT"
        or attribute.domain != "POINT"
        or len(attribute.data) != len(mesh.vertices)
    ):
        return None
    values = np.empty(len(mesh.vertices), dtype=np.int32)
    attribute.data.foreach_get("value", values)
    return values if np.all(values >= 0) else None


def shading_signature(mesh):
    normals = getattr(mesh, "corner_normals", None)
    if normals is None or not len(mesh.loops) or len(normals) != len(mesh.loops):
        return ""
    values = np.empty(len(normals) * 3, dtype=np.float32)
    normals.foreach_get("vector", values)
    return _mesh_signature(b"CP77Shading", values)


def is_mesh(value):
    return value is not None and getattr(value, "type", None) == "MESH"


def is_preview_only_modifier(modifier):
    group = getattr(modifier, "node_group", None)
    return (
        getattr(modifier, "type", "") == "NODES"
        and group is not None
        and bool(group.get(PREVIEW_ONLY_FLAG))
    )


def _vertex_xy(mesh):
    count = len(mesh.vertices)
    if not count:
        return np.empty((0, 2), dtype=np.float32)
    coordinates = np.empty(count * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", coordinates)
    return coordinates.reshape(count, 3)[:, :2]


def _bounds_scale_offset(xy):
    if not len(xy):
        return None
    minimum = np.min(xy, axis=0)
    maximum = np.max(xy, axis=0)
    extent = maximum - minimum
    if np.any(np.abs(extent) <= _UV_EPSILON):
        return None
    scale = 1.0 / extent
    offset = -minimum * scale
    return np.asarray((scale[0], scale[1], offset[0], offset[1]), dtype=np.float32)


def _coerce_scale_offset(value):
    if value is None:
        return None
    try:
        result = np.asarray(value, dtype=np.float32).reshape(-1)
    except (TypeError, ValueError):
        return None
    if result.size < 4 or not np.all(np.isfinite(result[:4])):
        return None
    return result[:4]


def _write_uv_layer(mesh, vertex_uv):
    loop_count = len(mesh.loops)
    if not loop_count:
        return False
    loop_vertices = np.empty(loop_count, dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", loop_vertices)
    loop_uv = np.ascontiguousarray(vertex_uv[loop_vertices], dtype=np.float32)
    layer = mesh.uv_layers.new(name="UVMap")
    layer.uv.foreach_set("vector", loop_uv.reshape(-1))
    mesh.update()
    return True


def uv_by_bounds(objects, *, scale_offset=None):
    explicit_scale_offset = _coerce_scale_offset(scale_offset)
    updated = 0
    for obj in objects:
        if not is_mesh(obj):
            continue
        mesh = obj.data
        if mesh.uv_layers:
            continue
        xy = _vertex_xy(mesh)
        if not len(xy):
            continue
        transform = explicit_scale_offset
        if transform is None:
            transform = _bounds_scale_offset(xy)
        if transform is None:
            continue
        vertex_uv = xy * transform[:2] + transform[2:4]
        if _write_uv_layer(mesh, vertex_uv):
            updated += 1
    return updated


def _mesh_signature(person, *arrays):
    digest = blake2b(digest_size=16, person=person)
    for values in arrays:
        contiguous = np.ascontiguousarray(values)
        digest.update(np.asarray(contiguous.shape, dtype=np.int64).tobytes())
        digest.update(contiguous.tobytes())
    return digest.hexdigest()


def _geometry_signature_arrays(mesh):
    if not len(mesh.vertices) or not len(mesh.loops) or not len(mesh.polygons):
        return None
    positions = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", positions)
    loop_vertices = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", loop_vertices)
    polygon_starts = np.empty(len(mesh.polygons), dtype=np.int32)
    polygon_totals = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("loop_start", polygon_starts)
    mesh.polygons.foreach_get("loop_total", polygon_totals)
    return positions, loop_vertices, polygon_starts, polygon_totals


def geometry_and_tangent_frame_signatures(mesh, *, uv_name="UVMap"):
    arrays = _geometry_signature_arrays(mesh)
    if arrays is None:
        return "", ""

    geometry = _mesh_signature(b"CP77Geometry", *arrays)
    uv_layer = mesh.uv_layers.get(uv_name) if getattr(mesh, "uv_layers", None) else None
    if uv_layer is None:
        return geometry, ""

    uv = np.empty(len(mesh.loops) * 2, dtype=np.float32)
    uv_layer.uv.foreach_get("vector", uv)
    tangent = _mesh_signature(b"CP77TangentFrame", *arrays, uv)
    return geometry, tangent


def geometry_signature(mesh):
    arrays = _geometry_signature_arrays(mesh)
    if arrays is None:
        return ""
    return _mesh_signature(b"CP77Geometry", *arrays)


def export_material_names(obj) -> list[str]:
    """The material names a mesh export writes for the object"""
    source_names = json_object(obj.get(SOURCE_MESH_EXTRAS_KEY)).get("materialNames")
    if isinstance(source_names, list):
        return [str(value) for value in source_names]
    explicit = obj.get("cp77_material_name")
    if isinstance(explicit, str) and explicit:
        return [explicit]
    return [
        authored_material_name(slot.material)
        for slot in obj.material_slots
        if slot.material is not None
    ]


def _attribute_arrays(mesh):
    """The per-vertex data an export writes beside the geometry"""
    arrays = []
    for layer in mesh.uv_layers:
        values = np.empty(len(layer.uv) * 2, dtype=np.float32)
        layer.uv.foreach_get("vector", values)
        arrays.extend(
            (np.frombuffer(layer.name.encode("utf-8"), dtype=np.uint8), values)
        )
    for attribute in mesh.color_attributes:
        values = np.empty(len(attribute.data) * 4, dtype=np.float32)
        attribute.data.foreach_get("color", values)
        arrays.extend(
            (np.frombuffer(attribute.name.encode("utf-8"), dtype=np.uint8), values)
        )
    if getattr(mesh, "has_custom_normals", False):
        normals = np.empty(len(mesh.corner_normals) * 3, dtype=np.float32)
        mesh.corner_normals.foreach_get("vector", normals)
        arrays.append(normals)
    if mesh.shape_keys is not None:
        for block in mesh.shape_keys.key_blocks:
            values = np.empty(len(block.data) * 3, dtype=np.float32)
            block.data.foreach_get("co", values)
            arrays.extend(
                (np.frombuffer(block.name.encode("utf-8"), dtype=np.uint8), values)
            )
    return arrays


def deform_weights(mesh, weighted):
    """Every vertex's group assignments in vertex order"""
    counts, groups, weights = [], [], []
    for vertex in mesh.vertices if weighted else ():
        elements = vertex.groups
        counts.append(len(elements))
        for element in elements:
            groups.append(element.group)
            weights.append(element.weight)
    pairs = np.stack(
        (
            np.repeat(np.arange(len(counts), dtype=np.int64), counts),
            np.asarray(groups, dtype=np.int64),
        ),
        axis=1,
    )
    return pairs, np.asarray(weights, dtype=np.float32)


def _export_mesh_arrays(mesh, weighted):
    geometry = np.frombuffer(geometry_signature(mesh).encode("ascii"), dtype=np.uint8)
    return (geometry, *deform_weights(mesh, weighted)), tuple(_attribute_arrays(mesh))


def export_signature(obj, *, mesh_cache=None):
    """A fingerprint of what a mesh export writes"""
    mesh = obj.data
    arrays = mesh_cache.get(mesh.as_pointer()) if mesh_cache is not None else None
    if arrays is None:
        # Objects sharing a mesh share its vertex groups.
        arrays = _export_mesh_arrays(mesh, bool(obj.vertex_groups))
        if mesh_cache is not None:
            mesh_cache[mesh.as_pointer()] = arrays
    (geometry, groups, weights), attributes = arrays
    names = "".join(group.name for group in obj.vertex_groups)
    materials = "".join(export_material_names(obj))
    return _mesh_signature(
        b"CP77Export",
        geometry,
        groups,
        weights,
        np.frombuffer(names.encode("utf-8"), dtype=np.uint8),
        np.frombuffer(materials.encode("utf-8"), dtype=np.uint8),
        *attributes,
    )


def refresh_tangent_sign_attributes(
    mesh,
    *,
    uv_name="UVMap",
    sign_name=TANGENT_SIGN_ATTRIBUTE,
    valid_name=TANGENT_SIGN_VALID_ATTRIBUTE,
):
    attributes = getattr(mesh, "attributes", None)
    uv_layers = getattr(mesh, "uv_layers", None)
    if attributes is None or uv_layers is None:
        return False

    uv_layer = uv_layers.get(uv_name)
    if uv_layer is None or not len(mesh.loops) or not hasattr(mesh, "calc_tangents"):
        return False

    try:
        mesh.calc_tangents(uvmap=uv_name)
    except (RuntimeError, TypeError):
        return False
    try:
        signs = np.empty(len(mesh.loops), dtype=np.float32)
        mesh.loops.foreach_get("bitangent_sign", signs)
    finally:
        free_tangents = getattr(mesh, "free_tangents", None)
        if free_tangents is not None:
            free_tangents()

    for name in (sign_name, valid_name):
        existing = attributes.get(name)
        if existing is not None:
            attributes.remove(existing)

    sign = attributes.new(name=sign_name, type="FLOAT", domain="CORNER")
    sign.data.foreach_set("value", signs)
    valid = attributes.new(name=valid_name, type="FLOAT", domain="CORNER")
    valid.data.foreach_set("value", np.ones(len(mesh.loops), dtype=np.float32))
    return True


def resolve_color_attribute_name(
    names,
    *,
    canonical="Color",
    aliases=("COLOR_0",),
    active_name="",
):
    available = tuple(str(name) for name in names if str(name))
    if canonical in available:
        return canonical
    for alias in aliases:
        if alias in available:
            return alias
    if active_name and active_name in available:
        return active_name
    if len(available) == 1:
        return available[0]
    return ""


def ensure_color_attribute_alias(
    mesh,
    *,
    canonical="Color",
    aliases=("COLOR_0",),
):
    color_attributes = getattr(mesh, "color_attributes", None)
    if color_attributes is None:
        return ""
    names = tuple(getattr(attribute, "name", "") for attribute in color_attributes)
    active = getattr(color_attributes, "active_color", None)
    source_name = resolve_color_attribute_name(
        names,
        canonical=canonical,
        aliases=aliases,
        active_name=getattr(active, "name", ""),
    )
    if not source_name:
        return ""
    if source_name == canonical:
        return source_name

    source = color_attributes.get(source_name)
    if source is None:
        return ""
    existing = color_attributes.get(canonical)
    if existing is not None:
        return canonical
    alias = color_attributes.new(
        name=canonical,
        type=source.data_type,
        domain=source.domain,
    )
    count = len(source.data)
    values = np.empty(count * 4, dtype=np.float32)
    field = "color_srgb" if source.data_type == "BYTE_COLOR" else "color"
    source.data.foreach_get(field, values)
    alias.data.foreach_set(field, values)
    return source_name


def set_constant_float_attribute(mesh, name, value, *, domain="POINT"):
    attributes = getattr(mesh, "attributes", None)
    if attributes is None:
        return False
    attribute = attributes.get(name)
    if attribute is not None and (
        attribute.domain != domain or attribute.data_type != "FLOAT"
    ):
        attributes.remove(attribute)
        attribute = None
    if attribute is None:
        attribute = attributes.new(name=name, type="FLOAT", domain=domain)
    attribute.data.foreach_set(
        "value",
        np.full(len(attribute.data), float(value), dtype=np.float32),
    )
    return True
