<<<<<<< Updated upstream
import os
import tempfile

import bpy

from ..common.atomic import atomic_replace_staged


def cp77_mlmask_export(self, context, filepath, export_format):
    active_object = bpy.context.active_object
    if active_object is None or active_object.active_material is None:
        self.report({'ERROR'}, "No active object with a material.")
        return {'CANCELLED'}
    active_material = active_object.active_material
    nodes = active_material.node_tree.nodes
    # print("Exporting Mask Images from " + active_material.name + " on " + active_object.name)

    mlmaskpath = str(active_material["MultilayerMask"])
    mlmask_file_name = (mlmaskpath.split("\\")[-1])
    masklist_folder_name = (mlmask_file_name.split(".")[0]) + "_layers/"
    masklist_folder_path = os.path.dirname(os.path.abspath(filepath))
    mask_outpath = os.path.join(
        masklist_folder_path,
        masklist_folder_name.rstrip("/"),
    )

    mask_list = []

    mlBSDFGroup = nodes.get("Multilayered 1.8.0")
    if not mlBSDFGroup:
        self.report({'ERROR'}, 'Multilayered shader node not found within selected material.')
        return {'CANCELLED'}

    mask_output_dir = bpy.path.abspath(mask_outpath)
    if not os.path.exists(mask_output_dir):
        os.makedirs(mask_output_dir)
    ext_map = {'PNG': 'png', 'JPEG': 'jpg', 'TARGA': 'tga', 'TIFF': 'tif'}
    selected_ext = ext_map.get(export_format, 'png')
    staged_paths = {}
    exported_images = []

    try:
        numLayers = 20
        layerBSDF = 1
        while layerBSDF <= numLayers:
            socket_name = ("Layer " + str(layerBSDF))
            socket = mlBSDFGroup.inputs.get(socket_name)
            if socket is None or not socket.is_linked:
                layerBSDF += 1
                continue

            layerGroupLink = socket.links[0]
            linkedLayerGroupName = layerGroupLink.from_node.name
            LayerGroup = nodes[linkedLayerGroupName]

            socket = LayerGroup.inputs.get("Mask")
            if socket is None or not socket.is_linked:
                layerBSDF += 1
                continue
            maskNodeLink = socket.links[0]
            MaskNode = nodes[maskNodeLink.from_node.name]

            if MaskNode and MaskNode.type == 'TEX_IMAGE' and MaskNode.image:
                img = MaskNode.image
                safe_name = "".join(
                    c for c in img.name
                    if c.isalnum() or c in (' ', '.', '_')
                ).strip()
                img_outpath = os.path.join(
                    mask_output_dir,
                    f"{safe_name}.{selected_ext}",
                )

                mask_list.append(
                    f"{masklist_folder_name}{safe_name}.{selected_ext}"
                )

                original_format = img.file_format
                img.file_format = export_format
                try:
                    handle, temporary_path = tempfile.mkstemp(
                        prefix=f".{safe_name}.",
                        suffix=f".{selected_ext}",
                        dir=mask_output_dir,
                    )
                    os.close(handle)
                    img.save_render(temporary_path)
                    staged_paths[img_outpath] = temporary_path
                    exported_images.append((img, img_outpath))
                finally:
                    img.file_format = original_format
            layerBSDF += 1

        if not mask_list:
            raise ValueError("No connected mask images were found")

        masklist_dir = os.path.dirname(os.path.abspath(filepath)) or os.curdir
        os.makedirs(masklist_dir, exist_ok=True)
        descriptor, masklist_temporary = tempfile.mkstemp(
            prefix=f".{os.path.basename(filepath)}.",
            suffix=".tmp",
            dir=masklist_dir,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("".join(f"{item}\n" for item in mask_list))
=======
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
>>>>>>> Stashed changes
            stream.flush()
            os.fsync(stream.fileno())
        staged_paths[filepath] = masklist_temporary
        atomic_replace_staged(staged_paths)
        staged_paths.clear()
<<<<<<< Updated upstream
    except Exception as error:
        self.report({'ERROR'}, f"MLMask export failed: {error}")
        return {'CANCELLED'}
    finally:
        for temporary_path in staged_paths.values():
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

    for img, img_outpath in exported_images:
        try:
            img.filepath = bpy.path.abspath(img_outpath)
            img.source = 'FILE'
            img.reload()
        except Exception as error:
            self.report(
                {'WARNING'},
                f"Exported {img.name}, but Blender could not reload it: {error}",
            )
    print(f"Masklist file saved to: {filepath}")

    success_message = "Exported MLMASK from " + active_material.name + " on " + active_object.name
    self.report({'INFO'}, success_message)
    return {'FINISHED'}
=======
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
>>>>>>> Stashed changes
