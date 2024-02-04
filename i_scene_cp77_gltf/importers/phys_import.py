import json
import bpy
import bmesh
from ..main.collisions import draw_box_collider, draw_convex_collider, set_collider_props


def cp77_phys_import(filepath, rig=None, chassis_z=None):
    physJsonPath = filepath
    collision_type = "VEHICLE"
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            space = area.spaces.active
            if space.type == "VIEW_3D":
                space.shading.wireframe_color_type = "OBJECT"

    with open(physJsonPath, "r") as phys:
        data = json.load(phys)

    for index, i in enumerate(data["Data"]["RootChunk"]["bodies"]):
        bname = i["Data"]["name"]["$value"]
        collection_name = bname
        new_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(new_collection)

        for index, i in enumerate(data["Data"]["RootChunk"]["bodies"][0]["Data"]["collisionShapes"]):
            collision_shape = i["Data"]["$type"]
            physmat = i["Data"]["material"]["$value"]
            submeshName = str(index) + "_" + collision_shape
            transform = i["Data"]["localToBody"]
            print(bname, collision_shape, physmat, submeshName, transform)

            if collision_shape == "physicsColliderConvex":
                vertices = i["Data"]["vertices"]
                obj = draw_convex_collider(submeshName, new_collection, vertices, physmat, transform, collision_type)
                if rig is not None:
                    constraint = obj.constraints.new("CHILD_OF")
                    constraint.target = rig
                    constraint.subtarget = "Base"
                    bpy.ops.constraint.childof_set_inverse(constraint="Child Of", owner="OBJECT")
                    if chassis_z is not None:
                        obj.delta_location[2] = chassis_z

            # If the type is "physicsColliderBox", create a box centered at the object's location
            elif collision_shape == "physicsColliderBox":
                half_extents = i["Data"]["halfExtents"]
                center = transform["position"]["X"], transform["position"]["Y"], transform["position"]["Z"]
                box = draw_box_collider(submeshName, new_collection, half_extents, center, physmat, collision_type)
                if rig is not None:
                    constraint = box.constraints.new("CHILD_OF")
                    constraint.target = rig
                    constraint.subtarget = "Base"
                    bpy.ops.constraint.childof_set_inverse(constraint="Child Of", owner="OBJECT")
                    if chassis_z is not None:
                        box.delta_location[2] = chassis_z

            # handle physicsColliderCapsule
            elif collision_shape == "physicsColliderCapsule":
                r = i["Data"]["radius"]
                h = i["Data"]["height"]

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

                name = "physicsColliderCapsule"
                mesh = bpy.data.meshes.new(name)
                bm.to_mesh(mesh)
                mesh.update()
                bm.free()
                capsule = bpy.data.objects.new(name, mesh)
                set_collider_props(capsule, collision_shape, physmat, collision_type)
                capsule.rotation_quaternion[1] = 1
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
                capsule.dimensions.z = float(h)
                capsule.location = transform["position"]["X"], transform["position"]["Y"], transform["position"]["Z"]
                capsule.rotation_quaternion = (
                    transform["orientation"]["r"],
                    transform["orientation"]["j"],
                    transform["orientation"]["k"],
                    transform["orientation"]["i"],
                )
                if rig is not None:
                    constraint = capsule.constraints.new("CHILD_OF")
                    constraint.target = rig
                    constraint.subtarget = "Base"
                    bpy.ops.constraint.childof_set_inverse(constraint="Child Of", owner="OBJECT")
                    if chassis_z is not None:
                        capsule.delta_location[2] = chassis_z
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                new_collection.objects.link(capsule)
