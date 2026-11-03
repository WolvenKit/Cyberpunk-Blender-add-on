from __future__ import annotations
<<<<<<< Updated upstream
from ....blender.transactions import track_created_datablock
=======
>>>>>>> Stashed changes

import math

import bpy
from mathutils import Matrix

<<<<<<< Updated upstream
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
=======
from ....assetio.values import color_bytes, field_float
from ....blender.light_preview import (
    BASE_ENERGY_KEY,
    PREVIEW_AVAILABLE_KEY,
    animate_flicker,
    capture_base_energy,
    configure_contributions,
    configure_cycles_distribution,
    configure_exposure,
    configure_shadow,
    create_proxy_samples,
    light_zone_objects,
    write_zone_light,
)
from ....blender.transactions import track_created_datablock
from ....core.log import get_logger
from ....entity.domain.light_representation import (
    light_representation,
    linear_color,
    numeric_energy,
    proxy_offsets,
    softened_cosine_spot_blend,
    uses_direction_axis,
)
from ....entity.domain.light_zones import is_emissive_only, zone_light
from ....entity.domain.lights import (
    effective_light_radius,
    is_destroyed_vehicle_appearance,
    light_starts_off,
)
from ....redSpace.transforms import red_light_local_to_blender_light
from ...common.entity_data import component_name
from ...common.light_environment import register_environment_lights
from ...common.light_probe_participation import apply_probe_capture_participation
from ...common.paths import depot_path
from ...common.vehicle_light_preview import capture_vehicle_light_base
from ..policy import LIGHT_COMPONENT_TYPES, MESH_COMPONENT_TYPES, is_component_enabled
from ..registry import EntityComponentHandlerRegistry
from ..transforms import resolve_handle_data

_LOG = get_logger(__name__)
_UNSET = object()
_LIGHT_DIRECTION_CORRECTION = Matrix(red_light_local_to_blender_light())


def light_channel_geometry(component, shape_lookup=None):
    shape = (
        resolve_handle_data(component, shape_lookup, "shape")
        if shape_lookup is not None
        else None
    )
    if not isinstance(shape, dict):
        shape = component.get("shape") if type(component) is dict else None
        if isinstance(shape, dict) and isinstance(shape.get("Data"), dict):
            shape = shape.get("Data")
    if not isinstance(shape, dict):
        return None, None
    vertices = shape.get("vertices")
    indices = shape.get("indices") or shape.get("faces")
>>>>>>> Stashed changes
    if not vertices or not indices:
        return None, None
    return vertices, indices


def collect_light_channel_components(*component_groups):
    collected = {}
    has_geometry = {}
    order = []
    for components in component_groups:
        for source in components or ():
<<<<<<< Updated upstream
            if not isinstance(source, dict) or source.get('$type') != 'entLightChannelComponent':
=======
            if (
                not isinstance(source, dict)
                or source.get("$type") != "entLightChannelComponent"
            ):
>>>>>>> Stashed changes
                continue
            key = component_name(source) or str(id(source))
            if key not in collected:
                collected[key] = source
                has_geometry[key] = _UNSET
                order.append(key)
                continue
            current_has_geometry = has_geometry[key]
            if current_has_geometry is _UNSET:
<<<<<<< Updated upstream
                current_has_geometry = light_channel_geometry(collected[key])[0] is not None
                has_geometry[key] = current_has_geometry
            if not current_has_geometry and light_channel_geometry(source)[0] is not None:
=======
                current_has_geometry = (
                    light_channel_geometry(collected[key])[0] is not None
                )
                has_geometry[key] = current_has_geometry
            if (
                not current_has_geometry
                and light_channel_geometry(source)[0] is not None
            ):
>>>>>>> Stashed changes
                collected[key] = source
                has_geometry[key] = True
    return [collected[key] for key in order]


def collect_light_components(*component_groups):
    collected = {}
    order = []
    for components in component_groups:
        for component in components or ():
<<<<<<< Updated upstream
            if not isinstance(component, dict) or component.get('$type') not in LIGHT_COMPONENT_TYPES:
                continue
            name = component_name(component)
            key = name or str(component.get('id') or id(component))
=======
            if (
                not isinstance(component, dict)
                or component.get("$type") not in LIGHT_COMPONENT_TYPES
            ):
                continue
            name = component_name(component)
            key = name or str(component.get("id") or id(component))
