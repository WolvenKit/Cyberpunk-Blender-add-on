import bpy
import os
from math import ceil, sqrt

# Directory path containing the .png files
directory_path = "M:\\blue"

# Function to import PNG images from the directory
def import_png_images():
    # Get a list of all .png files in the directory
    png_files = [f for f in os.listdir(directory_path) if f.endswith(".png")]
    
    # Calculate the grid size based on the number of images
    num_images = len(png_files)
    grid_size = ceil(sqrt(num_images))
    
    # Calculate the size of each grid cell
    cell_size = 1.0 / grid_size
    
    # Create an empty collection to group the imported planes
    collection = bpy.data.collections.new(name="ImagePlanes")
    bpy.context.scene.collection.children.link(collection)
    
    # Loop through the .png files and import them
    for i, png_file in enumerate(png_files):
        row = i // grid_size
        col = i % grid_size
        
        x_pos = col * cell_size + cell_size / 2
        y_pos = row * cell_size + cell_size / 2
        
        # Create an image plane and assign the PNG texture
        bpy.ops.mesh.primitive_plane_add(size=cell_size, enter_editmode=False, align='WORLD', location=(x_pos, y_pos, 0))
        plane = bpy.context.object
        plane.name = f"ImagePlane_{i}"
        
        # Add the plane to the collection
        collection.objects.link(plane)
        
        bpy.ops.object.material_slot_add()
        material = bpy.data.materials.new(name=f"Material_{i}")
        material.use_nodes = True
        bsdf = material.node_tree.nodes[loc("Principled BSDF")]
        texture = material.node_tree.nodes.new("ShaderNodeTexImage")
        texture.image = bpy.data.images.load(os.path.join(directory_path, png_file))
        material.node_tree.links.new(bsdf.inputs["Base Color"], texture.outputs["Color"])
        plane.data.materials[0] = material

# Clear existing objects in the scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Import the PNG images and calculate the grid size automatically
import_png_images()
