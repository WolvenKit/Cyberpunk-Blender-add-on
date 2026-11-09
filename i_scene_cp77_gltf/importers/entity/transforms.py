from __future__ import annotations

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from ...animation.domain.rig.naming import merged_bone_name
from ...assetio.values import cname_value, resolve_handle_reference
from ...blender.red_transforms import transform_matrix
from ...core.log import get_logger, log_once
from ..common.entity_data import build_component_lookup, component_name
from ..common.paths import depot_path

_LOG = get_logger(__name__)

ARMATURE_TYPE = "ARMATURE"
_UNSET = object()

_ARMATURE_BONE_SET_CACHE = {}
_RIG_BONE_INDEX_CACHE = {}
_RIG_BONE_MATRIX_CACHE = {}
_RIG_MODEL_SPACE_CACHE = {}
_RIG_BONE_MATRIX_ARRAY_CACHE = {}
_RIG_BONE_SOURCE_CACHE = {}
_SKINNING_BIND_NAME_CACHE = {}
_PENDING_CHILD_OF_INVERSES = {}


def clear_transform_caches():
    """Clear import-scoped transform, rig-matrix, and bone lookup caches"""
    _ARMATURE_BONE_SET_CACHE.clear()
    _RIG_BONE_INDEX_CACHE.clear()
    _RIG_BONE_MATRIX_CACHE.clear()
    _RIG_MODEL_SPACE_CACHE.clear()
    _RIG_BONE_MATRIX_ARRAY_CACHE.clear()
    _RIG_BONE_SOURCE_CACHE.clear()
    _SKINNING_BIND_NAME_CACHE.clear()


def build_slot_lookup(vehicle_slots):
    lookup = {}
    for slot in vehicle_slots or []:
        name = cname_value(slot.get("slotName"))
        if name:
            # Preserve the first slot registered under each name.
            lookup.setdefault(name, slot)
    return lookup


def build_rig_bone_index(rig_j):
    if not rig_j or not rig_j.get("boneNames"):
        return {}
    out = {}
    for index, bone in enumerate(rig_j["boneNames"]):
        name = cname_value(bone)
        if name:
            out[name] = index
    return out


def rig_bone_index_for(rig_j):
    if type(rig_j) is not dict:
        return {}
    key = id(rig_j)
    cached = _RIG_BONE_INDEX_CACHE.get(key)
    if cached is not None and cached[0] is rig_j:
        return cached[1]
    index = build_rig_bone_index(rig_j)
    _RIG_BONE_INDEX_CACHE[key] = (rig_j, index)
    return index


def _rig_json_bone_source(rig_j):
    cache_key = id(rig_j)
    cached = _RIG_BONE_SOURCE_CACHE.get(cache_key)
    if cached is not None and cached[0] is rig_j:
        return cached[1]
    bone_count = len(rig_j.get("boneNames") or ())
    apose_ls = rig_j.get("aPoseLS")
    has_apose = type(apose_ls) is list and len(apose_ls) == bone_count
    apose_ms = rig_j.get("aPoseMS")
    use_model_space = (
        has_apose and type(apose_ms) is list and len(apose_ms) == bone_count
    )
    transforms = (
        apose_ms
        if use_model_space
        else (apose_ls if has_apose else rig_j.get("boneTransforms"))
    )
    source = (transforms, rig_j.get("boneParentIndexes"), use_model_space)
    _RIG_BONE_SOURCE_CACHE[cache_key] = (rig_j, source)
    return source


def _rig_bone_matrices(rig_j):
    cache_key = id(rig_j)
    cached = _RIG_BONE_MATRIX_CACHE.get(cache_key)
    if cached is not None and cached[0] is rig_j:
        return cached[1]
    matrices = {}
    _RIG_BONE_MATRIX_CACHE[cache_key] = (rig_j, matrices)
    return matrices


def _rig_json_model_space_matrices(rig_j):
    if type(rig_j) is not dict:
        return ()
    cache_key = id(rig_j)
    cached = _RIG_MODEL_SPACE_CACHE.get(cache_key)
    if cached is not None and cached[0] is rig_j:
        return cached[1]
    matrix_cache = _rig_bone_matrices(rig_j)
    matrices = tuple(
        _rig_json_bone_matrix_for_index(rig_j, index, matrix_cache)
        for index in range(len(rig_j.get("boneNames") or ()))
    )
    _RIG_MODEL_SPACE_CACHE[cache_key] = (rig_j, matrices)
    return matrices


