from __future__ import annotations
from ....blender.transactions import track_created_datablock

import math

import bpy
from mathutils import Matrix

from ...common.entity_data import component_name
from ...common.paths import depot_path_value
from ..policy import LIGHT_COMPONENT_TYPES
from ..registry import EntityComponentHandlerRegistry
from ..transforms import resolve_handle_data, visual_scale_matrix

_UNSET = object()
_LIGHT_DIRECTION_CORRECTION = Matrix.Rotation(math.radians(90.0), 4, "X")


def light_channel_geometry(component, shape_lookup=None):
    shape = resolve_handle_data(component, shape_lookup, 'shape') if shape_lookup is not None else None
    if not isinstance(shape, dict):
        shape = component.get('shape') if type(component) is dict else None
        if isinstance(shape, dict) and isinstance(shape.get('Data'), dict):
            shape = shape.get('Data')
    if not isinstance(shape, dict):
        return None, None
    vertices = shape.get('vertices')
    indices = shape.get('indices') or shape.get('faces')
    if not vertices or not indices:
        return None, None
    return vertices, indices


def collect_light_channel_components(*component_groups):
    collected = {}
    has_geometry = {}
    order = []
    for components in component_groups:
        for source in components or ():
            if not isinstance(source, dict) or source.get('$type') != 'entLightChannelComponent':
                continue
            key = component_name(source) or str(id(source))
            if key not in collected:
                collected[key] = source
                has_geometry[key] = _UNSET
                order.append(key)
                continue
            current_has_geometry = has_geometry[key]
            if current_has_geometry is _UNSET:
                current_has_geometry = light_channel_geometry(collected[key])[0] is not None
                has_geometry[key] = current_has_geometry
            if not current_has_geometry and light_channel_geometry(source)[0] is not None:
                collected[key] = source
                has_geometry[key] = True
    return [collected[key] for key in order]


def collect_light_components(*component_groups):
    collected = {}
    order = []
    for components in component_groups:
        for component in components or ():
            if not isinstance(component, dict) or component.get('$type') not in LIGHT_COMPONENT_TYPES:
                continue
            name = component_name(component)
            key = name or str(component.get('id') or id(component))
            if key not in collected:
                collected[key] = component
                order.append(key)
    return [collected[key] for key in order]


