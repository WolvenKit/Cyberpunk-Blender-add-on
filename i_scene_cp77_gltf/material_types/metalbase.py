import bpy
import os
from ..main.common import *

class MetalBase:
    def __init__(self, BasePath,image_format, ProjPath, enableMask):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.enableMask = enableMask
        self.image_format = image_format

    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets=bsdf_socket_names()
        isDetailNormal=None

        mixRGB = create_node(CurMat.nodes,"ShaderNodeMixRGB", (-800,500) , blend_type = 'MULTIPLY')
        mixRGB.inputs[0].default_value = 1
        CurMat.links.new(mixRGB.outputs[0],pBSDF.inputs['Base Color'])

        if "BaseColor" in Data:
            bcolImg=imageFromRelPath(Data["BaseColor"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            bColNode = create_node(CurMat.nodes,"ShaderNodeTexImage", (-1400,650), label="BaseColor", image=bcolImg)
            CurMat.links.new(bColNode.outputs[0],mixRGB.inputs[1])

        if "DetailColor" in Data:
            dColImg=imageFromRelPath(Data["DetailColor"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            dColNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-1400,950), label="DetailColor", image=dColImg) 

        if "Metalness" in Data:
            mImg=imageFromRelPath(Data["Metalness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            metNode = create_node(CurMat.nodes,"ShaderNodeTexImage", (-1400,250), label="Metalness", image=mImg)

            mMulAddNode = create_node(CurMat.nodes,"ShaderNodeMath", (-1050,250) , operation = 'MULTIPLY_ADD')
            mMulAddNode.inputs[1].default_value = 1
            mMulAddNode.inputs[2].default_value = 0

            CurMat.links.new(metNode.outputs[0],mMulAddNode.inputs[0])
            CurMat.links.new(mMulAddNode.outputs[0],pBSDF.inputs['Metallic'])

        if "Roughness" in Data:
            rImg=imageFromRelPath(Data["Roughness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath, isNormal=True)
            rNode = create_node(CurMat.nodes,"ShaderNodeTexImage", (-1400,50), label="Roughness", image=rImg)

            rMulAddNode = create_node(CurMat.nodes,"ShaderNodeMath", (-1050,50) , operation = 'MULTIPLY_ADD')
            rMulAddNode.inputs[1].default_value = 1
            rMulAddNode.inputs[2].default_value = 0

            CurMat.links.new(rNode.outputs[0],rMulAddNode.inputs[0])
            CurMat.links.new(rMulAddNode.outputs[0],pBSDF.inputs['Roughness'])

        if "Normal" in Data:
            nMap = CreateShaderNodeGlobalNormalMap(CurMat,self.BasePath + Data["Normal"],-1000,-200,'Normal',self.image_format)
            normalVectorize = CurMat.nodes.new("ShaderNodeVectorMath")
            normalVectorize.operation='MULTIPLY_ADD'
            normalVectorize.location = (-1050,-200)
            normalVectorize.hide = True
            normalVectorize.inputs[1].default_value = 2, 2, 0
            normalVectorize.inputs[2].default_value = -1, -1, 0

            normalCreateVecZGroup = CreateCalculateVecNormalZ(CurMat,-800,-350)
            normalMap = create_node(CurMat.nodes, "ShaderNodeNormalMap",(-500,-350))

            CurMat.links.new(nMap.outputs[0],normalVectorize.inputs[0])
            CurMat.links.new(normalVectorize.outputs[0],normalCreateVecZGroup.inputs[0])
            CurMat.links.new(normalCreateVecZGroup.outputs[0],normalMap.inputs[1])
            CurMat.links.new(normalMap.outputs[0],pBSDF.inputs['Normal'])

        if "DetailNormal" in Data:
            dNNode = CreateShaderNodeGlobalNormalMap(CurMat,self.BasePath + Data["DetailNormal"],-1000,-500,'Normal',self.image_format)

            normalDetVectorize = CurMat.nodes.new("ShaderNodeVectorMath")
            normalDetVectorize.operation='MULTIPLY_ADD'
            normalDetVectorize.location = (-1050,-500)
            normalDetVectorize.hide = True
            normalDetVectorize.inputs[1].default_value = 2, 2, 0
            normalDetVectorize.inputs[2].default_value = -1, -1, 0

            normalAdd = create_node(CurMat.nodes, "ShaderNodeVectorMath",(-1050,-350),operation='ADD')

            CurMat.links.new(dNNode.outputs[0],normalDetVectorize.inputs[0])
            CurMat.links.new(normalVectorize.outputs[0],normalAdd.inputs[0])
            CurMat.links.new(normalDetVectorize.outputs[0],normalAdd.inputs[1])

            CurMat.links.new(normalAdd.outputs[0],normalCreateVecZGroup.inputs[0])

            isDetailNormal = True

        if "BaseColorScale" in Data:
            dColScale = CreateShaderNodeRGB(CurMat, Data["BaseColorScale"],-1400,500,'BaseColorScale',True)
            baseColorGamma = CurMat.nodes.new("ShaderNodeGamma")
            baseColorGamma.location = (-1050,500)
            baseColorGamma.inputs[1].default_value = 2.2
            baseColorGamma.hide = True
            CurMat.links.new(dColScale.outputs[0],baseColorGamma.inputs[0]) 
            CurMat.links.new(baseColorGamma.outputs[0],mixRGB.inputs[2]) 

        if 'GradientMap' in Data:
            gradmap = Data["GradientMap"]
            gradImg = imageFromRelPath(gradmap,self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
            grad_image_node = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-800,0), label="GradientMap", image=gradImg)
            color_ramp_node=CreateGradMapRamp(CurMat, grad_image_node)
            CurMat.links.new(mixRGB.outputs[0], color_ramp_node.inputs[0])
            CurMat.links.new(color_ramp_node.outputs[0], pBSDF.inputs['Base Color'])

        if 'MetalnessScale' in Data:
            mScale = CreateShaderNodeValue(CurMat,Data["MetalnessScale"],-1400, 200,"MetalnessScale")
            CurMat.links.new(mScale.outputs[0],mMulAddNode.inputs[1]) 

        if 'MetalnessBias' in Data:
            mBias = CreateShaderNodeValue(CurMat,Data["MetalnessBias"],-1400, 150,"MetalnessBias")
            CurMat.links.new(mBias.outputs[0],mMulAddNode.inputs[2])

        if 'RoughnessScale' in Data:
            rScale = CreateShaderNodeValue(CurMat,Data["RoughnessScale"],-1400, 0,"RoughnessScale")
            CurMat.links.new(rScale.outputs[0],rMulAddNode.inputs[1]) 

        if 'RoughnessBias' in Data:
            rBias = CreateShaderNodeValue(CurMat,Data["RoughnessBias"],-1400, -50,"RoughnessBias")
            CurMat.links.new(rBias.outputs[0],rMulAddNode.inputs[2])

        if "AlphaThreshold" in Data:
            aThreshold = CreateShaderNodeValue(CurMat,Data["AlphaThreshold"],-1400, 400,"AlphaThreshold")
        else:
            aThreshold = CreateShaderNodeValue(CurMat,1.0,-1400, 400,"AlphaThreshold")

        maskThreshold = create_node(CurMat.nodes,"ShaderNodeMath",(-1050,400),operation='GREATER_THAN')
        CurMat.links.new(bColNode.outputs[1],maskThreshold.inputs[0])
        CurMat.links.new(aThreshold.outputs[0],maskThreshold.inputs[1])
        # JATO: what is the purpose of this if/else?
        # if self.enableMask:
        #     CurMat.links.new(bColNode.outputs[1],alphaClamp.inputs['Value'])
        # else:
        #     CurMat.links.new(bColNode.outputs[0],alphaClamp.inputs['Value'])

        mulNode = CurMat.nodes.new("ShaderNodeMixRGB")
        mulNode.inputs[0].default_value = 1
        mulNode.blend_type = 'MULTIPLY'
        mulNode.location = (-450,-450)
        mulNode.hide = True

        if "Emissive" in Data:
            EmImg=imageFromRelPath(Data["Emissive"],self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
            emTexNode =create_node(CurMat.nodes,"ShaderNodeTexImage", (-800,-500), label="Emissive", image=EmImg)
            CurMat.links.new(emTexNode.outputs[0],mulNode.inputs[2])

        if "EmissiveColor" in Data:
            emColor = CreateShaderNodeRGB(CurMat, Data["EmissiveColor"],-700,-450,"EmissiveColor")
            CurMat.links.new(emColor.outputs[0],mulNode.inputs[1])

        CurMat.links.new(mulNode.outputs[0],pBSDF.inputs[sockets['Emission']])

        if "EmissiveEV" in Data:
            pBSDF.inputs['Emission Strength'].default_value =  Data["EmissiveEV"]

        #Setup a value node for the enableMask flag that turns off the alpha when 0 (false) and on when 1
        EnableMask = create_node(CurMat.nodes,"ShaderNodeValue",(-800, -150), label="EnableMask")
        EnableMask.outputs[0].default_value=int(self.enableMask)

        mathSubtract = create_node(CurMat.nodes,"ShaderNodeMath",(-800, -100), operation='SUBTRACT', label="Math")
        mathSubtract.inputs[0].default_value=1

        enableMaskClamp = create_node(CurMat.nodes,"ShaderNodeClamp",(-800, -50))

        backfaceGroup = CreateCullBackfaceGroup(CurMat, x = -500, y = -50,name = 'Cull Backface')

        # Case for when material is metalbasedet.mt
        # It's critical we create these links last so the metalbasedet links overwrite metalbase links
        if isDetailNormal:
            texCoord = CurMat.nodes.new("ShaderNodeTexCoord")
            texCoord.location = (-2300,0)
            mappingNode = CurMat.nodes.new("ShaderNodeMapping")
            mappingNode.location = (-2100,0)
            if "DetailU" in Data:
                if "DetailV" in Data:
                    mappingNode.inputs[3].default_value = (Data["DetailU"],Data["DetailV"],0)
            CurMat.links.new(texCoord.outputs[2],mappingNode.inputs[0])
            CurMat.links.new(mappingNode.outputs[0],dColNode.inputs[0])
            CurMat.links.new(mappingNode.outputs[0],dNNode.inputs[0])

            alphaMultiply = create_node(CurMat.nodes,"ShaderNodeMath", (-1050,800) , operation = 'MULTIPLY')
            CurMat.links.new(dColNode.outputs[1],alphaMultiply.inputs[0])
            CurMat.links.new(bColNode.outputs[1],alphaMultiply.inputs[1])
            CurMat.links.new(alphaMultiply.outputs[0],maskThreshold.inputs[0])

            dColmul = create_node(CurMat.nodes,"ShaderNodeMixRGB", (-800,650), blend_type = 'MULTIPLY')
            dColmul.inputs[0].default_value = 1
            CurMat.links.new(dColNode.outputs[0],dColmul.inputs[1])
            CurMat.links.new(bColNode.outputs[0],dColmul.inputs[2])
            CurMat.links.new(dColmul.outputs[0],mixRGB.inputs[1])

        CurMat.links.new(EnableMask.outputs['Value'], mathSubtract.inputs[1]) # Enablemask value into math which inverts it
        CurMat.links.new(mathSubtract.outputs['Value'], enableMaskClamp.inputs[1]) # Inverted value into clamp min, so if 1 its always solic, if 0 will use BaseColor alpha
        CurMat.links.new(maskThreshold.outputs[0], enableMaskClamp.inputs[0])
        CurMat.links.new(enableMaskClamp.outputs[0], backfaceGroup.inputs[0])
        CurMat.links.new(backfaceGroup.outputs[0], pBSDF.inputs['Alpha'])
        if not image_has_alpha(bcolImg): # if the image doesnt have alpha stick the color in instead
            CurMat.links.new(bColNode.outputs['Color'],enableMaskClamp.inputs['Value'])


used_params=['BaseColor',
 'BaseColorScale',
 'Metalness',
 'Roughness',
 'Normal',
 'AlphaThreshold',
 'MetalnessScale',
 'MetalnessBias',
 'RoughnessScale',
 'RoughnessBias',
 'NormalStrength',
 'Emissive',
 'EmissiveLift',
 'EmissiveEV',
 'EmissiveEVRaytracingBias',
 'EmissiveDirectionality',
 'EnableRaytracedEmissive',
 'EmissiveColor',
 'LayerTile',
 'VehicleDamageInfluence']