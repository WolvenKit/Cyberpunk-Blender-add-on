from ..materials.blender.images import imageFromRelPath
from ..materials.blender.nodes import CreateShaderNodeRGB, bsdf_socket_names, create_node, loc


from .mat_common import MaterialTypeBase

class EyeShadow(MaterialTypeBase):
    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets = bsdf_socket_names()
        pBSDF.inputs['Roughness'].default_value = 0.01
        pBSDF.inputs['IOR'].default_value = 1.2
        pBSDF.inputs[sockets['Transmission']].default_value = 1

        # JATO: setting for blender eevee that improves transmission/refraction look
        Mat.use_raytrace_refraction = True

        # MASK+SHADOW COLOR/ms
        if "Mask" in Data:
            mImg = imageFromRelPath(
                    Data["Mask"], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True
                    )
            mImgNode = create_node(CurMat.nodes, "ShaderNodeTexImage", (-1000, 250), label="Mask", image=mImg)

            separateColor = CurMat.nodes.new("ShaderNodeSeparateColor")
            separateColor.location = (-600, -100)

            CurMat.links.new(mImgNode.outputs[0], separateColor.inputs[0])
            CurMat.links.new(mImgNode.outputs[1], pBSDF.inputs['Coat Weight'])
            CurMat.links.new(separateColor.outputs[0], pBSDF.inputs['Alpha'])

        if "ShadowColor" in Data:
            msColorNode = CreateShaderNodeRGB(CurMat, Data["ShadowColor"], -600, 300, 'ShadowColor')
            CurMat.links.new(msColorNode.outputs[0], pBSDF.inputs['Base Color'])
