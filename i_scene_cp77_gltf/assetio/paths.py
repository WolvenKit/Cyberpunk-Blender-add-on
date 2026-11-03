import ntpath
import os
import posixpath
import re
from dataclasses import dataclass
from functools import lru_cache

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
# Whether local path lookups ignore letter case (Windows). A case-folding asset index then finds nothing that a direct
# lookup of the same path misses.
LOCAL_PATHS_IGNORE_CASE = os.path.normcase("A") == os.path.normcase("a")


def material_sidecar_path(filepath):
    """Resolve WolvenKit material sidecars without discarding dotted asset names"""
    stem = os.path.splitext(os.fspath(filepath))[0]
    if stem.casefold().endswith((".mesh", ".morphtarget")):
        stem = os.path.splitext(stem)[0]
    return stem + ".Material.json"


def is_morphtarget_path(filepath):
    """Identify the compound glTF suffix used by WolvenKit morph resources"""
    return (
        os.fspath(filepath)
        .casefold()
        .endswith((".morphtarget.glb", ".morphtarget.gltf"))
    )


def is_plain_file_name(name) -> bool:
    """Whether name can name a file on its own"""
    value = str(name or "")
    return (
        bool(value)
        and value not in (".", "..")
        and not any(mark in value for mark in ("/", "\\", ":"))
    )


def strip_windows_extended_prefix(path):
    """path without a \\\\?\\ or \\\\?\\UNC\\ prefix, written with either slash in any case"""
    value = str(path or "")
    prefix = value[:8].replace("/", "\\").upper()
    if prefix == "\\\\?\\UNC\\":
        return "\\\\" + value[8:]
    if prefix.startswith("\\\\?\\"):
        return value[4:]
    return value


def windows_long_path(path):
    """path made absolute in the Windows extended-length form"""
    value = os.fspath(path)
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return value
    value = ntpath.abspath(value)
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value[2:]
    return "\\\\?\\" + value


def is_windows_absolute(path):
    value = strip_windows_extended_prefix(path)
    return bool(_WINDOWS_DRIVE.match(value) or value.startswith("\\\\"))


def is_local_absolute(path):
    value = strip_windows_extended_prefix(path)
    return os.path.isabs(value) or is_windows_absolute(value)


def relative_local_path(path, root):
    path_value = strip_windows_extended_prefix(os.fspath(path))
    root_value = strip_windows_extended_prefix(os.fspath(root))
    if not path_value or not root_value:
        return ""

    windows_path = is_windows_absolute(path_value) or is_windows_absolute(root_value)
    path_module = ntpath if windows_path else os.path
    try:
        normalized_path = path_module.normpath(path_value)
        normalized_root = path_module.normpath(root_value)
        common = path_module.commonpath((normalized_path, normalized_root))
        if path_module.normcase(common) != path_module.normcase(normalized_root):
            return ""
        relative = path_module.relpath(normalized_path, normalized_root)
    except (OSError, ValueError):
        return ""

    if relative == path_module.pardir or relative.startswith(
        path_module.pardir + path_module.sep
    ):
        return ""
    return relative


_UNC_PATH = re.compile(r"^[\\/]{2,}(?=[^\\/:]+[\\/])")
_REPEATED_SEPARATORS = re.compile(r"[\\/]+")


def _entered_path(value):
    """A path as typed or pasted, cleaned up"""
    value = value.strip()
    while len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    prefix = _UNC_PATH.match(value)
    if prefix:
        return "\\\\" + _REPEATED_SEPARATORS.sub("\\\\", value[prefix.end() :])
    return value


@lru_cache(maxsize=131072)
def normalize_local_path(path):
    """An absolute, normalized local path"""
    value = strip_windows_extended_prefix(_entered_path(os.fspath(path)))
    if is_windows_absolute(value):
        return ntpath.normpath(value)
    return os.path.abspath(os.path.normpath(value))


@lru_cache(maxsize=262144)
def local_path_key(path):
    value = strip_windows_extended_prefix(os.fspath(path))
    if is_windows_absolute(value):
        return ntpath.normcase(ntpath.normpath(value)).replace("\\", "/")
    return os.path.normcase(os.path.normpath(value)).replace("\\", "/")


