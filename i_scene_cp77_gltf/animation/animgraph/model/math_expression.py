from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Tuple


SOCKET_ARRAYS = {
    'floatSockets': ('Float', 'f', 'animFloatLink', 'animAnimMathExpressionFloatSocket'),
    'vectorSockets': ('Vector', 'v', 'animVectorLink', 'animAnimMathExpressionVectorSocket'),
    'quaternionSockets': ('Quaternion', 'q', 'animQuaternionLink', 'animAnimMathExpressionQuaternionSocket'),
}

RETURN_VAR_TYPES = {
    0: 'Void/Unknown',
    1: 'Float',
    2: 'Vector',
    3: 'Quaternion',
    4: 'Bool',
    5: 'Int',
}

NODE_RETURN_BY_TYPE = {
    'animAnimNode_MathExpressionFloat': 'Float',
    'animAnimNode_MathExpressionVector': 'Vector',
    'animAnimNode_MathExpressionQuaternion': 'Quaternion',
    'animAnimNode_MathExpressionPose': 'Pose',
}


def safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return '' if value is None else repr(value)


def expression_string_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get('$value', ''))
    if value is None:
        return ''
    return str(value)


def expression_payload(expr_data: Any) -> Dict[str, Any]:
    """Return the owned mathExprExpression Data object, if present."""
    if not isinstance(expr_data, dict):
        return {}
    expression = expr_data.get('expression')
    if isinstance(expression, dict):
        data = expression.get('Data')
        if isinstance(data, dict):
            return data
    return {}


def expression_handle(expr_data: Any) -> str:
    expression = expr_data.get('expression') if isinstance(expr_data, dict) else None
    if isinstance(expression, dict):
        return str(expression.get('HandleId', '') or expression.get('HandleRefId', '') or '')
    return ''


def token_data(expr_data: Any) -> List[int]:
    payload = expression_payload(expr_data)
    value = payload.get('tokenData')
    if not isinstance(value, list):
        return []
    out: List[int] = []
    for item in value:
        try:
            out.append(int(item))
        except Exception:


            out.append(0)
    return out


def values_data(expr_data: Any) -> List[Any]:
    payload = expression_payload(expr_data)
    value = payload.get('valuesData')
    return list(value) if isinstance(value, list) else []


def return_var_type(expr_data: Any) -> int:
    payload = expression_payload(expr_data)
    raw = payload.get('returnVarType')
    try:
        return int(raw)
    except Exception:
        return -1


def return_type(expr_data: Any, node_type: str = '') -> str:
    node_return = NODE_RETURN_BY_TYPE.get(str(node_type or ''), '')
    if node_return:
        return node_return
    rid = return_var_type(expr_data)
    return RETURN_VAR_TYPES.get(rid, f'#{rid}' if rid >= 0 else '')


def _socket_var_id(socket_data: Any, default_index: int) -> int:
    if isinstance(socket_data, dict):
        try:
            return int(socket_data.get('expressionVarId', default_index))
        except Exception:
            pass
    return default_index


def socket_caption(array_name: str, index: int, socket_data: Any = None, expression_string: str = '') -> str:
    _label, prefix, _kind, _struct = SOCKET_ARRAYS.get(array_name, ('Input', 'x', '', ''))
    return f'{prefix}{_socket_var_id(socket_data, index)}'


def handle_id_of(wrapper: Any) -> str:
    if not isinstance(wrapper, dict):
        return ''
    node = wrapper.get('node')
    if not isinstance(node, dict):
        return ''
    if 'HandleRefId' in node:
        return str(node.get('HandleRefId', ''))
    if 'HandleId' in node:
        return str(node.get('HandleId', ''))
    return ''


def iter_expression_socket_links(expr_data: Any, expression_string: str = '') -> Iterable[Tuple[str, str, dict, Dict[str, Any]]]:
    """Yield socket links owned by animMathExpressionNodeData."""
    if not isinstance(expr_data, dict):
        return
    for array_name, (label, prefix, link_kind, struct_type) in SOCKET_ARRAYS.items():
        arr = expr_data.get(array_name)
        if not isinstance(arr, list):
            continue
        for index, item in enumerate(arr):
            if not isinstance(item, dict):
                continue
            link = item.get('link')
            if not isinstance(link, dict):
                continue
            var_id = _socket_var_id(item, index)
            caption = f'{prefix}{var_id}'
            summary = {
                'array': array_name,
                'index': index,
                'kind': label,
                'caption': caption,
                'expressionVarId': var_id,
                'linkType': link.get('$type', link_kind),
                'sourceHandle': handle_id_of(link),
                'socketType': item.get('$type', struct_type),
            }
            yield f'{array_name}[{index}].link', caption, link, summary


def parse_expression_data(expr_data: Any, expression_string: str = '', node_type: str = '') -> Dict[str, Any]:
    if not isinstance(expr_data, dict):
        return {'valid': False, 'tokens': [], 'values': [], 'sockets': []}

    sockets: List[Dict[str, Any]] = []
    for _path, _caption, _link, summary in iter_expression_socket_links(expr_data):
        sockets.append(summary)

    tokens = token_data(expr_data)
    values = values_data(expr_data)
    rtype = return_type(expr_data, node_type=node_type)
    formula = expression_string_value(expression_string)

    return {
        'valid': True,
        'type': str(expr_data.get('$type', 'animMathExpressionNodeData')),
        'expressionString': formula,
        'expressionHandle': expression_handle(expr_data),
        'returnVarType': return_var_type(expr_data),
        'returnType': rtype,
        'tokens': tokens,
        'values': values,
        'tokenCount': len(tokens),
        'valueCount': len(values),
        'sockets': sockets,
        'floatSocketCount': len(expr_data.get('floatSockets') or []) if isinstance(expr_data.get('floatSockets'), list) else 0,
        'vectorSocketCount': len(expr_data.get('vectorSockets') or []) if isinstance(expr_data.get('vectorSockets'), list) else 0,
        'quaternionSocketCount': len(expr_data.get('quaternionSockets') or []) if isinstance(expr_data.get('quaternionSockets'), list) else 0,
        'summary': f'{rtype or "MathExpression"}: {formula}' if formula else (rtype or 'MathExpression'),
        'raw': expr_data,
    }


def annotate_node(node: Any, expr_data: Any, expression_string: str = '', node_type: str = '') -> Dict[str, Any]:
    parsed = parse_expression_data(expr_data, expression_string=expression_string, node_type=node_type)
    try:
        node['red_math_expression'] = bool(parsed.get('valid'))
        node['red_math_token_count'] = int(parsed.get('tokenCount', 0))
        node['red_math_value_count'] = int(parsed.get('valueCount', 0))
        node['red_math_input_count'] = len(parsed.get('sockets', []))
        node['red_math_return_type'] = str(parsed.get('returnType', ''))
        node['red_math_expression_handle'] = str(parsed.get('expressionHandle', ''))
    except Exception:
        pass
    return parsed


def is_math_expression_node_type(node_type: str) -> bool:
    return str(node_type).startswith('animAnimNode_MathExpression')


def is_math_expression_data(obj: Any) -> bool:
    return isinstance(obj, dict) and obj.get('$type') == 'animMathExpressionNodeData'


def is_math_expression_socket_struct(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    return str(obj.get('$type', '')).startswith('animAnimMathExpression') and 'expressionVarId' in obj
