import bpy
import struct
import os
import bmesh
import json
import base64

from i_scene_cp77_gltf import create_new_object, draw_box_collider, draw_capsule_collider, draw_sphere_collider, set_collider_props
from i_scene_cp77_gltf.main.common import show_message

def draw_mesh_collider(name, collision_collection, vertices, faces, transform, physmat, collision_type):
    collision_shape = "physicsColliderMesh"
    obj = create_new_object(name, transform, collision_collection)
    set_collider_props(obj, collision_shape, physmat, collision_type)

    bm_verts = []
    if vertices:
        verts = [(j['X'], j['Y'], j['Z']) for j in vertices]
        bm = bmesh.new()
        for v in verts:
            bm_verts.append(bm.verts.new(v))
        if faces:
            for face_indices in faces:
                face_verts = [bm_verts[i] for i in face_indices]
                bm.faces.new(face_verts)
        bm.to_mesh(obj.data)
        bm.free()
    return obj

def parse_nxs(buffer):

    #Parsing PhysX NXS collider mesh format from buffer
#     Header:
#         0x00: "NXS\x01"
#         0x04: "MESH"
#         0x08: version(15)
#         0x0C: body count(1)
#         0x10: index flag(4 = uint8, 9 = uint16) (not sure, but these values work)
#         0x14: vertex count
#         0x18: triangle count
#     Data:
#         0x1C: vertices(count * 12 bytes, float32 x 3)
#         after vertices: indices(triangles * 3 * index_size)
#         after indices: "BV4 " marker → BVH(ignoring while import)

    buffer = base64.b64decode(buffer)
    magic = buffer[0:4]
    if magic != b'NXS\x01':
        raise ValueError(f"Invalid magic: {magic}")
    mesh_type = buffer[4:8]
    if mesh_type != b'MESH':
        raise ValueError(f"Invalid magic: {mesh_type}")

    version = struct.unpack_from('<I', buffer, 0x08)[0]
    body_count = struct.unpack_from('<I', buffer, 0x0C)[0]
    index_flag = struct.unpack_from('<I', buffer, 0x10)[0]
    vertex_count = struct.unpack_from('<I', buffer, 0x14)[0]
    triangle_count = struct.unpack_from('<I', buffer, 0x18)[0]
    verticles = []
    offset = 0x1C

    for i in range(vertex_count):
        x,y,z = struct.unpack_from('<fff', buffer, offset)
        verticles.append({'X': x, 'Y': y, 'Z': z})
        offset += 12

    faces = []
    if index_flag == 4:
        index_size = 1
    elif index_flag == 9:
        index_size = 2
    else:
        raise ValueError('Errors during import:\n\t' + '\n\t'.join("Unknown index flag in NXS buffer: {index_flag}"))

    for i in range(triangle_count):
        if index_size == 1:
            i0 = buffer[offset]
            i1 = buffer[offset+1]
            i2 = buffer[offset+2]
        else:
            i0 = struct.unpack_from('<H', buffer, offset)[0]
            i1 = struct.unpack_from('<H', buffer, offset+2)[0]
            i2 = struct.unpack_from('<H', buffer, offset+4)[0]
        faces.append((i0, i1, i2))
        offset += index_size * 3

    return verticles, faces

def cp77_collision_mesh_json_import(filepath: str):
    #Import embedded colliders from .mesh.json

    with open(filepath, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    data = raw_data["Data"]["RootChunk"]["parameters"][0]["Data"]["physicsData"]["Data"]["bodies"][0]["Data"]["collisionShapes"]

    mesh_name = os.path.basename(filepath).split(".")[0]+'.mesh'
    collection = bpy.data.collections.new(mesh_name)
    bpy.context.scene.collection.children.link(collection)

    for index in range(len(data) - 1, -1, -1):
        collision_shape = data[index]
        shape = collision_shape["Data"]["$type"]
        transform = collision_shape["Data"]["localToBody"]

        name =  f"{index}_{shape}"
        physmat = collision_shape["Data"]["material"]["$value"]
        collision_type = 'EMBEDDED'

        match shape:
            case "physicsColliderMesh":
                buffer = collision_shape["Data"]["compiledGeometryBuffer"]["Bytes"]
                verts, faces = parse_nxs(buffer)
                bpy_obj = draw_mesh_collider(name, collection, verts, faces, transform, physmat, collision_type)
            case "physicsColliderCapsule":
                height = collision_shape["Data"]["height"]
                radius = collision_shape["Data"]["radius"]
                position = (transform['position']['X'], transform['position']['Y'], transform['position']['Z'])
                orientation = (transform['orientation']['r'], transform['orientation']['j'],
                               transform['orientation']['k'], transform['orientation']['i'])
                bpy_obj = draw_capsule_collider(name, collection, radius, height, position, orientation, physmat, collision_type)
            case "physicsColliderSphere":
                radius = collision_shape["Data"]["radius"]
                position = (transform['position']['X'], transform['position']['Y'], transform['position']['Z'])
                bpy_obj = draw_sphere_collider(name, collection, radius, position, physmat, collision_type)
            case "physicsColliderBox":
                half_extents = collision_shape["Data"]["halfExtents"]
                bpy_obj = draw_box_collider(name, collection, half_extents, transform, physmat, collision_type)
            case _:
                show_message(f'{name} collision shape {index} has unknown shape')
                continue

        bpy_obj["_collider_raw_data"] = json.dumps(collision_shape)
        data.pop(index)

    collection["_mesh_json_data"] = json.dumps(raw_data)













