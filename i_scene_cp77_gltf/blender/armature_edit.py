import json
import time
from contextvars import ContextVar
from functools import wraps
from itertools import count

import bpy

from .transactions import (
    current_import_transaction,
    restore_id_properties,
    snapshot_id_properties,
    track_created_datablock,
)

_STAGED = ContextVar("cp77_staged_armatures", default=frozenset())
_EDIT_SESSION_IDS = count(1)


class ArmatureEditSession:
    """Build bones in an isolated window scene and restore the original scene explicitly"""

    def __init__(self, armature):
        self.armature = armature
        self.scene = None
        self.window = None
        self.original_scene = None
        self.original_view_layer = None
        self.original_visibility = None
        self.timings = {"enter": 0.0, "exit": 0.0}

    def __enter__(self):
        self.window = bpy.context.window
        if self.window is None:
            raise RuntimeError(
                "Armature construction requires a Blender window context."
            )
        self.original_scene = self.window.scene
        self.original_view_layer = self.window.view_layer
        self.original_visibility = (
            self.armature.hide_viewport,
            self.armature.hide_select,
        )
        self.scene = track_created_datablock(
            "scenes",
            bpy.data.scenes.new(f"__CP77_RIG_BUILD_{next(_EDIT_SESSION_IDS):06d}__"),
        )
        try:
            self.scene.collection.objects.link(self.armature)
            self.window.scene = self.scene
            self.window.view_layer = self.scene.view_layers[0]
            self.armature.hide_viewport = False
            self.armature.hide_select = False
            self.armature.select_set(True)
            self.window.view_layer.objects.active = self.armature
            started = time.perf_counter()
            if (
                bpy.context.active_object != self.armature
                or not bpy.ops.object.mode_set.poll()
            ):
                raise RuntimeError(
                    f"Unable to edit armature {self.armature.name!r} in its build scene."
                )
            bpy.ops.object.mode_set(mode="EDIT")
            self.timings["enter"] = time.perf_counter() - started
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self.timings

    def __exit__(self, exc_type, exc_value, traceback):
        if self.scene is None:
            return False
        try:
            started = time.perf_counter()
            if self.armature.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            self.timings["exit"] = time.perf_counter() - started
        finally:
            try:
                self.window.scene = self.original_scene
                self.window.view_layer = self.original_view_layer
            finally:
                try:
                    self.armature.hide_viewport, self.armature.hide_select = (
                        self.original_visibility
                    )
                finally:
                    if self.armature.name in self.scene.collection.objects:
                        self.scene.collection.objects.unlink(self.armature)
                    bpy.data.scenes.remove(self.scene)
                    self.scene = None
        return False


def _restore_properties(owner, values):
    for key in tuple(owner.keys()):
        if key not in values:
            del owner[key]
    for key, value in values.items():
        owner[key] = value


def _copy_property_ui(source, target, key):
    try:
        target.id_properties_ui(key).update(**source.id_properties_ui(key).as_dict())
    except TypeError:
        # String and group properties may not provide numeric UI metadata.
        pass
    path = "[" + json.dumps(key) + "]"
    if source.is_property_overridable_library(path):
        target.property_overridable_library_set(path, True)


def assembly_name(target):
    return str(target.get("_cp77_assembly_name", target.name))


def _rna_values(owner, *, exclude=()):
    values = {}
    for prop in owner.bl_rna.properties:
        name = prop.identifier
        if prop.is_readonly or name in exclude or prop.type == "COLLECTION":
            continue
        value = getattr(owner, name)
        if getattr(prop, "is_array", False):
            value = value.copy() if hasattr(value, "copy") else tuple(value)
        elif isinstance(value, set):
            value = set(value)
        if isinstance(value, bpy.types.PoseBone):
            value = ("__pose_bone__", value.name)
        values[name] = value
    return values


def capture_constraint(constraint):
    """RNA settings of a constraint and of its targets, in the form recreate_constraint() takes"""
    return (
        constraint.type,
        _rna_values(constraint),
        tuple(_rna_values(item) for item in getattr(constraint, "targets", ())),
    )


def _assign(target, owner, values):
    for name, value in values.items():
        if isinstance(value, tuple) and len(value) == 2 and value[0] == "__pose_bone__":
            value = target.pose.bones.get(value[1])
        setattr(owner, name, value)


def recreate_constraint(target, constraints, state):
    """Add a constraint to a stack of target's pose from a capture_constraint() state"""
    kind, properties, targets = state
    constraint = constraints.new(kind)
    _assign(target, constraint, properties)
    for item in targets:
        _assign(target, constraint.targets.new(), item)
    return constraint


