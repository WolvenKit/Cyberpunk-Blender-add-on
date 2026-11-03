import os

_ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RESOURCES_DIR = os.path.join(_ADDON_DIR, "resources")
# The game's default multilayer setup, bundled with its template and textures in their depot layout.
MULTILAYER_DEFAULT_SETUP = "engine\\materials\\defaults\\multilayer_default.mlsetup"
# The bundled base characters: their MetaRig, body, body shape keys and head parts with their shape keys.
BASE_CHARACTERS = {
    "MASC": {
        "rig": "man_base.npz",
        "body_mesh": "t0_000_ma_base__full_hql.npz",
        "body_sk": "ma_base_shapekeys.npz",
        "head_parts": [
            ("h0_000_ma_c__basehead.npz", "h0_000_pma__morphs.npz"),
            ("he_000_ma_c__basehead.npz", "he_000_ma_morphs.npz"),
            ("ht_000_ma_c__basehead.npz", "ht_000_ma_morphs.npz"),
            ("heb_000_ma_c__basehead.npz", "heb_000_ma_morphs.npz"),
        ],
    },
    "FEM": {
        "rig": "woman_base.npz",
        "body_mesh": "t0_000_wa_base__full_hql.npz",
        "body_sk": "wa_base_shapekeys.npz",
        "head_parts": [
            ("h0_000_wa_c__basehead.npz", "wa_basehead__shapekeys.npz"),
            ("he_000_wa_c__basehead.npz", "he_000_wa__morphs.npz"),
            ("ht_000_wa_c__basehead.npz", "ht_000_wa__morphs.npz"),
            ("heb_000_wa_c__basehead.npz", "heb_000_wa__morphs.npz"),
        ],
    },
}


def get_resources_dir():
    return _RESOURCES_DIR


def get_icon_dir():
    return os.path.join(_ADDON_DIR, "icons")


def get_refit_dir():
    return os.path.join(_RESOURCES_DIR, "refitters")


def get_multilayer_defaults_dir():
    return os.path.join(_RESOURCES_DIR, "multilayer_defaults")


def get_char_dir():
    return os.path.join(_RESOURCES_DIR, "characters")


def get_rig_dir():
    return os.path.join(_RESOURCES_DIR, "rigs")


def get_bundled_script_dir():
    return os.path.join(_RESOURCES_DIR, "scripts")


def get_workspace_dir():
    return os.path.join(_RESOURCES_DIR, "workspaces")


def get_nltk_data_dir():
    return os.path.join(_RESOURCES_DIR, "nltk_data")


def base_body_path(rig_name: str) -> str | None:
    """The bundled base body mesh for the base rig rig_name (woman_base, man_base), or None"""
    for character in BASE_CHARACTERS.values():
        if character["rig"] == f"{rig_name}.npz":
            return os.path.join(get_char_dir(), character["body_mesh"])
    return None
