import math
import sys
import time

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty
from bpy.types import PropertyGroup, Scene

from .core.registration import get_classes, RegistrationLedger
from .meshtools.vertex_color_presets import preset_enum_items
from .meshtools.refit_catalog import refitter_enum_items
from .animtools.runtime.read_models import bundled_rig_items

_ENUM_CACHE_TTL = 2.0
_ENUM_CACHE = {
    "collections": {"expires": 0.0, "signature": None, "items": ()},
    "armatures": {"expires": 0.0, "signature": None, "items": ()},
}
_EXCLUDED_COLLECTION_NAMES = frozenset({
    "Collection",
    "Scene Collection",
    "glTF_not_exported",
})


def _cached_enum_items(cache_name, signature, builder):
    cache = _ENUM_CACHE[cache_name]
    now = time.monotonic()
    if cache["signature"] != signature or now >= cache["expires"]:
        cache["items"] = tuple(builder())
        cache["signature"] = signature
        cache["expires"] = now + _ENUM_CACHE_TTL
    return cache["items"]


def SetCyclesRenderer(use_cycles=True, set_gi_params=False, scene=None):
    """Switch one scene to GPU Cycles and return the changes made"""
    changes = []
    if not use_cycles:
        return changes
    scene = scene or bpy.context.scene
    if scene.render.engine != 'CYCLES' or scene.cycles.device != 'GPU':
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'GPU'
        changes.append(f"Scene '{scene.name}' now renders with Cycles on the GPU")
    if set_gi_params and scene.cycles.transparent_max_bounces != 40:
        scene.cycles.transparent_max_bounces = 40
        changes.append(f"Scene '{scene.name}' transparent light paths increased to 40")
    return changes


def SetVulkanBackend(use_vulkan=True):
    """Select the Vulkan GPU backend in the user preferences and return the changes made"""
    if not use_vulkan:
        return []
    system_prefs = bpy.context.preferences.system
    if system_prefs.gpu_backend == 'VULKAN':
        return []
    system_prefs.gpu_backend = 'VULKAN'
    return ["GPU backend preference set to Vulkan; restart Blender to apply it"]


def CP77CollectionList(self, context):
    """Return mesh collection enum items without rescanning on every panel draw"""
    signature = (len(bpy.data.collections), len(bpy.data.objects))

    def build_items():
        for collection in bpy.data.collections:
            if collection.name in _EXCLUDED_COLLECTION_NAMES:
                continue
            if any(obj.type == 'MESH' for obj in collection.objects):
                yield (collection.name, collection.name, "")

    return _cached_enum_items("collections", signature, build_items)


def CP77ArmatureList(self, context):
    """Return armature enum items without rescanning on every panel draw"""
    signature = len(bpy.data.objects)
    return _cached_enum_items(
        "armatures",
        signature,
        lambda: (
            (obj.name, obj.name, "")
            for obj in bpy.data.objects
            if obj.type == 'ARMATURE'
        ),
    )


class CP77_PT_PanelProps(PropertyGroup):
    """Property definitions for the main addon UI panel"""

    vertex_color_presets: EnumProperty(
            name="Vertex Color Preset",
            items=preset_enum_items,
            )

    frameall: BoolProperty(
            name="All Frames",
            default=False,
            description="Insert a keyframe on every frame of the active action"
            )

    body_list: EnumProperty(
            items=bundled_rig_items,
            name="Bundled Rig"
            )

    fbx_rot: BoolProperty(
            name="",
            default=False,
            description="Rotate for an fbx orientated mesh"
            )

    refit_json: EnumProperty(
            items=refitter_enum_items(),
            name="Body Shape"
            )

    refit_addon_json: EnumProperty(
            items=refitter_enum_items(addon=True),
            name="Refitter Addon"
            )

    selected_armature: EnumProperty(
            name="Armatures",
            items=CP77ArmatureList
            )

    mesh_source: EnumProperty(
            items=CP77CollectionList
            )

    mesh_target: EnumProperty(
            items=CP77CollectionList
            )

    merge_distance: FloatProperty(
            name="Merge Distance",
            default=0.0001,
            min=0.0,
            max=1.0
            )

    smooth_factor: FloatProperty(
            name="Smooth Angle",
            description="Edges whose faces meet at a sharper angle than this stay sharp",
            subtype='ANGLE',
            default=0.5,
            min=0.0,
            max=math.pi
            )

    remap_depot: BoolProperty(
            name="Remap Depot",
            default=False,
            description="replace the json depot path with the one in prefs"
            )

    use_cycles: BoolProperty(
            name="Set Render Engine to Cycles",
            default=False,
            description="Sets the Render Engine to Cycles. Imported shaders may fail to compile while using EEVEE without the Vulkan backend"
            )

    use_vulkan: BoolProperty(
            name="Set Backend to Vulkan",
            default=False,
            description="(Requires Restart) Sets the Blender graphics backend to Vulkan which can compile shaders that fail using OpenGL."
            )

    update_gi: BoolProperty(
            name="Increase Transparent Light Paths",
            default=False,
            description="Increase Cycles maximum bounces for transparent light paths. This improves shading of layered meshes with alpha such as hair."
            )

    with_materials: BoolProperty(
            name="With Materials",
            default=True,
            description="Import WolvenKit-exported materials"
            )

    axl_yaml: BoolProperty(
            name="Use YAML instead of JSON",
            default=False,
            description="Use the ArchiveXL YAML format instead of JSON format for generated .xl files"
            )

    include_heightfields: BoolProperty(
            name="Include Heightfields",
            default=False,
            description="Write each new sector's cooked PhysX heightfield shapes into it as terrain collision nodes"
            )

    write_mltemplate: BoolProperty(
            name="Generate modified MLTEMPLATE",
            default=True,
            description="Write project-local MLTEMPLATE overrides when authored multilayer values do not match an existing named override"
            )

    animtab: EnumProperty(
            name="Animation Tab",
            items=[
                ('RIGSETUP', "Rig Setup", "Rig loading and configuration tools"),
                ('ANIMATION', "Animation", "Animation playback and keyframing tools"),
                ('FACIAL', "Facial", "Facial animation setup and baking tools"),
                ],
            default='ANIMATION'
            )

    def get_meshtab_items(self, context):
        return [
            ('UTILITIES', "Utilities", ""),
            ('MODELLING', "Modelling", ""),
            ('CHARACTERS', "Characters", ""),
            ('CLOTH', "Garment", "Garment setup, pinning, simulation, and bake tools"),
            ]

    meshtab: EnumProperty(
            items=get_meshtab_items,
            name="Mesh Tab"
            )


registration_classes = get_classes(sys.modules[__name__])

_LEDGER = RegistrationLedger("cyber_props")


def register_props():
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(registration_classes)
        _LEDGER.add_property(
            Scene,
            "cp77_panel_props",
            PointerProperty(type=CP77_PT_PanelProps),
        )
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_props():
    _LEDGER.cleanup_or_raise()
