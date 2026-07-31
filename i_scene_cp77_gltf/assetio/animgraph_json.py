from __future__ import annotations

import json
import sys
from typing import Any


def maximum_depth(root: Any) -> int:
    maximum = 0
    stack = [(root, 1)]
    while stack:
        value, depth = stack.pop()
        maximum = max(maximum, depth)
        if isinstance(value, dict):
            stack.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
    return maximum


def loads(text: str) -> Any:
    old_limit = sys.getrecursionlimit()
    try:
        if old_limit < 10000:
            sys.setrecursionlimit(10000)
        return json.loads(text)
    finally:
        if sys.getrecursionlimit() != old_limit:
            sys.setrecursionlimit(old_limit)


def load_file(filepath: str) -> Any:
    with open(filepath, 'r', encoding='utf-8-sig') as stream:
        return loads(stream.read())


def dumps(value: Any, *, indent: int = 2) -> str:
    old_limit = sys.getrecursionlimit()
    required = max(old_limit, maximum_depth(value) * 4 + 1000)
    try:
        if required != old_limit:
            sys.setrecursionlimit(required)
        return json.dumps(value, ensure_ascii=False, indent=indent)
    finally:
        if sys.getrecursionlimit() != old_limit:
            sys.setrecursionlimit(old_limit)


def dump_file(filepath: str, value: Any, *, indent: int = 2) -> None:
    with open(filepath, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(dumps(value, indent=indent))
        stream.write('\n')
