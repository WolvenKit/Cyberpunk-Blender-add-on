"""Facial-loader entry points backed by canonical JSON and rig data."""

from __future__ import annotations

from .facial_setup_loader import FacialSetupData as FacialSetup, load_facial_setup, load_rig
from ..main.datashards import RigData


def load_wkit_rig_skeleton(path: str) -> RigData:
    return load_rig(path)


def load_wkit_facialsetup(path: str, rig_info: RigData) -> FacialSetup:
    return load_facial_setup(path, rig_info)
