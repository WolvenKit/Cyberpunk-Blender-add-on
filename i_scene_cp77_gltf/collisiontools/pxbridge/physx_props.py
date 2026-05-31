import bpy
from . import physx_utils, viz

def update_gravity_cb(self, context):
    if self.is_initialized:
        try:
            from . import pxveh34 as _bridge
            g = self.gravity
            _bridge.set_gravity(g[0], g[1], g[2])
        except ImportError:
            pass
    return None

def get_armature_items(self, context):
    """Populate enum with all armature objects in the scene"""
    items = [("NONE", "None", "No armature selected")]
    for obj in context.scene.objects:
        if obj.type == 'ARMATURE':
            items.append((obj.name, obj.name, f"Armature: {obj.name}"))
    return items

def update_parent_armature(self, context):
    """Reset bone selection when armature changes"""
    self.target_bone = "NONE"

def get_bone_items(self, context):
    """Populate enum with all bones in the selected parent armature"""
    items = [("NONE", "None", "No bone selected")]
    if self.parent_armature and self.parent_armature != "NONE":
        armature_obj = context.scene.objects.get(self.parent_armature)
        if armature_obj and armature_obj.type == 'ARMATURE':
            for bone in armature_obj.data.bones:
                items.append((bone.name, bone.name, f"Bone: {bone.name}"))
    return items

class PhysXShapeItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(default="Shape")
    shape_type: bpy.props.EnumProperty(
        name="Type",
        items=[
            ('BOX', "Box", ""),
            ('SPHERE', "Sphere", ""),
            ('CAPSULE', "Capsule", ""),
            ('CONVEX', "Convex", ""),
            ('TRIANGLE', "Triangle", ""),
            ('HEIGHTFIELD', "HeightField", "")
        ],
        default='BOX'
    )
    dim_x: bpy.props.FloatProperty(name="X", default=1.0, min=0.01, update=viz.update_shader_visuals)
    dim_y: bpy.props.FloatProperty(name="Y", default=1.0, min=0.01, update=viz.update_shader_visuals)
    dim_z: bpy.props.FloatProperty(name="Z", default=1.0, min=0.01, update=viz.update_shader_visuals)
    hf_resolution: bpy.props.IntProperty(name="Grid Res", default=64, min=2, max=1024)
    local_pos: bpy.props.FloatVectorProperty(name="Position", subtype='TRANSLATION', update=viz.update_shader_visuals)
    local_rot: bpy.props.FloatVectorProperty(
        name="Orientation", subtype='QUATERNION', size=4, default=(1.0, 0.0, 0.0, 0.0), update=viz.update_shader_visuals
    )
    physics_material: bpy.props.EnumProperty(items=physx_utils.get_physmat_items, name="Material")
    cooked_data: bpy.props.StringProperty()
    is_cooked: bpy.props.BoolProperty(default=False)
    vertex_limit: bpy.props.IntProperty(name="Hull Verts", default=64, min=8, max=256)

    collision_preset: bpy.props.EnumProperty(
        name="Collision Preset",
        items=physx_utils.presets_lib.get_preset_items,
        update=physx_utils.update_collision_bits,
    )

    filter_group: bpy.props.BoolVectorProperty(size=20, subtype='LAYER_MEMBER')
    filter_mask: bpy.props.BoolVectorProperty(size=20, subtype='LAYER_MEMBER')
    filter_query: bpy.props.BoolVectorProperty(size=20, subtype='LAYER_MEMBER')

