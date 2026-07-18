import time

import bpy
from mathutils import Matrix, Quaternion, Vector

from ..collisiontools.pxbridge.io_phys import import_collider_as_actor
from ..jsontool import JSONTool


def _cname_value(value, default=''):
    if isinstance(value, dict):
        return value.get('$value', default)
    return value if value is not None else default


def _collect_handle_data(value, lookup):
    if isinstance(value, dict):
        data = value.get('Data')
        handle_id = value.get('HandleId')
        if handle_id is not None and isinstance(data, dict):
            lookup.setdefault(str(handle_id), data)
        for child in value.values():
            _collect_handle_data(child, lookup)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _collect_handle_data(child, lookup)


def _resolve_handle_data(value, lookup):
    if not isinstance(value, dict):
        return None
    data = value.get('Data')
    if isinstance(data, dict):
        return data
    handle_ref = value.get('HandleRefId')
    if handle_ref is not None:
        return lookup.get(str(handle_ref))
    return value if '$type' in value else None


def _vector3(value, default=(0.0, 0.0, 0.0)):
    if not isinstance(value, dict):
        return Vector(default)
    return Vector(
            (
                float(value.get('X', value.get('x', default[0]))),
                float(value.get('Y', value.get('y', default[1]))),
                float(value.get('Z', value.get('z', default[2]))),
                )
            )


def _quaternion(value):
    if not isinstance(value, dict):
        return Quaternion((1.0, 0.0, 0.0, 0.0))
    rotation = Quaternion(
            (
                float(value.get('r', value.get('W', 1.0))),
                float(value.get('i', value.get('X', 0.0))),
                float(value.get('j', value.get('Y', 0.0))),
                float(value.get('k', value.get('Z', 0.0))),
                )
            )
    rotation.normalize()
    return rotation


def _transform_matrix(value):
    if not isinstance(value, dict):
        return Matrix.Identity(4)
    position = value.get('position') or value.get('Position') or value.get('Translation')
    orientation = value.get('orientation') or value.get('Orientation') or value.get('Rotation')
    return Matrix.LocRotScale(_vector3(position), _quaternion(orientation), Vector((1.0, 1.0, 1.0)))


def _actor_type(body, params):
    simulation_type = _cname_value(params.get('simulationType')) or _cname_value(body.get('simulationType'))
    actor_type = str(simulation_type).rsplit('::', 1)[-1].upper()
    return actor_type if actor_type in {'STATIC', 'DYNAMIC', 'KINEMATIC'} else 'STATIC'


def _positive_mass(body, params):
    for source in (params, body):
        for key in ('massOverride', 'mass'):
            try:
                value = float(source.get(key, 0.0))
            except (TypeError, ValueError):
                continue
            if value > 0.0:
                return value
    return 0.0


def _new_collection_object(collection, existing_objects, expected_name):
    for obj in collection.objects:
        if obj not in existing_objects:
            return obj
    return collection.objects.get(expected_name)


def _cp77_phys_import(filepath, rig=None, chassis_z=None, target_collection=None, actor_matrix=None, context=None):
    context = context or bpy.context
    start_time = time.time()
    target_collection = target_collection or context.collection or context.scene.collection
    data = JSONTool.jsonload(filepath)
    root = data.get('Data', {}).get('RootChunk', {}) if isinstance(data, dict) else {}
    bodies = root.get('bodies') if isinstance(root, dict) else None
    if not isinstance(bodies, list):
        print(f'No physics bodies found in {filepath}')
        return

    handle_lookup = {}
    _collect_handle_data(root, handle_lookup)
    base_matrix = actor_matrix.copy() if isinstance(actor_matrix, Matrix) else Matrix.Identity(4)
    actor_count = 0
    shape_count = 0

    for body_index, body_ref in enumerate(bodies):
        body = _resolve_handle_data(body_ref, handle_lookup)
        if not isinstance(body, dict):
            continue

        params = _resolve_handle_data(body.get('params'), handle_lookup)
        if not isinstance(params, dict):
            params = body.get('params') if isinstance(body.get('params'), dict) else {}
        collision_shapes = body.get('collisionShapes') or ()
        body_name = _cname_value(body.get('name'), f'PhysicsBody_{body_index}')
        body_matrix = base_matrix @ _transform_matrix(body.get('localToModel'))
        actor_type = _actor_type(body, params)
        mass = _positive_mass(body, params)
        inertia = params.get('inertia') or body.get('inertia')
        com_offset = params.get('comOffset') or body.get('comOffset')
        body_filter = body.get('filterData') or body.get('filter')
        actor_obj = None
        body_shape_count = 0

        for shape_index, shape_ref in enumerate(collision_shapes):
            collider_data = _resolve_handle_data(shape_ref, handle_lookup)
            if not isinstance(collider_data, dict):
                continue

            collider_type = collider_data.get('$type', 'physicsColliderBox')
            submesh_name = body_name if actor_obj is None else f'{body_name}_{shape_index}_{collider_type}'
            existing_objects = set(target_collection.objects) if actor_obj is None else None

            try:
                shape_item = import_collider_as_actor(
                        collider_data,
                        submesh_name,
                        target_collection,
                        actor_obj=actor_obj,
                        context=context,
                        actor_type=actor_type,
                        mass=mass,
                        inertia=inertia,
                        com_offset=com_offset,
                        filter_data=collider_data.get('filterData') or body_filter,
                        )
            except Exception as exc:
                print(f'Error importing {collider_type} for {body_name}: {exc}')
                continue

            if shape_item is None:
                continue

            if actor_obj is None:
                actor_obj = _new_collection_object(target_collection, existing_objects, body_name)
                if actor_obj is None:
                    print(f'PhysX actor registration did not create an actor object for {body_name}')
                    break
                actor_obj.matrix_world = body_matrix
                actor_obj['physicsBodyName'] = body_name
                actor_obj['actorType'] = actor_type
                if rig is not None and actor_matrix is None:
                    constraint = actor_obj.constraints.new('CHILD_OF')
                    constraint.target = rig
                    constraint.subtarget = 'Base'
                    if chassis_z is not None:
                        actor_obj.delta_location[2] = chassis_z

            shape_item.name = f'{body_name}_{shape_index}_{shape_item.name}'[:63]
            body_shape_count += 1

        if actor_obj is not None and body_shape_count:
            actor_count += 1
            shape_count += body_shape_count

    scene_physx = getattr(context.scene, 'physx', None)
    if scene_physx is not None and actor_count:
        if hasattr(scene_physx, 'scene_built'):
            scene_physx.scene_built = False
        if hasattr(scene_physx, 'active_actor_count'):
            scene_physx.active_actor_count = len(scene_physx.actors)

    preferences = context.preferences.addons.get('i_scene_cp77_gltf')
    non_verbose = bool(preferences and preferences.preferences.non_verbose)
    if not non_verbose:
        elapsed = time.time() - start_time
        print(f'Registered {actor_count} physics body actors with {shape_count} shapes in {elapsed} seconds')


def cp77_phys_import(filepath, rig=None, chassis_z=None):
    return _cp77_phys_import(filepath, rig=rig, chassis_z=chassis_z)


def cp77_phys_import_into_collection(filepath, target_collection, actor_matrix=None, context=None, rig=None):
    return _cp77_phys_import(
            filepath,
            rig=rig,
            target_collection=target_collection,
            actor_matrix=actor_matrix,
            context=context,
            )
