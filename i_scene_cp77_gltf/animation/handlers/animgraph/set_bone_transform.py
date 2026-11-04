from __future__ import annotations

from ....assetio.transform_values import qs_transform_from_data
from ...domain.animgraph.set_bone_transform import evaluate_set_bone_transform
from .base import PoseOpHandler, resolve_bones


class SetBoneTransformHandler(PoseOpHandler):
    node_types = ("animAnimNode_SetBoneTransform",)

    def map_data(self, context, program_node, node_type, data):
        entries = []
        for raw in data.get("entries", ()):
            item = dict(raw)
            resolve_bones(
                context, item, ("transformToChange", "sourceBone", "offsetSpaceBone")
            )
            item["_offsetQs"] = qs_transform_from_data(item.get("offset"))
            item["_fastModelSourceOffset"] = bool(
                str(item.get("setMethod", "WholeTransform") or "WholeTransform")
                == "WholeTransform"
                and not bool(item.get("snapToReference", False))
                and not bool(item.get("offsetToReference", False))
                and str(item.get("sourceBone", "") or "")
                and str(item.get("sourceBone", "") or "")
                == str(item.get("offsetSpaceBone", "") or "")
            )
            entries.append(item)
        data["entries"] = tuple(entries)
        data["_allFastModelSourceOffset"] = bool(entries) and all(
            bool(item.get("_fastModelSourceOffset", False)) for item in entries
        )
        data["_usesTracks"] = False
        return data

    def evaluate(self, context, op):
        reference_pose_ms = (
            {}
            if op.child.model_space
            and bool(op.data.get("_allFastModelSourceOffset", False))
            else context._reference_model_pose(op.child)
        )
        evaluation = evaluate_set_bone_transform(
            op.pose,
            op.child.parent_map,
            reference_pose_ms,
            op.data.get("entries", ()) or (),
            model_space=op.child.model_space,
        )
        return evaluation
