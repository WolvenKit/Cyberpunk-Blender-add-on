import ntpath
import os
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache

import bpy

from ...assetio.index import build_asset_index, files_by_name
from ...assetio.names import fnv1a64
from ...assetio.paths import is_windows_absolute, strip_windows_extended_prefix
from ...blender.identity import rna_identity
from ...blender.image_cache import LoadedImageIndex
from ...blender.transactions import track_created_datablock
from ...core.log import get_logger
from ..resources import active_material_asset_indexes
from .helper_caches import register_helper_cache
from .profiling import begin_material_phase, end_material_phase

_LOG = get_logger(__name__)

_image_load_failures = {}
_image_failure_captures = []
_material_placeholder_sources = {}

# The mesh whose materials are being built, whose embedded textures sit beside it in the .mesh_embedded folder a
# WolvenKit export leaves there.
_EMBEDDING_MESH = ContextVar("cp77_embedding_mesh", default="")
_EMBEDDED_FOLDER_SUFFIX = ".mesh_embedded"

_IMAGE_PLACEHOLDER_PROP = "_cp77_image_placeholder"
_IMAGE_SOURCE_PATH_PROP = "_cp77_image_source_path"
_UI_DEFAULT_IMAGE_PROP = "_cp77_ui_default_image"
_ui_default_image_name = ""


@lru_cache(maxsize=64)
def _image_format_extension(image_format):
    if not image_format:
        return ""
    value = str(image_format)
    return value if value.startswith(".") else f".{value}"


@lru_cache(maxsize=32768)
def _with_image_extension(path, image_format):
    path = str(path or "")
    extension = _image_format_extension(image_format)
    if not path or not extension:
        return path
    root, current_extension = ntpath.splitext(path)
    return f"{root}{extension}" if current_extension else f"{path}{extension}"


def _image_name(reference):
    return ntpath.splitext(ntpath.basename(str(reference or "")))[0]


def _join_root_reference(root, reference):
    if is_windows_absolute(root):
        return ntpath.join(str(root), str(reference).replace("/", "\\"))
    return os.path.join(root, reference)


@lru_cache(maxsize=32768)
def _cached_filepath_key(path):
    path = strip_windows_extended_prefix(path)
    if is_windows_absolute(path):
        return ntpath.normcase(ntpath.normpath(path))
    path = bpy.path.abspath(path)
    return os.path.normcase(os.path.abspath(os.path.normpath(path)))


def _filepath_key(path):
    if not path:
        return ""
    try:
        path = os.fspath(path)
    except TypeError:
        path = str(path)
    if path.startswith("//"):
        path = bpy.path.abspath(path)
    return _cached_filepath_key(path)


def _file_is_available(filepath):
    filepath_key = _filepath_key(filepath)
    return bool(filepath_key and os.path.isfile(filepath_key))


def _image_source_path(image):
    try:
        stored = image.get(_IMAGE_SOURCE_PATH_PROP, "")
    except ReferenceError:
        stored = ""
    return stored or getattr(image, "filepath", "")


def image_is_placeholder(image):
    try:
        return bool(image.get(_IMAGE_PLACEHOLDER_PROP, False))
    except ReferenceError:
        return False


def _is_ui_default_image(image):
    if image is None or image.get(_UI_DEFAULT_IMAGE_PROP) != 1:
        return False
    if image.source != "GENERATED" or tuple(image.size) != (4, 4):
        return False
    if image.generated_type != "BLANK" or image.alpha_mode != "STRAIGHT":
        return False
    if tuple(image.generated_color) != (0.0, 0.0, 0.0, 1.0):
        return False
    return tuple(image.pixels[:]) == (0.0, 0.0, 0.0, 1.0) * 16


