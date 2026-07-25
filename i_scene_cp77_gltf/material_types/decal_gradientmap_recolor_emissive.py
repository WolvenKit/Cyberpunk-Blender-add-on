if __name__ != "__main__":
    from ..main.common import *
    from .mat_common import decal_values, depot_texture_exists
else:
    from mat_common import decal_values, depot_texture_exists


class DecalGradientmapRecolorEmissive:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def found(self, tex):
        result = depot_texture_exists(
            tex,
            self.image_format,
            self.BasePath,
            self.ProjPath,
        )
        if not result:
            print(f"Texture not found: {tex}")
        return result

    def create(self, Data, Mat):
        masktex = ""
        difftex = ""
        gradmap = ""
        emissive_gradmap = ""
        emissiveEV = 0
        diffAsMask = 1
        if "enableMask" in Data.keys():
            if Data["enableMask"] == True:
                diffAsMask = 0
        values = decal_values(Data)
        diffuse = values.get("DiffuseTexture", {})
        gradient = values.get("GradientMap", {})
        emissive_gradient = values.get("EmissiveGradientMap", {})
        mask = values.get("MaskTexture", {})
        difftex = diffuse.get("DepotPath", {}).get("$value", "")
        gradmap = gradient.get("DepotPath", {}).get("$value", "")
        emissive_gradmap = emissive_gradient.get("DepotPath", {}).get("$value", "")
        masktex = mask.get("DepotPath", {}).get("$value", "")
        emissiveEV = values.get("EmissiveEV", 0)
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc("Principled BSDF")]
        sockets = bsdf_socket_names()

        if self.found(difftex) and self.found(gradmap):
            diffImg = imageFromRelPath(
                    difftex,
                    self.image_format,
                    DepotPath=self.BasePath,
                    ProjPath=self.ProjPath,
                    isNormal=True,
                    )
            diff_image_node = create_node(
                    CurMat.nodes,
                    "ShaderNodeTexImage",
                    (-800, -300),
                    label="DiffuseTexture",
                    image=diffImg,
                    )

            gradImg = imageFromRelPath(
                    gradmap,
                    self.image_format,
                    DepotPath=self.BasePath,
                    ProjPath=self.ProjPath,
                    )
            grad_image_node = create_node(
                    CurMat.nodes,
                    "ShaderNodeTexImage",
                    (-500, -200),
                    label="GradientMap",
                    image=gradImg,
                    )
            CurMat.links.new(diff_image_node.outputs[0], grad_image_node.inputs[0])
            CurMat.links.new(grad_image_node.outputs[0], pBSDF.inputs["Base Color"])
            CurMat.links.new(grad_image_node.outputs[0], pBSDF.inputs[sockets["Emission"]])

            if emissive_gradmap and self.found(emissive_gradmap):
                emissiveGradImg = imageFromRelPath(
                        emissive_gradmap,
                        self.image_format,
                        DepotPath=self.BasePath,
                        ProjPath=self.ProjPath,
                        isNormal=True,
                        )
                emissive_grad_node = create_node(
                        CurMat.nodes,
                        "ShaderNodeTexImage",
                        (-500, -500),
                        label="EmissiveGradientMap",
                        image=emissiveGradImg,
                        )
                CurMat.links.new(diff_image_node.outputs[0], emissive_grad_node.inputs[0])
                emissive_mult = create_node(
                        CurMat.nodes, "ShaderNodeMath", (-300, -500), operation="MULTIPLY"
                        )
                emissive_mult.inputs[1].default_value = emissiveEV
                CurMat.links.new(emissive_grad_node.outputs[0], emissive_mult.inputs[0])
                CurMat.links.new(emissive_mult.outputs[0], pBSDF.inputs["Emission Strength"])

            if masktex and self.found(masktex):
                maskImg = imageFromRelPath(
                        masktex,
                        self.image_format,
                        DepotPath=self.BasePath,
                        ProjPath=self.ProjPath,
                        isNormal=True,
                        )
                mask_image_node = create_node(
                        CurMat.nodes,
                        "ShaderNodeTexImage",
                        (-800, -600),
                        label="MaskTexture",
                        image=maskImg,
                        )
                alpha_mult = create_node(
                        CurMat.nodes, "ShaderNodeMath", (-300, -350), operation="MULTIPLY"
                        )
                CurMat.links.new(grad_image_node.outputs[1], alpha_mult.inputs[0])
                CurMat.links.new(mask_image_node.outputs[0], alpha_mult.inputs[1])
                CurMat.links.new(alpha_mult.outputs[0], pBSDF.inputs["Alpha"])
            else:
                CurMat.links.new(grad_image_node.outputs[1], pBSDF.inputs["Alpha"])
        else:
            pBSDF.inputs["Alpha"].default_value = 0