def _rig_json_bone_matrix_array(rig_j):
    if type(rig_j) is not dict:
        return np.empty((0, 4, 4), dtype=np.float64)
    cache_key = id(rig_j)
    cached = _RIG_BONE_MATRIX_ARRAY_CACHE.get(cache_key)
    if cached is not None and cached[0] is rig_j:
        return cached[1]
    matrices = _rig_json_model_space_matrices(rig_j)
    array = np.asarray(matrices, dtype=np.float64)
    if not matrices:
        array = np.empty((0, 4, 4), dtype=np.float64)
    _RIG_BONE_MATRIX_ARRAY_CACHE[cache_key] = (rig_j, array)
    return array


def _rig_json_bone_matrix_for_index(rig_j, index, matrices, resolving=None):
    if type(rig_j) is not dict or index is None or index < 0:
        return Matrix.Identity(4)
    index_key = ("index", index)
    cached = matrices.get(index_key)
    if cached is not None:
        return cached

    resolving = resolving or set()
    if index in resolving:
        return Matrix.Identity(4)
    resolving.add(index)

    transforms, parents, use_model_space = _rig_json_bone_source(rig_j)
    if type(transforms) is list and index < len(transforms):
        matrix = transform_matrix(transforms[index])
        if not use_model_space:
            parent_index = (
                parents[index] if type(parents) is list and index < len(parents) else -1
            )
            parent_matrix = (
                _rig_json_bone_matrix_for_index(
                    rig_j, parent_index, matrices, resolving
                )
                if parent_index is not None and parent_index >= 0
                else Matrix.Identity(4)
            )
            matrix = parent_matrix @ matrix
    else:
        matrix = Matrix.Identity(4)

    resolving.remove(index)
    matrices[index_key] = matrix
    return matrix


def rig_json_bone_matrix(rig_j, bone_name, rig_bone_index=None):
    if type(rig_j) is not dict or not bone_name:
        return Matrix.Identity(4)
    matrices = _rig_bone_matrices(rig_j)
    cached = matrices.get(bone_name)
    if cached is not None:
        return cached
    index = (rig_bone_index or rig_bone_index_for(rig_j)).get(bone_name)
    matrix = (
        _rig_json_bone_matrix_for_index(rig_j, index, matrices)
        if index is not None
        else Matrix.Identity(4)
    )
    matrices[bone_name] = matrix
    return matrix


def build_slot_owner_binding_maps(
    slot_components,
    parent_transform_lookup,
    rig_json_by_component_name,
    rig_component_names,
):
    rig_jsons = {}
    rig_owner_names = {}
    for component in slot_components or ():
        owner_name = component_name(component)
        if not owner_name:
            continue
        binding = resolve_handle_data(
            component, parent_transform_lookup, "parentTransform"
        )
        bind_name = (
            cname_value(binding.get("bindName")) if type(binding) is dict else ""
        )
        if bind_name in rig_json_by_component_name:
            rig_jsons[owner_name] = rig_json_by_component_name[bind_name]
        if bind_name in rig_component_names:
            rig_owner_names[owner_name] = bind_name
    return rig_jsons, rig_owner_names


def component_local_matrix(component):
    transform = component.get("localTransform", {}) if type(component) is dict else {}
    return transform_matrix(transform)


def visual_scale_matrix(component):
    # Apply visualScale to component geometry, not its children.
    scale = component.get("visualScale") if type(component) is dict else None
    if type(scale) is not dict:
        return None
    vec = Vector((scale.get("X", 1), scale.get("Y", 1), scale.get("Z", 1)))
    if (
        abs(vec.x - 1.0) <= 1e-9
        and abs(vec.y - 1.0) <= 1e-9
        and abs(vec.z - 1.0) <= 1e-9
    ):
        return None
    return Matrix.LocRotScale(Vector((0, 0, 0)), Quaternion((1, 0, 0, 0)), vec)


def resolve_handle_data(component, lookup, key):
    value = component.get(key) if isinstance(component, dict) else None
    return resolve_handle_reference(value, lookup, component)


