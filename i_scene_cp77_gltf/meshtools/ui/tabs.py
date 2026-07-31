import bpy
from .validation import draw_glb_mesh_validation

from ...icons.cp77_icons import get_icon


def draw_cloth_tab(context, layout, has_mesh_selected):
        obj = context.active_object
        if obj and obj.type == 'ARMATURE':
            profile = obj.cp77_avatar

            box = layout.box()
            box.label(text="Avatar Profile", icon='ARMATURE_DATA')
            col = box.column(align=True)
            row = col.row(align=True)
            row.prop(profile, "enabled", text="")
            row.prop(profile, "profile_name", text="Profile")
            row.prop(profile, "state", text="State")
            row = col.row(align=True)
            row.prop(profile, "body_type", text="Body")
            row.prop(profile, "fitting_pose", text="Pose")
            col.prop(profile, "body_mesh", text="Fit Mesh")
            col.prop(profile, "status", text="Status")
            if profile.errors:
                msg = col.box()
                for line in profile.errors.splitlines()[:5]:
                    msg.label(text=line, icon='ERROR' if profile.state == 'ERROR' else 'INFO')
            row = col.row(align=True)
            row.operator("cp77.setup_cloth_colliders", text="Build Mannequin", icon='ARMATURE_DATA')
            row.operator("cp77.fit_avatar_colliders", text="Fit To Body", icon='MOD_SHRINKWRAP')
            row = col.row(align=True)
            row.operator("cp77.validate_avatar_profile", text="Validate")
            row.operator("cp77.clear_avatar_profile", text="Clear")

            box = layout.box()
            box.label(text="Native Collision Mannequin", icon='PHYSICS')
            col = box.column(align=True)
            col.prop(profile, "use_primitive_collision", text="Use Spheres / Capsules")
            row = col.row(align=True)
            row.label(text=f"Spheres: {profile.last_sphere_count}")
            row.label(text=f"Capsules: {profile.last_capsule_count}")
            row = col.row()
            row.template_list(
                "CP77_UL_cloth_colliders", "", obj, "cp77_cloth_colliders", obj, "cp77_cloth_collider_index"
                )
            buttons = row.column(align=True)
            buttons.operator("cp77.add_cloth_collider", icon='ADD', text="")
            buttons.operator("cp77.remove_cloth_collider", icon='REMOVE', text="")
            if obj.cp77_cloth_collider_index >= 0 and obj.cp77_cloth_collider_index < len(obj.cp77_cloth_colliders):
                item = obj.cp77_cloth_colliders[obj.cp77_cloth_collider_index]
                edit = layout.box()
                edit.label(text="Selected Collider")
                edit.prop(item, "name")
                edit.prop(item, "enabled")
                row = edit.row(align=True)
                row.prop(item, "collider_type")
                row.prop(item, "region")
                edit.prop_search(item, "bone", obj.data, "bones", text="Bone")
                if item.collider_type == 'CAPSULE':
                    edit.prop_search(item, "target_bone", obj.data, "bones", text="Target Bone")
                edit.prop(item, "radius")

            box = layout.box()
            box.label(text="Fit Padding", icon='MOD_SHRINKWRAP')
            col = box.column(align=True)
            col.prop(profile, "global_inflate")
            row = col.row(align=True)
            row.prop(profile, "torso_inflate")
            row.prop(profile, "pelvis_inflate")
            row = col.row(align=True)
            row.prop(profile, "arm_inflate")
            row.prop(profile, "leg_inflate")
            row = col.row(align=True)
            row.prop(profile, "head_inflate")
            row.prop(profile, "auto_fit_percentile")
            row = col.row(align=True)
            row.prop(profile, "min_radius")
            row.prop(profile, "max_radius")

            box = layout.box()
            box.label(text="Arrangement Anchors", icon='EMPTY_ARROWS')
            col = box.column(align=True)
            row = col.row(align=True)
            row.operator("cp77.generate_avatar_anchors", text="Generate Anchors")
            row.label(text=f"Anchors: {profile.last_anchor_count}")
            panel_box = col.box()
            panel_box.label(text="Arrangement Panels")
            row = panel_box.row(align=True)
            op = row.operator("cp77.create_arrangement_panel", text="Front Torso")
            op.panel_type = 'TORSO_FRONT'
            op = row.operator("cp77.create_arrangement_panel", text="Back Torso")
            op.panel_type = 'TORSO_BACK'
            row = panel_box.row(align=True)
            op = row.operator("cp77.create_arrangement_panel", text="Skirt")
            op.panel_type = 'SKIRT_FRONT'
            op = row.operator("cp77.create_arrangement_panel", text="Cape")
            op.panel_type = 'CAPE_BACK'
            row = panel_box.row(align=True)
            op = row.operator("cp77.create_arrangement_panel", text="Left Sleeve")
            op.panel_type = 'LEFT_SLEEVE'
            op = row.operator("cp77.create_arrangement_panel", text="Right Sleeve")
            op.panel_type = 'RIGHT_SLEEVE'
            row = col.row()
            row.template_list("CP77_UL_avatar_anchors", "", obj, "cp77_avatar_anchors", obj, "cp77_avatar_anchor_index")
            if obj.cp77_avatar_anchor_index >= 0 and obj.cp77_avatar_anchor_index < len(obj.cp77_avatar_anchors):
                anchor = obj.cp77_avatar_anchors[obj.cp77_avatar_anchor_index]
                edit = layout.box()
                edit.prop(anchor, "name")
                edit.prop(anchor, "anchor_type")
                edit.prop_search(anchor, "bone", obj.data, "bones", text="Bone")
                edit.prop(anchor, "local_pos")
            return

        if obj and obj.type == 'MESH':
            cloth = obj.cp77_cloth

            box = layout.box()
            box.label(text="Garment Setup", icon='MOD_CLOTH')
            col = box.column(align=True)
            col.prop(cloth, "enabled", text="Enable Garment Simulation")
            if not cloth.enabled:
                return
            row = col.row(align=True)
            row.prop(cloth, "workflow_state", text="State")
            row.prop(cloth, "garment_type", text="Type")
            row = col.row(align=True)
            row.prop(cloth, "avatar_armature", text="Avatar")
            row.operator("cp77.assign_avatar_to_garment", text="Use Selected")
            row = col.row(align=True)
            row.operator("cp77.validate_garment", text="Validate")
            row.operator("cp77.prepare_garment", text="Prepare / Rebuild")
            col.operator("cp77.apply_sample_cloth_defaults", text="Apply Native Defaults", icon='PRESET')
            col.prop(cloth, "validation_status", text="Status")
            if cloth.validation_errors:
                err = col.box()
                for line in cloth.validation_errors.splitlines()[:5]:
                    err.label(text=line, icon='ERROR' if cloth.workflow_state == 'ERROR' else 'INFO')
            row = col.row(align=True)
            row.label(text=f"Particles: {cloth.last_particle_count}")
            row.label(text=f"Tris: {cloth.last_triangle_count}")
            row = col.row(align=True)
            row.label(text=f"Pinned: {cloth.last_pinned_count}")
            row.label(text=f"Motion: {cloth.last_motion_constraint_count}")
            row.label(text=f"Colliders: {cloth.last_collider_count}")

            box = layout.box()
            box.label(text="Pins & Motion Constraints", icon='GROUP_VERTEX')
            col = box.column(align=True)
            col.prop_search(cloth, "pin_vg", obj, "vertex_groups", text="Hard Pin Group")
            row = col.row(align=True)
            row.operator("cp77.pin_cloth_verts", text="Pin Selected")
            row.operator("cp77.unpin_cloth_verts", text="Unpin Selected")
            row = col.row(align=True)
            row.operator("cp77.pin_upper_garment_band", text="Pin Upper Band")
            row.operator("cp77.clear_cloth_pins", text="Clear Pins")
            row = col.row(align=True)
            row.operator("cp77.create_fixed_seam_pins", text="Pin Selected Seam")
            op = row.operator("cp77.create_fixed_seam_pins", text="Pin Upper Seam")
            op.fallback_band = 'UPPER'
            row = col.row(align=True)
            row.prop(cloth, "auto_pin_fallback")
            row.prop(cloth, "pin_weight_threshold")
            col.separator()
            col.prop(cloth, "motion_constraint_source", text="Soft Motion")
            if cloth.motion_constraint_source == 'MOTION_GROUP':
                col.prop_search(cloth, "motion_constraint_vg", obj, "vertex_groups", text="Motion Group")
                row = col.row(align=True)
                row.operator("cp77.create_motion_constraint_group", text="Create Group")
                row.operator("cp77.copy_pins_to_motion_constraints", text="Pins To Motion")
            elif cloth.motion_constraint_source == 'PIN_GROUP':
                col.label(text="Uses the hard pin group as soft motion limits")
            zone = col.box()
            zone.label(text="Soft Zones")
            row = zone.row(align=True)
            op = row.operator("cp77.add_motion_constraint_zone", text="Collar")
            op.zone_type = 'COLLAR'
            op = row.operator("cp77.add_motion_constraint_zone", text="Waist")
            op.zone_type = 'WAIST'
            row = zone.row(align=True)
            op = row.operator("cp77.add_motion_constraint_zone", text="Left Cuff")
            op.zone_type = 'LEFT_CUFF'
            op = row.operator("cp77.add_motion_constraint_zone", text="Right Cuff")
            op.zone_type = 'RIGHT_CUFF'
            row = zone.row(align=True)
            op = row.operator("cp77.add_motion_constraint_zone", text="Selected Tacks")
            op.zone_type = 'TACKS'
            if cloth.motion_constraint_source != 'NONE':
                row = col.row(align=True)
                row.prop(cloth, "motion_constraint_radius", text="Radius")
                row.prop(cloth, "motion_constraint_min_radius", text="Tight")
                row = col.row(align=True)
                row.prop(cloth, "motion_constraint_stiffness", text="Stiffness")
                row.prop(cloth, "motion_constraint_scale", text="Scale")
                col.prop(cloth, "motion_constraint_bias", text="Bias")
            col.separator()
            col.prop(cloth, "separation_constraint_source", text="Separation")
            if cloth.separation_constraint_source == 'SEPARATION_GROUP':
                col.prop_search(cloth, "separation_constraint_vg", obj, "vertex_groups", text="Separation Group")
                row = col.row(align=True)
                row.operator("cp77.create_separation_constraint_group", text="Create Group")
                row.label(text=f"Active: {cloth.last_separation_constraint_count}")
                row = col.row(align=True)
                row.prop(cloth, "separation_constraint_radius", text="Radius")
                row.prop(cloth, "separation_constraint_offset", text="Normal Offset")

            box = layout.box()
            box.label(text="Seams & Sewing", icon='MOD_VERTEX_WEIGHT')
            col = box.column(align=True)
            row = col.row()
            row.template_list(
                "CP77_UL_garment_seam_pairs", "", obj, "cp77_garment_seams", obj, "cp77_garment_seam_index"
                )
            buttons = row.column(align=True)
            buttons.operator("cp77.create_seam_pair_from_selection", text="Add", icon='ADD')
            buttons.operator("cp77.remove_seam_pair", text="Remove", icon='REMOVE')
            buttons.operator("cp77.select_open_boundary_edges", text="Boundary", icon='EDGESEL')
            pair = None
            if obj.cp77_garment_seams and 0 <= obj.cp77_garment_seam_index < len(obj.cp77_garment_seams):
                pair = obj.cp77_garment_seams[obj.cp77_garment_seam_index]
            if pair:
                edit = col.box()
                edit.prop(pair, "name")
                edit.prop(pair, "target_object")
                row = edit.row(align=True)
                op = row.operator("cp77.capture_seam_side", text="Capture A")
                op.side = 'SOURCE'
                op = row.operator("cp77.capture_seam_side", text="Capture B")
                op.side = 'TARGET'
                row = edit.row(align=True)
                op = row.operator("cp77.select_seam_side", text="Select A")
                op.side = 'SOURCE'
                op = row.operator("cp77.select_seam_side", text="Select B")
                op.side = 'TARGET'
                row = edit.row(align=True)
                row.prop(pair, "stitch_distance", text="Distance")
                row.prop(pair, "stitch_strength", text="Strength")
                row = edit.row(align=True)
                row.prop(pair, "use_motion_constraints", text="Motion")
                row.prop(pair, "motion_radius", text="Radius")
                edit.prop(pair, "pin_endpoints")
                row = edit.row(align=True)
                row.operator("cp77.build_seam_constraint_groups", text="Build Groups")
                row.operator("cp77.create_stitched_panel_mesh", text="Create Stitched Mesh")
                edit.label(text=f"Status: {pair.status}")

            box = layout.box()
            box.label(text="Native Collision", icon='PHYSICS')
            col = box.column(align=True)
            avatar = cloth.avatar_armature
            if avatar and hasattr(avatar, "cp77_avatar"):
                profile = avatar.cp77_avatar
                row = col.row(align=True)
                row.label(text="NvCloth spheres/capsules", icon='CHECKMARK')
                row.prop(profile, "use_primitive_collision", text="Use")
            else:
                col.label(text="Assign an avatar profile for collision", icon='ERROR')
            col.prop(cloth, "collision_inflate", text="Collider Inflate")
            row = col.row(align=True)
            row.prop(cloth, "continuous_collision", text="CCD")
            row.prop(cloth, "collision_mass_scale", text="Mass Scale")
            col.label(text="Default: CCD on, mass scale 3.0; increase only for tunneling.")
            col.label(text=f"Mode: {obj.get('pxbridge_cloth_capsule_mode', 'not prepared')}")

            box = layout.box()
            box.label(text="Fabric & Solver", icon='MOD_PHYSICS')
            col = box.column(align=True)
            row = col.row(align=True)
            row.prop(cloth, "fabric_preset", text="Fabric")
            row.prop(cloth, "quality_preset", text="Quality")
            row = col.row(align=True)
            row.prop(cloth, "mass")
            row.prop(cloth, "friction")
            row.prop(cloth, "drag")
            row = col.row(align=True)
            row.prop(cloth, "solver_frequency")
            row.prop(cloth, "stiffness_frequency")
            row = col.row(align=True)
            row.prop(cloth, "damping")
            row.prop(cloth, "linear_drag")
            row = col.row(align=True)
            row.prop(cloth, "tether_scale")
            row.prop(cloth, "tether_stiffness")
            row = col.row(align=True)
            row.prop(cloth, "self_collision_distance")
            row.prop(cloth, "self_collision_stiffness")

            box = layout.box()
            box.label(text="Simulation & Bake", icon='PLAY')
            col = box.column(align=True)
            px_s = context.scene.physx
            if px_s.sim_running:
                col.operator("physx.stop_sim", icon='PAUSE', text="Pause Simulation")
            else:
                row = col.row(align=True)
                row.operator("physx.sim_step", icon='PLAY', text="Start / Resume")
                row.operator("physx.run_steps", text="Step")
            col.operator("cp77.reset_garment_sim", text="Reset Garment")
            row = col.row(align=True)
            row.prop(cloth, "bake_target", text="Bake")
            if cloth.bake_target == 'SHAPE_KEY':
                row.prop(cloth, "bake_shape_key", text="Shape Key")
            col.operator("cp77.apply_cloth_sim", icon='CHECKMARK', text="Bake Current Pose")
            return

        layout.label(text="Select an Armature to edit an avatar profile, or a Mesh to edit a garment")


