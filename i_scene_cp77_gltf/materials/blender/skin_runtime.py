from __future__ import annotations

import logging

import bpy
import numpy as np

from ...blender import shader_nodes
from ...blender.identity import rna_identity, rna_is_live
from ...blender.mesh import PREVIEW_ONLY_FLAG
from ...blender.naming import fit_id_name
from ...blender.transactions import track_created_datablock
from ...core.log import get_logger, log_once
from ...material_types.skin_regions import (
    DEFAULT_FACE_REGIONS,
    DEFAULT_FACE_REGIONSET_PATH,
    REGION_ATTRIBUTE_COUNT,
    REGIONS_PER_ATTRIBUTE,
    evaluate_region_influences,
    region_attribute_name,
)
from ...material_types.skin_wrinkles import (
    TRACK_NODE_PREFIX,
    WRINKLE_SQUASH_ATTRIBUTE,
    WRINKLE_STRETCH_ATTRIBUTE,
)
from .helper_caches import register_helper_cache

_WRINKLE_GROUPS = {}
_REGION_ATTRIBUTE_VERSION = 1
_WRINKLE_RUNTIME_VERSION = 3
_REGION_ATTRIBUTE_VERSION_PROP = "_cp77_skin_wrinkle_regions_version"
_REGION_ATTRIBUTE_SET_PROP = "_cp77_skin_wrinkle_region_set"
_REGION_ATTRIBUTE_DOMAIN_PROP = "_cp77_skin_wrinkle_region_domain"
_REGION_ATTRIBUTE_UV_PROP = "_cp77_skin_wrinkle_region_uv"
_MODIFIER_NAME = "CP77 Skin Wrinkles"
_GROUP_PREFIX = "CP77 Skin Wrinkles::"
_LOG = get_logger(__name__)


def clear_skin_runtime_cache():
    _WRINKLE_GROUPS.clear()


def skin_runtime_cache_stats():
    return {"armature_groups": len(_WRINKLE_GROUPS)}


register_helper_cache(
    "skin_runtime",
    clear=clear_skin_runtime_cache,
    stats=skin_runtime_cache_stats,
)


def _is_live_armature(armature):
    try:
        return rna_is_live(armature) and armature.type == "ARMATURE"
    except ReferenceError:
        return False


def _pointer_token(value):
    return f"{rna_identity(value):x}"


def _uses_wrinkle_regions(material):
    try:
        return (
            rna_is_live(material)
            and int(material.get("cp77_skin_wrinkle_region_count", 0) or 0) > 0
        )
    except (ReferenceError, ValueError):
        return False


def _driver_path(property_name):
    escaped = str(property_name).replace("\\", "\\\\").replace('"', '\\"')
    return f'["{escaped}"]'


def _bind_track_node(node, armature, track_name):
    output = node.outputs["Value"]
    try:
        output.driver_remove("default_value")
    except (AttributeError, RuntimeError, TypeError):
        log_once(
            _LOG,
            logging.DEBUG,
            "_bind_track_node",
            "_bind_track_node skipped what it could not read or write",
            exc_info=True,
        )

    if track_name not in armature:
        output.default_value = 0.0
        return False

    output.default_value = float(armature.get(track_name, 0.0))
    fcurve = output.driver_add("default_value")
    driver = fcurve.driver
    driver.type = "AVERAGE"
    while len(driver.variables):
        driver.variables.remove(driver.variables[0])
    variable = driver.variables.new()
    variable.name = "track"
    variable.type = "SINGLE_PROP"
    target = variable.targets[0]
    target.id = armature
    target.data_path = _driver_path(track_name)
    return True


def _sum_fields(nodes, links, fields, name, location):
    fields = list(fields)
    if not fields:
        return None
    total = fields[0]
    x, y = location
    for index, field in enumerate(fields[1:], start=1):
        add = shader_nodes.math(
            nodes,
            links,
            "ADD",
            name=f"{name} Sum {index + 1}",
            location=(x + index * 110, y),
        ).node
        links.new(total, add.inputs["Value"])
        links.new(field, shader_nodes.socket_by_identifier(add.inputs, "Value_001"))
        total = add.outputs["Value"]
    return shader_nodes.clamp(
        nodes,
        links,
        total,
        name=f"{name} Clamp",
        location=(x + len(fields) * 110 + 80, y),
    )


def _wrinkle_group_name(armature, domain):
    domain = "POINT" if domain == "POINT" else "CORNER"
    return fit_id_name(f"{_GROUP_PREFIX}{armature.name}", f"::{domain}")


