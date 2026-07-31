import bpy
from ..services.arrangement_service import execute_create_arrangement_panel
from ..services.avatar_service import (
    execute_add_cloth_collider,
    execute_clear_avatar_profile,
    execute_fit_avatar_colliders,
    execute_generate_avatar_anchors,
    execute_remove_cloth_collider,
    execute_setup_cloth_colliders,
    execute_validate_avatar_profile,
)
from ..services.garment_service import (
    execute_add_motion_constraint_zone,
    execute_apply_sample_cloth_defaults,
    execute_assign_avatar_to_garment,
    execute_clear_cloth_pins,
    execute_copy_pins_to_motion_constraints,
    execute_create_fixed_seam_pins,
    execute_create_motion_constraint_group,
    execute_create_separation_constraint_group,
    execute_pin_cloth_verts,
    execute_pin_upper_garment_band,
    execute_prepare_garment,
    execute_unpin_cloth_verts,
    execute_validate_garment,
)
from ..services.seam_service import (
    execute_build_seam_constraint_groups,
    execute_capture_seam_side,
    execute_create_seam_pair_from_selection,
    execute_create_stitched_panel_mesh,
    execute_remove_seam_pair,
    execute_select_open_boundary_edges,
    execute_select_seam_side,
)
from ..services.simulation_service import execute_apply_cloth_sim, execute_reset_garment_sim

class CP77_OT_setup_cloth_colliders(bpy.types.Operator):
    bl_idname = 'cp77.setup_cloth_colliders'
    bl_label = 'Create Avatar Collision Profile'
    bl_description = 'Generate an avatar collision mannequin from the active armature'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_setup_cloth_colliders(context, self.report).blender_status

class CP77_OT_add_cloth_collider(bpy.types.Operator):
    bl_idname = 'cp77.add_cloth_collider'
    bl_label = 'Add Cloth Collider'

    def execute(self, context):
        return execute_add_cloth_collider(context, self.report).blender_status

class CP77_OT_remove_cloth_collider(bpy.types.Operator):
    bl_idname = 'cp77.remove_cloth_collider'
    bl_label = 'Remove Cloth Collider'

    def execute(self, context):
        return execute_remove_cloth_collider(context, self.report).blender_status

class CP77_OT_fit_avatar_colliders(bpy.types.Operator):
    bl_idname = 'cp77.fit_avatar_colliders'
    bl_label = 'Fit Colliders To Body Mesh'
    bl_description = 'Estimate collider radii from the assigned body mesh and avatar bone weights'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_fit_avatar_colliders(context, self.report).blender_status

class CP77_OT_generate_avatar_anchors(bpy.types.Operator):
    bl_idname = 'cp77.generate_avatar_anchors'
    bl_label = 'Generate Arrangement Anchors'
    bl_description = 'Create named avatar anchors for garment placement and future arrangement tools'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_generate_avatar_anchors(context, self.report).blender_status

class CP77_OT_validate_avatar_profile(bpy.types.Operator):
    bl_idname = 'cp77.validate_avatar_profile'
    bl_label = 'Validate Avatar Profile'
    bl_description = 'Validate the active armature as a garment collision avatar'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_validate_avatar_profile(context, self.report).blender_status

class CP77_OT_clear_avatar_profile(bpy.types.Operator):
    bl_idname = 'cp77.clear_avatar_profile'
    bl_label = 'Clear Avatar Profile'
    bl_description = 'Remove generated avatar colliders and arrangement anchors from the active armature'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_clear_avatar_profile(context, self.report).blender_status

class CP77_OT_assign_avatar_to_garment(bpy.types.Operator):
    bl_idname = 'cp77.assign_avatar_to_garment'
    bl_label = 'Use Selected Avatar'
    bl_description = 'Assign the selected armature avatar profile to the active garment mesh'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_assign_avatar_to_garment(context, self.report).blender_status

class CP77_OT_validate_garment(bpy.types.Operator):
    bl_idname = 'cp77.validate_garment'
    bl_label = 'Validate Garment'
    bl_description = 'Check the active cloth mesh for common setup problems before simulation'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_validate_garment(context, self.report).blender_status