def draw_utilities_tab(context, layout, has_mesh_selected, has_meshes_selected, has_armature_selected):
        draw_glb_mesh_validation(context, layout)

        # Clean up Armature
        if has_armature_selected:
            box = layout.box()
            col = box.column()
            col.label(text="Clean up Armature", icon_value=get_icon("ARMATURE"))
            col.operator('delete_unused_bones.cp77', text='Delete unused bones')

        # Mesh Cleanup
        box = layout.box()
        box.label(text="Mesh Cleanup", icon_value=get_icon("TRAUMA"))
        col = box.column()
        col.operator("cp77.submesh_prep")

        # Armature Target
        if has_mesh_selected or has_meshes_selected:
            box = layout.box()
            box.label(text="Armature", icon_value=get_icon("ARMATURE"))
            col = box.column()
            col.operator("cp77.set_armature", text="Change Armature Target")

        # Mirror Tools
        if has_mesh_selected or has_meshes_selected:
            box = layout.box()
            box.label(text="Mirror Tools", icon_value=get_icon("MIRROR"))
            col = box.column()
            col.operator("cp77.mirror_x_axis", text="Safely mirror")
            col.operator("cp77.mirror_vertex_groups", text="Mirror Vertex Groups")
            box.operator("cp77.rotate_obj", text="Rotate Selected Objects")