def _build_wrinkle_group(armature, domain):
    domain = "POINT" if domain == "POINT" else "CORNER"
    group_name = _wrinkle_group_name(armature, domain)
    group = track_created_datablock(
        "node_groups",
        bpy.data.node_groups.new(group_name, "GeometryNodeTree"),
    )
    if hasattr(group, "is_modifier"):
        group.is_modifier = True
    # The wrinkle amounts only drive the skin shader; exported geometry never carries them.
    group[PREVIEW_ONLY_FLAG] = True
    group["cp77_skin_wrinkle_runtime_version"] = _WRINKLE_RUNTIME_VERSION
    group["cp77_skin_wrinkle_armature"] = armature.name
    group["cp77_skin_wrinkle_region_domain"] = domain
    group["cp77_skin_wrinkle_region_set"] = DEFAULT_FACE_REGIONSET_PATH

    group.interface.new_socket(
        name="Geometry",
        in_out="INPUT",
        socket_type="NodeSocketGeometry",
    )
    group.interface.new_socket(
        name="Geometry",
        in_out="OUTPUT",
        socket_type="NodeSocketGeometry",
    )

    nodes = group.nodes
    links = group.links
    group_input = nodes.new("NodeGroupInput")
    group_input.location = (-2400, 500)
    group_output = nodes.new("NodeGroupOutput")
    group_output.location = (2200, 500)

    region_outputs = []
    for pack_index in range(REGION_ATTRIBUTE_COUNT):
        y = 500 - pack_index * 170
        attribute = nodes.new("GeometryNodeInputNamedAttribute")
        attribute.data_type = "FLOAT_VECTOR"
        attribute.name = f"Wrinkle Regions {pack_index:02d}"
        attribute.label = attribute.name
        attribute.location = (-2400, y - 300)
        attribute.inputs["Name"].default_value = region_attribute_name(pack_index)

        split = nodes.new("ShaderNodeSeparateXYZ")
        split.name = f"Wrinkle Regions {pack_index:02d} Split"
        split.label = split.name
        split.location = (-2180, y - 300)
        links.new(attribute.outputs["Attribute"], split.inputs["Vector"])
        region_outputs.extend(
            (split.outputs["X"], split.outputs["Y"], split.outputs["Z"])
        )
    region_outputs = region_outputs[: len(DEFAULT_FACE_REGIONS)]

    squash_terms = []
    stretch_terms = []
    for index, ((track_name, is_stretch, _parts), region_output) in enumerate(
        zip(DEFAULT_FACE_REGIONS, region_outputs)
    ):
        y = 950 - index * 75
        track = nodes.new("ShaderNodeValue")
        track.name = f"{TRACK_NODE_PREFIX}{track_name}"
        track.label = track_name
        track.location = (-1850, y)
        track.outputs["Value"].default_value = 0.0

        weighted = shader_nodes.math(
            nodes, links, "MULTIPLY", name=f"{track_name} Weighted", location=(-1630, y)
        ).node
        links.new(region_output, weighted.inputs["Value"])
        links.new(
            track.outputs["Value"],
            shader_nodes.socket_by_identifier(weighted.inputs, "Value_001"),
        )
        (stretch_terms if is_stretch else squash_terms).append(
            weighted.outputs["Value"]
        )

    squash = _sum_fields(nodes, links, squash_terms, "Wrinkle Squash", (-1350, 620))
    stretch = _sum_fields(nodes, links, stretch_terms, "Wrinkle Stretch", (-1350, 300))

    geometry = group_input.outputs["Geometry"]
    stores = (
        (WRINKLE_SQUASH_ATTRIBUTE, squash, 1450, 620),
        (WRINKLE_STRETCH_ATTRIBUTE, stretch, 1760, 300),
    )
    for attribute_name, value, x, y in stores:
        store = nodes.new("GeometryNodeStoreNamedAttribute")
        store.data_type = "FLOAT"
        store.domain = domain
        store.name = f"Store {attribute_name}"
        store.label = store.name
        store.location = (x, y)
        store.inputs["Selection"].default_value = True
        store.inputs["Name"].default_value = attribute_name
        links.new(geometry, store.inputs["Geometry"])
        if value is not None:
            links.new(value, store.inputs["Value"])
        geometry = store.outputs["Geometry"]
    links.new(geometry, group_output.inputs["Geometry"])
    return group


