from __future__ import annotations

import bpy

from ....blender.animgraph.preview_settings import graph_settings
from ....blender.animgraph.rig_binding import binding_tree

# Dangle-state preview field -> graph preview settings field.
_SETTINGS_FIELDS = {
    "preview_visual_tags": "visual_tags",
    "preview_component_tags": "component_tags",
    "preview_skeletal_lod": "skeletal_lod",
    "preview_performance_mode": "performance_mode",
    "preview_external_events": "external_events",
    "preview_wrapper_variables": "wrapper_variables",
    "preview_anim_features_json": "anim_features_json",
    "preview_look_at_parts": "look_at_parts",
    "preview_look_at_enabled": "look_at_enabled",
    "preview_look_at_part": "look_at_part",
    "preview_look_at_object": "look_at_object",
    "preview_look_at_target": "look_at_target",
    "preview_look_at_speed": "look_at_speed",
    "preview_vector_inputs": "vector_inputs",
    "preview_visual_tag_requirements": "visual_tag_requirements",
    "evaluation_boundary": "evaluation_boundary",
    "preview_input_error": "input_error",
}


class GraphPreviewState:
    """dangle_state with its preview fields on tree's graph settings"""

    def __init__(self, dangle_state, tree):
        root = binding_tree(tree)
        object.__setattr__(self, "_state", dangle_state)
        object.__setattr__(self, "_tree_name", root.name)
        object.__setattr__(
            self,
            "_derived",
            {
                "preview_mode": "GRAPH",
                "animgraph_tree_name": root.name,
                "animgraph_source_text": str(root.red_source_text or ""),
                "animgraph_source_path": str(root.red_source_path or ""),
            },
        )

    def _settings(self):
        # Found by name each time: a removed tree's settings must never be touched (Blender does not guard them).
        tree = bpy.data.node_groups.get(self._tree_name)
        if tree is None:
            raise ReferenceError(f"AnimGraph tree {self._tree_name!r} was removed")
        return graph_settings(tree)

    def __getattr__(self, name):
        if name in self._derived:
            return self._derived[name]
        field = _SETTINGS_FIELDS.get(name)
        return getattr(self._settings(), field) if field else getattr(self._state, name)

    def __setattr__(self, name, value):
        if name in self._derived:
            raise AttributeError(
                f"{name} comes from the graph and cannot be set on its preview state"
            )
        field = _SETTINGS_FIELDS.get(name)
        setattr(self._settings() if field else self._state, field or name, value)
