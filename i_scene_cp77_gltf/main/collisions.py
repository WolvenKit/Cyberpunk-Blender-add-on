import bpy
import bmesh
from mathutils import Vector, Euler, Quaternion

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
                convcol.rotation_mode = 'QUATERNION'
                convcol.matrix_world = matrix
                convcol['collisionType'] = collider_type
                convcol['collisionShape'] = 'physicsColliderConvex'
                convcol['physics_material'] = physics_material
                colliderCollection.objects.link(convcol)
                convcol.display_type = 'WIRE'
                convcol.color = (0.005, 0.79105, 1, 1)
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
            box.name = "physicsColliderBox"
            box['collisionType'] = collider_type
            box['collisionShape'] = 'physicsColliderBox'
            box['physics_material'] = physics_material
            context.collection.objects.unlink(box)
            box.display_type = 'WIRE'
            box.color = (0.005, 0.79105, 1, 1)

            size = max_vertex - min_vertex

            # Set the position and scale of the bounding box
            box.location = center
            box.scale = size 
            box.rotation_mode = 'QUATERNION'
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

            name = 'physicsColliderCapsule'
            mesh = bpy.data.meshes.new(name)
            bm.to_mesh(mesh)
            mesh.update()
            bm.free()

            capsule = bpy.data.objects.new(name, mesh)
            capsule.display_type = 'WIRE'
            capsule.color = (0.005, 0.79105, 1, 1)

            capsule.show_wire = True
            capsule.show_in_front = True
            capsule.display.show_shadows = False
            capsule.location = center
            capsule.rotation_mode = 'QUATERNION'
            capsule['collisionType'] = collider_type
            capsule['collisionShape'] = 'physicsColliderCapsule'
            capsule['physics_material'] = physics_material
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
            name = 'physicsColliderSphere'
            mesh = bpy.data.meshes.new(name)
            bm.to_mesh(mesh)
            mesh.update()
            bm.free()

            sphere = bpy.data.objects.new(name, mesh)
            sphere.display_type = 'WIRE'
            sphere.color = (0.005, 0.79105, 1, 1)
            sphere.show_wire = True
            sphere.show_in_front = True
            sphere.display.show_shadows = False
            sphere.location = center
            sphere.rotation_mode = 'QUATERNION'
            sphere['collisionType'] = collider_type
            sphere['collisionShape'] = 'physicsColliderSphere'
            sphere['physics_material'] = physics_material
            colliderCollection.objects.link(sphere)

