from __future__ import annotations
<<<<<<< Updated upstream
from ....blender.transactions import track_created_datablock

import traceback
from dataclasses import dataclass
from typing import Any, Callable

import bpy

from ...common.entity_data import component_name
from ..policy import (
    APPEARANCE_PROXY_COMPONENT_TYPES,
    MESH_COMPONENT_TYPES,
    STATIC_MESH_COMPONENT_TYPES,
    STATIC_OCCLUDER_COMPONENT_TYPES,
)


@dataclass(frozen=True, slots=True)
class EntityStaticMeshOperations:
    """Shared operations required by the static-mesh service."""

    component_mesh_info: Callable[[dict], tuple]
    master_group_objects: Callable[[Any], tuple]
=======

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import bpy

from ....blender.transactions import track_created_datablock
from ....core.log import get_logger
from ...common.entity_data import component_name
from ..placement_metadata import store_mesh_placement
from ..policy import (
    APPEARANCE_PROXY_COMPONENT_TYPES,
    MESH_COMPONENT_TYPES,
    STATIC_OCCLUDER_COMPONENT_TYPES,
)

_LOG = get_logger(__name__)


def _copy_master_collection(
    group_name,
    source_objects,
    *,
    component_name_value,
    mesh_path,
    mesh_appearance,
    component_enabled,
    remap_references,
):
    collection = track_created_datablock(
        "collections",
        bpy.data.collections.new(group_name),
    )
    copied_objects = []
    object_copy_map = {}
    link_object = collection.objects.link
    hide_disabled = not component_enabled
    for source in source_objects:
        obj = track_created_datablock("objects", source.copy())
        object_copy_map[source] = obj
        copied_objects.append(obj)
        link_object(obj)
        obj["componentName"] = component_name_value
        obj["sourcePath"] = mesh_path
        obj["meshAppearance"] = mesh_appearance
        obj["cp77_component_enabled"] = component_enabled
        if hide_disabled:
            obj.hide_viewport = True
            obj.hide_render = True
        if obj.type == "ARMATURE":
            obj.hide_viewport = True
    remap_references(copied_objects, object_copy_map)
    return collection, copied_objects


@dataclass(frozen=True, slots=True)
class EntityStaticMeshOperations:
    """Shared operations required by the static-mesh service"""

    component_mesh_info: Callable[[dict], tuple]
    resolve_master_group: Callable[..., tuple]
    master_group_plan: Callable[..., Any]
    master_group_submesh_indexes: Callable[..., tuple]
>>>>>>> Stashed changes
    get_group: Callable[..., tuple]
    is_excluded_mesh: Callable[[str, str, str, set[str]], bool]
    remap_copied_object_references: Callable[[list[Any], dict[Any, Any]], None]
    component_is_zero_mask_culled: Callable[[dict], bool]
    chunk_mask_value: Callable[[dict], int | None]
    submesh_index_for_object: Callable[[Any], int | None]
    visual_scale_matrix: Callable[[dict], Any]
<<<<<<< Updated upstream
    child_of_inverse_matrix: Callable[[Any, str], Any]
    configure_child_of_constraint: Callable[[Any, Any, str, Any], Any]


