from __future__ import annotations

import json
import os

import bpy
from mathutils import Matrix

from ....assetio.documents import DocumentLoadError
from ....assetio.values import cname_or_empty, resource_path_text, strict_handle_data
from ....blender.collections import root_objects
from ....blender.ink import screens
from ....blender.ink.materials import bind_render_texture
from ....blender.transactions import track_created_datablock
from ....core.log import get_logger, log_once
from ....ink.domain.animation import load_animation
from ....ink.services.library import load_library
from ...common.entity_data import component_name
from ..registry import EntityComponentHandlerRegistry

WIDGET_COMPONENT_TYPES = frozenset({"WorldWidgetComponent"})
_LOG = get_logger(__name__)


def _mesh_bind_name(component, context=None):
    binding = strict_handle_data(component.get("meshTargetBinding"))
    if binding.get("enabled", 1) == 0:
        return ""
    name = binding.get("bindName")
    if isinstance(name, dict):
        resolved = str(name.get("$value") or "")
    else:
        resolved = str(name or "")
    if resolved or context is None:
        return resolved
    _matrix, bind_name, _slot_name, binding_type, _armature = (
        context.transform_resolver.resolve_component_matrix(component)
    )
    return bind_name if binding_type == "component" else ""


def widget_item_name(component) -> str | None:
    """The library item a widget component shows"""
    return cname_or_empty(component.get("itemNameToSpawn")) or None


def _live_collection(collection):
    if collection is None:
        return None
    try:
        name = collection.name
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_live_collection", type(error).__name__),
            "live collection: fell back after %s",
            error,
            exc_info=True,
        )
        return None
    return collection if bpy.data.collections.get(name) is collection else None


def _component_collection(context, bind_name):
    collections = context.state.get("component_collections", {})
    return _live_collection(collections.get(bind_name))


def _collection_objects(collection):
    if collection is None:
        return ()
    try:
        return tuple(collection.all_objects)
    except AttributeError as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_collection_objects", type(error).__name__),
            "collection objects: fell back after %s",
            error,
            exc_info=True,
        )
        result = list(collection.objects)
        for child in collection.children:
            result.extend(_collection_objects(child))
        return tuple(result)


