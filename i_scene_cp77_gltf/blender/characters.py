import bpy

# Loaded character parts carry their role and the load they came from, so the shape sliders find them after a rename.
CHARACTER_ROLE_KEY = "cp77_character_role"


CHARACTER_LOAD_KEY = "cp77_character_load"


BREAST_KEYS = {
    1: "t0_000_wa_base__full_breast_small_breast",
    2: "t0_000_wa_base__full_breast_big_breast",
}


_ROLE_FIELDS = {
    "HEAD": ("head_mesh_names", "head_load_token"),
    "BODY": ("body_mesh_name", "body_load_token"),
}


def character_objects(props, role):
    """The loaded objects of role"""
    names_field, token_field = _ROLE_FIELDS[role]
    names = [name for name in getattr(props, names_field).split(";") if name]
    token = getattr(props, token_field)

    def belongs(obj):
        return not token or (
            obj.get(CHARACTER_LOAD_KEY) == token and obj.get(CHARACTER_ROLE_KEY) == role
        )

    found = [
        obj
        for obj in (bpy.data.objects.get(name) for name in names)
        if obj is not None and belongs(obj)
    ]
    if token and len(found) < len(names):
        found = [
            obj
            for obj in bpy.data.objects
            if obj.get(CHARACTER_LOAD_KEY) == token
            and obj.get(CHARACTER_ROLE_KEY) == role
        ]
    return found


def breast_shape_objects(props):
    """The loaded body submeshes that carry breast shape keys"""
    return [
        obj
        for obj in character_objects(props, "BODY")
        if obj.type == "MESH"
        and obj.data.shape_keys
        and any(name in obj.data.shape_keys.key_blocks for name in BREAST_KEYS.values())
    ]
