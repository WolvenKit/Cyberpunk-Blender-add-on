from __future__ import annotations

from typing import Any, Iterable


class EntityComponentHandlerRegistry:
    """Map exact REDengine component types to execution handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, Any] = {}

    def register(self, component_types: Iterable[str], handler: Any) -> Any:
        for component_type in component_types:
            existing = self._handlers.get(component_type)
            if existing is not None and existing is not handler:
                raise ValueError(f"Handler already registered for {component_type}")
            self._handlers[component_type] = handler
        return handler

    def handler_for(self, component: Any) -> Any | None:
        if not isinstance(component, dict):
            return None
        return self._handlers.get(component.get("$type", ""))

    def execute(self, component: Any, context: Any) -> Any:
        handler = self.handler_for(component)
        if handler is None:
            return None
        return handler.execute(component, context)

    def execute_many(self, components: Iterable[Any], context: Any) -> list[Any]:
        results = []
        for component in components or ():
            result = self.execute(component, context)
            if result is not None:
                results.append(result)
        return results

    @property
    def component_types(self) -> frozenset[str]:
        return frozenset(self._handlers)
