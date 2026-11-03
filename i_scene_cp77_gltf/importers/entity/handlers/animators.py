from __future__ import annotations
<<<<<<< Updated upstream
from ....blender.transactions import track_created_datablock

import math

import bpy

from ....animation.keyframes import assign_action_with_slot, ensure_fcurve
from ...common.entity_data import component_name
from ....assetio.values import cname_value
from ..transforms import parent_transform_data

_AXIS_INDEX = {'X': 0, 'Y': 1, 'Z': 2}
=======

import bpy

from ....assetio.values import cname_value
from ....blender.keyframes import assign_action_with_slot, ensure_fcurve
from ....blender.transactions import track_created_datablock
from ....core.log import get_logger, log_once
from ...common.entity_data import component_name
from ..transform_animator import (
    TransformAnimatorProgram,
    preview_transform_animator_program,
    transform_animator_rotation_channel_keys,
    transform_animator_translation_channel_keys,
)
from ..transforms import component_local_matrix, resolve_handle_data

_LOG = get_logger(__name__)
_RUNTIME_VERSION = 3
>>>>>>> Stashed changes


def create_axes(ent_coll, name):
    obj = ent_coll.objects.get(name)
    if obj is None:
        obj = track_created_datablock("objects", bpy.data.objects.new(name, None))
        ent_coll.objects.link(obj)
<<<<<<< Updated upstream
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
=======
        obj.empty_display_size = 0.5
        obj.empty_display_type = "PLAIN_AXES"
        obj.rotation_mode = "XYZ"
    return obj


def _scene_fps():
    scene = bpy.context.scene
    fps = float(scene.render.fps)
    base = float(scene.render.fps_base or 1.0)
    return fps / base if fps > 0.0 and base > 0.0 else 30.0


def _set_keyframe_style(point, interpolation, easing):
    try:
        point.interpolation = interpolation
    except (AttributeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_set_keyframe_style 1", type(error).__name__),
            "set keyframe style: fell back after %s",
            error,
            exc_info=True,
        )
        point.interpolation = "LINEAR"
    if interpolation not in {"CONSTANT", "LINEAR", "BEZIER"}:
        try:
            point.easing = easing
        except (AttributeError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_set_keyframe_style 2", type(error).__name__),
                "set keyframe style: fell back after %s",
                error,
                exc_info=True,
            )


def _write_fcurve(action, obj, data_path, axis_no, keys):
    if not keys:
        return None
    fcurve = ensure_fcurve(
        action,
        obj,
        data_path,
        axis_no,
        "Transform Animator",
    )
    points = fcurve.keyframe_points
    points.add(len(keys))
    fps = _scene_fps()
    for point, key in zip(points, keys):
        point.co = (1.0 + key.seconds * fps, key.value)
        _set_keyframe_style(point, key.interpolation, key.easing)
    fcurve.update()
    return fcurve


def set_transform_animator_action(
    obj,
    program: TransformAnimatorProgram,
    *,
    base_local_position=(0.0, 0.0, 0.0),
    action_suffix="",
):
    rotation_keys = transform_animator_rotation_channel_keys(program)
    translation_keys = transform_animator_translation_channel_keys(
        program,
        base_local_position,
    )
    if not rotation_keys and not translation_keys:
        return None

    suffix = action_suffix or program.name or "TransformAnimation"
    action = track_created_datablock(
        "actions",
        bpy.data.actions.new(f"{obj.name}__{suffix}"),
    )
    action.use_fake_user = True
    assign_action_with_slot(obj, action)

    obj.rotation_mode = "XYZ"
    fcurves = []
    for axis_no, keys in rotation_keys.items():
        fcurve = _write_fcurve(action, obj, "delta_rotation_euler", axis_no, keys)
        if fcurve is not None:
            fcurves.append(fcurve)
    for axis_no, keys in translation_keys.items():
        fcurve = _write_fcurve(action, obj, "delta_location", axis_no, keys)
        if fcurve is not None:
            fcurves.append(fcurve)

    if program.looping and program.duration_seconds > 1.0e-8:
        for fcurve in fcurves:
            modifier = fcurve.modifiers.new(type="CYCLES")
            modifier.mode_before = "REPEAT"
            modifier.mode_after = "REPEAT"
    return action


def ensure_transform_animator_empty(
    ent_coll,
    name,
    programs,
    *,
    matrix_world=None,
    base_local_position=(0.0, 0.0, 0.0),
):
    target = create_axes(ent_coll=ent_coll, name=name)
    if matrix_world is not None:
        target.matrix_world = matrix_world
    programs = tuple(programs or ())
    if not programs:
        return target

    if (
        int(target.get("cp77_transform_animator_runtime_version", 0))
        != _RUNTIME_VERSION
    ):
        target.delta_location = (0.0, 0.0, 0.0)
        target.delta_rotation_euler = (0.0, 0.0, 0.0)
        active_action = None
        for index, program in enumerate(programs):
            suffix = program.name or f"TransformAnimation_{index + 1}"
            action = set_transform_animator_action(
                target,
                program,
                base_local_position=base_local_position,
                action_suffix=suffix,
            )
            if action is None:
                continue
            if active_action is None and program.auto_start:
                active_action = action

        animation_data = target.animation_data_create()
        if active_action is not None:
            assign_action_with_slot(target, active_action)
        else:
            animation_data.action = None
        target["cp77_transform_animator_runtime_version"] = _RUNTIME_VERSION
    return target