class EntityStaticMeshService:
    """Execute non-skinned mesh components for one entity appearance."""

    __slots__ = (
        "entity_collection",
        "appearance_name",
        "app_resource",
        "masters",
        "excluded_meshes",
        "transform_resolver",
        "transform_animators",
        "operations",
        "warnings",
        "last_skip_reason",
=======
    configure_child_of_constraint: Callable[[Any, Any, str], Any]


class _EntityMeshServiceBase:
    __slots__ = ()

    def _skip(self, reason, message=""):
        self.last_skip_reason = reason
        if message and message not in self.warnings:
            self.warnings.append(message)


class EntityStaticMeshService(_EntityMeshServiceBase):
    """Execute non-skinned mesh components for one entity appearance"""

    __slots__ = (
        "appearance_name",
        "entity_collection",
        "excluded_meshes",
        "last_skip_reason",
        "masters",
        "operations",
        "transform_animators",
        "transform_resolver",
        "warnings",
>>>>>>> Stashed changes
    )

    def __init__(
        self,
        *,
        entity_collection,
        appearance_name,
<<<<<<< Updated upstream
        app_resource,
=======
>>>>>>> Stashed changes
        masters,
        excluded_meshes,
        transform_resolver,
        transform_animators,
        operations: EntityStaticMeshOperations,
        warnings: list[str],
    ):
        self.entity_collection = entity_collection
        self.appearance_name = appearance_name
<<<<<<< Updated upstream
        self.app_resource = app_resource
=======
>>>>>>> Stashed changes
        self.masters = masters
        self.excluded_meshes = excluded_meshes
        self.transform_resolver = transform_resolver
        self.transform_animators = transform_animators
        self.operations = operations
        self.warnings = warnings
        self.last_skip_reason = ""

<<<<<<< Updated upstream
    def _skip(self, reason, message=""):
        self.last_skip_reason = reason
        if message and message not in self.warnings:
            self.warnings.append(message)
        return None

=======
>>>>>>> Stashed changes
    def execute(self, component):
        self.last_skip_reason = ""
        operations = self.operations
        if operations.component_is_zero_mask_culled(component):
            return self._skip("zero_chunk_mask")

        comp_name = component_name(component)
        depot_path, meshname, meshpath, mesh_appearance, component_enabled = (
            operations.component_mesh_info(component)
        )
        if not meshname or not meshpath:
            return self._skip("missing_mesh_resource")
        if operations.is_excluded_mesh(
            depot_path,
            meshpath,
            meshname,
            self.excluded_meshes,
        ):
            return self._skip("excluded_mesh")

        new = None
        hide_disabled = not component_enabled
        try:
<<<<<<< Updated upstream
            group, group_name = operations.get_group(
                meshpath,
                mesh_appearance,
                self.masters,
                source_glb=meshpath,
            )
            copied_objects = []
            if group:
                new = track_created_datablock("collections", bpy.data.collections.new(group_name))
                object_copy_map = {}
                link_object = new.objects.link
                for old_obj in operations.master_group_objects(group):
                    obj = track_created_datablock("objects", old_obj.copy())
                    object_copy_map[old_obj] = obj
                    copied_objects.append(obj)
                    link_object(obj)
                    obj['componentName'] = comp_name
                    obj['sourcePath'] = meshpath
                    obj['meshAppearance'] = mesh_appearance
                    obj['componentEnabled'] = component_enabled
                    if self.app_resource:
                        obj['appResource'] = self.app_resource
                    obj['entAppearance'] = self.appearance_name
                    if hide_disabled:
                        obj.hide_viewport = True
                        obj.hide_render = True
                    if 'Armature' in obj.name:
                        obj.hide_viewport = True
                operations.remap_copied_object_references(
                    copied_objects,
                    object_copy_map,
                )
            if new is None:
                print('collection not found after import - ', meshname)
=======
            group, group_name = operations.resolve_master_group(
                meshpath,
                mesh_appearance,
                self.masters,
                operations.get_group,
            )
            copied_objects = []
            copied_root_flags = ()
            copied_submesh_indexes = ()
            resource_matrices = ()
            if group:
                plan = operations.master_group_plan(group)
                copied_root_flags = plan.root_flags
                resource_matrices = plan.resource_matrices
                new, copied_objects = _copy_master_collection(
                    group_name,
                    plan.objects,
                    component_name_value=comp_name,
                    mesh_path=meshpath,
                    mesh_appearance=mesh_appearance,
                    component_enabled=component_enabled,
                    remap_references=operations.remap_copied_object_references,
                )
            if new is None:
                _LOG.error(
                    "Entity mesh master collection not found after import: %s", meshname
                )
>>>>>>> Stashed changes
                return self._skip(
                    "master_collection_missing",
                    f"Entity mesh master not found for {comp_name}: {meshpath}",
                )

<<<<<<< Updated upstream
            resolved_matrix, bind_name, slot_name, binding_type, attach_armature = (
=======
            resolved_matrix, bind_name, slot_name, binding_type, _ = (
>>>>>>> Stashed changes
                self.transform_resolver.resolve_component_matrix(component)
            )
            component_scale = operations.visual_scale_matrix(component)
            if component_scale is not None:
                resolved_matrix = resolved_matrix @ component_scale

<<<<<<< Updated upstream
            can_bind_bone = (
                binding_type in {'slot', 'bone'}
                and bind_name
                and attach_armature is not None
            )
            child_inverse = (
                operations.child_of_inverse_matrix(attach_armature, bind_name)
                if can_bind_bone
                else None
            )
            animator_target, animator_info = self.transform_animators.target_for_component(
                component
            )
            has_bind_name = bool(bind_name)
            has_slot_name = bool(slot_name)
            chunk_mask = operations.chunk_mask_value(component)
            copied_object_set = set(copied_objects)

            for obj in copied_objects:
                obj['bindingType'] = binding_type
                if has_bind_name:
                    obj['bindname'] = bind_name
                if has_slot_name:
                    obj['slotName'] = slot_name
                obj['deformationRigSkinning'] = False

                if chunk_mask is not None:
                    submesh_index = operations.submesh_index_for_object(obj)
=======
            attachment_target, attachment_subtarget, _attachment_type = (
                self.transform_resolver.resolve_dynamic_attachment(component)
            )
            can_bind_live = attachment_target is not None
            animator_target = self.transform_animators.target_for_component(component)
            has_bind_name = bool(bind_name)
            has_slot_name = bool(slot_name)
            chunk_mask = operations.chunk_mask_value(component)
            if chunk_mask is not None:
                copied_submesh_indexes = operations.master_group_submesh_indexes(
                    group,
                    operations.submesh_index_for_object,
                )
            else:
                copied_submesh_indexes = (None,) * len(copied_objects)
            for obj, is_root, submesh_index, resource_matrix in zip(
                copied_objects,
                copied_root_flags,
                copied_submesh_indexes,
                resource_matrices,
            ):
                store_mesh_placement(obj, resolved_matrix, resource_matrix)
                obj["cp77_binding_type"] = binding_type
                if has_bind_name:
                    obj["bindname"] = bind_name
                if has_slot_name:
                    obj["slotName"] = slot_name

                if chunk_mask is not None:
>>>>>>> Stashed changes
                    if submesh_index is not None:
                        hidden = hide_disabled or not bool(
                            (chunk_mask >> submesh_index) & 1
                        )
                        obj.hide_viewport = hidden
                        obj.hide_render = hidden
                elif hide_disabled:
                    obj.hide_viewport = True
                    obj.hide_render = True

<<<<<<< Updated upstream
                if obj.parent in copied_object_set:
                    # Children inherit the copied parent transform.
                    continue

                obj.matrix_world = resolved_matrix @ obj.matrix_world
                if can_bind_bone:
                    operations.configure_child_of_constraint(
                        obj,
                        attach_armature,
                        bind_name,
                        child_inverse,
                    )
                if animator_target is not None:
                    self.transform_animators.add_driver(
                        obj,
                        animator_target,
                        animator_info,
                    )

            if copied_objects:
                new['depotPath'] = depot_path
                new['meshAppearance'] = mesh_appearance
                new['meshpath'] = 'its an entity'
                if bind_name:
                    new['bindname'] = bind_name
=======
                if not is_root:
                    continue

                obj.matrix_world = resolved_matrix @ resource_matrix
                if can_bind_live and animator_target is None:
                    operations.configure_child_of_constraint(
                        obj,
                        attachment_target,
                        attachment_subtarget,
                    )
                if animator_target is not None:
                    self.transform_animators.add_binding(obj, animator_target)

            if copied_objects:
                new["meshPath"] = depot_path
                new["meshAppearance"] = mesh_appearance
                new["sourcePath"] = meshpath
                if bind_name:
                    new["bindname"] = bind_name
>>>>>>> Stashed changes

            self.entity_collection.children.link(new)
            return new

        except Exception as error:
<<<<<<< Updated upstream
            print('Failed on ', meshname)
            print(traceback.format_exc())
            if new is not None and self.entity_collection.children.get(new.name) is None:
                for obj in list(new.objects):
                    bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.collections.remove(new, do_unlink=True)
            return self._skip(
                "execution_error",
                f"Entity mesh component failed for {comp_name} ({meshpath}): "
                f"{type(error).__name__}: {error}",
            )


class EntityStaticMeshHandler:
    component_types = STATIC_MESH_COMPONENT_TYPES

    def execute(self, component, context):
        return context.static_meshes.execute(component)
=======
            error.add_note(f"While importing entity mesh {meshname} ({meshpath})")
            raise
>>>>>>> Stashed changes


@dataclass(frozen=True, slots=True)
class EntitySkinnedMeshOperations:
<<<<<<< Updated upstream
    """Legacy operations required by the extracted skinned-mesh service."""

    component_mesh_info: Callable[[dict], tuple]
    master_group_objects: Callable[[Any], tuple]
=======
    """Operations required by the skinned-mesh service"""

    component_mesh_info: Callable[[dict], tuple]
    resolve_master_group: Callable[..., tuple]
    master_group_plan: Callable[..., Any]
    master_group_submesh_indexes: Callable[..., tuple]
>>>>>>> Stashed changes
    get_group: Callable[..., tuple]
    is_excluded_mesh: Callable[[str, str, str, set[str]], bool]
    remap_copied_object_references: Callable[[list[Any], dict[Any, Any]], None]
    component_is_zero_mask_culled: Callable[[dict], bool]
    chunk_mask_value: Callable[[dict], int | None]
    submesh_index_for_object: Callable[[Any], int | None]
    visual_scale_matrix: Callable[[dict], Any]
    bind_skinned_objects_to_rig: Callable[[list[Any], Any], None]


<<<<<<< Updated upstream
class EntitySkinnedMeshService:
    """Execute components whose resolved skinning binding is active."""

    __slots__ = (
        "entity_collection",
        "appearance_name",
        "app_resource",
        "masters",
        "excluded_meshes",
        "transform_resolver",
        "transform_animators",
        "rig",
        "component_skin_placement_info",
        "operations",
        "warnings",
        "last_skip_reason",
=======
class EntitySkinnedMeshService(_EntityMeshServiceBase):
    """Execute components whose resolved skinning binding is active"""

    __slots__ = (
        "appearance_name",
        "component_skin_placement_info",
        "entity_collection",
        "excluded_meshes",
        "last_skip_reason",
        "masters",
        "operations",
        "rig",
        "transform_animators",
        "transform_resolver",
        "warnings",
>>>>>>> Stashed changes
    )

    def __init__(
        self,
        *,
        entity_collection,
        appearance_name,
<<<<<<< Updated upstream
        app_resource,
=======
>>>>>>> Stashed changes
        masters,
        excluded_meshes,
        transform_resolver,
        transform_animators,
        rig,
        component_skin_placement_info,
        operations: EntitySkinnedMeshOperations,
        warnings: list[str],
    ):
        self.entity_collection = entity_collection
        self.appearance_name = appearance_name
<<<<<<< Updated upstream
        self.app_resource = app_resource
=======
>>>>>>> Stashed changes
        self.masters = masters
        self.excluded_meshes = excluded_meshes
        self.transform_resolver = transform_resolver
        self.transform_animators = transform_animators
        self.rig = rig
        self.component_skin_placement_info = component_skin_placement_info
        self.operations = operations
        self.warnings = warnings
        self.last_skip_reason = ""

<<<<<<< Updated upstream
    def _skip(self, reason, message=""):
        self.last_skip_reason = reason
        if message and message not in self.warnings:
            self.warnings.append(message)
        return None

=======
>>>>>>> Stashed changes
    def execute(self, component):
        self.last_skip_reason = ""
        operations = self.operations
        if operations.component_is_zero_mask_culled(component):
            return self._skip("zero_chunk_mask")

        comp_name = component_name(component)
        depot_path, meshname, meshpath, mesh_appearance, component_enabled = (
            operations.component_mesh_info(component)
        )
        if not meshname or not meshpath:
            return self._skip("missing_mesh_resource")
        if operations.is_excluded_mesh(
            depot_path,
            meshpath,
            meshname,
            self.excluded_meshes,
        ):
            return self._skip("excluded_mesh")

        new = None
        hide_disabled = not component_enabled
        try:
<<<<<<< Updated upstream
            group, group_name = operations.get_group(
                meshpath,
                mesh_appearance,
                self.masters,
                source_glb=meshpath,
            )
            copied_objects = []
            if group:
                new = track_created_datablock("collections", bpy.data.collections.new(group_name))
                object_copy_map = {}
                link_object = new.objects.link
                for old_obj in operations.master_group_objects(group):
                    # Copied meshes retarget to the final MetaRig.
                    if getattr(old_obj, "type", None) == "ARMATURE":
                        continue
                    obj = track_created_datablock("objects", old_obj.copy())
                    object_copy_map[old_obj] = obj
                    copied_objects.append(obj)
                    link_object(obj)
                    obj['componentName'] = comp_name
                    obj['sourcePath'] = meshpath
                    obj['meshAppearance'] = mesh_appearance
                    obj['componentEnabled'] = component_enabled
                    if self.app_resource:
                        obj['appResource'] = self.app_resource
                    obj['entAppearance'] = self.appearance_name
                    if hide_disabled:
                        obj.hide_viewport = True
                        obj.hide_render = True
                    if 'Armature' in obj.name:
                        obj.hide_viewport = True
                operations.remap_copied_object_references(
                    copied_objects,
                    object_copy_map,
                )
            if new is None:
                print('collection not found after import - ', meshname)
                return self._skip(
                    "master_collection_missing",
                    f"Entity skinned-mesh master not found for "
                    f"{comp_name}: {meshpath}",
=======
            group, group_name = operations.resolve_master_group(
                meshpath,
                mesh_appearance,
                self.masters,
                operations.get_group,
            )
            copied_objects = []
            copied_root_flags = ()
            copied_submesh_indexes = ()
            resource_matrices = ()
            if group:
                plan = operations.master_group_plan(group)
                copied_root_flags = plan.non_armature_root_flags
                resource_matrices = plan.non_armature_resource_matrices
                new, copied_objects = _copy_master_collection(
                    group_name,
                    plan.non_armature_objects,
                    component_name_value=comp_name,
                    mesh_path=meshpath,
                    mesh_appearance=mesh_appearance,
                    component_enabled=component_enabled,
                    remap_references=operations.remap_copied_object_references,
                )
            if new is None:
                _LOG.error(
                    "Entity mesh master collection not found after import: %s", meshname
                )
                return self._skip(
                    "master_collection_missing",
                    f"Entity skinned-mesh master not found for {comp_name}: {meshpath}",
>>>>>>> Stashed changes
                )

            resolved_matrix, bind_name, slot_name, binding_type, _attach_armature = (
                self.transform_resolver.resolve_component_matrix(component)
            )
<<<<<<< Updated upstream
            skin_root_bone, skin_attachment_status = (
                self.component_skin_placement_info.get(
                    id(component),
                    ('', 'not_applicable'),
                )
=======
            skin_root_bone, _skin_status = self.component_skin_placement_info.get(
                id(component),
                ("", "not_applicable"),
>>>>>>> Stashed changes
            )
            component_scale = operations.visual_scale_matrix(component)
            if component_scale is not None:
                resolved_matrix = resolved_matrix @ component_scale

<<<<<<< Updated upstream
            animator_target, animator_info = self.transform_animators.target_for_component(
                component
            )
            has_bind_name = bool(bind_name)
            has_slot_name = bool(slot_name)
            chunk_mask = operations.chunk_mask_value(component)
            copied_object_set = set(copied_objects)

            for obj in copied_objects:
                obj['bindingType'] = binding_type
                if has_bind_name:
                    obj['bindname'] = bind_name
                if has_slot_name:
                    obj['slotName'] = slot_name
                obj['deformationRigSkinning'] = True
                obj['skinAttachmentStatus'] = skin_attachment_status
                if skin_root_bone:
                    obj['skinAttachmentRootBone'] = skin_root_bone

                if chunk_mask is not None:
                    submesh_index = operations.submesh_index_for_object(obj)
=======
            animator_target = self.transform_animators.target_for_component(component)
            has_bind_name = bool(bind_name)
            has_slot_name = bool(slot_name)
            chunk_mask = operations.chunk_mask_value(component)
            if chunk_mask is not None:
                copied_submesh_indexes = operations.master_group_submesh_indexes(
                    group,
                    operations.submesh_index_for_object,
                    exclude_armatures=True,
                )
            else:
                copied_submesh_indexes = (None,) * len(copied_objects)
            for obj, is_root, submesh_index, resource_matrix in zip(
                copied_objects,
                copied_root_flags,
                copied_submesh_indexes,
                resource_matrices,
            ):
                store_mesh_placement(obj, resolved_matrix, resource_matrix)
                obj["cp77_binding_type"] = binding_type
                if has_bind_name:
                    obj["bindname"] = bind_name
                if has_slot_name:
                    obj["slotName"] = slot_name
                if skin_root_bone:
                    obj["cp77_skin_attachment_root_bone"] = skin_root_bone

                if chunk_mask is not None:
>>>>>>> Stashed changes
                    if submesh_index is not None:
                        hidden = hide_disabled or not bool(
                            (chunk_mask >> submesh_index) & 1
                        )
                        obj.hide_viewport = hidden
                        obj.hide_render = hidden
                elif hide_disabled:
                    obj.hide_viewport = True
                    obj.hide_render = True

<<<<<<< Updated upstream
                if obj.parent in copied_object_set:
                    # Children inherit the copied parent transform.
                    continue

                obj.matrix_world = resolved_matrix @ obj.matrix_world
                if animator_target is not None:
                    self.transform_animators.add_driver(
                        obj,
                        animator_target,
                        animator_info,
                    )
=======
                if not is_root:
                    continue

                obj.matrix_world = resolved_matrix @ resource_matrix
                if animator_target is not None:
                    self.transform_animators.add_binding(obj, animator_target)
>>>>>>> Stashed changes

            operations.bind_skinned_objects_to_rig(copied_objects, self.rig)

            if copied_objects:
<<<<<<< Updated upstream
                new['depotPath'] = depot_path
                new['meshAppearance'] = mesh_appearance
                new['meshpath'] = 'its an entity'
                if bind_name:
                    new['bindname'] = bind_name
=======
                new["meshPath"] = depot_path
                new["meshAppearance"] = mesh_appearance
                new["sourcePath"] = meshpath
                if bind_name:
                    new["bindname"] = bind_name
>>>>>>> Stashed changes

            self.entity_collection.children.link(new)
            return new

        except Exception as error:
<<<<<<< Updated upstream
            print('Failed on ', meshname)
            print(traceback.format_exc())
            if new is not None and self.entity_collection.children.get(new.name) is None:
                for obj in list(new.objects):
                    bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.collections.remove(new, do_unlink=True)
            return self._skip(
                "execution_error",
                f"Entity skinned-mesh component failed for "
                f"{comp_name} ({meshpath}): "
                f"{type(error).__name__}: {error}",
            )


class EntityMeshService:
    """Route mesh components while enforcing optional component policies."""

    __slots__ = (
        "static",
        "skinned",
        "uses_skinning",
=======
            error.add_note(
                f"While importing entity skinned mesh {meshname} ({meshpath})"
            )
            raise


class EntityMeshService:
    """Route mesh components while enforcing optional component policies"""

    __slots__ = (
>>>>>>> Stashed changes
        "include_occluders",
        "include_proxies",
        "last_route",
        "last_skip_reason",
<<<<<<< Updated upstream
=======
        "skinned",
        "static",
        "uses_skinning",
>>>>>>> Stashed changes
    )

    def __init__(
        self,
        static,
        skinned,
        uses_skinning,
        *,
        include_occluders=False,
        include_proxies=False,
    ):
        self.static = static
        self.skinned = skinned
        self.uses_skinning = uses_skinning
        self.include_occluders = bool(include_occluders)
        self.include_proxies = bool(include_proxies)
        self.last_route = ""
        self.last_skip_reason = ""

    def execute(self, component):
        self.last_route = ""
        self.last_skip_reason = ""
        component_type = component.get("$type") if isinstance(component, dict) else ""
        if (
            component_type in STATIC_OCCLUDER_COMPONENT_TYPES
            and not self.include_occluders
        ):
            self.last_route = "static"
            self.last_skip_reason = "occluders_disabled"
            return None
        if (
            component_type in APPEARANCE_PROXY_COMPONENT_TYPES
            and not self.include_proxies
        ):
            self.last_route = "static"
            self.last_skip_reason = "appearance_proxies_disabled"
            return None

        service = self.skinned if self.uses_skinning(component) else self.static
        self.last_route = "skinned" if service is self.skinned else "static"
        result = service.execute(component)
        self.last_skip_reason = getattr(service, "last_skip_reason", "")
        return result


class EntityMeshHandler:
    component_types = MESH_COMPONENT_TYPES

    def execute(self, component, context):
        return context.meshes.execute(component)
