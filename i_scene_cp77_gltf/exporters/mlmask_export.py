import bpy
import os

def cp77_mlmask_export(self,context, filepath, export_format):
    active_object = bpy.context.active_object
    active_material = active_object.active_material
    nodes = active_material.node_tree.nodes
    # print("Exporting Mask Images from " + active_material.name + " on " + active_object.name)

    projpath = str(active_material["ProjPath"])
    mlmaskpath = str(active_material["MultilayerMask"])
    mlmask_file_name = (mlmaskpath.split("\\")[-1])
    masklist_folder_name = (mlmask_file_name.split(".")[0]) + "_layers/"
    masklist_folder_path = (mlmaskpath.split(".")[0]) + "_layers"
    mask_outpath = projpath + masklist_folder_path

    mask_list = []

    mlBSDFGroup = nodes.get("Multilayered 1.8.0")
    if not mlBSDFGroup:
        self.report({'ERROR'}, 'Multilayered shader node not found within selected material.')
        return # TODO throw error in OP

    mask_output_dir = bpy.path.abspath(mask_outpath)
    if not os.path.exists(mask_output_dir):
        os.makedirs(mask_output_dir)
    ext_map = {'PNG': 'png', 'JPEG': 'jpg', 'TARGA': 'tga', 'TIFF': 'tif'}
    selected_ext = ext_map.get(export_format, 'png')

    numLayers = 20
    layerBSDF = 1
    while layerBSDF<=numLayers:
        socket_name = ("Layer "+str(layerBSDF))
        socket = mlBSDFGroup.inputs.get(socket_name)
        # JATO: if there's no connected node group skip to next layer. TODO warn user this breaks mlmask/mlsetup relationship? or maybe write dummy mask?
        if not socket.is_linked:
            layerBSDF += 1
            continue

        layerGroupLink = socket.links[0]
        linkedLayerGroupName = layerGroupLink.from_node.name
        LayerGroup= nodes[linkedLayerGroupName]

        MaskNode = None
        socket_name = "Mask"
        socket = LayerGroup.inputs.get(socket_name)
        # JATO: if there's no connected mask node skip to next layer. TODO warn user this breaks mlmask/mlsetup relationship? or maybe write dummy mask?
        if not socket.is_linked:
            layerBSDF += 1
            continue
        maskNodeLink = socket.links[0]
        linkedMaskNodeName = maskNodeLink.from_node.name
        MaskNode=nodes[linkedMaskNodeName]

        if MaskNode and MaskNode.type == 'TEX_IMAGE' and MaskNode.image:
            img = MaskNode.image
            # JATO: LLM thinks this is a good idea... who am i to judge?
            safe_name = "".join([c for c in img.name if c.isalnum() or c in (' ', '.', '_')]).strip()
            img_outpath = os.path.join(mask_output_dir, f"{safe_name}.{selected_ext}")

            mask_list.append(f"{masklist_folder_name}{safe_name}.{selected_ext}")

            try:
                original_format = img.file_format
                img.file_format = export_format
                img.save_render(img_outpath)
                img.file_format = original_format

                img.filepath = bpy.path.abspath(img_outpath)
                img.source = 'FILE'
                img.reload()
            except Exception as e:
                self.report({'ERROR'}, f"Failed {img.name}: {str(e)}")

        layerBSDF += 1

    with open(filepath, 'w') as f:
        f.writelines(f"{item}\n" for item in mask_list)
    print(f"Masklist file saved to: {filepath}")

    success_message = "Exported MLMASK from " + active_material.name + " on " + active_object.name
    self.report({'INFO'}, success_message)