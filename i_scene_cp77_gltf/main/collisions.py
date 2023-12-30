import bpy
import bmesh
from mathutils import Vector, Euler, Quaternion

def create_new_object(name, transform, collision_collection):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    collision_collection.objects.link(obj)  
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    # create dicts for position/orientation
    position = (transform['position']['X'], transform['position']['Y'], transform['position']['Z'])
    #orientation = (transform['orientation']['r'], transform['orientation']['j'], transform['orientation']['k'], transform['orientation']['i'])
    obj.location = position
    return obj

def set_collider_props(obj, collision_shape, physmat, collision_type):
    obj['collisionType'] = collision_type
    obj['collisionShape'] = collision_shape
    obj['physics_material'] = physmat
    obj.display_type = 'WIRE'
    obj.color = (0.005, 0.79105, 1, 1)
    obj.show_wire = True
    obj.show_in_front = True
    obj.display.show_shadows = False
    obj.rotation_mode = 'QUATERNION'

                
def draw_convex_collider(name, collision_collection, vertices, physmat, transform, collision_type):
    collision_shape = "physicsColliderConvex"
    obj = create_new_object(name, transform, collision_collection)
    set_collider_props(obj, collision_shape, physmat, collision_type)
    if vertices:
        verts = [(j['X'], j['Y'], j['Z']) for j in vertices]
        bm = bmesh.new()
        for v in verts:
            bm.verts.new(v)
        bm.to_mesh(obj.data)
        bm.free()


def draw_sphere_collider(name, collision_collection, radius, position, physmat, collision_type):
    collision_shape = 'physicsColliderSphere'
    r = float(radius)
    bm = bmesh.new()
   # position = (transform['position']['X'], transform['position']['Y'], transform['position']['Z'])
    bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=9, radius=r)
    name = collision_shape
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    mesh.update()
    bm.free()
    sphere = bpy.data.objects.new(name, mesh)
    sphere.location = position
    set_collider_props(sphere, collision_shape, physmat, collision_type)
    collision_collection.objects.link(sphere)

def draw_capsule_collider(name, collision_collection, radius, height, position, rotation, physmat, collision_type):
    collision_shape = 'physicsColliderCapsule'
    is_edit_mode = bpy.context.object.mode == 'EDIT'
    r = float(radius)
    h = float(height)   
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=9, radius=r)
    delta_Z = float(h)
    bm.verts.ensure_lookup_table()
    for vert in bm.verts:
        if vert.co[2] < 0:
            vert.co[2] -= delta_Z
        elif vert.co[2] > 0:
            vert.co[2] += delta_Z
    name = collision_shape
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    mesh.update()
    bm.free()
    capsule = bpy.data.objects.new(name, mesh)
    set_collider_props(capsule, collision_shape, physmat, collision_type)
    capsule.location = position
    capsule.rotation_quaternion[1] = 1
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    if is_edit_mode:
        bpy.ops.object.mode_set(mode='OBJECT')
    capsule.dimensions.z = h
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    capsule.rotation_quaternion = rotation
    collision_collection.objects.link(capsule)
    # Re-enter Edit mode
    if is_edit_mode:
        bpy.ops.object.mode_set(mode='EDIT')



def draw_box_collider(name, collision_collection, half_extents, transform, physmat, collision_type):
    collision_shape = "physicsColliderBox"
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    box = bpy.context.object
    set_collider_props(box, collision_shape, physmat, collision_type)
    dimensions = (2 * half_extents['X'], 2 * half_extents['Y'], 2 * half_extents['Z'])          
    box.scale = dimensions
    box.name = name
    set_collider_props(box, collision_shape, physmat, collision_type)
    box.location = transform['position']['X'], transform['position']['Y'], transform['position']['Z']
    box.rotation_quaternion = transform['orientation']['r'], transform['orientation']['j'], transform['orientation']['k'], transform['orientation']['i']
    collision_collection.objects.link(box)
    bpy.context.collection.objects.unlink(box) # Unlink from the current collection
    

