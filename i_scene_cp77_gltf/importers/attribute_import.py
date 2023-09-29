import bpy

from io_scene_gltf2.io.imp.gltf2_io_binary import BinaryData
from io_scene_gltf2.blender.imp.gltf2_blender_mesh import points_edges_tris
from io_scene_gltf2.blender.imp.gltf2_blender_mesh import squish

def manage_garment_support(existingMeshes, gltf_importer):
    curMeshCount = 0
    for name in bpy.data.meshes.keys():
        if name not in existingMeshes:
            mesh = bpy.data.meshes[name]
            for prim in gltf_importer.data.meshes[curMeshCount].primitives:
                if '_GARMENTSUPPORTWEIGHT' in prim.attributes:
                    indices = get_indices(gltf_importer, prim)
                    
                    add_vertex_color_attribute('_GARMENTSUPPORTWEIGHT', 'GarmentSupportWeight', gltf_importer, mesh, prim, indices)
                    
                    add_vertex_color_attribute('_GARMENTSUPPORTCAP', 'GarmentSupportCap', gltf_importer, mesh, prim, indices)
                    
                mesh.color_attributes.render_color_index = 0
                curMeshCount = curMeshCount + 1

def add_vertex_color_attribute(accessor_name, attribute_name, gltf_importer, mesh, prim, indices):
    if accessor_name in prim.attributes:
        cols = BinaryData.decode_accessor(gltf_importer, prim.attributes[accessor_name], cache=True)
        cols = cols[indices]
        if cols.shape[1] == 3:
            cols = colors_rgb_to_rgba(cols)
        layer = mesh.vertex_colors.new(name=attribute_name)

        if layer is None:
            print("WARNING: Vertex colors are ignored because the maximum number of vertex color layers has been "
                "reached.")
        else:
            mesh.color_attributes[layer.name].data.foreach_set('color', squish(cols))

def get_indices(gltf_importer, prim):
    if prim.indices is not None:
        indices = BinaryData.decode_accessor(gltf_importer, prim.indices)
        indices = indices.reshape(len(indices))
    else:
        num_verts = gltf_importer.data.accessors[prim.attributes['POSITION']].count
        indices = np.arange(0, num_verts, dtype=np.uint32)

    mode = 4 if prim.mode is None else prim.mode
    points, edges, tris = points_edges_tris(mode, indices)
    if points is not None:
        indices = points
    elif edges is not None:
        indices = edges
    else:
        indices = tris
    return indices