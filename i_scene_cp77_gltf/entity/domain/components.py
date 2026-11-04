from __future__ import annotations

import copy
from collections import Counter
from dataclasses import replace

from ...assetio.cruids import new_cruid, rebuild_cruid_dict
from ...assetio.handles import hand_over_definitions
from ...assetio.values import (
    cname_entry,
    cname_or_empty,
    cname_text,
    handle_data,
    resource_path_entry,
    resource_path_text,
)
from ..model.component_types import MESH_TYPES, SKINNED_TYPES, type_key
from ..model.edits import AppearanceEdit, Binding, ComponentEdit, ComponentKey
from .chunks import mask_text, parse_mask
from .document import (
    AppearanceDocument,
    ComponentPair,
    binding_of,
    component_name,
    skin_of,
)

_VISUAL_CONTROLLER = "entVisualControllerComponent"
_HARD_BINDING = "entHardTransformBinding"
_SKINNING_BINDING = "entSkinningBinding"
_EDITED_KEYS = frozenset(
    {
        "$type",
        "name",
        "id",
        "isEnabled",
        "mesh",
        "meshAppearance",
        "chunkMask",
        "parentTransform",
        "skinning",
    }
)


def component_key(component: dict) -> ComponentKey:
    return ComponentKey(component_name(component), str(component.get("id", "")))


def component_edit_from(pair: ComponentPair, handles) -> ComponentEdit | None:
    """A mesh component's current values as an edit, or None for other components"""
    listed = pair.listed
    key = type_key(listed.get("$type"))
    if key is None:
        return None
    return ComponentEdit(
        key=component_key(listed),
        template=None,
        name=component_name(listed),
        enabled=bool(listed.get("isEnabled", 1)),
        type_key=key,
        mesh=resource_path_text(listed.get("mesh")),
        mesh_appearance=cname_text(listed.get("meshAppearance")),
        chunk_mask=parse_mask(listed.get("chunkMask")),
        attach=binding_of(listed, handles),
        skin=skin_of(listed, handles),
    )


def _walk(value):
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            yield current
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


def document_cruids(app: AppearanceDocument) -> set[str]:
    """Every component id in the document"""
    return {
        str(pair.listed["id"])
        for name in app.appearance_names()
        for pair in app.components(name)
        if "id" in pair.listed
    } | {
        str(chunk["id"])
        for name in app.appearance_names()
        for chunk in (app.package(name) or {}).get("Chunks") or ()
        if isinstance(chunk, dict) and "id" in chunk
    }


def _copies(pair: ComponentPair) -> tuple[dict, ...]:
    return tuple(copy_ for copy_ in (pair.compiled, pair.listed) if copy_ is not None)


