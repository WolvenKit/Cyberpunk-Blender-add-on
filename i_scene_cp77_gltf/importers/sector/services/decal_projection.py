from __future__ import annotations

import math
import time
from dataclasses import dataclass

import bpy
import numpy as np
from mathutils import Matrix, Vector

from ....bartmoss.clipping import (
    EPSILON,
    BoundsGrid,
    clip_triangles_to_box,
    triangle_box_classes_and_planes,
)
from ....blender.custom_normals import set_custom_normals_from_vertices
from ....blender.matrix import object_world_matrix
from ....blender.mesh import refresh_tangent_sign_attributes
from ....blender.naming import fit_id_name
from ....blender.transactions import track_created_datablock
from ....core.log import debug_exception, get_logger, log_once
from ....material_types.decal_composite import (
    DECAL_UV_LAYER,
    PROJECTION_COVERAGE_ATTRIBUTE,
    PROJECTOR_BITANGENT_ATTRIBUTE,
    PROJECTOR_FRAME_VALID_ATTRIBUTE,
    PROJECTOR_TANGENT_ATTRIBUTE,
    PROJECTOR_UP_ATTRIBUTE,
    composite_material,
    decal_surface_material,
    requires_receiver_composite,
)
from .decal_projection_math import (
    normal_threshold_radians,
    projected_uv_coverage_array,
    projection_clip_bounds,
    projection_padding,
    projection_surface_offset,
    stacked_surface_offsets,
)

_LOG = get_logger(__name__)

COMPOSITE_BUILD_PROFILE_DEFAULTS = {
    "composite_copy_seconds": 0.0,
    "composite_prepare_seconds": 0.0,
    "composite_factors_seconds": 0.0,
    "composite_adapt_seconds": 0.0,
    "composite_finalize_seconds": 0.0,
    "composite_clone_seconds": 0.0,
    "composite_clone_create_seconds": 0.0,
    "composite_clone_properties_seconds": 0.0,
    "composite_clone_defaults_seconds": 0.0,
    "composite_clone_drivers_seconds": 0.0,
    "composite_clone_special_seconds": 0.0,
    "composite_clone_nodes": 0,
    "composite_clone_links": 0,
}


@dataclass(slots=True)
class PendingDecalProjection:
    projector: object
    material: object | None
    data: dict
    node_index: int
    instance_index: int


@dataclass(slots=True)
class _TriangleBatch:
    positions: np.ndarray
    normals: np.ndarray
    materials: tuple
    uvs: dict
    colors: dict


@dataclass(slots=True)
class _TriangleBatchRef:
    batch: _TriangleBatch
    indices: np.ndarray
    local_positions: np.ndarray | None = None


@dataclass(slots=True, frozen=True)
class _ReceiverMesh:
    object: object
    matrix_world: Matrix
    bounds: tuple


@dataclass(slots=True)
class _ProjectionMeshArrays:
    mesh: object
    coordinates: np.ndarray
    vertex_normals: np.ndarray
    corner_normals: np.ndarray | None
    uv_arrays: dict
    color_arrays: dict
    triangle_vertices: np.ndarray
    triangle_loops: np.ndarray
    triangle_material_indices: np.ndarray


@dataclass(slots=True, frozen=True)
class _ProjectorLocalBounds:
    inverse_rotation: np.ndarray
    inverse_translation: np.ndarray
    clip_minimum: np.ndarray
    clip_maximum: np.ndarray


def _inflate_bounds(bounds, padding):
    if padding <= 0.0:
        return bounds
    minimum, maximum = bounds
    offset = Vector((padding, padding, padding))
    return minimum - offset, maximum + offset


def _projection_padding(projector):
    scale = projector.matrix_world.to_scale()
    return projection_padding((scale.x, scale.y, scale.z))


def _points_bounds(points):
    minimum = Vector((math.inf, math.inf, math.inf))
    maximum = Vector((-math.inf, -math.inf, -math.inf))
    for point in points:
        for axis in range(3):
            minimum[axis] = min(minimum[axis], point[axis])
            maximum[axis] = max(maximum[axis], point[axis])
    return minimum, maximum


def _projector_bounds(projector):
    matrix = projector.matrix_world
    return _points_bounds(
        matrix @ Vector((x, y, z))
        for x in (-0.5, 0.5)
        for y in (-0.5, 0.5)
        for z in (-0.5, 0.5)
    )


def _triangle_material(obj, mesh, material_index):
    slots = getattr(obj, "material_slots", ())
    if 0 <= material_index < len(slots):
        return slots[material_index].material
    if 0 <= material_index < len(mesh.materials):
        return mesh.materials[material_index]
    return None


def _requires_evaluated_mesh(obj):
    mesh = getattr(obj, "data", None)
    return (
        bool(getattr(obj, "modifiers", ()))
        or getattr(mesh, "shape_keys", None) is not None
    )


def _foreach_array(collection, property_name, width, dtype=np.float64):
    values = np.empty(len(collection) * width, dtype=dtype)
    collection.foreach_get(property_name, values)
    return values.reshape((-1, width))


def _loop_triangle_arrays(mesh):
    mesh.calc_loop_triangles()
    count = len(mesh.loop_triangles)
    vertices = np.empty(count * 3, dtype=np.int32)
    loops = np.empty(count * 3, dtype=np.int32)
    material_indices = np.empty(count, dtype=np.int32)
    try:
        mesh.loop_triangles.foreach_get("vertices", vertices)
        mesh.loop_triangles.foreach_get("loops", loops)
        mesh.loop_triangles.foreach_get("material_index", material_indices)
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_loop_triangle_arrays", type(error).__name__),
            "loop triangle arrays: fell back after %s",
            error,
            exc_info=True,
        )
        for index, triangle in enumerate(mesh.loop_triangles):
            offset = index * 3
            vertices[offset : offset + 3] = triangle.vertices
            loops[offset : offset + 3] = triangle.loops
            material_indices[index] = triangle.material_index
    return (
        vertices.reshape((-1, 3)),
        loops.reshape((-1, 3)),
        material_indices,
    )


def _mesh_projection_arrays(mesh):
    coordinates = _foreach_array(mesh.vertices, "co", 3)
    vertex_normals = _foreach_array(mesh.vertices, "normal", 3)

    corner_normals = None
    source_corner_normals = getattr(mesh, "corner_normals", None)
    if source_corner_normals is not None and len(source_corner_normals):
        try:
            corner_normals = _foreach_array(
                source_corner_normals,
                "vector",
                3,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_mesh_projection_arrays", type(error).__name__),
                "mesh projection arrays: fell back after %s",
                error,
                exc_info=True,
            )
            corner_normals = None

    uv_arrays = {
        layer.name: _foreach_array(
            layer.uv,
            "vector",
            2,
            dtype=np.float32,
        )
        for layer in mesh.uv_layers
    }
    color_arrays = {
        attribute.name: (
            attribute.domain,
            _foreach_array(
                attribute.data,
                "color",
                4,
                dtype=np.float32,
            ),
        )
        for attribute in getattr(mesh, "color_attributes", ())
    }
    triangle_vertices, triangle_loops, material_indices = _loop_triangle_arrays(mesh)
    return _ProjectionMeshArrays(
        mesh=mesh,
        coordinates=coordinates,
        vertex_normals=vertex_normals,
        corner_normals=corner_normals,
        uv_arrays=uv_arrays,
        color_arrays=color_arrays,
        triangle_vertices=triangle_vertices,
        triangle_loops=triangle_loops,
        triangle_material_indices=material_indices,
    )


