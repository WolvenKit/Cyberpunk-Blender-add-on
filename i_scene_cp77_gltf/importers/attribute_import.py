import bpy

from io_scene_gltf2.io.imp.gltf2_io_binary import BinaryData
from io_scene_gltf2.blender.imp.gltf2_blender_mesh import points_edges_tris
from io_scene_gltf2.blender.imp.gltf2_blender_mesh import squish

def rename_color_attribute(mesh, name_before, name_after):
    if mesh.color_attributes is None:
        return
    col_layer = mesh.color_attributes.get(name_before)
    if col_layer is not None:
        col_layer.name = name_after

def manage_garment_support(existingMeshes, gltf_importer_data):
    gltf_importer = gltf_importer_data
    curMeshCount = 0
    for name in bpy.data.meshes.keys():
        if name in existingMeshes or "Icosphere" in name:
            continue
        mesh = bpy.data.meshes[name]

        # fix attributes. also fix exceptions.
        for prim in gltf_importer.data.meshes[curMeshCount].primitives:
            if not ('_GARMENTSUPPORTWEIGHT' in prim.attributes or '_GARMENTSUPPORTCAP' in prim.attributes):
                continue
            indices = get_indices(gltf_importer, prim)
            if '_GARMENTSUPPORTWEIGHT' in prim.attributes:
                mesh.color_attributes.remove(mesh.color_attributes['_GARMENTSUPPORTWEIGHT'])
                add_vertex_color_attribute('_GARMENTSUPPORTWEIGHT', '_GARMENTSUPPORTWEIGHT', gltf_importer, mesh, prim, indices)
            if '_GARMENTSUPPORTCAP' in prim.attributes:
                mesh.color_attributes.remove(mesh.color_attributes['_GARMENTSUPPORTCAP'])
                add_vertex_color_attribute('_GARMENTSUPPORTCAP', '_GARMENTSUPPORTCAP', gltf_importer, mesh, prim, indices)
            mesh.color_attributes.render_color_index = 0

        # rename attributes
        # TODO (manavortex): Presto said that they needed an underscore to be exported. However, I used them without underscore,
        # and they worked fine - I could see GarmentSupportCap becoming active in-game
        rename_color_attribute(mesh, "_GARMENTSUPPORTCAP", "GarmentSupportCap")
        rename_color_attribute(mesh, "_GARMENTSUPPORTWEIGHT", "GarmentSupportWeight")

        curMeshCount = curMeshCount + 1


def add_vertex_color_attribute(accessor_name, attribute_name, gltf_importer_data, mesh, prim, indices):
    gltf_importer = gltf_importer_data
    if not accessor_name in prim.attributes:
        return
    cols = BinaryData.decode_accessor(gltf_importer, prim.attributes[accessor_name], cache=True)
    cols = cols[indices]
    if cols.shape[1] == 3:
        cols = colors_rgb_to_rgba(cols)
    layer = mesh.vertex_colors.new(name=attribute_name)

    if layer is None:
        print("WARNING: Vertex colors are ignored (maximum number of vertex color layers has been reached)")
    else:
        mesh.color_attributes[layer.name].data.foreach_set('color', squish(cols))

def get_indices(gltf_importer_data, prim):
    gltf_importer = gltf_importer_data
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
