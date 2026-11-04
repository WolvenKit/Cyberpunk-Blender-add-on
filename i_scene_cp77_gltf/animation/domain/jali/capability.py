from __future__ import annotations

import importlib
from dataclasses import dataclass
from functools import lru_cache

from ....assetio.resources import get_nltk_data_dir
from ....core.log import debug_exception, get_logger

_LOG = get_logger(__name__)


def _use_bundled_nltk_data() -> None:
    """Search the add-on's NLTK data first"""
    import nltk

    folder = get_nltk_data_dir()
    if folder not in nltk.data.path:
        nltk.data.path.insert(0, folder)


def _import(name: str):
    if name == "g2p_en":
        _use_bundled_nltk_data()
    return importlib.import_module(name)


class _LazyModule:
    def __init__(self, name: str):
        self._name = name

    def __getattr__(self, name: str):
        return getattr(_import(self._name), name)


@dataclass(frozen=True)
class DependencyStatus:
    parselmouth: bool
    g2p: bool
    parselmouth_error: str = ""
    g2p_error: str = ""


def _probe(name: str) -> tuple[bool, str]:
    try:
        _import(name)
    except ImportError as error:
        return False, str(error)
    except Exception as error:
        debug_exception(
            _LOG, "Could not import %s; that capability is unavailable", name
        )
        return False, f"{type(error).__name__}: {error}"
    return True, ""


@lru_cache(maxsize=1)
def dependency_status() -> DependencyStatus:
    parselmouth_available, parselmouth_error = _probe("parselmouth")
    g2p_available, g2p_error = _probe("g2p_en")
    return DependencyStatus(
        parselmouth=parselmouth_available,
        g2p=g2p_available,
        parselmouth_error=parselmouth_error,
        g2p_error=g2p_error,
    )


parselmouth = _LazyModule("parselmouth")
g2p_en = _LazyModule("g2p_en")


def call(*args, **kwargs):
    return importlib.import_module("parselmouth.praat").call(*args, **kwargs)