def _normalized_rows(values):
    lengths = np.linalg.norm(values, axis=1)
    nonzero = lengths > EPSILON
    result = np.zeros_like(values)
    result[nonzero] = values[nonzero] / lengths[nonzero, None]
    return result


def _collect_triangles(receivers, projector_bounds, projector_local_bounds=None):
    started = time.perf_counter()
    projector_grid = BoundsGrid(projector_bounds)
    batches_by_projector = [[] for _ in projector_bounds]
    depsgraph = None
    mesh_cache = {}
    metrics = {
        "receivers": len(receivers),
        "array_cache_hits": 0,
        "array_cache_misses": 0,
        "source_triangles": 0,
        "candidate_triangles": 0,
        "triangle_projector_matches": 0,
        "oriented_bounds_rejected": 0,
        "triangle_batches": 0,
    }

    for receiver in receivers:
        obj = receiver.object
        matrix = receiver.matrix_world
        object_projectors = projector_grid.query_indices(receiver.bounds)
        if not object_projectors:
            continue

        evaluated = None
        cacheable = not _requires_evaluated_mesh(obj)
        if not cacheable:
            if depsgraph is None:
                depsgraph = bpy.context.evaluated_depsgraph_get()
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh(
                preserve_all_data_layers=True,
                depsgraph=depsgraph,
            )
        else:
            mesh = obj.data
        if mesh is None:
            continue

        try:
            arrays = None
            mesh_identity = mesh.as_pointer()
            if cacheable:
                cached = mesh_cache.get(mesh_identity)
                if cached is not None and cached.mesh is mesh:
                    arrays = cached
                    metrics["array_cache_hits"] += 1
            if arrays is None:
                arrays = _mesh_projection_arrays(mesh)
                metrics["array_cache_misses"] += 1
                if cacheable:
                    mesh_cache[mesh_identity] = arrays

            triangle_count = len(arrays.triangle_vertices)
            metrics["source_triangles"] += triangle_count
            if triangle_count == 0:
                continue

            matrix_array = np.asarray(
                tuple(tuple(row) for row in matrix),
                dtype=np.float64,
            )
            rotation_array = matrix_array[:3, :3]
            translation = matrix_array[:3, 3]
            world_positions = arrays.coordinates @ rotation_array.T + translation
            triangle_positions = world_positions[arrays.triangle_vertices]
            triangle_minimums = triangle_positions.min(axis=1)
            triangle_maximums = triangle_positions.max(axis=1)
            projector_matches = []
            candidate_parts = []
            for projector_index_value in object_projectors:
                minimum, maximum = projector_bounds[projector_index_value]
                minimum_array = np.asarray(tuple(minimum), dtype=np.float64)
                maximum_array = np.asarray(tuple(maximum), dtype=np.float64)
                mask = np.logical_and(
                    np.all(
                        triangle_maximums + EPSILON >= minimum_array,
                        axis=1,
                    ),
                    np.all(
                        triangle_minimums <= maximum_array + EPSILON,
                        axis=1,
                    ),
                )
                indices = np.flatnonzero(mask).astype(np.int32, copy=False)
                if not len(indices):
                    continue
                local_positions = None
                if projector_local_bounds is not None:
                    local_bounds = projector_local_bounds[projector_index_value]
                    local_positions = (
                        triangle_positions[indices] @ local_bounds.inverse_rotation.T
                        + local_bounds.inverse_translation
                    )
                    local_minimums = local_positions.min(axis=1)
                    local_maximums = local_positions.max(axis=1)
                    local_mask = np.logical_and(
                        np.all(
                            local_maximums + EPSILON >= local_bounds.clip_minimum,
                            axis=1,
                        ),
                        np.all(
                            local_minimums <= local_bounds.clip_maximum + EPSILON,
                            axis=1,
                        ),
                    )
                    rejected = int(len(indices) - np.count_nonzero(local_mask))
                    if rejected:
                        metrics["oriented_bounds_rejected"] += rejected
                        indices = indices[local_mask]
                        local_positions = local_positions[local_mask]
                    if not len(indices):
                        continue
                projector_matches.append(
                    (projector_index_value, indices, local_positions)
                )
                candidate_parts.append(indices)

            if not candidate_parts:
                continue

            candidate_indices = np.unique(np.concatenate(candidate_parts))
            metrics["candidate_triangles"] += len(candidate_indices)
            metrics["triangle_projector_matches"] += sum(
                len(indices) for _, indices, _ in projector_matches
            )

            candidate_vertex_indices = arrays.triangle_vertices[candidate_indices]
            candidate_loop_indices = arrays.triangle_loops[candidate_indices]
            candidate_positions = triangle_positions[candidate_indices]
            normal_matrix_source = matrix.to_3x3().inverted_safe().transposed()
            normal_matrix = np.asarray(
                tuple(tuple(row) for row in normal_matrix_source),
                dtype=np.float64,
            )
            local_normals = (
                arrays.corner_normals[candidate_loop_indices]
                if arrays.corner_normals is not None
                else arrays.vertex_normals[candidate_vertex_indices]
            )
            candidate_normals = _normalized_rows(
                local_normals.reshape((-1, 3)) @ normal_matrix.T
            ).reshape((-1, 3, 3))
            candidate_uvs = {
                name: values[candidate_loop_indices]
                for name, values in arrays.uv_arrays.items()
            }
            candidate_colors = {
                name: values[
                    candidate_loop_indices
                    if domain == "CORNER"
                    else candidate_vertex_indices
                ]
                for name, (domain, values) in arrays.color_arrays.items()
            }

            material_by_index = {}
            candidate_material_indices = arrays.triangle_material_indices[
                candidate_indices
            ]
            candidate_materials = []
            for material_index in candidate_material_indices:
                material_index_value = int(material_index)
                material = material_by_index.get(material_index_value)
                if material_index_value not in material_by_index:
                    material = _triangle_material(
                        obj,
                        mesh,
                        material_index_value,
                    )
                    material_by_index[material_index_value] = material
                candidate_materials.append(material)

            batch = _TriangleBatch(
                positions=candidate_positions,
                normals=candidate_normals,
                materials=tuple(candidate_materials),
                uvs=candidate_uvs,
                colors=candidate_colors,
            )
            metrics["triangle_batches"] += 1
            for (
                projector_index_value,
                triangle_indices,
                local_positions,
            ) in projector_matches:
                rows = np.searchsorted(candidate_indices, triangle_indices).astype(
                    np.int32,
                    copy=False,
                )
                batches_by_projector[projector_index_value].append(
                    _TriangleBatchRef(
                        batch=batch,
                        indices=rows,
                        local_positions=local_positions,
                    )
                )
        finally:
            if evaluated is not None:
                evaluated.to_mesh_clear()

    metrics["unique_meshes"] = len(mesh_cache)
    metrics["elapsed"] = time.perf_counter() - started
    return batches_by_projector, metrics


