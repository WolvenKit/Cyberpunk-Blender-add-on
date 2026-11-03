from __future__ import annotations

from ...domain.animgraph.branch_frames import identity_frame
from .base import GraphNodeHandler, execute_first_child


class InputHandler(GraphNodeHandler):
    kinds = ("INPUT",)

    def execute(self, context, step):
        return step.input_frame


class ReferenceHandler(GraphNodeHandler):
    kinds = ("REFERENCE",)

    def execute(self, context, step):
        result = context._reference_frame(step.input_frame)
        step.frame_cache[step.cache_key] = result
        return result


class IdentityHandler(GraphNodeHandler):
    kinds = ("IDENTITY",)

    def execute(self, context, step):
        result = identity_frame(step.input_frame)
        step.frame_cache[step.cache_key] = result
        return result


class NullLinkHandler(GraphNodeHandler):
    kinds = ("NULL_LINK",)

    def execute(self, context, step):
        result = (
            identity_frame(step.input_frame)
            if step.additive_branch
            else context._reference_frame(step.input_frame)
        )
        step.frame_cache[step.cache_key] = result
        return result


class SlotPassthroughHandler(GraphNodeHandler):
    kinds = ("SLOT_PASSTHROUGH",)

    def execute(self, context, step):
        result = execute_first_child(context, step)
        step.frame_cache[step.cache_key] = result
        return result
