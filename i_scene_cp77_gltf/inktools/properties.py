from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from ..core.log import get_logger
from . import services
from .blender import hierarchy

_LOG = get_logger(__name__)


def _edit(field: str):
    def update(self, _context):
        if services.controls_syncing():
            return
        value = getattr(self, field)
        if not isinstance(value, (bool, int, float, str)):
            value = tuple(float(component) for component in value)
        result = services.record_edit(self.id_data, **{field: value})
        if not result.ok:
            _LOG.warning("%s", result.message)

    return update


class CP77InkWidgetControls(bpy.types.PropertyGroup):
    text: StringProperty(name="Text", update=_edit("text"))
    font_size: IntProperty(name="Font Size", min=0, update=_edit("font_size"))
    size: FloatVectorProperty(name="Size", size=2, min=0.0, update=_edit("size"))
    opacity: FloatProperty(
        name="Opacity", min=0.0, max=1.0, subtype="FACTOR", update=_edit("opacity")
    )
    tint: FloatVectorProperty(
        name="Tint",
        size=4,
        subtype="COLOR",
        min=0.0,
        soft_max=1.0,
        update=_edit("tint"),
    )
    visible: BoolProperty(name="Visible", update=_edit("visible"))


def _widget_index(self):
    widget = hierarchy.picked_widget(self.id_data)
    return self.id_data.objects.find(widget.name) if widget is not None else -1


def _pick_widget(self, index):
    objects = self.id_data.objects
    if 0 <= index < len(objects) and hierarchy.is_screen_root(objects[index]):
        self.widget = objects[index]


class CP77InkToolsSettings(bpy.types.PropertyGroup):
    widget: PointerProperty(
        name="Widget",
        description="The widget the sequence, Refresh and Export buttons act on",
        type=bpy.types.Object,
        poll=lambda _settings, obj: hierarchy.is_screen_root(obj),
    )
    widget_index: IntProperty(name="Widget", get=_widget_index, set=_pick_widget)
