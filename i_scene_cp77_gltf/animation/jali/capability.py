from __future__ import annotations

import importlib
from dataclasses import dataclass
from functools import lru_cache


class _LazyModule:
    def __init__(self, name: str):
        self._name = name

    def __getattr__(self, name: str):
        return getattr(importlib.import_module(self._name), name)


@dataclass(frozen=True)
class DependencyStatus:
    parselmouth: bool
    g2p: bool
    parselmouth_error: str = ""
    g2p_error: str = ""


def _probe(name: str) -> tuple[bool, str]:
    try:
        importlib.import_module(name)
    except ImportError as error:
        return False, str(error)
    except Exception as error:
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

