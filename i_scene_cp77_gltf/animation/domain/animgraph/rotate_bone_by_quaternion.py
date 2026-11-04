from __future__ import annotations

from ...model.animgraph.indices import index_name
from .topology import has_link


def rotate_bone_by_quaternion_data(node_type, node):
    return {
        "bone": index_name(node.get("bone"), "animTransformIndex", allow_text=True),
        "useIncrementalMode": bool(node.get("useIncrementalMode", False)),
        "resetOnActivation": bool(node.get("resetOnActivation", True)),
        "hasQuaternionNode": has_link(node, "quaternionNode"),
    }
