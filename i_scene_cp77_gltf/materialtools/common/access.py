from __future__ import annotations

from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)


def material_property(material, name, default=None):
    if material is None:
        return default
    try:
        return material.get(name, default)
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("material_property", type(error).__name__),
            "material property: fell back after %s",
            error,
            exc_info=True,
        )
        return default


def node_input(node, name):
    try:
        inputs = node.inputs if node is not None else None
        return inputs.get(name) if inputs is not None else None
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("node_input", type(error).__name__),
            "node input: fell back after %s",
            error,
            exc_info=True,
        )
        return None


def active_mesh(context):
    obj = getattr(context, "active_object", None)
    try:
        return obj if obj is not None and obj.type == "MESH" else None
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("active_mesh", type(error).__name__),
            "active mesh: fell back after %s",
            error,
            exc_info=True,
        )
        return None


def active_material(context):
    obj = active_mesh(context)
    return getattr(obj, "active_material", None) if obj is not None else None
