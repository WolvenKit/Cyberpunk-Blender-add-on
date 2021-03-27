import bpy

from io_scene_gltf2.blender.imp.gltf2_blender_image import BlenderImage
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from io_scene_gltf2.blender.imp.gltf2_blender_gltf import BlenderGlTF
gltf_importer = glTFImporter("E:\\stuff\\bb.gltf", { "files": None, "loglevel": 0, "import_pack_images" :True, "merge_vertices" :False, "import_shading" : 'NORMALS', "bone_heuristic":'TEMPERANCE', "guess_original_bind_pose" : True})
gltf_importer.read()
gltf_importer.checks()

for img in gltf_importer.data.images:
    img.blender_image_name = None
    
BlenderImage.create(gltf_importer,1)