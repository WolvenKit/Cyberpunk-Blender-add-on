from __future__ import annotations

import os

import bpy

from ...animation.domain.animgraph.shared_meta_pose import (
    resolve_owner_index,
    resource_stem,
)
from ...animation.services.animgraph.repository import AnimGraphRepository
from ...assetio.paths import strip_json_suffix
from ...blender.animgraph.source import store_graph_source
from ...blender.animgraph.tree_ops import new_graph_tree
from ...blender.rig_metadata import source_rig_part_bindings, source_rig_paths
from .parser import AnimGraphParser


def build_graph_tree(
    payload, filepath: str, armature, context=None, *, rig_part: str = ""
):
    """A new AnimGraph tree for payload, bound to armature"""
    name = (
        strip_json_suffix(os.path.basename(filepath or ""))
        or f"{armature.name}_animgraph"
    )
    tree = new_graph_tree(name)
    try:
        AnimGraphParser(tree).execute(payload, context)
        tree.red_bound_armature = armature
        tree.red_rig_part = rig_part
    except Exception:
        bpy.data.node_groups.remove(tree, do_unlink=True)
        raise
    return tree


def import_graph(filepath: str, armature, context=None, *, rig_part: str = ""):
    """Import the graph at filepath bound to armature"""
    document = AnimGraphRepository().load(filepath)
    tree = build_graph_tree(
        document.payload, filepath, armature, context, rig_part=rig_part
    )
    store_graph_source(tree, document.source_text, filepath)
    return tree


def rig_part_items(armature) -> list[tuple[str, str, str]]:
    """The armature's MetaRig parts as enum items"""
    return [
        (path, resource_stem(path, ".rig.json") or path, path)
        for path in source_rig_paths(armature)
    ]


def default_rig_part(armature, filepath: str) -> str:
    """The part the preview binds the graph to without a pick"""
    paths = source_rig_paths(armature)
    try:
        return paths[
            resolve_owner_index(filepath, paths, source_rig_part_bindings(armature))
        ]
    except ValueError:
        return paths[0] if paths else ""
