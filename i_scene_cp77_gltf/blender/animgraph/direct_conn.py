from __future__ import annotations

import json
from typing import Any

from ...animation.model.animgraph import direct_conn, indices
from ...core.log import get_logger, log_once
from .access import get_attr, get_idprop
from .owned_handles import allocate_owned_handle_id

_LOG = get_logger(__name__)

SOURCE_STATE_KEY = "red_direct_conn_source_json"
SOURCE_HANDLE_KEY = "red_direct_conn_source_handle_id"


def capture_import_state(node: Any, data: dict) -> None:
    wrapper = data.get("sourceTransform") if isinstance(data, dict) else None
    if isinstance(data, dict):
        # An unresaved constraint reads its legacy channel; importing resaves it onto sourceTransformIndex.
        legacy_name = direct_conn.legacy_source_name(data)
        if legacy_name and not (
            data.get("isSourceTransformResaved")
            and direct_conn.current_source_name(data)
        ):
            data["sourceTransformIndex"] = indices.transform_index(legacy_name)
        data["isSourceTransformResaved"] = 1
    try:
        node[SOURCE_STATE_KEY] = json.dumps(
            wrapper, ensure_ascii=False, separators=(",", ":")
        )
        if isinstance(wrapper, dict):
            node[SOURCE_HANDLE_KEY] = str(
                wrapper.get("HandleId", "") or wrapper.get("HandleRefId", "") or ""
            )
    except (
        AttributeError,
        KeyError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("capture_import_state", type(error).__name__),
            "capture import state: fell back after %s",
            error,
            exc_info=True,
        )


def seed_authored_state(node: Any) -> None:
    try:
        source_handle = allocate_owned_handle_id(node)
        node[SOURCE_HANDLE_KEY] = source_handle
        node[SOURCE_STATE_KEY] = json.dumps(
            direct_conn.authored_defaults(source_handle_id=source_handle)[
                "sourceTransform"
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except (
        AttributeError,
        KeyError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("seed_authored_state", type(error).__name__),
            "seed authored state: fell back after %s",
            error,
            exc_info=True,
        )


def source_handle_id(node: Any) -> str:
    value = str(get_idprop(node, SOURCE_HANDLE_KEY, "") or "")
    if value:
        return value
    value = allocate_owned_handle_id(node)
    try:
        node[SOURCE_HANDLE_KEY] = value
    except (
        AttributeError,
        KeyError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("source_handle_id", type(error).__name__),
            "source handle id: fell back after %s",
            error,
            exc_info=True,
        )
    return value


def canonicalize_node_data(node: Any, data: dict) -> dict:
    if str(get_attr(node, "red_type", "") or "") != direct_conn.RED_TYPE:
        return data
    if "sourceTransform" not in data:
        raw = str(get_idprop(node, SOURCE_STATE_KEY, "") or "")
        if raw:
            try:
                data["sourceTransform"] = json.loads(raw)
            except (TypeError, ValueError):
                pass
    return direct_conn.canonicalize_for_export(
        data,
        source_handle_id=source_handle_id(node),
    )
