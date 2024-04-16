import json
import os 
import bpy
from mathutils import Vector, Euler, Quaternion
from ..main.common import show_message
from .phys_export import export_colliders_to_phys

def get_collider_collections(context, collider_type):
    collider_collections = []
    
    for collection in context.scene.collection.children:
        type = bpy.data.collections[collection.name]["collider_type"]
        if type == collider_type:
            collider_collections.append(collection)
    
    if not collider_collections:
        print(f"Error: Collider collection not found.")
        return None
    else: 
        return collider_collections

def cp77_collision_export(filepath, collision_type):
    context = bpy.context
    if collision_type == 'VEHICLE':
        collections = get_collider_collections(context, 'VEHICLE')
        export_colliders_to_phys(collections, filepath)
    if collision_type == 'ENTITY':
        show_message('Exporting of Entity Colliders is not yet supported')
    if collision_type == 'WORLD':
        show_message('Exporting of collision nodes is not yet supported')
