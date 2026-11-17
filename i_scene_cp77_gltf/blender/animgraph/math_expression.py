from __future__ import annotations

from typing import Any

from ...animation.domain.animgraph.math_expression import (
    SOCKET_ARRAY_BY_KIND,
    MathExpressionError,
    recompiled_expression_data,
)
from ...animation.model.animgraph import math_expression
from ...animation.model.animgraph.constants import LINK_SOCKET
from ...assetio import animgraph_json as json_io
from .property_codec import property_by_key
from .sm_model import new_handle_id
from .sockets import bind_input_socket
from .tree_ops import link_sockets, new_socket

FORMULA_KEY = "expressionString"
COMPILED_FORMULA_KEY = "_cp77_compiled_formula"
DATA_KEY = "red_math_expression_data_json"
HANDLE_KEY = "red_math_expression_handle"


def node_formula(node: Any) -> str:
    item = property_by_key(node, FORMULA_KEY)
    return str(item.string_value) if item is not None else ""


def stored_expression_data(node: Any) -> Any:
    raw = str(node.get(DATA_KEY, "") or "")
    return json_io.loads(raw) if raw else None


def formula_edited(item: Any) -> None:
    pointer = item.as_pointer()
    for node in getattr(item.id_data, "nodes", ()):
        if math_expression.is_math_expression_node_type(
            getattr(node, "red_type", "")
        ) and any(prop.as_pointer() == pointer for prop in node.red_properties):
            apply_formula(node)
            return


def apply_formula(node: Any) -> None:
    formula = node_formula(node)
    previous = str(node.get(COMPILED_FORMULA_KEY, "") or "")
    if formula == previous:
        return
    try:
        data, moves, encoded = recompiled_expression_data(
            stored_expression_data(node),
            formula,
            previous,
            str(node.get(HANDLE_KEY, "") or "") or new_handle_id(),
            str(node.red_type),
        )
    except MathExpressionError:
        return
    node[DATA_KEY] = json_io.dumps(data, indent=None)
    node[COMPILED_FORMULA_KEY] = formula
    math_expression.annotate_node(
        node, data, expression_string=formula, node_type=str(node.red_type)
    )
    _rebuild_sockets(node, encoded.variables, moves)


def _rebuild_sockets(node: Any, variables, moves) -> None:
    tree = node.id_data
    sources = {}
    for socket in list(node.inputs):
        slot = math_expression.socket_slot(getattr(socket, "red_json_path", ""))
        if slot is None:
            continue
        sources[slot] = [link.from_socket for link in socket.links]
        node.inputs.remove(socket)
    counts = dict.fromkeys(math_expression.SOCKET_ARRAYS, 0)
    for variable in variables:
        array_name = SOCKET_ARRAY_BY_KIND[variable.kind]
        slot = (array_name, counts[array_name])
        counts[array_name] += 1
        link_type = math_expression.SOCKET_ARRAYS[array_name][2]
        socket = new_socket(node, "INPUT", LINK_SOCKET[link_type][0], variable.name)
        bind_input_socket(
            socket,
            owner_handle=str(node.red_handle_id or ""),
            json_path=f"expressionData.{array_name}[{slot[1]}].link",
            link_type=link_type,
        )
        for source in sources.get(moves.get(slot), ()):
            link_sockets(tree, source, socket)