class CP77_OT_prepare_garment(bpy.types.Operator):
    bl_idname = 'cp77.prepare_garment'
    bl_label = 'Prepare Garment'
    bl_description = 'Validate and build the PhysX/NvCloth scene for the active garment'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_prepare_garment(context, self.report).blender_status

class CP77_OT_pin_cloth_verts(bpy.types.Operator):
    bl_idname = 'cp77.pin_cloth_verts'
    bl_label = 'Pin Selected'
    bl_description = 'Add selected vertices to the configured pin group'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_pin_cloth_verts(context, self.report).blender_status

class CP77_OT_unpin_cloth_verts(bpy.types.Operator):
    bl_idname = 'cp77.unpin_cloth_verts'
    bl_label = 'Unpin Selected'
    bl_description = 'Remove selected vertices from the configured pin group'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_unpin_cloth_verts(context, self.report).blender_status

class CP77_OT_pin_upper_garment_band(bpy.types.Operator):
    bl_idname = 'cp77.pin_upper_garment_band'
    bl_label = 'Pin Upper Band'
    bl_description = 'Pin the highest band of garment vertices as a quick waistband/collar/cape anchor'
    bl_options = {'REGISTER', 'UNDO'}
    band_percent: bpy.props.FloatProperty(name='Band', default=0.08, min=0.01, max=0.5)

    def execute(self, context):
        return execute_pin_upper_garment_band(context, self.report, self.band_percent).blender_status

class CP77_OT_clear_cloth_pins(bpy.types.Operator):
    bl_idname = 'cp77.clear_cloth_pins'
    bl_label = 'Clear Pins'
    bl_description = 'Remove all vertices from the configured pin group'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_clear_cloth_pins(context, self.report).blender_status

class CP77_OT_create_motion_constraint_group(bpy.types.Operator):
    bl_idname = 'cp77.create_motion_constraint_group'
    bl_label = 'Create Motion Group'
    bl_description = "Create the garment's soft motion-constraint vertex group"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_create_motion_constraint_group(context, self.report).blender_status

class CP77_OT_copy_pins_to_motion_constraints(bpy.types.Operator):
    bl_idname = 'cp77.copy_pins_to_motion_constraints'
    bl_label = 'Pins To Motion'
    bl_description = 'Copy pin weights into the motion-constraint group'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_copy_pins_to_motion_constraints(context, self.report).blender_status

class CP77_OT_create_separation_constraint_group(bpy.types.Operator):
    bl_idname = 'cp77.create_separation_constraint_group'
    bl_label = 'Create Separation Group'
    bl_description = "Create the garment's separation-constraint vertex group"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_create_separation_constraint_group(context, self.report).blender_status

class CP77_OT_apply_sample_cloth_defaults(bpy.types.Operator):
    bl_idname = 'cp77.apply_sample_cloth_defaults'
    bl_label = 'Apply Native Defaults'
    bl_description = 'Apply sample-aligned NvCloth defaults for avatar garment simulation'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_apply_sample_cloth_defaults(context, self.report).blender_status

class CP77_OT_create_fixed_seam_pins(bpy.types.Operator):
    bl_idname = 'cp77.create_fixed_seam_pins'
    bl_label = 'Fixed Seam Pins'
    bl_description = 'Pin selected seam vertices as fixed NvCloth particles'
    bl_options = {'REGISTER', 'UNDO'}
    fallback_band: bpy.props.EnumProperty(name='Fallback', items=[('SELECTED', 'Selected Only', 'Only use selected vertices'), ('UPPER', 'Upper Band', 'Use the highest local-Z garment band if nothing is selected'), ('LOWER', 'Lower Band', 'Use the lowest local-Z garment band if nothing is selected')], default='SELECTED')
    band_percent: bpy.props.FloatProperty(name='Band', default=0.06, min=0.01, max=0.5)

    def execute(self, context):
        return execute_create_fixed_seam_pins(context, self.report, self.band_percent, self.fallback_band).blender_status

