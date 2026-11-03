import os
import sys

import bpy
<<<<<<< Updated upstream
from .materials.multilayer_setup import CP77ImportMLSetup
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Operator, OperatorFileListElement, PropertyGroup, TOPBAR_MT_file_import
from bpy_extras.io_utils import ImportHelper

from ..addon_identity import get_addon_preferences
from .mesh import import_cyberpunk_glb, import_external_glb, reload_materials
from .character import (
    CP77CharacterShapeProps, CP77_OT_LoadBaseCharacter, CP77_OT_NpzImportMesh, CP77_OT_NpzImportShapeKeys,
    )
from ..assetio.documents import DocumentSession
from ..cyber_props import SetCyclesRenderer, SetVulkanBackend
from ..icons.cp77_icons import get_icon
from ..gltf.provenance import GLBProvenanceError, inspect_glb
from ..registration import get_classes, RegistrationLedger
from .entity.repository import EntityRepository

_last_selected_entity_appearance = {}
_last_selected_gltf_appearance = {}
_gltf_appearance_cache = {}
_entity_appearance_cache = {}
=======
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import (
    Operator,
    OperatorFileListElement,
    PropertyGroup,
    TOPBAR_MT_file_import,
)
from bpy_extras.io_utils import ImportHelper

from ..animation.model.animgraph.constants import ANIMGRAPH_FILE_FILTER
from ..assetio.cache import store_bounded
from ..assetio.documents import DocumentSession, FileIdentity
from ..assetio.index import IndexPolicy
from ..assetio.paths import absolute_local_path_key, material_sidecar_path
from ..blender.gpu_backend import opengl_shader_warning
from ..blender.import_hooks import after_import, before_import
from ..blender.selection import select_objects
from ..blender.transactions import (
    BlenderImportTransaction,
    raise_if_rollback_incomplete,
)
from ..core.addon_identity import get_addon_preferences
from ..core.log import debug_exception, get_logger, log_once
from ..core.notifications import import_operation, report
from ..core.registration import RegistrationLedger, get_classes
from ..cyber_props import SetCyclesRenderer, SetVulkanBackend
from ..gltf.provenance import inspect_glb
from ..icons.cp77_icons import get_icon
from ..materials.repository import MaterialResourceRepository
from ..materials.resources import load_material_bundle
from .animgraph.parser import cancel_deferred_link_timers
from .character.npz import (
    CP77_OT_LoadBaseCharacter,
    CP77_OT_NpzImportMesh,
    CP77_OT_NpzImportShapeKeys,
    CP77CharacterShapeProps,
)
from .common import appearance_list, dialog_model
from .common.dialog_model import balanced_rows, category_property
from .entity import dialog as entity_dialog
from .entity.repository import EntityRepository
from .materials.multilayer_setup import CP77ImportMLSetup
from .mesh.external import import_external_glb
from .mesh.orchestration import import_cyberpunk_glb, resolve_direct_animation_target
from .rig.reader import create_armature_from_data
from .sector import dialog as sector_dialog
from .sector.options import DECAL_MODES, SECTOR_CHOICES

_LOG = get_logger(__name__)

_last_selected_entity_appearance = {}
_last_selected_gltf_appearance = {}
_entity_appearance_cache = {}
_ENTITY_APPEARANCE_CACHE_LIMIT = 32
# The rows of the dialog drawing its appearance list that its All Appearances toggle or "default" covers.
_covered_rows = frozenset()
>>>>>>> Stashed changes


class AppearanceItem(PropertyGroup):
    name: StringProperty()
    selected: BoolProperty(default=False)


<<<<<<< Updated upstream
class CP77_UL_AppearanceList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        self.use_filter_show = len(data.appearance_list) > 15

        row = layout.row(align=True)
        all_selected = any(i.name == "all" and i.selected for i in data.appearance_list)

        if item.name.startswith("-") or item.name.startswith("─"):
            sep_row = layout.row()
            sep_row.separator(factor=0.5)
            sep_row.enabled = False
            return

        if item.name == "all":
            row.prop(item, "selected", text=item.name, text_ctxt=f"All appearances")
            return

        if item.name == "default":
            resolved = getattr(data, "_resolved_default", None)
            label = f"default → {resolved}" if resolved else "default"

            if all_selected:
                if item.selected:
                    item.selected = False
                row.enabled = False
            row.prop(item, "selected", text=label)
            return

        if all_selected:
            if item.selected:
                item.selected = False
            row.enabled = False

        elif getattr(data, "_default_selected", False):
            resolved = getattr(data, "_resolved_default", None)
            if resolved and item.name.lower() == resolved.lower():
                if item.selected:
                    item.selected = False
                row.enabled = False

        row.prop(item, "selected", text=item.name)
=======
def _cover_appearance_rows(dialog):
    """Work out, once as dialog draws its appearance list, which rows its toggle or "default" covers"""
    global _covered_rows
    items = dialog.appearance_list
    _covered_rows = appearance_list.covered_appearances(
        tuple(item.name for item in items),
        frozenset(item.name for item in items if item.selected),
        dialog.all_appearances,
        getattr(dialog, "_resolved_default", None),
    )


class CP77_UL_AppearanceList(bpy.types.UIList):
    """The import dialogs' appearances"""

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        self.use_filter_show = len(data.appearance_list) > 15
        resolved = getattr(data, "_resolved_default", None)
        row = layout.row(align=True)
        row.active = item.name not in _covered_rows
        label = (
            f"default → {resolved}"
            if item.name == "default" and resolved
            else item.name
        )
        row.prop(item, "selected", text=label)
>>>>>>> Stashed changes


class CP77ImportRig(Operator):
    bl_idname = "import_scene.rig"
    bl_label = "Import Rig from JSON"
<<<<<<< Updated upstream
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Import a rig from a rig.JSON file and create an armature in Blender"

    filter_glob: StringProperty(
            default="*.rig.json",
            options={'HIDDEN'},
            )
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    create_debug: BoolProperty(
        name="Create Debug Empties", default=False,
        description="Create Empties at the Joints - Useful for Validating and Debugging Transforms"
        )

    bind_pose: EnumProperty(
            name="Rig Bind Pose",
            items=(("A-Pose", "A-Pose", "Will Fallback to T Pose if Unavailable"),
                   ("T-Pose", "T-Pose", "")),
            description="Bind Pose to Load",
            default="T-Pose"
            )

    def execute(self, context):
        from .rig import create_armature_from_data

        create_armature_from_data(self.filepath, self.bind_pose, self.create_debug)

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
=======
    bl_options = {"REGISTER", "UNDO"}
    bl_description = (
        "Import a rig from a rig.JSON file and create an armature in Blender"
    )

    filter_glob: StringProperty(
        default="*.rig.json",
        options={"HIDDEN"},
    )
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    bind_pose: EnumProperty(
        name="Rig Bind Pose",
        items=(
            ("A-Pose", "A-Pose", "Will Fallback to T Pose if Unavailable"),
            ("cp77_t_pose", "T-Pose", ""),
        ),
        description="Bind Pose to Load",
        default="cp77_t_pose",
    )

    @import_operation
    def execute(self, context):
        transaction = BlenderImportTransaction()
        try:
            with transaction.scope():
                armature = create_armature_from_data(self.filepath, self.bind_pose)
        except Exception as error:
            raise_if_rollback_incomplete(transaction.rollback(), error)
            raise
        if armature is None:
            transaction.rollback()
            report(
                self,
                "ERROR",
                f"No armature was created: {os.path.basename(self.filepath)} holds no rig data.",
                logger=_LOG,
            )
            return {"CANCELLED"}
        transaction.commit()
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
>>>>>>> Stashed changes

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Rig Import Options")
        row = box.row()
        row.label(text="Bind Pose:")
        row.prop(self, "bind_pose", text="")
<<<<<<< Updated upstream
        row = box.row()
        row.prop(self, "create_debug")


class CP7PhysImport(Operator):
    bl_idname = "import_scene.phys"
    bl_label = "Import .phys Collisions"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Import collisions from an exported .phys.json"

    filepath: StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        from .collision import import_phys

        import_phys(self.filepath)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
=======