def _light_float(component, key, default=0.0):
    value = component.get(key, default) if isinstance(component, dict) else default
    if isinstance(value, dict):
        value = value.get('$value', default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _light_color(component):
    color = component.get('color') if isinstance(component, dict) else None
    if not isinstance(color, dict):
        return 1.0, 1.0, 1.0
    return tuple(
            max(0.0, min(1.0, _light_float(color, channel, 255.0) / 255.0)) for channel in ('Red', 'Green', 'Blue')
            )


def _blender_light_type(component):
    light_type = component.get('type') if isinstance(component, dict) else None
    if light_type == 'LT_Spot':
        return 'SPOT'
    if light_type == 'LT_Area':
        return 'AREA'
    if light_type in {'LT_Directional', 'LT_Sun'} or (isinstance(component, dict) and component.get('directional', 0)):
        return 'SUN'
    return 'POINT'


def _set_light_distance(light_data, radius):
    if radius <= 0.0:
        return
    if hasattr(light_data, 'use_custom_distance'):
        light_data.use_custom_distance = True
    if hasattr(light_data, 'cutoff_distance'):
        light_data.cutoff_distance = radius


def _set_light_softness(light_data, component):
    source_radius = _light_float(component, 'sourceRadius', -1.0)
    if source_radius < 0.0:
        source_radius = _light_float(component, 'shadowRadius', -1.0)
    if source_radius >= 0.0 and hasattr(light_data, 'shadow_soft_size'):
        light_data.shadow_soft_size = source_radius


def _configure_area_light(light_data, component):
    shape = component.get('areaShape', 'ALS_Rectangle')
    radius = max(_light_float(component, 'radius', 0.0), 0.0)
    side_a = max(_light_float(component, 'areaRectSideA', 1.0), 0.001)
    side_b = max(_light_float(component, 'areaRectSideB', 1.0), 0.001)
    capsule_length = max(_light_float(component, 'capsuleLength', 0.0), 0.0)

    if shape == 'ALS_Capsule':
        light_data.shape = 'RECTANGLE'
        light_data.size = max(capsule_length + radius * 2.0, 0.001)
        light_data.size_y = max(radius * 2.0, 0.001)
    elif shape in {'ALS_Sphere', 'ALS_Circle', 'ALS_Disc'}:
        light_data.shape = 'DISK'
        light_data.size = max(radius * 2.0, side_a, 0.001)
    elif shape in {'ALS_Ellipse', 'ALS_Oval'}:
        light_data.shape = 'ELLIPSE'
        light_data.size = side_a
        light_data.size_y = side_b
    elif shape in {'ALS_Rectangle', 'ALS_Rect'}:
        light_data.shape = 'RECTANGLE'
        light_data.size = side_a
        light_data.size_y = side_b
    else:
        light_data.shape = 'SQUARE'
        light_data.size = side_a


def _configure_light_data(light_data, component):
    intensity = max(_light_float(component, 'intensity', 0.0), 0.0)
    on_strength = max(_light_float(component, 'onStrength', 1.0), 0.0)
    light_data.energy = intensity * on_strength / 10.0
    light_data.color = _light_color(component)

    radius = max(_light_float(component, 'radius', 0.0), 0.0)
    _set_light_distance(light_data, radius)
    if hasattr(light_data, 'use_shadow'):
        light_data.use_shadow = bool(component.get('enableLocalShadows', 1))
    if hasattr(light_data, 'diffuse_factor'):
        light_data.diffuse_factor = max(_light_float(component, 'sceneDiffuse', 1.0), 0.0)
    if hasattr(light_data, 'specular_factor'):
        specular = 0.0 if component.get('noSpecular', 0) else max(_light_float(component, 'sceneSpecular', 1.0), 0.0)
        light_data.specular_factor = specular * max(_light_float(component, 'sceneSpecularScale', 100.0), 0.0) / 100.0
    if hasattr(light_data, 'volume_factor'):
        light_data.volume_factor = max(_light_float(component, 'scaleVolFog', 0.0), 0.0) / 100.0 if component.get(
            'useInFog', 0
            ) else 0.0
    if hasattr(light_data, 'transmission_factor'):
        light_data.transmission_factor = 1.0 if component.get('useInTransparents', 1) else 0.0

    temperature = _light_float(component, 'temperature', -1.0)
    if temperature > 0.0 and hasattr(light_data, 'temperature'):
        if hasattr(light_data, 'use_temperature'):
            light_data.use_temperature = True
        light_data.temperature = temperature

    if light_data.type == 'SPOT':
        outer_angle = max(_light_float(component, 'outerAngle', 45.0), 0.001)
        inner_angle = max(0.0, min(_light_float(component, 'innerAngle', outer_angle), outer_angle))
        light_data.spot_size = math.radians(min(outer_angle, 179.0))
        light_data.spot_blend = max(0.0, min(1.0, 1.0 - inner_angle / outer_angle))
        _set_light_softness(light_data, component)
    elif light_data.type == 'AREA':
        _configure_area_light(light_data, component)
    elif light_data.type == 'SUN':
        shadow_angle = _light_float(component, 'shadowAngle', -1.0)
        if shadow_angle >= 0.0 and hasattr(light_data, 'angle'):
            light_data.angle = math.radians(shadow_angle)
    else:
        _set_light_softness(light_data, component)


def _store_light_metadata(light_obj, component, filepath):
    component_type = component.get('$type', 'entLightComponent')
    light_obj['ntype'] = component_type
    light_obj['componentName'] = component_name(component)
    light_obj['entJSON'] = filepath

    for key in (
            'type', 'unit', 'intensity', 'EV', 'radius', 'innerAngle', 'outerAngle',
            'sourceRadius', 'shadowRadius', 'softness', 'areaShape', 'areaRectSideA',
            'areaRectSideB', 'capsuleLength', 'areaTwoSided', 'attenuation',
            'lightChannel', 'group', 'turnOnByDefault', 'onStrength', 'materialZone',
            'enableLocalShadows', 'enableContactShadows', 'contactShadows',
            'sceneDiffuse', 'sceneSpecular', 'sceneSpecularScale', 'scaleVolFog',
            'useInFog', 'useInGI', 'useInTransparents', 'temperature',
            ):
        value = component.get(key)
        if isinstance(value, (str, int, float, bool)):
            light_obj[key] = value

    color = component.get('color')
    if isinstance(color, dict):
        light_obj['redColor'] = [
            int(_light_float(color, 'Red', 255)),
            int(_light_float(color, 'Green', 255)),
            int(_light_float(color, 'Blue', 255)),
            int(_light_float(color, 'Alpha', 255)),
            ]

    flicker = component.get('flicker')
    if isinstance(flicker, dict):
        for source_key, target_key in (
                ('flickerPeriod', 'flickerPeriod'),
                ('flickerStrength', 'flickerStrength'),
                ('positionOffset', 'flickerPositionOffset'),
                ):
            value = flicker.get(source_key)
            if isinstance(value, (int, float)):
                light_obj[target_key] = value

    ies_profile = depot_path_value(component, 'iesProfile')
    if ies_profile:
        light_obj['iesProfile'] = ies_profile


def create_entity_light(component, filepath):
    name = component_name(component) or component.get('$type', 'Light')
    light_data = track_created_datablock("lights", bpy.data.lights.new(name, _blender_light_type(component)))
    _configure_light_data(light_data, component)
    light_obj = track_created_datablock("objects", bpy.data.objects.new(name, light_data))
    light_obj.rotation_mode = 'QUATERNION'
    light_obj.show_in_front = True
    _store_light_metadata(light_obj, component, filepath)
    return light_obj


def create_light_channel_mesh(component, shape_lookup, filepath):
    vertices, indices = light_channel_geometry(component, shape_lookup)
    if not vertices or not indices:
        return None
    name = component_name(component) or 'LightChannel'
    mesh_data = track_created_datablock("meshes", bpy.data.meshes.new(name))
    verts = [(v.get('X', 0), v.get('Y', 0), v.get('Z', 0)) for v in vertices]
    if isinstance(indices[0], (list, tuple)):
        faces = [list(face[:3]) for face in indices if len(face) >= 3]
    else:
        faces = [indices[i:i + 3] for i in range(0, len(indices), 3) if len(indices[i:i + 3]) == 3]
    mesh_data.from_pydata(verts, [], faces)
    mesh_data.update()

    obj = track_created_datablock("objects", bpy.data.objects.new(name, mesh_data))
    obj.display_type = 'WIRE'
    obj.color = (0.005, 0.79105, 1, 1)
    obj.show_wire = True
    obj.show_in_front = True
    obj.display.show_shadows = False
    obj.rotation_mode = 'QUATERNION'
    obj['ntype'] = 'entLightChannelComponent'
    obj['name'] = name
    obj['entJSON'] = filepath
    return obj


class EntityLightHandler:
    component_types = LIGHT_COMPONENT_TYPES

    def execute(self, component, context):
        light_collection = context.state.get("light_collection")
        if light_collection is None:
            light_collection = track_created_datablock("collections", bpy.data.collections.new(context.entity_collection.name + "_lights"))
            light_collection["nodeType"] = ", ".join(sorted(LIGHT_COMPONENT_TYPES))
            light_collection["entAppearance"] = context.appearance_name
            context.entity_collection.children.link(light_collection)
            context.state["light_collection"] = light_collection

        light_obj = create_entity_light(component, context.filepath)
        light_collection.objects.link(light_obj)

        resolved_matrix, bindname, slotname, binding_type, attach_armature = (
            context.transform_resolver.resolve_component_matrix(component)
        )
        if light_obj.data.type in {"SPOT", "AREA", "SUN"}:
            resolved_matrix = resolved_matrix @ _LIGHT_DIRECTION_CORRECTION
        light_obj.matrix_world = resolved_matrix @ light_obj.matrix_world
        light_obj["bindingType"] = binding_type
        if bindname:
            light_obj["bindname"] = bindname
        if slotname:
            light_obj["slotName"] = slotname

        operations = context.operations
        component_enabled = operations.is_component_enabled(component)
        light_obj["componentEnabled"] = component_enabled
        if not component_enabled:
            light_obj.hide_viewport = True
            light_obj.hide_render = True

        if binding_type in {"slot", "bone"} and bindname and attach_armature is not None:
            operations.configure_child_of_constraint(
                light_obj,
                attach_armature,
                bindname,
                operations.child_of_inverse_matrix(attach_armature, bindname),
            )

        context.transform_animators.add_component_driver(component, light_obj)

        return light_obj


class EntityLightChannelHandler:
    component_types = frozenset({"entLightChannelComponent"})

    def execute(self, component, context):
        lcgroupname = component_name(component) or "LightChannel"
        mesh_obj = create_light_channel_mesh(component, context.shape_lookup, context.filepath)
        if mesh_obj is None:
            return None

        lcgroup = track_created_datablock("collections", bpy.data.collections.new(lcgroupname))
        lcgroup.objects.link(mesh_obj)

        resolved_matrix, bindname, slotname, binding_type, attach_armature = (
            context.transform_resolver.resolve_component_matrix(component)
        )
        component_scale = visual_scale_matrix(component)
        if component_scale is not None:
            resolved_matrix = resolved_matrix @ component_scale
        mesh_obj["bindingType"] = binding_type
        if bindname:
            mesh_obj["bindname"] = bindname
            lcgroup["bindname"] = bindname
        if slotname:
            mesh_obj["slotName"] = slotname

        operations = context.operations
        component_enabled = operations.is_component_enabled(component)
        mesh_obj["componentEnabled"] = component_enabled
        mesh_obj.matrix_world = resolved_matrix @ mesh_obj.matrix_world
        if not component_enabled:
            mesh_obj.hide_viewport = True
            mesh_obj.hide_render = True

        if binding_type in {"slot", "bone"} and bindname and attach_armature is not None:
            operations.configure_child_of_constraint(
                mesh_obj,
                attach_armature,
                bindname,
                operations.child_of_inverse_matrix(attach_armature, bindname),
            )

        lcgroup["componentName"] = lcgroupname
        lcgroup["nodeType"] = "entLightChannelComponent"
        lcgroup["bindingType"] = binding_type
        lcgroup["entAppearance"] = context.appearance_name
        context.entity_collection.children.link(lcgroup)
        return mesh_obj


def create_auxiliary_component_registry():
    registry = EntityComponentHandlerRegistry()
    registry.register(EntityLightHandler.component_types, EntityLightHandler())
    registry.register(EntityLightChannelHandler.component_types, EntityLightChannelHandler())
    return registry