def component_transform_animator_info(
    component, parent_transform_lookup, transform_animator_lookup
):
    binding = resolve_handle_data(component, parent_transform_lookup, "parentTransform")
    bind_name = (
        cname_value(binding.get("bindName")) if isinstance(binding, dict) else ""
    )
    if not bind_name:
        return "", None
    programs = transform_animator_lookup.get(bind_name) or ()
    return bind_name, preview_transform_animator_program(programs)


class EntityTransformAnimatorService:
    """Own transform-parent animator targets for one imported appearance"""

    __slots__ = (
        "building",
        "components_by_name",
        "configure_child_of_constraint",
        "entity_collection",
        "parent_transform_lookup",
        "targets",
        "transform_animator_lookup",
        "transform_resolver",
>>>>>>> Stashed changes
    )

    def __init__(
        self,
        entity_collection,
        parent_transform_lookup,
        transform_animator_lookup,
<<<<<<< Updated upstream
=======
        transform_resolver,
        configure_child_of_constraint,
>>>>>>> Stashed changes
    ):
        self.entity_collection = entity_collection
        self.parent_transform_lookup = parent_transform_lookup
        self.transform_animator_lookup = transform_animator_lookup or {}
<<<<<<< Updated upstream

    def ensure_component_target(self, component):
        name = component_name(component)
        return ensure_transform_animator_empty(
            self.entity_collection,
            name,
            self.transform_animator_lookup.get(name),
        )

    def target_for_component(self, component):
        name, info = component_transform_animator_info(
=======
        self.transform_resolver = transform_resolver
        self.configure_child_of_constraint = configure_child_of_constraint
        self.components_by_name = (
            getattr(transform_resolver, "components_by_name", {}) or {}
        )
        self.targets = {}
        self.building = set()

    def ensure_component_target(self, component):
        name = component_name(component)
        if not name:
            return None
        if name in self.building:
            _LOG.warning("Transform animator parent cycle detected at %s", name)
            return None
        target = self.targets.get(name)
        if target is not None:
            return target

        self.building.add(name)
        try:
            matrix_world = self.transform_resolver.resolve_component_matrix(component)[
                0
            ]
            local_position = tuple(
                float(value) for value in component_local_matrix(component).translation
            )
            programs = self.transform_animator_lookup.get(name) or ()
            target = ensure_transform_animator_empty(
                self.entity_collection,
                name,
                programs,
                matrix_world=matrix_world,
                base_local_position=local_position,
            )
            self.targets[name] = target

            binding = resolve_handle_data(
                component, self.parent_transform_lookup, "parentTransform"
            )
            bind_name = (
                cname_value(binding.get("bindName"))
                if isinstance(binding, dict)
                else ""
            )
            parent_component = (
                self.components_by_name.get(bind_name) if bind_name else None
            )
            if (
                isinstance(parent_component, dict)
                and parent_component.get("$type") == "gameTransformAnimatorComponent"
            ):
                parent_target = self.ensure_component_target(parent_component)
                if parent_target is not None and parent_target is not target:
                    self.configure_child_of_constraint(target, parent_target, "")
            else:
                attachment_target, attachment_subtarget, _attachment_type = (
                    self.transform_resolver.resolve_dynamic_attachment(component)
                )
                if attachment_target is not None:
                    self.configure_child_of_constraint(
                        target,
                        attachment_target,
                        attachment_subtarget,
                    )

            unsupported = []
            for program in programs:
                for item in program.unsupported_items:
                    if item not in unsupported:
                        unsupported.append(item)
            if unsupported:
                _LOG.debug(
                    "Transform animator %s ignores unsupported timeline item(s): %s",
                    name,
                    ", ".join(unsupported),
                )
            return target
        finally:
            self.building.discard(name)

    def target_for_component(self, component):
        name, program = component_transform_animator_info(
>>>>>>> Stashed changes
            component,
            self.parent_transform_lookup,
            self.transform_animator_lookup,
        )
<<<<<<< Updated upstream
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
=======
        if program is None:
            return None
        animator_component = self.components_by_name.get(name)
        if not isinstance(animator_component, dict):
            return None
        return self.ensure_component_target(animator_component)

    def add_binding(self, obj, target):
        if obj is None or target is None:
            return None
        return self.configure_child_of_constraint(obj, target, "")
>>>>>>> Stashed changes


class EntityTransformAnimatorHandler:
    component_types = frozenset({"gameTransformAnimatorComponent"})

    def execute(self, component, context):
        return context.transform_animators.ensure_component_target(component)