def draw_modelling_tab(context, layout, has_mesh_selected, has_meshes_selected):
        # Vert Tools
        box = layout.box()
        box.label(text="Vertex Groups", icon_value=get_icon("TRAUMA"))
        col = box.column()
        col.operator("cp77.group_verts", text="Group Ungrouped Verts")
        col.operator("cp77.del_empty_vgroup", text="Delete Unused Vert Groups")

        if not (has_mesh_selected or has_meshes_selected):
            box = layout.box()
            box.label(icon_value=get_icon("SCULPT"), text="Select a mesh")
            return

        # UV Checker
        box = layout.box()
        box.label(icon_value=get_icon("SCULPT"), text="Modelling:")
        col = box.column()

        if context.object.active_material and context.object.active_material.name == 'UV_Checker':
            col.operator("cp77.uv_unchecker", text="Remove UV Checker")
        else:
            col.operator("cp77.uv_checker", text="Apply UV Checker")

        col.operator("cp77.shrinkwrap", text="GarmentSupport/Decal")
        col.operator("cp77.trans_weights", text="Weight Transfer Tool")

        if has_mesh_selected and context.active_object.data.materials and any(
                mat.name.startswith('submesh_') for mat in context.active_object.data.materials if mat
                ):
            col.operator("cp77.safe_split", text="Split into submeshes")
        elif has_meshes_selected:
            col.operator("cp77.safe_join", text="Join Meshes")

        # AKL Autofitter
        box = layout.box()
        box.label(text="AKL Autofitter", icon_value=get_icon("REFIT"))
        col = box.column()
        col.operator("cp77.auto_fitter", text="Refit Selected Meshes")

        # Vertex Colours
        box = layout.box()
        box.label(text="Vertex Colours", icon="BRUSH_DATA")
        col = box.column()
        col.operator("cp77.apply_vertex_color_preset")
        col.operator("cp77.add_vertex_color_preset")
        col.operator("cp77.delete_vertex_color_preset")