def skinning_binding_data(component, skinning_lookup=None):
    resolved = resolve_handle_data(component, skinning_lookup, "skinning")
    if resolved is not None:
        return resolved
    skinning = component.get("skinning") if type(component) is dict else None
    return skinning if isinstance(skinning, dict) and "Data" not in skinning else None


def skinning_bind_name(component, skinning_lookup=None):
    cache_key = (id(component), id(skinning_lookup))
    cached = _SKINNING_BIND_NAME_CACHE.get(cache_key)
    if cached is not None and cached[0] is component and cached[1] is skinning_lookup:
        return cached[2]
    data = skinning_binding_data(component, skinning_lookup)
    bind_name = cname_value(data.get("bindName")) if isinstance(data, dict) else ""
    _SKINNING_BIND_NAME_CACHE[cache_key] = (component, skinning_lookup, bind_name)
    return bind_name


def component_uses_skinning(component, skinning_lookup=None):
    bind_name = skinning_bind_name(component, skinning_lookup)
    return bool(bind_name and bind_name != "None")


def is_live_armature_object(obj):
    if obj is None:
        return False
    try:
        if obj.type != ARMATURE_TYPE:
            return False
        name = obj.name
    except (AttributeError, ReferenceError, RuntimeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("is_live_armature_object 1", type(error).__name__),
            "is live armature object: fell back after %s",
            error,
            exc_info=True,
        )
        return False
    objects = getattr(getattr(bpy, "data", None), "objects", None)
    if objects is None:
        return False
    try:
        return objects.get(name) is obj
    except (AttributeError, ReferenceError, RuntimeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("is_live_armature_object 2", type(error).__name__),
            "is live armature object: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def cache_armature_bones(armature):
    try:
        pose = armature.pose
        bone_count = len(pose.bones)
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("cache_armature_bones", type(error).__name__),
            "cache armature bones: fell back after %s",
            error,
            exc_info=True,
        )
        return set()
    cache_key = (id(armature), armature.data.as_pointer())
    cached = _ARMATURE_BONE_SET_CACHE.get(cache_key)
    if cached is not None and cached[0] is armature and cached[1] == bone_count:
        return cached[2]
    if not is_live_armature_object(armature):
        return set()
    bone_set = set(pose.bones.keys())
    _ARMATURE_BONE_SET_CACHE[cache_key] = (armature, bone_count, bone_set)
    return bone_set


def armature_has_bone(armature, bone_name):
    return bool(armature and bone_name and bone_name in cache_armature_bones(armature))


def build_slot_component_lookups(components):
    lookups = {}
    for component in components or []:
        slots = component.get("slots") if type(component) is dict else None
        name = component_name(component)
        if name and isinstance(slots, list):
            lookups[name] = build_slot_lookup(slots)
    return lookups


