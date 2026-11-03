from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SectorNodeHandlerBinding:
    node_type: str
    dependency_handler: object = None
    placement_handler: object = None

    @property
    def placement_phase(self):
        handler = self.placement_handler or self.dependency_handler
        return int(getattr(handler, "placement_phase", 20))

    @property
    def has_placement(self):
        return callable(getattr(self.placement_handler, "place", None))

    def collect_dependencies(self, parsed_sector, node):
        if self.dependency_handler is None:
            return ()
        return self.dependency_handler.collect_dependencies(parsed_sector, node)

    def place(self, context):
        if not self.has_placement:
            raise RuntimeError(
                f"No placement handler registered for {self.node_type}"
            )
        return self.placement_handler.place(context)

    @property
    def name(self):
        names = []
        if self.dependency_handler is not None:
            names.append(type(self.dependency_handler).__name__)
        if (
            self.placement_handler is not None
            and self.placement_handler is not self.dependency_handler
        ):
            names.append(type(self.placement_handler).__name__)
        return "+".join(names) if names else "legacy"


class SectorNodeHandlerRegistry:
    def __init__(self):
        self._bindings = {}

    def _binding(self, node_type):
        node_type = str(node_type)
        binding = self._bindings.get(node_type)
        if binding is None:
            binding = SectorNodeHandlerBinding(node_type=node_type)
            self._bindings[node_type] = binding
        return binding

    @staticmethod
    def _assign_role(binding, role, handler):
        current = getattr(binding, role)
        if current is not None and current is not handler:
            raise RuntimeError(
                f"{binding.node_type} already has {role.replace('_', ' ')} "
                f"{type(current).__name__}"
            )
        setattr(binding, role, handler)

    def register(self, handler, *node_types):
        has_dependencies = callable(
            getattr(handler, "collect_dependencies", None)
        )
        has_placement = callable(getattr(handler, "place", None))
        if not has_dependencies and not has_placement:
            raise TypeError(
                f"{type(handler).__name__} is not a sector node handler"
            )

        for node_type in node_types:
            binding = self._binding(node_type)
            if has_dependencies:
                self._assign_role(binding, "dependency_handler", handler)
            if has_placement:
                self._assign_role(binding, "placement_handler", handler)
        return handler

    def register_dependencies(self, handler, *node_types):
        if not callable(getattr(handler, "collect_dependencies", None)):
            raise TypeError(
                f"{type(handler).__name__} has no collect_dependencies()"
            )
        for node_type in node_types:
            self._assign_role(
                self._binding(node_type),
                "dependency_handler",
                handler,
            )
        return handler

    def register_placement(self, handler, *node_types):
        if not callable(getattr(handler, "place", None)):
            raise TypeError(f"{type(handler).__name__} has no place()")
        for node_type in node_types:
            self._assign_role(
                self._binding(node_type),
                "placement_handler",
                handler,
            )
        return handler

    def get(self, node_type):
        return self._bindings.get(str(node_type))

    def handler_name(self, node_type):
        binding = self.get(node_type)
        return binding.name if binding is not None else "legacy"

    def items(self):
        return tuple(self._bindings.items())


NODE_HANDLERS = SectorNodeHandlerRegistry()


def register_node_handler(*node_types):
    def decorator(handler):
        NODE_HANDLERS.register(handler, *node_types)
        return handler
    return decorator


def register_dependency_handler(*node_types):
    def decorator(handler):
        NODE_HANDLERS.register_dependencies(handler, *node_types)
        return handler
    return decorator


def register_placement_handler(*node_types):
    def decorator(handler):
        NODE_HANDLERS.register_placement(handler, *node_types)
        return handler
    return decorator