def ui_default_render_image():
    """Reuse an owned, unmodified UI default while preserving author edits"""
    global _ui_default_image_name
    image = bpy.data.images.get(_ui_default_image_name)
    if _is_ui_default_image(image):
        return image
    for image in bpy.data.images:
        if _is_ui_default_image(image):
            _ui_default_image_name = image.name
            return image
    before_count = len(bpy.data.images)
    image = track_created_datablock(
        "images",
        bpy.data.images.new(
            "CP77 UI Default Render Texture", width=4, height=4, alpha=True
        ),
    )
    image.generated_type = "BLANK"
    image.generated_color = (0.0, 0.0, 0.0, 1.0)
    image.alpha_mode = "STRAIGHT"
    image[_UI_DEFAULT_IMAGE_PROP] = 1
    _ui_default_image_name = image.name
    _LOADED_IMAGES.count_unindexed_image(before_count)
    return image


def _image_lookup_key(image):
    filepath_key = _filepath_key(_image_source_path(image))
    if not filepath_key:
        return None
    return filepath_key, image.colorspace_settings.name == "Non-Color"


_LOADED_IMAGES = LoadedImageIndex(_image_lookup_key)


def _find_loaded_image(filepath, is_normal=False):
    started = begin_material_phase()
    result = None
    try:
        filepath_key = _filepath_key(filepath)
        if not filepath_key:
            return None
        image = _LOADED_IMAGES.find((filepath_key, bool(is_normal)))
        if (
            image is not None
            and image_is_placeholder(image)
            and _file_is_available(filepath)
        ):
            return None
        result = image
        return result
    finally:
        if result is not None and image_is_placeholder(result):
            _record_image_load_failure(filepath, None)
        if started is not None:
            end_material_phase(
                started,
                "material.image_lookup",
                label=str(filepath or ""),
                metadata={"hit": result is not None, "nonColor": bool(is_normal)},
            )


def _resolve_indexed_image(reference, root, image_format):
    started = begin_material_phase()
    resolved = None
    original_root = root
    try:
        if not reference or not root:
            return None

        ext = _image_format_extension(image_format)
        indexes = active_material_asset_indexes()
        if not ext or indexes is None:
            return None

        root = os.path.abspath(os.path.normpath(root.replace("\\", os.sep)))
        local_reference = reference.replace("\\", os.sep).replace("/", os.sep)
        indexed_reference = _with_image_extension(local_reference, image_format)
        try:
            resolved = indexes.resolve(indexed_reference, root, ext)
        except (OSError, ValueError):
            return None
        return resolved
    finally:
        if started is not None:
            end_material_phase(
                started,
                "material.image_resolve",
                label=str(reference or ""),
                metadata={
                    "resolved": bool(resolved),
                    "root": str(root or original_root or ""),
                },
            )


def _cache_image(image, filepath, is_normal):
    _LOADED_IMAGES.remember((_filepath_key(filepath), bool(is_normal)), image)


def _record_image_load_failure(filepath, error):
    key = _filepath_key(filepath) or str(filepath or "")
    entry = (
        str(filepath or ""),
        f"{type(error).__name__}: {error}" if error is not None else "not found",
    )
    _image_load_failures.setdefault(key, entry)
    for capture in _image_failure_captures:
        capture.setdefault(key, entry)


def clear_image_load_failures():
    _image_load_failures.clear()


def consume_image_load_failures():
    failures = tuple(_image_load_failures.values())
    _image_load_failures.clear()
    return failures


def begin_image_failure_capture():
    """Start collecting texture failures"""
    capture = {}
    _image_failure_captures.append(capture)
    return capture


def end_image_failure_capture(capture):
    for index in range(len(_image_failure_captures) - 1, -1, -1):
        if _image_failure_captures[index] is capture:
            del _image_failure_captures[index]
            break
    return tuple(capture.values())


def _placeholder_sources(node_tree, visited):
    for node in node_tree.nodes:
        image = getattr(node, "image", None)
        if image is not None and image_is_placeholder(image):
            yield _image_source_path(image)
        group = getattr(node, "node_tree", None)
        if group is not None and rna_identity(group) not in visited:
            visited.add(rna_identity(group))
            yield from _placeholder_sources(group, visited)


def record_material_placeholders(material):
    """Report placeholder textures of a material reused from the material cache"""
    key = (rna_identity(material), getattr(material, "name", ""))
    sources = _material_placeholder_sources.get(key)
    if sources is None:
        node_tree = getattr(material, "node_tree", None)
        sources = (
            tuple(dict.fromkeys(_placeholder_sources(node_tree, set())))
            if node_tree is not None
            else ()
        )
        _material_placeholder_sources[key] = sources
    for source in sources:
        _record_image_load_failure(source, None)


