import bpy
from bpy.app.handlers import persistent

from ...importers.character.npz import breast_shape_objects, character_objects

# Which character tab sections show, and the object count and loaded parts they were found for.
_SECTIONS = [(False, False), None]


@persistent
def clear_character_sections(_unused=None):
    _SECTIONS[:] = ((False, False), None)


def character_sections(props):
    """Whether the loaded head has shape keys and the loaded body breast shapes"""
    key = (
        len(bpy.data.objects),
        props.head_mesh_names,
        props.head_load_token,
        props.body_mesh_name,
        props.body_load_token,
    )
    sections, found_for = _SECTIONS
    if found_for != key:
        sections = (
            any(obj.data.shape_keys for obj in character_objects(props, "HEAD")),
            bool(breast_shape_objects(props)),
        )
        _SECTIONS[:] = (sections, key)
    return sections