class _AppearanceEditor:
    def __init__(
        self, app: AppearanceDocument, appearance: str, taken_cruids: set[str]
    ):
        self.app = app
        self.appearance = appearance
        self.taken_cruids = taken_cruids
        self.definition = app.definition(appearance)
        if self.definition is None:
            raise KeyError(f"Appearance '{appearance}' is not in the .app")
        self.package = app.package(appearance)
        self.structure_changed = False

    def pairs(self) -> tuple[ComponentPair, ...]:
        return self.app.components(self.appearance)

    def find(self, key: ComponentKey) -> ComponentPair | None:
        pairs = self.pairs()
        exact = next(
            (pair for pair in pairs if component_key(pair.listed) == key), None
        )
        return exact or next(
            (pair for pair in pairs if component_name(pair.listed) == key.name), None
        )

    def find_template(self, key: ComponentKey) -> ComponentPair | None:
        found = self.find(key)
        if found is not None:
            return found
        for name in self.app.appearance_names():
            for pair in self.app.components(name):
                if component_key(pair.listed) == key:
                    return pair
        return None

    def _type_template(self, red_type: str) -> dict | None:
        for name in self.app.appearance_names():
            for pair in self.app.components(name):
                if pair.listed.get("$type") == red_type:
                    return pair.listed
        return None

    def remove(self, pair: ComponentPair) -> None:
        hand_over_definitions(
            self.app.document, [pair.listed, pair.compiled], excluded=_copies(pair)
        )
        self.definition["components"] = [
            entry
            for entry in self.definition.get("components") or ()
            if handle_data(entry) is not pair.listed
        ]
        if self.package is not None and pair.compiled is not None:
            self.package["Chunks"] = [
                chunk
                for chunk in self.package.get("Chunks") or ()
                if chunk is not pair.compiled
            ]
        self.structure_changed = True

    def add(self, template: ComponentPair, name: str) -> ComponentPair:
        copied = self.app.handles.rehandle(
            {"listed": template.listed, "compiled": template.compiled}
        )
        pair = ComponentPair(
            copied["listed"], copied["compiled"] if self.package is not None else None
        )
        cruid = new_cruid(self.taken_cruids)
        for copy_ in _copies(pair):
            copy_["id"] = cruid
            copy_["name"] = cname_entry(name, copy_.get("name"))
        self._insert(self.definition.setdefault("components", []), pair.listed)
        if pair.compiled is not None:
            self._insert(self.package.setdefault("Chunks", []), pair.compiled)
        self.structure_changed = True
        return pair

    @staticmethod
    def _insert(entries: list, value: dict) -> None:
        index = next(
            (
                i
                for i, entry in enumerate(entries)
                if handle_data(entry).get("$type") == _VISUAL_CONTROLLER
            ),
            len(entries),
        )
        entries.insert(index, value)

    def rename(self, pair: ComponentPair, new_name: str) -> None:
        old_name = component_name(pair.listed)
        for copy_ in _copies(pair):
            copy_["name"] = cname_entry(new_name, copy_.get("name"))
        seen = set()
        for other in self.pairs():
            for copy_ in _copies(other):
                for key in ("parentTransform", "skinning"):
                    data = self.app.handles.resolve(copy_.get(key))
                    if not data or id(data) in seen:
                        continue
                    seen.add(id(data))
                    if cname_or_empty(data.get("bindName")) == old_name:
                        data["bindName"] = cname_entry(new_name, data.get("bindName"))

    def update(self, pair: ComponentPair, edit: ComponentEdit) -> None:
        if type_key(pair.listed.get("$type")) != edit.type_key:
            self._change_type(pair, edit.type_key)
        for copy_ in _copies(pair):
            if bool(copy_.get("isEnabled", 1)) != edit.enabled:
                copy_["isEnabled"] = 1 if edit.enabled else 0
            if resource_path_text(copy_.get("mesh")) != edit.mesh:
                flags = (
                    (copy_.get("mesh") or {}).get("Flags", "Default")
                    if isinstance(copy_.get("mesh"), dict)
                    else "Default"
                )
                copy_["mesh"] = resource_path_entry(edit.mesh, flags)
            if cname_text(copy_.get("meshAppearance")) != edit.mesh_appearance:
                copy_["meshAppearance"] = cname_entry(
                    edit.mesh_appearance, copy_.get("meshAppearance")
                )
            if parse_mask(copy_.get("chunkMask")) != edit.chunk_mask:
                copy_["chunkMask"] = mask_text(edit.chunk_mask)
        if binding_of(pair.listed, self.app.handles) != edit.attach:
            if edit.attach is None:
                self._drop(pair, "parentTransform")
            else:
                self._set_binding(
                    pair,
                    "parentTransform",
                    _HARD_BINDING,
                    edit.attach.target,
                    edit.attach.slot,
                )
        skin = edit.skin if edit.type_key in SKINNED_TYPES else ""
        if skin_of(pair.listed, self.app.handles) != skin:
            if not skin:
                self._drop(pair, "skinning")
            else:
                self._set_binding(pair, "skinning", _SKINNING_BINDING, skin, None)

    def _change_type(self, pair: ComponentPair, new_key: str) -> None:
        red_type = MESH_TYPES[new_key]
        template = self._type_template(red_type)
        for copy_ in _copies(pair):
            copy_["$type"] = red_type
            if template is None:
                continue
            for key in [
                key for key in copy_ if key not in template and key not in _EDITED_KEYS
            ]:
                del copy_[key]
            for key, value in template.items():
                if key not in copy_ and key not in _EDITED_KEYS:
                    copy_[key] = self.app.handles.rehandle(value)
        if new_key not in SKINNED_TYPES:
            self._drop(pair, "skinning")

    def _drop(self, pair: ComponentPair, key: str) -> None:
        held = [copy_[key] for copy_ in _copies(pair) if key in copy_]
        hand_over_definitions(self.app.document, held, excluded=_copies(pair))
        for copy_ in _copies(pair):
            copy_.pop(key, None)

    def _reference_counts(self) -> Counter:
        return Counter(
            str(node["HandleRefId"])
            for node in _walk(self.app.document)
            if "HandleRefId" in node
        )

    def _shared_outside(self, pair: ComponentPair, key: str) -> bool:
        """Whether the pair's binding handle is also referenced by something other than the pair's other copy"""
        handle_ids = {
            str(value.get("HandleId", value.get("HandleRefId", "")))
            for copy_ in _copies(pair)
            for value in (copy_.get(key),)
            if isinstance(value, dict)
        }
        own_references = Counter(
            str(copy_[key]["HandleRefId"])
            for copy_ in _copies(pair)
            if isinstance(copy_.get(key), dict) and "HandleRefId" in copy_[key]
        )
        counts = self._reference_counts()
        return any(
            counts[handle_id] > own_references[handle_id] for handle_id in handle_ids
        )

    def _binding_template(self, binding_type: str) -> dict:
        for node in _walk(self.app.document):
            data = node.get("Data") if "HandleId" in node else None
            if isinstance(data, dict) and data.get("$type") == binding_type:
                return copy.deepcopy(data)
        if binding_type == _HARD_BINDING:
            return {
                "$type": binding_type,
                "bindName": cname_entry("None"),
                "slotName": cname_entry("None"),
            }
        return {"$type": binding_type, "bindName": cname_entry("None")}

    def _set_binding(
        self,
        pair: ComponentPair,
        key: str,
        binding_type: str,
        target: str,
        slot: str | None,
    ) -> None:
        data = self.app.handles.resolve(pair.listed.get(key))
        if not data or self._shared_outside(pair, key):
            held = [copy_[key] for copy_ in _copies(pair) if key in copy_]
            hand_over_definitions(self.app.document, held, excluded=_copies(pair))
            data = (
                self._binding_template(binding_type)
                if not data
                else copy.deepcopy(data)
            )
            holder, referrer = (
                (pair.compiled, pair.listed)
                if pair.compiled is not None
                else (pair.listed, None)
            )
            handle = self.app.handles.wrap(data)
            holder[key] = handle
            if referrer is not None:
                referrer[key] = self.app.handles.reference(handle["HandleId"])
        data["bindName"] = cname_entry(target, data.get("bindName"))
        if slot is not None:
            data["slotName"] = cname_entry(slot or "None", data.get("slotName"))