class CP77MocapImport(Operator, ImportHelper):
    bl_idname = "import_scene.cp77_mocap"
    bl_label = "Import Mocap onto Cyberpunk Rig"
    bl_description = "Retarget BVH or iClone rlMotion files onto the active Cyberpunk body rig, one action per file"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(default="*.bvh;*.rlmotion", options={"HIDDEN"})
    files: CollectionProperty(type=OperatorFileListElement)
    directory: StringProperty(subtype="DIR_PATH")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != "ARMATURE":
            cls.poll_message_set("Select the Cyberpunk rig the motion goes onto")
            return False
        return True

    @import_operation
    def execute(self, context):
        from .animation.mocap import import_mocap_to_armature

        armature = context.active_object
        names = [entry.name for entry in self.files if entry.name] or [
            os.path.basename(self.filepath)
        ]
        imported = 0
        for name in names:
            try:
                import_mocap_to_armature(
                    os.path.join(
                        self.directory or os.path.dirname(self.filepath), name
                    ),
                    armature,
                )
            except Exception as error:
                report(self, "ERROR", f"{name}: {error}", error=error, logger=_LOG)
                continue
            imported += 1
        return {"FINISHED"} if imported else {"CANCELLED"}


_ANIMGRAPH_ENUM_ITEMS = {}  # Blender reads dynamic enum strings after the items callback returns.


def _animgraph_armature_items(_self, context):
    items = [
        (obj.name, obj.name, "")
        for obj in context.scene.objects
        if obj.type == "ARMATURE"
    ]
    _ANIMGRAPH_ENUM_ITEMS["armature"] = items or [
        ("NONE", "No Armature", "Add an armature to the scene first")
    ]
    return _ANIMGRAPH_ENUM_ITEMS["armature"]


def _animgraph_rig_part_items(self, _context):
    from .animgraph.graph_import import rig_part_items

    armature = bpy.data.objects.get(self.armature)
    items = [
        (
            "AUTO",
            "Automatic",
            "The part an entity's component binds the graph to, else the one whose rig "
            "file name matches the graph's, else the first part",
        )
    ]
    if armature is not None and armature.type == "ARMATURE":
        items += rig_part_items(armature)
    _ANIMGRAPH_ENUM_ITEMS["rig_part"] = items
    return items


class CP77AnimGraphImport(Operator, ImportHelper):
    bl_idname = "import_scene.cp77_animgraph"
    bl_label = "Import Cyberpunk AnimGraph"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Import a WolvenKit AnimGraph bound to an armature and open it in the Animation workspace"

    filename_ext = ".animgraph.json"
    filter_glob: StringProperty(default=ANIMGRAPH_FILE_FILTER, options={"HIDDEN"})
    armature: EnumProperty(
        name="Armature",
        items=_animgraph_armature_items,
        description="The armature the graph animates",
    )
    rig_part: EnumProperty(
        name="Rig Part",
        items=_animgraph_rig_part_items,
        description="The armature's MetaRig part the graph animates",
    )

    def invoke(self, context, event):
        active = getattr(context, "active_object", None)
        if active is not None and active.type == "ARMATURE":
            self.armature = active.name
        return ImportHelper.invoke(self, context, event)

    def draw(self, context):
        self.layout.prop(self, "armature")
        self.layout.prop(self, "rig_part")

    @import_operation
    def execute(self, context):
        from ..blender.workspace import show_graph
        from .animgraph.graph_import import default_rig_part, import_graph

        armature = bpy.data.objects.get(self.armature)
        if armature is None or armature.type != "ARMATURE":
            report(
                self, "ERROR", "Choose the armature the graph animates.", logger=_LOG
            )
            return {"CANCELLED"}
        rig_part = (
            default_rig_part(armature, self.filepath)
            if self.rig_part == "AUTO"
            else self.rig_part
        )
        transaction = BlenderImportTransaction()
        try:
            with transaction.scope():
                tree = import_graph(self.filepath, armature, context, rig_part=rig_part)
        except Exception as error:
            raise_if_rollback_incomplete(transaction.rollback(), error)
            raise
        transaction.commit()
        if context.window is not None:
            show_graph(context, tree)
        report(self, "INFO", f"Imported AnimGraph {tree.name}.", logger=_LOG)
        return {"FINISHED"}


def _clear_entity_appearance_cache():
    _entity_appearance_cache.clear()


@bpy.app.handlers.persistent
def _cancel_animgraph_link_timers_before_load(_unused=None):
    cancel_deferred_link_timers()


@bpy.app.handlers.persistent
def _clear_entity_appearance_cache_before_load(_unused=None):
    _clear_entity_appearance_cache()
>>>>>>> Stashed changes


def _load_entity_for_ui(filepath):
    if not filepath or not os.path.isfile(filepath):
        return None
<<<<<<< Updated upstream
    with DocumentSession() as documents:
        return EntityRepository(documents).load(filepath, required=True)


def get_appearance_items(self, context):
    try:
        entity = _load_entity_for_ui(self.filepath)
    except Exception as error:
        print(f"[CP77] Error reading appearances: {error}")
=======
    try:
        source_identity = FileIdentity.from_path(filepath)
    except OSError:
        debug_exception(_LOG, "Could not read %s; the dialog shows no entity", filepath)
        return None
    normalized = source_identity.path.key
    identity = (
        normalized,
        source_identity.mtime_ns,
        source_identity.size,
    )
    cached = _entity_appearance_cache.get(identity)
    if cached is not None:
        return cached
    for key in tuple(_entity_appearance_cache):
        if key[0] == normalized:
            _entity_appearance_cache.pop(key, None)
    with DocumentSession() as documents:
        entity = EntityRepository(documents).load(filepath, required=True)
    return store_bounded(
        _entity_appearance_cache,
        identity,
        entity,
        limit=_ENTITY_APPEARANCE_CACHE_LIMIT,
    )


def get_appearance_items(self):
    try:
        entity = _load_entity_for_ui(self.filepath)
    except Exception as error:
        log_once(
            _LOG,
            "WARNING",
            ("appearances", type(error).__name__),
            "Unable to read appearances: %s",
            error,
            exc_info=True,
        )
>>>>>>> Stashed changes
        return []
    return list(entity.appearance_names) if entity is not None else []


class CP77EntityImport(Operator, ImportHelper):
    bl_idname = "io_scene_gltf.cp77entity"
    bl_label = "Import Ent from JSON"
<<<<<<< Updated upstream
    bl_description = "Import Characters and Vehicles from Cyberpunk 2077 Entity Files"

    filter_glob: StringProperty(
            default="*.ent.json",
            options={'HIDDEN'},
            )

    filepath: StringProperty(
        name="Filepath",
        subtype='FILE_PATH'
        )

    # generate_overrides: BoolProperty(name="Generate Overrides for Multilayer materials (may be slow)",default=False,description="Imports overrides and palettes for multilayered materials")
=======
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Import Characters and Vehicles from Cyberpunk 2077 Entity Files"

    filter_glob: StringProperty(
        default="*.ent.json",
        options={"HIDDEN"},
    )

    filepath: StringProperty(name="Filepath", subtype="FILE_PATH")
>>>>>>> Stashed changes

    appearance_list: CollectionProperty(type=AppearanceItem)
    active_appearance_index: IntProperty(default=0)

    exclude_meshes: StringProperty(
        name="Meshes_to_Exclude",
        description="Meshes to skip during import",
        default="",
<<<<<<< Updated upstream
        options={'HIDDEN'}
        )

    include_collisions: BoolProperty(
        name="Include Collisions", default=False,
        description="Use this option to import collision bodies with this entity"
        )
    include_phys: BoolProperty(
        name="Include .phys Collisions", default=False,
        description="Use this option if you want to import the .phys collision bodies. Useful for vehicle modding"
        )
    include_entCollider: BoolProperty(
        name="Include Collision Components", default=False,
        description="Use this option to import entColliderComponent and entSimpleColliderComponent"
        )
    import_occluders: BoolProperty(
        name="Include Static Occluders", default=False,
        description="Import entStaticOccluderMeshComponent geometry"
        )
    import_proxies: BoolProperty(
        name="Include Appearance Proxies", default=False,
        description="Import entAppearanceProxyMeshComponent geometry"
        )
    include_lights: BoolProperty(
        name="Import Lights",
        default=False,
        description=(
            "Import entity light components and light-channel components"
        ),
        )
    inColl: StringProperty(
        name="Collector to put the imported entity in",
        description="Collector to put the imported entity in",
        default='',
        options={'HIDDEN'}
        )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