def CP77CollisionGen(self, context, matchSize, collider_type, collision_shape, sampleverts, radius, height, physics_material):
    is_edit_mode = bpy.context.object.mode == 'EDIT'
    selected_objects = context.selected_objects
    bpy.context.space_data.shading.wireframe_color_type = 'OBJECT'
    colliderCollection = None

    # Check for a collection ending with ".phys"
    for collection in bpy.data.collections:
        if collider_type == "VEHICLE":
            if collection.name.endswith(".phys"):
                colliderCollection = collection

    # If colliderCollection is still None, create a new collection
    if colliderCollection is None:
        if collider_type == 'VEHICLE':
            colliderCollection = bpy.data.collections.new("collisions.phys")
            bpy.context.scene.collection.children.link(colliderCollection)
        elif collider_type == 'ENTITY':
            colliderCollection = bpy.data.collections.new("entColliderComponent")
            bpy.context.scene.collection.children.link(colliderCollection)
        elif collider_type == 'WORLD':
            colliderCollection = bpy.data.collections.new("worldCollisionNode")
            bpy.context.scene.collection.children.link(colliderCollection)
    

    min_vertex = Vector((float('inf'), float('inf'), float('inf')))
    max_vertex = Vector((float('-inf'), float('-inf'), float('-inf')))

    # Calculate the bounding box of the selected objects
    for obj in selected_objects:
        if obj.type == 'MESH':
            matrix = obj.matrix_world
            mesh = obj.data
            for vertex in mesh.vertices:
                vertex_world = matrix @ vertex.co
                min_vertex = Vector(min(min_vertex[i], vertex_world[i]) for i in range(3))
                max_vertex = Vector(max(max_vertex[i], vertex_world[i]) for i in range(3))

        # Calculate the center of the bounding box
        center = (min_vertex + max_vertex) / 2

        if collision_shape == 'CONVEX':
            if not is_edit_mode:
                bpy.ops.object.mode_set(mode='EDIT') 
            # Get the bmesh linked to the active object
            obj = bpy.context.edit_object
            bm = bmesh.from_edit_mesh(obj.data)

            # Get all selected vertices
            selected_verts = [v for v in bm.verts if v.select]

            verts_to_sample = int(sampleverts)

            # Check if we have enough vertices
            if len(selected_verts) < verts_to_sample:
                print("Sample number is higher than selected vertices count!")
                bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Sample number is higher than selected vertices count!")
                return {'CANCELLED'}
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
                convcol = bpy.data.objects.new("physicsColliderConvex", mesh)
                convcol.matrix_world = matrix
                shape = "physicsColliderConvex"
                set_collider_props(convcol, shape, physics_material, collider_type)
                colliderCollection.objects.link(convcol)
                context.view_layer.objects.active = convcol
                convcol.select_set(True)

                if not is_edit_mode:
                    bpy.ops.object.mode_set(mode='OBJECT')
                      
      
        if collision_shape == "BOX":
            #switch to object mode
            if is_edit_mode:
                bpy.ops.object.mode_set(mode='OBJECT')

            # Create a new mesh object
            bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD', location=(0, 0, 0))
            box = context.object
            shape = "physicsColliderBox"
            box.name = shape
            set_collider_props(box, shape, physics_material, collider_type)
            context.collection.objects.unlink(box)
            size = max_vertex - min_vertex
            # Set the position and scale of the bounding box
            box.location = center
            box.scale = size 
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            colliderCollection.objects.link(box)
            context.view_layer.objects.active = box
            box.select_set(True)

            # Re-enter Edit mode
            if is_edit_mode:
                bpy.ops.object.mode_set(mode='EDIT')

        if collision_shape == 'CAPSULE':
            if matchSize:
                # Calculate the size of the capsule based on the bounding box
                r = (max_vertex - min_vertex).x / 2
                h = (max_vertex - min_vertex).z 
            else: 
                r = float(radius) 
                h = height   

                # create the capsule
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=9, radius=r)
            delta_Z = float(h)
            bm.verts.ensure_lookup_table()
            for vert in bm.verts:
                if vert.co[2] < 0:
                    vert.co[2] -= delta_Z
                elif vert.co[2] > 0:
                    vert.co[2] += delta_Z

            shape = 'physicsColliderCapsule'
            name = shape
            mesh = bpy.data.meshes.new(name)
            bm.to_mesh(mesh)
            mesh.update()
            bm.free()
            capsule = bpy.data.objects.new(name, mesh)
            set_collider_props(capsule, collision_shape, physics_material, collider_type)
            capsule.location = center
            capsule.rotation_quaternion[1] = 1
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
            if is_edit_mode:
                bpy.ops.object.mode_set(mode='OBJECT')
            capsule.dimensions.z = float(h)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            colliderCollection.objects.link(capsule)
            # Re-enter Edit mode
            if is_edit_mode:
                bpy.ops.object.mode_set(mode='EDIT')

        if collision_shape == 'SPHERE':
            if matchSize:
                # Calculate the size of the capsule based on the bounding box
                r = (max_vertex - min_vertex).x / 2
            else: 
                r = float(radius)
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=9, radius=r)
            shape = 'physicsColliderSphere'
            name = shape
            mesh = bpy.data.meshes.new(name)
            bm.to_mesh(mesh)
            mesh.update()
            bm.free()
            sphere = bpy.data.objects.new(name, mesh)
            set_collider_props(sphere, collision_shape, physics_material, collider_type)
            colliderCollection.objects.link(sphere)

