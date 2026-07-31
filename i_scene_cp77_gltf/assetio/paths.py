import ntpath
import os
import posixpath
import re
from dataclasses import dataclass
from functools import lru_cache


_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


def _strip_windows_extended_prefix(path):
    value = str(path or "")
    if value.startswith("\\\\?\\UNC\\"):
        return "\\\\" + value[8:]
    if value.startswith("\\\\?\\"):
        return value[4:]
    return value


def is_windows_absolute(path):
    value = _strip_windows_extended_prefix(path)
    return bool(_WINDOWS_DRIVE.match(value) or value.startswith("\\\\"))


def is_local_absolute(path):
    value = _strip_windows_extended_prefix(path)
    return os.path.isabs(value) or is_windows_absolute(value)


@lru_cache(maxsize=131072)
def normalize_local_path(path):
    value = _strip_windows_extended_prefix(os.fspath(path))
    if is_windows_absolute(value):
        return ntpath.normpath(value)
    return os.path.abspath(os.path.normpath(value))


@lru_cache(maxsize=262144)
def local_path_key(path):
    value = _strip_windows_extended_prefix(os.fspath(path))
    if is_windows_absolute(value):
        return ntpath.normcase(ntpath.normpath(value)).replace("\\", "/")
    return os.path.normcase(os.path.normpath(value)).replace("\\", "/")


@lru_cache(maxsize=262144)
def normalize_depot_path(path):
    value = str(path or "").replace("\\", "/")
    value = posixpath.normpath(value)
    if value == ".":
        return ""
    while value.startswith("./"):
        value = value[2:]
    return value.lstrip("/")


@lru_cache(maxsize=262144)
def depot_path_key(path):
    return normalize_depot_path(path).casefold()


@dataclass(frozen=True, slots=True)
class LocalPath:
    value: str

    @classmethod
    def from_value(cls, path):
        return cls(normalize_local_path(path))

    @property
    def key(self):
        return local_path_key(self.value)

    def __fspath__(self):
        return self.value

    def __str__(self):
        return self.value


@dataclass(frozen=True, slots=True)
class DepotPath:
    value: str

    @classmethod
    def from_value(cls, path):
        return cls(normalize_depot_path(path))

    @property
    def key(self):
        return depot_path_key(self.value)

    def __str__(self):
        return self.value
