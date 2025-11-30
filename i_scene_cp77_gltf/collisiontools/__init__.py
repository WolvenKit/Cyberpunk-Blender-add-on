import bpy
from ..cyber_props import *
from bpy.types import (Operator, Panel)

from .collisions import *
from ..main.common import get_classes

class CP77CollisionGenerator(Operator):
    bl_idname = "generate_cp77.collisions"
    bl_label = "Generate Collider"
    bl_options = {'REGISTER', "UNDO"}
    bl_description = "Generate Colliders for use with Cyberpunk 2077" 

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props
        CP77CollisionGen(self, context,props.matchSize, props.collision_type, props.collision_shape, props.sampleverts, props.radius, props.height, props.physics_material)
        return {"FINISHED"}
    
    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.5,align=True)
        split.label(text="Collision Type:")
        split.prop(props, 'collision_type', text="")
        if props.collision_type == 'TERRAIN':
            return
        row = layout.row(align=True)
        split = row.split(factor=0.5,align=True)
        split.label(text="Collision Shape:")
        split.prop(props, 'collision_shape', text="")
        row = layout.row(align=True)
        split = row.split(factor=0.5,align=True)
        split.label(text="Material:")
        split.prop(props, 'physics_material', text="")
        row = layout.row(align=True)
        split = row.split(factor=0.5,align=True)
        if props.collision_shape == 'CONVEX':
            row.label(text="Vertices to Sample:")
            row.prop(props,"sampleverts", text="")

        if props.collision_shape == 'CAPSULE':
            row.prop(props, "matchSize", text="Match the size of the selected mesh")
            if not props.matchSize:
                row = layout.row(align=True)
                row.label(text="Radius:")
                row.prop(props, "radius", text="")
                row.label(text="Height:")
                row.prop(props, "height", text="")


class CP77PhysMatAssign(Operator):
    bl_idname = "object.set_physics_material"
    bl_label = "Set Physics Properties"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Update the Collilder Properties Based on the current Physmat"

    # Need to implement a callback here so that changing the material automatically updates the other properties

    def execute(self, context):
        selected_physmat = context.object["physics_material"]

        # Find the corresponding material data
        physmat_data = next((mat for mat in physmats_data if mat["Name"] == selected_physmat), None)

        if physmat_data is not None:
        
            # Set custom properties on the object
            obj = context.object
            props = context.scene.cp77_panel_props
            obj['simulationType'] = props.simulation_type
            obj["physics_material"] = props.physics_material
            obj["Density"] = physmat_data.get("Density", 0)
            obj["staticFriction"] = physmat_data.get("staticFriction", 0)
            obj["dynamicFriction"] = physmat_data.get("dynamicFriction", 0)
            obj["restitution"] = physmat_data.get("restitution", 0)
            volume = calculate_mesh_volume(obj)
            obj['volume'] = volume
            # Calculate mass based on density and mesh volume
            mass = obj["Density"] * volume
            obj["Mass"] = mass
            obj['collisionType'] = props.collision_type
            a, b, c = obj.dimensions
            Ix = (1 / 12) * obj["Density"] * volume * (b**2 + c**2)
            Iy = (1 / 12) * obj["Density"] * volume * (a**2 + c**2)
            Iz = (1 / 12) * obj["Density"] * volume * (a**2 + b**2)

            # Set the inertia
            obj["inertia_X"] = Ix
            obj["inertia_Y"] = Iy
            obj["inertia_Z"] = Iz
            
        return {'FINISHED'}


class CP77_PT_CollisionTools(Panel):
    bl_label = "Collision Tools"
    bl_idname = "CP77_PT_collisions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        if cp77_addon_prefs.context_only:
            return context.active_object and context.active_object.type == 'MESH' 
        else:
            return context

    def draw(self, context):
        layout = self.layout
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences

        if cp77_addon_prefs.show_modtools:
            if cp77_addon_prefs.show_collisiontools:
                props = context.scene.cp77_panel_props
                box = layout.box()
                row = box.row(align=True)
                row.operator("generate_cp77.collisions")
                row = box.row(align=True)
                row.operator("import_scene.phys")
                row = box.row(align=True)
                row.operator("export_scene.collisions")
                obj = context.active_object
                if obj and "collisionType" in obj:
                    box = layout.box()
                    box.label(text='Collision Properties')
                    row = box.row()
                    split = row.split(factor=0.3,align=True)
                    split.label(text='Type:')
                    split.prop(props, 'collision_type', text="")
                    row = box.row()
                    split = row.split(factor=0.5,align=True)
                    split.label(text="simulationType")
                    split.prop(props, 'simulation_type', text="")
                    row = box.row()
                    split = row.split(factor=0.3,align=True)
                    split.label(text='Material:')
                    split.prop(props, 'physics_material', text="")
                    row = box.row()
                    row.label(text=f"Mass: {obj.get('Mass', 0):.2f}")
                    row = box.row()
                    row.alignment = 'LEFT'
                    col = row.column(align=True)
                    col.label(text='Inertia:')
                    row = box.row()
                    row.alignment = 'CENTER'
                    col = row.column(align=True)
                    split = col.split(factor=0.33,align=True)
                    split.label(text=f"X: {obj.get('inertia_X', 0):.0f}")
                    split.label(text=f"Y: {obj.get('inertia_Y', 0):.0f}")
                    split.label(text=f"Z: {obj.get('inertia_Z', 0):.0f}")
                    row = box.row()
                    row.operator('object.set_physics_material')
                    if obj['collisionShape'] =='physicsColliderConvex':
                        row = box.row()
                        row.operator('mesh.convex_hull', text="Regenerate Convex Hull")
                        
operators, other_classes = get_classes(sys.modules[__name__])


def register_collisiontools():
    for cls in operators:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    for cls in other_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)


def unregister_collisiontools():
    for cls in reversed(other_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)