def draw_characters_tab(context, layout, has_mesh_selected):
        box = layout.box()
        box.label(text="Characters", icon='MESH_DATA')
        col = box.column()
        col.operator("cp77.load_base_character", icon='IMPORT')

        char_props = context.scene.cp77_character_shape

        # Head shape sliders
        head_obj = None
        if char_props.head_mesh_names:
            for name in char_props.head_mesh_names.split(";"):
                obj = bpy.data.objects.get(name)
                if obj and obj.data.shape_keys:
                    head_obj = obj
                    break

        if head_obj:
            box = layout.box()
            box.label(text="Head Shape", icon='SHAPEKEY_DATA')
            col = box.column(align=True)
            col.prop(char_props, "eyes")
            col.prop(char_props, "nose")
            col.prop(char_props, "mouth")
            col.prop(char_props, "jaw")
            col.prop(char_props, "ears")

        # Body shape sliders
        body_obj = bpy.data.objects.get(char_props.body_mesh_name) if char_props.body_mesh_name else None
        if body_obj and body_obj.data.shape_keys:
            has_breast_keys = any("breast" in kb.name for kb in body_obj.data.shape_keys.key_blocks)
            if has_breast_keys:
                box = layout.box()
                box.label(text=f"Body Shape: {body_obj.name}", icon='SHAPEKEY_DATA')
                col = box.column(align=True)
                col.prop(char_props, "breasts")