def _refresh_wrinkle_group(group, armature):
    present = tuple(
        track_name
        for track_name, _is_stretch, _parts in DEFAULT_FACE_REGIONS
        if track_name in armature
    )
    signature = "\x1f".join(present)
    armature_pointer = _pointer_token(armature)
    if (
        group.get("cp77_skin_track_signature", "") == signature
        and str(group.get("cp77_skin_track_armature_pointer", "") or "")
        == armature_pointer
    ):
        return int(group.get("cp77_skin_bound_track_count", 0) or 0)

    bound = 0
    for track_name, _is_stretch, _parts in DEFAULT_FACE_REGIONS:
        node = group.nodes.get(f"{TRACK_NODE_PREFIX}{track_name}")
        if node is None:
            continue
        if _bind_track_node(node, armature, track_name):
            bound += 1
    group["cp77_skin_track_signature"] = signature
    group["cp77_skin_track_armature_pointer"] = armature_pointer
    group["cp77_skin_bound_track_count"] = bound
    return bound


def _wrinkle_group_for_armature(armature, domain):
    domain = "POINT" if domain == "POINT" else "CORNER"
    key = (rna_identity(armature), domain)
    group = _WRINKLE_GROUPS.get(key)
    if not rna_is_live(group):
        group = None
    if group is None:
        expected_name = _wrinkle_group_name(armature, domain)
        candidate = bpy.data.node_groups.get(expected_name)
        if (
            rna_is_live(candidate)
            and candidate.bl_idname == "GeometryNodeTree"
            and int(candidate.get("cp77_skin_wrinkle_runtime_version", 0) or 0)
            == _WRINKLE_RUNTIME_VERSION
            and candidate.get("cp77_skin_wrinkle_armature") == armature.name
            and candidate.get("cp77_skin_wrinkle_region_domain") == domain
        ):
            group = candidate
            if not group.get(PREVIEW_ONLY_FLAG):
                # Groups saved before the flag existed.
                group[PREVIEW_ONLY_FLAG] = True
        else:
            group = _build_wrinkle_group(armature, domain)
        _WRINKLE_GROUPS[key] = group
    _refresh_wrinkle_group(group, armature)
    return group


def _region_attributes_are_current(mesh, uv_name):
    try:
        if (
            int(mesh.get(_REGION_ATTRIBUTE_VERSION_PROP, 0) or 0)
            != _REGION_ATTRIBUTE_VERSION
        ):
            return False
        if mesh.get(_REGION_ATTRIBUTE_SET_PROP) != DEFAULT_FACE_REGIONSET_PATH:
            return False
        if mesh.get(_REGION_ATTRIBUTE_UV_PROP) != uv_name:
            return False
        domain = str(mesh.get(_REGION_ATTRIBUTE_DOMAIN_PROP, "") or "")
        if domain not in {"POINT", "CORNER"}:
            return False
        expected_count = len(mesh.vertices) if domain == "POINT" else len(mesh.loops)
        for index in range(REGION_ATTRIBUTE_COUNT):
            attribute = mesh.attributes.get(region_attribute_name(index))
            if (
                attribute is None
                or attribute.domain != domain
                or attribute.data_type != "FLOAT_VECTOR"
                or len(attribute.data) != expected_count
            ):
                return False
        return True
    except (AttributeError, ReferenceError, TypeError, ValueError):
        log_once(
            _LOG,
            logging.DEBUG,
            "_region_attributes_are_current",
            "_region_attributes_are_current skipped what it could not read or write",
            exc_info=True,
        )
        return False


