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
            stream.flush()
            os.fsync(stream.fileno())
        staged_paths[filepath] = masklist_temporary
        atomic_replace_staged(staged_paths)
        staged_paths.clear()
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
