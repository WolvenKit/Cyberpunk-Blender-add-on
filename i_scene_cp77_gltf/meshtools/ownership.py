from __future__ import annotations

OWNER_TAG = "cp77_meshtools_owner"
ROLE_TAG = "cp77_meshtools_role"
OWNER_VALUE = "CP77_MESHTOOLS"
SOURCE_TAG = "cp77_meshtools_source"


def tag_owned(datablock, role, *, source=""):
    datablock[OWNER_TAG] = OWNER_VALUE
    datablock[ROLE_TAG] = str(role)
    if source:
        datablock[SOURCE_TAG] = str(source)
    elif SOURCE_TAG in datablock:
        del datablock[SOURCE_TAG]
    return datablock


def is_owned(datablock, role=None):
    if datablock is None or datablock.get(OWNER_TAG) != OWNER_VALUE:
        return False
    return role is None or datablock.get(ROLE_TAG) == role


def owned_source(datablock):
    return str(datablock.get(SOURCE_TAG, "")) if datablock is not None else ""


def find_owned_material(materials, role):
    return next((material for material in materials if is_owned(material, role)), None)
