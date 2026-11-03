<<<<<<< Updated upstream
import typing

from ...animation.animgraph_constants import VAR_ARRAYS
from ...blender.animgraph import variables as variable_bindings
=======
from ...animation.model.animgraph.constants import VAR_ARRAYS
from ...blender.animgraph import variables as variable_bindings
from ...core.log import debug_exception, get_logger, log_once

_LOG = get_logger(__name__)

>>>>>>> Stashed changes

class ParserDocumentMixin:
    def _import_variables(self, root_chunk: dict) -> None:
        container = root_chunk.get("variables")
        if not isinstance(container, dict):
            return
        data = container.get("Data")
<<<<<<< Updated upstream
        if not isinstance(data, dict) or data.get("$type") != "animAnimVariableContainer":
            return

        try:
            self.root_tree['red_variables_handle'] = str(container.get('HandleId', '') or '')
        except Exception:
            pass
=======
        if (
            not isinstance(data, dict)
            or data.get("$type") != "animAnimVariableContainer"
        ):
            return

        try:
            self.root_tree["red_variables_handle"] = str(
                container.get("HandleId", "") or ""
            )
        except (AttributeError, TypeError, ValueError) as exc:
            log_once(
                _LOG,
                "DEBUG",
                ("ParserDocumentMixin._import_variables", type(exc).__name__),
                "import variables: fell back after %s",
                exc,
                exc_info=True,
            )
            self.problems.append(f"variable container handle was not stored: {exc}")
>>>>>>> Stashed changes

        target = self.root_tree.variables
        target.clear()

<<<<<<< Updated upstream
        try:
            self.root_tree.red_variable_sync_suspended = True
        except Exception:
            pass
=======
        self.root_tree.red_variable_sync_suspended = True
>>>>>>> Stashed changes
        try:
            for array_name, var_type in VAR_ARRAYS:
                entries = data.get(array_name) or []
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    inner = entry.get("Data") or {}
                    slot = target.add()
<<<<<<< Updated upstream
                    variable_bindings.set_variable_from_json(slot, var_type, inner, entry, array_name)
        finally:
            try:
                self.root_tree.red_variable_sync_suspended = False
            except Exception:
                pass
=======
                    variable_bindings.set_variable_from_json(
                        slot, var_type, inner, entry, array_name
                    )
        finally:
            self.root_tree.red_variable_sync_suspended = False
>>>>>>> Stashed changes

        try:
            variable_bindings.bind_all_variables(self.root_tree)
        except Exception as exc:
<<<<<<< Updated upstream
            self.problems.append(f"variable binding failed: {exc}")

    @classmethod
    def _format_variable_value(cls, value: typing.Any) -> str:
        if value is None:
            return ""
        rendered = cls._flatten_value(value)
        return rendered if rendered is not None else ""

=======
            debug_exception(_LOG, "Could not bind the AnimGraph variables")
            self.problems.append(f"variable binding failed: {exc}")

>>>>>>> Stashed changes
    def _import_features(self, root_chunk: dict) -> None:
        entries = root_chunk.get("animFeatures")
        if not isinstance(entries, list):
            return
        target = self.root_tree.features
        target.clear()
        for entry in entries:
<<<<<<< Updated upstream
            if not isinstance(entry, dict) or entry.get("$type") != "animAnimFeatureEntry":
=======
            if (
                not isinstance(entry, dict)
                or entry.get("$type") != "animAnimFeatureEntry"
            ):
>>>>>>> Stashed changes
                continue
            slot = target.add()
            slot.name = (entry.get("name") or {}).get("$value", "") or "<unnamed>"
            slot.class_name = (entry.get("className") or {}).get("$value", "")
            slot.debug_enabled = bool(entry.get("debugEnabled"))
            slot.force_allocate = bool(entry.get("forceAllocate"))