def _follow_renames(edit: ComponentEdit, renames: dict[str, str]) -> ComponentEdit:
    """Attach and skin targets that still name a renamed component's old name follow it to its new name"""
    attach = edit.attach
    if attach is not None and attach.target in renames:
        attach = Binding(renames[attach.target], attach.slot)
    skin = renames.get(edit.skin, edit.skin)
    if attach == edit.attach and skin == edit.skin:
        return edit
    return replace(edit, attach=attach, skin=skin)


def apply_appearance_edit(
    app: AppearanceDocument, edit: AppearanceEdit, *, taken_cruids: set[str]
) -> None:
    editor = _AppearanceEditor(app, edit.name, taken_cruids)
    final_names = {component.name for component in edit.components}
    renames = {
        component.key.name: component.name
        for component in edit.components
        if component.key is not None
        and component.key.name != component.name
        and component.key.name not in final_names
    }
    for key in edit.removed:
        pair = editor.find(key)
        if pair is not None:
            editor.remove(pair)
    for component in edit.components:
        if component.key is None:
            continue
        pair = editor.find(component.key)
        if pair is None:
            raise KeyError(
                f"Component '{component.key.name}' is not in appearance '{edit.name}'"
            )
        if component_name(pair.listed) != component.name:
            editor.rename(pair, component.name)
        editor.update(pair, _follow_renames(component, renames))
    for component in edit.components:
        if component.key is not None:
            continue
        template = (
            editor.find_template(component.template)
            if component.template is not None
            else None
        )
        if template is None:
            raise KeyError(
                f"Added component '{component.name}' has no template component"
            )
        editor.update(
            editor.add(template, component.name), _follow_renames(component, renames)
        )
    if editor.structure_changed and editor.package is not None:
        rebuild_cruid_dict(editor.package)
