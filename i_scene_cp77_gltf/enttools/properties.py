from __future__ import annotations

import zlib

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from ..entity.model.component_types import MESH_TYPES, TYPE_LABELS
from .runtime.scene_cache import entity_index
from .runtime.updates import updates_suspended

TYPE_ITEMS = tuple((key, TYPE_LABELS[key], MESH_TYPES[key]) for key in MESH_TYPES)


def _field_changed(field):
    def update(self, context):
        if updates_suspended():
            return
        from .services.components import field_changed

        field_changed(context, self, field)

    return update


def _tools_changed(field):
    def update(self, context):
        if updates_suspended():
            return
        from .services.selection import tools_changed

        tools_changed(context, field)

    return update


_ITEM_CACHE: dict[str, tuple] = {}


def _cached_items(owner, key, items):
    """Dynamic enum items, each numbered from its identifier"""
    numbered = tuple(
        (
            identifier,
            label,
            description,
            "NONE",
            zlib.crc32(identifier.encode("utf-8")) & 0x7FFFFFFF,
        )
        for identifier, label, description in items
    )
    stored = owner.get(key, 0)
    if not any(item[4] == stored for item in numbered):
        numbered = (("__NONE__", "None", "", "NONE", stored), *numbered)
    # Blender keeps no reference to dynamic enum strings; holding them here keeps them alive.
    _ITEM_CACHE[key] = numbered
    return numbered


def _entity_items(self, context):
    return _cached_items(
        self,
        "entity",
        ((ref.import_id, ref.label, ref.ent_path) for ref in entity_index().entities),
    )


def _appearance_items(self, context):
    from .services.selection import appearance_choices

    return _cached_items(self, "appearance", appearance_choices(self.entity))


class CP77EntityComponentState(PropertyGroup):
    key_name: StringProperty(options={"HIDDEN"})
    key_cruid: StringProperty(options={"HIDDEN"})
    template_name: StringProperty(options={"HIDDEN"})
    template_cruid: StringProperty(options={"HIDDEN"})
    name: StringProperty(
        name="Name",
        description="The component's name in the appearance (name)",
        update=_field_changed("name"),
    )
    enabled: BoolProperty(
        name="Enabled",
        default=True,
        description="isEnabled",
        update=_field_changed("enabled"),
    )
    type_key: EnumProperty(
        name="Type", items=TYPE_ITEMS, update=_field_changed("type_key")
    )
    mesh: StringProperty(options={"HIDDEN"})
    mesh_collection: PointerProperty(type=bpy.types.Collection, name="Mesh")
    mesh_collection_name: StringProperty(options={"HIDDEN"})
    base_mesh: StringProperty(
        name="Base Mesh",
        description="The game mesh this mesh is exported over (a copy of it is made under the new name)",
    )
    mesh_appearance: StringProperty(
        name="Mesh Appearance",
        description="meshAppearance",
        update=_field_changed("mesh_appearance"),
    )
    chunk_mask: StringProperty(options={"HIDDEN"})
    attach_target: StringProperty(
        name="Attach To",
        description="parentTransform bindName",
        update=_field_changed("attach"),
    )
    attach_slot: StringProperty(
        name="Slot",
        description="parentTransform slotName",
        update=_field_changed("attach"),
    )
    skin_target: StringProperty(
        name="Deform With",
        description="skinning bindName",
        update=_field_changed("skin"),
    )
    removed: BoolProperty(options={"HIDDEN"})
    applied: StringProperty(options={"HIDDEN"})


class CP77EntityAppearanceState(PropertyGroup):
    initialized: BoolProperty(options={"HIDDEN"})
    name: StringProperty(name="Appearance")
    entry_name: StringProperty(
        name="Entry Name", description="The entity's appearance entry name (name)"
    )
    source_name: StringProperty(options={"HIDDEN"})
    origin: StringProperty(options={"HIDDEN"})
    is_default: BoolProperty(options={"HIDDEN"})
    removed: BoolProperty(options={"HIDDEN"})
    components: CollectionProperty(type=CP77EntityComponentState)


class CP77EntityChoice(PropertyGroup):
    name: StringProperty()


class CP77EntityIssue(PropertyGroup):
    appearance: StringProperty()
    component: StringProperty()
    message: StringProperty()


class CP77EntityToolsState(PropertyGroup):
    entity: EnumProperty(
        name="Entity", items=_entity_items, update=_tools_changed("entity")
    )
    appearance: EnumProperty(
        name="Appearance", items=_appearance_items, update=_tools_changed("appearance")
    )
    component_index: IntProperty(
        name="Component", default=0, min=0, update=_tools_changed("component_index")
    )
    issues: CollectionProperty(type=CP77EntityIssue)
    issue_index: IntProperty(default=0, min=0, update=_tools_changed("issue_index"))
    attach_choices: CollectionProperty(type=CP77EntityChoice)
    slot_choices: CollectionProperty(type=CP77EntityChoice)
    rig_choices: CollectionProperty(type=CP77EntityChoice)
    choices_key: StringProperty(options={"HIDDEN"})


ENTITY_PROPERTY_CLASSES = (
    CP77EntityComponentState,
    CP77EntityAppearanceState,
    CP77EntityChoice,
    CP77EntityIssue,
    CP77EntityToolsState,
)
