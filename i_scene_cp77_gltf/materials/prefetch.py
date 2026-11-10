import os

from ..assetio.catalog import ResourceKind
from ..assetio.paths import LocalPath, is_local_absolute
from ..assetio.resolver import resolve_asset_path
from ..core.log import debug_exception, get_logger
from .params import coerce_texture_path, lookup_param

_LOG = get_logger(__name__)


def _json_reference(reference):
    value = str(reference or "")
    return value if value.casefold().endswith(".json") else f"{value}.json"


def _resolve_reference(reference, roots, extension):
    value = _json_reference(reference)
    if not value:
        return ""
    if is_local_absolute(value):
        return LocalPath.from_value(value).value
    return (
        resolve_asset_path(
            value,
            roots=roots,
            extensions=(extension,),
            warn=False,
        )
        or ""
    )


def _merge_prefetch_stats(target, source, prefix):
    for key, value in source.items():
        target[f"{prefix}_{key}"] = int(value)


def _mask_layer_paths(repository, reference, layer_count, roots):
    value = str(reference or "")
    if not value or layer_count <= 1:
        return ()
    local_reference = value.replace("\\", os.sep).replace("/", os.sep)
    mask_stem = os.path.splitext(os.path.basename(local_reference))[0]
    if not mask_stem:
        return ()
    resolved_paths = []
    seen = set()
    asset_indexes = getattr(repository, "asset_indexes", None)
    if asset_indexes is None:
        return ()
    for layer_index in range(max(0, int(layer_count) - 1)):
        filename = f"{mask_stem}_{layer_index}.png"
        resolved = None
        for root in roots:
            mask_dir = (
                os.path.splitext(os.path.join(root, local_reference))[0] + "_layers"
            )
            candidate = os.path.join(mask_dir, filename)
            try:
                resolved = asset_indexes.resolve(candidate, root, ".png")
            except Exception:
                debug_exception(_LOG, "Could not resolve the mask layer %s", candidate)
                resolved = None
            if resolved:
                break
        if not resolved:
            continue
        key = LocalPath.from_value(resolved).key
        if key in seen:
            continue
        seen.add(key)
        resolved_paths.append(resolved)
    return tuple(resolved_paths)


def prefetch_multilayer_documents(
    repository,
    materials,
    material_indices,
    *,
    project_root="",
    depot_root="",
    max_workers=4,
):
    stats = {
        "setup_documents": 0,
        "template_documents": 0,
        "mask_files": 0,
        "mask_bytes": 0,
    }
    if repository is None or repository.documents is None:
        return stats

    roots = tuple(root for root in (project_root, depot_root) if root)
    setup_paths = []
    material_requests = []
    seen_setup = set()
    resolved_setups = {}
    seen_requests = set()
    for material_index in material_indices:
        try:
            material = materials[material_index]
        except (IndexError, TypeError):
            continue
        data = lookup_param(material, "Data", {})
        setup_reference = coerce_texture_path(lookup_param(data, "MultilayerSetup"))
        if not setup_reference:
            continue
        reference_key = _json_reference(setup_reference)
        if reference_key not in resolved_setups:
            resolved_setups[reference_key] = _resolve_reference(
                setup_reference,
                roots,
                ".mlsetup.json",
            )
        path = resolved_setups[reference_key]
        if not path:
            continue
        mask_reference = coerce_texture_path(lookup_param(data, "MultilayerMask"))
        request = (path, str(mask_reference or ""))
        if request not in seen_requests:
            seen_requests.add(request)
            material_requests.append(request)
        key = LocalPath.from_value(path).key
        if key in seen_setup:
            continue
        seen_setup.add(key)
        setup_paths.append(path)

    if not setup_paths:
        return stats

    setup_prefetch = repository.documents.prefetch(
        setup_paths,
        expected_kind=ResourceKind.MLSETUP,
        max_workers=max_workers,
    )
    _merge_prefetch_stats(stats, setup_prefetch, "setup")

    template_paths = []
    setup_layer_counts = {}
    seen_template = set()
    resolved_templates = {}
    for path in setup_paths:
        document = repository.load(
            path,
            expected_kind=ResourceKind.MLSETUP,
            required=False,
        )
        if document is None:
            continue
        stats["setup_documents"] += 1
        layers = lookup_param(document.root, "layers", ()) or ()
        setup_layer_counts[LocalPath.from_value(path).key] = len(layers)
        for layer in layers:
            material_reference = coerce_texture_path(lookup_param(layer, "material"))
            if not material_reference:
                continue
            reference_key = _json_reference(material_reference)
            if reference_key not in resolved_templates:
                resolved_templates[reference_key] = _resolve_reference(
                    material_reference,
                    roots,
                    ".mltemplate.json",
                )
            template_path = resolved_templates[reference_key]
            if not template_path:
                continue
            key = LocalPath.from_value(template_path).key
            if key in seen_template:
                continue
            seen_template.add(key)
            template_paths.append(template_path)

    template_prefetch = repository.documents.prefetch(
        template_paths,
        expected_kind=ResourceKind.MLTEMPLATE,
        max_workers=max_workers,
    )
    _merge_prefetch_stats(stats, template_prefetch, "template")
    for path in template_paths:
        if (
            repository.load(
                path,
                expected_kind=ResourceKind.MLTEMPLATE,
                required=False,
            )
            is not None
        ):
            stats["template_documents"] += 1

    mask_paths = []
    seen_masks = set()
    for setup_path, mask_reference in material_requests:
        if not mask_reference:
            continue
        layer_count = setup_layer_counts.get(
            LocalPath.from_value(setup_path).key,
            0,
        )
        for mask_path in _mask_layer_paths(
            repository,
            mask_reference,
            layer_count,
            roots,
        ):
            key = LocalPath.from_value(mask_path).key
            if key in seen_masks:
                continue
            seen_masks.add(key)
            mask_paths.append(mask_path)

    warm_files = getattr(repository.documents, "warm_files", None)
    if warm_files is not None and mask_paths:
        mask_prefetch = warm_files(mask_paths, max_workers=max_workers)
        stats["mask_files"] = int(mask_prefetch.get("warmed", 0))
        stats["mask_bytes"] = int(mask_prefetch.get("bytes", 0))
        stats["mask_failed"] = int(mask_prefetch.get("failed", 0))

    return stats
