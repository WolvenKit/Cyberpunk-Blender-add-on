import math

import bmesh
import bpy

from ...blender.context import (
    get_safe_mode,
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.mesh import is_mesh
<<<<<<< Updated upstream
from ...blender.shapekeys import has_shape_keys
from ..model import MeshToolResult


def prepare_submesh(context, smooth_factor: float, merge_distance: float):
    angle_deg = max(0.0, min(180.0, float(smooth_factor)))

    # Validate first
    targets = [ob for ob in context.selected_objects if ob.type == 'MESH']
    if not targets:
        return MeshToolResult.failure("Select one or more meshes.")

    # Store context
    store_current_context()

    try:
        # Switch to object mode if needed
        if get_safe_mode() != 'OBJECT':
            safe_mode_switch('OBJECT')
=======
from ...blender.operator_results import OperationResult
from ...blender.selection import selected_meshes
from ...blender.shapekeys import has_shape_keys
from ...core.log import get_logger
from .garment_contract import (
    GARMENT_ATTRIBUTE_DEFAULTS,
    GARMENT_ATTRIBUTE_DOMAIN,
    GARMENT_ATTRIBUTE_TYPE,
)

_LOG = get_logger(__name__)


def prepare_submesh(context, smooth_angle: float, merge_distance: float):
    angle = max(0.0, min(math.pi, float(smooth_angle)))

    targets = selected_meshes(context)
    if not targets:
        return OperationResult.cancelled("Select one or more meshes.")

    store_current_context()

    try:
        if get_safe_mode() != "OBJECT":
            safe_mode_switch("OBJECT")
>>>>>>> Stashed changes

        merged_total = 0
        for ob in targets:
            me = ob.data
<<<<<<< Updated upstream
            # avoid modifying other objects that share this mesh
=======
            # Avoid modifying other objects that share this mesh.
>>>>>>> Stashed changes
            if me.users > 1:
                ob.data = me = me.copy()

            do_merge = merge_distance > 0.0 and not has_shape_keys(ob)
            bm = bmesh.new()
            try:
                bm.from_mesh(me)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                start = len(bm.verts)
<<<<<<< Updated upstream
                # mark seams at boundaries & wires
=======

>>>>>>> Stashed changes
                for e in bm.edges:
                    if len(e.link_faces) == 0 or e.is_boundary:
                        e.seam = True
                if do_merge:
<<<<<<< Updated upstream
                    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=float(merge_distance))
=======
                    bmesh.ops.remove_doubles(
                        bm, verts=bm.verts, dist=float(merge_distance)
                    )
>>>>>>> Stashed changes
                bm.normal_update()
                for f in bm.faces:
                    f.smooth = True

                bm.to_mesh(me)
                merged_total += max(0, start - len(bm.verts))
            finally:
                bm.free()

            me.update(calc_edges=True, calc_edges_loose=True)

