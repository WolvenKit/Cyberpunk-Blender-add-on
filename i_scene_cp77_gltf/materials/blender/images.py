from ...blender.transactions import track_created_datablock
import ntpath
import os
from functools import lru_cache

import bpy
import numpy as np

from .profiling import begin_material_phase, end_material_phase

_image_lookup_cache = {}
_image_lookup_complete = False
_image_lookup_count = -1

def _image_format_extension(image_format):
    if not image_format:
        return ''
    return image_format if image_format.startswith('.') else f'.{image_format}'


def _with_image_extension(path, image_format):
    ext = _image_format_extension(image_format)
    return f'{path[:-4]}{ext}' if path.lower().endswith('.xbm') else f'{path[:-3]}{image_format}'


def _strip_windows_extended_prefix(path):
    if not path:
        return path
    normalized = str(path).replace('/', '\\')
    lowered = normalized.lower()
    if lowered.startswith('\\\\?\\unc\\'):
        return '\\\\' + normalized[8:]
    if lowered.startswith('\\\\?\\'):
        return normalized[4:]
    return normalized


def _looks_like_windows_path(path):
    if not path:
        return False
    path = str(path)
    drive, tail = ntpath.splitdrive(path)
    return bool(drive) or path.startswith('\\\\')


def _join_root_reference(root, reference):
    if _looks_like_windows_path(root):
        return ntpath.join(str(root), str(reference).replace('/', '\\'))
    return os.path.join(root, reference)


@lru_cache(maxsize=32768)
def _cached_filepath_key(path):
    path = _strip_windows_extended_prefix(path)
    if _looks_like_windows_path(path):
        return ntpath.normcase(ntpath.normpath(path))
    try:
        path = bpy.path.abspath(path)
    except Exception:
        pass
    return os.path.normcase(os.path.abspath(os.path.normpath(path)))


def _filepath_key(path):
    if not path:
        return ''
    try:
        path = os.fspath(path)
    except TypeError:
        path = str(path)
    if path.startswith('//'):
        try:
            path = bpy.path.abspath(path)
        except Exception:
            pass
    return _cached_filepath_key(path)


def _matches_colorspace(image, is_normal):
    non_color = image.colorspace_settings.name == 'Non-Color'
    return non_color if is_normal else not non_color


def _rebuild_image_lookup_cache():
    global _image_lookup_complete, _image_lookup_count
    _image_lookup_cache.clear()
    for image in bpy.data.images:
        filepath = getattr(image, 'filepath', '')
        filepath_key = _filepath_key(filepath)
        if filepath_key:
            is_normal = image.colorspace_settings.name == 'Non-Color'
            _image_lookup_cache.setdefault((filepath_key, is_normal), image.name)
    _image_lookup_count = len(bpy.data.images)
    _image_lookup_complete = True


def _find_loaded_image(filepath, is_normal=False):
    global _image_lookup_complete
    started = begin_material_phase()
    result = None
    try:
        filepath_key = _filepath_key(filepath)
        if not filepath_key:
            return None

        if not _image_lookup_complete or _image_lookup_count != len(bpy.data.images):
            _rebuild_image_lookup_cache()

        key = (filepath_key, bool(is_normal))
        cached_name = _image_lookup_cache.get(key)
        if not cached_name:
            return None

        image = bpy.data.images.get(cached_name)
        if image and _filepath_key(image.filepath) == filepath_key and _matches_colorspace(image, is_normal):
            result = image
            return result

        _rebuild_image_lookup_cache()
        cached_name = _image_lookup_cache.get(key)
        image = bpy.data.images.get(cached_name) if cached_name else None
        result = image if image and _matches_colorspace(image, is_normal) else None
        return result
    finally:
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
        from ..resources import active_material_asset_indexes

        ext = _image_format_extension(image_format)
        indexes = active_material_asset_indexes()
        if not ext or indexes is None:
            return None

        root = os.path.abspath(os.path.normpath(root.replace('\\', os.sep)))
        local_reference = reference.replace('\\', os.sep).replace('/', os.sep)
        indexed_reference = _with_image_extension(local_reference, image_format)
        try:
            resolved = indexes.resolve(indexed_reference, root, ext)
        except Exception:
            resolved = None
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