def _receiver_object_allowed(obj):
    if obj.type != "MESH" or obj.get("cp77_decal_surface"):
        return False
    node_type = str(obj.get("cp77_node_type", ""))
    if obj.hide_render or "Collision" in node_type or "Occluder" in node_type:
        return False
    mesh = getattr(obj, "data", None)
    return mesh is not None and bool(mesh.polygons)


def _matrix_identity(matrix):
    return tuple(round(float(value), 8) for row in matrix for value in row)


def _receiver_objects(collection):
    result = []
    seen = set()
    stack = set()

    def append(obj, matrix, instanced):
        object_identity = obj.as_pointer()
        identity = (
            object_identity,
            _matrix_identity(matrix) if instanced else None,
        )
        if identity in seen or not _receiver_object_allowed(obj):
            return
        seen.add(identity)
        bounds = _points_bounds(matrix @ Vector(corner) for corner in obj.bound_box)
        result.append(_ReceiverMesh(obj, matrix.copy(), bounds))

    def walk(current, instance_matrix=None):
        collection_identity = current.as_pointer()
        if collection_identity in stack:
            return
        stack.add(collection_identity)
        try:
            for obj in current.objects:
                instanced = instance_matrix is not None
                matrix = (
                    object_world_matrix(obj)
                    if not instanced
                    else instance_matrix @ object_world_matrix(obj)
                )
                append(obj, matrix, instanced)
                source_collection = getattr(obj, "instance_collection", None)
                if (
                    obj.instance_type == "COLLECTION"
                    and source_collection is not None
                    and not obj.hide_render
                ):
                    offset = Matrix.Translation(
                        -Vector(source_collection.instance_offset)
                    )
                    walk(source_collection, matrix @ offset)

            for child in current.children:
                walk(child, instance_matrix)
        finally:
            stack.remove(collection_identity)

    walk(collection)
    return result


def _projector_frame(matrix):
    axes = []
    basis = matrix.to_3x3()
    for index, local_axis in enumerate(
        (
            Vector((1.0, 0.0, 0.0)),
            Vector((0.0, 1.0, 0.0)),
            Vector((0.0, 0.0, 1.0)),
        )
    ):
        axis = basis.col[index]
        if axis.length_squared <= EPSILON:
            axis = local_axis
        axes.append(np.asarray(tuple(axis.normalized()), dtype=np.float64))
    return tuple(axes)


def _point_attribute_default(attribute_name, is_vector):
    if is_vector:
        return (0.0, 0.0, 0.0)
    if attribute_name == PROJECTOR_FRAME_VALID_ATTRIBUTE:
        return 0.0
    return 1.0


