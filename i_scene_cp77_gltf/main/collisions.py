import bpy
import bmesh


def CP77CollisionGen(context, sampleverts):
    # Ensure you are in 'EDIT' mode and some vertices of a mesh are selected
    if bpy.context.mode == "EDIT_MESH" and bpy.context.object.type == "MESH":
        # Get the bmesh linked to the active object
        obj = bpy.context.edit_object
        bm = bmesh.from_edit_mesh(obj.data)

        # Get all selected vertices
        selected_verts = [v for v in bm.verts if v.select]

        verts_to_sample = int(sampleverts)

        # Check if we have enough vertices
        if len(selected_verts) < verts_to_sample:
            print("Sample number is higher than selected vertices count !")
        else:
            # sample the vertices
            step_size = len(selected_verts) // verts_to_sample
            sampled_verts = [
                selected_verts[i] for i in range(0, len(selected_verts), step_size)
            ][:verts_to_sample]
            coords = [v.co.copy() for v in sampled_verts]

            # Create a new mesh with these vertices
            mesh = bpy.data.meshes.new(name="physicsColliderConvex")
            mesh.from_pydata(coords, [], [])

            # Link it to scene
            obj = bpy.data.objects.new("physicsColliderConvex", mesh)
            bpy.context.collection.objects.link(obj)
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
    else:
        print("Please select some vertices of a mesh in edit mode!")