def image_load_failure_message(failures, *, limit=3):
    entries = (
        tuple(failures.values()) if isinstance(failures, dict) else tuple(failures)
    )
    if not entries:
        return ""
    sample = ", ".join(path for path, _reason in entries[:limit])
    if len(entries) > limit:
        sample += f", and {len(entries) - limit} more"
    return (
        f"{len(entries)} texture file(s) could not be loaded; "
        f"valid generated placeholders were used: {sample}"
    )


def _new_placeholder_image(name, filepath, is_normal=False, error=None):
    image = track_created_datablock(
        "images",
        bpy.data.images.new(name, width=1, height=1, alpha=True),
    )
    image.generated_type = "BLANK"
    image.generated_color = (1.0, 0.0, 1.0, 1.0)
    image.alpha_mode = "CHANNEL_PACKED"
    image.filepath = filepath
    image[_IMAGE_PLACEHOLDER_PROP] = True
    image[_IMAGE_SOURCE_PATH_PROP] = filepath
    if is_normal:
        image.colorspace_settings.name = "Non-Color"
    _cache_image(image, filepath, is_normal)
    _record_image_load_failure(filepath, error)
    return image


def _new_file_image(name, filepath, is_normal=False):
    started = begin_material_phase()
    image = None
    try:
        try:
            image = track_created_datablock(
                "images",
                bpy.data.images.load(filepath, check_existing=False),
            )
        except (OSError, RuntimeError, ValueError) as error:
            image = _new_placeholder_image(
                name,
                filepath,
                is_normal,
                error,
            )
            return image

        image.name = name
        # Each of these assignments signals an image reload, even when the value is unchanged.
        if image.alpha_mode != "CHANNEL_PACKED":
            image.alpha_mode = "CHANNEL_PACKED"
        if image.filepath != filepath:
            image.filepath = filepath
        if is_normal and image.colorspace_settings.name != "Non-Color":
            image.colorspace_settings.name = "Non-Color"
        _cache_image(image, filepath, is_normal)
        return image
    finally:
        if started is not None:
            end_material_phase(
                started,
                "material.image_create",
                label=str(filepath or ""),
                metadata={
                    "nonColor": bool(is_normal),
                    "image": getattr(image, "name", ""),
                },
            )


def clear_image_lookup_cache():
    global _ui_default_image_name
    _LOADED_IMAGES.clear()
    _material_placeholder_sources.clear()
    _ui_default_image_name = ""
    _cached_filepath_key.cache_clear()
    _with_image_extension.cache_clear()
    _image_format_extension.cache_clear()


def image_lookup_cache_stats():
    return {
        "entries": len(_LOADED_IMAGES),
        "indexed": _LOADED_IMAGES.complete,
        "indexed_images": _LOADED_IMAGES.indexed_images,
        "path_keys": _cached_filepath_key.cache_info().currsize,
        "extension_paths": _with_image_extension.cache_info().currsize,
    }


register_helper_cache(
    "images",
    clear=clear_image_lookup_cache,
    stats=image_lookup_cache_stats,
)


def imageFromPath(Img, image_format, isNormal=False):
    filepath = _with_image_extension(Img, image_format)
    image = _find_loaded_image(filepath, isNormal)
    if image:
        return image

    return _new_file_image(_image_name(Img), filepath, isNormal)


def imageFromFilePath(filepath, isNormal=False):
    filepath = os.path.abspath(os.fspath(filepath))
    image = _find_loaded_image(filepath, isNormal)
    if image:
        return image
    name = os.path.splitext(os.path.basename(filepath))[0]
    return _new_file_image(name, filepath, isNormal)


@contextmanager
def embedded_textures_of(mesh_path):
    """Let the textures mesh_path embeds resolve while its materials build"""
    token = _EMBEDDING_MESH.set(str(mesh_path or ""))
    try:
        yield
    finally:
        _EMBEDDING_MESH.reset(token)