>>>>>>> Stashed changes
            if key not in collected:
                collected[key] = component
                order.append(key)
    return [collected[key] for key in order]


<<<<<<< Updated upstream
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
=======
def _set_light_distance(light_data, radius):
    if radius <= 0.0:
        return
    if hasattr(light_data, "use_custom_distance"):
        light_data.use_custom_distance = True
    if hasattr(light_data, "cutoff_distance"):
        light_data.cutoff_distance = radius


def _configure_light_data(light_data, component, representation, sample_count=1):
    light_data.energy = numeric_energy(component) / max(1, int(sample_count))
    light_data.color = linear_color(component)
    configure_exposure(light_data, field_float(component, "EV", 0.0))
    if hasattr(light_data, "normalize"):
        light_data.normalize = True
    configure_contributions(light_data, component)
    if hasattr(light_data, "use_temperature"):
        light_data.use_temperature = False

    radius = effective_light_radius(
        field_float(component, "radius", 5.0),
        component.get("sceneDiffuse", True),
        component.get("sceneSpecular", not bool(component.get("noSpecular", 0))),
    )
    _set_light_distance(light_data, radius)

    source_radius = max(field_float(component, "sourceRadius", 0.0), 0.0)
    finite_source = representation in {
        "SPHERICAL_POINT",
        "CAPSULE_POINT_CHAIN",
        "CAPSULE_SPOT_CHAIN",
        "CAPSULE_WIDE_SPOT_POINT_CHAIN",
    }
    if hasattr(light_data, "shadow_soft_size"):
        light_data.shadow_soft_size = source_radius if finite_source else 0.0

    if light_data.type == "SPOT":
        outer_angle = max(field_float(component, "outerAngle", 45.0), 0.001)
        inner_angle = max(
            0.0, min(field_float(component, "innerAngle", outer_angle), outer_angle)
        )
        light_data.spot_size = math.radians(min(outer_angle, 179.999))
        light_data.spot_blend = softened_cosine_spot_blend(
            inner_angle,
            outer_angle,
            field_float(component, "softness", 2.0),
        )

    configure_shadow(light_data, component, representation)
    return radius


def _configure_distribution(
    light_data, component, radius, resolved_ies="", resolved_projection=""
):
    configure_cycles_distribution(
        light_data,
        component.get("attenuation", ""),
        radius,
        bool(component.get("clampAttenuation", False)),
        ies_path=resolved_ies,
        projection_path=resolved_projection,
    )


def _store_light_metadata(light_obj, component):
    component_type = component.get("$type", "entLightComponent")
    light_obj["cp77_type"] = component_type
    light_obj["componentName"] = component_name(component)
    apply_probe_capture_participation(light_obj, component)

    for key in (
        "type",
        "unit",
        "intensity",
        "EV",
        "radius",
        "innerAngle",
        "outerAngle",
        "sourceRadius",
        "shadowRadius",
        "softness",
        "areaShape",
        "areaRectSideA",
        "areaRectSideB",
        "capsuleLength",
        "areaTwoSided",
        "attenuation",
        "lightChannel",
        "group",
        "turnOnByDefault",
        "onStrength",
        "materialZone",
        "enableLocalShadows",
        "enableContactShadows",
        "contactShadows",
        "sceneDiffuse",
        "sceneSpecular",
        "sceneSpecularScale",
        "scaleVolFog",
        "scaleEnvProbes",
        "scaleGI",
        "useInFog",
        "useInGI",
        "useInEnvProbes",
        "useInParticles",
        "useInTransparents",
        "temperature",
        "clampAttenuation",
        "spotCapsule",
        "envColorGroup",
        "colorGroupSaturation",
        "portalAngleCutoff",
        "shadowAngle",
        "shadowFadeDistance",
        "shadowFadeRange",
        "roughnessBias",
        "allowDistantLight",
        "autoHideDistance",
        "autoHideRange",
        "lightType",
        "emissiveOnly",
        "allowSeparateEmissiveColor",
        "highBeamConeMultiplier",
        "highBeamRadiusMultiplier",
        "highBeamPitchAngle",
        "rayTracingIntensityScale",
        "rayTracingContactShadowRange",
        "rayTracingLightSourceRadius",
        "rtxdiShadowStartingDistance",
        "pathTracingOverrideScaleGI",
        "turnOnTime",
        "turnOffTime",
        "loopTime",
        "synchronizedLoop",
        "isDestructible",
        "colliderName",
        "colliderTag",
        "directional",
    ):
