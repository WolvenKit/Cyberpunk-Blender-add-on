import math

from ...assetio.values import coerce_float, unwrapped
from ...blender.mesh import uv_by_bounds
from ...core.log import get_logger

_LOG = get_logger(__name__)
_TERRAIN_UV_TOLERANCE = 1.0e-7


def _lookup(data, key, default=None):
    if not isinstance(data, dict):
        return default
    if key in data:
        return data[key]
    folded = str(key).casefold()
    for candidate, value in data.items():
        if str(candidate).casefold() == folded:
            return value
    return default


# The wrappers a material parameter's value sits in.
_PARAMETER_WRAPPERS = ("$value", "value", "scalar", "vector")


def _float_value(data, key, default=0.0):
    return coerce_float(
        unwrapped(_lookup(data, key, default), _PARAMETER_WRAPPERS),
        default,
        unwrap=False,
    )


def _vector4(data, key):
    value = unwrapped(_lookup(data, key), _PARAMETER_WRAPPERS)
    if isinstance(value, dict):
        components = []
        for axis in ("X", "Y", "Z", "W"):
            raw = _lookup(value, axis)
            try:
                component = float(raw)
            except (TypeError, ValueError):
                return None
            if not math.isfinite(component):
                return None
            components.append(component)
        return tuple(components)
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        try:
            result = tuple(float(value[index]) for index in range(4))
        except (TypeError, ValueError):
            return None
        return result if all(math.isfinite(component) for component in result) else None
    return None


def _material_records(mats):
    return {
        str(record.get("Name")): record
        for record in mats or ()
        if isinstance(record, dict) and record.get("Name")
    }


def _terrain_transform(records, names):
    selected_name = None
    selected = None
    old_vertex_format = False
    for name in names or ():
        record = records.get(str(name))
        if record is None:
            continue
        data = record.get("Data") or {}
        if _float_value(data, "UseOldVertexFormat", 0.0) > 0.0:
            if selected is None:
                return None, True
            old_vertex_format = True
            continue
        candidate = _vector4(data, "UVGenScaleOffset")
        if candidate is None:
            continue
        if selected is None:
            selected_name = str(name)
            selected = candidate
            continue
        if any(
            abs(left - right) > _TERRAIN_UV_TOLERANCE
            for left, right in zip(selected, candidate)
        ):
            _LOG.debug(
                "Terrain UV transforms differ across material candidates; "
                "using %s for this submesh instead of %s",
                selected_name,
                name,
            )
            break
    return selected, old_vertex_format


def apply_terrain_generated_uvs(direct_result, mats=(), material_names_by_submesh=None):
    objects = tuple(direct_result.get("objects") or ())
    submeshes = tuple(direct_result["mesh_data"].submeshes)
    if len(objects) != len(submeshes):
        raise RuntimeError(
            f"Terrain mesh result mismatch: {len(objects)} objects "
            f"for {len(submeshes)} submeshes."
        )

    if material_names_by_submesh is None:
        material_names_by_submesh = tuple(
            tuple(str(name) for name in submesh.material_names if name)
            for submesh in submeshes
        )
    else:
        material_names_by_submesh = tuple(
            tuple(str(name) for name in names if name)
            for names in material_names_by_submesh
        )
    if len(material_names_by_submesh) != len(objects):
        raise RuntimeError(
            f"Terrain material plan mismatch: {len(material_names_by_submesh)} plans "
            f"for {len(objects)} objects."
        )

    records = _material_records(mats)
    exact = 0
    fallback = 0
    old_format_missing_uv = 0
    for obj, names in zip(objects, material_names_by_submesh):
        mesh = getattr(obj, "data", None)
        if mesh is None or getattr(obj, "type", None) != "MESH" or mesh.uv_layers:
            continue
        transform, old_vertex_format = _terrain_transform(records, names)
        if transform is not None:
            exact += uv_by_bounds((obj,), scale_offset=transform)
            continue
        if old_vertex_format:
            old_format_missing_uv += 1
        fallback += uv_by_bounds((obj,))

    if old_format_missing_uv:
        _LOG.warning(
            "%d terrain submesh(es) requested UseOldVertexFormat but contained no UVs; "
            "generated local-bounds fallback UVs",
            old_format_missing_uv,
        )
    if exact or fallback:
        _LOG.debug(
            "Generated terrain UVs for %d submesh(es): %d UVGenScaleOffset, %d fallback",
            exact + fallback,
            exact,
            fallback,
        )
    return {
        "updated": exact + fallback,
        "engine": exact,
        "fallback": fallback,
        "old_format_missing_uv": old_format_missing_uv,
    }