def _embedded_files(root, extension, *, depth=None):
    """The extension files of the .mesh_embedded folders under root, by lower-case file name"""
    index = build_asset_index(root, (extension,), depth=depth)
    return files_by_name(index, extension, folder_suffix=_EMBEDDED_FOLDER_SUFFIX)


def _resolve_embedded_image(reference, image_format, roots):
    """A texture a mesh embeds"""
    ext = _image_format_extension(image_format)
    if not reference or not ext:
        return None
    parts = [part for part in str(reference).replace("/", "\\").split("\\") if part]
    if not parts:
        return None
    embedded = parts[0].casefold() == "_embedded"
    if embedded:
        name = os.path.splitext(parts[-1])[0]
        if not name.isdigit():
            return None
    else:
        name = str(fnv1a64("\\".join(parts).lower()))
    relative = []
    if not embedded:
        relative.append(os.path.join(*parts[:-1]) if len(parts) > 1 else "")
    mesh = _EMBEDDING_MESH.get()
    mesh_folder = os.path.dirname(os.path.abspath(mesh)) if mesh else ""
    project = next(
        (
            root
            for root in roots
            if root
            and mesh_folder
            and os.path.normcase(mesh_folder).startswith(
                os.path.normcase(os.path.abspath(root))
            )
        ),
        "",
    )
    if project:
        relative.append(os.path.relpath(mesh_folder, os.path.abspath(project)))
    directories = [
        os.path.join(root, folder) for root in roots if root for folder in relative
    ]
    if mesh_folder and not project:
        directories.append(mesh_folder)
    filename = name + ext
    for directory in dict.fromkeys(
        os.path.normpath(directory) for directory in directories
    ):
        if os.path.isdir(directory):
            found = _embedded_files(directory, ext, depth=1).get(filename.casefold())
            if found:
                return found
    if embedded and project:
        # Another mesh of the project can embed the texture a material names, so its folders are searched too.
        return _embedded_files(os.path.abspath(project), ext).get(filename.casefold())
    return None


def resolve_relative_image_path(ImgPath, image_format="png", DepotPath="", ProjPath=""):
    """Resolve a relative image through the asset index, then among the textures meshes embed"""
    if isinstance(ImgPath, float) or isinstance(ProjPath, float):
        return None
    return (
        _resolve_indexed_image(ImgPath, ProjPath, image_format)
        or _resolve_indexed_image(ImgPath, DepotPath, image_format)
        or _resolve_embedded_image(ImgPath, image_format, (ProjPath, DepotPath))
    )


def imageFromRelPath(
    ImgPath, image_format="png", isNormal=False, DepotPath="", ProjPath=""
):
    DepotPath = DepotPath.replace("\\", os.sep)
    ProjPath = ProjPath.replace("\\", os.sep)
    if isinstance(ImgPath, float):
        _LOG.warning("Refusing unresolved relative image path %s", ImgPath)
        return
    if isinstance(ProjPath, float):
        _LOG.warning("Refusing unresolved project image path %s", ProjPath)
        return

    inProj = _with_image_extension(
        _join_root_reference(ProjPath, ImgPath), image_format
    )
    inDepot = _with_image_extension(
        _join_root_reference(DepotPath, ImgPath), image_format
    )

    image = _find_loaded_image(inProj, isNormal)
    if image:
        return image

    resolved = resolve_relative_image_path(
        ImgPath,
        image_format=image_format,
        DepotPath=DepotPath,
        ProjPath=ProjPath,
    )
    if not resolved:
        # Preserve the unresolved-file placeholder without performing an
        # independent filesystem probe. Project overrides are selected by the
        # index; an unresolved reference retains the depot candidate as provenance.
        resolved = inDepot or inProj

    image = _find_loaded_image(resolved, isNormal)
    if image:
        return image
    return _new_file_image(_image_name(ImgPath), resolved, isNormal)


def image_has_alpha(img):
    b = 32 if img.is_float else 8
    return (
        img.depth == 2 * b  # Grayscale+Alpha
        or img.depth == 4 * b  # RGB+Alpha
    )