>>>>>>> Stashed changes
        value = component.get(key)
        if isinstance(value, (str, int, float, bool)):
            light_obj[key] = value

<<<<<<< Updated upstream
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
=======
    color = component.get("color")
    if isinstance(color, dict):
        light_obj["color"] = [int(value) for value in color_bytes(color, 255.0, 4)]

    flicker = component.get("flicker")
    if isinstance(flicker, dict):
        for source_key, target_key in (
            ("flickerPeriod", "flickerPeriod"),
            ("flickerStrength", "flickerStrength"),
            ("positionOffset", "flickerPositionOffset"),
        ):
>>>>>>> Stashed changes
            value = flicker.get(source_key)
            if isinstance(value, (int, float)):
                light_obj[target_key] = value

<<<<<<< Updated upstream
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
=======
    emissive_color = component.get("emissiveColor")
    if isinstance(emissive_color, dict):
        light_obj["emissiveColor"] = [
            int(value) for value in color_bytes(emissive_color, 0.0, 4)
        ]

    for source_key in ("projectionTexture", "turnOnCurve", "turnOffCurve", "loopCurve"):
        depot_value = depot_path(component, source_key, normalize=False)
        if depot_value:
            light_obj[source_key] = depot_value
        else:
            value = component.get(source_key)
            if isinstance(value, dict):
                value = value.get("$value")
            if isinstance(value, str) and value not in {"", "None"}:
                light_obj[source_key] = value

    ies_profile = depot_path(component, "iesProfile", normalize=False)
    if ies_profile:
        light_obj["iesProfile"] = ies_profile


def create_entity_light(component, resolved_ies="", resolved_projection=""):
    name = component_name(component) or component.get("$type", "Light")
    blender_type, representation = light_representation(component)
    offsets = proxy_offsets(component, representation)
    light_data = track_created_datablock(
        "lights", bpy.data.lights.new(name, blender_type)
    )
    effective_radius = _configure_light_data(
        light_data, component, representation, len(offsets)
    )
    light_obj = track_created_datablock(
        "objects", bpy.data.objects.new(name, light_data)
    )
    light_obj.rotation_mode = "QUATERNION"
    light_obj.show_in_front = True
    capture_base_energy(light_obj)
    _store_light_metadata(light_obj, component)
    light_obj["cp77_proxy_representation"] = representation
    light_obj["cp77_effective_radius"] = effective_radius

    _configure_distribution(
        light_data, component, effective_radius, resolved_ies, resolved_projection
    )
    if resolved_ies:
        light_obj["cp77_resolved_ies_profile"] = resolved_ies
    if resolved_projection:
        light_obj["cp77_resolved_projection_texture"] = resolved_projection
    capture_vehicle_light_base(light_obj)
    light_obj.location.x = float(offsets[0])
    samples = create_proxy_samples(
        light_obj,
        representation,
        offsets,
        effective_radius,
        resolved_ies,
        resolved_projection,
    )
    for sample in samples:
        sample.rotation_mode = "QUATERNION"
        sample.show_in_front = True
        _store_light_metadata(sample, component)
        capture_vehicle_light_base(sample)
    return light_obj, samples


def create_light_channel_mesh(component, shape_lookup):
    vertices, indices = light_channel_geometry(component, shape_lookup)
    if not vertices or not indices:
        return None
    name = component_name(component) or "LightChannel"
    mesh_data = track_created_datablock("meshes", bpy.data.meshes.new(name))
    verts = [(v.get("X", 0), v.get("Y", 0), v.get("Z", 0)) for v in vertices]
    if isinstance(indices[0], (list, tuple)):
        faces = [list(face[:3]) for face in indices if len(face) >= 3]
    else:
        faces = [
            indices[i : i + 3]
            for i in range(0, len(indices), 3)
            if len(indices[i : i + 3]) == 3
        ]
>>>>>>> Stashed changes
    mesh_data.from_pydata(verts, [], faces)
    mesh_data.update()

    obj = track_created_datablock("objects", bpy.data.objects.new(name, mesh_data))
