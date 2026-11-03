import json

import bpy

from ..common.access import node_input

_SESSION_KEY = "cp77MaterialToolsSurfacePaint"
_SURFACE_SETTINGS = {
    "mode": "MATERIAL",
    "use_occlude": True,
    "use_backface_culling": True,
    "use_normal_falloff": True,
    "seam_bleed": 0,
}


def mask_paint_uv(state):
    layers = state.obj.data.uv_layers
    vector = node_input(state.mask_node, "Vector")
    links = tuple(vector.links) if vector is not None else ()
    name = ""
    if links:
        source = links[0].from_node
        if source.type == "UVMAP":
            name = source.uv_map
        elif source.type != "TEX_COORD" or links[0].from_socket.name != "UV":
            raise ValueError(
                "Mask painting requires a UV map connected directly to the mask image"
            )
    if name:
        layer = layers.get(name)
        if layer is None:
            raise ValueError(f"Mask UV map {name!r} is missing on the active mesh")
    else:
        layer = next((uv for uv in layers if uv.active_render), layers.active)
    if layer is None:
        raise ValueError("The active mesh has no mask UV map")
    return next(index for index, uv in enumerate(layers) if uv == layer)


def configure_surface_paint(context, state):
    index = mask_paint_uv(state)
    paint = context.tool_settings.image_paint
    scene = context.scene
    if _SESSION_KEY in scene:
        snapshot = json.loads(scene[_SESSION_KEY])
    else:
        snapshot = {
            "settings": {name: getattr(paint, name) for name in _SURFACE_SETTINGS},
            "uvs": {},
        }
    mesh = state.obj.data
    if mesh.name not in snapshot["uvs"]:
        snapshot["uvs"][mesh.name] = mesh.uv_layers.active.name
        scene[_SESSION_KEY] = json.dumps(snapshot)
    try:
        for name, value in _SURFACE_SETTINGS.items():
            if getattr(paint, name) != value:
                setattr(paint, name, value)
        if state.obj.data.uv_layers.active_index != index:
            state.obj.data.uv_layers.active_index = index
    except Exception:
        restore_surface_paint(context)
        raise


def restore_surface_paint(context):
    scene = getattr(context, "scene", None)
    if scene is None or _SESSION_KEY not in scene:
        return
    snapshot = json.loads(scene[_SESSION_KEY])
    paint = context.tool_settings.image_paint
    for name, value in snapshot["settings"].items():
        if getattr(paint, name) != value:
            setattr(paint, name, value)
    for mesh_name, uv_name in snapshot["uvs"].items():
        mesh = bpy.data.meshes.get(mesh_name)
        if mesh is None:
            continue
        for index, uv in enumerate(mesh.uv_layers):
            if uv.name == uv_name:
                mesh.uv_layers.active_index = index
                break
    del scene[_SESSION_KEY]