class EntityWorldWidgetHandler:
    """Shows a WorldWidgetComponent's widget library on the meshes it targets"""

    component_types = WIDGET_COMPONENT_TYPES

    def __init__(self, options=None):
        self.options = dict(options or {})
        self._libraries: dict = {}
        self._canvases: dict = {}
        self._animations: dict = {}
        self._static_images: dict = {}

    def _library(self, widget_json, item_name, resolve, warnings, name):
        key = (
            os.path.normcase(widget_json),
            item_name,
            int(self.options.get("resolution_slot", 0)),
        )
        if key not in self._libraries:
            try:
                loaded = load_library(
                    widget_json, item=item_name, resolver=resolve, preferred_slot=key[2]
                )
            except (DocumentLoadError, OSError, ValueError, KeyError) as error:
                loaded = None
                warnings.append(
                    f"ink widget {widget_json} could not be loaded for {name}: {error}"
                )
            self._libraries[key] = loaded
            if loaded is not None:
                warnings.extend(
                    f"{name}: {where}: {message}" for where, message in loaded.warnings
                )
        return self._libraries[key]

    def _animation(self, loaded, warnings, name):
        path = loaded.animation_path
        if not path:
            return None
        if path not in self._animations:
            try:
                self._animations[path] = load_animation(path)
            except (DocumentLoadError, OSError, ValueError) as error:
                self._animations[path] = None
                warnings.append(
                    f"ink animation {path} could not be loaded for {name}: {error}"
                )
        return self._animations[path]

    def execute(self, component, context):
        name = component_name(component) or "WorldWidget"
        widget_depot = resource_path_text(component.get("widgetResource"))
        widget_collection = self._widget_collection(context)
        bind_name = _mesh_bind_name(component, context)
        target_collection = _component_collection(context, bind_name)
        target_objects = _collection_objects(target_collection)
        warnings = context.state.setdefault("widget_warnings", [])

        root = track_created_datablock("objects", bpy.data.objects.new(name, None))
        root.empty_display_type = "PLAIN_AXES"
        root.empty_display_size = 0.05
        root.hide_render = True
        widget_collection.objects.link(root)
        root["cp77_type"] = "WorldWidgetComponent"
        root["componentName"] = name

        target_roots = root_objects(target_objects)
        if target_roots:
            root.parent = target_roots[0]
            root.matrix_parent_inverse = Matrix.Identity(4)
            root.matrix_basis = Matrix.Identity(4)
        else:
            self._stamp_fallback_binding(root, component, context, name)

        enabled = context.operations.is_component_enabled(component)
        root["cp77_component_enabled"] = enabled
        if not enabled:
            root.hide_viewport = True
            root.hide_render = True

        resolve = context.resolve_export
        widget_json = (
            resolve(widget_depot, ".inkwidget.json") if widget_depot and resolve else ""
        )
        if not widget_json:
            warnings.append(
                f"ink widget for {name} was not found: {widget_depot or 'no widgetResource'}"
            )
            return root
        item_name = widget_item_name(component)
        loaded = self._library(widget_json, item_name, resolve, warnings, name)
        if loaded is None:
            return root
        animation = self._animation(loaded, warnings, name)
        max_dimension = max(1, int(self.options.get("max_raster_dimension", 2048)))
        key = (loaded.path, loaded.item.name, max_dimension)
        if key not in self._canvases:
            self._canvases[key] = screens.render(
                loaded, animation, max_dimension=max_dimension
            )
        canvas = self._canvases[key]
        if animation is not None:
            image = screens.create_texture(name, canvas)
        else:
            image = self._static_images.get(key)
            if image is None or bpy.data.images.get(image.name) is not image:
                image = screens.create_texture(
                    f"{loaded.item.name}_{os.path.basename(loaded.path)}", canvas
                )
                self._static_images[key] = image

        materials, bound_slots = bind_render_texture(target_objects, image, name)
        screens.register(root, image, loaded, animation, max_dimension=max_dimension)
        root["cp77_ink_bound_material_slots"] = int(bound_slots)
        root["cp77_ink_bound_materials"] = json.dumps(
            list(materials), separators=(",", ":")
        )
        if bound_slots:
            _LOG.debug(
                "ink widget %s: bound %d slot(s) on %s with %s",
                name,
                bound_slots,
                bind_name,
                image.name,
            )
        if target_collection is None:
            warnings.append(
                f"ink widget target component not found for {name}: {bind_name or '<empty>'}"
            )
        elif bound_slots == 0:
            warnings.append(
                f"ink widget target {bind_name} has no screen material to show {name} on"
            )
        return root

    @staticmethod
    def _widget_collection(context):
        collection = _live_collection(context.state.get("ink_widget_collection"))
        if collection is not None:
            return collection
        context.state.pop("ink_widget_collection", None)

        collection = track_created_datablock(
            "collections",
            bpy.data.collections.new(f"{context.entity_collection.name}_ink"),
        )
        collection["cp77_node_type"] = "WorldWidgetComponent"
        context.entity_collection.children.link(collection)
        context.state["ink_widget_collection"] = collection
        return collection

    @staticmethod
    def _stamp_fallback_binding(obj, component, context, name):
        resolver = context.transform_resolver
        resolved_matrix, bind_name, slot_name, binding_type, _ = (
            resolver.resolve_component_matrix(component)
        )
        obj.matrix_world = resolved_matrix
        obj["componentName"] = name
        obj["cp77_binding_type"] = binding_type
        if bind_name:
            obj["bindname"] = bind_name
        if slot_name:
            obj["slotName"] = slot_name


def register_widget_handlers(registry, options=None):
    registry.register(
        EntityWorldWidgetHandler.component_types,
        EntityWorldWidgetHandler(options),
    )
    return registry


def create_widget_component_registry(options=None):
    return register_widget_handlers(EntityComponentHandlerRegistry(), options)