<<<<<<< Updated upstream
    obj.display_type = 'WIRE'
=======
    obj.display_type = "WIRE"
>>>>>>> Stashed changes
    obj.color = (0.005, 0.79105, 1, 1)
    obj.show_wire = True
    obj.show_in_front = True
    obj.display.show_shadows = False
<<<<<<< Updated upstream
    obj.rotation_mode = 'QUATERNION'
    obj['ntype'] = 'entLightChannelComponent'
    obj['name'] = name
    obj['entJSON'] = filepath
    return obj


=======
    obj.hide_render = True
    obj.rotation_mode = "QUATERNION"
    obj["cp77_type"] = "entLightChannelComponent"
    obj["componentName"] = name
    obj["channels"] = str(component.get("channels", ""))
    obj["cp77_light_channel_volume"] = True
    return obj


def _is_mesh_component(component):
    return component.get("$type") in MESH_COMPONENT_TYPES


def _drive_zone(component, zone, context):
    """Write zone onto the light-zone objects of the mesh component the light binds to"""
    parent = context.transform_resolver.parent_component(component)
    if parent is None or not _is_mesh_component(parent):
        return
    collection = context.state.get("component_collections", {}).get(
        component_name(parent)
    )
    if collection is None:
        _LOG.debug(
            "Light component %s is bound to mesh %s, which was not imported; it sets no zone",
            component_name(component),
            component_name(parent),
        )
        return
    objects = light_zone_objects(collection)
    write_zone_light(objects, zone)
    if objects and not zone.device:
        context.entity_collection[PREVIEW_AVAILABLE_KEY] = True


def _follow_binding(obj, component, context):
    """Constrain obj to the transform animator, bone or rig its component's binding chain ends at"""
    animator_target = context.transform_animators.target_for_component(component)
    if animator_target is not None:
        context.transform_animators.add_binding(obj, animator_target)
        return
    target, subtarget, _attachment_type = (
        context.transform_resolver.resolve_dynamic_attachment(component)
    )
    if target is not None:
        context.operations.configure_child_of_constraint(obj, target, subtarget)


>>>>>>> Stashed changes
class EntityLightHandler:
    component_types = LIGHT_COMPONENT_TYPES

    def execute(self, component, context):
<<<<<<< Updated upstream
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
=======
        # A game or vehicle light component sets the colour and level of a light zone on its direct parent mesh, whose
        # light-zone materials read them from their objects; an emissive-only one casts no light besides. A zone that
        # several components name on one mesh takes the values of the last; a zone no light writes is dark.
        zone = zone_light(
            component,
            destroyed=is_destroyed_vehicle_appearance(context.appearance_name),
        )
        if is_emissive_only(component):
            if zone is not None:
                _drive_zone(component, zone, context)
            elif is_component_enabled(component):
                _LOG.warning(
                    "Emissive-only light component %s names no light zone (materialZone %r); it sets nothing",
                    component_name(component),
                    component.get("materialZone"),
                )
            return None
        light_collection = context.state.get("light_collection")
        if light_collection is None:
            light_collection = track_created_datablock(
                "collections",
                bpy.data.collections.new(context.entity_collection.name + "_lights"),
            )
            light_collection["cp77_node_type"] = ", ".join(
                sorted(LIGHT_COMPONENT_TYPES)
            )
            context.entity_collection.children.link(light_collection)
            context.state["light_collection"] = light_collection

        ies_profile = depot_path(component, "iesProfile", normalize=False)
        resolved_ies = ""
        if ies_profile and context.resolve_export is not None:
            resolved_ies = context.resolve_export(ies_profile, ".ies") or ""
        projection_texture = depot_path(component, "projectionTexture", normalize=False)
        resolved_projection = ""
        if projection_texture and context.resolve_export is not None:
            resolved_projection = (
                context.resolve_export(
                    projection_texture,
                    (".dds", ".png", ".tga", ".jpg", ".jpeg"),
                )
                or ""
            )
        light_obj, proxy_children = create_entity_light(
            component,
            resolved_ies,
            resolved_projection,
        )
        light_collection.objects.link(light_obj)
        for child in proxy_children:
            light_collection.objects.link(child)
        operations = context.operations
        component_enabled = operations.is_component_enabled(component)
        for obj in (light_obj, *proxy_children):
            obj["cp77_component_enabled"] = component_enabled
            if not component_enabled:
                obj.hide_viewport = True
                obj.hide_render = True

        scene = getattr(bpy.context, "scene", None)
        if scene is not None:
            register_environment_lights(scene, (light_obj, *proxy_children))

        is_vehicle_light = component.get("$type") == "vehicleLightComponent"
        # A light that starts off (turnOnByDefault 0) stays dark until its device switches it on, as in the game; a
        # vehicle's lights stay dark until the vehicle switches light them.
        active_default = (
            component_enabled
            and not light_starts_off(component)
            and not is_vehicle_light
        )
        seed = component_name(component) or component.get("id") or light_obj.name
        for obj in (light_obj, *proxy_children):
            animate_flicker(
                obj.data,
                component.get("flicker"),
                seed,
                base_energy=float(obj[BASE_ENERGY_KEY]),
                active=active_default,
            )
            if not active_default:
                obj.data.energy = 0.0

        resolved_matrix, bindname, slotname, binding_type, _ = (
            context.transform_resolver.resolve_component_matrix(component)
        )
        representation = str(light_obj.get("cp77_proxy_representation", ""))
        if uses_direction_axis(representation):
            resolved_matrix = resolved_matrix @ _LIGHT_DIRECTION_CORRECTION
        light_obj.matrix_world = resolved_matrix @ light_obj.matrix_world
        light_obj["cp77_binding_type"] = binding_type
