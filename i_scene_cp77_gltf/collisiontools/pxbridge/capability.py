import ctypes
import importlib.util
import os
import sys
import types
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import bpy


class PhysXCapabilityState(str, Enum):
    UNINITIALIZED = "UNINITIALIZED"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class PhysXCapability:
    state: PhysXCapabilityState
    reason: str = ""
    bridge_path: str = ""


_CAPABILITY = PhysXCapability(PhysXCapabilityState.UNINITIALIZED)
_BRIDGE = None
_DLL_DIRECTORY_HANDLE = None
_DLL_HANDLES = []
_NATIVE_PACKAGE_NAME = "_cp77_physx_native"
_NATIVE_MODULE_NAME = _NATIVE_PACKAGE_NAME + ".pxbridge"
_REQUIRED_DLLS = (
    "PxFoundation_x64.dll",
    "PhysX3Common_x64.dll",
    "PhysX3_x64.dll",
    "PhysX3Cooking_x64.dll",
    "NvCloth_x64.dll",
)



def _release_native_resources():
    global _DLL_DIRECTORY_HANDLE
    _DLL_HANDLES.clear()
    handle = _DLL_DIRECTORY_HANDLE
    _DLL_DIRECTORY_HANDLE = None
    if handle is not None:
        try:
            handle.close()
        except Exception:
            pass

def _package_dir():
    return Path(__file__).resolve().parent


def _physx_dir():
    return _package_dir() / "physx"


def _bridge_slot():
    folder = "blender51_plus" if tuple(bpy.app.version) >= (5, 1, 0) else "blender50"
    return _package_dir() / "native" / folder / "pxbridge.pyd"


def capability_status():
    return _CAPABILITY


def _set_unavailable(reason, path=""):
    global _CAPABILITY
    _CAPABILITY = PhysXCapability(
        PhysXCapabilityState.UNAVAILABLE,
        str(reason),
        os.fspath(path) if path else "",
    )
    return _CAPABILITY


def initialize_physx_capability():
    global _CAPABILITY, _BRIDGE, _DLL_DIRECTORY_HANDLE
    if _CAPABILITY.state is not PhysXCapabilityState.UNINITIALIZED:
        return _CAPABILITY
    if os.name != "nt":
        return _set_unavailable("PhysX bridge is available only on Windows x64")

    bridge_path = _bridge_slot()
    if not bridge_path.is_file():
        stub_path = bridge_path.with_suffix(bridge_path.suffix + ".stub")
        if stub_path.is_file():
            return _set_unavailable(
                f"Replace {stub_path.name} with a compatible pxbridge.pyd",
                bridge_path,
            )
        return _set_unavailable("Compatible pxbridge.pyd is not installed", bridge_path)

    physx_dir = _physx_dir()
    try:
        if hasattr(os, "add_dll_directory"):
            _DLL_DIRECTORY_HANDLE = os.add_dll_directory(os.fspath(physx_dir))
        for name in _REQUIRED_DLLS:
            path = physx_dir / name
            if not path.is_file():
                raise FileNotFoundError(path)
            _DLL_HANDLES.append(ctypes.WinDLL(os.fspath(path)))

        package = sys.modules.get(_NATIVE_PACKAGE_NAME)
        if package is None:
            package = types.ModuleType(_NATIVE_PACKAGE_NAME)
            package.__path__ = []
            sys.modules[_NATIVE_PACKAGE_NAME] = package
        spec = importlib.util.spec_from_file_location(
            _NATIVE_MODULE_NAME,
            os.fspath(bridge_path),
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create extension loader for {bridge_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[_NATIVE_MODULE_NAME] = module
        spec.loader.exec_module(module)
        _BRIDGE = module
        _CAPABILITY = PhysXCapability(
            PhysXCapabilityState.AVAILABLE,
            "",
            os.fspath(bridge_path),
        )
        return _CAPABILITY
    except Exception as error:
        sys.modules.pop(_NATIVE_MODULE_NAME, None)
        sys.modules.pop(_NATIVE_PACKAGE_NAME, None)
        _BRIDGE = None
        _release_native_resources()
        return _set_unavailable(error, bridge_path)


def require_bridge():
    capability = initialize_physx_capability()
    if capability.state is not PhysXCapabilityState.AVAILABLE or _BRIDGE is None:
        raise RuntimeError(capability.reason or "PhysX bridge is unavailable")
    return _BRIDGE


def shutdown_physx_capability():
    global _CAPABILITY, _BRIDGE, _DLL_DIRECTORY_HANDLE
    sys.modules.pop(_NATIVE_MODULE_NAME, None)
    sys.modules.pop(_NATIVE_PACKAGE_NAME, None)
    _BRIDGE = None
    _release_native_resources()
    _CAPABILITY = PhysXCapability(PhysXCapabilityState.UNINITIALIZED)