<<<<<<< Updated upstream
        # apply Shade Auto Smooth to selected meshes
        active_backup = context.view_layer.objects.active
        context.view_layer.objects.active = targets[0]
        bpy.ops.object.shade_auto_smooth(use_auto_smooth=True, angle=math.radians(angle_deg))
        context.view_layer.objects.active = active_backup

        return MeshToolResult.success(
=======
        active_backup = context.view_layer.objects.active
        context.view_layer.objects.active = targets[0]
        result = bpy.ops.object.shade_auto_smooth(use_auto_smooth=True, angle=angle)
        if "FINISHED" not in result:
            return OperationResult.cancelled(
                "Blender could not apply automatic smooth shading."
            )
        context.view_layer.objects.active = active_backup

        return OperationResult.finished(
>>>>>>> Stashed changes
            f"Submesh preparation complete. {merged_total} verts merged across {len(targets)} object(s)."
        )

    finally:
<<<<<<< Updated upstream
        # restore original context
=======
>>>>>>> Stashed changes
        restore_previous_context()


def set_armature_target(context, reparent):
<<<<<<< Updated upstream
    """Set armature for a group of objects quickly with the option to reparent them if desired """
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
=======
    """Set armature for a group of objects quickly with the option to reparent them if desired"""
    meshes = selected_meshes(context)
>>>>>>> Stashed changes
    props = context.scene.cp77_panel_props
    target_armature_name = props.selected_armature
    target_armature = bpy.data.objects.get(target_armature_name)

    obj = context.object
    if not obj:
<<<<<<< Updated upstream
        return MeshToolResult.failure("No active object. Please select a mesh and try again.")
    if not is_mesh(obj):
        return MeshToolResult.failure("The active object is not a mesh.")
    if len(selected_meshes) == 0 or not target_armature or target_armature.type != 'ARMATURE':
        return MeshToolResult.success()

    # Ensure the target armature has a collection
    if not target_armature.users_collection:
        target_collection = bpy.data.collections.new(target_armature.name + "_collection")
=======
        return OperationResult.cancelled(
            "No active object. Please select a mesh and try again.",
            "ERROR_INVALID_CONTEXT",
        )
    if not is_mesh(obj):
        return OperationResult.cancelled("The active object is not a mesh.")
    if len(meshes) == 0 or not target_armature or target_armature.type != "ARMATURE":
        _LOG.debug(
            "Armature retarget skipped: selected_meshes=%d target=%s",
            len(meshes),
            target_armature_name or "<none>",
        )
        return OperationResult.finished()

    if not target_armature.users_collection:
        target_collection = bpy.data.collections.new(
            target_armature.name + "_collection"
        )
>>>>>>> Stashed changes
        context.scene.collection.children.link(target_collection)
        target_collection.objects.link(target_armature)
    else:
        target_collection = target_armature.users_collection[0]

<<<<<<< Updated upstream
    for mesh in selected_meshes:
        retargeted = False
        for modifier in mesh.modifiers:
            if modifier.type == 'ARMATURE':
=======
    for mesh in meshes:
        retargeted = False
        for modifier in mesh.modifiers:
            if modifier.type == "ARMATURE":
>>>>>>> Stashed changes
                if modifier.object != target_armature:
                    modifier.object = target_armature
                retargeted = True
                break

        if not retargeted:
<<<<<<< Updated upstream
            armature = mesh.modifiers.new('Armature', 'ARMATURE')
=======
            armature = mesh.modifiers.new("Armature", "ARMATURE")
>>>>>>> Stashed changes
            armature.object = target_armature

        if reparent:
            mesh.parent = target_armature
<<<<<<< Updated upstream
            # Move to collection
=======

>>>>>>> Stashed changes
            for col in list(mesh.users_collection):
                col.objects.unlink(mesh)
            target_collection.objects.link(mesh)

<<<<<<< Updated upstream
    return MeshToolResult.success()


def create_color_attributes(obj):
    """Create color attributes for garment support."""
    mesh = obj.data

    attrs = [
        ("_GARMENTSUPPORTWEIGHT", (1.0, 0.0, 0.0, 1.0)),
        ("_GARMENTSUPPORTCAP", (0.0, 0.0, 0.0, 1.0)),
        ]

    for name, color in attrs:
        if name in mesh.color_attributes:
            continue

        attr = mesh.color_attributes.new(
                name=name,
                domain='CORNER',
                type='BYTE_COLOR'
                )

        for i in range(len(attr.data)):
            attr.data[i].color = color
=======
    _LOG.info(
        "Armature target updated: target=%s meshes=%d reparent=%s",
        target_armature.name,
        len(meshes),
        bool(reparent),
    )
    return OperationResult.finished()


def create_color_attributes(obj):
    """Create canonical GarmentSupport color attributes on the mesh vertex domain"""
    mesh = obj.data
    for name, color in GARMENT_ATTRIBUTE_DEFAULTS.items():
        if name in mesh.color_attributes:
            continue
        attribute = mesh.color_attributes.new(
            name=name,
            domain=GARMENT_ATTRIBUTE_DOMAIN,
            type=GARMENT_ATTRIBUTE_TYPE,
        )
        if not attribute.data:
            continue
        field = "color_srgb" if attribute.data_type == "BYTE_COLOR" else "color"
        attribute.data.foreach_set(field, tuple(color) * len(attribute.data))
>>>>>>> Stashed changes