class EntityTransformResolver:
    def __init__(
        self,
        components,
        parent_transform_lookup,
        skinning_lookup=None,
        rig=None,
        rig_j=None,
        rig_bone_index=None,
        default_slot_lookup=None,
        slot_owner_rig_jsons=None,
        rig_json_by_component_name=None,
        rig_json_by_bone_name=None,
        armature_by_component_name=None,
        slot_owner_rig_owner_names=None,
        components_by_name=None,
        slot_component_lookups=None,
        component_skin_placements=None,
        local_matrix_resolver=None,
    ):
        self.components = components or []
        self.components_by_name = (
            components_by_name
            if components_by_name is not None
            else build_component_lookup(self.components)
        )
        self.parent_transform_lookup = parent_transform_lookup or {}
        self.skinning_lookup = skinning_lookup or {}
        self.slot_component_lookups = (
            slot_component_lookups
            if slot_component_lookups is not None
            else build_slot_component_lookups(self.components)
        )
        self.rig = rig
        self.rig_j = rig_j
        self.rig_bone_index = rig_bone_index or rig_bone_index_for(rig_j)
        self.slot_owner_rig_jsons = slot_owner_rig_jsons or {}
        self.rig_json_by_component_name = rig_json_by_component_name or {}
        self.rig_json_by_bone_name = rig_json_by_bone_name or {}
        self.armature_by_component_name = armature_by_component_name or {}
        self.rig_owners_by_json_id = {}
        for owner_name, owner_rig_json in self.rig_json_by_component_name.items():
            if owner_rig_json is not None:
                self.rig_owners_by_json_id.setdefault(id(owner_rig_json), []).append(
                    owner_name
                )
        self.slot_owner_rig_owner_names = slot_owner_rig_owner_names or {}
        self.default_slot_lookup = default_slot_lookup or {}
        self.component_skin_placements = component_skin_placements or {}
        self.local_matrix_resolver = local_matrix_resolver or component_local_matrix
        self.cache = {}
        self.local_matrix_cache = {}
        self.binding_cache = {}
        self.slot_matrix_cache = {}
        self.bone_matrix_cache = {}
        self.bone_source_cache = {}
        self.slot_cache = {}
        self.binding_target_cache = {}
        self.dynamic_attachment_cache = {}
        self.resolving = set()
        self.dynamic_attachment_resolving = set()
        self.warned_missing_bones = set()

    def _slot_owner_rig_owner_name(self, slot_owner=None):
        if slot_owner and slot_owner in self.slot_owner_rig_owner_names:
            return self.slot_owner_rig_owner_names[slot_owner]
        return ""

    def _binding_data(self, component):
        key = id(component)
        binding = self.binding_cache.get(key, _UNSET)
        if binding is _UNSET:
            binding = resolve_handle_data(
                component, self.parent_transform_lookup, "parentTransform"
            )
            # Disabled bindings resolve the component at the entity root.
            if type(binding) is dict and binding.get("enabled", 1) == 0:
                binding = None
            self.binding_cache[key] = binding
        return binding

    def _local_matrix(self, component):
        key = id(component)
        matrix = self.local_matrix_cache.get(key)
        if matrix is None:
            matrix = self.local_matrix_resolver(component)
            self.local_matrix_cache[key] = matrix
        return matrix

    def _rig_json_has_bone(self, bone_name, rig_j=None):
        target_name = merged_bone_name(bone_name)
        return bool(target_name and target_name in rig_bone_index_for(rig_j))

    def _pose_bone_fallback_armature(self, bone_name, slot_owner=None):
        if not bone_name or bone_name == "None":
            return None
        target_name = merged_bone_name(bone_name)
        owner_name = self._slot_owner_rig_owner_name(slot_owner)
        owner = self.armature_by_component_name.get(owner_name) if owner_name else None
        if armature_has_bone(owner, target_name):
            return owner
        if owner is not self.rig and armature_has_bone(self.rig, target_name):
            return self.rig
        return None

    def _bone_source(self, bone_name, slot_owner=None):
        target_name = merged_bone_name(bone_name)
        cache_key = (target_name, slot_owner)
        cached = self.bone_source_cache.get(cache_key, _UNSET)
        if cached is not _UNSET:
            return cached

        # Bone lookup and model-space accumulation use the completed merged hierarchy.
        if self._rig_json_has_bone(target_name, self.rig_j):
            armature = self.rig if armature_has_bone(self.rig, target_name) else None
            result = (self.rig_j, armature)
        else:
            result = (None, self._pose_bone_fallback_armature(target_name, slot_owner))
        self.bone_source_cache[cache_key] = result
        return result

    def _rig_json_for_bone(self, bone_name, slot_owner=None):
        return self._bone_source(bone_name, slot_owner)[0]

    def _armature_for_owner(self, slot_owner=None):
        owner_name = self._slot_owner_rig_owner_name(slot_owner)
        if owner_name:
            armature = self.armature_by_component_name.get(owner_name)
            if is_live_armature_object(armature):
                return armature
        return self.rig if is_live_armature_object(self.rig) else None

    def _armature_world(self, slot_owner=None):
        armature = self._armature_for_owner(slot_owner)
        return (
            armature.matrix_world.copy() if armature is not None else Matrix.Identity(4)
        )

    def bone_matrix(self, bone_name, slot_owner=None):
        target_name = merged_bone_name(bone_name)
        cache_key = (target_name, slot_owner)
        cached = self.bone_matrix_cache.get(cache_key)
        if cached is not None:
            return cached
        rig_json, armature = self._bone_source(target_name, slot_owner)
        if rig_json is not None:
            armature_world = (
                armature.matrix_world.copy()
                if armature is not None
                else Matrix.Identity(4)
            )
            matrix = armature_world @ rig_json_bone_matrix(
                rig_json, target_name, rig_bone_index_for(rig_json)
            )
        elif armature is not None and armature_has_bone(armature, target_name):
            matrix = armature.matrix_world @ armature.pose.bones[target_name].matrix
        else:
            if (
                target_name
                and target_name != "None"
                and target_name not in self.warned_missing_bones
            ):
                self.warned_missing_bones.add(target_name)
                _LOG.warning(
                    "bone '%s' (MetaRig '%s') not found; resolving at the entity root",
                    bone_name,
                    target_name,
                )
            matrix = self._armature_world(slot_owner)
        self.bone_matrix_cache[cache_key] = matrix
        return matrix

    def resolve_slot_matrix(self, slot_owner, slot_name):
        # Slot transforms are relative to their owning bone.
        cache_key = (slot_owner, slot_name)
        cached = self.slot_matrix_cache.get(cache_key)
        if cached is not None:
            return cached
        slot = self._slot(slot_owner, slot_name)
        if not slot:
            result = (
                self._owner_component_matrix(slot_owner),
                slot_owner,
                slot_name,
                None,
            )
        else:
            source_bone_name = cname_value(slot.get("boneName"), slot_name)
            bone_name = merged_bone_name(source_bone_name)
            result = (
                self.bone_matrix(source_bone_name, slot_owner) @ transform_matrix(slot),
                bone_name,
                slot_name,
                self._attachment_armature(bone_name, slot_owner),
            )
        self.slot_matrix_cache[cache_key] = result
        return result

    def _attachment_armature(self, bone_name, slot_owner=None):
        if not bone_name or bone_name == "None":
            return None
        return self._bone_source(bone_name, slot_owner)[1]

    def _rig_owner_armature(self, component_name_value):
        armature = self.armature_by_component_name.get(component_name_value)
        if is_live_armature_object(armature):
            return armature
        return self._armature_for_owner()

    def _owner_component_matrix(self, owner):
        component = self.components_by_name.get(owner)
        if component is None:
            return Matrix.Identity(4)
        return self.resolve_component_matrix(component)[0]

    def _get_binding_target(self, bind_name):
        # A binding targets a component; slot lookup is performed on that component.
        cached = self.binding_target_cache.get(bind_name)
        if cached is not None:
            return cached
        if not bind_name or bind_name == "None":
            target = "none"
        elif bind_name in self.components_by_name:
            target = "component"
        elif bind_name == "deformation_rig":
            target = "deformation_rig"
        elif bind_name in ("vehicle_slots", "slots"):
            target = "slot"
        elif self._rig_json_for_bone(bind_name) is not None or armature_has_bone(
            self.rig, merged_bone_name(bind_name)
        ):
            target = "bone"
        else:
            target = "unresolved"
        self.binding_target_cache[bind_name] = target
        return target

    def _resolve_parent_target(self, bind_name, slot_name, component=None):
        target_type = self._get_binding_target(bind_name)
        if target_type == "none":
            return Matrix.Identity(4), bind_name, slot_name, "none", None

        if target_type == "deformation_rig":
            armature = self._rig_owner_armature("deformation_rig")
            matrix = (
                armature.matrix_world.copy()
                if armature is not None
                else Matrix.Identity(4)
            )
            return matrix, bind_name, slot_name, "deformation_rig", armature

        if target_type == "bone":
            target_name = merged_bone_name(bind_name)
            return (
                self.bone_matrix(bind_name),
                target_name,
                slot_name,
                "bone",
                self._attachment_armature(bind_name),
            )

        if target_type == "slot":
            matrix, bone_name, resolved_slot, armature = self.resolve_slot_matrix(
                bind_name, slot_name
            )
            return matrix, bone_name, resolved_slot, "slot", armature

        if target_type == "component":
            bound_component = self.components_by_name[bind_name]
            if slot_name and slot_name != "None":
                lookup = self._slot_lookup_for_owner(bind_name)
                if lookup and slot_name in lookup:
                    matrix, bone_name, resolved_slot, armature = (
                        self.resolve_slot_matrix(bind_name, slot_name)
                    )
                    return matrix, bone_name, resolved_slot, "slot", armature
            if (
                component is not None
                and component_uses_skinning(component, self.skinning_lookup)
                and self._component_is_rig_owner(bound_component)
            ):
                armature = self._rig_owner_armature(bind_name)
                matrix = (
                    armature.matrix_world.copy()
                    if armature is not None
                    else Matrix.Identity(4)
                )
                return matrix, bind_name, slot_name, "skinning_root", armature
            parent_matrix, _, _, _, parent_armature = self.resolve_component_matrix(
                bound_component
            )
            return parent_matrix, bind_name, slot_name, "component", parent_armature

        return Matrix.Identity(4), bind_name, slot_name, "unresolved", None

    def parent_component(self, component):
        """The component the parentTransform of component binds it to directly, or None"""
        binding = self._binding_data(component)
        if type(binding) is not dict:
            return None
        return self.components_by_name.get(cname_value(binding.get("bindName")))

    def resolve_binding(self, component):
        binding = self._binding_data(component)
        if type(binding) is not dict:
            # Floating skin targets inherit the transform of their skinning component.
            skin_bind = skinning_bind_name(component, self.skinning_lookup)
            if skin_bind and skin_bind != "None":
                armature = self._rig_owner_armature(skin_bind)
                matrix = (
                    armature.matrix_world.copy()
                    if armature is not None
                    else Matrix.Identity(4)
                )
                return matrix, skin_bind, "", "skinning_root", armature
            return Matrix.Identity(4), "", "", "none", None
        bind_name = cname_value(binding.get("bindName"))
        slot_name = cname_value(binding.get("slotName"))
        return self._resolve_parent_target(bind_name, slot_name, component=component)

    def _root_attachment(self, component, attachment_type):
        """The rig object that a component at the entity root follows"""
        if self._component_is_rig_owner(component):
            return (
                self._rig_owner_armature(component_name(component)),
                "",
                attachment_type,
            )
        return self._armature_for_owner(), "", attachment_type

    def resolve_dynamic_attachment(self, component):
        key = id(component)
        cached = self.dynamic_attachment_cache.get(key, _UNSET)
        if cached is not _UNSET:
            return cached
        if key in self.dynamic_attachment_resolving:
            return None, "", "cycle"

        self.dynamic_attachment_resolving.add(key)
        try:
            binding = self._binding_data(component)
            if type(binding) is not dict:
                skin_bind = skinning_bind_name(component, self.skinning_lookup)
                if skin_bind and skin_bind != "None":
                    result = self._rig_owner_armature(skin_bind), "", "skinning_root"
                else:
                    result = self._root_attachment(component, "none")
            else:
                bind_name = cname_value(binding.get("bindName"))
                slot_name = cname_value(binding.get("slotName"))
                result = self._resolve_dynamic_parent_target(
                    bind_name,
                    slot_name,
                    component=component,
                )
            self.dynamic_attachment_cache[key] = result
            return result
        finally:
            self.dynamic_attachment_resolving.discard(key)

    def _resolve_dynamic_parent_target(self, bind_name, slot_name, component=None):
        target_type = self._get_binding_target(bind_name)
        if target_type in {"none", "unresolved"}:
            return self._root_attachment(component, target_type)

        if target_type == "deformation_rig":
            return self._rig_owner_armature("deformation_rig"), "", target_type

        if target_type == "bone":
            target_name = merged_bone_name(bind_name)
            return self._attachment_armature(target_name), target_name, target_type

        if target_type == "slot":
            _, bone_name, _, armature = self.resolve_slot_matrix(bind_name, slot_name)
            return armature, bone_name, target_type

        bound_component = self.components_by_name[bind_name]
        if slot_name and slot_name != "None":
            lookup = self._slot_lookup_for_owner(bind_name)
            if lookup and slot_name in lookup:
                _, bone_name, _, armature = self.resolve_slot_matrix(
                    bind_name, slot_name
                )
                return armature, bone_name, "slot"

        if (
            component is not None
            and component_uses_skinning(component, self.skinning_lookup)
            and self._component_is_rig_owner(bound_component)
        ):
            return self._rig_owner_armature(bind_name), "", "skinning_root"

        armature, subtarget, inherited_type = self.resolve_dynamic_attachment(
            bound_component
        )
        if armature is None:
            return None, "", "component"
        return armature, subtarget, inherited_type

    def resolve_component_matrix(self, component):
        # Compose bindings as parent times local using the owning armature.
        key = id(component)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        if key in self.resolving:
            return Matrix.Identity(4), "", "", "cycle", None
        self.resolving.add(key)
        try:
            parent_matrix, bind_name, slot_name, binding_type, attach_armature = (
                self.resolve_binding(component)
            )
            matrix = parent_matrix @ self._local_matrix(component)
            skin_placement = self.component_skin_placements.get(key)
            if skin_placement is not None:
                matrix = matrix @ skin_placement
            result = (matrix, bind_name, slot_name, binding_type, attach_armature)
            self.cache[key] = result
            return result
        finally:
            self.resolving.discard(key)

    def _slot_lookup_for_owner(self, owner):
        lookup = self.slot_component_lookups.get(owner)
        if not lookup and owner in ("vehicle_slots", "slots"):
            lookup = self.default_slot_lookup
        return lookup

    def _slot(self, owner, slot_name):
        cache_key = (owner, slot_name)
        if cache_key in self.slot_cache:
            return self.slot_cache[cache_key]
        lookup = self._slot_lookup_for_owner(owner)
        slot = lookup.get(slot_name) if lookup else None
        self.slot_cache[cache_key] = slot
        return slot

    def _component_is_rig_owner(self, component):
        return type(component) is dict and bool(
            depot_path(component, "rig", normalize=False)
        )


