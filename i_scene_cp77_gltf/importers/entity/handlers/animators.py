from __future__ import annotations
from ....blender.transactions import track_created_datablock

import math

import bpy

from ....animation.keyframes import assign_action_with_slot, ensure_fcurve
from ...common.entity_data import component_name
from ....assetio.values import cname_value
from ..transforms import parent_transform_data

_AXIS_INDEX = {'X': 0, 'Y': 1, 'Z': 2}


def create_axes(ent_coll, name):
    obj = ent_coll.objects.get(name)
    if obj is None:
        obj = track_created_datablock("objects", bpy.data.objects.new(name, None))
        ent_coll.objects.link(obj)
        obj.empty_display_size = .5
        obj.empty_display_type = 'PLAIN_AXES'
        obj.rotation_mode = 'XYZ'
    return obj


def set_rotation_axis_cycles(obj, axis_no, delta_radians, end_frame):
    start_value = obj.rotation_euler[axis_no]
    action = track_created_datablock("actions", bpy.data.actions.new(f'{obj.name}_rotation'))
    assign_action_with_slot(obj, action)
    fcurve = ensure_fcurve(action, obj, 'rotation_euler', axis_no, 'Rotation')
    keyframes = fcurve.keyframe_points
    if len(keyframes) < 2:
        keyframes.add(2 - len(keyframes))
    keyframes[0].co = (1, start_value)
    keyframes[1].co = (end_frame, start_value + delta_radians)
    keyframes[0].interpolation = 'LINEAR'
    keyframes[1].interpolation = 'LINEAR'
    fcurve.update()
    modifier = fcurve.modifiers.new(type='CYCLES')
    modifier.mode_before = 'REPEAT'
    modifier.mode_after = 'REPEAT'


def build_anim_impl_lookup(chunks):
    lookup = {}
    for chunk in chunks or ():
        if not isinstance(chunk, dict) or chunk.get('$type') != 'gameTransformAnimatorComponent':
            continue
        try:
            impl = chunk['animations'][0]['timeline']['items'][0]['impl']
        except (KeyError, IndexError, TypeError):
            continue
        if 'HandleId' in impl:
            lookup[int(impl['HandleId'])] = impl.get('Data')
    return lookup


def transform_animator_info(component, anim_impl_lookup):
    if not isinstance(component, dict) or component.get('$type') != 'gameTransformAnimatorComponent':
        return None
    try:
        animation = (component.get('animations') or [])[0]
        if animation.get('$type') != 'gameTransformAnimationDefinition':
            return None
        item = animation['timeline']['items'][0]
        impl_ref = int(item['impl']['HandleRefId'])
        chunk_anim = anim_impl_lookup.get(impl_ref)
    except (KeyError, IndexError, TypeError, ValueError):
        return None

    if not isinstance(chunk_anim, dict) or chunk_anim.get('$type') != 'gameTransformAnimation_RotateOnAxis':
        return None

    axis_name = chunk_anim.get('axis') or 'X'
    direction = -1 if chunk_anim.get('reverseDirection', False) else 1
    return {
        'axis_name': axis_name,
        'axis_no': _AXIS_INDEX.get(axis_name, 0),
        'duration': item.get('duration', 0),
        'delta_radians': math.radians(chunk_anim.get('numberOfFullRotations', 0) * direction * 360),
        }


def build_transform_animator_lookup(components, anim_impl_lookup):
    lookup = {}
    for component in components or []:
        info = transform_animator_info(component, anim_impl_lookup)
        name = component_name(component)
        if name and info is not None:
            lookup[name] = info
    return lookup


def ensure_transform_animator_empty(ent_coll, name, info):
    target = create_axes(ent_coll=ent_coll, name=name)
    if info is None:
        return target
    target['transformAnimatorAxis'] = info['axis_no']
    target['transformAnimatorAxisName'] = info['axis_name']
    if not target.get('transformAnimatorInitialized'):
        set_rotation_axis_cycles(target, info['axis_no'], info['delta_radians'], info['duration'] * 30)
        target['transformAnimatorInitialized'] = True
    return target


def component_transform_animator_info(component, parent_transform_lookup, transform_animator_lookup):
    binding = parent_transform_data(component, parent_transform_lookup)
    bind_name = cname_value(binding.get('bindName')) if isinstance(binding, dict) else ''
    if not bind_name:
        return '', None
    return bind_name, transform_animator_lookup.get(bind_name)


def add_rotation_axis_driver(obj, target, axis_no):
    if obj is None or target is None or axis_no is None:
        return None
    if getattr(obj, 'rotation_mode', 'XYZ') == 'QUATERNION':
        obj.rotation_mode = 'XYZ'
    base_value = obj.rotation_euler[axis_no]
    try:
        obj.driver_remove('rotation_euler', axis_no)
    except (TypeError, RuntimeError):
        pass
    fcurve = obj.driver_add('rotation_euler', axis_no)
    driver = fcurve.driver
    driver.type = 'SCRIPTED'
    driver.expression = f'{base_value:.17g} + animator_axis'
    var = driver.variables.new()
    var.name = 'animator_axis'
    var.type = 'SINGLE_PROP'
    target_ref = var.targets[0]
    target_ref.id = target
    target_ref.data_path = f'rotation_euler[{axis_no}]'
    return driver


class EntityTransformAnimatorService:
    """Own animator targets and rotation-driver binding for one appearance."""

    __slots__ = (
        "entity_collection",
        "parent_transform_lookup",
        "transform_animator_lookup",
    )

    def __init__(
        self,
        entity_collection,
        parent_transform_lookup,
        transform_animator_lookup,
    ):
        self.entity_collection = entity_collection
        self.parent_transform_lookup = parent_transform_lookup
        self.transform_animator_lookup = transform_animator_lookup or {}

    def ensure_component_target(self, component):
        name = component_name(component)
        return ensure_transform_animator_empty(
            self.entity_collection,
            name,
            self.transform_animator_lookup.get(name),
        )

    def target_for_component(self, component):
        name, info = component_transform_animator_info(
            component,
            self.parent_transform_lookup,
            self.transform_animator_lookup,
        )
        if info is None:
            return None, None
        return ensure_transform_animator_empty(
            self.entity_collection,
            name,
            info,
        ), info

    def add_driver(self, obj, target, info):
        if target is None or info is None:
            return None
        return add_rotation_axis_driver(obj, target, info["axis_no"])

    def add_component_driver(self, component, obj):
        target, info = self.target_for_component(component)
        return self.add_driver(obj, target, info)


class EntityTransformAnimatorHandler:
    component_types = frozenset({"gameTransformAnimatorComponent"})

    def execute(self, component, context):
        return context.transform_animators.ensure_component_target(component)
