from __future__ import annotations

# What a tool layer runs around each import: before(scene) -> state, then after(scene, state) once the import
# committed. Scene Tools installs its Lights preview when it registers.
_IMPORT_HOOK = None


def register_import_hook(before, after) -> None:
    """Install before and after, run around each import"""
    global _IMPORT_HOOK
    _IMPORT_HOOK = (before, after)


def unregister_import_hook() -> None:
    global _IMPORT_HOOK
    _IMPORT_HOOK = None


def before_import(scene):
    """What the installed hook records of scene before an import"""
    hook = _IMPORT_HOOK
    return None if hook is None else (hook[1], hook[0](scene))


def after_import(scene, recorded) -> None:
    """Hand a committed import's scene to the hook installed when recorded (before_import) was taken"""
    if recorded is not None:
        after, state = recorded
        after(scene, state)