>>>>>>> Stashed changes
        if bindname:
            light_obj["bindname"] = bindname
        if slotname:
            light_obj["slotName"] = slotname
<<<<<<< Updated upstream

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

=======
        _follow_binding(light_obj, component, context)
        # Last, so a light that fails before leaves its vehicle's flag and its zone as they were.
        if is_vehicle_light:
            context.entity_collection[PREVIEW_AVAILABLE_KEY] = True
        if zone is not None:
            _drive_zone(component, zone, context)
>>>>>>> Stashed changes
        return light_obj


class EntityLightChannelHandler:
    component_types = frozenset({"entLightChannelComponent"})

    def execute(self, component, context):
        lcgroupname = component_name(component) or "LightChannel"
<<<<<<< Updated upstream
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
=======
        mesh_obj = create_light_channel_mesh(component, context.shape_lookup)
        if mesh_obj is None:
            return None

        lcgroup = track_created_datablock(
            "collections", bpy.data.collections.new(lcgroupname)
        )
        lcgroup.objects.link(mesh_obj)

        resolved_matrix, bindname, slotname, binding_type, _ = (
            context.transform_resolver.resolve_component_matrix(component)
        )
        component_scale = context.operations.visual_scale_matrix(component)
        if component_scale is not None:
            resolved_matrix = resolved_matrix @ component_scale
        mesh_obj["cp77_binding_type"] = binding_type
>>>>>>> Stashed changes
        if bindname:
            mesh_obj["bindname"] = bindname
            lcgroup["bindname"] = bindname
        if slotname:
            mesh_obj["slotName"] = slotname

        operations = context.operations
        component_enabled = operations.is_component_enabled(component)
<<<<<<< Updated upstream
        mesh_obj["componentEnabled"] = component_enabled
=======
        mesh_obj["cp77_component_enabled"] = component_enabled
>>>>>>> Stashed changes
        mesh_obj.matrix_world = resolved_matrix @ mesh_obj.matrix_world
        if not component_enabled:
            mesh_obj.hide_viewport = True
            mesh_obj.hide_render = True
<<<<<<< Updated upstream

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
=======
        _follow_binding(mesh_obj, component, context)

        lcgroup["componentName"] = lcgroupname
        lcgroup["cp77_node_type"] = "entLightChannelComponent"
        lcgroup["cp77_binding_type"] = binding_type
>>>>>>> Stashed changes
        context.entity_collection.children.link(lcgroup)
        return mesh_obj


def create_auxiliary_component_registry():
    registry = EntityComponentHandlerRegistry()
    registry.register(EntityLightHandler.component_types, EntityLightHandler())
<<<<<<< Updated upstream
    registry.register(EntityLightChannelHandler.component_types, EntityLightChannelHandler())
=======
    registry.register(
        EntityLightChannelHandler.component_types, EntityLightChannelHandler()
    )
>>>>>>> Stashed changes
    return registry
