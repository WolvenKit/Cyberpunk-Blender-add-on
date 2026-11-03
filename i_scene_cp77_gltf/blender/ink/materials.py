from __future__ import annotations

from ...assetio.paths import backslash_depot_key
from ...core.log import get_logger, log_once
from ..naming import fit_id_name
from ..shader_nodes import link, math, new_node, socket, socket_by_identifier
from ..transactions import (
    new_tracked_datablock,
    track_created_datablock,
    track_mutation,
)

_LOG = get_logger(__name__)

UI_TEMPLATE_KEYS = frozenset(
    backslash_depot_key(value)
    for value in (
        r"base\materials\metal_base_ui.mt",
        r"base\fx\shaders\parallaxscreen_transparent_ui.mt",
        r"base\fx\shaders\parallaxscreen_transparent_ui_txaa.mt",
    )
)
RENDER_TEXTURE_LABEL = "UIRenderTexture L"
COMPONENT_KEY = "cp77_ink_widget_component"


def is_ui_material(material) -> bool:
    if material is None:
        return False
    return backslash_depot_key(material.get("MaterialTemplate", "")) in UI_TEMPLATE_KEYS


def _render_texture_nodes(material):
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return ()
    return tuple(
        node
        for node in tree.nodes
        if node.bl_idname == "ShaderNodeTexImage"
        and str(node.label or node.name).startswith(RENDER_TEXTURE_LABEL)
    )


def _restore_slot(slot, material, link) -> None:
    try:
        if link is not None:
            slot.link = link
        slot.material = material
    except (AttributeError, ReferenceError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_restore_slot", type(error).__name__),
            "restore slot: fell back after %s",
            error,
            exc_info=True,
        )


def bind_render_texture(
    objects, image, component_name: str
) -> tuple[tuple[str, ...], int]:
    """Bind image into the UI materials of objects"""
    copies, names, bound = {}, [], 0
    for obj in objects:
        if getattr(obj, "type", None) != "MESH":
            continue
        for index, slot in enumerate(getattr(obj, "material_slots", ())):
            source = slot.material
            if not is_ui_material(source) or not _render_texture_nodes(source):
                continue
            link = getattr(slot, "link", None)
            track_mutation(
                ("ink_widget_material_slot", obj.as_pointer(), index),
                lambda slot=slot, source=source, link=link: _restore_slot(
                    slot, source, link
                ),
                verify=lambda slot=slot, source=source, link=link: (
                    slot.material is source
                    and (link is None or getattr(slot, "link", None) == link)
                ),
                label=f"ink widget material slot {obj.name}[{index}]",
            )
            material = copies.get(source.as_pointer())
            if material is None:
                material = track_created_datablock("materials", source.copy())
                material.name = fit_id_name(source.name, f"_{component_name}_ink")
                material[COMPONENT_KEY] = component_name
                for node in _render_texture_nodes(material):
                    node.image = image
                copies[source.as_pointer()] = material
                names.append(material.name)
            if link is not None:
                try:
                    slot.link = "OBJECT"
                except (AttributeError, TypeError, ValueError) as error:
                    log_once(
                        _LOG,
                        "DEBUG",
                        ("bind_render_texture", type(error).__name__),
                        "bind render texture: fell back after %s",
                        error,
                        exc_info=True,
                    )
            slot.material = material
            bound += 1
    return tuple(names), bound


def preview_material(name: str, image):
    """A material showing a render texture of premultiplied colour"""
    material = new_tracked_datablock("materials", name)
    material.use_nodes = True
    material.use_backface_culling = False
    material.surface_render_method = "BLENDED"
    tree = material.node_tree
    tree.nodes.clear()
    texture = new_node(tree, "ShaderNodeTexImage", "Ink Raster", (-520, 0))
    texture.image = image
    texture.extension = "CLIP"
    emission = new_node(tree, "ShaderNodeEmission", "Ink Colour", (-160, 120))
    uncovered = math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        1.0,
        socket(texture.outputs, "Alpha"),
        name="Ink Uncovered",
        location=(-160, -120),
    )
    backdrop = new_node(tree, "ShaderNodeBsdfTransparent", "Ink Backdrop", (40, -120))
    over = new_node(tree, "ShaderNodeAddShader", "Ink Over", (240, 0))
    output = new_node(tree, "ShaderNodeOutputMaterial", "Ink Output", (440, 0))
    link(tree, socket(texture.outputs, "Color"), socket(emission.inputs, "Color"))
    link(tree, uncovered, socket(backdrop.inputs, "Color"))
    link(tree, emission.outputs["Emission"], over.inputs["Shader"])
    link(
        tree, backdrop.outputs["BSDF"], socket_by_identifier(over.inputs, "Shader_001")
    )
    link(tree, over.outputs["Shader"], socket(output.inputs, "Surface"))
    return material


def rebind_copies(copy_map, component_name: str, bound_names, image) -> tuple[str, ...]:
    """Give each copied object its own copies of the bound materials"""
    copies, names = {}, []
    for source_object, target_object in copy_map.items():
        if getattr(source_object, "type", None) != "MESH":
            continue
        targets = tuple(getattr(target_object, "material_slots", ()))
        for index, source_slot in enumerate(
            getattr(source_object, "material_slots", ())
        ):
            material = source_slot.material
            if index >= len(targets) or material is None:
                continue
            if (
                material.name not in bound_names
                and material.get(COMPONENT_KEY) != component_name
            ):
                continue
            copy = copies.get(material.as_pointer())
            if copy is None:
                copy = track_created_datablock("materials", material.copy())
                copy.name = fit_id_name(material.name, f"_{target_object.name}")
                for node in _render_texture_nodes(copy):
                    node.image = image
                copies[material.as_pointer()] = copy
                names.append(copy.name)
            try:
                targets[index].link = "OBJECT"
            except (AttributeError, TypeError, ValueError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("rebind_copies", type(error).__name__),
                    "rebind copies: fell back after %s",
                    error,
                    exc_info=True,
                )
            targets[index].material = copy
    return tuple(names)
