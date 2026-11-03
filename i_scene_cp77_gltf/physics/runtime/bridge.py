import ctypes
import importlib.util
import os
import sys
import types
from pathlib import Path

from ...core.log import debug_exception, get_logger
from ..model.bridge import PhysXCapability, PhysXCapabilityState
from ..native import extensions
from ..native.extensions import (
    native_runtime_copy,
    release_native_runtime_copies,
)
from .bridge_contract import validate_current_bridge_contract
from .cloth_provider import invalidate_cloth_object_cache

_LOG = get_logger(__name__)

_CAPABILITY = PhysXCapability(PhysXCapabilityState.UNINITIALIZED)
_HOST = None
_BRIDGE = None
_DLL_DIRECTORY_HANDLE = None
_DLL_HANDLES = []
_NATIVE_PACKAGE_NAME = "_cp77_physx_native"
_NATIVE_MODULE_NAME = _NATIVE_PACKAGE_NAME + ".pxbridge"
_RUNTIME_OWNER = "i_scene_cp77_gltf"
_REQUIRED_DLLS = (
    "PxFoundation_x64.dll",
    "PhysX3Common_x64.dll",
    "PhysX3_x64.dll",
    "PhysX3Cooking_x64.dll",
    "NvCloth_x64.dll",
)


def install_host(host) -> None:
    """Install host, the bridge's BridgeHost, before the bridge loads"""
    global _HOST
    _HOST = host


def uninstall_host(host=None) -> None:
    global _HOST
    if host is None or _HOST is host:
        _HOST = None


def _host():
    if _HOST is None:
        raise RuntimeError("The PhysX bridge host is not installed")
    return _HOST


def _runtime_cleanup_registry():
    package = _shared_native_state()
    if not hasattr(package, "_cp77_runtime_cleanup_clients"):
        package._cp77_runtime_cleanup_clients = {}
    return package._cp77_runtime_cleanup_clients


def register_runtime_cleanup_client(name, callback):
    key = str(name or "").strip()
    if not key:
        raise ValueError("Runtime cleanup client name is required")
    if not callable(callback):
        raise TypeError("Runtime cleanup callback must be callable")
    registry = _runtime_cleanup_registry()
    identifier = (_RUNTIME_OWNER, key)
    existing = registry.get(identifier)
    if existing is not None and existing is not callback:
        raise RuntimeError(f"PhysX runtime cleanup client already registered: {key}")
    registry[identifier] = callback


def unregister_runtime_cleanup_client(name, callback=None):
    package = sys.modules.get(_NATIVE_PACKAGE_NAME)
    if package is None:
        return
    registry = getattr(package, "_cp77_runtime_cleanup_clients", {})
    identifier = (_RUNTIME_OWNER, str(name or "").strip())
    existing = registry.get(identifier)
    if existing is not None and (callback is None or existing is callback):
        registry.pop(identifier, None)


def _cleanup_runtime_clients(bridge, *, all_owners=False):
    package = sys.modules.get(_NATIVE_PACKAGE_NAME)
    registry = getattr(package, "_cp77_runtime_cleanup_clients", {})
    errors = []
    for (owner, name), callback in tuple(registry.items()):
        if not all_owners and owner != _RUNTIME_OWNER:
            continue
        try:
            callback(bridge)
        except Exception as error:
            debug_exception(
                _LOG, "A native runtime client cleanup failed: %s.%s", owner, name
            )
            errors.append(RuntimeError(f"{owner}.{name}: {error}"))
    return errors


def _shared_runtime_invalidated(bridge):
    # A scene reset leaves the bridge initialized; shutdown and runtime invalidation record their own state
    # after the cleanup clients have run.
    initialized = bool(
        bridge is not None
        and hasattr(bridge, "is_initialized")
        and bridge.is_initialized()
    )
    _mark_scene_runtime_stale(initialized=initialized)
    invalidate_cloth_object_cache()


def _release_native_resources():
    global _DLL_DIRECTORY_HANDLE
    _DLL_HANDLES.clear()
    handle = _DLL_DIRECTORY_HANDLE
    _DLL_DIRECTORY_HANDLE = None
    if handle is not None:
        try:
            handle.close()
        except Exception:
            debug_exception(_LOG, "Could not close a native resource handle")


def _mark_scene_runtime_stale(*, initialized=None):
    if _HOST is not None:
        _HOST.mark_scene_runtime_stale(initialized=initialized)


def reset_native_scene(bridge):
    if not bridge_owned_by_extension() or bridge is not _BRIDGE:
        raise RuntimeError(
            "PhysX scene reset requires the active extension-owned bridge"
        )
    errors = _cleanup_runtime_clients(bridge, all_owners=True)
    if errors:
        raise RuntimeError("; ".join(str(error) for error in errors))
    bridge.reset()


