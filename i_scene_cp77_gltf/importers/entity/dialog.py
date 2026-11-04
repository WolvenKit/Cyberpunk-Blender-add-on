from __future__ import annotations

from dataclasses import dataclass

from ..common import dialog_model
from ..common.dialog_model import Category

ENTITY_CHOICES = (
    "lights",
    "light_linking",
    "light_channel_volumes",
    "gameplay_animations",
    "facial_setup",
    "facial_animations",
    "collider_components",
    "mesh_colliders",
    "phys_collisions",
    "screens",
)

CATEGORIES = (
    Category(
        "lighting", "Lighting", ("lights", "light_linking", "light_channel_volumes")
    ),
    Category(
        "animation",
        "Animation",
        ("gameplay_animations", "facial_setup", "facial_animations"),
    ),
    Category(
        "collisions",
        "Collisions",
        ("collider_components", "mesh_colliders", "phys_collisions"),
    ),
    Category("screens", "Screens", ("screens",)),
)
CATEGORY_NAMES = frozenset(category.name for category in CATEGORIES)

CHOICE_LABELS = {
    "lights": "Lights",
    "light_linking": "Light Linking",
    "light_channel_volumes": "Light Channel Volumes",
    "gameplay_animations": "Gameplay Animations",
    "facial_setup": "Facial Setup",
    "facial_animations": "Facial Animations",
    "collider_components": "Collider Components",
    "mesh_colliders": "Mesh Colliders",
    "phys_collisions": ".phys Collisions",
    "screens": "Screens",
}

# Tooltips: what each button and tick imports, with the component types it covers.
CATEGORY_DESCRIPTIONS = {
    "lighting": "The entity's lights and its light-channel components",
    "animation": "The entity's gameplay animations and facial setup",
    "collisions": "The entity's collider components, the colliders built into its meshes, and its .phys resources",
    "screens": "WorldWidgetComponent resources and ink animations, bound to their target meshes",
}
CHOICE_DESCRIPTIONS = {
    "lights": "Import entLightComponent, vehicleLightComponent and gameLightComponent lights and their IES profiles",
    "light_linking": "Link the lights through the entity's entLightChannelComponents, without keeping the volume objects",
    "light_channel_volumes": "Keep the entLightChannelComponent volume objects",
    "gameplay_animations": (
        "Import the first exported gameplay animation set declared by the entity onto its rig; the rig stays in its "
        "rest pose"
    ),
    "facial_setup": "Locate the entity's facial setup export and bind it to the imported rig",
    "facial_animations": (
        "Also import the first exported animation set that targets the facial rig; facial sets are large and can take "
        "noticeably longer"
    ),
    "collider_components": "Import entColliderComponent and entSimpleColliderComponent",
    "mesh_colliders": "Import the physics built into the entity's meshes",
    "phys_collisions": "Import the .phys resources, such as a vehicle chassis",
    "screens": "Import WorldWidgetComponent resources and bind them to their target meshes",
}

# The ticks a category brings the first time it is switched on.
STARTING_CHOICES = frozenset(
    {"lights", "light_linking", "gameplay_animations", "collider_components"}
)

IMPORT_SETTINGS = (
    "materials",
    "proxies",
    "occluders",
    "shadow_meshes",
    "refresh_index",
)
_COLLISION_CHOICES = frozenset(
    {"collider_components", "mesh_colliders", "phys_collisions"}
)
_MEMORY_KEY = "entity_import_choices"


@dataclass(frozen=True, slots=True)
class EntityDialogState:
    materials: bool
    proxies: bool
    occluders: bool
    shadow_meshes: bool
    refresh_index: bool
    categories: frozenset[str]
    choices: frozenset[str]

    @classmethod
    def default(cls):
        return cls(
            materials=True,
            proxies=False,
            occluders=False,
            shadow_meshes=False,
            refresh_index=False,
            categories=frozenset(),
            choices=STARTING_CHOICES,
        )

    def to_json(self):
        return dialog_model.memory_json(self)

    @classmethod
    def from_json(cls, text):
        """The state in text"""
        return dialog_model.read_memory(
            text,
            cls.default(),
            flags=IMPORT_SETTINGS,
            sets={"categories": CATEGORY_NAMES, "choices": frozenset(ENTITY_CHOICES)},
        )

    def effective_choices(self):
        """The ticked choices of the switched-on categories"""
        return dialog_model.effective_choices(CATEGORIES, self.categories, self.choices)

    def inactive_choices(self):
        # Facial animations play on the facial rig, which only Facial Setup brings.
        return (
            frozenset()
            if "facial_setup" in self.effective_choices()
            else frozenset({"facial_animations"})
        )

    def request_fields(self):
        """The EntityImportRequest fields these choices ask for"""
        chosen = self.effective_choices()
        return {
            "with_materials": self.materials,
            "include_proxies": self.proxies,
            "include_occluders": self.occluders,
            "include_shadow_meshes": self.shadow_meshes,
            "include_lights": "lights" in chosen,
            "include_light_channels": bool(
                {"light_linking", "light_channel_volumes"} & chosen
            ),
            "link_lights": "light_linking" in chosen,
            "keep_light_channel_volumes": "light_channel_volumes" in chosen,
            "include_animations": "gameplay_animations" in chosen,
            "include_facial_setup": "facial_setup" in chosen,
            "include_facial_animations": {"facial_animations", "facial_setup"}
            <= chosen,
            "include_collisions": bool(_COLLISION_CHOICES & chosen),
            "include_entity_colliders": "collider_components" in chosen,
            "include_mesh_colliders": "mesh_colliders" in chosen,
            "include_phys": "phys_collisions" in chosen,
            "include_inkwidgets": "screens" in chosen,
        }


def appearance_rows(names):
    """The appearance list's rows"""
    if len(names) < 2:
        return ("default",)
    others = sorted(
        {str(name) for name in names if str(name).casefold() != "default"},
        key=str.casefold,
    )
    return ("default", *others)


def remembered_state(preferences):
    return EntityDialogState.from_json(
        dialog_model.remembered_text(preferences, _MEMORY_KEY)
    )


def remember_state(preferences, state):
    dialog_model.remember_text(preferences, _MEMORY_KEY, state.to_json())
