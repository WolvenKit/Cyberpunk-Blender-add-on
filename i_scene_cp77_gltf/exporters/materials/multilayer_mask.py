import ntpath
import os
import tempfile

from ...assetio.atomic import atomic_replace_staged
from ...blender.operator_results import OperationResult
from ...core.log import debug_exception, get_logger
from ...materials.blender.multilayer import layer_nodes, linked_source, multilayer_root
from .project_paths import replace_depot_suffix, source_raw_relative

_LOG = get_logger(__name__)


def _resource_stem(resource_path, suffix):
    name = ntpath.basename(str(resource_path or "").replace("/", "\\"))
    if name.casefold().endswith(suffix.casefold()):
        return name[: -len(suffix)]
    return ntpath.splitext(name)[0]


def _mask_image(layer):
    inputs = getattr(layer, "inputs", None)
    mask_socket = inputs.get("Mask") if inputs is not None else None
    source = linked_source(mask_socket)
    visited = set()
    while source is not None and id(source) not in visited:
        visited.add(id(source))
        if getattr(source, "type", None) == "TEX_IMAGE":
            return getattr(source, "image", None)
        if getattr(source, "type", None) != "REROUTE":
            return None
        reroute_inputs = getattr(source, "inputs", None)
        source = linked_source(reroute_inputs[0] if reroute_inputs else None)
    return None


def _save_image_staged(image, directory, final_path, export_format, extension):
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(final_path)}.",
        suffix=f".{extension}",
        dir=directory,
    )
    os.close(descriptor)
    try:
        os.unlink(temporary_path)
    except OSError:
        debug_exception(_LOG, "Could not remove the temporary file %s", temporary_path)

    original_format = image.file_format
    try:
        image.file_format = export_format
        image.save(filepath=temporary_path, save_copy=True)
    finally:
        image.file_format = original_format

    if not os.path.isfile(temporary_path) or os.path.getsize(temporary_path) == 0:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
        raise OSError(f"Blender did not write mask image {image.name}")
    return temporary_path


def cp77_mlmask_export(context, filepath, export_format):
    """Write the active material's layer masks and the .masklist that orders them"""
    active_object = getattr(context, "active_object", None)
    active_material = (
        getattr(active_object, "active_material", None)
        if active_object is not None
        else None
    )
    node_tree = (
        getattr(active_material, "node_tree", None)
        if active_material is not None
        else None
    )
    if active_material is None or node_tree is None:
        return OperationResult.cancelled(
            "Select a mesh with an editable multilayer material."
        )

    mlmask_path = str(active_material.get("MultilayerMask", "") or "")
    if not mlmask_path:
        return OperationResult.cancelled(
            "Active material does not contain a MultilayerMask resource path."
        )

    root = multilayer_root(node_tree.nodes)
    if root is None:
        return OperationResult.cancelled(
            "Multilayered shader node not found within selected material."
        )

    linked_layers = dict(layer_nodes(node_tree.nodes, root, 20, False))
    if not linked_layers:
        return OperationResult.cancelled("No linked multilayer layers were found.")
    layer_count = max(linked_layers) + 1
    if layer_count < 2:
        return OperationResult.cancelled(
            "A multilayer mask set requires at least two material layers."
        )

    ext_map = {"PNG": "png", "JPEG": "jpg", "TARGA": "tga", "TIFF": "tif"}
    extension = ext_map.get(export_format)
    if extension is None:
        return OperationResult.cancelled(
            f"Unsupported mask export format: {export_format}"
        )

    mask_stem = _resource_stem(mlmask_path, ".mlmask")
    if not mask_stem:
        return OperationResult.cancelled(
            "The MultilayerMask resource has no valid filename."
        )

    output_root = os.path.dirname(os.path.abspath(filepath)) or os.curdir
    mask_folder_name = f"{mask_stem}_layers"
    mask_output_dir = os.path.join(output_root, mask_folder_name)
    # Created only once the user has confirmed where the export goes.
    os.makedirs(mask_output_dir, exist_ok=True)

    staged_paths = {}
    mask_list = []
    try:
        for layer_index in range(1, layer_count):
            layer_number = layer_index + 1
            layer = linked_layers.get(layer_index)
            if layer is None:
                raise ValueError(
                    f"Layer {layer_number} is disconnected; mask-set layer ordering must be contiguous"
                )
            image = _mask_image(layer)
            if image is None:
                raise ValueError(
                    f"Layer {layer_number} Mask must be connected directly to an Image Texture (reroutes are supported)"
                )

            mask_index = layer_index
            filename = f"{mask_stem}_{mask_index}.{extension}"
            final_path = os.path.join(mask_output_dir, filename)
            temporary_path = _save_image_staged(
                image,
                mask_output_dir,
                final_path,
                export_format,
                extension,
            )
            staged_paths[final_path] = temporary_path
            mask_list.append(f"{mask_folder_name}/{filename}")

        descriptor, masklist_temporary = tempfile.mkstemp(
            prefix=f".{os.path.basename(filepath)}.",
            suffix=".tmp",
            dir=output_root,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            for item in mask_list:
                stream.write(item + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        staged_paths[filepath] = masklist_temporary
        atomic_replace_staged(staged_paths)
        staged_paths.clear()
    except ValueError as error:
        # A layer the mask set cannot describe; write failures propagate with their traceback.
        return OperationResult.cancelled(f"MLMask export failed: {error}", error=error)
    finally:
        for temporary_path in staged_paths.values():
            try:
                if os.path.exists(temporary_path):
                    os.unlink(temporary_path)
            except OSError as error:
                _LOG.debug(
                    "Staged mask file %s was not removed: %s", temporary_path, error
                )

    _LOG.info(
        "Masklist file saved to %s with %d ordered layer mask(s)",
        filepath,
        len(mask_list),
    )
    message = f"Exported MLMASK from {active_material.name} on {active_object.name} ({len(mask_list)} masks)"
    relative = source_raw_relative(filepath)
    if not relative:
        return OperationResult.finished(
            message + ".",
            warnings=(
                "The file is outside a WolvenKit project's source/raw folder; the material's MultilayerMask "
                "path was not updated.",
            ),
        )
    active_material["MultilayerMask"] = replace_depot_suffix(
        relative, ".masklist", ".mlmask"
    )
    return OperationResult.finished(
        f"{message}. The material's MultilayerMask now points to {active_material['MultilayerMask']}."
    )