class CP77_OT_add_motion_constraint_zone(bpy.types.Operator):
    bl_idname = 'cp77.add_motion_constraint_zone'
    bl_label = 'Add Motion Zone'
    bl_description = "Add selected or inferred vertices to the garment's soft NvCloth motion-constraint group"
    bl_options = {'REGISTER', 'UNDO'}
    zone_type: bpy.props.EnumProperty(name='Zone', items=[('COLLAR', 'Collar', 'Soft collar/cape neckline constraint'), ('WAIST', 'Waistband', 'Soft waistband or hem control'), ('LEFT_CUFF', 'Left Cuff', 'Soft cuff control on the local negative-X side'), ('RIGHT_CUFF', 'Right Cuff', 'Soft cuff control on the local positive-X side'), ('TACKS', 'Temporary Tacks', 'Soft temporary tacks from selected vertices'), ('SELECTED', 'Selected', 'Use selected vertices without changing defaults')], default='SELECTED')
    weight: bpy.props.FloatProperty(name='Weight', default=1.0, min=0.0, max=1.0)
    band_percent: bpy.props.FloatProperty(name='Band', default=0.08, min=0.01, max=0.5)

    def execute(self, context):
        return execute_add_motion_constraint_zone(context, self.report, self.band_percent, self.weight, self.zone_type).blender_status

class CP77_OT_select_open_boundary_edges(bpy.types.Operator):
    bl_idname = 'cp77.select_open_boundary_edges'
    bl_label = 'Select Boundary Edges'
    bl_description = 'Select open boundary edges on the active garment panel'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_select_open_boundary_edges(context, self.report).blender_status

class CP77_OT_remove_seam_pair(bpy.types.Operator):
    bl_idname = 'cp77.remove_seam_pair'
    bl_label = 'Remove Seam Pair'
    bl_description = 'Remove the active seam pair from the garment'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_remove_seam_pair(context, self.report).blender_status

class CP77_OT_create_seam_pair_from_selection(bpy.types.Operator):
    bl_idname = 'cp77.create_seam_pair_from_selection'
    bl_label = 'Create Seam Pair'
    bl_description = 'Capture selected edge chains from the active panel and one selected target panel'
    bl_options = {'REGISTER', 'UNDO'}
    name: bpy.props.StringProperty(name='Name', default='Seam Pair')

    def execute(self, context):
        return execute_create_seam_pair_from_selection(context, self.report, self.name).blender_status

class CP77_OT_capture_seam_side(bpy.types.Operator):
    bl_idname = 'cp77.capture_seam_side'
    bl_label = 'Capture Seam Side'
    bl_description = 'Capture the selected edge chain into the active seam pair'
    bl_options = {'REGISTER', 'UNDO'}
    side: bpy.props.EnumProperty(name='Side', items=[('SOURCE', 'Source', 'Capture on the active garment'), ('TARGET', 'Target', 'Capture target side from active or selected target mesh')], default='SOURCE')

    def execute(self, context):
        return execute_capture_seam_side(context, self.report, self.side).blender_status

class CP77_OT_select_seam_side(bpy.types.Operator):
    bl_idname = 'cp77.select_seam_side'
    bl_label = 'Select Seam Side'
    bl_description = 'Restore a captured seam side as the current mesh selection'
    bl_options = {'REGISTER', 'UNDO'}
    side: bpy.props.EnumProperty(name='Side', items=[('SOURCE', 'Source', ''), ('TARGET', 'Target', '')], default='SOURCE')

    def execute(self, context):
        return execute_select_seam_side(context, self.report, self.side).blender_status

class CP77_OT_build_seam_constraint_groups(bpy.types.Operator):
    bl_idname = 'cp77.build_seam_constraint_groups'
    bl_label = 'Build Seam Groups'
    bl_description = 'Create vertex groups from the active seam pair for pins and soft motion constraints'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_build_seam_constraint_groups(context, self.report).blender_status