def _projection_mesh_data(
    pending,
    triangle_batches,
    material_cache,
    projector_local_bounds=None,
    material_pointer_cache=None,
    surface_offset=None,
):
    projection_started = time.perf_counter()
    projector_matrix = pending.projector.matrix_world.copy()
    if projector_local_bounds is None:
        inverse = projector_matrix.inverted_safe()
        inverse_array = np.asarray(
            tuple(tuple(row) for row in inverse),
            dtype=np.float64,
        )
        inverse_rotation = inverse_array[:3, :3]
        inverse_translation = inverse_array[:3, 3]
    else:
        inverse_rotation = projector_local_bounds.inverse_rotation
        inverse_translation = projector_local_bounds.inverse_translation
    flip_x = bool(pending.data.get("horizontalFlip", 0))
    flip_y = bool(pending.data.get("verticalFlip", 0))
    projector_scale = projector_matrix.to_scale()
    if projector_local_bounds is None:
        _, clip_padding = _projection_padding(pending.projector)
        clip_minimum, clip_maximum = projection_clip_bounds(clip_padding)
    else:
        clip_minimum = projector_local_bounds.clip_minimum
        clip_maximum = projector_local_bounds.clip_maximum
    projector_tangent, projector_bitangent, projector_up = _projector_frame(
        projector_matrix
    )
    orientation_world = projector_up
    normal_threshold = normal_threshold_radians(pending.data)
    if surface_offset is None:
        surface_offset = projection_surface_offset(
            tuple(abs(float(value)) for value in projector_scale)
        )
    offset = surface_offset

    if pending.material is None:
        material_mode = "RECEIVER_ONLY"
    elif requires_receiver_composite(pending.material):
        material_mode = "RECEIVER_COMPOSITE"
    else:
        material_mode = "TRANSPARENT_OVERLAY"

    vertices = []
    faces = []
    normals = []
    decal_uvs = []
    projection_coverages = []
    receiver_uvs = {}
    colors = {}
    materials = []
    material_indices = []
    material_lookup = {}
    resolved_material_indices = {}
    if material_pointer_cache is None:
        material_pointer_cache = {}
    fully_inside_triangles = 0
    boundary_clipped_triangles = 0
    fast_volume_rejected = 0
    front_volume_rejected = 0
    normal_threshold_rejected = 0
    coverage_rejected = 0
    classification_seconds = 0.0
    full_emit_seconds = 0.0
    full_projection_seconds = 0.0
    full_geometry_seconds = 0.0
    full_attributes_seconds = 0.0
    full_material_seconds = 0.0
    boundary_clip_seconds = 0.0
    boundary_select_seconds = 0.0
    boundary_material_seconds = 0.0
    boundary_emit_seconds = 0.0
    boundary_assemble_seconds = 0.0
    boundary_surface_eval_seconds = 0.0
    boundary_geometry_seconds = 0.0
    boundary_attributes_seconds = 0.0
    boundary_clip_timings = {
        "box_clip": 0.0,
        "scalar_clip": 0.0,
        "triangulate": 0.0,
        "chunk_merge": 0.0,
    }
    material_profile = {
        **COMPOSITE_BUILD_PROFILE_DEFAULTS,
        "index_calls": 0,
        "overlay_calls": 0,
        "resolved_hits": 0,
        "resolved_misses": 0,
        "pointer_hits": 0,
        "pointer_misses": 0,
        "pointer_miss_seconds": 0.0,
        "receiver_only_resolutions": 0,
        "composite_calls": 0,
        "composite_cache_hits": 0,
        "composite_cache_misses": 0,
        "composite_hit_seconds": 0.0,
        "composite_miss_seconds": 0.0,
        "composite_none": 0,
        "fallback_calls": 0,
        "fallback_seconds": 0.0,
        "slot_hits": 0,
        "slot_misses": 0,
    }

    decal_pointer = pending.material.as_pointer() if pending.material is not None else 0
    overlay_material = None
    overlay_material_index = None
    if material_mode == "TRANSPARENT_OVERLAY":
        overlay_material = decal_surface_material(
            pending.material,
            material_cache,
        )

    def material_pointer(material):
        if material is None:
            return 0
        identity = id(material)
        cached = material_pointer_cache.get(identity)
        if cached is not None:
            material_profile["pointer_hits"] += 1
            return cached[1]
        material_profile["pointer_misses"] += 1
        pointer_started = time.perf_counter()
        pointer = material.as_pointer()
        material_profile["pointer_miss_seconds"] += (
            time.perf_counter() - pointer_started
        )
        material_pointer_cache[identity] = (material, pointer)
        return pointer

    def material_index_for(receiver_material):
        nonlocal overlay_material_index
        material_profile["index_calls"] += 1
        if material_mode == "TRANSPARENT_OVERLAY":
            material_profile["overlay_calls"] += 1
            if overlay_material is None:
                return 0
            if overlay_material_index is None:
                overlay_material_index = len(materials)
                materials.append(overlay_material)
            return overlay_material_index

        receiver_key = material_pointer(receiver_material)
        if receiver_key in resolved_material_indices:
            material_profile["resolved_hits"] += 1
            return resolved_material_indices[receiver_key]
        material_profile["resolved_misses"] += 1

        if material_mode == "RECEIVER_ONLY":
            material_profile["receiver_only_resolutions"] += 1
            composite = receiver_material
        elif material_mode == "RECEIVER_COMPOSITE":
            material_profile["composite_calls"] += 1
            composite_key = (receiver_key, decal_pointer)
            cache_hit = composite_key in material_cache
            composite_started = time.perf_counter()
            composite = composite_material(
                receiver_material,
                pending.material,
                material_cache,
                receiver_pointer=receiver_key,
                decal_pointer=decal_pointer,
                profile=material_profile,
            )
            composite_elapsed = time.perf_counter() - composite_started
            if cache_hit:
                material_profile["composite_cache_hits"] += 1
                material_profile["composite_hit_seconds"] += composite_elapsed
            else:
                material_profile["composite_cache_misses"] += 1
                material_profile["composite_miss_seconds"] += composite_elapsed
            if composite is None:
                material_profile["composite_none"] += 1
                material_profile["fallback_calls"] += 1
                fallback_started = time.perf_counter()
                composite = decal_surface_material(
                    pending.material,
                    material_cache,
                )
                material_profile["fallback_seconds"] += (
                    time.perf_counter() - fallback_started
                )
        else:
            composite = overlay_material

        if composite is None:
            material_index = 0
        else:
            material_key = material_pointer(composite)
            material_index = material_lookup.get(material_key)
            if material_index is None:
                material_profile["slot_misses"] += 1
                material_index = len(materials)
                material_lookup[material_key] = material_index
                materials.append(composite)
            else:
                material_profile["slot_hits"] += 1
        resolved_material_indices[receiver_key] = material_index
        return material_index

    setup_seconds = time.perf_counter() - projection_started
    for batch_ref in triangle_batches:
        classification_started = time.perf_counter()
        batch = batch_ref.batch
        row_indices = np.asarray(batch_ref.indices, dtype=np.int32)
        if not len(row_indices):
            continue
        selected_positions = batch.positions[row_indices]
        selected_normals = batch.normals[row_indices]
        alignment_batch = np.einsum(
            "tvc,c->tv",
            selected_normals,
            orientation_world,
        )
        if normal_threshold is None:
            threshold_allowed = np.ones(len(row_indices), dtype=np.bool_)
        else:
            threshold_allowed = np.any(
                alignment_batch + EPSILON >= normal_threshold,
                axis=1,
            )
        if batch_ref.local_positions is None:
            local_position_batch = (
                selected_positions @ inverse_rotation.T + inverse_translation
            )
        else:
            local_position_batch = batch_ref.local_positions
        triangle_uv_names = set(batch.uvs)
        triangle_color_names = set(batch.colors)
        existing_vertex_count = len(vertices)
        for name in triangle_uv_names.difference(receiver_uvs):
            receiver_uvs[name] = [(0.0, 0.0)] * existing_vertex_count
        missing_uv_layers = tuple(set(receiver_uvs).difference(triangle_uv_names))
        for name in triangle_color_names.difference(colors):
            colors[name] = [(1.0, 1.0, 1.0, 1.0)] * existing_vertex_count
        missing_color_layers = tuple(set(colors).difference(triangle_color_names))

        clip_classes, _ = triangle_box_classes_and_planes(
            local_position_batch,
            clip_minimum,
            clip_maximum,
        )
        outside_rows = clip_classes < 0
        fast_volume_rejected += int(np.count_nonzero(outside_rows))
        if np.any(outside_rows):
            front_volume_rejected += int(
                np.count_nonzero(
                    outside_rows
                    & np.all(
                        local_position_batch[:, :, 2] > clip_maximum[2],
                        axis=1,
                    )
                )
            )

        normal_threshold_rejected += int(np.count_nonzero(~threshold_allowed))
        threshold_fully_allowed = (
            np.ones(len(row_indices), dtype=np.bool_)
            if normal_threshold is None
            else np.all(
                alignment_batch + EPSILON >= normal_threshold,
                axis=1,
            )
        )
        full_rows = np.flatnonzero((clip_classes > 0) & threshold_fully_allowed)
        classification_seconds += time.perf_counter() - classification_started

        full_emit_started = time.perf_counter()
        full_projection_started = time.perf_counter()
        if len(full_rows):
            full_uvs, full_coverages = projected_uv_coverage_array(
                local_position_batch[full_rows],
                alignment_batch[full_rows],
                pending.data,
                normal_threshold,
                flip_x,
                flip_y,
            )
            visible = np.any(full_coverages > EPSILON, axis=1)
            coverage_rejected += int(np.count_nonzero(~visible))
            full_rows = full_rows[visible]
            full_uvs = full_uvs[visible]
            full_coverages = full_coverages[visible]
        full_projection_seconds += time.perf_counter() - full_projection_started

        if len(full_rows):
            full_geometry_started = time.perf_counter()
            fully_inside_triangles += len(full_rows)
            batch_rows = row_indices[full_rows]
            full_positions = selected_positions[full_rows]
            full_normals = selected_normals[full_rows]
            full_alignments = alignment_batch[full_rows]
            offset_directions = np.where(
                full_alignments[:, :, None] >= 0.0,
                full_normals,
                -full_normals,
            )
            world_positions = full_positions + offset_directions * offset
            face_normals = np.cross(
                world_positions[:, 1] - world_positions[:, 0],
                world_positions[:, 2] - world_positions[:, 0],
            )
            expected_normals = full_normals.sum(axis=1)
            reverse_faces = (
                np.einsum(
                    "tc,tc->t",
                    face_normals,
                    expected_normals,
                )
                < 0.0
            )
            full_geometry_seconds += time.perf_counter() - full_geometry_started

            full_attributes_started = time.perf_counter()
            start = len(vertices)
            vertex_count = len(full_rows) * 3
            vertices.extend(world_positions.reshape((-1, 3)))
            normals.extend(full_normals.reshape((-1, 3)))
            decal_uvs.extend(full_uvs.reshape((-1, 2)))
            projection_coverages.extend(full_coverages.reshape(-1))
            for name in missing_uv_layers:
                receiver_uvs[name].extend(((0.0, 0.0),) * vertex_count)
            for name, values in batch.uvs.items():
                receiver_uvs[name].extend(values[batch_rows].reshape((-1, 2)))
            for name in missing_color_layers:
                colors[name].extend(((1.0, 1.0, 1.0, 1.0),) * vertex_count)
            for name, values in batch.colors.items():
                colors[name].extend(values[batch_rows].reshape((-1, 4)))

            face_starts = start + np.arange(len(batch_rows), dtype=np.int64) * 3
            face_values = np.column_stack(
                (face_starts, face_starts + 1, face_starts + 2)
            )
            if np.any(reverse_faces):
                face_values[reverse_faces, 1], face_values[reverse_faces, 2] = (
                    face_values[reverse_faces, 2].copy(),
                    face_values[reverse_faces, 1].copy(),
                )
            faces.extend(face_values)
            full_attributes_seconds += time.perf_counter() - full_attributes_started

            full_material_started = time.perf_counter()
            material_indices.extend(
                material_index_for(batch.materials[int(batch_row)])
                for batch_row in batch_rows
            )
            full_material_seconds += time.perf_counter() - full_material_started
        full_emit_seconds += time.perf_counter() - full_emit_started

        boundary_clip_started = time.perf_counter()
        boundary_select_started = time.perf_counter()
        boundary_rows = np.flatnonzero(
            threshold_allowed
            & (clip_classes >= 0)
            & ~((clip_classes > 0) & threshold_fully_allowed)
        )
        boundary_weight_chunks = []
        boundary_local_chunks = []
        boundary_source_rows = []
        boundary_material_indices = []
        boundary_select_seconds += time.perf_counter() - boundary_select_started
        if len(boundary_rows):
            weights, positions, sources, polygon_count = clip_triangles_to_box(
                local_position_batch[boundary_rows],
                clip_minimum,
                clip_maximum,
                source_values=(
                    None if normal_threshold is None else alignment_batch[boundary_rows]
                ),
                scalar_minimum=normal_threshold,
                timings=boundary_clip_timings,
            )
            boundary_clipped_triangles += polygon_count
            if len(sources):
                boundary_material_started = time.perf_counter()
                source_rows = row_indices[boundary_rows[sources]]
                boundary_weight_chunks.append(weights)
                boundary_local_chunks.append(positions)
                boundary_source_rows.extend(source_rows.tolist())
                boundary_material_indices.extend(
                    material_index_for(batch.materials[int(row)]) for row in source_rows
                )
                boundary_material_seconds += (
                    time.perf_counter() - boundary_material_started
                )
        boundary_clip_seconds += time.perf_counter() - boundary_clip_started

        boundary_emit_started = time.perf_counter()
        if boundary_weight_chunks:
            boundary_assemble_started = time.perf_counter()
            fan_weights = np.concatenate(boundary_weight_chunks, axis=0)
            fan_local_positions = np.concatenate(boundary_local_chunks, axis=0)
            source_rows = np.asarray(boundary_source_rows, dtype=np.int32)
            fan_material_indices = np.asarray(
                boundary_material_indices,
                dtype=np.int32,
            )
            boundary_assemble_seconds += time.perf_counter() - boundary_assemble_started

            boundary_surface_eval_started = time.perf_counter()
            source_normals = batch.normals[source_rows]
            fan_normals = np.einsum(
                "fvi,fic->fvc",
                fan_weights,
                source_normals,
            )
            normal_lengths = np.linalg.norm(fan_normals, axis=2)
            safe_lengths = np.where(
                normal_lengths > EPSILON,
                normal_lengths,
                1.0,
            )
            fan_normals = fan_normals / safe_lengths[:, :, None]
            fan_alignments = np.einsum(
                "fvc,c->fv",
                fan_normals,
                orientation_world,
            )
            fan_uvs, fan_coverages = projected_uv_coverage_array(
                fan_local_positions,
                fan_alignments,
                pending.data,
                normal_threshold,
                flip_x,
                flip_y,
            )
            visible_fans = np.any(fan_coverages > EPSILON, axis=1)
            coverage_rejected += int(np.count_nonzero(~visible_fans))
            boundary_surface_eval_seconds += (
                time.perf_counter() - boundary_surface_eval_started
            )

            if np.any(visible_fans):
                boundary_geometry_started = time.perf_counter()
                fan_weights = fan_weights[visible_fans]
                fan_normals = fan_normals[visible_fans]
                fan_alignments = fan_alignments[visible_fans]
                fan_uvs = fan_uvs[visible_fans]
                fan_coverages = fan_coverages[visible_fans]
                source_rows = source_rows[visible_fans]
                fan_material_indices = fan_material_indices[visible_fans]
                source_positions = batch.positions[source_rows]
                fan_world_positions = np.einsum(
                    "fvi,fic->fvc",
                    fan_weights,
                    source_positions,
                )
                fan_offset_directions = np.where(
                    fan_alignments[:, :, None] >= 0.0,
                    fan_normals,
                    -fan_normals,
                )
                fan_world_positions = (
                    fan_world_positions + fan_offset_directions * offset
                )

                face_normals = np.cross(
                    fan_world_positions[:, 1] - fan_world_positions[:, 0],
                    fan_world_positions[:, 2] - fan_world_positions[:, 0],
                )
                expected_normals = fan_normals.sum(axis=1)
                reverse_faces = (
                    np.einsum(
                        "fc,fc->f",
                        face_normals,
                        expected_normals,
                    )
                    < 0.0
                )
                boundary_geometry_seconds += (
                    time.perf_counter() - boundary_geometry_started
                )

                boundary_attributes_started = time.perf_counter()
                start = len(vertices)
                visible_count = len(fan_world_positions)
                vertex_count = visible_count * 3
                vertices.extend(fan_world_positions.reshape((-1, 3)))
                normals.extend(fan_normals.reshape((-1, 3)))
                decal_uvs.extend(fan_uvs.reshape((-1, 2)))
                projection_coverages.extend(fan_coverages.reshape(-1).tolist())

                for name in missing_uv_layers:
                    receiver_uvs[name].extend(((0.0, 0.0),) * vertex_count)
                for name, values in batch.uvs.items():
                    fan_values = np.einsum(
                        "fvi,fic->fvc",
                        fan_weights,
                        values[source_rows],
                    )
                    receiver_uvs[name].extend(fan_values.reshape((-1, 2)))
                for name in missing_color_layers:
                    colors[name].extend(((1.0, 1.0, 1.0, 1.0),) * vertex_count)
                for name, values in batch.colors.items():
                    fan_values = np.einsum(
                        "fvi,fic->fvc",
                        fan_weights,
                        values[source_rows],
                    )
                    colors[name].extend(fan_values.reshape((-1, 4)))

                face_starts = start + np.arange(visible_count, dtype=np.int64) * 3
                face_values = np.column_stack(
                    (face_starts, face_starts + 1, face_starts + 2)
                )
                if np.any(reverse_faces):
                    face_values[reverse_faces, 1], face_values[reverse_faces, 2] = (
                        face_values[reverse_faces, 2].copy(),
                        face_values[reverse_faces, 1].copy(),
                    )
                faces.extend(face_values)
                material_indices.extend(fan_material_indices.tolist())
                boundary_attributes_seconds += (
                    time.perf_counter() - boundary_attributes_started
                )
        boundary_emit_seconds += time.perf_counter() - boundary_emit_started

    return (
        vertices,
        faces,
        normals,
        decal_uvs,
        receiver_uvs,
        colors,
        {
            PROJECTION_COVERAGE_ATTRIBUTE: projection_coverages,
            PROJECTOR_TANGENT_ATTRIBUTE: np.tile(
                projector_tangent,
                (len(vertices), 1),
            ),
            PROJECTOR_BITANGENT_ATTRIBUTE: np.tile(
                projector_bitangent,
                (len(vertices), 1),
            ),
            PROJECTOR_UP_ATTRIBUTE: np.tile(
                projector_up,
                (len(vertices), 1),
            ),
            PROJECTOR_FRAME_VALID_ATTRIBUTE: np.ones(
                len(vertices),
                dtype=np.float32,
            ),
        },
        materials,
        material_indices,
        {
            "fully_inside_triangles": fully_inside_triangles,
            "boundary_clipped_triangles": boundary_clipped_triangles,
            "fast_volume_rejected": fast_volume_rejected,
            "front_volume_rejected": front_volume_rejected,
            "normal_threshold_rejected": normal_threshold_rejected,
            "coverage_rejected": coverage_rejected,
            "setup_seconds": setup_seconds,
            "classification_seconds": classification_seconds,
            "full_emit_seconds": full_emit_seconds,
            "full_projection_seconds": full_projection_seconds,
            "full_geometry_seconds": full_geometry_seconds,
            "full_attributes_seconds": full_attributes_seconds,
            "full_material_seconds": full_material_seconds,
            "boundary_clip_seconds": boundary_clip_seconds,
            "boundary_select_seconds": boundary_select_seconds,
            "boundary_box_clip_seconds": boundary_clip_timings["box_clip"],
            "boundary_scalar_clip_seconds": boundary_clip_timings["scalar_clip"],
            "boundary_triangulate_seconds": boundary_clip_timings["triangulate"],
            "boundary_chunk_merge_seconds": boundary_clip_timings["chunk_merge"],
            "boundary_material_seconds": boundary_material_seconds,
            "boundary_emit_seconds": boundary_emit_seconds,
            "boundary_assemble_seconds": boundary_assemble_seconds,
            "boundary_surface_eval_seconds": boundary_surface_eval_seconds,
            "boundary_geometry_seconds": boundary_geometry_seconds,
            "boundary_attributes_seconds": boundary_attributes_seconds,
            **{
                f"material_{key}": material_profile[key]
                for key in COMPOSITE_BUILD_PROFILE_DEFAULTS
            },
            "material_index_calls": material_profile["index_calls"],
            "material_overlay_calls": material_profile["overlay_calls"],
            "material_resolved_hits": material_profile["resolved_hits"],
            "material_resolved_misses": material_profile["resolved_misses"],
            "material_pointer_hits": material_profile["pointer_hits"],
            "material_pointer_misses": material_profile["pointer_misses"],
            "material_pointer_miss_seconds": material_profile["pointer_miss_seconds"],
            "material_receiver_only_resolutions": material_profile[
                "receiver_only_resolutions"
            ],
            "material_composite_calls": material_profile["composite_calls"],
            "material_composite_cache_hits": material_profile["composite_cache_hits"],
            "material_composite_cache_misses": material_profile[
                "composite_cache_misses"
            ],
            "material_composite_hit_seconds": material_profile["composite_hit_seconds"],
            "material_composite_miss_seconds": material_profile[
                "composite_miss_seconds"
            ],
            "material_composite_none": material_profile["composite_none"],
            "material_fallback_calls": material_profile["fallback_calls"],
            "material_fallback_seconds": material_profile["fallback_seconds"],
            "material_slot_hits": material_profile["slot_hits"],
            "material_slot_misses": material_profile["slot_misses"],
        },
    )