=======
        options={"HIDDEN"},
    )
    inColl: StringProperty(
        name="Collector to put the imported entity in",
        description="Collector to put the imported entity in",
        default="",
        options={"HIDDEN"},
    )

    all_appearances: BoolProperty(
        name="All Appearances",
        default=False,
        options={"SKIP_SAVE"},
        description="Import every appearance of the entity, each once",
    )
    materials: BoolProperty(
        name="Materials",
        default=True,
        options={"SKIP_SAVE"},
        description="Build the materials of the imported meshes",
    )
    proxies: BoolProperty(
        name="Proxy Meshes",
        default=False,
        options={"SKIP_SAVE"},
        description="Import entAppearanceProxyMeshComponent geometry",
    )
    occluders: BoolProperty(
        name="Occluders",
        default=False,
        options={"SKIP_SAVE"},
        description="Import entStaticOccluderMeshComponent geometry",
    )
    shadow_meshes: BoolProperty(
        name="Shadow Meshes",
        default=False,
        options={"SKIP_SAVE"},
        description="Import mesh components whose mesh is a *_shadow.mesh",
    )
    refresh_index: BoolProperty(
        name="Refresh Asset Index",
        default=False,
        options={"SKIP_SAVE"},
        description=(
            "Rescan the source/raw tree before import; leave disabled for "
            "faster repeated imports when exported files have not changed"
        ),
    )

    def invoke(self, context, event):
        dialog_model.state_to_operator(
            self,
            entity_dialog.remembered_state(get_addon_preferences(context)),
            settings=entity_dialog.IMPORT_SETTINGS,
            categories=entity_dialog.CATEGORIES,
            choices=entity_dialog.ENTITY_CHOICES,
        )
        self.sync_appearance_rows()
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def check(self, context):
        """Fill the rows of another file chosen in the file browser"""
        return self.sync_appearance_rows()
>>>>>>> Stashed changes

    def get_default_appearance_name(self):
        try:
            entity = _load_entity_for_ui(self.filepath)
        except Exception as error:
<<<<<<< Updated upstream
            print(f"[CP77] Error resolving defaultAppearance: {error}")
            return None
        if entity is None or entity.default_appearance.casefold() in {"", "none", "null", "random"}:
=======
            log_once(
                _LOG,
                "WARNING",
                ("default appearance", type(error).__name__),
                "Unable to resolve defaultAppearance: %s",
                error,
                exc_info=True,
            )
            return None
        if entity is None or entity.default_appearance.casefold() in {
            "",
            "none",
            "null",
            "random",
        }:
>>>>>>> Stashed changes
            return None
        return entity.default_appearance

    def ent_update_appearance_list(self):
