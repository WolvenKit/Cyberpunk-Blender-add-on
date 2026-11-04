import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from .rig_binding import binding_tree


class REDengine_PreviewVectorInput(bpy.types.PropertyGroup):
    key: StringProperty(options={"HIDDEN"})
    group: StringProperty(name="Group", options={"HIDDEN"})
    input_name: StringProperty(name="Input", options={"HIDDEN"})
    source_handle: StringProperty(name="Source Handle", options={"HIDDEN"})
    value: FloatVectorProperty(
        name="Value",
        size=3,
        default=(0.0, 0.0, 0.0),
        description="Preview-only live VectorInput value; exported AnimGraph data is unchanged",
    )


class REDengine_PreviewVisualTag(bpy.types.PropertyGroup):
    tag: StringProperty(name="Visual Tag")
    graph_path: StringProperty(name="Graph Path", options={"HIDDEN"})


class REDengine_GraphPreviewSettings(bpy.types.PropertyGroup):
    visual_tags: StringProperty(
        name="Visual Tags",
        description="Comma-separated visual tags for graph preview; blank means an empty tag set. Applied when Play is "
        "pressed; does not change the exported graph",
    )
    component_tags: StringProperty(
        name="Component Tags",
        description="Comma-separated animation component tags for graph preview (ComponentTagCondition); blank means "
        "an untagged component. Applied when Play is pressed; does not change the exported graph",
    )
    skeletal_lod: IntProperty(
        name="Skeletal LOD",
        default=0,
        min=0,
        max=15,
        description="REDengine animation level of detail used to resolve ConditionalSegment branches during graph "
        "preview; 0 is highest quality",
    )
    performance_mode: BoolProperty(
        name="Performance Mode",
        default=False,
        description="Resolve SkipPerformanceMode segments as skipped during graph preview; preview-only and not "
        "exported",
    )
    external_events: StringProperty(
        name="External Events",
        description="Comma-separated external AnimGraph events fired once on the next graph preview update; consumed "
        "after firing and not exported",
    )
    wrapper_variables: StringProperty(
        name="Wrapper Variables",
        description="Comma-separated anim wrapper variables that are set during graph preview, for the WrapperValue "
        "transition conditions; not exported",
    )
    anim_features_json: StringProperty(
        name="Anim Features",
        default="{}",
        description='Preview-only feature values as JSON, for example {"seat_front_left_window":{"state":1}}; not '
        "exported",
    )
    look_at_parts: StringProperty(options={"HIDDEN"})
    look_at_enabled: BoolProperty(name="Look at Target", default=False)
    look_at_part: StringProperty(name="Body Part", default="Eyes")
    look_at_object: PointerProperty(
        name="Target Object",
        type=bpy.types.Object,
        description="Follow this object's world position during graph preview",
    )
    look_at_target: FloatVectorProperty(
        name="Target Position",
        size=3,
        default=(0.0, 3.0, 1.6),
        subtype="TRANSLATION",
        description="Target position in the rig's model space when no target object is selected",
    )
    look_at_speed: FloatProperty(
        name="Transition Speed",
        default=60.0,
        min=0.01,
        description="Angular speed in degrees per second when acquiring or releasing the target",
    )
    vector_inputs: CollectionProperty(type=REDengine_PreviewVectorInput)
    visual_tag_requirements: CollectionProperty(type=REDengine_PreviewVisualTag)
    evaluation_boundary: StringProperty(name="Preview Boundary", options={"HIDDEN"})
    input_error: StringProperty(name="Preview Input Error", options={"HIDDEN"})
    view_handle: StringProperty(name="Viewed Node", options={"HIDDEN", "SKIP_SAVE"})


PREVIEW_SETTINGS_CLASSES = (
    REDengine_PreviewVectorInput,
    REDengine_PreviewVisualTag,
    REDengine_GraphPreviewSettings,
)

# Dangle-state fields a graph imported before its settings moved onto the graph still carries, by settings field.
_ADOPTED_FIELDS = {
    "visual_tags": "preview_visual_tags",
    "component_tags": "preview_component_tags",
    "skeletal_lod": "preview_skeletal_lod",
    "performance_mode": "preview_performance_mode",
    "external_events": "preview_external_events",
    "anim_features_json": "preview_anim_features_json",
    "look_at_parts": "preview_look_at_parts",
    "look_at_enabled": "preview_look_at_enabled",
    "look_at_part": "preview_look_at_part",
    "look_at_object": "preview_look_at_object",
    "look_at_target": "preview_look_at_target",
    "look_at_speed": "preview_look_at_speed",
}


def graph_settings(tree) -> REDengine_GraphPreviewSettings:
    """The preview settings of the graph tree belongs to, kept on its root tree"""
    return binding_tree(tree).red_preview


def copy_graph_settings(source_tree, target_tree) -> None:
    """Give target_tree's graph the preview settings of source_tree's, as when a graph's tree is built anew"""
    _copy_properties(graph_settings(source_tree), graph_settings(target_tree))


def _copy_properties(source, target) -> None:
    for prop in source.bl_rna.properties:
        name = prop.identifier
        if prop.type == "COLLECTION":
            items = getattr(target, name)
            items.clear()
            for item in getattr(source, name):
                _copy_properties(item, items.add())
        elif not prop.is_readonly:
            setattr(target, name, getattr(source, name))


def _dangle_rig(root):
    rig = bpy.data.objects.get(str(root.get("cp77_dangle_rig", "") or ""))
    return rig if rig is not None and getattr(rig, "type", "") == "ARMATURE" else None


def adopt_dangle_settings(tree) -> bool:
    """Copy the Dangle rig's preview settings and source document onto a graph without a source"""
    root = binding_tree(tree)
    rig = _dangle_rig(root)
    state = getattr(rig, "dangle_state", None)
    if root.red_source_text or state is None or not state.animgraph_source_text:
        return False
    settings = root.red_preview
    for field, legacy in _ADOPTED_FIELDS.items():
        setattr(settings, field, getattr(state, legacy))
    settings.vector_inputs.clear()
    for legacy in state.preview_vector_inputs:
        item = settings.vector_inputs.add()
        item.key, item.group, item.input_name = (
            legacy.key,
            legacy.group,
            legacy.input_name,
        )
        item.source_handle, item.value = legacy.source_handle, legacy.value
    settings.visual_tag_requirements.clear()
    for legacy in state.preview_visual_tag_requirements:
        item = settings.visual_tag_requirements.add()
        item.tag, item.graph_path = legacy.tag, legacy.graph_path
    root.red_source_text = state.animgraph_source_text
    root.red_source_path = state.animgraph_source_path
    return True