def _pose_state(target):
    return {
        bone.name: (
            _rna_values(bone, exclude={"name", "matrix", "matrix_basis"}),
            bone.matrix_basis.copy(),
            snapshot_id_properties(bone),
            tuple(capture_constraint(constraint) for constraint in bone.constraints),
        )
        for bone in target.pose.bones
    }


def _restore_pose(target, snapshot):
    for name, (values, basis, properties, constraints) in snapshot.items():
        bone = target.pose.bones.get(name)
        if bone is None:
            raise RuntimeError(f"Rollback could not restore pose bone {name!r}")
        _assign(target, bone, values)
        bone.matrix_basis = basis
        restore_id_properties(bone, properties)
        for constraint in tuple(bone.constraints):
            bone.constraints.remove(constraint)
        for state in constraints:
            recreate_constraint(target, bone.constraints, state)


def _check_dependencies(target, removed):
    if not removed:
        return
    for obj in bpy.data.objects:
        if (
            obj.parent == target
            and obj.parent_type == "BONE"
            and obj.parent_bone in removed
        ):
            raise ValueError(
                f"Detach bone-parented object {obj.name!r} before removing its rig part"
            )
        owners = [obj]
        if obj.type == "ARMATURE":
            owners.extend(
                bone
                for bone in obj.pose.bones
                if obj != target or bone.name not in removed
            )
        for owner in owners:
            for constraint in owner.constraints:
                if (
                    getattr(constraint, "target", None) == target
                    and getattr(constraint, "subtarget", "") in removed
                ):
                    raise ValueError(
                        f"Constraint {constraint.name!r} still uses a removed bone"
                    )
                for item in getattr(constraint, "targets", ()):
                    if item.target == target and item.subtarget in removed:
                        raise ValueError(
                            f"Constraint {constraint.name!r} still uses a removed bone"
                        )


def atomic_armature_update(function):
    @wraps(function)
    def update(target, *args, **kwargs):
        if target.as_pointer() in _STAGED.get():
            return function(target, *args, **kwargs)
        if target.type != "ARMATURE" or target.mode != "OBJECT":
            raise ValueError("Rig assembly changes require an armature in Object Mode")
        if target.library or target.override_library or target.data.library:
            raise ValueError("Make the rig local before changing its assembly")
        staged = None
        staged_data = None
        original_data = target.data
        original_name = original_data.name
        properties = snapshot_id_properties(target)
        token = None
        committed = False
        try:
            staged = target.copy()
            staged_data = original_data.copy()
            staged.data = staged_data
            staged["_cp77_assembly_name"] = target.name
            token = _STAGED.set(_STAGED.get() | {staged.as_pointer()})
            result = function(staged, *args, **kwargs)
            removed = set(original_data.bones.keys()) - set(staged_data.bones.keys())
            _check_dependencies(target, removed)
            del staged["_cp77_assembly_name"]
            transaction = current_import_transaction()

            def cleanup_original():
                try:
                    if original_data.users == 0:
                        bpy.data.armatures.remove(original_data)
                        staged_data.name = original_name
                except (ReferenceError, RuntimeError):
                    pass

            if transaction is not None:
                pose_state = _pose_state(target)

                def restore():
                    target.data = original_data
                    _restore_properties(target, properties)
                    _restore_pose(target, pose_state)

                transaction.track_mutation(
                    (
                        "armature_assembly",
                        target.as_pointer(),
                        original_data.as_pointer(),
                    ),
                    restore,
                    label=f"rig assembly {target.name}",
                )
                transaction.defer_commit_cleanup(cleanup_original)
            # Commit properties first; a failed assignment cannot destroy pose channels.
            for key in tuple(target.keys()):
                if key not in staged:
                    del target[key]
            for key, value in snapshot_id_properties(staged).items():
                target[key] = value
                if key not in properties:
                    _copy_property_ui(staged, target, key)
            target.data = staged_data
            committed = True
            track_created_datablock("armatures", staged_data)
            if transaction is None:
                cleanup_original()
            return target if result is staged else result
        except Exception:
            if not committed:
                _restore_properties(target, properties)
            raise
        finally:
            if token is not None:
                _STAGED.reset(token)
            if staged is not None:
                bpy.data.objects.remove(staged, do_unlink=True)
            if staged_data is not None and staged_data.users == 0:
                bpy.data.armatures.remove(staged_data)

    return update
