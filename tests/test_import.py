import bpy

def test_import_mesh():
    bpy.ops.import_scene.gltf(filepath="tests/test_files/woman_average_q115_netrunner_suit.glb")

def test_cube():
    bpy.ops.mesh.primitive_cube_add(size=4)
    cube_obj = bpy.context.active_object
    cube_obj.location.x = 5
    cube_obj.location.y = 5
    cube_obj.location.z = 5