def invalidate_physx_runtime():
    bridge = _BRIDGE
    active_owner = bridge_owned_by_extension()
    errors = _cleanup_runtime_clients(
        bridge if active_owner else None, all_owners=active_owner
    )
    if errors:
        raise RuntimeError("; ".join(str(error) for error in errors))
    if bridge is not None and active_owner:
        if hasattr(bridge, "nvcloth_is_initialized") and hasattr(
            bridge, "nvcloth_shutdown"
        ):
            if bridge.nvcloth_is_initialized():
                bridge.nvcloth_shutdown()
        if hasattr(bridge, "is_initialized") and hasattr(bridge, "reset"):
            if bridge.is_initialized():
                bridge.reset()

    invalidate_cloth_object_cache()
    still_initialized = (
        bool(bridge.is_initialized())
        if bridge is not None and active_owner and hasattr(bridge, "is_initialized")
        else False
    )
    _mark_scene_runtime_stale(initialized=still_initialized)
    if active_owner:
        package = sys.modules.get(_NATIVE_PACKAGE_NAME)
        if package is not None:
            package._cp77_runtime_active_owner = None


def _native_dir():
    return Path(__file__).resolve().parents[1] / "native"


def _physx_dir():
    return _native_dir() / "bin"


def native_python_dir():
    return extensions.native_python_dir(_native_dir(), _host().blender_version)


def native_extension_path(module_name):
    return extensions.native_extension_path(
        _native_dir(), module_name, _host().blender_version
    )


def _bridge_slot():
    return native_extension_path("pxbridge")


def capability_status():
    return _CAPABILITY


def _set_unavailable(reason, path="", *, error=None):
    global _CAPABILITY
    _CAPABILITY = PhysXCapability(
        PhysXCapabilityState.UNAVAILABLE,
        str(reason),
        os.fspath(path) if path else "",
    )
    exc_info = (type(error), error, error.__traceback__) if error is not None else None
    _LOG.warning(
        "PhysX bridge is unavailable: %s", _CAPABILITY.reason, exc_info=exc_info
    )
    return _CAPABILITY


def _shared_native_state():
    """The two Blender extensions coordinate ownership of the single native bridge"""
    package = sys.modules.get(_NATIVE_PACKAGE_NAME)
    if package is None:
        package = types.ModuleType(_NATIVE_PACKAGE_NAME)
        package.__path__ = []
        sys.modules[_NATIVE_PACKAGE_NAME] = package
    if not hasattr(package, "_cp77_runtime_owners"):
        package._cp77_runtime_owners = set()
        package._cp77_runtime_active_owner = None
    return package


def bridge_owned_by_extension():
    package = sys.modules.get(_NATIVE_PACKAGE_NAME)
    return (
        package is not None
        and getattr(package, "_cp77_runtime_active_owner", None) == _RUNTIME_OWNER
    )


def _claim_native_runtime():
    package = _shared_native_state()
    active = package._cp77_runtime_active_owner
    if active is not None and active != _RUNTIME_OWNER:
        raise RuntimeError(
            f"PhysX native bridge is active in {active}; stop its simulation before using {_RUNTIME_OWNER}"
        )
    package._cp77_runtime_active_owner = _RUNTIME_OWNER


def _release_native_runtime():
    package = sys.modules.get(_NATIVE_PACKAGE_NAME)
    if package is None:
        return False, False
    was_active = getattr(package, "_cp77_runtime_active_owner", None) == _RUNTIME_OWNER
    if was_active:
        package._cp77_runtime_active_owner = None
    owners = getattr(package, "_cp77_runtime_owners", set())
    owners.discard(_RUNTIME_OWNER)
    return was_active, not bool(owners)