class CP77_OT_create_stitched_panel_mesh(bpy.types.Operator):
    bl_idname = 'cp77.create_stitched_panel_mesh'
    bl_label = 'Create Stitched Mesh'
    bl_description = 'Create a single garment mesh by bridging the active seam pair'
    bl_options = {'REGISTER', 'UNDO'}
    hide_sources: bpy.props.BoolProperty(name='Hide Source Panels', default=True)
    reverse_target: bpy.props.BoolProperty(name='Reverse Target', default=False)

    def execute(self, context):
        return execute_create_stitched_panel_mesh(context, self.report, self.hide_sources, self.reverse_target).blender_status

class CP77_OT_create_arrangement_panel(bpy.types.Operator):
    bl_idname = 'cp77.create_arrangement_panel'
    bl_label = 'Create Arrangement Panel'
    bl_description = 'Generate a simple cloth panel from avatar anchors and attach it with garment constraints'
    bl_options = {'REGISTER', 'UNDO'}
    panel_type: bpy.props.EnumProperty(name='Panel', items=[('TORSO_FRONT', 'Front Torso', 'Panel between chest and waist in front of the avatar'), ('TORSO_BACK', 'Back Torso', 'Panel between chest and waist behind the avatar'), ('SKIRT_FRONT', 'Front Skirt', 'Waist-hung front skirt panel'), ('CAPE_BACK', 'Back Cape', 'Shoulder/collar-hung cape panel'), ('LEFT_SLEEVE', 'Left Sleeve', 'Panel along left shoulder to wrist'), ('RIGHT_SLEEVE', 'Right Sleeve', 'Panel along right shoulder to wrist')], default='TORSO_FRONT')
    width: bpy.props.FloatProperty(name='Width', default=0.0, min=0.0, max=10.0)
    height: bpy.props.FloatProperty(name='Height', default=0.0, min=0.0, max=10.0)
    offset: bpy.props.FloatProperty(name='Offset', default=0.08, min=-1.0, max=1.0)
    segments_x: bpy.props.IntProperty(name='X Segments', default=8, min=1, max=128)
    segments_y: bpy.props.IntProperty(name='Y Segments', default=12, min=1, max=128)

    def execute(self, context):
        return execute_create_arrangement_panel(context, self.report, self.height, self.offset, self.panel_type, self.segments_x, self.segments_y, self.width).blender_status

class CP77_OT_apply_cloth_sim(bpy.types.Operator):
    bl_idname = 'cp77.apply_cloth_sim'
    bl_label = 'Bake Cloth'
    bl_description = 'Bake the current simulated cloth pose non-destructively or commit it to the mesh'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_apply_cloth_sim(context, self.report).blender_status

class CP77_OT_reset_garment_sim(bpy.types.Operator):
    bl_idname = 'cp77.reset_garment_sim'
    bl_label = 'Reset Garment'
    bl_description = 'Stop simulation, clear the cloth handle, and restore disabled deform modifiers'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return execute_reset_garment_sim(context, self.report).blender_status
CLOTH_OPERATOR_CLASSES = (CP77_OT_setup_cloth_colliders, CP77_OT_add_cloth_collider, CP77_OT_remove_cloth_collider, CP77_OT_fit_avatar_colliders, CP77_OT_generate_avatar_anchors, CP77_OT_validate_avatar_profile, CP77_OT_clear_avatar_profile, CP77_OT_assign_avatar_to_garment, CP77_OT_validate_garment, CP77_OT_prepare_garment, CP77_OT_pin_cloth_verts, CP77_OT_unpin_cloth_verts, CP77_OT_pin_upper_garment_band, CP77_OT_clear_cloth_pins, CP77_OT_create_motion_constraint_group, CP77_OT_copy_pins_to_motion_constraints, CP77_OT_create_separation_constraint_group, CP77_OT_apply_sample_cloth_defaults, CP77_OT_create_fixed_seam_pins, CP77_OT_add_motion_constraint_zone, CP77_OT_select_open_boundary_edges, CP77_OT_remove_seam_pair, CP77_OT_create_seam_pair_from_selection, CP77_OT_capture_seam_side, CP77_OT_select_seam_side, CP77_OT_build_seam_constraint_groups, CP77_OT_create_stitched_panel_mesh, CP77_OT_create_arrangement_panel, CP77_OT_apply_cloth_sim, CP77_OT_reset_garment_sim)
