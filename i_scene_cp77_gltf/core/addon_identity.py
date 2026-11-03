import tomllib
from functools import lru_cache
from pathlib import Path

import bpy

from ..assetio.files import read_bytes

# The add-on's root package (this module lives one level below it), under which Blender keeps its preferences.
ADDON_PACKAGE = __package__.rpartition(".")[0]
RUNTIME_BUILD = (2, 5, 0)
_MANIFEST_PATH = Path(__file__).parents[1] / "blender_manifest.toml"


USER_FOLDER = "cp77_io_suite"


def runtime_build_string():
    return ".".join(map(str, RUNTIME_BUILD))


def user_config_dir(*parts):
    """The add-on's folder in Blender's user config folder, created on demand"""
    return bpy.utils.user_resource(
        "CONFIG", path="/".join((USER_FOLDER, *parts)), create=True
    )


def get_addon_preferences(context=None, *, required=True):
    context = context or bpy.context
    addon = context.preferences.addons.get(ADDON_PACKAGE)
    if addon is None:
        if required:
            raise RuntimeError(
                f"Cyberpunk 2077 IO Suite preferences are unavailable for {ADDON_PACKAGE!r}"
            )
        return None
    return addon.preferences


@lru_cache(maxsize=1)
def get_addon_version():
    try:
        version = tomllib.loads(read_bytes(_MANIFEST_PATH).decode("utf-8")).get(
            "version"
        )
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError(
            f"Could not read Cyberpunk 2077 IO Suite version from {_MANIFEST_PATH.name}"
        ) from exc

    if not isinstance(version, str) or not version.strip():
        raise RuntimeError(
            f"Cyberpunk 2077 IO Suite version is missing from {_MANIFEST_PATH.name}"
        )

    release = version.split("+", 1)[0].split("-", 1)[0]
    try:
        return tuple(int(part) for part in release.split("."))
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid Cyberpunk 2077 IO Suite version {version!r} in "
            f"{_MANIFEST_PATH.name}"
        ) from exc
