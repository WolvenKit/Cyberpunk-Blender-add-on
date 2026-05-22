from ..jsontool import JSONTool
import bpy
import bmesh
import time
from ..collisiontools.pxbridge.io_phys import import_collider_as_actor

def cp77_phys_import(filepath, rig=None, chassis_z=None):
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    start_time = time.time()
    physJsonPath = filepath
    collision_type = 'VEHICLE'
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            if space.type == 'VIEW_3D':
                space.shading.wireframe_color_type = 'OBJECT'

    data = JSONTool.jsonload(physJsonPath)

    for index, i in enumerate(data['Data']['RootChunk']['bodies']):
        bname = (i['Data']['name']['$value'])
        collection_name = bname
        new_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(new_collection)

        for index, i in enumerate(data['Data']['RootChunk']['bodies'][0]['Data']['collisionShapes']):
            collision_shape = i['Data']['$type']
            physmat = i['Data']['material']['$value']
            submeshName = str(index) + '_' + collision_shape
            transform = i['Data']['localToBody']
            print(bname, collision_shape, physmat, submeshName, transform)
            
            # Pass to pxbridge to create a native PhysX actor instead of a mesh representation
            obj = import_collider_as_actor(i, submeshName, new_collection)
            
            if obj and rig is not None:
                constraint = obj.constraints.new('CHILD_OF')
                constraint.target = rig
                constraint.subtarget = 'Base'
                bpy.ops.constraint.childof_set_inverse(constraint="Child Of", owner='OBJECT')
                if chassis_z is not None:
                    obj.delta_location[2] = chassis_z

    if not cp77_addon_prefs.non_verbose:
        print(f"phys collider Import Time: {(time.time() - start_time)} Seconds")