def matching_child_of_constraint(obj, target, subtarget):
    for constraint in getattr(obj, "constraints", ()):
        if (
            constraint.type == "CHILD_OF"
            and constraint.target == target
            and constraint.subtarget == subtarget
        ):
            return constraint
    return None


def configure_child_of_constraint(obj, target, subtarget):
    constraints = obj.constraints
    constraint = matching_child_of_constraint(obj, target, subtarget)
    if constraint is None:
        constraint = constraints.get("Child Of")
        if constraint is None or constraint.type != "CHILD_OF":
            constraint = constraints.new(type="CHILD_OF")
            constraint.name = "Child Of"
    expected_world = obj.matrix_world.copy()
    constraint.target = target
    constraint.subtarget = subtarget
    constraint.set_inverse_pending = True
    constraint_index = next(
        (
            index
            for index, candidate in enumerate(constraints)
            if candidate is constraint
        ),
        -1,
    )
    if constraint_index >= 0:
        request_child_of_inverse(obj, constraint_index, expected_world)
    return constraint


def request_child_of_inverse(obj, constraint_index, expected_world):
    """Have the next flush evaluate a pending Child Of constraint of obj"""
    _PENDING_CHILD_OF_INVERSES[(id(obj), constraint_index)] = (
        obj,
        constraint_index,
        expected_world,
    )