def initialize_physx_capability():
    global _CAPABILITY, _BRIDGE, _DLL_DIRECTORY_HANDLE
    if _CAPABILITY.state is not PhysXCapabilityState.UNINITIALIZED:
        return _CAPABILITY
    if os.name != "nt":
        return _set_unavailable("PhysX bridge is available only on Windows x64")
    if _HOST is None:
        return _set_unavailable("The PhysX bridge host is not installed")

    bridge_path = _bridge_slot()
    if not bridge_path.is_file():
        stub_path = bridge_path.with_suffix(bridge_path.suffix + ".stub")
        if stub_path.is_file():
            return _set_unavailable(
                f"Replace {stub_path.name} with a compatible pxbridge.pyd",
                bridge_path,
            )
        return _set_unavailable("Compatible pxbridge.pyd is not installed", bridge_path)

    try:
        # The binaries load from a per-process copy so the add-on's own folder stays removable.
        copies = native_runtime_copy(
            [*sorted(_physx_dir().glob("*.dll")), bridge_path],
            "pxbridge-" + bridge_path.parent.name,
        )
    except OSError as error:
        return _set_unavailable(
            f"Could not prepare the native PhysX runtime: {error}",
            bridge_path,
            error=error,
        )
    loaded_path = copies[bridge_path.name]
    existing = sys.modules.get(_NATIVE_MODULE_NAME)
    if existing is not None:
        if Path(getattr(existing, "__file__", "")).resolve() != loaded_path.resolve():
            return _set_unavailable(
                "A different PhysX bridge binary is already loaded", bridge_path
            )
        try:
            validate_current_bridge_contract(existing)
        except Exception as error:
            return _set_unavailable(error, bridge_path, error=error)
        package = _shared_native_state()
        package._cp77_runtime_owners.add(_RUNTIME_OWNER)
        register_runtime_cleanup_client(
            "_capability_scene_state", _shared_runtime_invalidated
        )
        _BRIDGE = existing
        _CAPABILITY = PhysXCapability(
            PhysXCapabilityState.AVAILABLE, "", os.fspath(bridge_path)
        )
        return _CAPABILITY
    module = None
    try:
        if hasattr(os, "add_dll_directory"):
            _DLL_DIRECTORY_HANDLE = os.add_dll_directory(os.fspath(loaded_path.parent))
        for name in _REQUIRED_DLLS:
            path = copies.get(name)
            if path is None:
                raise FileNotFoundError(_physx_dir() / name)
            _DLL_HANDLES.append(ctypes.WinDLL(os.fspath(path)))

        package = _shared_native_state()
        spec = importlib.util.spec_from_file_location(
            _NATIVE_MODULE_NAME,
            os.fspath(loaded_path),
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create extension loader for {bridge_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[_NATIVE_MODULE_NAME] = module
        spec.loader.exec_module(module)
        validate_current_bridge_contract(module)
        package._cp77_runtime_owners.add(_RUNTIME_OWNER)
        register_runtime_cleanup_client(
            "_capability_scene_state", _shared_runtime_invalidated
        )
        _BRIDGE = module
        _CAPABILITY = PhysXCapability(
            PhysXCapabilityState.AVAILABLE,
            "",
            os.fspath(bridge_path),
        )
        return _CAPABILITY
    except Exception as error:
        if sys.modules.get(_NATIVE_MODULE_NAME) is module:
            sys.modules.pop(_NATIVE_MODULE_NAME, None)
        package = sys.modules.get(_NATIVE_PACKAGE_NAME)
        if package is not None and not getattr(package, "_cp77_runtime_owners", set()):
            sys.modules.pop(_NATIVE_PACKAGE_NAME, None)
        _BRIDGE = None
        _release_native_resources()
        return _set_unavailable(error, bridge_path, error=error)


def require_bridge():
    capability = initialize_physx_capability()
    if capability.state is not PhysXCapabilityState.AVAILABLE or _BRIDGE is None:
        raise RuntimeError(capability.reason or "PhysX bridge is unavailable")
    _claim_native_runtime()
    return _BRIDGE


def initialized_bridge():
    bridge = require_bridge()
    initialized = (
        bool(bridge.is_initialized()) if hasattr(bridge, "is_initialized") else False
    )
    if not initialized:
        if not bridge.init():
            raise RuntimeError("PhysX initialization failed")
    return bridge


def shutdown_physx_capability():
    global _CAPABILITY, _BRIDGE
    bridge = _BRIDGE
    active_owner = bridge_owned_by_extension()
    errors = _cleanup_runtime_clients(
        bridge if active_owner else None, all_owners=active_owner
    )
    if errors:
        raise RuntimeError("; ".join(str(error) for error in errors))
    if bridge is not None and active_owner:
        if hasattr(bridge, "nvcloth_is_initialized") and hasattr(
            bridge, "nvcloth_shutdown"
        ):
            if bridge.nvcloth_is_initialized():
                bridge.nvcloth_shutdown()
        if hasattr(bridge, "is_initialized") and hasattr(bridge, "shutdown"):
            if bridge.is_initialized():
                bridge.shutdown()
    _mark_scene_runtime_stale(initialized=False)
    unregister_runtime_cleanup_client(
        "_capability_scene_state", _shared_runtime_invalidated
    )
    _was_active, last_owner = _release_native_runtime()
    if last_owner:
        sys.modules.pop(_NATIVE_MODULE_NAME, None)
        sys.modules.pop(_NATIVE_PACKAGE_NAME, None)
    _BRIDGE = None
    _release_native_resources()
    if last_owner:
        release_native_runtime_copies()
    _CAPABILITY = PhysXCapability(PhysXCapabilityState.UNINITIALIZED)
