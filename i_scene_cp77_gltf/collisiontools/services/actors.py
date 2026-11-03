from __future__ import annotations

import base64
import json
import math

from mathutils import Euler, Vector

from ...blender.operator_results import OperationResult
from ...blender.physics.actors import native_shape_definition
from ...blender.physics.bridge_session import require_initialized_bridge
from ...blender.physics.objects import get_actor_world_transform, get_clean_mesh_data
from ...physics.model.materials import get_mat_density


def validate_scene_actors(context, excluded_objects=()):

    excluded = (
        excluded_objects if type(excluded_objects) is set else set(excluded_objects)
    )
    errors = []
    for item in context.scene.physx.actors:
        obj = item.obj_ref
        if not obj or obj in excluded:
            continue
        for shape in obj.physx.shapes:
            if (
                shape.shape_type in {"CONVEX", "TRIANGLE", "HEIGHTFIELD"}
                and not shape.cooked_data
            ):
                errors.append(f"{obj.name}: {shape.name} not cooked")
    if errors:
        return OperationResult.cancelled("Errors: " + "; ".join(errors))
    return OperationResult.finished("Scene Valid")


def build_authored_actors(context, bridge, excluded_objects=()):

    excluded = (
        excluded_objects if type(excluded_objects) is set else set(excluded_objects)
    )
    count = 0
    for item in context.scene.physx.actors:
        obj = item.obj_ref
        if not obj or obj.physx.actor_type == "NONE" or obj in excluded:
            continue
        px = obj.physx
        shapes = []
        for shape in px.shapes:
            definition = native_shape_definition(shape)
            if definition is not None:
                shapes.append(definition)
        if not shapes:
            continue
        loc, quat = get_actor_world_transform(item, context)
        actor_pose = [loc.x, loc.y, loc.z, quat.x, quat.y, quat.z, quat.w]
        com = list(px.com_offset)
        inertia = list(px.inertia)
        handle = bridge.create_actor(
            px.actor_type, actor_pose, shapes, px.mass, com, inertia
        )
        item.actor_handle = str(handle)
        count += 1
    return count


def apply_force_to_active_actor(context):

    px_scene = context.scene.physx
    obj = context.active_object
    handle = next(
        (item.actor_handle for item in px_scene.actors if item.obj_ref == obj), "0"
    )
    if handle == "0":
        return OperationResult.cancelled("The active object is not a built PhysX actor")
    try:
        bridge = require_initialized_bridge(context)
        force = px_scene.force_value
        point = (
            context.scene.cursor.location
            if px_scene.use_force_pos
            else Vector((0.0, 0.0, 0.0))
        )
        bridge.apply_force(
            int(handle),
            [force[0], force[1], force[2]],
            int(px_scene.force_mode),
            px_scene.use_force_pos,
            [point.x, point.y, point.z],
        )
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)
    return OperationResult.finished()


def cook_active_shape(context):
    try:
        bridge = require_initialized_bridge(context)
        obj = context.object
        shape = obj.physx.shapes[obj.physx.shape_index]
        if shape.shape_type == "HEIGHTFIELD":
            verts, indices = get_clean_mesh_data(obj, "TRIANGLE")
            result = bridge.cook_heightfield_from_mesh(
                int(shape.heightfield_rows),
                int(shape.heightfield_columns),
                verts,
                indices,
            )
            if not isinstance(result, dict):
                return OperationResult.cancelled(
                    "PhysX returned an invalid heightfield cook result"
                )
            cooked = result.get("data")
            if not cooked:
                return OperationResult.cancelled(
                    "PhysX returned no cooked heightfield data"
                )
            shape.cooked_data = base64.b64encode(cooked).decode("ascii")
            shape.is_cooked = True
            shape.heightfield_height_scale = max(float(result["height_scale"]), 1.0e-9)
            shape.heightfield_row_scale = max(float(result["row_scale"]), 1.0e-9)
            shape.heightfield_column_scale = max(float(result["column_scale"]), 1.0e-9)
            local_pos = result.get("local_pos", (0.0, 0.0, 0.0))
            local_rot = result.get("local_rot", (0.5, 0.5, 0.5, 0.5))
            shape.local_pos = tuple(float(value) for value in local_pos[:3])
            shape.local_rot = (
                float(local_rot[3]),
                float(local_rot[0]),
                float(local_rot[1]),
                float(local_rot[2]),
            )
            extents = result.get("extents")
            if extents and len(extents) >= 3:
                shape.heightfield_extents = tuple(
                    max(float(value), 0.0) for value in extents[:3]
                )
            material_source = str(
                getattr(shape, "physics_material_source", "")
                or shape.physics_material
                or "Default"
            )
            material_storage = str(
                getattr(shape, "physics_material_storage", "string") or "string"
            )
            shape.heightfield_materials_json = json.dumps(
                [
                    {
                        "$type": "CName",
                        "$storage": material_storage,
                        "$value": material_source,
                    }
                ],
                separators=(",", ":"),
            )
            shape.heightfield_material_indices_json = json.dumps(
                [0] * 16, separators=(",", ":")
            )
        elif shape.shape_type in {"CONVEX", "TRIANGLE"}:
            verts, indices = get_clean_mesh_data(
                obj, shape.shape_type, shape.vertex_limit
            )
            cooked = bridge.cook_mesh(
                shape.shape_type, verts, indices, shape.vertex_limit
            )
            if not cooked:
                return OperationResult.cancelled("PhysX returned no cooked mesh data")
            shape.cooked_data = base64.b64encode(cooked).decode("ascii")
            shape.is_cooked = True
            shape.local_pos = (0.0, 0.0, 0.0)
            shape.local_rot = (1.0, 0.0, 0.0, 0.0)
        else:
            return OperationResult.cancelled(
                "Only convex, triangle, and heightfield shapes are cooked from Blender meshes"
            )
        return OperationResult.finished("Cooking Complete")
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)


