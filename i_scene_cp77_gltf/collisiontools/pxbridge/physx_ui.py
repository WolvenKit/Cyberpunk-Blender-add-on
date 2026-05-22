import bpy
from mathutils import Vector, Matrix


class PhysXToolsGizmoGroup(bpy.types.GizmoGroup):
    bl_idname = "PHYSX_GGT_tools"
    bl_label = "PhysX Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT'}

    @classmethod
    def poll(cls, context):
        return context.scene.physx.is_initialized

    def setup(self, context):
        gz_force = self.gizmos.new("GIZMO_GT_move_3d")
        gz_force.scale_basis = 0.6
        gz_force.line_width = 2.0

        def get_force(): return list(context.scene.physx.force_value)

        def set_force(v): context.scene.physx.force_value = v

        gz_force.target_set_handler("offset", get=get_force, set=set_force)
        self.force_gizmo = gz_force

        gz_grab = self.gizmos.new("GIZMO_GT_move_3d")
        gz_grab.scale_basis = 1.0
        gz_grab.line_width = 3.0

        def get_pos():
            v = context.scene.physx.manipulator_pos
            return [v[0], v[1], v[2]]

        def set_pos(v): context.scene.physx.manipulator_pos = v

        gz_grab.target_set_handler("offset", get=get_pos, set=set_pos)
        self.grab_gizmo = gz_grab

    def draw_prepare(self, context):
        px_s = context.scene.physx
        if px_s.use_grab_mode:
            self.force_gizmo.hide = True
            self.grab_gizmo.hide = False
            try:
                pos = Vector(px_s.manipulator_pos)
                self.grab_gizmo.matrix_basis = Matrix.Translation(pos).to_4x4()
            except:
                pass
        else:
            self.grab_gizmo.hide = True
            obj = context.object
            if obj and obj.physx.actor_type == 'DYNAMIC':
                self.force_gizmo.hide = False
                if px_s.use_force_pos:
                    start_loc = context.scene.cursor.location
                else:
                    start_loc = obj.matrix_world.to_translation()
                self.force_gizmo.matrix_basis = Matrix.Translation(start_loc).to_4x4()
            else:
                self.force_gizmo.hide = True


class PHYSX_UL_actor_list(bpy.types.UIList):
    """Actor list UI with bone parenting indicator"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if not item.obj_ref:
            layout.label(text="<Error>", icon='ERROR')
            return
        layout.prop(item.obj_ref, "name", text="", emboss=False, icon='OBJECT_DATAMODE')
        layout.prop(item.obj_ref.physx, "actor_type", text="")
        if item.use_bone_parent and item.target_bone != "NONE":
            bone_col = layout.column()
            bone_col.scale_x = 0.5
            bone_col.label(text="", icon='BONE_DATA')
            layout.label(text=f"{item.target_bone}", icon='DOT')


class PHYSX_UL_shape_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icon_map = {
            'BOX': 'MESH_CUBE',
            'SPHERE': 'MESH_UVSPHERE',
            'CAPSULE': 'MESH_CAPSULE',
            'CONVEX': 'MESH_ICOSPHERE',
            'TRIANGLE': 'MESH_DATA',
            'HEIGHTFIELD': 'MESH_GRID'
            }
        shape_icon = icon_map.get(item.shape_type, 'MESH_CUBE')

        layout.prop(item, "name", text="", emboss=False, icon=shape_icon)
        layout.prop(item, "shape_type", text="")