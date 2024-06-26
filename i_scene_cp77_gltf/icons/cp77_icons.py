import bpy
import os
import bpy.utils.previews
from ..main.common import get_icon_dir
custom_icons = None

def load_icons():
    global custom_icons
    if custom_icons is None:
        icons_dir = get_icon_dir()
        custom_icons = bpy.utils.previews.new()
        custom_icons.load("WKIT", os.path.join(icons_dir, "wkit.png"), 'IMAGE')
        custom_icons.load("SCULPT", os.path.join(icons_dir, "sculpt.png"), 'IMAGE')
        custom_icons.load("TRAUMA", os.path.join(icons_dir, "trauma.png"), 'IMAGE')
        custom_icons.load("TECH", os.path.join(icons_dir, "tech.png"), 'IMAGE')
        custom_icons.load("REFIT", os.path.join(icons_dir, "refit.png"), 'IMAGE')

def unload_icons():
    global custom_icons
    if custom_icons is not None:
        bpy.utils.previews.remove(custom_icons)
        custom_icons = None

def get_icon(name):
    if custom_icons and name in custom_icons:
        return custom_icons[name].icon_id
    return 0
