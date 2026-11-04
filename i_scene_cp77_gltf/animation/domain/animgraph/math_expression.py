from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from ....bartmoss.scalar import all_finite
from ...model.animgraph.indices import index_name
from ...model.animgraph.math_expression import (
    expression_payload,
    expression_string_value,
)


class MathExpressionError(ValueError):
    pass


SCALAR = "scalar"
VECTOR = "vector"
QUATERNION = "quaternion"
_FLOAT_EPSILON = 1.1920928955078125e-07
_OPERATOR_CHARS = frozenset("+-*/^%(),&|!><=")
_NAME_CHARS = frozenset("_$#@")


@dataclass(frozen=True)
class _Vec4:
    x: float
    y: float
    z: float
    w: float = 1.0

    def tuple(self):
        return (self.x, self.y, self.z, self.w)


@dataclass(frozen=True)
class _Quat:
    x: float
    y: float
    z: float
    w: float

    def tuple(self):
        return (self.x, self.y, self.z, self.w)

    def __mul__(self, other):
        rhs = as_quaternion(other)
        ax, ay, az, aw = self.tuple()
        bx, by, bz, bw = rhs.tuple()
        return _Quat(
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz,
        )


def as_scalar(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MathExpressionError(
            f"MathExpression expected a scalar, got {type(value).__name__}"
        )
    value = float(value)
    if not math.isfinite(value):
        raise MathExpressionError("MathExpression produced a non-finite scalar")
    return value


def as_vector(value):
    if isinstance(value, _Vec4):
        return value
    if isinstance(value, Mapping):
        out = _Vec4(
            float(value.get("X", value.get("x", 0.0))),
            float(value.get("Y", value.get("y", 0.0))),
            float(value.get("Z", value.get("z", 0.0))),
            float(value.get("W", value.get("w", 1.0))),
        )
        if all_finite(out.tuple()):
            return out
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        out = _Vec4(
            float(value[0]),
            float(value[1]),
            float(value[2]),
            float(value[3]) if len(value) >= 4 else 1.0,
        )
        if all_finite(out.tuple()):
            return out
    raise MathExpressionError(
        f"MathExpression expected a Vector4, got {type(value).__name__}"
    )


def as_quaternion(value):
    if isinstance(value, _Quat):
        return value
    if isinstance(value, Mapping):
        out = _Quat(
            float(value.get("i", value.get("X", value.get("x", 0.0)))),
            float(value.get("j", value.get("Y", value.get("y", 0.0)))),
            float(value.get("k", value.get("Z", value.get("z", 0.0)))),
            float(value.get("r", value.get("W", value.get("w", 1.0)))),
        )
        if all_finite(out.tuple()):
            return out
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        out = _Quat(float(value[0]), float(value[1]), float(value[2]), float(value[3]))
        if all_finite(out.tuple()):
            return out
    raise MathExpressionError(
        f"MathExpression expected a Quaternion, got {type(value).__name__}"
    )


def _value_type(value):
    if isinstance(value, _Vec4):
        return VECTOR
    if isinstance(value, _Quat):
        return QUATERNION
    as_scalar(value)
    return SCALAR


def _float_div(left, right):
    # Dividing by zero gives 0, so a graph dividing by an unset value keeps a finite pose.
    denominator = as_scalar(right)
    return as_scalar(left) / denominator if denominator != 0.0 else 0.0


def _vector_add(left, right):
    a, b = as_vector(left), as_vector(right)
    return _Vec4(a.x + b.x, a.y + b.y, a.z + b.z, a.w + b.w)


def _vector_sub(left, right):
    a, b = as_vector(left), as_vector(right)
    return _Vec4(a.x - b.x, a.y - b.y, a.z - b.z, a.w - b.w)


def _vector_scale(vector, scalar):
    v, f = as_vector(vector), as_scalar(scalar)
    return _Vec4(v.x * f, v.y * f, v.z * f, v.w * f)


def _vector_div(vector, scalar):
    denominator = as_scalar(scalar)
    if denominator == 0.0:
        return _Vec4(0.0, 0.0, 0.0, 0.0)
    v = as_vector(vector)
    return _Vec4(
        v.x / denominator, v.y / denominator, v.z / denominator, v.w / denominator
    )


def _dot(left, right):
    a, b = as_vector(left), as_vector(right)
    return a.x * b.x + a.y * b.y + a.z * b.z


def _cross(left, right):
    a, b = as_vector(left), as_vector(right)
    return _Vec4(
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x,
        1.0,
    )


def _length_sq(value):
    v = as_vector(value)
    return v.x * v.x + v.y * v.y + v.z * v.z


def _length(value):
    return math.sqrt(_length_sq(value))


def _norm(value):
    v = as_vector(value)
    magnitude = _length(v)
    if magnitude == 0.0:
        return v
    return _Vec4(v.x / magnitude, v.y / magnitude, v.z / magnitude, v.w)


def _lerp(left, right, weight):
    a, b, t = as_vector(left), as_vector(right), as_scalar(weight)
    return _Vec4(
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
        a.z + (b.z - a.z) * t,
        a.w + (b.w - a.w) * t,
    )


def _set_component(vector, index, value):
    data = list(as_vector(vector).tuple())
    data[index] = as_scalar(value)
    return _Vec4(*data)


def _set_pair(vector, first_index, second_index, first_value, second_value):
    data = list(as_vector(vector).tuple())
    data[first_index] = as_scalar(first_value)
    data[second_index] = as_scalar(second_value)
    return _Vec4(*data)


def _round_away_from_zero(value):
    value = as_scalar(value)
    if value >= 0.0:
        return float(math.floor(value + 0.5))
    return float(math.ceil(value - 0.5))


def _cbrt(value):
    value = as_scalar(value)
    return math.copysign(abs(value) ** (1.0 / 3.0), value)


def _truthy(value):
    return as_scalar(value) > _FLOAT_EPSILON


def _logical_and(left, right):
    return 1.0 if _truthy(left) and _truthy(right) else 0.0


def _logical_or(left, right):
    return 1.0 if _truthy(left) or _truthy(right) else 0.0


def _logical_xor(left, right):
    return 1.0 if _truthy(left) != _truthy(right) else 0.0


def _logical_not(value):
    return 0.0 if _truthy(value) else 1.0


def _equal(left, right):
    return 1.0 if abs(as_scalar(left) - as_scalar(right)) < _FLOAT_EPSILON else 0.0


def _compare(left, right, operation):
    a, b = as_scalar(left), as_scalar(right)
    return 1.0 if operation(a, b) else 0.0


def _axis_angle(axis, angle_degrees):
    vector = as_vector(axis)
    half = math.radians(as_scalar(angle_degrees)) * 0.5
    sine = math.sin(half)
    return _Quat(vector.x * sine, vector.y * sine, vector.z * sine, math.cos(half))


def _axis_quaternion(axis, angle_degrees):
    half = math.radians(as_scalar(angle_degrees)) * 0.5
    sine = math.sin(half)
    x, y, z = axis
    return _Quat(x * sine, y * sine, z * sine, math.cos(half))


def _rot_euler(roll_degrees, pitch_degrees, yaw_degrees):
    roll = _axis_quaternion((0.0, 1.0, 0.0), roll_degrees)
    pitch = _axis_quaternion((1.0, 0.0, 0.0), pitch_degrees)
    yaw = _axis_quaternion((0.0, 0.0, 1.0), yaw_degrees)
    return yaw * pitch * roll


def _quat_pitch(value):
    q = as_quaternion(value)
    y2, z2 = q.y * q.y, q.z * q.z
    unit_length = q.w * q.w + q.x * q.x + y2 + z2
    wxyz = q.w * q.x + q.y * q.z
    eps = 0.001
    if wxyz > (0.5 - eps) * unit_length:
        return 90.0
    if wxyz < (-0.5 + eps) * unit_length:
        return -90.0
    return math.degrees(math.asin(2.0 * wxyz / unit_length))


def _quat_yaw(value):
    q = as_quaternion(value)
    x2, z2 = q.x * q.x, q.z * q.z
    unit_length = q.w * q.w + x2 + q.y * q.y + z2
    wxyz = q.w * q.x + q.y * q.z
    eps = 0.001
    if wxyz > (0.5 - eps) * unit_length:
        return math.degrees(2.0 * math.atan2(q.y, q.w))
    if wxyz < (-0.5 + eps) * unit_length:
        return math.degrees(-2.0 * math.atan2(q.y, q.w))
    return math.degrees(
        math.atan2(2.0 * (q.w * q.z - q.x * q.y), 1.0 - 2.0 * (z2 + x2))
    )


def _quat_roll(value):
    q = as_quaternion(value)
    x2, y2 = q.x * q.x, q.y * q.y
    unit_length = q.w * q.w + x2 + y2 + q.z * q.z
    wxyz = q.w * q.x + q.y * q.z
    eps = 0.001
    if wxyz > (0.5 - eps) * unit_length or wxyz < (-0.5 + eps) * unit_length:
        return 0.0
    return math.degrees(
        math.atan2(2.0 * (q.w * q.y - q.x * q.z), 1.0 - 2.0 * (y2 + x2))
    )


def _degrees_sin(value):
    return math.sin(math.radians(as_scalar(value)))


def _degrees_cos(value):
    return math.cos(math.radians(as_scalar(value)))


def _degrees_tan(value):
    return math.tan(math.radians(as_scalar(value)))


def _degrees_asin(value):
    return math.degrees(math.asin(as_scalar(value)))


def _degrees_acos(value):
    return math.degrees(math.acos(as_scalar(value)))


def _degrees_atan(value):
    return math.degrees(math.atan(as_scalar(value)))


def _source_sign(value):
    return 1.0 if as_scalar(value) >= 0.0 else -1.0


def _operator_key(name, *types):
    return name, tuple(types)


_OPERATORS = {
    _operator_key("+", SCALAR, SCALAR): (
        SCALAR,
        lambda a, b: as_scalar(a) + as_scalar(b),
    ),
    _operator_key("-", SCALAR, SCALAR): (
        SCALAR,
        lambda a, b: as_scalar(a) - as_scalar(b),
    ),
    _operator_key("*", SCALAR, SCALAR): (
        SCALAR,
        lambda a, b: as_scalar(a) * as_scalar(b),
    ),
    _operator_key("/", SCALAR, SCALAR): (SCALAR, _float_div),
    _operator_key("^", SCALAR, SCALAR): (
        SCALAR,
        lambda a, b: math.pow(as_scalar(a), as_scalar(b)),
    ),
    _operator_key("%", SCALAR, SCALAR): (
        SCALAR,
        lambda a, b: math.fmod(as_scalar(a), as_scalar(b)),
    ),
    _operator_key("sin", SCALAR): (SCALAR, _degrees_sin),
    _operator_key("cos", SCALAR): (SCALAR, _degrees_cos),
    _operator_key("tan", SCALAR): (SCALAR, _degrees_tan),
    _operator_key("asin", SCALAR): (SCALAR, _degrees_asin),
    _operator_key("acos", SCALAR): (SCALAR, _degrees_acos),
    _operator_key("atan", SCALAR): (SCALAR, _degrees_atan),
    _operator_key("min", SCALAR, SCALAR): (
        SCALAR,
        lambda a, b: min(as_scalar(a), as_scalar(b)),
    ),
    _operator_key("max", SCALAR, SCALAR): (
        SCALAR,
        lambda a, b: max(as_scalar(a), as_scalar(b)),
    ),
    _operator_key("log", SCALAR): (SCALAR, lambda a: math.log(as_scalar(a))),
    _operator_key("log2", SCALAR): (
        SCALAR,
        lambda a: math.log(as_scalar(a)) / math.log(2.0),
    ),
    _operator_key("sqrt", SCALAR): (SCALAR, lambda a: math.sqrt(as_scalar(a))),
    _operator_key("cbrt", SCALAR): (SCALAR, _cbrt),
    _operator_key("abs", SCALAR): (SCALAR, lambda a: abs(as_scalar(a))),
    _operator_key("ceil", SCALAR): (SCALAR, lambda a: float(math.ceil(as_scalar(a)))),
    _operator_key("floor", SCALAR): (SCALAR, lambda a: float(math.floor(as_scalar(a)))),
    _operator_key("round", SCALAR): (SCALAR, _round_away_from_zero),
    _operator_key("#NEG", SCALAR): (SCALAR, lambda a: -as_scalar(a)),
    _operator_key("clamp", SCALAR, SCALAR, SCALAR): (
        SCALAR,
        lambda value, low, high: min(
            max(as_scalar(value), as_scalar(low)), as_scalar(high)
        ),
    ),
    _operator_key("sign", SCALAR): (SCALAR, _source_sign),
    _operator_key("Vec", SCALAR, SCALAR, SCALAR): (
        VECTOR,
        lambda x, y, z: _Vec4(as_scalar(x), as_scalar(y), as_scalar(z), 1.0),
    ),
    _operator_key("-", VECTOR, VECTOR): (VECTOR, _vector_sub),
    _operator_key("+", VECTOR, VECTOR): (VECTOR, _vector_add),
    _operator_key("*", VECTOR, SCALAR): (VECTOR, _vector_scale),
    _operator_key("*", SCALAR, VECTOR): (
        VECTOR,
        lambda scalar, vector: _vector_scale(vector, scalar),
    ),
    _operator_key("/", VECTOR, SCALAR): (VECTOR, _vector_div),
    _operator_key("/", SCALAR, VECTOR): (
        VECTOR,
        lambda scalar, vector: _vector_div(vector, scalar),
    ),
    _operator_key("dot", VECTOR, VECTOR): (SCALAR, _dot),
    _operator_key("cross", VECTOR, VECTOR): (VECTOR, _cross),
    _operator_key("length", VECTOR): (SCALAR, _length),
    _operator_key("lengthSq", VECTOR): (SCALAR, _length_sq),
    _operator_key("norm", VECTOR): (VECTOR, _norm),
    _operator_key("lerp", VECTOR, VECTOR, SCALAR): (VECTOR, _lerp),
    _operator_key("setX", VECTOR, SCALAR): (
        VECTOR,
        lambda v, f: _set_component(v, 0, f),
    ),
    _operator_key("setY", VECTOR, SCALAR): (
        VECTOR,
        lambda v, f: _set_component(v, 1, f),
    ),
    _operator_key("setZ", VECTOR, SCALAR): (
        VECTOR,
        lambda v, f: _set_component(v, 2, f),
    ),
    _operator_key("setXY", VECTOR, SCALAR, SCALAR): (
        VECTOR,
        lambda v, x, y: _set_pair(v, 0, 1, x, y),
    ),
    _operator_key("setYZ", VECTOR, SCALAR, SCALAR): (
        VECTOR,
        lambda v, y, z: _set_pair(v, 1, 2, y, z),
    ),
    _operator_key("setXZ", VECTOR, SCALAR, SCALAR): (
        VECTOR,
        lambda v, x, z: _set_pair(v, 0, 2, x, z),
    ),
    _operator_key("getX", VECTOR): (SCALAR, lambda v: as_vector(v).x),
    _operator_key("getY", VECTOR): (SCALAR, lambda v: as_vector(v).y),
    _operator_key("getZ", VECTOR): (SCALAR, lambda v: as_vector(v).z),
    _operator_key("Rot", VECTOR, SCALAR): (QUATERNION, _axis_angle),
    _operator_key("Rot", SCALAR, SCALAR, SCALAR): (QUATERNION, _rot_euler),
    _operator_key("getRoll", QUATERNION): (SCALAR, _quat_roll),
    _operator_key("getPitch", QUATERNION): (SCALAR, _quat_pitch),
    _operator_key("getYaw", QUATERNION): (SCALAR, _quat_yaw),
    _operator_key("&", SCALAR, SCALAR): (SCALAR, _logical_and),
    _operator_key("|", SCALAR, SCALAR): (SCALAR, _logical_or),
    _operator_key("xor", SCALAR, SCALAR): (SCALAR, _logical_xor),
    _operator_key("!", SCALAR): (SCALAR, _logical_not),
    _operator_key(">", SCALAR, SCALAR): (
        SCALAR,
        lambda a, b: _compare(a, b, lambda x, y: x > y),
    ),
    _operator_key("greater_or_equal", SCALAR, SCALAR): (
        SCALAR,
        lambda a, b: _compare(a, b, lambda x, y: x >= y),
    ),
    _operator_key("<", SCALAR, SCALAR): (
        SCALAR,
        lambda a, b: _compare(a, b, lambda x, y: x < y),
    ),
    _operator_key("less_or_equal", SCALAR, SCALAR): (
        SCALAR,
        lambda a, b: _compare(a, b, lambda x, y: x <= y),
    ),
    _operator_key("=", SCALAR, SCALAR): (SCALAR, _equal),
}


@dataclass(frozen=True)
class _LexToken:
    kind: str
    value: Any


@dataclass(frozen=True)
class _OpToken:
    name: str
    argc: int


@dataclass(frozen=True)
class ExpressionVariable:
    name: str
    kind: str
    variable_id: int


@dataclass(frozen=True)
class _Instruction:
    kind: str
    value: Any


def _is_name_char(char):
    return char.isalnum() or char in _NAME_CHARS


def _tokenize(formula):
    tokens = []
    index = 0
    length = len(formula)
    while index < length:
        char = formula[index]
        if char.isspace():
            index += 1
            continue
        if char.isdigit() or char == ".":
            end = index + 1
            while end < length and (formula[end].isdigit() or formula[end] == "."):
                end += 1
            text = formula[index:end]
            try:
                value = float(text)
            except ValueError as error:
                raise MathExpressionError(
                    f"Invalid MathExpression number {text!r} in {formula!r}"
                ) from error
            tokens.append(_LexToken("number", value))
            index = end
            continue
        if _is_name_char(char) and not char.isdigit():
            end = index + 1
            while end < length and _is_name_char(formula[end]):
                end += 1
            tokens.append(_LexToken("name", formula[index:end]))
            index = end
            continue
        if char in _OPERATOR_CHARS:
            tokens.append(_LexToken("operator", char))
            index += 1
            continue
        raise MathExpressionError(
            f"Unrecognized MathExpression token {char!r} in {formula!r}"
        )
    return tuple(tokens)


def _precedence(name):
    if name == "#NEG":
        return 5
    if name == "^":
        return 4
    if name in {"*", "/", "%"}:
        return 3
    if name in {"+", "-"}:
        return 2
    if name.startswith("FUNC:"):
        return 6
    return 0


def _to_rpn(formula):
    tokens = _tokenize(formula)
    if not tokens:
        raise MathExpressionError("MathExpression has no expressionString")
    output = []
    operators = []
    arg_counts = []
    previous_was_operator = True
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "number":
            output.append(token)
            previous_was_operator = False
        elif token.kind == "name":
            is_function = (
                index + 1 < len(tokens)
                and tokens[index + 1].kind == "operator"
                and tokens[index + 1].value == "("
            )
            if is_function:
                operators.append(_OpToken(f"FUNC:{token.value}", 0))
                previous_was_operator = True
            else:
                output.append(token)
                previous_was_operator = False
        else:
            symbol = token.value
            if symbol == "(":
                function_parenthesis = bool(
                    operators and operators[-1].name.startswith("FUNC:")
                )
                operators.append(_OpToken("(", 0))
                arg_counts.append(1 if function_parenthesis else 0)
                previous_was_operator = True
            elif symbol == ",":
                while operators and operators[-1].name != "(":
                    output.append(operators.pop())
                if not operators or not arg_counts or arg_counts[-1] <= 0:
                    raise MathExpressionError(
                        f"Invalid function argument separator in {formula!r}"
                    )
                arg_counts[-1] += 1
                previous_was_operator = True
            elif symbol == ")":
                while operators and operators[-1].name != "(":
                    output.append(operators.pop())
                if not operators:
                    raise MathExpressionError(
                        f"Opening bracket not found in {formula!r}"
                    )
                operators.pop()
                argc = arg_counts.pop() if arg_counts else 0
                if operators and operators[-1].name.startswith("FUNC:"):
                    function = operators.pop()
                    if previous_was_operator:
                        raise MathExpressionError(
                            f"Invalid empty function argument in {formula!r}"
                        )
                    output.append(_OpToken(function.name[5:], argc))
                previous_was_operator = False
            else:
                if previous_was_operator and symbol == "-":
                    name, argc = "#NEG", 1
                elif previous_was_operator and symbol == "!":
                    name, argc = "!", 1
                else:
                    name, argc = symbol, 1 if previous_was_operator else 2
                while (
                    operators
                    and operators[-1].name != "("
                    and not operators[-1].name.startswith("FUNC:")
                    and _precedence(operators[-1].name) >= _precedence(name)
                ):
                    output.append(operators.pop())
                operators.append(_OpToken(name, argc))
                previous_was_operator = True
        index += 1
    while operators:
        operator = operators.pop()
        if operator.name == "(":
            raise MathExpressionError(f"Missing closing bracket in {formula!r}")
        if operator.name.startswith("FUNC:"):
            raise MathExpressionError(f"Missing function argument list in {formula!r}")
        output.append(operator)
    return tuple(output)


def _variable_kind(name):
    if name.startswith("$"):
        return VECTOR
    if name.startswith("#"):
        return QUATERNION
    return SCALAR


def _bind_program(formula, rpn):
    type_stack = []
    variables = []
    variable_by_name = {}
    instructions = []
    for token in rpn:
        if isinstance(token, _LexToken) and token.kind == "number":
            type_stack.append(SCALAR)
            instructions.append(_Instruction("constant", float(token.value)))
            continue
        if isinstance(token, _LexToken) and token.kind == "name":
            variable = variable_by_name.get(token.value)
            if variable is None:
                variable = ExpressionVariable(
                    token.value, _variable_kind(token.value), len(variables)
                )
                variable_by_name[token.value] = variable
                variables.append(variable)
            type_stack.append(variable.kind)
            instructions.append(_Instruction("variable", variable))
            continue
        if not isinstance(token, _OpToken):
            raise MathExpressionError(
                f"Invalid compiled MathExpression token in {formula!r}"
            )
        if token.argc > len(type_stack):
            raise MathExpressionError(
                f"MathExpression operator {token.name!r} has too few arguments in {formula!r}"
            )
        argument_types = tuple(type_stack[-token.argc :]) if token.argc else ()
        if token.argc:
            del type_stack[-token.argc :]
        operator = _OPERATORS.get(_operator_key(token.name, *argument_types))
        if operator is None:
            rendered = ", ".join(argument_types) or "no arguments"
            raise MathExpressionError(
                f"Could not find matching MathExpression operator {token.name!r} for {rendered} in {formula!r}"
            )
        return_type, function = operator
        type_stack.append(return_type)
        instructions.append(
            _Instruction("operator", (token.name, token.argc, return_type, function))
        )
    if len(type_stack) != 1:
        raise MathExpressionError(
            f"MathExpression evaluates into multiple return types in {formula!r}"
        )
    return tuple(instructions), tuple(variables), type_stack[0]


@dataclass(frozen=True)
class ExpressionProgram:
    formula: str
    instructions: tuple[_Instruction, ...]
    variables: tuple[ExpressionVariable, ...]
    return_type: str

    def evaluate(self, values):
        stack = []
        try:
            for instruction in self.instructions:
                if instruction.kind == "constant":
                    stack.append(instruction.value)
                    continue
                if instruction.kind == "variable":
                    variable = instruction.value
                    if variable.name not in values:
                        raise MathExpressionError(
                            f"MathExpression input {variable.name!r} has no preview value"
                        )
                    value = values[variable.name]
                    actual_type = _value_type(value)
                    if actual_type != variable.kind:
                        raise MathExpressionError(
                            f"MathExpression variable {variable.name!r} expects {variable.kind}, got {actual_type}"
                        )
                    stack.append(value)
                    continue
                _name, argc, return_type, function = instruction.value
                if argc > len(stack):
                    raise MathExpressionError(
                        f"MathExpression {self.formula!r} execution stack underflow"
                    )
                arguments = stack[-argc:] if argc else []
                if argc:
                    del stack[-argc:]
                result = function(*arguments)
                if _value_type(result) != return_type:
                    raise MathExpressionError(
                        f"MathExpression operator {_name!r} returned the wrong type"
                    )
                stack.append(result)
            if len(stack) != 1:
                raise MathExpressionError(
                    f"MathExpression {self.formula!r} execution returned {len(stack)} values"
                )
            return stack[0]
        except MathExpressionError:
            raise
        except (ArithmeticError, TypeError, ValueError) as error:
            raise MathExpressionError(
                f"MathExpression {self.formula!r} failed: {error}"
            ) from error

    def evaluate_scalar(self, values):
        if self.return_type != SCALAR:
            raise MathExpressionError(
                f"MathExpression {self.formula!r} does not have a float return value"
            )
        return as_scalar(self.evaluate(values))

    def evaluate_vector(self, values):
        if self.return_type != VECTOR:
            raise MathExpressionError(
                f"MathExpression {self.formula!r} does not have a vector return value"
            )
        return as_vector(self.evaluate(values))

    def evaluate_quaternion(self, values):
        if self.return_type != QUATERNION:
            raise MathExpressionError(
                f"MathExpression {self.formula!r} does not have a quaternion return value"
            )
        return as_quaternion(self.evaluate(values))


@dataclass(frozen=True)
class ExpressionSocketBinding:
    name: str
    kind: str
    socket: Mapping


@lru_cache(maxsize=256)
def compile_expression(formula: str) -> ExpressionProgram:
    text = str(formula or "")
    rpn = _to_rpn(text)
    instructions, variables, return_type = _bind_program(text, rpn)
    return ExpressionProgram(text, instructions, variables, return_type)


@dataclass(frozen=True)
class _UncompiledExpression:
    """An expression saved without a program, evaluating to its type's default"""

    formula: str
    variables: tuple = ()

    def evaluate_scalar(self, values):
        return 0.0

    def evaluate_vector(self, values):
        return _Vec4(0.0, 0.0, 0.0, 0.0)

    def evaluate_quaternion(self, values):
        return _Quat(0.0, 0.0, 0.0, 1.0)


def compile_node_expression(node):
    data = node.get("expressionData") or {}
    formula = expression_string_value(node.get("expressionString"))
    try:
        expression = compile_expression(formula)
    except MathExpressionError:
        tokens = expression_payload(data).get("tokenData")
        if isinstance(tokens, list) and not tokens:
            # Text saved with empty token data has no program to run.
            return _UncompiledExpression(formula), ()
        raise
    socket_specs = (
        ("floatSockets", "float", SCALAR),
        ("vectorSockets", "vector", VECTOR),
        ("quaternionSockets", "quaternion", QUATERNION),
    )
    sockets = {}
    for array_name, binding_kind, value_kind in socket_specs:
        for socket in data.get(array_name) or ():
            variable_id = int(socket.get("expressionVarId", -1))
            if variable_id in sockets:
                raise MathExpressionError(
                    f"Duplicate MathExpression socket ID {variable_id}"
                )
            sockets[variable_id] = binding_kind, value_kind, socket
    expected_ids = {variable.variable_id for variable in expression.variables}
    if set(sockets) != expected_ids:
        raise MathExpressionError(
            f"MathExpression {expression.formula!r} socket IDs do not match its variables"
        )
    bindings = []
    for variable in expression.variables:
        binding_kind, value_kind, socket = sockets[variable.variable_id]
        if value_kind != variable.kind:
            raise MathExpressionError(
                f"MathExpression variable {variable.name!r} expects a {variable.kind} socket, got {value_kind}"
            )
        bindings.append(ExpressionSocketBinding(variable.name, binding_kind, socket))
    node_type = str(node.get("$type", "") or "")
    expected_return = {
        "animAnimNode_MathExpressionFloat": SCALAR,
        "animAnimNode_MathExpressionVector": VECTOR,
        "animAnimNode_MathExpressionQuaternion": QUATERNION,
    }.get(node_type)
    if expected_return is not None and expression.return_type != expected_return:
        raise MathExpressionError(
            f"MathExpression {expression.formula!r} returns {expression.return_type}, not {expected_return}"
        )
    return expression, tuple(bindings)


def math_expression_pose_data(node_type, node):
    return {
        "outputFloatTrack": index_name(
            node.get("outputFloatTrack"), "animNamedTrackIndex", allow_text=True
        ),
        "expressionString": node.get("expressionString", ""),
        "expressionData": node.get("expressionData") or {},
    }
