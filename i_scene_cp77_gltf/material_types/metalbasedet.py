import bpy
import os
from ..main.common import *

class MetalBaseDet:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format
    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes[loc('Principled BSDF')]
        sockets=bsdf_socket_names()

        # TEXTURES
        if "BaseColor" in Data:
            bcolImg=imageFromRelPath(Data["BaseColor"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            bColNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-900,100), label="BaseColor", image=bcolImg)

        if "DetailColor" in Data:
            dColImg=imageFromRelPath(Data["DetailColor"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            dColNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-900,0), label="DetailColor", image=dColImg) 

        if "Metalness" in Data:
            mImg=imageFromRelPath(Data["Metalness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            metNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-900,-100), label="Metalness", image=mImg)

        if "Roughness" in Data:
            rImg=imageFromRelPath(Data["Roughness"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            rNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-900,-250), label="Roughness", image=rImg)

        if "Normal" in Data:
            nImg = imageFromPath(self.BasePath + Data["Normal"],self.image_format, True)
            nNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-900,-400), label="Normal", image=nImg)            

        if "DetailNormal" in Data:
            dNImg = imageFromPath(self.BasePath + Data["DetailNormal"],self.image_format, True)
            dNNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-900,-500), label="DetailNormal", image=dNImg)
        
        if "Emissive" in Data:
            EmcolImg=imageFromRelPath(Data["BaseColor"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            EmColNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-900,200), label="Emmisive", image=EmcolImg)



        # PARAMETERS

        if "BaseColorScale" in Data:
            bColScale = CreateShaderNodeRGB(CurMat, Data["BaseColorScale"],-900,50,'BaseColorScale',True)

        if "DetailU" in Data:
            dU = CreateShaderNodeValue(CurMat,Data["DetailU"],-1000, 350,"DetailU")

        if "DetailV" in Data:
            dV = CreateShaderNodeValue(CurMat,Data["DetailV"],-1000, 300,"DetailV")

        if 'RoughnessScale' in Data:
            rScale = CreateShaderNodeValue(CurMat,Data["RoughnessScale"],-900, -300,"RoughnessScale")

        if 'RoughnessBias' in Data:
            rBias = CreateShaderNodeValue(CurMat,Data["RoughnessBias"],-900, -350,"RoughnessBias")

        if 'MetalnessScale' in Data:
            mScale = CreateShaderNodeValue(CurMat,Data["MetalnessScale"],-900, -150,"MetalnessScale")

        if 'MetalnessBias' in Data:
            mBias = CreateShaderNodeValue(CurMat,Data["MetalnessBias"],-900, -200,"MetalnessBias")
        
        if "AlphaThreshold" in Data:
            aThreshold = CreateShaderNodeValue(CurMat,Data["AlphaThreshold"],-900, -550,"AlphaThreshold")

        # multiply BaseColor texture and BaseColorScale
        sBaseCol = create_node(CurMat.nodes,"ShaderNodeMixRGB", (-550,100) , blend_type = 'MULTIPLY')
        sBaseCol.inputs[0].default_value = 1
        CurMat.links.new(bColNode.outputs[0],sBaseCol.inputs[1])
        CurMat.links.new(bColScale.outputs[0],sBaseCol.inputs[2])

        # multiply Metalness and MetalnessScale then add MetalnessBias
        if "Metalness" in Data:
            mMulNode = create_node(CurMat.nodes,"ShaderNodeMath", (-550,-100) , operation = 'MULTIPLY')
            CurMat.links.new(metNode.outputs[0],mMulNode.inputs[0])
            CurMat.links.new(mScale.outputs[0],mMulNode.inputs[1])
            mAddNode = create_node(CurMat.nodes,"ShaderNodeMath", (-350,-100) , operation = 'ADD')
            CurMat.links.new(mMulNode.outputs[0],mAddNode.inputs[0])
            CurMat.links.new(mBias.outputs[0],mAddNode.inputs[1])

        # multiply Roughness and RoughnessScale then add RoughnessBias
        if "Roughness" in Data:
            rMulNode = create_node(CurMat.nodes,"ShaderNodeMath", (-550,-150) , operation = 'MULTIPLY')
            CurMat.links.new(rNode.outputs[0],rMulNode.inputs[0])
            CurMat.links.new(rScale.outputs[0],rMulNode.inputs[1])
            rAddNode = create_node(CurMat.nodes,"ShaderNodeMath", (-350,-150) , operation = 'ADD')
            CurMat.links.new(rMulNode.outputs[0],rAddNode.inputs[0])
            CurMat.links.new(rBias.outputs[0],rAddNode.inputs[1])        


        if "DetailU" in Data:
            # multiply detail texture UV and detailUV
            UVNode = create_node(CurMat.nodes,"ShaderNodeTexCoord",(-800,300))
            dUVCombine = create_node(CurMat.nodes, "ShaderNodeCombineXYZ",(-700,200))
            sDetUV = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-600,300), operation="MULTIPLY")
            CurMat.links.new(dU.outputs[0],dUVCombine.inputs[0])
            CurMat.links.new(dV.outputs[0],dUVCombine.inputs[1])
            CurMat.links.new(UVNode.outputs[2],sDetUV.inputs[0])
            CurMat.links.new(dUVCombine.outputs[0],sDetUV.inputs[1])
            CurMat.links.new(sDetUV.outputs[0],dColNode.inputs[0])

        if "DetailColor" in Data:
            # multiply DetailColor and BaseColorScale
            dColmul = create_node(CurMat.nodes,"ShaderNodeMixRGB", (-550,0), blend_type = 'MULTIPLY')
            dColmul.inputs[0].default_value = 1
            CurMat.links.new(dColNode.outputs[0],dColmul.inputs[1])
            CurMat.links.new(bColScale.outputs[0],dColmul.inputs[2])

        if "DetailNormal" in Data:
            # connect multiplied UV to DetailNormal
            CurMat.links.new(sDetUV.outputs[0],dNNode.inputs[0])

        if "DetailColor" in Data:
            # multiply BaseColor and DetailColor
            finalColor = create_node(CurMat.nodes,"ShaderNodeMixRGB", (-350,50), blend_type = 'MULTIPLY')
            finalColor.inputs[0].default_value = 1
            CurMat.links.new(sBaseCol.outputs[0],finalColor.inputs[1])
            CurMat.links.new(dColmul.outputs[0],finalColor.inputs[2])

        if "DetailNormal" in Data:
            # combine normal textures
            nSepNode = create_node(CurMat.nodes,"ShaderNodeSeparateRGB", (-550,-300)) 
            nDetSepNode = create_node(CurMat.nodes,"ShaderNodeSeparateRGB", (-550,-400)) 
            redAddNode = create_node(CurMat.nodes,"ShaderNodeMath", (-350,-300), operation = "ADD") 
            greenAddNode = create_node(CurMat.nodes,"ShaderNodeMath", (-350,-350), operation = "ADD") 
            blueMulNode = create_node(CurMat.nodes,"ShaderNodeMath", (-350,-400), operation = "MULTIPLY") 
            nCombNode = create_node(CurMat.nodes,"ShaderNodeCombineRGB", (-150,-350)) 
            CurMat.links.new(nNode.outputs[0],nSepNode.inputs[0])
            CurMat.links.new(dNNode.outputs[0],nDetSepNode.inputs[0])
            CurMat.links.new(nSepNode.outputs[0],redAddNode.inputs[0])      
            CurMat.links.new(nSepNode.outputs[1],greenAddNode.inputs[0])
            CurMat.links.new(nSepNode.outputs[2],blueMulNode.inputs[0])
            CurMat.links.new(nDetSepNode.outputs[0],redAddNode.inputs[1])
            CurMat.links.new(nDetSepNode.outputs[1],greenAddNode.inputs[1])
            CurMat.links.new(nDetSepNode.outputs[2],blueMulNode.inputs[1])
            CurMat.links.new(redAddNode.outputs[0],nCombNode.inputs[0])
            CurMat.links.new(greenAddNode.outputs[0],nCombNode.inputs[1])
            CurMat.links.new(blueMulNode.outputs[0],nCombNode.inputs[2])
            nMap = create_node(CurMat.nodes,"ShaderNodeNormalMap",  (-200,-250))   
            NRG = CreateRebildNormalGroup(CurMat, -350, -250, "DetailNormal Rebuilt")
            CurMat.links.new(nCombNode.outputs[0],NRG.inputs[0])
            CurMat.links.new(NRG.outputs[0],nMap.inputs[1])
        

        # alpha
        # aMulNode = create_node(CurMat.nodes,"ShaderNodeMath", (-600,-550), operation = "MULTIPLY") 
        # aMulNode2 = create_node(CurMat.nodes,"ShaderNodeMath", (-500,-600), operation = "MULTIPLY") 
        # CurMat.links.new(bColNode.outputs[0],aMulNode.inputs[0])
        # CurMat.links.new(dColNode.outputs[0],aMulNode.inputs[1])
        # CurMat.links.new(aMulNode.outputs[0],aMulNode2.inputs[0])
        # CurMat.links.new(bColScaleW.outputs[0],aMulNode2.inputs[1])
        # aSubNode = create_node(CurMat.nodes,"ShaderNodeMath", (-400,-650), operation = "SUBTRACT") 
        # CurMat.links.new(aMulNode2.outputs[0],aSubNode.inputs[0])
        # CurMat.links.new(aThreshold.outputs[0],aSubNode.inputs[1])
        
        # final links
        if "DetailColor" in Data:
            CurMat.links.new(finalColor.outputs[0],pBSDF.inputs['Base Color'])
            CurMat.links.new(dColNode.outputs[1],pBSDF.inputs['Alpha'])
        else:
            CurMat.links.new(sBaseCol.outputs[0],pBSDF.inputs['Base Color'])

        if "Roughness" in Data:
            CurMat.links.new(rAddNode.outputs[0],pBSDF.inputs['Roughness'])
        if "Metalness" in Data:
            CurMat.links.new(mAddNode.outputs[0],pBSDF.inputs['Metallic'])
        if "Emissive" in Data:
            CurMat.links.new(EmColNode.outputs[0],pBSDF.inputs[sockets['Emission']])
            pBSDF.inputs["Emission Strength"].default_value = 1.0 # was the default in 3.6 seems to be 0 now
        if "DetailNormal" in Data:
            CurMat.links.new(nMap.outputs[0],pBSDF.inputs['Normal'])
        else:
            CurMat.links.new(nNode.outputs[0],pBSDF.inputs['Normal'])
        