def fit_bounds_shape(context, shape_index=-1):

    obj = context.object
    px = obj.physx
    index = shape_index if shape_index >= 0 else px.shape_index
    if index < 0 or index >= len(px.shapes):
        return OperationResult.cancelled("No valid PhysX shape is selected")
    if not getattr(obj, "bound_box", None):
        return OperationResult.cancelled("The active mesh has no bounds to fit")
    shape = px.shapes[index]
    bounds = [Vector(bound) for bound in obj.bound_box]
    for vertex in bounds:
        vertex.x *= obj.scale.x
        vertex.y *= obj.scale.y
        vertex.z *= obj.scale.z
    minimum = Vector(tuple(min(v[i] for v in bounds) for i in range(3)))
    maximum = Vector(tuple(max(v[i] for v in bounds) for i in range(3)))
    size = maximum - minimum
    center = (minimum + maximum) / 2.0
    shape.local_pos = (
        (0.0, 0.0, 0.0) if shape.shape_type in {"CONVEX", "TRIANGLE"} else center
    )
    if shape.shape_type == "BOX":
        shape.dim_x, shape.dim_y, shape.dim_z = size.x / 2.0, size.y / 2.0, size.z / 2.0
    elif shape.shape_type == "SPHERE":
        shape.dim_x = max(size) / 2.0
    elif shape.shape_type == "CAPSULE":
        radius = max(size.x, size.y) / 2.0
        half_height = (size.z / 2.0) - radius
        if half_height < 0.0:
            half_height = 0.0
            radius = size.z / 2.0
        shape.dim_x = radius
        shape.dim_y = half_height
        shape.local_rot = Euler((0.0, math.radians(90.0), 0.0)).to_quaternion()
    if context.area is not None:
        context.area.tag_redraw()
    return OperationResult.finished()


def calculate_dynamics(context):

    obj = context.object
    px = obj.physx
    try:
        bridge = require_initialized_bridge(context)
        shapes = []
        densities = []
        for shape in px.shapes:
            definition = native_shape_definition(shape)
            if definition is None:
                continue
            definition["mat"] = [0.0, 0.0, 0.0]
            shapes.append(definition)
            densities.append(get_mat_density(shape.physics_material))
        result = bridge.compute_mass_props(shapes, densities)
        if px.calc_mass:
            px.mass = result["mass"]
        if px.calc_offset:
            px.com_offset = result["com"]
        if px.calc_inertia:
            px.inertia = result["inertia"]
    except Exception as error:
        return OperationResult.cancelled(
            f"Mass calculation failed: {error}", error=error
        )
    return OperationResult.finished()


def mutate_shape_list(context, action):

    px = context.object.physx
    if action == "ADD":
        index = len(px.shapes)
        shape = px.shapes.add()
        shape.name = f"Shape {index + 1}"
        # A mesh fits the new shape to its bounds; an actor with no geometry starts the default box at its origin.
        if context.object.type == "MESH":
            result = fit_bounds_shape(context, index)
            if not result.ok:
                px.shapes.remove(index)
                return OperationResult.cancelled(
                    "Could not fit the new PhysX shape to the active mesh"
                )
        px.shape_index = index
    elif action == "REMOVE":
        if not px.shapes or px.shape_index < 0 or px.shape_index >= len(px.shapes):
            return OperationResult.cancelled("No valid PhysX shape is selected")
        px.shapes.remove(px.shape_index)
        px.shape_index = min(max(0, px.shape_index - 1), max(0, len(px.shapes) - 1))
    return OperationResult.finished()


def mutate_actor_list(context, action):

    px_scene = context.scene.physx
    if action == "ADD":
        obj = context.active_object
        if (
            obj is None
            or getattr(obj, "type", None) != "MESH"
            or getattr(obj, "physx", None) is None
        ):
            return OperationResult.cancelled(
                "Select a mesh object before adding a PhysX actor"
            )
        if any(item.obj_ref == obj for item in px_scene.actors):
            return OperationResult.cancelled(
                "The active object is already a PhysX actor"
            )
        actor_index = len(px_scene.actors)
        item = px_scene.actors.add()
        item.obj_ref = obj
        if not obj.physx.shapes:
            shape = obj.physx.shapes.add()
            shape.name = "Shape 1"
            result = fit_bounds_shape(context, 0)
            if not result.ok:
                obj.physx.shapes.remove(0)
                px_scene.actors.remove(actor_index)
                return OperationResult.cancelled(
                    "Could not fit an initial PhysX shape to the active mesh"
                )
        px_scene.actor_list_index = actor_index
    elif action == "REMOVE":
        index = px_scene.actor_list_index
        if not px_scene.actors or index < 0 or index >= len(px_scene.actors):
            return OperationResult.cancelled("No valid PhysX actor is selected")
        px_scene.actors.remove(index)
        px_scene.actor_list_index = min(
            max(0, index - 1), max(0, len(px_scene.actors) - 1)
        )
    return OperationResult.finished()