def _region_source_uv(mesh, uv_layer):
    loop_count = len(mesh.loops)
    loop_uv = np.empty(loop_count * 2, dtype=np.float32)
    uv_layer.uv.foreach_get("vector", loop_uv)
    loop_uv = loop_uv.reshape((-1, 2))

    vertex_count = len(mesh.vertices)
    loop_vertices = np.empty(loop_count, dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", loop_vertices)
    first_loop = np.full(vertex_count, loop_count, dtype=np.int32)
    np.minimum.at(first_loop, loop_vertices, np.arange(loop_count, dtype=np.int32))
    valid = first_loop < loop_count
    point_uv = np.zeros((vertex_count, 2), dtype=np.float32)
    point_uv[valid] = loop_uv[first_loop[valid]]
    if np.allclose(loop_uv, point_uv[loop_vertices], rtol=0.0, atol=1e-6):
        return "POINT", point_uv
    return "CORNER", loop_uv


def ensure_skin_wrinkle_region_attributes(mesh):
    if mesh is None or not len(getattr(mesh, "loops", ())):
        return False
    uv_layers = getattr(mesh, "uv_layers", None)
    if not uv_layers:
        return False

    uv_layer = uv_layers.active or uv_layers[0]
    if _region_attributes_are_current(mesh, uv_layer.name):
        return True

    domain, source_uv = _region_source_uv(mesh, uv_layer)
    region_values = evaluate_region_influences(source_uv)

    for pack_index in range(REGION_ATTRIBUTE_COUNT):
        name = region_attribute_name(pack_index)
        attribute = mesh.attributes.get(name)
        if attribute is not None and (
            attribute.domain != domain or attribute.data_type != "FLOAT_VECTOR"
        ):
            mesh.attributes.remove(attribute)
            attribute = None
        if attribute is None:
            attribute = mesh.attributes.new(
                name=name,
                type="FLOAT_VECTOR",
                domain=domain,
            )

        packed = np.zeros((len(source_uv), 3), dtype=np.float32)
        start = pack_index * REGIONS_PER_ATTRIBUTE
        stop = min(start + REGIONS_PER_ATTRIBUTE, region_values.shape[1])
        packed[:, : stop - start] = region_values[:, start:stop]
        attribute.data.foreach_set("vector", packed.reshape(-1))

    mesh[_REGION_ATTRIBUTE_VERSION_PROP] = _REGION_ATTRIBUTE_VERSION
    mesh[_REGION_ATTRIBUTE_SET_PROP] = DEFAULT_FACE_REGIONSET_PATH
    mesh[_REGION_ATTRIBUTE_DOMAIN_PROP] = domain
    mesh[_REGION_ATTRIBUTE_UV_PROP] = uv_layer.name
    return True


def _object_armature(obj):
    for modifier in getattr(obj, "modifiers", ()):
        if getattr(modifier, "type", None) != "ARMATURE":
            continue
        armature = getattr(modifier, "object", None)
        if _is_live_armature(armature):
            return armature
    parent = getattr(obj, "parent", None)
    return parent if _is_live_armature(parent) else None


def _ensure_wrinkle_modifier(obj, armature):
    domain = str(obj.data.get(_REGION_ATTRIBUTE_DOMAIN_PROP, "CORNER") or "CORNER")
    group = _wrinkle_group_for_armature(armature, domain)
    modifier = None
    for candidate in getattr(obj, "modifiers", ()):
        if getattr(candidate, "type", None) != "NODES":
            continue
        if (
            candidate.name == _MODIFIER_NAME
            or getattr(candidate, "node_group", None) is group
        ):
            modifier = candidate
            break
    if modifier is None:
        modifier = obj.modifiers.new(name=_MODIFIER_NAME, type="NODES")
    modifier.name = _MODIFIER_NAME
    modifier.node_group = group

    modifiers = obj.modifiers
    wrinkle_index = next(
        (index for index, item in enumerate(modifiers) if item is modifier),
        -1,
    )
    armature_index = next(
        (
            index
            for index, item in enumerate(modifiers)
            if getattr(item, "type", None) == "ARMATURE"
        ),
        -1,
    )
    if wrinkle_index >= 0 and armature_index >= 0 and wrinkle_index > armature_index:
        modifiers.move(wrinkle_index, armature_index)
    return modifier


def bind_skin_materials_for_object(obj, armature=None):
    if getattr(obj, "type", None) != "MESH":
        return 0

    slots = tuple(getattr(obj, "material_slots", ()))
    if not any(
        _uses_wrinkle_regions(getattr(slot, "material", None)) for slot in slots
    ):
        return 0

    try:
        if not ensure_skin_wrinkle_region_attributes(obj.data):
            return 0
        armature = armature if _is_live_armature(armature) else _object_armature(obj)
        if armature is None:
            return 0
        _ensure_wrinkle_modifier(obj, armature)
        return 1
    except Exception:
        _LOG.warning(
            "Skin wrinkle runtime binding failed for %s; importing without dynamic wrinkles",
            getattr(obj, "name", "<mesh>"),
            exc_info=True,
        )
        return 0


def _descendants(root):
    pending = list(getattr(root, "children", ()))
    seen = set()
    while pending:
        obj = pending.pop()
        key = rna_identity(obj)
        if key in seen:
            continue
        seen.add(key)
        yield obj
        pending.extend(getattr(obj, "children", ()))


def bind_skin_materials_for_armature(armature):
    if not _is_live_armature(armature):
        return 0
    changed = 0
    for obj in _descendants(armature):
        if getattr(obj, "type", None) != "MESH":
            continue
        if _object_armature(obj) is not armature:
            continue
        changed += bind_skin_materials_for_object(obj, armature)
    return changed
