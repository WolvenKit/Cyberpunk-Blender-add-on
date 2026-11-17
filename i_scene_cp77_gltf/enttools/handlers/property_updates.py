from ...core.log import get_logger
from ...core.notifications import show_message
from ..blender.state import ensure_appearance_state
from ..runtime.scene_cache import entity_index
from ..runtime.updates import suspended
from ..services.appearances import switch_appearance
from ..services.components import apply_field
from ..services.selection import (
    NOT_IMPORTED,
    appearance_choices,
    current_collection,
    refresh_choices,
    select_component_objects,
)

_LOG = get_logger(__name__)


def tools_changed(context, field: str) -> None:
    tools = context.scene.cp77_entity_tools
    if field == "entity":
        choices = appearance_choices(tools.entity)
        with suspended():
            if choices:
                tools.appearance = choices[0][0]
            tools.component_index = 0
        refresh_choices(context)
    elif field == "appearance":
        if tools.appearance.startswith(NOT_IMPORTED):
            result = switch_appearance(
                context, tools.entity, tools.appearance[len(NOT_IMPORTED) :]
            )
        else:
            collection = current_collection(context)

            result = (
                switch_appearance(
                    context, tools.entity, ensure_appearance_state(collection).name
                )
                if collection
                else None
            )
        if result is not None and not result.ok:
            show_message(result.message, severity="ERROR", logger=_LOG)
        with suspended():
            tools.component_index = 0
        refresh_choices(context)
    elif field == "component_index":
        refresh_choices(context)
        select_component_objects(context)
    elif field == "issue_index":
        if not 0 <= tools.issue_index < len(tools.issues):
            return
        issue = tools.issues[tools.issue_index]
        for collection in entity_index().collections(tools.entity):
            state = ensure_appearance_state(collection)
            if state.name != issue.appearance:
                continue
            index = next(
                (
                    i
                    for i, item in enumerate(state.components)
                    if item.name == issue.component
                ),
                None,
            )
            with suspended():
                tools.appearance = collection.name
                if index is not None:
                    tools.component_index = index
            refresh_choices(context)
            select_component_objects(context)
            return


def field_changed(context, item, field: str) -> None:
    """A component field was edited in the panel"""
    collection = item.id_data
    index = next(
        i
        for i, candidate in enumerate(collection.cp77_entity_state.components)
        if candidate == item
    )
    result = apply_field(context, collection, index, field)
    if not result.ok:
        show_message(result.message, severity=result.level, logger=_LOG)
    elif field in {"attach", "name"}:
        refresh_choices(context)