def _new_file_image(name, filepath, is_normal=False):
    global _image_lookup_count
    started = begin_material_phase()
    image = None
    try:
        image = track_created_datablock("images", bpy.data.images.new(name, 1, 1))
        image.source = 'FILE'
        image.alpha_mode = 'CHANNEL_PACKED'
        image.filepath = filepath
        if is_normal:
            image.colorspace_settings.name = 'Non-Color'
        _image_lookup_cache[(_filepath_key(filepath), bool(is_normal))] = image.name
        _image_lookup_count = len(bpy.data.images)
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
    global _image_lookup_complete, _image_lookup_count
    _image_lookup_cache.clear()
    _image_lookup_complete = False
    _image_lookup_count = -1
    _cached_filepath_key.cache_clear()


def imageFromPath(Img, image_format, isNormal=False):
    filepath = _with_image_extension(Img, image_format)
    image = _find_loaded_image(filepath, isNormal)
    if image:
        return image

    return _new_file_image(os.path.basename(Img)[:-4], filepath, isNormal)


def resolve_relative_image_path(ImgPath, image_format='png', DepotPath='', ProjPath=''):
    """Resolve a relative image through project/depot asset index snapshots."""
    if isinstance(ImgPath, float) or isinstance(ProjPath, float):
        return None
    return (
        _resolve_indexed_image(ImgPath, ProjPath, image_format)
        or _resolve_indexed_image(ImgPath, DepotPath, image_format)
    )


def imageFromRelPath(ImgPath, image_format='png', isNormal=False, DepotPath='', ProjPath=''):
    DepotPath = DepotPath.replace('\\', os.sep)
    ProjPath = ProjPath.replace('\\', os.sep)
    if isinstance(ImgPath, float):
        print(f"refusing to process unresolved relative image path {ImgPath}")
        return
    if isinstance(ProjPath, float):
        print(f"refusing to process unresolved project path {ProjPath}")
        return

    inProj = _with_image_extension(_join_root_reference(ProjPath, ImgPath), image_format)
    inDepot = _with_image_extension(_join_root_reference(DepotPath, ImgPath), image_format)

    image = _find_loaded_image(inProj, isNormal) or _find_loaded_image(inDepot, isNormal)
    if image:
        return image

    resolved = resolve_relative_image_path(
        ImgPath,
        image_format=image_format,
        DepotPath=DepotPath,
        ProjPath=ProjPath,
    )
    if resolved:
        image = _find_loaded_image(resolved, isNormal)
        if image:
            return image
    else:
        # Preserve the legacy unresolved-file placeholder without performing an
        # independent filesystem probe. Project overrides are selected by the
        # index; an unresolved reference retains the depot candidate as provenance.
        resolved = inDepot or inProj

    return _new_file_image(os.path.basename(ImgPath)[:-4], resolved, isNormal)


def image_has_alpha(img):
    b = 32 if img.is_float else 8
    return (
            img.depth == 2 * b or  # Grayscale+Alpha
            img.depth == 4 * b  # RGB+Alpha
    )


def crop_image(orig_img, outname, cropped_min_x, cropped_max_x, cropped_min_y, cropped_max_y):
    """Crop a Blender image with one bulk RNA read and write."""
    channels = int(orig_img.channels)
    source_width, source_height = map(int, orig_img.size)
    width = int(cropped_max_x - cropped_min_x)
    height = int(cropped_max_y - cropped_min_y)
    if width <= 0 or height <= 0:
        raise ValueError("Crop bounds produce an empty image")

    source = np.empty(source_width * source_height * channels, dtype=np.float32)
    orig_img.pixels.foreach_get(source)
    source = source.reshape(source_height, source_width, channels)
    y_start = source_height - int(cropped_max_y)
    y_end = source_height - int(cropped_min_y)
    cropped = np.ascontiguousarray(
            source[y_start:y_end, int(cropped_min_x):int(cropped_max_x), :]
            )

    cropped_img = track_created_datablock("images", bpy.data.images.new(
            name=outname, width=width, height=height, alpha=channels == 4
            ))
    cropped_img.pixels.foreach_set(cropped.reshape(-1))
    cropped_img.update()
    return cropped_img