class PhysXActorItem(bpy.types.PropertyGroup):
    obj_ref: bpy.props.PointerProperty(type=bpy.types.Object)
    actor_handle: bpy.props.StringProperty(default="0")

    use_bone_parent: bpy.props.BoolProperty(
        name="Use Bone Parent",
        description="Attach this actor to an armature bone instead of object origin",
        default=False
    )
    parent_armature: bpy.props.EnumProperty(
        name="Parent Armature",
        description="Select armature object containing the target bone",
        items=get_armature_items,
        update=update_parent_armature
    )
    target_bone: bpy.props.EnumProperty(
        name="Target Bone",
        description="Select bone within parent armature (bone head is attachment point)",
        items=get_bone_items
    )

    def poll_armature_availability(self):
        """Check if referenced object is attached to/is an armature"""
        obj = self.obj_ref
        if not obj:
            return False

        if obj.type == 'ARMATURE':
            return True

        if obj.parent and obj.parent.type == 'ARMATURE':
            return True

        for mod in obj.modifiers:
            if mod.type == 'ARMATURE':
                return True

        for const in obj.constraints:
            if const.type in {'CHILD_OF', 'ARMATURE'} and const.target and const.target.type == 'ARMATURE':
                return True

        return False

class PhysXObjectProperties(bpy.types.PropertyGroup):
    actor_type: bpy.props.EnumProperty(
        name="Type",
        items=[('NONE', "Ignored", ""), ('STATIC', "Static", ""), ('DYNAMIC', "Dynamic", ""),
               ('KINEMATIC', "Kinematic", "")],
        default='STATIC'
    )
    is_terrain: bpy.props.BoolProperty(name="Is Terrain", default=False, description="Allow Heightfields")
    shapes: bpy.props.CollectionProperty(type=PhysXShapeItem)
    shape_index: bpy.props.IntProperty()
    mass: bpy.props.FloatProperty(name="Mass", default=10.0, min=0.001)
    com_offset: bpy.props.FloatVectorProperty(name="CoM Offset", subtype='TRANSLATION')
    inertia: bpy.props.FloatVectorProperty(name="Inertia", description="Custom inertia")

    calc_mass: bpy.props.BoolProperty(name="Mass", default=True)
    calc_inertia: bpy.props.BoolProperty(name="Inertia", default=True)
    calc_offset: bpy.props.BoolProperty(name="Offset", default=True)

class PhysXSceneProperties(bpy.types.PropertyGroup):
    is_initialized: bpy.props.BoolProperty(default=False)
    ui_tab: bpy.props.EnumProperty(
        items=[
            ('WORLD', "World", "World"),
            ('ACTORS', "Actors", "Actors"),
            ('SIM', "Simulation", "Simulation"),
            ('DANGLES', "Dangles", "Dangles"),
        ],
        default='WORLD'
    )
    scene_built: bpy.props.BoolProperty(default=False, name="Scene Built")
    sim_running: bpy.props.BoolProperty(name="Simulating", default=False)
    viz_enabled: bpy.props.BoolProperty(name="Debug Draw", default=True)

    active_actor_count: bpy.props.IntProperty(default=0)

    actors: bpy.props.CollectionProperty(type=PhysXActorItem)
    actor_list_index: bpy.props.IntProperty()

    gravity: bpy.props.FloatVectorProperty(
        name="Gravity", default=(0.0, 0.0, -9.81), subtype='ACCELERATION', update=update_gravity_cb
    )

    force_mode: bpy.props.EnumProperty(
        name="Mode",
        items=[('0', "Force", ""), ('1', "Impulse", ""), ('2', "Velocity", ""), ('3', "Acceleration", "")]
    )
    force_value: bpy.props.FloatVectorProperty(name="Vector", default=(0, 0, 1000))
    use_force_pos: bpy.props.BoolProperty(name="Use Cursor Pos", default=False)

    sim_steps: bpy.props.IntProperty(name="Steps", default=1, min=1)

    use_grab_mode: bpy.props.BoolProperty(
        name="Enable Manipulator",
        description="Spawn a kinematic sphere to push objects around",
        default=False
    )
    manipulator_pos: bpy.props.FloatVectorProperty(
        name="Hand Pos",
        subtype='TRANSLATION'
    )
    manipulator_handle: bpy.props.StringProperty(default="0")