<<<<<<< Updated upstream
        self.appearance_list.clear()
        names = get_appearance_items(self, bpy.context)

        self._resolved_default = self.get_default_appearance_name()

        last_selected = _last_selected_entity_appearance.get(self.filepath, [])

        if not names:
            item = self.appearance_list.add()
            item.name = "default"
            item.selected = True
            return

        if len(names) == 1:
            item = self.appearance_list.add()
            item.name = "default"
            item.selected = True
            return

        def_item = self.appearance_list.add()
        def_item.name = "default"
        def_item.selected = "default" in last_selected or not last_selected

        all_item = self.appearance_list.add()
        all_item.name = "all"
        all_item.selected = "all" in last_selected

        sep = self.appearance_list.add()
        sep.name = "----"
        sep.selected = False

        for name in sorted([n for n in names if n.lower() != "default"], key=str.lower):
            item = self.appearance_list.add()
            item.name = name
            item.selected = name in last_selected

    def draw(self, context):
        cp77_addon_prefs = get_addon_preferences(context)
        props = context.scene.cp77_panel_props
        layout = self.layout

        box = layout.box()
        box.label(text="Entity Appearance", icon='OUTLINER_OB_GROUP_INSTANCE')

        if not self.filepath:
            if len(self.appearance_list) > 0:
                self.appearance_list.clear()
                self._last_filepath = ""

            row = box.row(align=True)
            row.label(text="Please select a .ent.json file")
            return

        last = getattr(self, '_last_filepath', '')
        if last != self.filepath:
            self.ent_update_appearance_list()
            self._last_filepath = self.filepath

        if len(self.appearance_list) == 0:
            box = layout.box()
            row = box.row(align=True)
            row.label(text="No appearances found", icon='INFO')
            sub = box.row()
            sub.alignment = 'CENTER'
            sub.enabled = False
            sub.label(text=f"Will import base components only")

        row = box.row()
        row.template_list(
=======
        """Fill the rows for the chosen file, with the ticks and the toggle this session last used for it"""
        self.appearance_list.clear()
        self._resolved_default = self.get_default_appearance_name()
        rows = entity_dialog.appearance_rows(get_appearance_items(self))
        ticks, self.all_appearances = appearance_list.appearance_ticks(
            rows,
            _last_selected_entity_appearance.get(self.filepath),
        )
        for name in rows:
            item = self.appearance_list.add()
            item.name = name
            item.selected = name in ticks

    def _chosen_file(self):
        """The entity file chosen in the browser, or "" while a folder or nothing is"""
        return self.filepath if self.filepath and os.path.isfile(self.filepath) else ""

    def sync_appearance_rows(self):
        """Fill the rows when another file is chosen"""
        chosen = self._chosen_file()
        previous = getattr(self, "_last_filepath", "")
        if chosen == previous:
            return False
        if previous:
            store_bounded(
                _last_selected_entity_appearance,
                previous,
                (
                    frozenset(
                        item.name for item in self.appearance_list if item.selected
                    ),
                    bool(self.all_appearances),
                ),
                limit=32,
            )
        self._last_filepath = chosen
        if chosen:
            self.ent_update_appearance_list()
        return True

    def draw(self, context):
        layout = self.layout
        props = context.scene.cp77_panel_props

        # The rows belong to the chosen file; invoke and check fill them when another file is chosen.
        if self._chosen_file():
            box = layout.box()
            box.label(text="Appearances")
            if len(self.appearance_list) > 1:
                box.prop(self, "all_appearances", toggle=True)
            _cover_appearance_rows(self)
            box.template_list(
>>>>>>> Stashed changes
                "CP77_UL_AppearanceList",
                "",
                self,
                "appearance_list",
                self,
                "active_appearance_index",
<<<<<<< Updated upstream
                rows=min(10, len(self.appearance_list))
                )

        selected_names = [item.name for item in self.appearance_list if item.selected]

        if "default" in selected_names:
            resolved = getattr(self, '_resolved_default', None)
            if resolved and resolved.lower() != "default":
                for item in self.appearance_list:
                    if item.name.lower() == resolved.lower() and item.selected:
                        box = layout.box()
                        row = box.row(align=True)
                        row.label(text="Skipping duplicate entity import:", icon="INFO")
                        sub = box.row()
                        sub.alignment = 'CENTER'
                        sub.enabled = False
                        sub.label(text=f"↳ '{resolved}' matches 'default'")
                        break

        box = layout.box()
        box.label(text="Entity Import")
        col = box.column()
        col.prop(props, "with_materials")
        if cp77_addon_prefs.experimental_features:
            col.prop(props, "remap_depot")
        # col.prop(self, 'generate_overrides')
        box = layout.box()
        col = box.column()
        col.prop(props, 'use_vulkan')
        col.prop(props, 'use_cycles')
        if props.use_cycles:
            col.prop(props, 'update_gi')

        if not self.include_collisions:
            self.include_phys = False
            self.include_entCollider = False
            self._collisions_initialized = False
        else:
            if not hasattr(self, "_collisions_initialized") or not self._collisions_initialized:
                self.include_phys = True
                self.include_entCollider = True
                self._collisions_initialized = True

        header, panel = layout.panel(
            "cp77_entity_optional_imports",
            default_closed=True,
            )
        header.label(text="Optional Imports")
        if panel:
            col = panel.column()
            col.prop(self, "import_occluders")
            col.prop(self, "import_proxies")
            col.prop(self, "include_lights")
            col.prop(self, "include_collisions")
            if self.include_collisions:
                nested = col.column(align=True)
                nested.prop(self, "include_phys")
                nested.prop(self, "include_entCollider")

    def execute(self, context):
        props = context.scene.cp77_panel_props

        SetVulkanBackend(props.use_vulkan)
        SetCyclesRenderer(props.use_cycles, props.update_gi)

        selected = [item.name for item in self.appearance_list if item.selected]

        if selected:
            _last_selected_entity_appearance[self.filepath] = selected

        if "all" in selected:
            apps = ["ALL"]

        elif "default" in selected:
            resolved = getattr(self, '_resolved_default', None)
            filtered = []

            for name in selected:
                if name == "default":
                    filtered.append("default")
                elif resolved and name.lower() == resolved.lower():
                    print(f"[CP77] Warning: '{name}' is the same as resolved defaultAppearance.")
                    print(f"[CP77] It was already included via 'default'. Skipping duplicate.")
                else:
                    filtered.append(name)

            apps = filtered if filtered else ["default"]

        else:
            apps = selected

        print('apps - ', apps)
        bob = self.filepath
        inColl = self.inColl
        # print('Bob - ',bob)
        from .entity import EntityImportRequest, import_entity

        try:
            result = import_entity(
                EntityImportRequest(
                    with_materials=props.with_materials,
                    filepath=bob,
                    appearances=tuple(apps),
                    excluded_meshes=(),
                    include_collisions=self.include_collisions,
                    include_phys=self.include_phys,
                    include_entity_colliders=self.include_entCollider,
                    include_occluders=self.import_occluders,
                    include_proxies=self.import_proxies,
                    include_lights=self.include_lights,
                    parent_collection_name=inColl,
                )
            )
        except Exception as error:
            self.report({'ERROR'}, f"Entity import failed: {error}")
            return {'CANCELLED'}
        if result.warnings:
            self.report(
                {'WARNING'},
                f"Entity import completed with warnings: {result.warnings[0]}",
            )
        if result.failures:
            self.report(
                {'ERROR'},
                f"Entity import failed and was rolled back: {result.failures[0]}",
            )
        return result.blender_status


class CP77StreamingSectorImport(Operator, ImportHelper):
    bl_idname = "io_scene_gltf.cp77sector"
    bl_label = "Import All StreamingSectors from project"
    bl_description = "Load Cyberpunk 2077 Streaming Sectors"

    filter_glob: StringProperty(
            default="*.cpmodproj",
            options={'HIDDEN'},
            )

    filepath: StringProperty(
        name="Filepath",
        subtype='FILE_PATH'
        )

    want_collisions: BoolProperty(
        name="Import Collisions", default=False,
        description="Import Box and Capsule Collision objects (mesh not yet supported)"
        )
    am_modding: BoolProperty(
        name="Generate New Collectors", default=False,
        description="Generate _new collectors for sectors to allow modifications to be saved back to game"
        )
    with_lights: BoolProperty(
        name="Import Lights", default=False,
        description=(
            "Import sector lights and light-related components in nested entities"
        )
        )
    import_foliage: BoolProperty(
        name="Import Foliage",
        default=False,
        description=(
            "Import foliage populations; foliage-destruction metadata also "
            "requires Import Collisions"
        ),
        )
    import_effects: BoolProperty(
        name="Import Effects",
        default=False,
        description="Import particle and effect nodes",
        )
    import_proxies: BoolProperty(
        name="Import Proxy Meshes", default=False,
        description=(
            "Import all proxy mesh nodes, including global water-patch proxies"
        )
        )
    import_acoustics: BoolProperty(
        name="Import Acoustic Data", default=False,
        description="Import acoustic sector markers and resolve acoustic data resources"
        )
    import_occluders: BoolProperty(
        name="Import Occluders", default=False,
        description="Import static and instanced occluder geometry"
        )
    import_minimap: BoolProperty(
        name="Import Minimap Data", default=False,
        description="Import minimap data nodes and resolve minimap resources"
        )
    import_environment_probes: BoolProperty(
        name="Import Environment Probes", default=False,
        description="Import reflection probe volumes and resolve environment probe resources"
        )
    import_world_metadata: BoolProperty(
        name="Import World Metadata", default=False,
        description=(
            "Import ambient and interior areas, light-channel volumes and shapes, "
            "interior maps, static fog volumes, static sound emitters, and world boundaries"
            )
        )
    import_gi: BoolProperty(
        name="Import GI Data", default=False,
        description="Import global illumination nodes, spaces, and GI resources"
        )

    def draw(self, context):
        cp77_addon_prefs = get_addon_preferences(context)
        props = context.scene.cp77_panel_props
        layout = self.layout

        box = layout.box()
        box.label(text="Sector Import", icon='OUTLINER_OB_GROUP_INSTANCE')
        col = box.column()
        col.prop(self, "am_modding")
        col.prop(props, "with_materials")

        header, panel = layout.panel(
            "cp77_sector_optional_imports",
            default_closed=True,
            )
        header.label(text="Optional Imports")
        if panel:
            col = panel.column()
            col.prop(self, "want_collisions")
            col.prop(self, "with_lights")
            col.prop(self, "import_foliage")
            col.prop(self, "import_effects")
            col.prop(self, "import_proxies")
            col.prop(self, "import_acoustics")
            col.prop(self, "import_minimap")
            col.prop(self, "import_occluders")
            col.prop(self, "import_environment_probes")
            col.prop(self, "import_world_metadata")
            col.prop(self, "import_gi")

        if cp77_addon_prefs.experimental_features:
            box = layout.box()
            col = box.column()
            col.prop(props, "remap_depot")

    def execute(self, context):
        bob = self.filepath
        props = context.scene.cp77_panel_props
        print('Importing Sectors from project - ', bob)
        from .sector.execution import import_sectors

        try:
            result = import_sectors(
                filepath=bob,
                with_mats=props.with_materials,
                remap_depot=props.remap_depot,
                want_collisions=self.want_collisions,
                am_modding=self.am_modding,
                with_lights=self.with_lights,
                import_foliage=self.import_foliage,
                import_effects=self.import_effects,
                import_proxies=self.import_proxies,
                import_acoustics=self.import_acoustics,
                import_occluders=self.import_occluders,
                import_minimap=self.import_minimap,
                import_environment_probes=self.import_environment_probes,
                import_world_metadata=self.import_world_metadata,
                import_gi=self.import_gi,
                )
        except Exception as error:
            self.report({'ERROR'}, f"Sector import failed: {error}")
            return {'CANCELLED'}
        if result.warnings:
            self.report(
                {'WARNING'},
                f"Sector import completed with warnings: {result.warnings[0]}",
            )
        if result.failures:
            self.report(
                {'ERROR'},
                f"Sector import failed and was rolled back: {result.failures[0]}",
            )
        return result.blender_status



def get_gltf_appearance_items(self, context):
=======
                rows=min(10, max(1, len(self.appearance_list))),
            )

        box = layout.box()
        box.label(text="Import")
        grid = box.grid_flow(columns=2, even_columns=True, row_major=True)
        for name in entity_dialog.IMPORT_SETTINGS:
            grid.prop(self, name)
        if self.materials:
            grid.prop(props, "use_vulkan")
            grid.prop(props, "use_cycles")
            if props.use_cycles:
                grid.prop(props, "update_gi")
        if get_addon_preferences(context).experimental_features:
            box.prop(props, "remap_depot")

        first = 0
        for count in balanced_rows(len(entity_dialog.CATEGORIES)):
            row = layout.row(align=True)
            for category in entity_dialog.CATEGORIES[first : first + count]:
                row.prop(self, category_property(category), toggle=True)
            first += count

        inactive = dialog_model.state_from_operator(
            self,
            entity_dialog.EntityDialogState,
            settings=entity_dialog.IMPORT_SETTINGS,
            categories=entity_dialog.CATEGORIES,
            choices=entity_dialog.ENTITY_CHOICES,
        ).inactive_choices()
        for category in entity_dialog.CATEGORIES:
            if len(category.choices) < 2 or not getattr(
                self, category_property(category)
            ):
                continue
            header, panel = layout.panel(
                f"cp77_entity_{category.name}", default_closed=False
            )
            header.label(text=category.label)
            if panel:
                grid = panel.grid_flow(columns=2, even_columns=True, row_major=True)
                for choice in category.choices:
                    cell = grid.row()
                    cell.active = choice not in inactive
                    cell.prop(self, choice)

    @import_operation
    def execute(self, context):
        # A file chosen without a check (a name typed and confirmed, or a scripted call) gets its rows here.
        self.sync_appearance_rows()
        props = context.scene.cp77_panel_props
        state = dialog_model.state_from_operator(
            self,
            entity_dialog.EntityDialogState,
            settings=entity_dialog.IMPORT_SETTINGS,
            categories=entity_dialog.CATEGORIES,
            choices=entity_dialog.ENTITY_CHOICES,
        )
        entity_dialog.remember_state(get_addon_preferences(context), state)

        if state.materials:
            for message in (
                *SetVulkanBackend(props.use_vulkan),
                *SetCyclesRenderer(props.use_cycles, props.update_gi),
            ):
                report(self, "INFO", message, logger=_LOG)
            if warning := opengl_shader_warning():
                report(self, "WARNING", warning, logger=_LOG)

        ticked = [item.name for item in self.appearance_list if item.selected]
        store_bounded(
            _last_selected_entity_appearance,
            self.filepath,
            (frozenset(ticked), bool(self.all_appearances)),
            limit=32,
        )
        apps = appearance_list.appearance_request(
            ticked,
            self.all_appearances,
            getattr(self, "_resolved_default", None),
        )

        _LOG.debug(
            "Entity appearance selection: %s", ", ".join(str(app) for app in apps)
        )
        cp77_addon_prefs = get_addon_preferences(context)
        depot_root = ""
        configured = str(cp77_addon_prefs.depotfolder_path or "")
        if configured and os.path.isdir(configured):
            depot_root = configured
        from .entity.execution import import_entity
        from .entity.options import EntityImportRequest

        before = before_import(context.scene)
        try:
            result = import_entity(
                EntityImportRequest(
                    **state.request_fields(),
                    filepath=self.filepath,
                    appearances=tuple(apps),
                    excluded_meshes=(),
                    parent_collection_name=self.inColl,
                    depot_root=depot_root,
                    report_owner=self,
                    index_policy=(
                        IndexPolicy.REFRESH
                        if state.refresh_index
                        else IndexPolicy.REUSE
                    ),
                )
            )
        except Exception as error:
            report(
                self,
                "ERROR",
                f"Entity import failed: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        if result.warnings:
            report(
                self,
                "WARNING",
                f"Entity import completed; notification summary contains {len(result.warnings)} warning(s); first: {result.warnings[0]}",
                logger=_LOG,
            )
        if result.failures:
            report(
                self,
                "ERROR",
                f"Entity import failed and was rolled back: {result.failures[0]}",
                logger=_LOG,
            )
        else:
            after_import(context.scene, before)
        return result.blender_status


# One toggle button per category and one tick per choice, labelled and described as the entity dialog model names them.
CP77EntityImport.__annotations__.update(
    {
        **{
            category_property(category): BoolProperty(
                name=category.label,
                default=False,
                options={"SKIP_SAVE"},
                description=entity_dialog.CATEGORY_DESCRIPTIONS[category.name],
            )
            for category in entity_dialog.CATEGORIES
        },
        **{
            choice: BoolProperty(
                name=label,
                default=choice in entity_dialog.STARTING_CHOICES,
                options={"SKIP_SAVE"},
                description=entity_dialog.CHOICE_DESCRIPTIONS[choice],
            )
            for choice, label in entity_dialog.CHOICE_LABELS.items()
        },
    }
)


# The label and tooltip of each sector decal mode.
_DECAL_MODE_TEXT = {
    "CONFORMAL": (
        "Conformal Projection",
        "Clip receiver surfaces to decal projector volumes and blend decal channels into receiver materials",
    ),
    "LEGACY_PLANES": (
        "Legacy Planes",
        "Import editable flat decal planes for compatibility and debugging",
    ),
    "PROJECTORS_ONLY": (
        "Projectors Only",
        "Import editable decal projector volumes without rendered surfaces",
    ),
}


class CP77StreamingSectorImport(Operator, ImportHelper):
    bl_idname = "io_scene_gltf.cp77sector"
    bl_label = "Import All StreamingSectors from project"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Load Cyberpunk 2077 Streaming Sectors"

    filter_glob: StringProperty(
        default="*.cpmodproj",
        options={"HIDDEN"},
    )

    filepath: StringProperty(name="Filepath", subtype="FILE_PATH")

    materials: BoolProperty(
        name="Materials",
        default=True,
        options={"SKIP_SAVE"},
        description="Build the materials of the imported meshes",
    )
    proxies: BoolProperty(
        name="Proxy Meshes",
        default=False,
        options={"SKIP_SAVE"},
        description="Import all proxy mesh nodes, including global water-patch proxies",
    )
    refresh_index: BoolProperty(
        name="Refresh Asset Index",
        default=False,
        options={"SKIP_SAVE"},
        description=(
            "Rescan the source/raw tree before import; leave disabled for "
            "faster repeated imports when exported files have not changed"
        ),
    )
    decal_mode: EnumProperty(
        name="Projected Decals",
        items=tuple((mode, *_DECAL_MODE_TEXT[mode]) for mode in sorted(DECAL_MODES)),
        default="CONFORMAL",
        options={"SKIP_SAVE"},
    )
    existing_sectors: EnumProperty(
        name="Existing Sectors",
        items=(
            (
                "ADD_MISSING",
                "Add Missing Nodes",
                "Keep content already imported for a sector and place only nodes that are not yet in the scene",
            ),
            (
                "REPLACE",
                "Replace Content",
                "Remove previously imported content of each sector and rebuild it; changes are only discarded once the import succeeds",
            ),
        ),
        default="ADD_MISSING",
        options={"SKIP_SAVE"},
    )
    collections: EnumProperty(
        name="Collections",
        items=(
            (
                "SOURCE_NODES",
                "Per Source Node",
                "Group the content of every sector node in its own collection",
            ),
            (
                "SECTOR",
                "Per Sector",
                "Place content directly in the sector collection; recommended for large imports",
            ),
        ),
        default="SOURCE_NODES",
        options={"SKIP_SAVE"},
    )

    def invoke(self, context, event):
        dialog_model.state_to_operator(
            self,
            sector_dialog.remembered_state(get_addon_preferences(context)),
            settings=sector_dialog.SECTOR_IMPORT_SETTINGS,
            categories=sector_dialog.CATEGORIES,
            choices=SECTOR_CHOICES,
        )
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Import")
        column = box.column()
        column.prop(self, "existing_sectors")
        column.prop(self, "collections")
        column.prop(self, "decal_mode")
        grid = box.grid_flow(columns=2, even_columns=True, row_major=True)
        for name in ("materials", "proxies", "refresh_index"):
            grid.prop(self, name)
        if get_addon_preferences(context).experimental_features:
            box.prop(context.scene.cp77_panel_props, "remap_depot")

        first = 0
        for count in balanced_rows(len(sector_dialog.CATEGORIES)):
            row = layout.row(align=True)
            for category in sector_dialog.CATEGORIES[first : first + count]:
                row.prop(self, category_property(category), toggle=True)
            first += count

        inactive = dialog_model.state_from_operator(
            self,
            sector_dialog.DialogState,
            settings=sector_dialog.SECTOR_IMPORT_SETTINGS,
            categories=sector_dialog.CATEGORIES,
            choices=SECTOR_CHOICES,
        ).inactive_choices()
        for category in sector_dialog.CATEGORIES:
            if len(category.choices) < 2 or not getattr(
                self, category_property(category)
            ):
                continue
            header, panel = layout.panel(
                f"cp77_sector_{category.name}", default_closed=False
            )
            header.label(text=category.label)
            if panel:
                grid = panel.grid_flow(columns=2, even_columns=True, row_major=True)
                for choice in category.choices:
                    cell = grid.row()
                    cell.active = choice not in inactive
                    cell.prop(self, choice)

    @import_operation
    def execute(self, context):
        from .sector.execution import import_sectors

        state = dialog_model.state_from_operator(
            self,
            sector_dialog.DialogState,
            settings=sector_dialog.SECTOR_IMPORT_SETTINGS,
            categories=sector_dialog.CATEGORIES,
            choices=SECTOR_CHOICES,
        )
        sector_dialog.remember_state(get_addon_preferences(context), state)
        options = state.options(remap_depot=context.scene.cp77_panel_props.remap_depot)
        if options.with_materials and (warning := opengl_shader_warning()):
            report(self, "WARNING", warning, logger=_LOG)
        _LOG.debug("Sector import requested: %s", self.filepath)
        before = before_import(context.scene)
        try:
            result = import_sectors(
                self.filepath,
                options,
                force_refresh=state.refresh_index,
                report_owner=self,
            )
        except Exception as error:
            report(
                self,
                "ERROR",
                f"Sector import failed: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        if result.warnings:
            report(
                self,
                "WARNING",
                f"Sector import completed; notification summary contains {len(result.warnings)} warning(s); first: {result.warnings[0]}",
                logger=_LOG,
            )
        if result.failures:
            report(
                self,
                "ERROR",
                f"Sector import failed and was rolled back: {result.failures[0]}",
                logger=_LOG,
            )
        else:
            after_import(context.scene, before)
        return result.blender_status


# One toggle button per category and one tick per choice, labelled as the dialog model names them.
CP77StreamingSectorImport.__annotations__.update(
    {
        **{
            category_property(category): BoolProperty(
                name=category.label, default=False, options={"SKIP_SAVE"}
            )
            for category in sector_dialog.CATEGORIES
        },
        **{
            choice: BoolProperty(
                name=label,
                default=choice in sector_dialog.STARTING_CHOICES,
                options={"SKIP_SAVE"},
            )
            for choice, label in sector_dialog.CHOICE_LABELS.items()
        },
    }
)


def get_gltf_appearance_items(self):
>>>>>>> Stashed changes
    if not self.filepath:
        return []

    names = []

<<<<<<< Updated upstream
    base = os.path.splitext(self.filepath)[0]
    material_json = base + ".Material.json"

    if os.path.isfile(material_json):
        try:
            from ..materials.resources import load_material_bundle

            bundle = load_material_bundle(material_json)
            appearances = bundle.appearances
            values = appearances.keys() if isinstance(appearances, dict) else appearances
            names.extend(str(name) for name in values if name)
        except Exception as error:
            print(f"[CP77] Error reading material.json: {error}")
=======
    material_json = material_sidecar_path(self.filepath)

    if os.path.isfile(material_json):
        try:
            bundle = load_material_bundle(material_json)
            appearances = bundle.appearances
            values = (
                appearances.keys() if isinstance(appearances, dict) else appearances
            )
            names.extend(str(name) for name in values if name)
        except Exception as error:
            log_once(
                _LOG,
                "WARNING",
                ("material appearances", type(error).__name__),
                "Unable to read Material.json: %s",
                error,
                exc_info=True,
            )
>>>>>>> Stashed changes

    return names


<<<<<<< Updated upstream
def clean_appearance_name(name, index):
    suffix = str(index)
    if name.endswith(suffix):
        return name[:-len(suffix)]
    return name


class CP77Import(Operator, ImportHelper):
    bl_idname = "io_scene_gltf.cp77"
    bl_label = "Import Cyberpunk GLB"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Import a WolvenKit/direct GLB, or normalize an external GLB through Blender"

    filter_glob: StringProperty(default="*.glb", options={'HIDDEN'})
    filepath: StringProperty(name="Filepath", subtype='FILE_PATH')
    files: CollectionProperty(type=OperatorFileListElement)
    directory: StringProperty(subtype='FILE_PATH')

    appearance_list: CollectionProperty(type=AppearanceItem)
    active_appearance_index: IntProperty(default=0)

    image_format: EnumProperty(
            name="Textures",
            items=(("png", "Use PNG textures", ""),
                   ("dds", "Use DDS textures", ""),
                   ("jpg", "Use JPG textures", ""),
                   ("tga", "Use TGA textures", ""),
                   ("bmp", "Use BMP textures", ""),
                   ("jpeg", "Use JPEG textures", "")),
            default="png"
            )

    # exclude_unused_mats: BoolProperty(name="Exclude Unused Materials",default=True,description="Enabling this options skips all the materials that aren't being used by any mesh")

    # Kwekmaster: QoL option to match WolvenKit GUI options - Name change to With Materials
    hide_armatures: BoolProperty(
        name="Hide Armatures", default=True, description="Hide the armatures on imported meshes"
        )

    import_garmentsupport: BoolProperty(
        name="Import Garment Support (Experimental)", default=True,
        description="Imports Garment Support mesh data as color attributes"
        )
    # generate_overrides: BoolProperty(name="Generate Overrides for Multilayer materials (may be slow)",default=False,description="Imports overrides and palettes for multilayered materials")

    scripting: BoolProperty(
        name="Scripting", default=False,
        description="Tell it its being called by a script so it can ignore the gui file lists", options={'HIDDEN'}
        )
    import_tracks: BoolProperty(
        name="Import Tracks", default=True, description="Import Animation Float Tracks to F-Curves"
        )

    def gltf_update_appearance_list(self):
        self.appearance_list.clear()
        names = get_gltf_appearance_items(self, bpy.context)

        last_selected = _last_selected_gltf_appearance.get(self.filepath, [])

        if not names:
            return

        cleaned_names = []
        for i, name in enumerate(names):
            clean_name = clean_appearance_name(name, i)
            cleaned_names.append(clean_name)

        if len(cleaned_names) == 1:
            item = self.appearance_list.add()
            item.name = clean_name
            item.selected = True
            return

        all_item = self.appearance_list.add()
        all_item.name = "all"
        all_item.selected = "all" in last_selected or not last_selected

        for name in cleaned_names:
            item = self.appearance_list.add()
            item.name = name
            item.selected = name in last_selected

    def draw(self, context):
        cp77_addon_prefs = get_addon_preferences(context)
        props = context.scene.cp77_panel_props
        layout = self.layout

        box = layout.box()
        box.label(text="Mesh Appearance", icon='OUTLINER_OB_GROUP_INSTANCE')

        if not self.filepath:
            row = box.row(align=True)
            row.label(text="Please select a .glb file")
            return

        if self.filepath:
            last = getattr(self, '_last_filepath', '')
            if last != self.filepath:
                self.gltf_update_appearance_list()
                self._last_filepath = self.filepath

            if len(self.appearance_list) == 0:
                box = layout.box()
                row = box.row(align=True)
                row.label(text="No appearances found", icon='INFO')
                sub = box.row()
                sub.alignment = 'CENTER'
                sub.enabled = False
                sub.label(text="Importing GLB without CP77 material sidecar")
                return

            row = box.row()

            row.template_list(
                    "CP77_UL_AppearanceList",
                    "",
                    self,
                    "appearance_list",
                    self,
                    "active_appearance_index",
                    rows=min(10, len(self.appearance_list)),
                    )

        if not props.with_materials:
            box = layout.box()
            col = box.column()
            col.prop(props, 'with_materials')
            if cp77_addon_prefs.experimental_features:
                col.prop(props, "remap_depot")
            box = layout.box()
            col = box.column()
            col.prop(self, 'hide_armatures')
            col.prop(self, 'import_garmentsupport')
            if cp77_addon_prefs.experimental_features:
                col.prop(props, "remap_depot")
        if props.with_materials:
            box = layout.box()
            col = box.column()
            col.prop(props, 'with_materials')
            if cp77_addon_prefs.experimental_features:
                col.prop(props, "remap_depot")
            # col.prop(self, 'generate_overrides')
            # if not self.show_appearance_selection:
            #   col.prop(self, 'exclude_unused_mats')
            box = layout.box()
            col = box.column()
            col.prop(props, 'use_vulkan')
            col.prop(props, 'use_cycles')
            if props.use_cycles:
                col.prop(props, 'update_gi')
            box = layout.box()
            box.label(text='Texture Format:')
            box.prop(self, 'image_format', text='')
            box = layout.box()
            col = box.column()
            col.prop(self, 'hide_armatures')
            col.prop(self, 'import_garmentsupport')
        box = layout.box()
        col = box.column()
        col.prop(self, 'import_tracks')

        # if not self.show_appearance_selection:
        #    col.prop(self, 'exclude_unused_mats')

    def execute(self, context):
        props = context.scene.cp77_panel_props
        inspection = None
        import_path = self.filepath

        if not self.scripting:
            selected_names = [
                str(getattr(item, "name", "") or "")
                for item in self.files
                if str(getattr(item, "name", "") or "")
            ]
            if selected_names:
                base_directory = self.directory or os.path.dirname(self.filepath)
                selected_paths = [
                    os.path.join(base_directory, name)
                    for name in selected_names
                ]
            else:
                selected_paths = [self.filepath] if self.filepath else []
            if len(selected_paths) != 1:
                self.report(
                    {'ERROR'},
                    "The UI importer accepts exactly one GLB at a time.",
                )
                return {'CANCELLED'}
            import_path = os.path.abspath(selected_paths[0])
            try:
                inspection = inspect_glb(import_path)
            except GLBProvenanceError as error:
                self.report({'ERROR'}, str(error))
                return {'CANCELLED'}

            if not inspection.claims_cp77_origin:
                try:
                    summary = import_external_glb(import_path, inspection)
                except Exception as error:
                    self.report({'ERROR'}, str(error))
                    return {'CANCELLED'}
                generator = inspection.generator or "unspecified generator"
                self.report(
                    {'INFO'},
                    f"Imported {summary.mesh_count} external meshes and "
                    f"{summary.armature_count} armatures and "
                    f"{summary.action_count} actions from {generator}"
                    + (
                        "; objects were normalized for CP77 export."
                        if summary.object_count
                        else "."
                    ),
                )
                return {'FINISHED'}

            if not inspection.direct_import_supported:
                self.report(
                    {'ERROR'},
                    f"{inspection.generator or 'The GLB generator'} identifies a CP77 source, "
                    f"but the document content is {inspection.content_kind.value!r} and cannot "
                    "be imported by the direct CP77 path.",
                )
                return {'CANCELLED'}

        SetVulkanBackend(props.use_vulkan)
        SetCyclesRenderer(props.use_cycles, props.update_gi)

        selected = [item.name for item in self.appearance_list if item.selected]
        if selected:
            _last_selected_gltf_appearance[self.filepath] = selected

        if "all" in selected:
            appearances = ["ALL"]
        elif len(selected) == 0:
            appearances = ["default"]
        else:
            appearances = selected

        print('apps - ', appearances)

        try:
            result = import_cyberpunk_glb(
                    props.with_materials,
                    props.remap_depot,
                    False,
                    self.image_format,
                    import_path,
                    self.hide_armatures,
                    self.import_garmentsupport,
                    () if inspection is not None else self.files,
                    os.path.dirname(import_path) if inspection is not None else self.directory,
                    appearances,
                    self.scripting,
                    self.import_tracks,
                    False,
                    animation_target='AUTO',
                    content_kind=(
                        inspection.content_kind.value
                        if inspection is not None
                        else None
                    ),
                    )
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

        if result.failures:
            self.report(
                {'ERROR'},
                f"GLB import was incomplete: {result.failures[0]}",
            )
            return {'CANCELLED'}
        if result.warnings:
            self.report(
                {'WARNING'},
                f"GLB import completed with warnings: {result.warnings[0]}",
            )
        if inspection is not None:
            self.report(
                {'INFO'},
                f"Imported {inspection.content_kind.value} GLB from "
                f"{inspection.generator or inspection.source.value}.",
            )
        return {'FINISHED'}


class CP77MaterialReload(Operator):
    bl_idname = "reload_material.cp77"
    bl_label = "Reload Material"
    bl_options = {'REGISTER', 'UNDO'}
    bl_parent_id = "CP77_PT_MaterialTools"
    bl_description = "Reload the active material from json."

    def execute(self, context):
        active_object = context.active_object
        if not active_object:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        active_material = active_object.active_material
        if not active_material:
            self.report({'ERROR'}, "Active object has no material")
            return {'CANCELLED'}
        # JATO: TODO make a popup asking to use the locate mesh operator
        if not active_material.get("MeshPath"):
            self.report(
                    {'ERROR'},
                    "Material was not reloaded: Use Locate Mesh to find a valid source file within a WolvenKit project"
                    )
            return {'CANCELLED'}

        old_mat = active_material
        old_mat_idx = active_object.active_material_index

        new_mat = reload_materials(self, context)

        # The reload service must return the same Blender material type.
        if type(new_mat) is not type(old_mat):
            self.report({'ERROR'}, 'Material failed to reload')
            return {'CANCELLED'}

        context.active_object.active_material = new_mat
        context.active_object.active_material_index = old_mat_idx

        from ..materialtools.editor import synchronize_panel
        synchronize_panel(context)

        try:
            if old_mat.users == 0:
                bpy.data.materials.remove(
                    old_mat,
                    do_unlink=True,
                    do_id_user=True,
                    do_ui_user=True,
                )
        except (ReferenceError, RuntimeError, TypeError):
            pass

        return {"FINISHED"}


def menu_func_import(self, context):
    self.layout.operator(CP77Import.bl_idname, text="Cyberpunk GLB (.glb)", icon_value=get_icon('WKIT'))
    self.layout.operator(CP77EntityImport.bl_idname, text="Cyberpunk Entity (.json)", icon_value=get_icon('WKIT'))
    self.layout.operator(
        CP77StreamingSectorImport.bl_idname, text="Cyberpunk StreamingSector", icon_value=get_icon('WKIT')
        )
    self.layout.operator(CP77ImportRig.bl_idname, text="Cyberpunk Rig import (.rig.json)", icon_value=get_icon('WKIT'))
=======
class CP77Import(Operator, ImportHelper):
    bl_idname = "io_scene_gltf.cp77"
    bl_label = "Import Cyberpunk glTF / GLB"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = (
        "Import mesh appearances or animations from one or more glTF / GLB files"
    )

    filter_glob: StringProperty(default="*.glb;*.gltf", options={"HIDDEN"})
    filepath: StringProperty(name="Filepath", subtype="FILE_PATH")
    files: CollectionProperty(type=OperatorFileListElement)
    directory: StringProperty(subtype="DIR_PATH")
    appearance_list: CollectionProperty(type=AppearanceItem)
    active_appearance_index: IntProperty(default=0)
    all_appearances: BoolProperty(
        name="All Appearances",
        default=False,
        options={"SKIP_SAVE"},
        description="Import every appearance of the mesh, each once",
    )
    image_format: EnumProperty(
        name="Textures",
        items=tuple(
            (extension, extension.upper(), "")
            for extension in ("png", "dds", "jpg", "tga", "bmp", "jpeg")
        ),
        default="png",
    )
    hide_armatures: BoolProperty(name="Hide Mesh Armatures", default=True)
    import_garmentsupport: BoolProperty(name="Import Garment Support", default=True)
    import_tracks: BoolProperty(name="Import Float Tracks", default=True)
    refresh_asset_index: BoolProperty(
        name="Refresh Asset Index",
        default=False,
        description=(
            "Rescan texture folders before import. Project folders are "
            "revalidated automatically; use this for large depot folders "
            "after exporting new textures"
        ),
    )
    animation_target: EnumProperty(
        name="Animation Rig",
        items=(
            (
                "AUTO",
                "Selected Rig or Reconstruct",
                "Use the selected CP77 rig; reconstruct the source rig when none is selected",
            ),
            (
                "SELECTED",
                "Selected Rig",
                "Import onto the selected CP77 rig or a selected mesh's CP77 rig",
            ),
            (
                "NEW",
                "Reconstruct Rig",
                "Create an independent rig from each animation file's source skeleton",
            ),
        ),
        default="AUTO",
    )

    def _selected_paths(self):
        directory = self.directory or os.path.dirname(self.filepath)
        paths = [os.path.join(directory, item.name) for item in self.files if item.name]
        if not paths and self.filepath:
            paths = [self.filepath]
        unique = {}
        for path in paths:
            unique.setdefault(absolute_local_path_key(path), os.path.abspath(path))
        return tuple(unique.values())

    def _chosen_file(self):
        """The one file chosen in the browser, or "" while a folder, nothing or several files are"""
        paths = self._selected_paths()
        return paths[0] if len(paths) == 1 and os.path.isfile(paths[0]) else ""

    def gltf_update_appearance_list(self, path):
        """Fill the rows for path"""
        self.appearance_list.clear()
        names = get_gltf_appearance_items(self)
        rows = (
            "default",
            *dict.fromkeys(name for name in names if name.casefold() != "default"),
        )
        ticks, self.all_appearances = appearance_list.appearance_ticks(
            rows, _last_selected_gltf_appearance.get(path)
        )
        for name in rows:
            item = self.appearance_list.add()
            item.name = name
            item.selected = name in ticks

    def _remember_appearances(self, path):
        ticked = frozenset(item.name for item in self.appearance_list if item.selected)
        store_bounded(
            _last_selected_gltf_appearance,
            path,
            (ticked, bool(self.all_appearances)),
            limit=32,
        )

    def sync_appearance_rows(self):
        """Fill the rows when another file is chosen or its material sidecar changes"""
        chosen = self._chosen_file()
        try:
            identity = (
                FileIdentity.from_path(material_sidecar_path(chosen)).key
                if chosen
                else None
            )
        except OSError:
            debug_exception(_LOG, "Could not read the material sidecar of %s", chosen)
            identity = None
        previous = getattr(self, "_appearance_identity", ("", None))
        if (chosen, identity) == previous:
            return False
        if previous[0]:
            self._remember_appearances(previous[0])
        self._appearance_identity = (chosen, identity)
        if chosen:
            self.gltf_update_appearance_list(chosen)
        return True

    def invoke(self, context, event):
        self.sync_appearance_rows()
        return ImportHelper.invoke(self, context, event)

    def check(self, context):
        """Fill the rows of another file chosen in the file browser"""
        return self.sync_appearance_rows()

    def draw(self, context):
        prefs = get_addon_preferences(context)
        props = context.scene.cp77_panel_props
        layout = self.layout
        # The rows belong to the one chosen file; with several files, each imports its default appearance.
        if self._chosen_file():
            box = layout.box()
            box.label(text="Appearances")
            if len(self.appearance_list) > 1:
                box.prop(self, "all_appearances", toggle=True)
            _cover_appearance_rows(self)
            box.template_list(
                "CP77_UL_AppearanceList",
                "",
                self,
                "appearance_list",
                self,
                "active_appearance_index",
                rows=min(10, max(2, len(self.appearance_list))),
            )
        box = layout.box()
        box.prop(props, "with_materials")
        if props.with_materials:
            if prefs.experimental_features:
                box.prop(props, "remap_depot")
            box.prop(self, "image_format")
            box.prop(self, "refresh_asset_index")
            box.prop(props, "use_vulkan")
            box.prop(props, "use_cycles")
            if props.use_cycles:
                box.prop(props, "update_gi")
        box.prop(self, "hide_armatures")
        box.prop(self, "import_garmentsupport")
        box = layout.box()
        box.label(text="Animations")
        box.prop(self, "animation_target")
        box.prop(self, "import_tracks")

    @import_operation
    def execute(self, context):
        props = context.scene.cp77_panel_props
        paths = self._selected_paths()
        if not paths:
            report(
                self, "ERROR", "Select at least one .glb or .gltf file.", logger=_LOG
            )
            return {"CANCELLED"}
        # A file chosen without a check (a name typed and confirmed, or a scripted call) gets its rows here.
        self.sync_appearance_rows()
        chosen = self._chosen_file()
        appearances = ("default",)
        if chosen:
            ticked = [item.name for item in self.appearance_list if item.selected]
            appearances = appearance_list.appearance_request(
                ticked, self.all_appearances, None
            )
            self._remember_appearances(chosen)
        target = (
            "NEW"
            if self.animation_target == "NEW"
            else resolve_direct_animation_target(context)
        )
        if target is None:
            target = (
                "SELECTED"
                if self.animation_target == "SELECTED"
                else (
                    "SELECTED"
                    if any(obj.type == "ARMATURE" for obj in context.selected_objects)
                    else "NEW"
                )
            )
        if props.with_materials:
            for message in (
                *SetVulkanBackend(props.use_vulkan),
                *SetCyclesRenderer(props.use_cycles, props.update_gi),
            ):
                report(self, "INFO", message, logger=_LOG)
            if warning := opengl_shader_warning():
                report(self, "WARNING", warning, logger=_LOG)
        imported, warnings, failures, objects = 0, [], [], []
        with DocumentSession() as documents:
            material_resources = MaterialResourceRepository(
                documents,
                image_index_policy=(
                    IndexPolicy.REFRESH
                    if self.refresh_asset_index
                    else IndexPolicy.REUSE
                ),
            )
            for path in paths:
                try:
                    inspection = inspect_glb(path)
                    if inspection.content_kind.value == "empty":
                        raise ValueError(
                            "The file contains no mesh or animation payload."
                        )
                    if (
                        not inspection.claims_cp77_origin
                        and inspection.content_kind.value not in {"animation", "rig"}
                    ):
                        import_external_glb(path, inspection)
                        objects.extend(context.selected_objects)
                    else:
                        if (
                            inspection.claims_cp77_origin
                            and not inspection.direct_import_supported
                        ):
                            raise ValueError(
                                f"Unsupported CP77 payload: {inspection.content_kind.value}."
                            )
                        result = import_cyberpunk_glb(
                            path,
                            with_materials=props.with_materials,
                            remap_depot=props.remap_depot,
                            image_format=self.image_format,
                            hide_armatures=self.hide_armatures,
                            import_garmentsupport=self.import_garmentsupport,
                            appearances=appearances,
                            import_tracks=self.import_tracks,
                            animation_target=target,
                            content_kind=inspection.content_kind.value,
                            document_session=documents,
                            material_resources=material_resources,
                            report_owner=self,
                        )
                        if result.failures:
                            raise RuntimeError("; ".join(result.failures))
                        warnings.extend(
                            f"{os.path.basename(path)}: {message}"
                            for message in result.warnings
                        )
                        for item in result:
                            objects.extend(
                                item.get("all_objects") or (item.get("armature"),)
                            )
                    imported += 1
                except Exception as error:
                    message = f"{os.path.basename(path)}: {error}"
                    failures.append(message)
                    _LOG.exception("Import failed: %s", message)
        objects = list(
            dict.fromkeys(
                obj for obj in objects if obj is not None and not obj.hide_get()
            )
        )
        if objects:
            select_objects(objects, clear=True, context=context)
        for message in failures:
            report(self, "WARNING" if imported else "ERROR", message, logger=_LOG)
        if warnings:
            report(
                self,
                "WARNING",
                f"{len(warnings)} warning(s); first: {warnings[0]}",
                logger=_LOG,
            )
        if imported:
            report(
                self,
                "WARNING" if failures else "INFO",
                f"Imported {imported} of {len(paths)} file(s).",
                logger=_LOG,
            )
            return {"FINISHED"}
        return {"CANCELLED"}


def menu_func_import(self, context):
    self.layout.operator(
        CP77Import.bl_idname,
        text="Cyberpunk glTF / GLB (.gltf, .glb)",
        icon_value=get_icon("WKIT"),
    )
    self.layout.operator(
        CP77EntityImport.bl_idname,
        text="Cyberpunk Entity (.json)",
        icon_value=get_icon("WKIT"),
    )
    self.layout.operator(
        CP77StreamingSectorImport.bl_idname,
        text="Cyberpunk StreamingSector",
        icon_value=get_icon("WKIT"),
    )
    self.layout.operator(
        CP77ImportRig.bl_idname,
        text="Cyberpunk Rig import (.rig.json)",
        icon_value=get_icon("WKIT"),
    )
    self.layout.operator(
        CP77AnimGraphImport.bl_idname,
        text="Cyberpunk AnimGraph (.animgraph.json)",
        icon_value=get_icon("WKIT"),
    )
>>>>>>> Stashed changes


_npz_classes = (
    CP77ImportMLSetup,
    CP77CharacterShapeProps,
    CP77_OT_NpzImportMesh,
    CP77_OT_NpzImportShapeKeys,
    CP77_OT_LoadBaseCharacter,
)
registration_classes = get_classes(
    sys.modules[__name__],
    extra_classes=_npz_classes,
)


_LEDGER = RegistrationLedger("importers")


def _remove_import_menu():
    try:
        TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception:
<<<<<<< Updated upstream
        pass
=======
        _LOG.debug(
            "File import menu entry was not present during cleanup", exc_info=True
        )
>>>>>>> Stashed changes


def register_importers():
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(registration_classes)
        _LEDGER.add_property(
            bpy.types.Scene,
            "cp77_character_shape",
            bpy.props.PointerProperty(type=CP77CharacterShapeProps),
        )
        _remove_import_menu()
        TOPBAR_MT_file_import.append(menu_func_import)
        _LEDGER.add_cleanup("import menu", _remove_import_menu)
<<<<<<< Updated upstream
        from .entity.rigs import register_rig_cache_handlers, unregister_rig_cache_handlers
        register_rig_cache_handlers()
        _LEDGER.add_cleanup("rig cache handlers", unregister_rig_cache_handlers)
=======
        _LEDGER.add_handler(
            bpy.app.handlers.load_pre,
            _clear_entity_appearance_cache_before_load,
        )
        _LEDGER.add_cleanup(
            "entity appearance UI cache", _clear_entity_appearance_cache
        )
        _LEDGER.add_handler(
            bpy.app.handlers.load_pre, _cancel_animgraph_link_timers_before_load
        )
        _LEDGER.add_cleanup(
            "AnimGraph deferred link timers", cancel_deferred_link_timers
        )
        from .entity.rigs import (
            register_rig_cache_handlers,
            unregister_rig_cache_handlers,
        )

        register_rig_cache_handlers()
        _LEDGER.add_cleanup("rig cache handlers", unregister_rig_cache_handlers)
        from ..animation.services.rig.repository import (
            register_stored_rig_documents,
            unregister_stored_rig_documents,
        )
        from ..blender.rig_metadata import stored_rig_part_document

        register_stored_rig_documents(stored_rig_part_document)
        _LEDGER.add_cleanup("stored rig documents", unregister_stored_rig_documents)
>>>>>>> Stashed changes
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_importers():
<<<<<<< Updated upstream
    failures = _LEDGER.cleanup()
    if failures:
        raise RuntimeError("; ".join(f"{label}: {error}" for label, error in failures))
=======
    _LEDGER.cleanup_or_raise()
>>>>>>> Stashed changes