def _build_projection_surface(collection, patch_records):
    if not patch_records:
        return None

    name = fit_id_name(f"DecalSurfaces_{collection.name}")
    vertices = []
    faces = []
    normals = []
    decal_uvs = []
    receiver_uvs = {}
    colors = {}
    point_attributes = {}
    materials = []
    material_lookup = {}
    material_indices = []
    projector_indices = []
    ranges = []

    for projector_index, (pending, data) in enumerate(patch_records):
        (
            patch_vertices,
            patch_faces,
            patch_normals,
            patch_decal_uvs,
            patch_receiver_uvs,
            patch_colors,
            patch_point_attributes,
            patch_materials,
            patch_material_indices,
            _patch_metrics,
        ) = data
        vertex_start = len(vertices)
        face_start = len(faces)
        vertex_count = len(patch_vertices)
        face_count = len(patch_faces)

        existing_vertex_count = len(vertices)
        patch_uv_names = set(patch_receiver_uvs)
        for layer_name in set(receiver_uvs).difference(patch_uv_names):
            receiver_uvs[layer_name].extend(((0.0, 0.0),) * vertex_count)
        for layer_name in patch_uv_names.difference(receiver_uvs):
            receiver_uvs[layer_name] = [(0.0, 0.0)] * existing_vertex_count
        for layer_name, values in patch_receiver_uvs.items():
            receiver_uvs[layer_name].extend(values)

        patch_color_names = set(patch_colors)
        for layer_name in set(colors).difference(patch_color_names):
            colors[layer_name].extend(((1.0, 1.0, 1.0, 1.0),) * vertex_count)
        for layer_name in patch_color_names.difference(colors):
            colors[layer_name] = [(1.0, 1.0, 1.0, 1.0)] * existing_vertex_count
        for layer_name, values in patch_colors.items():
            colors[layer_name].extend(values)

        patch_attribute_names = set(patch_point_attributes)
        for attribute_name in set(point_attributes).difference(patch_attribute_names):
            existing = point_attributes[attribute_name]
            is_vector = bool(existing) and isinstance(
                existing[0],
                (tuple, list, np.ndarray),
            )
            default = _point_attribute_default(attribute_name, is_vector)
            existing.extend((default,) * vertex_count)
        for attribute_name in patch_attribute_names.difference(point_attributes):
            patch_values = patch_point_attributes[attribute_name]
            patch_array = np.asarray(patch_values)
            is_vector = patch_array.ndim == 2 and patch_array.shape[1] == 3
            default = _point_attribute_default(attribute_name, is_vector)
            point_attributes[attribute_name] = [default] * existing_vertex_count
        for attribute_name, values in patch_point_attributes.items():
            point_attributes[attribute_name].extend(values)

        local_material_map = []
        for material in patch_materials:
            material_key = material.as_pointer() if material is not None else 0
            global_index = material_lookup.get(material_key)
            if global_index is None:
                global_index = len(materials)
                material_lookup[material_key] = global_index
                materials.append(material)
            local_material_map.append(global_index)

        vertices.extend(patch_vertices)
        normals.extend(patch_normals)
        decal_uvs.extend(patch_decal_uvs)
        faces.extend(
            tuple(vertex_start + index for index in face) for face in patch_faces
        )
        material_indices.extend(
            local_material_map[int(index)] for index in patch_material_indices
        )
        projector_indices.extend((projector_index,) * face_count)
        ranges.append(
            (
                pending,
                vertex_start,
                vertex_count,
                face_start,
                face_count,
            )
        )

    mesh = track_created_datablock("meshes", bpy.data.meshes.new(name))
    vertex_values = np.ascontiguousarray(vertices, dtype=np.float32)
    triangle_values = np.ascontiguousarray(faces, dtype=np.int32)
    vertex_count = len(vertex_values)
    triangle_count = len(triangle_values)
    loop_count = triangle_count * 3
    loop_vertices = triangle_values.reshape(-1)

    mesh.vertices.add(vertex_count)
    mesh.vertices.foreach_set("co", vertex_values.reshape(-1))
    mesh.loops.add(loop_count)
    mesh.loops.foreach_set("vertex_index", loop_vertices)
    mesh.polygons.add(triangle_count)
    mesh.polygons.foreach_set(
        "loop_start",
        np.arange(0, loop_count, 3, dtype=np.int32),
    )
    mesh.polygons.foreach_set(
        "loop_total",
        np.full(triangle_count, 3, dtype=np.int32),
    )
    mesh.update(calc_edges=True)
    for material in materials:
        if material is not None:
            mesh.materials.append(material)
    mesh.polygons.foreach_set(
        "material_index",
        np.asarray(material_indices, dtype=np.int32),
    )
    mesh.polygons.foreach_set(
        "use_smooth",
        np.ones(triangle_count, dtype=np.bool_),
    )
    set_custom_normals_from_vertices(
        mesh,
        normals,
        label=f"projected decal surface {name!r}",
    )

    receiver_uv_names = tuple(receiver_uvs)
    for layer_name, values in receiver_uvs.items():
        layer = mesh.uv_layers.new(name=layer_name)
        layer_values = np.asarray(values, dtype=np.float32)
        layer.uv.foreach_set(
            "vector",
            layer_values[loop_vertices].reshape(-1),
        )
    decal_layer = mesh.uv_layers.new(name=DECAL_UV_LAYER)
    decal_values = np.asarray(decal_uvs, dtype=np.float32)
    decal_layer.uv.foreach_set(
        "vector",
        decal_values[loop_vertices].reshape(-1),
    )
    mesh.update()
    refresh_tangent_sign_attributes(mesh, uv_name=DECAL_UV_LAYER)
    if receiver_uv_names:
        try:
            mesh.uv_layers.active_index = 0
        except (AttributeError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_build_projection_surface 1", type(error).__name__),
                "build projection surface: fell back after %s",
                error,
                exc_info=True,
            )
        for layer in mesh.uv_layers:
            if hasattr(layer, "active_render"):
                layer.active_render = layer.name == receiver_uv_names[0]
    for layer_name, values in colors.items():
        attribute = mesh.color_attributes.new(
            name=layer_name,
            type="FLOAT_COLOR",
            domain="POINT",
        )
        attribute.data.foreach_set(
            "color",
            np.asarray(values, dtype=np.float32).reshape(-1),
        )
    for attribute_name, values in point_attributes.items():
        values_array = np.asarray(values, dtype=np.float32)
        if values_array.ndim == 2 and values_array.shape[1] == 3:
            attribute = mesh.attributes.new(
                name=attribute_name,
                type="FLOAT_VECTOR",
                domain="POINT",
            )
            attribute.data.foreach_set("vector", values_array.reshape(-1))
        else:
            attribute = mesh.attributes.new(
                name=attribute_name,
                type="FLOAT",
                domain="POINT",
            )
            attribute.data.foreach_set("value", values_array.reshape(-1))
    try:
        projector_attribute = mesh.attributes.new(
            name="CP77_DecalProjectorIndex",
            type="INT",
            domain="FACE",
        )
        projector_attribute.data.foreach_set(
            "value",
            np.asarray(projector_indices, dtype=np.int32),
        )
    except (AttributeError, RuntimeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_build_projection_surface 2", type(error).__name__),
            "build projection surface: fell back after %s",
            error,
            exc_info=True,
        )

    obj = track_created_datablock("objects", bpy.data.objects.new(name, mesh))
    collection.objects.link(obj)
    obj["cp77_decal_surface"] = True
    for property_name, value in (
        ("visible_shadow", False),
        ("visible_diffuse", True),
        ("visible_glossy", True),
        ("visible_transmission", True),
    ):
        if not hasattr(obj, property_name):
            continue
        try:
            setattr(obj, property_name, value)
        except (AttributeError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_build_projection_surface 3", type(error).__name__),
                "build projection surface: fell back after %s",
                error,
                exc_info=True,
            )

    for (
        pending,
        vertex_start,
        vertex_count,
        face_start,
        face_count,
    ) in ranges:
        pending.projector["cp77_decal_surface"] = obj.name

    return obj