@lru_cache(maxsize=131072)
def absolute_local_path_key(path):
    return local_path_key(normalize_local_path(path))


def same_local_path(left, right) -> bool:
    return local_path_key(left) == local_path_key(right)


@lru_cache(maxsize=262144)
def normalize_depot_path(path):
    value = str(path or "").replace("\\", "/")
    value = posixpath.normpath(value)
    if value == ".":
        return ""
    while value.startswith("./"):
        value = value[2:]
    return value.lstrip("/")


def depot_to_local_fragment(value) -> str:
    """The normalized depot path value with the local separator, to join under a local root"""
    return normalize_depot_path(value).replace("/", os.sep)


def depot_parts(depot_path) -> tuple[str, ...]:
    """The folder and file names of a depot path that names a file inside its root"""
    text = str(depot_path or "")
    if "\x00" in text:
        raise ValueError(f"{depot_path!r} contains a NUL character")
    parts = tuple(part for part in normalize_depot_path(text).split("/") if part)
    if any(part in (".", "..") or ":" in part for part in parts):
        raise ValueError(f"{depot_path} leaves the project's folders")
    return parts


def confined_join(root, path, *, resolve_links=False):
    """path joined under root, for a file that asset data names"""
    parts = depot_parts(path)
    if not parts:
        raise ValueError(f"{path!r} names no file")
    base = os.path.realpath(root) if resolve_links else os.path.abspath(root)
    joined = os.path.join(base, *parts)
    candidate = os.path.realpath(joined) if resolve_links else joined
    try:
        inside = os.path.commonpath((base, candidate)) == base
    except ValueError:
        inside = False
    if not inside:
        raise ValueError(f"{path} leaves {root}")
    return candidate


@lru_cache(maxsize=262144)
def depot_path_key(path):
    return normalize_depot_path(path).casefold()


@lru_cache(maxsize=2048)
def _backslash_depot_key(value):
    return value.replace("/", "\\").casefold()


def backslash_depot_key(path):
    """path case-folded with backslash separators"""
    return _backslash_depot_key(str(path or ""))


def strip_json_suffix(path):
    """The path without its trailing .json suffixes"""
    value = str(path or "")
    while value.casefold().endswith(".json"):
        value = value[:-5]
    return value


def animgraph_json_path(path):
    """path ending in exactly one .animgraph.json, whatever .animgraph / .json endings it had"""
    value = strip_json_suffix(path)
    while value.casefold().endswith(".animgraph"):
        value = value[:-10]
    return value + ".animgraph.json"


@lru_cache(maxsize=32)
def _source_tree_pattern(tree):
    name = str(tree or "").strip().strip("/\\")
    if not name or "/" in name or "\\" in name:
        raise ValueError(f"Invalid source tree name: {tree!r}")
    return re.compile(rf"(?:^|/)source/{re.escape(name)}(?=$|/)", re.IGNORECASE)


def split_source_tree_root(filepath: str, tree: str) -> tuple[str, str]:
    if not filepath:
        return "", ""
    value = strip_windows_extended_prefix(os.fspath(filepath))
    path_module = ntpath if is_windows_absolute(value) else os.path
    normalized = path_module.normpath(value)
    match = _source_tree_pattern(tree).search(normalized.replace("\\", "/"))
    if match is None:
        return "", ""
    end = match.end()
    root = normalized[:end]
    remainder = normalized[end:].lstrip("/\\")
    return root, path_module.normpath(remainder) if remainder else ""


def split_source_raw_root(filepath: str) -> tuple[str, str]:
    root, remainder = split_source_tree_root(filepath, "raw")
    if root:
        return root, remainder
    if not filepath:
        return "", ""
    value = strip_windows_extended_prefix(os.fspath(filepath))
    path_module = ntpath if is_windows_absolute(value) else os.path
    normalized = path_module.normpath(value)
    return path_module.dirname(normalized), path_module.basename(normalized)


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
