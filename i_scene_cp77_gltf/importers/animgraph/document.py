import typing

from ...animation.animgraph_constants import VAR_ARRAYS
from ...blender.animgraph import variables as variable_bindings

class ParserDocumentMixin:
    def _import_variables(self, root_chunk: dict) -> None:
        container = root_chunk.get("variables")
        if not isinstance(container, dict):
            return
        data = container.get("Data")
        if not isinstance(data, dict) or data.get("$type") != "animAnimVariableContainer":
            return

        try:
            self.root_tree['red_variables_handle'] = str(container.get('HandleId', '') or '')
        except Exception:
            pass

        target = self.root_tree.variables
        target.clear()

        try:
            self.root_tree.red_variable_sync_suspended = True
        except Exception:
            pass
        try:
            for array_name, var_type in VAR_ARRAYS:
                entries = data.get(array_name) or []
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    inner = entry.get("Data") or {}
                    slot = target.add()
                    variable_bindings.set_variable_from_json(slot, var_type, inner, entry, array_name)
        finally:
            try:
                self.root_tree.red_variable_sync_suspended = False
            except Exception:
                pass

        try:
            variable_bindings.bind_all_variables(self.root_tree)
        except Exception as exc:
            self.problems.append(f"variable binding failed: {exc}")

    @classmethod
    def _format_variable_value(cls, value: typing.Any) -> str:
        if value is None:
            return ""
        rendered = cls._flatten_value(value)
        return rendered if rendered is not None else ""

    def _import_features(self, root_chunk: dict) -> None:
        entries = root_chunk.get("animFeatures")
        if not isinstance(entries, list):
            return
        target = self.root_tree.features
        target.clear()
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("$type") != "animAnimFeatureEntry":
                continue
            slot = target.add()
            slot.name = (entry.get("name") or {}).get("$value", "") or "<unnamed>"
            slot.class_name = (entry.get("className") or {}).get("$value", "")
            slot.debug_enabled = bool(entry.get("debugEnabled"))
            slot.force_allocate = bool(entry.get("forceAllocate"))
