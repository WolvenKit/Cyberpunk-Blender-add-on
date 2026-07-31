from functools import lru_cache
from pathlib import Path
import tomllib

import bpy


ADDON_PACKAGE = __package__
_MANIFEST_PATH = Path(__file__).with_name("blender_manifest.toml")


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
        with _MANIFEST_PATH.open("rb") as manifest_file:
            version = tomllib.load(manifest_file).get("version")
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError(
            f"Could not read Cyberpunk 2077 IO Suite version from "
            f"{_MANIFEST_PATH.name}"
        ) from exc

    if not isinstance(version, str) or not version.strip():
        raise RuntimeError(
            f"Cyberpunk 2077 IO Suite version is missing from "
            f"{_MANIFEST_PATH.name}"
        )

    release = version.split("+", 1)[0].split("-", 1)[0]
    try:
        return tuple(int(part) for part in release.split("."))
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid Cyberpunk 2077 IO Suite version {version!r} in "
            f"{_MANIFEST_PATH.name}"
        ) from exc
