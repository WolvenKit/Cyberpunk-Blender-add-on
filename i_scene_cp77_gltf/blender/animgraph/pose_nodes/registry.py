from __future__ import annotations


class PoseNodeHandlerRegistry:
    """Maps REDengine pose-node $type values to the handler that plans and evaluates them"""

    def __init__(self):
        self._handlers = {}

    def register(self, handler, *red_types):
        for red_type in red_types:
            current = self._handlers.get(str(red_type))
            if current is not None and current is not handler:
                raise RuntimeError(
                    f"{red_type} already has pose node handler {type(current).__name__}"
                )
            self._handlers[str(red_type)] = handler
        return handler

    def get(self, red_type):
        return self._handlers.get(str(red_type or ""))

    def supports(self, red_type) -> bool:
        return str(red_type or "") in self._handlers

    def red_types(self) -> frozenset[str]:
        return frozenset(self._handlers)


POSE_NODE_HANDLERS = PoseNodeHandlerRegistry()


def register_pose_node_handler(*red_types):
    def decorator(handler_class):
        POSE_NODE_HANDLERS.register(handler_class(), *red_types)
        return handler_class

    return decorator
