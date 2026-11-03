import bpy

from ....blender.animgraph import builder
from ....animation.animgraph.schema import rtti
from ....animation.animgraph_constants import ANIMGRAPH_TREE_ID
from ....blender.animgraph.categories import (
    BLEND_TYPES, BONE_TYPES, CLIP_TYPES, CONTAINER_TYPES,
    PHYSICS_TYPES, POSESPACE_TYPES, TERMINATOR_TYPES,
)


class REDENGINE_OT_add_node(bpy.types.Operator):
    bl_idname = "redengine.add_node"
    bl_label = "Add AnimGraph Node"
    bl_options = {'REGISTER', 'UNDO'}

    node_type: bpy.props.StringProperty(
        name="Node Type",
        description="REDengine node $type without the animAnimNode_ prefix",
    )

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == 'NODE_EDITOR'
            and space.edit_tree is not None
            and space.edit_tree.bl_idname == ANIMGRAPH_TREE_ID
        )

    def invoke(self, context, event):
        self._cursor = context.space_data.cursor_location.copy()
        return self.execute(context)

    def execute(self, context):
        tree = context.space_data.edit_tree
        location = getattr(self, "_cursor", None)
        if location is None:
            location = (0.0, 0.0)
        node = builder.build_node(tree, self.node_type, location=location)
        for other in tree.nodes:
            other.select = False
        node.select = True
        tree.nodes.active = node
        return {'FINISHED'}


def _all_types():
    return set(rtti.available_node_types())


def _value_types():
    grouped = (BLEND_TYPES | BONE_TYPES | CLIP_TYPES | CONTAINER_TYPES
               | PHYSICS_TYPES | POSESPACE_TYPES | TERMINATOR_TYPES)
    types = {t for t in _all_types() if rtti.output_kind(t) != 'animPoseLink'}
    return sorted(t for t in types if t not in grouped)


def _known_grouped():
    grouped = set()
    for _name, fn in _MENU_GROUPS[:-1]:
        grouped.update(fn())
    return grouped


def _other_metadata_types():
    return sorted(_all_types() - _known_grouped())


_MENU_GROUPS = [
    ("Containers", lambda: sorted(_all_types() & CONTAINER_TYPES)),
    ("Blends & Switches", lambda: sorted(_all_types() & BLEND_TYPES)),
    ("Clips", lambda: sorted(_all_types() & CLIP_TYPES)),
    ("Constraints & IK", lambda: sorted(_all_types() & {
        "PointConstraint", "OrientConstraint", "ParentConstraint", "AimConstraint",
        "AimConstraint_ObjectUp", "AimConstraint_ObjectRotationUp", "TwistConstraint",
        "TranslationLimit", "DirectConnConstraint", "Ik2", "Ik2Constraint",
        "LookAt", "LookAtController", "AddIkRequest", "ReadIkRequest",
        "AddSnapToTerrainIkRequest", "FloorIk", "FootStepScaling", "FootStepAdjuster",
        "HumanIk", "EyesLookAt", "EyesTracksLookAt", "EyesReset",
    })),
    ("Bone Ops", lambda: sorted(_all_types() & (BONE_TYPES | {
        "SetBonePosition", "SetBoneOrientation", "RotateBoneByQuaternion",
        "TransformRotator", "TrackSetter", "SetTrackRange", "RotationLimit",
        "ConeLimit", "FloatTrackDirectConnConstraint", "TransformToTrack",
    }))),
    ("Pose Space", lambda: sorted(_all_types() & POSESPACE_TYPES)),
    ("Physics", lambda: sorted(_all_types() & PHYSICS_TYPES)),
    ("Value", _value_types),
    ("Terminators", lambda: sorted(_all_types() & TERMINATOR_TYPES)),
    ("Other Metadata", _other_metadata_types),
]


def _draw_type_list(layout, types):
    for short in types:
        op = layout.operator(REDENGINE_OT_add_node.bl_idname, text=short)
        op.node_type = short


def _make_submenu(group_name, types_fn):
    idname = "REDENGINE_MT_add_" + group_name.lower().replace(" ", "_").replace("&", "and")

    class _Sub(bpy.types.Menu):
        bl_idname = idname
        bl_label = group_name

        def draw(self, context):
            _draw_type_list(self.layout, types_fn())

    _Sub.__name__ = idname
    return _Sub


_submenus = [_make_submenu(name, fn) for name, fn in _MENU_GROUPS]


class REDENGINE_MT_add_root(bpy.types.Menu):
    bl_idname = "REDENGINE_MT_add_root"
    bl_label = "REDengine AnimGraph"

    def draw(self, context):
        for sub in _submenus:
            self.layout.menu(sub.bl_idname)


def menu_func_add(self, context):
    space = context.space_data
    if (space is not None and space.type == 'NODE_EDITOR'
            and space.edit_tree is not None
            and space.edit_tree.bl_idname == ANIMGRAPH_TREE_ID):
        self.layout.menu(REDENGINE_MT_add_root.bl_idname)


add_classes = (REDENGINE_OT_add_node, *_submenus, REDENGINE_MT_add_root)
