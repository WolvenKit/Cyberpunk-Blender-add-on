from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from .values import coerce_int


def _walk_handles(value: Any, visit) -> None:
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if "HandleId" in current:
                visit(current)
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


def _handle_number(value: Any) -> int:
    return coerce_int(value, -1, unwrap=False)


def resolve_handle(value: Any, data_by_handle: Mapping[str, dict]) -> Any:
    if not isinstance(value, dict):
        return value
    if isinstance(value.get("Data"), dict):
        return value["Data"]
    if "HandleRefId" in value:
        return data_by_handle.get(str(value["HandleRefId"]))
    return value


class HandleIndex:
    """The handles of one document, for resolving references and allocating new ids"""

    __slots__ = ("_data", "_next")

    def __init__(self):
        self._data: dict[str, dict] = {}
        self._next = 0

    @classmethod
    def build(cls, document: Any) -> HandleIndex:
        index = cls()
        _walk_handles(document, index._add)
        return index

    def _add(self, handle: dict) -> None:
        handle_id = str(handle["HandleId"])
        data = handle.get("Data")
        self._data[handle_id] = data if isinstance(data, dict) else {}
        self._next = max(self._next, _handle_number(handle_id) + 1)

    def resolve(self, value: Any) -> dict:
        """The data a handle or handle reference stands for"""
        if not isinstance(value, dict) or not (
            "HandleRefId" in value or "HandleId" in value
        ):
            return {}
        data = resolve_handle(value, self._data)
        return data if isinstance(data, dict) and data is not value else {}

    def allocate(self) -> str:
        value = str(self._next)
        self._next += 1
        return value

    def wrap(self, data: dict) -> dict:
        """A new handle holding data"""
        handle = {"HandleId": self.allocate(), "Data": data}
        self._data[handle["HandleId"]] = data
        return handle

    @staticmethod
    def reference(handle_id: str) -> dict:
        return {"HandleRefId": str(handle_id)}

    def rehandle(self, value: Any) -> Any:
        """A deep copy of value whose handles get fresh ids"""
        copied = copy.deepcopy(value)
        renamed: dict[str, str] = {}

        def renumber(handle):
            new_id = self.allocate()
            renamed[str(handle["HandleId"])] = new_id
            handle["HandleId"] = new_id

        _walk_handles(copied, renumber)
        stack = [copied]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                reference = current.get("HandleRefId")
                if reference is not None and str(reference) in renamed:
                    current["HandleRefId"] = renamed[str(reference)]
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)
        _walk_handles(copied, self._add)
        return copied

    def standalone(self, value: Any) -> Any:
        """A deep copy of value that reads on its own in another document"""
        defined: set[str] = set()

        def copied(current):
            if isinstance(current, dict):
                reference = current.get("HandleRefId")
                if reference is not None and str(reference) not in defined:
                    if str(reference) not in self._data:
                        raise ValueError(
                            f"handle {reference} is not defined in its document"
                        )
                    current = {
                        "HandleId": str(reference),
                        "Data": self._data[str(reference)],
                    }
                if "HandleId" in current:
                    defined.add(str(current["HandleId"]))
                return {key: copied(item) for key, item in current.items()}
            if isinstance(current, list):
                return [copied(item) for item in current]
            return current

        return copied(value)


def _references_in_order(value, handle_id: str):
    """(container, key) of every reference to handle_id, in the order the document serializes them"""
    stack = [(None, None, value)]
    while stack:
        container, key, current = stack.pop()
        if isinstance(current, dict):
            if (
                str(current.get("HandleRefId", "")) == handle_id
                and container is not None
            ):
                yield container, key
            stack.extend(
                (current, child_key, child)
                for child_key, child in reversed(list(current.items()))
            )
        elif isinstance(current, list):
            stack.extend(
                (current, index, child)
                for index, child in reversed(list(enumerate(current)))
            )


def hand_over_definitions(document, value, *, excluded=()) -> None:
    """Move each handle defined inside value to its next reference before value is removed or replaced"""
    definitions = []
    _walk_handles(value, definitions.append)
    for definition in definitions:
        handle_id = str(definition["HandleId"])
        for container, key in _references_in_order(document, handle_id):
            if any(_contains(owner, container) for owner in excluded):
                continue
            container[key] = {
                "HandleId": definition["HandleId"],
                "Data": definition.get("Data"),
            }
            break


def _contains(owner, target) -> bool:
    stack = [owner]
    while stack:
        current = stack.pop()
        if current is target:
            return True
        if isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return False