def clear_pending_child_of_inverse_requests():
    _PENDING_CHILD_OF_INVERSES.clear()


def pending_child_of_inverse_count():
    return len(_PENDING_CHILD_OF_INVERSES)


def flush_pending_child_of_inverse_requests():
    requested = len(_PENDING_CHILD_OF_INVERSES)
    if not requested:
        return {
            "requested": 0,
            "pending": 0,
            "mismatches": 0,
            "max_translation_error": 0.0,
            "max_basis_error": 0.0,
        }

    bpy.context.view_layer.update()
    pending = 0
    mismatches = 0
    max_translation_error = 0.0
    max_basis_error = 0.0
    examples = []
    for obj, constraint_index, expected_world in tuple(
        _PENDING_CHILD_OF_INVERSES.values()
    ):
        try:
            if constraint_index >= len(obj.constraints):
                continue
            constraint = obj.constraints[constraint_index]
            if constraint.type != "CHILD_OF":
                continue
            if constraint.set_inverse_pending:
                pending += 1
            translation_error = float(
                (obj.matrix_world.translation - expected_world.translation).length
            )
            basis_error = max(
                abs(float(obj.matrix_world[row][column] - expected_world[row][column]))
                for row in range(3)
                for column in range(3)
            )
            max_translation_error = max(max_translation_error, translation_error)
            max_basis_error = max(max_basis_error, basis_error)
            if translation_error > 1.0e-3 or basis_error > 1.0e-4:
                mismatches += 1
                if len(examples) < 8:
                    examples.append(obj.name)
        except (
            AttributeError,
            ReferenceError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("flush_pending_child_of_inverse_requests", type(error).__name__),
                "flush pending child of inverse requests: fell back after %s",
                error,
                exc_info=True,
            )
            continue
    _PENDING_CHILD_OF_INVERSES.clear()
    return {
        "requested": requested,
        "pending": pending,
        "mismatches": mismatches,
        "max_translation_error": max_translation_error,
        "max_basis_error": max_basis_error,
        "examples": tuple(examples),
    }