def project_pending_decals(
    collection,
    pending,
    material_cache,
    *,
    output_collection=None,
):
    if not pending:
        return {
            "projectors": 0,
            "patches": 0,
            "triangles": 0,
            "errors": (),
            "timings": {
                "receiver_scan": 0.0,
                "triangle_collect": 0.0,
                "patch_build": 0.0,
                "patch_geometry": 0.0,
                "geometry_setup": 0.0,
                "geometry_classification": 0.0,
                "geometry_full_emit": 0.0,
                "geometry_boundary_clip": 0.0,
                "geometry_boundary_emit": 0.0,
                "surface_commit": 0.0,
            },
            "projection_metrics": {},
        }

    projector_padding = [_projection_padding(item.projector)[0] for item in pending]
    bounds = [
        _inflate_bounds(
            _projector_bounds(item.projector),
            projector_padding[index],
        )
        for index, item in enumerate(pending)
    ]

    receiver_started = time.perf_counter()
    receivers = _receiver_objects(collection)
    receiver_elapsed = time.perf_counter() - receiver_started

    projector_local_bounds = []
    for item in pending:
        inverse = item.projector.matrix_world.inverted_safe()
        inverse_array = np.asarray(
            tuple(tuple(row) for row in inverse),
            dtype=np.float64,
        )
        _, clip_padding = _projection_padding(item.projector)
        clip_minimum, clip_maximum = projection_clip_bounds(clip_padding)
        projector_local_bounds.append(
            _ProjectorLocalBounds(
                inverse_rotation=inverse_array[:3, :3],
                inverse_translation=inverse_array[:3, 3],
                clip_minimum=np.asarray(clip_minimum, dtype=np.float64),
                clip_maximum=np.asarray(clip_maximum, dtype=np.float64),
            )
        )

    collect_started = time.perf_counter()
    triangles_by_projector, projection_metrics = _collect_triangles(
        receivers,
        bounds,
        projector_local_bounds,
    )
    collect_elapsed = time.perf_counter() - collect_started

    patches = 0
    projected_triangles = 0
    errors = []
    # Draw order: later decals cover earlier ones where they overlap, so they stand further off the receivers.
    projection_jobs = sorted(
        zip(pending, triangles_by_projector, projector_local_bounds, bounds),
        key=lambda job: (
            int(job[0].data.get("orderNo", 0) or 0),
            job[0].node_index,
            job[0].instance_index,
        ),
    )
    surface_offsets = stacked_surface_offsets(
        [
            projection_surface_offset(
                tuple(
                    abs(float(value))
                    for value in job[0].projector.matrix_world.to_scale()
                )
            )
            for job in projection_jobs
        ],
        [(tuple(job[3][0]), tuple(job[3][1])) for job in projection_jobs],
    )
    patch_started = time.perf_counter()
    geometry_started = patch_started
    patch_records = []
    geometry_metrics = {
        "fully_inside_triangles": 0,
        "boundary_clipped_triangles": 0,
        "fast_volume_rejected": 0,
        "front_volume_rejected": 0,
        "normal_threshold_rejected": 0,
        "coverage_rejected": 0,
    }
    geometry_timings = {
        "setup": 0.0,
        "classification": 0.0,
        "full_emit": 0.0,
        "full_projection": 0.0,
        "full_geometry": 0.0,
        "full_attributes": 0.0,
        "full_material": 0.0,
        "boundary_clip": 0.0,
        "boundary_select": 0.0,
        "boundary_box_clip": 0.0,
        "boundary_scalar_clip": 0.0,
        "boundary_triangulate": 0.0,
        "boundary_chunk_merge": 0.0,
        "boundary_material": 0.0,
        "boundary_emit": 0.0,
        "boundary_assemble": 0.0,
        "boundary_surface_eval": 0.0,
        "boundary_geometry": 0.0,
        "boundary_attributes": 0.0,
    }
    material_profile_metrics = {
        **{
            f"material_{key}": value
            for key, value in COMPOSITE_BUILD_PROFILE_DEFAULTS.items()
        },
        "material_index_calls": 0,
        "material_overlay_calls": 0,
        "material_resolved_hits": 0,
        "material_resolved_misses": 0,
        "material_pointer_hits": 0,
        "material_pointer_misses": 0,
        "material_pointer_miss_seconds": 0.0,
        "material_receiver_only_resolutions": 0,
        "material_composite_calls": 0,
        "material_composite_cache_hits": 0,
        "material_composite_cache_misses": 0,
        "material_composite_hit_seconds": 0.0,
        "material_composite_miss_seconds": 0.0,
        "material_composite_none": 0,
        "material_fallback_calls": 0,
        "material_fallback_seconds": 0.0,
        "material_slot_hits": 0,
        "material_slot_misses": 0,
    }
    material_pointer_cache = {}
    for (item, candidates, local_bounds, _bounds), surface_offset in zip(
        projection_jobs, surface_offsets
    ):
        try:
            data = _projection_mesh_data(
                item,
                candidates,
                material_cache,
                local_bounds,
                material_pointer_cache,
                surface_offset,
            )
        except Exception as error:
            debug_exception(
                _LOG,
                "Could not project decal %s:%s",
                item.node_index,
                item.instance_index,
            )
            message = f"decal {item.node_index}:{item.instance_index}: {error}"
            errors.append(message)
            continue
        patch_metrics = data[9]
        for key in geometry_metrics:
            geometry_metrics[key] += int(patch_metrics.get(key, 0))
        for key in geometry_timings:
            geometry_timings[key] += float(patch_metrics.get(f"{key}_seconds", 0.0))
        for key, default_value in material_profile_metrics.items():
            value = patch_metrics.get(key, 0)
            if isinstance(default_value, float):
                material_profile_metrics[key] += float(value)
            else:
                material_profile_metrics[key] += int(value)
        triangle_count = len(data[1])
        if triangle_count:
            patch_records.append((item, data))
            patches += 1
            projected_triangles += triangle_count
    geometry_elapsed = time.perf_counter() - geometry_started
    surface_started = time.perf_counter()
    surface_objects = 0
    try:
        surface = _build_projection_surface(
            output_collection or collection,
            patch_records,
        )
        surface_objects = int(surface is not None)
    except Exception as error:
        debug_exception(_LOG, "Could not build the combined decal surface")
        message = f"combined decal surface: {error}"
        errors.append(message)
        patches = 0
        projected_triangles = 0
    surface_elapsed = time.perf_counter() - surface_started
    patch_elapsed = time.perf_counter() - patch_started

    projection_metrics = dict(projection_metrics)
    projection_metrics["receiver_count"] = len(receivers)
    projection_metrics["surface_objects"] = surface_objects
    projection_metrics.update(geometry_metrics)
    projection_metrics.update(material_profile_metrics)
    return {
        "projectors": len(pending),
        "patches": patches,
        "triangles": projected_triangles,
        "errors": tuple(errors),
        "timings": {
            "receiver_scan": receiver_elapsed,
            "triangle_collect": collect_elapsed,
            "patch_build": patch_elapsed,
            "patch_geometry": geometry_elapsed,
            "geometry_setup": geometry_timings["setup"],
            "geometry_classification": geometry_timings["classification"],
            "geometry_full_emit": geometry_timings["full_emit"],
            "geometry_full_projection": geometry_timings["full_projection"],
            "geometry_full_geometry": geometry_timings["full_geometry"],
            "geometry_full_attributes": geometry_timings["full_attributes"],
            "geometry_full_material": geometry_timings["full_material"],
            "geometry_boundary_clip": geometry_timings["boundary_clip"],
            "geometry_boundary_select": geometry_timings["boundary_select"],
            "geometry_boundary_box_clip": geometry_timings["boundary_box_clip"],
            "geometry_boundary_scalar_clip": geometry_timings["boundary_scalar_clip"],
            "geometry_boundary_triangulate": geometry_timings["boundary_triangulate"],
            "geometry_boundary_chunk_merge": geometry_timings["boundary_chunk_merge"],
            "geometry_boundary_material": geometry_timings["boundary_material"],
            "geometry_boundary_emit": geometry_timings["boundary_emit"],
            "geometry_boundary_assemble": geometry_timings["boundary_assemble"],
            "geometry_boundary_surface_eval": geometry_timings["boundary_surface_eval"],
            "geometry_boundary_geometry": geometry_timings["boundary_geometry"],
            "geometry_boundary_attributes": geometry_timings["boundary_attributes"],
            "surface_commit": surface_elapsed,
        },
        "projection_metrics": projection_metrics,
    }
