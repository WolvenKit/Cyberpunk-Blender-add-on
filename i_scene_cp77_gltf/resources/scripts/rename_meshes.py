import bpy


def get_coll():
    # Get the active collection in the outliner
    return bpy.context.collection


def format_i(index):
    # Format the index as "00, 01, 02"
    return f"{index:02d}"


def rename_meshes(collection):
    if collection:
        # get the meshes
        mesh = [obj for obj in collection.objects if obj.type == "MESH"]
        # Iterate through each mesh and rename
        for index, mesh in enumerate(mesh):
            formatted_index = format_i(index)
            new_name = f"submesh_{formatted_index}_LOD_1"
            mesh.name = new_name
            print(f"Renamed {mesh.name}")


# Get the currently selected collection
coll = get_coll()

# Rename meshes in the selected collection
rename_meshes(coll)
