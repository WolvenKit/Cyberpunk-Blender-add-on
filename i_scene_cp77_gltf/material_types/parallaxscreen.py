import bpy
import os
from ..main.common import *

class ParallaxScreen:
    def __init__(self, BasePath,image_format,ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def createStepGroup(self):
        if 'step' in bpy.data.node_groups.keys():
            stepGroup = bpy.data.node_groups['step']
            return stepGroup
        else:
            stepGroup = bpy.data.node_groups.new("step","ShaderNodeTree")
            stepGroup.inputs.new('NodeSocketFloat','y')
            stepGroup.inputs.new('NodeSocketFloat','x')
            stepGroup.outputs.new('NodeSocketFloat','result')
            stepGroupI = create_node(stepGroup.nodes, "NodeGroupInput",(-1400,0))
            stepGroupO = create_node(stepGroup.nodes, "NodeGroupOutput",(-200,0))
            greaterThan = create_node(stepGroup.nodes,"ShaderNodeMath",(-1200,0), operation= "GREATER_THAN")
            compare = create_node(stepGroup.nodes,"ShaderNodeMath",(-1200,-50), operation= "COMPARE")
            compare.inputs[2].default_value = 0
            add = create_node(stepGroup.nodes,"ShaderNodeMath",(-1050,-25), operation= "ADD")
            compare2 = create_node(stepGroup.nodes,"ShaderNodeMath",(-900,-25), operation= "COMPARE")
            compare2.inputs[1].default_value = 1
            compare2.inputs[2].default_value = 2
            stepGroup.links.new(stepGroupI.outputs[1],greaterThan.inputs[0])
            stepGroup.links.new(stepGroupI.outputs[0],greaterThan.inputs[1])
            stepGroup.links.new(stepGroupI.outputs[1],compare.inputs[0])
            stepGroup.links.new(stepGroupI.outputs[0],compare.inputs[1])
            stepGroup.links.new(greaterThan.outputs[0],add.inputs[0])
            stepGroup.links.new(compare.outputs[0],add.inputs[1])
            stepGroup.links.new(add.outputs[0],compare2.inputs[0])
            stepGroup.links.new(compare2.outputs[0],stepGroupO.inputs[0])

            return stepGroup
        
    def colorlessTexGroup(self):
        if 'colorlessTex' in bpy.data.node_groups.keys():
            colorlessTexGroup = bpy.data.node_groups['colorlessTex']
            return colorlessTexGroup 
        else:   
            colorlessTexGroup = bpy.data.node_groups.new("colorlessTex","ShaderNodeTree")
            colorlessTexGroup.inputs.new('NodeSocketColor', 'Color')
            colorlessTexGroup.outputs.new('NodeSocketColor', 'Color')
            colorlessTexGroupI = create_node(colorlessTexGroup.nodes, "NodeGroupInput",(-1400,0))
            colorlessTexGroupO = create_node(colorlessTexGroup.nodes, "NodeGroupOutput",(-200,0))
            separate = create_node(colorlessTexGroup.nodes, "ShaderNodeSeparateColor",(-1200,0))
            compare = create_node(colorlessTexGroup.nodes, "ShaderNodeMath",(-1000,25), operation="COMPARE")
            compare.inputs[2].default_value = 0
            compare2 = create_node(colorlessTexGroup.nodes, "ShaderNodeMath",(-1000,-25), operation="COMPARE")
            compare2.inputs[2].default_value = 0
            add = create_node(colorlessTexGroup.nodes, "ShaderNodeMath",(-800,0))
            compare3 = create_node(colorlessTexGroup.nodes, "ShaderNodeMath",(-650,0), operation="COMPARE")
            compare3.inputs[1].default_value = 2 
            compare3.inputs[2].default_value = 0            
            combine = create_node(colorlessTexGroup.nodes, "ShaderNodeCombineColor",(-1000,-75))
            mixRGB = create_node(colorlessTexGroup.nodes, "ShaderNodeMixRGB",(-400,0))
            colorlessTexGroup.links.new(colorlessTexGroupI.outputs[0],separate.inputs[0])
            colorlessTexGroup.links.new(separate.outputs[0],combine.inputs[0])
            colorlessTexGroup.links.new(separate.outputs[0],compare.inputs[0])
            colorlessTexGroup.links.new(separate.outputs[1],compare.inputs[1])
            colorlessTexGroup.links.new(separate.outputs[0],compare2.inputs[0])
            colorlessTexGroup.links.new(separate.outputs[2],compare2.inputs[1])
            colorlessTexGroup.links.new(compare.outputs[0],add.inputs[0])
            colorlessTexGroup.links.new(compare2.outputs[0],add.inputs[1])
            colorlessTexGroup.links.new(add.outputs[0],compare3.inputs[0])
            colorlessTexGroup.links.new(compare3.outputs[0],mixRGB.inputs[0])
            colorlessTexGroup.links.new(colorlessTexGroupI.outputs[0],mixRGB.inputs[1])
            colorlessTexGroup.links.new(combine.outputs[0],mixRGB.inputs[2])
            colorlessTexGroup.links.new(mixRGB.outputs[0],colorlessTexGroupO.inputs[0])
            return colorlessTexGroup 

    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF=CurMat.nodes['Principled BSDF']
        pBSDF.inputs['Specular'].default_value = 0

        if "BlinkingSpeed" in Data:
            blinkingSpeed = CreateShaderNodeValue(CurMat,Data["BlinkingSpeed"],-2000, 450,"BlinkingSpeed") 

        if "HSV_Mod" in Data:
            HSV_Mod_w = CreateShaderNodeValue(CurMat,Data["HSV_Mod"]["W"],-2000, 150,"HSV_Mod.w") 
            HSV_Mod_x = CreateShaderNodeValue(CurMat,Data["HSV_Mod"]["X"],-2000, -950,"HSV_Mod.x")  
            HSV_Mod_y = CreateShaderNodeValue(CurMat,Data["HSV_Mod"]["Y"],-2000, -900,"HSV_Mod.y")  

        if "LayersSeparation" in Data:
            layersSeparation = CreateShaderNodeValue(CurMat,Data["LayersSeparation"],-2000, 100,"LayersSeparation") 

        if "ScanlinesDensity" in Data:
            scanlinesDensity = CreateShaderNodeValue(CurMat,Data["ScanlinesDensity"],-2000, 50,"ScanlinesDensity") 

        if "ScanlinesIntensity" in Data:
            scanlinesIntensity = CreateShaderNodeValue(CurMat,Data["ScanlinesIntensity"],-2000, 0,"ScanlinesIntensity") 

        if "IntensityPerLayer" in Data:
            intensityPerLayer_x = CreateShaderNodeValue(CurMat,Data["IntensityPerLayer"]["X"],-2000, -50,"IntensityPerLayer.x") 
            intensityPerLayer_y = CreateShaderNodeValue(CurMat,Data["IntensityPerLayer"]["Y"],-2000, -100,"IntensityPerLayer.y") 
            intensityPerLayer_z = CreateShaderNodeValue(CurMat,Data["IntensityPerLayer"]["Z"],-2000, -150,"IntensityPerLayer.z") 

        if "ImageScale" in Data:
            imageScale = CreateShaderNodeValue(CurMat,Data["ImageScale"],-2000, -200,"ImageScale")

        if "ScrollSpeed1" in Data:
            scrollSpeed1 = CreateShaderNodeValue(CurMat,Data["ScrollSpeed1"],-2000, -250,"ScrollSpeed1")

        if "ScrollStepFactor1" in Data:
            scrollStepFactor1 = CreateShaderNodeValue(CurMat,Data["ScrollStepFactor1"],-2000, -300,"ScrollStepFactor1")  

        if "ScrollMaskHeight1" in Data:
            scrollMaskHeight1 = CreateShaderNodeValue(CurMat,Data["ScrollMaskHeight1"],-2000, -350,"ScrollMaskHeight1")  

        if "ScrollMaskStartPoint1" in Data:
            scrollMaskStartPoint1 = CreateShaderNodeValue(CurMat,Data["ScrollMaskStartPoint1"],-2000, -400,"ScrollMaskStartPoint1")  

        if "ScrollSpeed2" in Data:
            scrollSpeed2 = CreateShaderNodeValue(CurMat,Data["ScrollSpeed2"],-2000, -500,"ScrollSpeed2")

        if "ScrollStepFactor2" in Data:
            scrollStepFactor2 = CreateShaderNodeValue(CurMat,Data["ScrollStepFactor2"],-2000, -550,"ScrollStepFactor2")  

        if "ScrollMaskHeight2" in Data:
            scrollMaskHeight2 = CreateShaderNodeValue(CurMat,Data["ScrollMaskHeight2"],-2000, -600,"ScrollMaskHeight2")  

        if "ScrollMaskStartPoint2" in Data:
            scrollMaskStartPoint2 = CreateShaderNodeValue(CurMat,Data["ScrollMaskStartPoint2"],-2000, -650,"ScrollMaskStartPoint2")  

        if "IsBroken" in Data:
            isBroken = CreateShaderNodeValue(CurMat,Data["IsBroken"],-2000, -700,"IsBroken")

        if "ScrollVerticalOrHorizontal" in Data:
            scrollVerticalOrHorizontal = CreateShaderNodeValue(CurMat,Data["ScrollVerticalOrHorizontal"],-2000, -750,"ScrollVerticalOrHorizontal")  
        
        if "Emissive" in Data:
            emissive = CreateShaderNodeValue(CurMat,Data["Emissive"],-2000, -800,"Emissive")  

        if "EmissiveColor" in Data:
            emissiveColor = CreateShaderNodeRGB(CurMat,Data["EmissiveColor"],-2000, -850,"EmissiveColor")

        if "FixForBlack" in Data:
            fixForBlack = CreateShaderNodeValue(CurMat,Data["FixForBlack"],-2000, -1000,"FixForBlack")  

        if "Metalness" in Data:
            metalness = CreateShaderNodeValue(CurMat,Data["Metalness"],-2000, -1050,"Metalness")  

        if "Roughness" in Data:
            roughness = CreateShaderNodeValue(CurMat,Data["Roughness"],-2000, -1100,"Roughness")  

        if "ParalaxTexture" in Data:
            parImg=imageFromRelPath(Data["ParalaxTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.image_format)

        if "BlinkingMaskTexture" in Data:
            blinkImg=imageFromRelPath(Data["BlinkingMaskTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.image_format)

        if "ScanlineTexture" in Data:
            scanLineImg = imageFromRelPath(Data["ScanlineTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.image_format)

        if "ScrollMaskTexture" in Data:
            scrollMaskImg=imageFromRelPath(Data["ScrollMaskTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.image_format)

        # tangent, geometry node, uv
        tangent = create_node(CurMat.nodes, "ShaderNodeTangent", (-2000,400))
        tangent.direction_type = "UV_MAP"
        geometry = create_node(CurMat.nodes, "ShaderNodeNewGeometry", (-2000,300))
        UVMap = create_node(CurMat.nodes,"ShaderNodeUVMap",(-2000, 200))

        # binormal
        vecCross = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-1850,350), operation="CROSS_PRODUCT")
        CurMat.links.new(geometry.outputs[1], vecCross.inputs[0])
        CurMat.links.new(tangent.outputs[0], vecCross.inputs[1])

        # leftRightDot
        vecDot = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-1500,200), operation= "DOT_PRODUCT")
        CurMat.links.new(geometry.outputs[4], vecDot.inputs[0])
        CurMat.links.new(tangent.outputs[0], vecDot.inputs[1])

        # topDownDot
        vecDot2 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-1500,150), operation= "DOT_PRODUCT")
        CurMat.links.new(geometry.outputs[4], vecDot2.inputs[0])
        CurMat.links.new(vecCross.outputs[0], vecDot2.inputs[1])

        # modUV
        vecMul = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-1350,150), operation= "MULTIPLY")
        combine = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",(-1200,175))
        CurMat.links.new(vecDot2.outputs["Value"], vecMul.inputs[0])
        CurMat.links.new(HSV_Mod_w.outputs[0], vecMul.inputs[1])
        CurMat.links.new(vecDot.outputs["Value"], combine.inputs[0])
        CurMat.links.new(vecMul.outputs[0], combine.inputs[1])

        # newUV
        vecSub = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-1500,0), operation= "SUBTRACT")
        vecSub.inputs[1].default_value = (.5,.5,.5)
        vecMul2 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-1350,0), operation= "MULTIPLY")
        vecAdd = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-1200,0), operation= "ADD")
        vecAdd.inputs[1].default_value = (.5,.5,.5)
        CurMat.links.new(UVMap.outputs[0], vecSub.inputs[0])
        CurMat.links.new(vecSub.outputs[0], vecMul2.inputs[0])
        CurMat.links.new(imageScale.outputs[0], vecMul2.inputs[1])
        CurMat.links.new(vecMul2.outputs[0], vecAdd.inputs[0])

        # time node
        time = CreateShaderNodeValue(CurMat,1,-2000, -450,"Time")
        timeDriver = time.outputs[0].driver_add("default_value")
        timeDriver.driver.expression = "frame / 24" #FIXME: frame / framerate variable

        # scroll1
        if 'scroll1' in bpy.data.node_groups.keys():
            scroll1Group = bpy.data.node_groups['scroll1']
        else:
            scroll1Group = bpy.data.node_groups.new("scroll1","ShaderNodeTree") 
            scroll1Group.inputs.new('NodeSocketFloat','ScrollSpeed1')
            scroll1Group.inputs.new('NodeSocketFloat','ScrollStepFactor1')
            scroll1Group.inputs.new('NodeSocketFloat','Time')
            scroll1Group.outputs.new('NodeSocketFloat','scroll1')
            scroll1GroupI = create_node(scroll1Group.nodes, "NodeGroupInput",(-1400,0))
            scroll1GroupO = create_node(scroll1Group.nodes, "NodeGroupOutput",(-800,0))
            mul = create_node(scroll1Group.nodes, "ShaderNodeMath",(-1250,0),operation="MULTIPLY")
            mul2 = create_node(scroll1Group.nodes, "ShaderNodeMath",(-1100,0),operation="MULTIPLY")
            div = create_node(scroll1Group.nodes, "ShaderNodeMath",(-950,0),operation="DIVIDE")
            scroll1Group.links.new(scroll1GroupI.outputs[2],mul.inputs[0])
            scroll1Group.links.new(scroll1GroupI.outputs[0],mul.inputs[1])
            scroll1Group.links.new(mul.outputs[0],mul2.inputs[0])
            scroll1Group.links.new(scroll1GroupI.outputs[1],mul2.inputs[1])
            scroll1Group.links.new(mul2.outputs[0],div.inputs[0])
            scroll1Group.links.new(scroll1GroupI.outputs[1],div.inputs[1])
            scroll1Group.links.new(div.outputs[0],scroll1GroupO.inputs[0])

        scroll1 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1500, -200), label="scroll1")
        scroll1.node_tree = scroll1Group
        scroll1.name = "scroll1"
        CurMat.links.new(scrollSpeed1.outputs[0], scroll1.inputs[0])
        CurMat.links.new(scrollStepFactor1.outputs[0], scroll1.inputs[1])
        CurMat.links.new(time.outputs[0], scroll1.inputs[2])

        # scrollUV1
        if 'scrollUV1' in bpy.data.node_groups.keys():
            scrollUV1Group = bpy.data.node_groups['scrollUV1']
        else:
            scrollUV1Group = bpy.data.node_groups.new("scrollUV1","ShaderNodeTree") 
            scrollUV1Group.inputs.new('NodeSocketVector','newUV')
            scrollUV1Group.inputs.new('NodeSocketFloat','ScrollMaskHeight1')
            scrollUV1Group.inputs.new('NodeSocketFloat','scroll1')
            scrollUV1Group.inputs.new('NodeSocketFloat','ScrollMaskStartPoint1')
            scrollUV1Group.outputs.new('NodeSocketVector','scrollUV1')
            scrollUV1GroupI = create_node(scrollUV1Group.nodes, "NodeGroupInput",(-1400,0))
            scrollUV1GroupO = create_node(scrollUV1Group.nodes, "NodeGroupOutput",(-200,0))
            separate = create_node(scrollUV1Group.nodes, "ShaderNodeSeparateXYZ",(-1250,100))
            div2 = create_node(scrollUV1Group.nodes, "ShaderNodeMath",(-1250,0),operation="DIVIDE")
            mul3 = create_node(scrollUV1Group.nodes, "ShaderNodeMath",(-1100,0),operation="MULTIPLY")
            add = create_node(scrollUV1Group.nodes, "ShaderNodeMath",(-950,0),operation="ADD")
            frac = create_node(scrollUV1Group.nodes, "ShaderNodeMath",(-800,0),operation="FRACT")
            mul4 = create_node(scrollUV1Group.nodes, "ShaderNodeMath",(-650,0),operation="MULTIPLY")
            add2 = create_node(scrollUV1Group.nodes, "ShaderNodeMath",(-500,0),operation="ADD")
            combine2 = create_node(scrollUV1Group.nodes, "ShaderNodeCombineXYZ",(-350,100))
            div2.inputs[0].default_value = 1
            scrollUV1Group.links.new(scrollUV1GroupI.outputs[0],separate.inputs[0])
            scrollUV1Group.links.new(scrollUV1GroupI.outputs[1],div2.inputs[1])
            scrollUV1Group.links.new(separate.outputs[1],mul3.inputs[0])
            scrollUV1Group.links.new(div2.outputs[0],mul3.inputs[1])
            scrollUV1Group.links.new(mul3.outputs[0],add.inputs[0])
            scrollUV1Group.links.new(scrollUV1GroupI.outputs[2],add.inputs[1])
            scrollUV1Group.links.new(add.outputs[0],frac.inputs[0])
            scrollUV1Group.links.new(frac.outputs[0],mul4.inputs[0])
            scrollUV1Group.links.new(scrollUV1GroupI.outputs[1],mul4.inputs[1])
            scrollUV1Group.links.new(mul4.outputs[0],add2.inputs[0])
            scrollUV1Group.links.new(scrollUV1GroupI.outputs[3],add2.inputs[1])
            scrollUV1Group.links.new(separate.outputs[0],combine2.inputs[0])
            scrollUV1Group.links.new(add2.outputs[0],combine2.inputs[1])
            scrollUV1Group.links.new(combine2.outputs[0],scrollUV1GroupO.inputs[0])

        scrollUV1 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1350, -200), label="scrollUV1")
        scrollUV1.node_tree = scrollUV1Group
        scrollUV1.name = "scrollUV1"
        CurMat.links.new(vecAdd.outputs[0], scrollUV1.inputs[0])
        CurMat.links.new(scrollMaskHeight1.outputs[0], scrollUV1.inputs[1])
        CurMat.links.new(scroll1.outputs[0], scrollUV1.inputs[2])
        CurMat.links.new(scrollMaskStartPoint1.outputs[0], scrollUV1.inputs[3])
        # scrollUV1X
        if 'scrollUV1X' in bpy.data.node_groups.keys():
            scrollUV1XGroup = bpy.data.node_groups['scrollUV1X']
        else:
            scrollUV1XGroup = bpy.data.node_groups.new("scrollUV1X","ShaderNodeTree") 
            scrollUV1XGroup.inputs.new('NodeSocketVector','newUV')
            scrollUV1XGroup.inputs.new('NodeSocketFloat','ScrollMaskHeight1')
            scrollUV1XGroup.inputs.new('NodeSocketFloat','scroll1')
            scrollUV1XGroup.inputs.new('NodeSocketFloat','ScrollMaskStartPoint1')
            scrollUV1XGroup.outputs.new('NodeSocketVector','scrollUV1X')
            scrollUV1XGroupI = create_node(scrollUV1XGroup.nodes, "NodeGroupInput",(-1400,0))
            scrollUV1XGroupO = create_node(scrollUV1XGroup.nodes, "NodeGroupOutput",(-200,0))
            separate = create_node(scrollUV1XGroup.nodes, "ShaderNodeSeparateXYZ",(-1250,-100))
            div = create_node(scrollUV1XGroup.nodes, "ShaderNodeMath",(-1250,0),operation="DIVIDE")
            mul = create_node(scrollUV1XGroup.nodes, "ShaderNodeMath",(-1100,0),operation="MULTIPLY")
            add = create_node(scrollUV1XGroup.nodes, "ShaderNodeMath",(-950,0),operation="ADD")
            frac = create_node(scrollUV1XGroup.nodes, "ShaderNodeMath",(-800,0),operation="FRACT")
            mul2 = create_node(scrollUV1XGroup.nodes, "ShaderNodeMath",(-650,0),operation="MULTIPLY")
            add2 = create_node(scrollUV1XGroup.nodes, "ShaderNodeMath",(-500,0),operation="ADD")
            combine4 = create_node(scrollUV1XGroup.nodes, "ShaderNodeCombineXYZ",(-350,-100))
            div.inputs[0].default_value = 1
            scrollUV1XGroup.links.new(scrollUV1XGroupI.outputs[0],separate.inputs[0])
            scrollUV1XGroup.links.new(scrollUV1XGroupI.outputs[1],div.inputs[1])
            scrollUV1XGroup.links.new(separate.outputs[0],mul.inputs[0])
            scrollUV1XGroup.links.new(div.outputs[0],mul.inputs[1])
            scrollUV1XGroup.links.new(mul.outputs[0],add.inputs[0])
            scrollUV1XGroup.links.new(scrollUV1XGroupI.outputs[2],add.inputs[1])
            scrollUV1XGroup.links.new(add.outputs[0],frac.inputs[0])
            scrollUV1XGroup.links.new(frac.outputs[0],mul2.inputs[0])
            scrollUV1XGroup.links.new(scrollUV1XGroupI.outputs[1],mul2.inputs[1])
            scrollUV1XGroup.links.new(mul2.outputs[0],add2.inputs[0])
            scrollUV1XGroup.links.new(scrollUV1XGroupI.outputs[3],add2.inputs[1])
            scrollUV1XGroup.links.new(separate.outputs[1],combine4.inputs[1])
            scrollUV1XGroup.links.new(add2.outputs[0],combine4.inputs[0])
            scrollUV1XGroup.links.new(combine4.outputs[0],scrollUV1XGroupO.inputs[0])

        scrollUV1X = create_node(CurMat.nodes,"ShaderNodeGroup",(-1350, -250), label="scrollUV1X")
        scrollUV1X.node_tree = scrollUV1XGroup
        scrollUV1X.name = "scrollUV1X"
        CurMat.links.new(vecAdd.outputs[0], scrollUV1X.inputs[0])
        CurMat.links.new(scrollMaskHeight1.outputs[0], scrollUV1X.inputs[1])
        CurMat.links.new(scroll1.outputs[0], scrollUV1X.inputs[2])
        CurMat.links.new(scrollMaskStartPoint1.outputs[0], scrollUV1X.inputs[3])

        # scroll2
        if 'scroll2' in bpy.data.node_groups.keys():
            scroll2Group = bpy.data.node_groups['scroll2']
        else:
            scroll2Group = bpy.data.node_groups.new("scroll2","ShaderNodeTree") 
            scroll2Group.inputs.new('NodeSocketFloat','ScrollSpeed2')
            scroll2Group.inputs.new('NodeSocketFloat','ScrollStepFactor2')
            scroll2Group.inputs.new('NodeSocketFloat','Time')
            scroll2Group.outputs.new('NodeSocketFloat','scroll2')
            scroll2GroupI = create_node(scroll2Group.nodes, "NodeGroupInput",(-1400,0))
            scroll2GroupO = create_node(scroll2Group.nodes, "NodeGroupOutput",(-800,0))
            mul = create_node(scroll2Group.nodes, "ShaderNodeMath",(-1250,0),operation="MULTIPLY")
            mul2 = create_node(scroll2Group.nodes, "ShaderNodeMath",(-1100,0),operation="MULTIPLY")
            div = create_node(scroll2Group.nodes, "ShaderNodeMath",(-950,0),operation="DIVIDE")
            scroll2Group.links.new(scroll2GroupI.outputs[2],mul.inputs[0])
            scroll2Group.links.new(scroll2GroupI.outputs[0],mul.inputs[1])
            scroll2Group.links.new(mul.outputs[0],mul2.inputs[0])
            scroll2Group.links.new(scroll2GroupI.outputs[1],mul2.inputs[1])
            scroll2Group.links.new(mul2.outputs[0],div.inputs[0])
            scroll2Group.links.new(scroll2GroupI.outputs[1],div.inputs[1])
            scroll2Group.links.new(div.outputs[0],scroll2GroupO.inputs[0])

        scroll2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1500, -300), label="scroll2")
        scroll2.node_tree = scroll2Group
        scroll2.name = "scroll2"
        CurMat.links.new(scrollSpeed2.outputs[0], scroll2.inputs[0])
        CurMat.links.new(scrollStepFactor2.outputs[0], scroll2.inputs[1])
        CurMat.links.new(time.outputs[0], scroll2.inputs[2])

        # scrollUV2
        if 'scrollUV2' in bpy.data.node_groups.keys():
            scrollUV2Group = bpy.data.node_groups['scrollUV2']
        else:
            scrollUV2Group = bpy.data.node_groups.new("scrollUV2","ShaderNodeTree") 
            scrollUV2Group.inputs.new('NodeSocketVector','newUV')
            scrollUV2Group.inputs.new('NodeSocketFloat','ScrollMaskHeight2')
            scrollUV2Group.inputs.new('NodeSocketFloat','scroll2')
            scrollUV2Group.inputs.new('NodeSocketFloat','ScrollMaskStartPoint2')
            scrollUV2Group.outputs.new('NodeSocketVector','scrollUV2')
            scrollUV2GroupI = create_node(scrollUV2Group.nodes, "NodeGroupInput",(-1400,0))
            scrollUV2GroupO = create_node(scrollUV2Group.nodes, "NodeGroupOutput",(-200,0))
            separate = create_node(scrollUV2Group.nodes, "ShaderNodeSeparateXYZ",(-1250,100))
            div2 = create_node(scrollUV2Group.nodes, "ShaderNodeMath",(-1250,0),operation="DIVIDE")
            mul3 = create_node(scrollUV2Group.nodes, "ShaderNodeMath",(-1100,0),operation="MULTIPLY")
            add = create_node(scrollUV2Group.nodes, "ShaderNodeMath",(-950,0),operation="ADD")
            frac = create_node(scrollUV2Group.nodes, "ShaderNodeMath",(-800,0),operation="FRACT")
            mul4 = create_node(scrollUV2Group.nodes, "ShaderNodeMath",(-650,0),operation="MULTIPLY")
            add2 = create_node(scrollUV2Group.nodes, "ShaderNodeMath",(-500,0),operation="ADD")
            combine3 = create_node(scrollUV2Group.nodes, "ShaderNodeCombineXYZ",(-350,100))
            div2.inputs[0].default_value = 1
            scrollUV2Group.links.new(scrollUV2GroupI.outputs[0],separate.inputs[0])
            scrollUV2Group.links.new(scrollUV2GroupI.outputs[1],div2.inputs[1])
            scrollUV2Group.links.new(separate.outputs[1],mul3.inputs[0])
            scrollUV2Group.links.new(div2.outputs[0],mul3.inputs[1])
            scrollUV2Group.links.new(mul3.outputs[0],add.inputs[0])
            scrollUV2Group.links.new(scrollUV2GroupI.outputs[2],add.inputs[1])
            scrollUV2Group.links.new(add.outputs[0],frac.inputs[0])
            scrollUV2Group.links.new(frac.outputs[0],mul4.inputs[0])
            scrollUV2Group.links.new(scrollUV2GroupI.outputs[1],mul4.inputs[1])
            scrollUV2Group.links.new(mul4.outputs[0],add2.inputs[0])
            scrollUV2Group.links.new(scrollUV2GroupI.outputs[3],add2.inputs[1])
            scrollUV2Group.links.new(separate.outputs[0],combine3.inputs[0])
            scrollUV2Group.links.new(add2.outputs[0],combine3.inputs[1])
            scrollUV2Group.links.new(combine3.outputs[0],scrollUV2GroupO.inputs[0])

        scrollUV2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1350, -300), label="scrollUV2")
        scrollUV2.node_tree = scrollUV2Group
        scrollUV2.name = "scrollUV2"
        CurMat.links.new(vecAdd.outputs[0], scrollUV2.inputs[0])
        CurMat.links.new(scrollMaskHeight2.outputs[0], scrollUV2.inputs[1])
        CurMat.links.new(scroll2.outputs[0], scrollUV2.inputs[2])
        CurMat.links.new(scrollMaskStartPoint2.outputs[0], scrollUV2.inputs[3])

        # scrollUV2X
        if 'scrollUV2X' in bpy.data.node_groups.keys():
            scrollUV2XGroup = bpy.data.node_groups['scrollUV2X']
        else:
            scrollUV2XGroup = bpy.data.node_groups.new("scrollUV2X","ShaderNodeTree") 
            scrollUV2XGroup.inputs.new('NodeSocketVector','newUV')
            scrollUV2XGroup.inputs.new('NodeSocketFloat','ScrollMaskHeight2')
            scrollUV2XGroup.inputs.new('NodeSocketFloat','scroll2')
            scrollUV2XGroup.inputs.new('NodeSocketFloat','ScrollMaskStartPoint2')
            scrollUV2XGroup.outputs.new('NodeSocketVector','scrollUV2X')
            scrollUV2XGroupI = create_node(scrollUV2XGroup.nodes, "NodeGroupInput",(-1400,0))
            scrollUV2XGroupO = create_node(scrollUV2XGroup.nodes, "NodeGroupOutput",(-200,0))
            separate = create_node(scrollUV2XGroup.nodes, "ShaderNodeSeparateXYZ",(-1250,-100))
            div = create_node(scrollUV2XGroup.nodes, "ShaderNodeMath",(-1250,0),operation="DIVIDE")
            mul = create_node(scrollUV2XGroup.nodes, "ShaderNodeMath",(-1100,0),operation="MULTIPLY")
            add = create_node(scrollUV2XGroup.nodes, "ShaderNodeMath",(-950,0),operation="ADD")
            frac = create_node(scrollUV2XGroup.nodes, "ShaderNodeMath",(-800,0),operation="FRACT")
            mul2 = create_node(scrollUV2XGroup.nodes, "ShaderNodeMath",(-650,0),operation="MULTIPLY")
            add2 = create_node(scrollUV2XGroup.nodes, "ShaderNodeMath",(-500,0),operation="ADD")
            combine14 = create_node(scrollUV2XGroup.nodes, "ShaderNodeCombineXYZ",(-350,-100))
            div.inputs[0].default_value = 1
            scrollUV2XGroup.links.new(scrollUV2XGroupI.outputs[0],separate.inputs[0])
            scrollUV2XGroup.links.new(scrollUV2XGroupI.outputs[1],div.inputs[1])
            scrollUV2XGroup.links.new(separate.outputs[0],mul.inputs[0])
            scrollUV2XGroup.links.new(div.outputs[0],mul.inputs[1])
            scrollUV2XGroup.links.new(mul.outputs[0],add.inputs[0])
            scrollUV2XGroup.links.new(scrollUV2XGroupI.outputs[2],add.inputs[1])
            scrollUV2XGroup.links.new(add.outputs[0],frac.inputs[0])
            scrollUV2XGroup.links.new(frac.outputs[0],mul2.inputs[0])
            scrollUV2XGroup.links.new(scrollUV2XGroupI.outputs[1],mul2.inputs[1])
            scrollUV2XGroup.links.new(mul2.outputs[0],add2.inputs[0])
            scrollUV2XGroup.links.new(scrollUV2XGroupI.outputs[3],add2.inputs[1])
            scrollUV2XGroup.links.new(separate.outputs[1],combine14.inputs[1])
            scrollUV2XGroup.links.new(add2.outputs[0],combine14.inputs[0])
            scrollUV2XGroup.links.new(combine14.outputs[0],scrollUV2XGroupO.inputs[0])

        scrollUV2X = create_node(CurMat.nodes,"ShaderNodeGroup",(-1350, -350), label="scrollUV2X")
        scrollUV2X.node_tree = scrollUV2XGroup
        scrollUV2X.name = "scrollUV2X"
        CurMat.links.new(vecAdd.outputs[0], scrollUV2X.inputs[0])
        CurMat.links.new(scrollMaskHeight2.outputs[0], scrollUV2X.inputs[1])
        CurMat.links.new(scroll2.outputs[0], scrollUV2X.inputs[2])
        CurMat.links.new(scrollMaskStartPoint2.outputs[0], scrollUV2X.inputs[3])

        # rndBlocks  
        lerpG = createLerpGroup()
        lerp = create_node(CurMat.nodes,"ShaderNodeGroup",(-1050, -450), label="lerp")
        lerp.node_tree = lerpG 
        lerp.inputs[0].default_value = 2
        lerp.inputs[1].default_value = 8
        frac2 = create_node(CurMat.nodes,"ShaderNodeMath", (-1200,-450) , operation = 'FRACT')
        add7 = create_node(CurMat.nodes,"ShaderNodeMath", (-1350,-450) , operation = 'ADD')
        add7.inputs[1].default_value = 0.375
        CurMat.links.new(time.outputs[0],add7.inputs[0])
        CurMat.links.new(add7.outputs[0],frac2.inputs[0])
        CurMat.links.new(frac2.outputs[0],lerp.inputs[2]) # rndBlocks   

        # brokenUV
        if 'brokenUV' in bpy.data.node_groups.keys():
            brokenUVGroup = bpy.data.node_groups['brokenUV']
        else:
            brokenUVGroup = bpy.data.node_groups.new("brokenUV","ShaderNodeTree") 
            brokenUVGroup.inputs.new('NodeSocketFloat','rndBlocks')
            brokenUVGroup.inputs.new('NodeSocketFloat','Time')
            brokenUVGroup.inputs.new('NodeSocketVector','UV')
            brokenUVGroup.outputs.new('NodeSocketVector','brokenUV')
            brokenUVGroupI = create_node(brokenUVGroup.nodes, "NodeGroupInput",(-1400,0))
            brokenUVGroupO = create_node(brokenUVGroup.nodes, "NodeGroupOutput",(200,0))
            hash12G = createHash12Group()
            hash12 = create_node(brokenUVGroup.nodes,"ShaderNodeGroup",(-650,-50), label="hash12")
            hash12.node_tree = hash12G
            add = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-1250,0) , operation = 'ADD')
            add.inputs[1].default_value = 0.35748
            mul = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-1100,0) , operation = 'MULTIPLY')
            mul.inputs[1].default_value = 60
            floor = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-800,-50) , operation = 'FLOOR')
            separate = create_node(brokenUVGroup.nodes,"ShaderNodeSeparateXYZ", (-800,0))
            combine15 = create_node(brokenUVGroup.nodes,"ShaderNodeCombineXYZ", (-650,0))
            vecAdd2 = create_node(brokenUVGroup.nodes,"ShaderNodeVectorMath", (-350,0) , operation = 'ADD')
            vecFrac = create_node(brokenUVGroup.nodes,"ShaderNodeVectorMath", (-200,0) , operation = 'FRACTION')
            mul2 = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-1250,-100) , operation = 'MULTIPLY')
            floor2 = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-1100,-100) , operation = 'FLOOR')
            div = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-950,-100) , operation = 'DIVIDE')
            add2 = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-800,-100) , operation = 'ADD')
            add2.inputs[1].default_value = 1
            mul3 = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-650,-100) , operation = 'MULTIPLY')
            frac = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-500,-100) , operation = 'FRACT')
            clamp = create_node(brokenUVGroup.nodes,"ShaderNodeClamp", (-350,-100))
            lerp2 = create_node(brokenUVGroup.nodes,"ShaderNodeGroup",(-200,-100), label="lerp")
            lerp2.node_tree = lerpG 
            lerp2.inputs[0].default_value = 1
            lerp2.inputs[1].default_value = 4
            vecDiv = create_node(brokenUVGroup.nodes,"ShaderNodeVectorMath", (-50,0) , operation = 'DIVIDE')

            brokenUVGroup.links.new(brokenUVGroupI.outputs[1],add.inputs[0])
            brokenUVGroup.links.new(add.outputs[0],mul.inputs[0])
            brokenUVGroup.links.new(mul.outputs[0],floor.inputs[0])
            brokenUVGroup.links.new(floor.outputs[0],hash12.inputs[0])
            brokenUVGroup.links.new(brokenUVGroupI.outputs[2],separate.inputs[0])
            brokenUVGroup.links.new(separate.outputs[0],combine15.inputs[0])
            brokenUVGroup.links.new(separate.outputs[0],combine15.inputs[1])
            brokenUVGroup.links.new(combine15.outputs[0],vecAdd2.inputs[0])
            brokenUVGroup.links.new(hash12.outputs[0],vecAdd2.inputs[1])
            brokenUVGroup.links.new(vecAdd2.outputs[0],vecFrac.inputs[0])
            brokenUVGroup.links.new(separate.outputs[0],mul2.inputs[0])
            brokenUVGroup.links.new(brokenUVGroupI.outputs[0],mul2.inputs[1])
            brokenUVGroup.links.new(mul2.outputs[0],floor2.inputs[0])
            brokenUVGroup.links.new(floor2.outputs[0],div.inputs[0])
            brokenUVGroup.links.new(brokenUVGroupI.outputs[0],div.inputs[1])
            brokenUVGroup.links.new(div.outputs[0],add2.inputs[0])
            brokenUVGroup.links.new(add2.outputs[0],mul3.inputs[0])
            brokenUVGroup.links.new(brokenUVGroupI.outputs[1],mul3.inputs[0])
            brokenUVGroup.links.new(mul3.outputs[0],frac.inputs[0])
            brokenUVGroup.links.new(frac.outputs[0],clamp.inputs[0])
            brokenUVGroup.links.new(clamp.outputs[0],lerp2.inputs[2])
            brokenUVGroup.links.new(vecFrac.outputs[0],vecDiv.inputs[0])
            brokenUVGroup.links.new(lerp2.outputs[0],vecDiv.inputs[1])
            brokenUVGroup.links.new(vecDiv.outputs[0],brokenUVGroupO.inputs[0])

        brokenUV = create_node(CurMat.nodes,"ShaderNodeGroup",(-1050, -500), label="brokenUV")
        brokenUV.node_tree = brokenUVGroup

        CurMat.links.new(lerp.outputs[0],brokenUV.inputs[0])
        CurMat.links.new(time.outputs[0],brokenUV.inputs[1])
        CurMat.links.new(UVMap.outputs[0],brokenUV.inputs[2])

        # rndColorIndex
        if 'rndColorIndex' in bpy.data.node_groups.keys():
            rndColorIGroup = bpy.data.node_groups['rndColorIndex']
        else:       
            rndColorIGroup = bpy.data.node_groups.new("rndColorIndex","ShaderNodeTree") 
            rndColorIGroup.inputs.new('NodeSocketFloat','rndBlocks')
            rndColorIGroup.inputs.new('NodeSocketFloat','Time')
            rndColorIGroup.inputs.new('NodeSocketVector','brokenUV')
            rndColorIGroup.outputs.new('NodeSocketInt','rndColorIndex')
            rndColorIGroupI = create_node(rndColorIGroup.nodes, "NodeGroupInput",(-1400,0))
            rndColorIGroupO = create_node(rndColorIGroup.nodes, "NodeGroupOutput",(200,0))  
            separate2 = create_node(rndColorIGroup.nodes,"ShaderNodeSeparateXYZ", (-1250,0))
            combine5 = create_node(rndColorIGroup.nodes,"ShaderNodeCombineXYZ", (-1100,0))
            vecMul = create_node(rndColorIGroup.nodes,"ShaderNodeVectorMath", (-950,0), operation="MULTIPLY")
            vecFloor = create_node(rndColorIGroup.nodes,"ShaderNodeVectorMath", (-800,0), operation="FLOOR")
            vecDiv2 = create_node(rndColorIGroup.nodes,"ShaderNodeVectorMath", (-650,0), operation="DIVIDE")
            frac6 = create_node(rndColorIGroup.nodes,"ShaderNodeMath", (-500,-50), operation="FRACT")
            vecMul2 = create_node(rndColorIGroup.nodes,"ShaderNodeVectorMath", (-350,-25), operation="MULTIPLY")
            vecSub = create_node(rndColorIGroup.nodes,"ShaderNodeVectorMath", (-200,-25), operation="SUBTRACT")
            vecSub.inputs[1].default_value = (0.1625,0.1625,0.1625)
            hash12G = createHash12Group()
            hash12_2 = create_node(rndColorIGroup.nodes,"ShaderNodeGroup",(-50,-25), label="hash12")
            hash12_2.node_tree = hash12G
            mul9 = create_node(rndColorIGroup.nodes,"ShaderNodeMath", (100,-25), operation="MULTIPLY")
            mul9.inputs[1].default_value = 4
            rndColorIGroup.links.new(rndColorIGroupI.outputs[2],separate2.inputs[0])
            rndColorIGroup.links.new(separate2.outputs[0],combine5.inputs[0])
            rndColorIGroup.links.new(separate2.outputs[0],combine5.inputs[1])
            rndColorIGroup.links.new(combine5.outputs[0],vecMul.inputs[0])
            rndColorIGroup.links.new(rndColorIGroupI.outputs[0],vecMul.inputs[1])
            rndColorIGroup.links.new(vecMul.outputs[0],vecFloor.inputs[0])
            rndColorIGroup.links.new(vecFloor.outputs[0],vecDiv2.inputs[0])
            rndColorIGroup.links.new(rndColorIGroupI.outputs[0],vecDiv2.inputs[1])
            rndColorIGroup.links.new(rndColorIGroupI.outputs[1],frac6.inputs[0])
            rndColorIGroup.links.new(vecDiv2.outputs[0],vecMul2.inputs[0])
            rndColorIGroup.links.new(frac6.outputs[0],vecMul2.inputs[1])
            rndColorIGroup.links.new(vecMul2.outputs[0],vecSub.inputs[0])
            rndColorIGroup.links.new(vecSub.outputs[0],hash12_2.inputs[0])
            rndColorIGroup.links.new(hash12_2.outputs[0],mul9.inputs[0])
            rndColorIGroup.links.new(mul9.outputs[0],rndColorIGroupO.inputs[0])
                
        rndColorIndex = create_node(CurMat.nodes,"ShaderNodeGroup",(-900, -475), label="rndColorIndex")
        rndColorIndex.node_tree = rndColorIGroup
        CurMat.links.new(lerp.outputs[0],rndColorIndex.inputs[0])
        CurMat.links.new(time.outputs[0],rndColorIndex.inputs[1])
        CurMat.links.new(brokenUV.outputs[0],rndColorIndex.inputs[2])

        # rndColors
        if 'rndColor' in bpy.data.node_groups.keys():
            rndColorGroup = bpy.data.node_groups['rndColor']
        else:
            rndColorGroup = bpy.data.node_groups.new("rndColor","ShaderNodeTree") 
            rndColorGroup.inputs.new('NodeSocketInt','rndColorIndex')
            rndColorGroup.outputs.new('NodeSocketColor','rndColor')
            rndColorGroupI = create_node(rndColorGroup.nodes, "NodeGroupInput",(-1400,0))
            rndColorGroupO = create_node(rndColorGroup.nodes, "NodeGroupOutput",(200,0))  
            compare = create_node(rndColorGroup.nodes,"ShaderNodeMath", (-1100,150), operation="COMPARE")
            compare.inputs[1].default_value = 0
            compare.inputs[2].default_value = 0
            compare2 = create_node(rndColorGroup.nodes,"ShaderNodeMath", (-1100,50), operation="COMPARE")
            compare2.inputs[1].default_value = 1
            compare2.inputs[2].default_value = 0
            compare3 = create_node(rndColorGroup.nodes,"ShaderNodeMath", (-1100,-50), operation="COMPARE")
            compare3.inputs[1].default_value = 2
            compare3.inputs[2].default_value = 0
            compare4 = create_node(rndColorGroup.nodes,"ShaderNodeMath", (-1100,-150), operation="COMPARE")
            compare4.inputs[1].default_value = 3
            compare4.inputs[2].default_value = 0
            combine5 = create_node(rndColorGroup.nodes,"ShaderNodeCombineXYZ", (-900,175)) # float3 (1,1,1)
            combine5.inputs[0].default_value = 1
            combine5.inputs[1].default_value = 1
            combine5.inputs[2].default_value = 1
            combine6 = create_node(rndColorGroup.nodes,"ShaderNodeCombineXYZ", (-900,75)) # float3 (.2,0,0)
            combine6.inputs[0].default_value = .2
            combine6.inputs[1].default_value = 0
            combine6.inputs[2].default_value = 0
            combine7 = create_node(rndColorGroup.nodes,"ShaderNodeCombineXYZ", (-900,-25)) # float3 (0,1,0)
            combine7.inputs[0].default_value = 0
            combine7.inputs[1].default_value = 1
            combine7.inputs[2].default_value = 0
            combine8 = create_node(rndColorGroup.nodes,"ShaderNodeCombineXYZ", (-900,-125)) # float3 (0,0,1)
            combine8.inputs[0].default_value = 0
            combine8.inputs[1].default_value = 0
            combine8.inputs[2].default_value = 1
            vecMul3 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-700,150), operation="MULTIPLY")
            vecMul4 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-700,50), operation="MULTIPLY")
            vecMul5 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-700,-50), operation="MULTIPLY")
            vecMul6 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-700,-150), operation="MULTIPLY")
            vecAdd3 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-500,100), operation="ADD")
            vecAdd4 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-500,-100), operation="ADD")
            vecAdd5 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-300,0), operation="ADD")
            rndColorGroup.links.new(rndColorGroupI.outputs[0],compare.inputs[0])
            rndColorGroup.links.new(rndColorGroupI.outputs[0],compare2.inputs[0])
            rndColorGroup.links.new(rndColorGroupI.outputs[0],compare3.inputs[0])
            rndColorGroup.links.new(rndColorGroupI.outputs[0],compare4.inputs[0])
            rndColorGroup.links.new(compare.outputs[0],vecMul3.inputs[1])
            rndColorGroup.links.new(compare2.outputs[0],vecMul4.inputs[1])
            rndColorGroup.links.new(compare3.outputs[0],vecMul5.inputs[1])
            rndColorGroup.links.new(compare4.outputs[0],vecMul6.inputs[1])
            rndColorGroup.links.new(combine5.outputs[0],vecMul3.inputs[0])
            rndColorGroup.links.new(combine6.outputs[0],vecMul4.inputs[0])
            rndColorGroup.links.new(combine7.outputs[0],vecMul5.inputs[0])
            rndColorGroup.links.new(combine8.outputs[0],vecMul6.inputs[0])
            rndColorGroup.links.new(vecMul3.outputs[0],vecAdd3.inputs[0])
            rndColorGroup.links.new(vecMul4.outputs[0],vecAdd3.inputs[1])
            rndColorGroup.links.new(vecMul5.outputs[0],vecAdd4.inputs[0])
            rndColorGroup.links.new(vecMul6.outputs[0],vecAdd4.inputs[1])
            rndColorGroup.links.new(vecAdd3.outputs[0],vecAdd5.inputs[0])
            rndColorGroup.links.new(vecAdd4.outputs[0],vecAdd5.inputs[1])
            rndColorGroup.links.new(vecAdd5.outputs[0],rndColorGroupO.inputs[0])

        rndColor = create_node(CurMat.nodes,"ShaderNodeGroup",(-750, -475), label="rndColor")
        rndColor.node_tree = rndColorGroup

        CurMat.links.new(rndColorIndex.outputs[0],rndColor.inputs[0])

        # rand
        hash12G = createHash12Group()
        hash12 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1550,-550), label="hash12")
        hash12.node_tree = hash12G
        combine9 = create_node(CurMat.nodes,"ShaderNodeCombineXYZ", (-1700,-550))
        CurMat.links.new(time.outputs[0],combine9.inputs[0])
        CurMat.links.new(time.outputs[0],combine9.inputs[1])
        CurMat.links.new(combine9.outputs[0],hash12.inputs[0])

        # rndOff
        if 'rndOff' in bpy.data.node_groups.keys():
            rndOffGroup = bpy.data.node_groups['rndOff']
        else:
            rndOffGroup = bpy.data.node_groups.new("rndOff","ShaderNodeTree") 
            rndOffGroupO = create_node(rndOffGroup.nodes, "NodeGroupOutput",(0,0)) 
            rndOffGroup.outputs.new('NodeSocketFloat','x')
            rndOffGroup.outputs.new('NodeSocketFloat','y')
            rndOffGroup.outputs.new('NodeSocketFloat','z')
            rndOffGroup.outputs.new('NodeSocketFloat','w')
            rndOffGroupO.inputs[0].default_value = -0.01
            rndOffGroupO.inputs[1].default_value = .015
            rndOffGroupO.inputs[2].default_value = -0.02
            rndOffGroupO.inputs[3].default_value = .01

        rndOff = create_node(CurMat.nodes,"ShaderNodeGroup",(-1550, -600), label="rndOff")
        rndOff.node_tree = rndOffGroup

        # randomOffset
        if 'randomOffset' in bpy.data.node_groups.keys():
            randomOffsetGroup = bpy.data.node_groups['randomOffset']
        else:
            randomOffsetGroup = bpy.data.node_groups.new("randomOffset","ShaderNodeTree")
            randomOffsetGroup.inputs.new('NodeSocketFloat','rand')
            randomOffsetGroup.inputs.new('NodeSocketFloat','rndOff.x')
            randomOffsetGroup.inputs.new('NodeSocketFloat','rndOff.y')
            randomOffsetGroup.inputs.new('NodeSocketFloat','rndOff.z')
            randomOffsetGroup.inputs.new('NodeSocketFloat','rndOff.w')
            randomOffsetGroup.outputs.new('NodeSocketVector','randomOffset')
            randomOffsetGroupI = create_node(randomOffsetGroup.nodes, "NodeGroupInput",(-400,0))
            randomOffsetGroupO = create_node(randomOffsetGroup.nodes, "NodeGroupOutput",(200,0))            
            lerp3 = create_node(randomOffsetGroup.nodes,"ShaderNodeGroup",(-200,0), label="lerp")
            lerp3.node_tree = lerpG
            lerp4 = create_node(randomOffsetGroup.nodes,"ShaderNodeGroup",(-200,-50), label="lerp")
            lerp4.node_tree = lerpG
            combine10 = create_node(randomOffsetGroup.nodes,"ShaderNodeCombineXYZ",(0,-25))
            randomOffsetGroup.links.new(randomOffsetGroupI.outputs[1],lerp3.inputs[0])
            randomOffsetGroup.links.new(randomOffsetGroupI.outputs[2],lerp3.inputs[1])
            randomOffsetGroup.links.new(randomOffsetGroupI.outputs[0],lerp3.inputs[2])
            randomOffsetGroup.links.new(randomOffsetGroupI.outputs[3],lerp4.inputs[0])
            randomOffsetGroup.links.new(randomOffsetGroupI.outputs[4],lerp4.inputs[1])
            randomOffsetGroup.links.new(randomOffsetGroupI.outputs[0],lerp4.inputs[2])
            randomOffsetGroup.links.new(lerp3.outputs[0],combine10.inputs[0])
            randomOffsetGroup.links.new(lerp4.outputs[0],combine10.inputs[1])
            randomOffsetGroup.links.new(combine10.outputs[0],randomOffsetGroupO.inputs[0])
            
        randomOffset = create_node(CurMat.nodes,"ShaderNodeGroup",(-1350, -575), label="randomOffset")
        randomOffset.node_tree = randomOffsetGroup

        CurMat.links.new(hash12.outputs[0],randomOffset.inputs[0])
        CurMat.links.new(rndOff.outputs[0],randomOffset.inputs[1])
        CurMat.links.new(rndOff.outputs[1],randomOffset.inputs[2])
        CurMat.links.new(rndOff.outputs[2],randomOffset.inputs[3])
        CurMat.links.new(rndOff.outputs[3],randomOffset.inputs[4])

        # newRandomOffset
        if 'newRandomOffset' in bpy.data.node_groups.keys():
            newRandomOffsetGroup = bpy.data.node_groups['newRandomOffset']
        else:        
            newRandomOffsetGroup = bpy.data.node_groups.new("newRandomOffset","ShaderNodeTree")
            newRandomOffsetGroup.inputs.new('NodeSocketFloat','rand')
            newRandomOffsetGroup.inputs.new('NodeSocketVector','randomOffset')
            newRandomOffsetGroup.outputs.new('NodeSocketVector','newRandomOffset')
            newRandomOffsetGroupI = create_node(newRandomOffsetGroup.nodes, "NodeGroupInput",(-800,0))
            newRandomOffsetGroupO = create_node(newRandomOffsetGroup.nodes, "NodeGroupOutput",(200,0))
            stepG = self.createStepGroup()
            step = create_node(newRandomOffsetGroup.nodes,"ShaderNodeGroup",(-200, 0), label="step")
            step.node_tree = stepG
            step.inputs[0].default_value = .7
            vecLerpG = createVecLerpGroup()
            vecLerp = create_node(newRandomOffsetGroup.nodes,"ShaderNodeGroup",(0, 0), label="lerp")
            vecLerp.node_tree = vecLerpG
            vecLerp.inputs[0].default_value = (.01,-0.01,0)
            newRandomOffsetGroup.links.new(newRandomOffsetGroupI.outputs[0],step.inputs[1])
            newRandomOffsetGroup.links.new(newRandomOffsetGroupI.outputs[1],vecLerp.inputs[1])
            newRandomOffsetGroup.links.new(step.outputs[0],vecLerp.inputs[2])
            newRandomOffsetGroup.links.new(vecLerp.outputs[0],newRandomOffsetGroupO.inputs[0])

        newRandomOffset = create_node(CurMat.nodes,"ShaderNodeGroup",(-1200, -575), label="newRandomOffset")
        newRandomOffset.node_tree = newRandomOffsetGroup
        CurMat.links.new(hash12.outputs[0],newRandomOffset.inputs[0])
        CurMat.links.new(randomOffset.outputs[0],newRandomOffset.inputs[1])

        # l1
        if 'l1' in bpy.data.node_groups.keys():
            l1Group = bpy.data.node_groups['l1']
        else:     
            l1Group = bpy.data.node_groups.new("l1","ShaderNodeTree")   

            l1Group.inputs.new('NodeSocketVector','newUV') 
            l1Group.outputs.new('NodeSocketVector','l1')    
            l1GroupI = create_node(l1Group.nodes, "NodeGroupInput",(-800,0))
            l1GroupO = create_node(l1Group.nodes, "NodeGroupOutput",(200,0))  
            separate3 = create_node(l1Group.nodes,"ShaderNodeSeparateXYZ",(-650,0))                              
            clamp2 = create_node(l1Group.nodes,"ShaderNodeClamp",(-500,25))
            clamp3 = create_node(l1Group.nodes,"ShaderNodeClamp",(-500,-25))
            combine11 = create_node(l1Group.nodes,"ShaderNodeCombineXYZ",(-350,0))   
            l1Group.links.new(l1GroupI.outputs[0],separate3.inputs[0])
            l1Group.links.new(separate3.outputs[0],clamp2.inputs[0])
            l1Group.links.new(separate3.outputs[1],clamp3.inputs[0])
            l1Group.links.new(clamp2.outputs[0],combine11.inputs[0])
            l1Group.links.new(clamp3.outputs[0],combine11.inputs[1])
            l1Group.links.new(combine11.outputs[0],l1GroupO.inputs[0])

        l1 = create_node(CurMat.nodes,"ShaderNodeGroup",(-950,300), label="l1")
        l1.node_tree = l1Group 
        CurMat.links.new(vecAdd.outputs[0],l1.inputs[0])

        # l2
        if 'l2' in bpy.data.node_groups.keys():
            l2Group = bpy.data.node_groups['l2']
        else:     
            l2Group = bpy.data.node_groups.new("l2","ShaderNodeTree")
            l2Group.inputs.new('NodeSocketVector','modUV')
            l2Group.inputs.new('NodeSocketVector','newUV')
            l2Group.inputs.new('NodeSocketFloat','l2')
            l2Group.outputs.new('NodeSocketVector','newRandomOffset')   
            l2GroupI = create_node(l2Group.nodes, "NodeGroupInput",(-800,0))
            l2GroupO = create_node(l2Group.nodes, "NodeGroupOutput",(200,0))
            vecMul7 = create_node(l2Group.nodes,"ShaderNodeVectorMath",(-600,0),operation="MULTIPLY")
            vecAdd6 = create_node(l2Group.nodes,"ShaderNodeVectorMath",(-450,0),operation="ADD")
            separate4 = create_node(l2Group.nodes,"ShaderNodeSeparateXYZ",(-300,0))  
            clamp4 = create_node(l2Group.nodes,"ShaderNodeClamp",(-150,25))
            clamp5 = create_node(l2Group.nodes,"ShaderNodeClamp",(-150,-25))
            combine12 = create_node(l2Group.nodes,"ShaderNodeCombineXYZ",(0,0))   
            l2Group.links.new(l2GroupI.outputs[0],vecMul7.inputs[0])
            l2Group.links.new(l2GroupI.outputs[2],vecMul7.inputs[1])
            l2Group.links.new(l2GroupI.outputs[1],vecAdd6.inputs[0])
            l2Group.links.new(vecMul7.outputs[0],vecAdd6.inputs[1])
            l2Group.links.new(vecAdd6.outputs[0],separate4.inputs[0])
            l2Group.links.new(separate4.outputs[0],clamp4.inputs[0])
            l2Group.links.new(separate4.outputs[1],clamp5.inputs[0])
            l2Group.links.new(clamp4.outputs[0],combine12.inputs[0])
            l2Group.links.new(clamp5.outputs[0],combine12.inputs[1])
            l2Group.links.new(combine12.outputs[0],l2GroupO.inputs[0])

        l2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-950,250), label="l2")
        l2.node_tree = l2Group 

        CurMat.links.new(vecAdd.outputs[0],l2.inputs[1])
        CurMat.links.new(combine.outputs[0],l2.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0],l2.inputs[2])

        # l3
        if 'l3' in bpy.data.node_groups.keys():
            l3Group = bpy.data.node_groups['l3']
        else:     
            l3Group = bpy.data.node_groups.new("l3","ShaderNodeTree")
            l3Group.inputs.new('NodeSocketVector','modUV')
            l3Group.inputs.new('NodeSocketVector','newUV')
            l3Group.inputs.new('NodeSocketFloat','LayersSeparation')
            l3Group.outputs.new('NodeSocketVector','l3')   
            l3GroupI = create_node(l3Group.nodes, "NodeGroupInput",(-800,0))
            l3GroupO = create_node(l3Group.nodes, "NodeGroupOutput",(300,0))
            vecMul8 = create_node(l3Group.nodes,"ShaderNodeVectorMath",(-600,0),operation="MULTIPLY")
            vecMul9 = create_node(l3Group.nodes,"ShaderNodeVectorMath",(-450,0),operation="MULTIPLY")
            vecMul9.inputs[1].default_value = (2,2,2)
            vecAdd7 = create_node(l3Group.nodes,"ShaderNodeVectorMath",(-300,0),operation="ADD")
            separate5 = create_node(l3Group.nodes,"ShaderNodeSeparateXYZ",(-150,0))  
            clamp6 = create_node(l3Group.nodes,"ShaderNodeClamp",(-0,25))
            clamp7 = create_node(l3Group.nodes,"ShaderNodeClamp",(-0,-25))
            combine13 = create_node(l3Group.nodes,"ShaderNodeCombineXYZ",(150,0)) 
            l3Group.links.new(l3GroupI.outputs[0],vecMul8.inputs[0])
            l3Group.links.new(l3GroupI.outputs[2],vecMul8.inputs[1])
            l3Group.links.new(vecMul8.outputs[0],vecMul9.inputs[0])
            l3Group.links.new(l3GroupI.outputs[1],vecAdd7.inputs[0])
            l3Group.links.new(vecMul9.outputs[0],vecAdd7.inputs[1])
            l3Group.links.new(vecAdd7.outputs[0],separate5.inputs[0])
            l3Group.links.new(separate5.outputs[0],clamp6.inputs[0])
            l3Group.links.new(separate5.outputs[1],clamp7.inputs[0])
            l3Group.links.new(clamp6.outputs[0],combine13.inputs[0])
            l3Group.links.new(clamp7.outputs[0],combine13.inputs[1])
            l3Group.links.new(combine13.outputs[0],l3GroupO.inputs[0])

        l3 = create_node(CurMat.nodes,"ShaderNodeGroup",(-950,200), label="l3")
        l3.node_tree = l3Group 

        CurMat.links.new(vecAdd.outputs[0],l3.inputs[1])
        CurMat.links.new(combine.outputs[0],l3.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0],l3.inputs[2])

        # i1

        i1 = create_node(CurMat.nodes,"ShaderNodeTexImage",(-800,300), label="i1", image=parImg)
        colorlessTexG = self.colorlessTexGroup()
        colorlessTex = create_node(CurMat.nodes,"ShaderNodeGroup",(-550,300), label="colorlessTex")
        colorlessTex.node_tree = colorlessTexG        
        CurMat.links.new(l1.outputs[0],i1.inputs[0])
        CurMat.links.new(i1.outputs[0],colorlessTex.inputs[0])


        # i2
        i2 = create_node(CurMat.nodes,"ShaderNodeTexImage",(-800,250), label="i2", image=parImg)
        CurMat.links.new(l2.outputs[0],i2.inputs[0])
        colorlessTex2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-550,250), label="colorlessTex")
        colorlessTex2.node_tree = colorlessTexG        
        CurMat.links.new(i2.outputs[0],colorlessTex2.inputs[0])

        # i3
        i3 = create_node(CurMat.nodes,"ShaderNodeTexImage",(-800,200), label="i3", image=parImg)
        CurMat.links.new(l3.outputs[0],i3.inputs[0])
        colorlessTex3 = create_node(CurMat.nodes,"ShaderNodeGroup",(-550,200), label="colorlessTex")
        colorlessTex3.node_tree = colorlessTexG        
        CurMat.links.new(i3.outputs[0],colorlessTex3.inputs[0])

        # if BlinkingSpeed > 0

        iA = create_node(CurMat.nodes,"ShaderNodeTexImage",(-800,350), label="iA", image=blinkImg)

        CurMat.links.new(l1.outputs[0],iA.inputs[0])
        
        if 'if BlinkingSpeed > 0' in bpy.data.node_groups.keys():
            bl1Group = bpy.data.node_groups['if BlinkingSpeed > 0']
        else:     
            bl1Group = bpy.data.node_groups.new("if BlinkingSpeed > 0","ShaderNodeTree")
            bl1Group.inputs.new('NodeSocketFloat','BlinkingSpeed')
            bl1Group.inputs.new('NodeSocketFloat','time')
            bl1Group.inputs.new('NodeSocketColor','iA')
            bl1Group.inputs.new('NodeSocketColor','i1')
            bl1Group.outputs.new('NodeSocketColor','new_i1')
            bl1GroupI = create_node(bl1Group.nodes, "NodeGroupInput",(-1050,0))
            bl1GroupO = create_node(bl1Group.nodes, "NodeGroupOutput",(300,0))   
            mul10 = create_node(bl1Group.nodes,"ShaderNodeMath",(-950,100),operation = "MULTIPLY")
            sin = create_node(bl1Group.nodes,"ShaderNodeMath",(-650,100),operation = "SINE")              
            mul11 = create_node(bl1Group.nodes,"ShaderNodeMath",(-500,100),operation = "MULTIPLY") 
            mul11.inputs[1].default_value = 100
            mul11.use_clamp = True
            separate6 = create_node(bl1Group.nodes,"ShaderNodeSeparateXYZ",(-500,150))
            floor3 = create_node(bl1Group.nodes,"ShaderNodeMath",(-350,150),operation = "FLOOR") 
            floor3.use_clamp = True
            vecMul10 = create_node(bl1Group.nodes,"ShaderNodeVectorMath",(-200,100),operation = "MULTIPLY") 
            vecAdd8 = create_node(bl1Group.nodes,"ShaderNodeVectorMath",(-150,50),operation = "ADD") 
            mixRGB = create_node(bl1Group.nodes,"ShaderNodeMixRGB",(200,50)) 
            bl1Group.links.new(bl1GroupI.outputs[1],mul10.inputs[0])
            bl1Group.links.new(bl1GroupI.outputs[0],mul10.inputs[1])
            bl1Group.links.new(mul10.outputs[0],sin.inputs[0])
            bl1Group.links.new(sin.outputs[0],mul11.inputs[0])
            bl1Group.links.new(bl1GroupI.outputs[2],separate6.inputs[0])
            bl1Group.links.new(separate6.outputs[0],floor3.inputs[0])
            bl1Group.links.new(bl1GroupI.outputs[3],vecMul10.inputs[0])
            bl1Group.links.new(floor3.outputs[0],vecMul10.inputs[1])
            bl1Group.links.new(vecMul10.outputs[0],vecAdd8.inputs[0])
            bl1Group.links.new(mul11.outputs[0],vecAdd8.inputs[1])

            bl1Group.links.new(vecAdd8.outputs[0],mixRGB.inputs[0])
            bl1Group.links.new(vecMul10.outputs[0],mixRGB.inputs[2])
            bl1Group.links.new(bl1GroupI.outputs[3],mixRGB.inputs[1])
            bl1Group.links.new(mixRGB.outputs[0],bl1GroupO.inputs[0])


        bl1 = create_node(CurMat.nodes,"ShaderNodeGroup",(-350,325), label="if BlinkingSpeed > 0")
        bl1.node_tree = bl1Group 
        CurMat.links.new(blinkingSpeed.outputs[0],bl1.inputs[0])
        CurMat.links.new(time.outputs[0],bl1.inputs[1])
        CurMat.links.new(iA.outputs[0],bl1.inputs[2])
        CurMat.links.new(colorlessTex.outputs[0],bl1.inputs[3])

        # scanlineUV
        if 'scanlineUV' in bpy.data.node_groups.keys():
            scanlineUVGroup = bpy.data.node_groups['scanlineUV']
        else:           
            scanlineUVGroup = bpy.data.node_groups.new("scanlineUV","ShaderNodeTree")
            scanlineUVGroup.inputs.new('NodeSocketFloat','ScanlinesDensity')
            scanlineUVGroup.inputs.new('NodeSocketFloat','time')
            scanlineUVGroup.inputs.new('NodeSocketVector','UV')
            scanlineUVGroup.outputs.new('NodeSocketVector','scanlineUV')
            scanlineUVGroupI = create_node(scanlineUVGroup.nodes, "NodeGroupInput",(-1050,0))
            scanlineUVGroupO = create_node(scanlineUVGroup.nodes, "NodeGroupOutput",(300,0))
            combine16 = create_node(scanlineUVGroup.nodes,"ShaderNodeCombineXYZ",(-900,100))
            combine16.inputs[0].default_value = 1
            vecMul11 = create_node(scanlineUVGroup.nodes,"ShaderNodeVectorMath",(-750,100),operation = "MULTIPLY")
            combine17 = create_node(scanlineUVGroup.nodes,"ShaderNodeCombineXYZ",(-900,50))
            combine17.inputs[0].default_value = 2
            combine17.inputs[1].default_value = 2
            vecMul12 = create_node(scanlineUVGroup.nodes,"ShaderNodeVectorMath",(-750,50),operation = "MULTIPLY")
            vecAdd9 = create_node(scanlineUVGroup.nodes,"ShaderNodeVectorMath",(-600,75),operation = "ADD")
            scanlineUVGroup.links.new(scanlineUVGroupI.outputs[0],combine16.inputs[1])
            scanlineUVGroup.links.new(scanlineUVGroupI.outputs[2],vecMul11.inputs[0])
            scanlineUVGroup.links.new(combine16.outputs[0],vecMul11.inputs[1])
            scanlineUVGroup.links.new(combine17.outputs[0],vecMul12.inputs[0])
            scanlineUVGroup.links.new(scanlineUVGroupI.outputs[1],vecMul12.inputs[1])
            scanlineUVGroup.links.new(vecMul11.outputs[0],vecAdd9.inputs[0])
            scanlineUVGroup.links.new(vecMul12.outputs[0],vecAdd9.inputs[1])
            scanlineUVGroup.links.new(vecAdd9.outputs[0],scanlineUVGroupO.inputs[0])

        scanlineUV = create_node(CurMat.nodes,"ShaderNodeGroup",(-950,100), label="scanlineUV")
        scanlineUV.node_tree = scanlineUVGroup 
        CurMat.links.new(scanlinesDensity.outputs[0],scanlineUV.inputs[0])
        CurMat.links.new(time.outputs[0],scanlineUV.inputs[1])
        CurMat.links.new(UVMap.outputs[0],scanlineUV.inputs[2])

        # sampledScanlines
        scanlineTexture = create_node(CurMat.nodes,"ShaderNodeTexImage",(-800,100), label="ScanlineTexture", image=scanLineImg)
        separate7 = create_node(CurMat.nodes,"ShaderNodeSeparateXYZ",(-550,100))
        CurMat.links.new(scanlineUV.outputs[0],scanlineTexture.inputs[0])
        CurMat.links.new(scanlineTexture.outputs[0],separate7.inputs[0])

        # lineMask
        lerp5 = create_node(CurMat.nodes,"ShaderNodeGroup",(-400,100), label="lerp")
        lerp5.node_tree = lerpG
        lerp5.inputs[1].default_value = 1
        CurMat.links.new(scanlinesIntensity.outputs[0],lerp5.inputs[0])
        CurMat.links.new(separate7.outputs[0],lerp5.inputs[2])

        # i1 * IntensityPerLayer.x;
        vecMul13 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-950,25),operation = "MULTIPLY")
        CurMat.links.new(bl1.outputs[0],vecMul13.inputs[0])
        CurMat.links.new(intensityPerLayer_x.outputs[0],vecMul13.inputs[1])

        # i2 * IntensityPerLayer.y * lineMask;
        vecMul14 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-950,-25),operation = "MULTIPLY")
        vecMul15 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-800,-25),operation = "MULTIPLY")
        CurMat.links.new(colorlessTex2.outputs[0],vecMul14.inputs[0])
        CurMat.links.new(intensityPerLayer_y.outputs[0],vecMul14.inputs[1])
        CurMat.links.new(vecMul14.outputs[0],vecMul15.inputs[0])
        CurMat.links.new(lerp5.outputs[0],vecMul15.inputs[1])

        # i3 * IntensityPerLayer.z * lineMask;
        vecMul16 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-950,-75),operation = "MULTIPLY")
        vecMul17 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-800,-75),operation = "MULTIPLY")
        CurMat.links.new(colorlessTex3.outputs[0],vecMul16.inputs[0])
        CurMat.links.new(intensityPerLayer_z.outputs[0],vecMul16.inputs[1])
        CurMat.links.new(vecMul16.outputs[0],vecMul17.inputs[0])
        CurMat.links.new(lerp5.outputs[0],vecMul17.inputs[1])

        # m2 = (1-(1-i3)*(1-i2));
        if 'm2' in bpy.data.node_groups.keys():
            m2Group = bpy.data.node_groups['m2']
        else:           
            m2Group = bpy.data.node_groups.new("m2","ShaderNodeTree")
            m2Group.inputs.new('NodeSocketVector','i3')
            m2Group.inputs.new('NodeSocketVector','i2')
            m2Group.outputs.new('NodeSocketVector','m2')
            m2GroupI = create_node(m2Group.nodes, "NodeGroupInput",(-1050,0))
            m2GroupO = create_node(m2Group.nodes, "NodeGroupOutput",(300,0))
            vecSub2 =  create_node(m2Group.nodes,"ShaderNodeVectorMath",(-900,25),operation = "SUBTRACT")
            vecSub2.inputs[0].default_value = (1,1,1)
            vecSub3 =  create_node(m2Group.nodes,"ShaderNodeVectorMath",(-900,-25),operation = "SUBTRACT")
            vecSub3.inputs[0].default_value = (1,1,1)
            vecMul18 = create_node(m2Group.nodes,"ShaderNodeVectorMath",(-750,0),operation = "MULTIPLY")
            vecSub4 =  create_node(m2Group.nodes,"ShaderNodeVectorMath",(-600,0),operation = "SUBTRACT")
            vecSub4.inputs[0].default_value = (1,1,1)
            m2Group.links.new(m2GroupI.outputs[0],vecSub2.inputs[1])
            m2Group.links.new(m2GroupI.outputs[1],vecSub3.inputs[1])
            m2Group.links.new(vecSub2.outputs[0],vecMul18.inputs[0])
            m2Group.links.new(vecSub3.outputs[0],vecMul18.inputs[1])
            m2Group.links.new(vecMul18.outputs[0],vecSub4.inputs[1])
            m2Group.links.new(vecSub4.outputs[0],m2GroupO.inputs[0])

        m2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-650,-25), label="m2")
        m2.node_tree = m2Group
        CurMat.links.new(vecMul17.outputs[0],m2.inputs[0])
        CurMat.links.new(vecMul15.outputs[0],m2.inputs[1])

        # m3 = (1-(1-m2)*(1-i1));
        if 'm3' in bpy.data.node_groups.keys():
            m3Group = bpy.data.node_groups['m3']
        else:           
            m3Group = bpy.data.node_groups.new("m3","ShaderNodeTree")
            m3Group.inputs.new('NodeSocketVector','m2')
            m3Group.inputs.new('NodeSocketVector','i1')    
            m3Group.outputs.new('NodeSocketVector','m3')
            m3GroupI = create_node(m3Group.nodes, "NodeGroupInput",(-1050,0))
            m3GroupO = create_node(m3Group.nodes, "NodeGroupOutput",(300,0))   
            vecSub5 =  create_node(m3Group.nodes,"ShaderNodeVectorMath",(-900,25),operation = "SUBTRACT")
            vecSub5.inputs[0].default_value = (1,1,1)
            vecSub6 =  create_node(m3Group.nodes,"ShaderNodeVectorMath",(-900,-25),operation = "SUBTRACT")
            vecSub6.inputs[0].default_value = (1,1,1)
            vecMul19 = create_node(m3Group.nodes,"ShaderNodeVectorMath",(-750,0),operation = "MULTIPLY")
            vecSub7 =  create_node(m3Group.nodes,"ShaderNodeVectorMath",(-600,0),operation = "SUBTRACT")
            vecSub7.inputs[0].default_value = (1,1,1)
            m3Group.links.new(m3GroupI.outputs[0],vecSub5.inputs[1])
            m3Group.links.new(m3GroupI.outputs[1],vecSub6.inputs[1])
            m3Group.links.new(vecSub5.outputs[0],vecMul19.inputs[0])
            m3Group.links.new(vecSub6.outputs[0],vecMul19.inputs[1])
            m3Group.links.new(vecMul19.outputs[0],vecSub7.inputs[1])
            m3Group.links.new(vecSub7.outputs[0],m3GroupO.inputs[0])
        m3 = create_node(CurMat.nodes,"ShaderNodeGroup",(-500,-25), label="m3")
        m3.node_tree = m3Group 
        CurMat.links.new(m2.outputs[0],m3.inputs[0])
        CurMat.links.new(vecMul13.outputs[0],m3.inputs[1])

        # position of glitches
        separate8 = create_node(CurMat.nodes,"ShaderNodeSeparateXYZ", (-1150,-125))
        greaterThan = create_node(CurMat.nodes,"ShaderNodeMath", (-950,-125),operation="GREATER_THAN")
        greaterThan.inputs[1].default_value = .02
        lessThan = create_node(CurMat.nodes,"ShaderNodeMath", (-950,-175),operation="LESS_THAN")
        lessThan.inputs[1].default_value = .12
        minimum = create_node(CurMat.nodes,"ShaderNodeMath", (-800,-150),operation="MINIMUM")
        greaterThan2 = create_node(CurMat.nodes,"ShaderNodeMath", (-950,-225),operation="GREATER_THAN")
        greaterThan2.inputs[1].default_value = .28
        lessThan2 = create_node(CurMat.nodes,"ShaderNodeMath", (-950,-275),operation="LESS_THAN")
        lessThan2.inputs[1].default_value = .543
        minimum2 = create_node(CurMat.nodes,"ShaderNodeMath", (-800,-250),operation="MINIMUM")
        greaterThan3 = create_node(CurMat.nodes,"ShaderNodeMath", (-950,-325),operation="GREATER_THAN")
        greaterThan3.inputs[1].default_value = .78
        lessThan3 = create_node(CurMat.nodes,"ShaderNodeMath", (-950,-375),operation="LESS_THAN")
        lessThan3.inputs[1].default_value = .85
        minimum3 = create_node(CurMat.nodes,"ShaderNodeMath", (-800, -350),operation="MINIMUM")
        add10 = create_node(CurMat.nodes,"ShaderNodeMath", (-650,-200),operation="ADD")
        add11 = create_node(CurMat.nodes,"ShaderNodeMath", (-650,-300),operation="ADD")
        mixRGB2 = create_node(CurMat.nodes,"ShaderNodeMixRGB",(-600, -475)) 
        mixRGB2.inputs[1].default_value = (0,0,0,0)
        CurMat.links.new(UVMap.outputs[0],separate8.inputs[0])
        CurMat.links.new(separate8.outputs[0],greaterThan.inputs[0])
        CurMat.links.new(separate8.outputs[0],lessThan.inputs[0])
        CurMat.links.new(greaterThan.outputs[0],minimum.inputs[0])
        CurMat.links.new(lessThan.outputs[0],minimum.inputs[1])
        CurMat.links.new(separate8.outputs[0],greaterThan2.inputs[0])
        CurMat.links.new(separate8.outputs[0],lessThan2.inputs[0])
        CurMat.links.new(greaterThan2.outputs[0],minimum2.inputs[0])
        CurMat.links.new(lessThan2.outputs[0],minimum2.inputs[1])
        CurMat.links.new(separate8.outputs[0],greaterThan3.inputs[0])
        CurMat.links.new(separate8.outputs[0],lessThan3.inputs[0])
        CurMat.links.new(greaterThan3.outputs[0],minimum3.inputs[0])
        CurMat.links.new(lessThan3.outputs[0],minimum3.inputs[1])
        CurMat.links.new(minimum.outputs[0],add10.inputs[0])
        CurMat.links.new(minimum2.outputs[0],add10.inputs[1])
        CurMat.links.new(add10.outputs[0],add11.inputs[0])
        CurMat.links.new(minimum3.outputs[0],add11.inputs[1])
        CurMat.links.new(rndColor.outputs[0],mixRGB2.inputs[2])
        CurMat.links.new(add11.outputs[0],mixRGB2.inputs[0])
        
        # connect glitches with texture
        parTex = create_node(CurMat.nodes,"ShaderNodeTexImage",(-900, -525), label="ParalaxTexture", image=parImg)
        CurMat.links.new(brokenUV.outputs[0],parTex.inputs[0])
        colorlessTex4 = create_node(CurMat.nodes,"ShaderNodeGroup",(-650, -525), label="colorlessTex")
        colorlessTex4.node_tree = colorlessTexG        
        CurMat.links.new(parTex.outputs[0],colorlessTex4.inputs[0])
        vecMul20 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-500, -550),operation="MULTIPLY")
        CurMat.links.new(mixRGB2.outputs[0],vecMul20.inputs[0])
        CurMat.links.new(colorlessTex4.outputs[0],vecMul20.inputs[1])

        parTex2 = create_node(CurMat.nodes,"ShaderNodeTexImage",(-900, -575), label="ParalaxTexture", image=parImg)
        colorlessTex6 = create_node(CurMat.nodes,"ShaderNodeGroup",(-650, -575), label="colorlessTex")
        colorlessTex6.node_tree = colorlessTexG        
        CurMat.links.new(parTex2.outputs[0],colorlessTex6.inputs[0])
        vecAdd10 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-1050, -575),operation="ADD")
        vecMul21 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-500, -600),operation="MULTIPLY")
        vecMul21.inputs[0].default_value = (.4,.4,.4)
        vecAdd11 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-350, -512.5),operation="ADD")

        CurMat.links.new(vecAdd.outputs[0],vecAdd10.inputs[0])
        CurMat.links.new(newRandomOffset.outputs[0],vecAdd10.inputs[1])
        CurMat.links.new(vecAdd10.outputs[0],parTex2.inputs[0])
        CurMat.links.new(colorlessTex6.outputs[0],vecMul21.inputs[1])
        CurMat.links.new(vecMul20.outputs[0],vecAdd11.inputs[0])
        CurMat.links.new(vecMul21.outputs[0],vecAdd11.inputs[1])

        # if isBroken > 0
        mixRGB3 = create_node(CurMat.nodes,"ShaderNodeMixRGB",(-350,-25))
        mixRGB4 = create_node(CurMat.nodes,"ShaderNodeMixRGB",(-350,-75))
        CurMat.links.new(isBroken.outputs[0],mixRGB3.inputs[0])
        CurMat.links.new(m3.outputs[0],mixRGB3.inputs[1])
        CurMat.links.new(vecAdd11.outputs[0],mixRGB3.inputs[2])
        CurMat.links.new(add11.outputs[0],mixRGB4.inputs[0])
        CurMat.links.new(m3.outputs[0],mixRGB4.inputs[1])
        CurMat.links.new(mixRGB3.outputs[0],mixRGB4.inputs[2])

        # scrollMask
        scrollMask = create_node(CurMat.nodes,"ShaderNodeTexImage",(-1700, -650), label="ScrollMaskTexture", image=scrollMaskImg)
        CurMat.links.new(l1.outputs[0],scrollMask.inputs[0])
        # finalScrollUV
        if 'finalScrollUV' in bpy.data.node_groups.keys():
            finalScrollUVGroup = bpy.data.node_groups['finalScrollUV']
        else:           
            finalScrollUVGroup = bpy.data.node_groups.new("finalScrollUV","ShaderNodeTree")
            finalScrollUVGroup.inputs.new('NodeSocketVector','scrollUV2')
            finalScrollUVGroup.inputs.new('NodeSocketVector','scrollUV1')   
            finalScrollUVGroup.inputs.new('NodeSocketColor','scrollMask')  
            finalScrollUVGroup.inputs.new('NodeSocketVector','scrollUV2X')
            finalScrollUVGroup.inputs.new('NodeSocketVector','scrollUV1X')
            finalScrollUVGroup.inputs.new('NodeSocketVector','ScrollVerticalOrHorizontal')
            finalScrollUVGroup.outputs.new('NodeSocketVector','finalScrollUV')   
            finalScrollUVGroupI = create_node(finalScrollUVGroup.nodes, "NodeGroupInput",(-1050,0))
            finalScrollUVGroupO = create_node(finalScrollUVGroup.nodes, "NodeGroupOutput",(-150,0))   
            vecLerp2 = create_node(finalScrollUVGroup.nodes,"ShaderNodeGroup",(-750, 0), label="lerp")
            vecLerp2.node_tree = vecLerpG 
            separate9 = create_node(finalScrollUVGroup.nodes,"ShaderNodeSeparateXYZ",(-900, -50))
            vecLerp3 = create_node(finalScrollUVGroup.nodes,"ShaderNodeGroup",(-750, -100), label="lerp")
            vecLerp3.node_tree = vecLerpG  
            vecLerp4 = create_node(finalScrollUVGroup.nodes,"ShaderNodeGroup",(-600, 0), label="lerp")
            vecLerp4.node_tree = vecLerpG                      
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs[0],vecLerp2.inputs[0])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs[1],vecLerp2.inputs[1])
            finalScrollUVGroup.links.new(separate9.outputs[0],vecLerp2.inputs[2])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs[2],separate9.inputs[0])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs[3],vecLerp3.inputs[0])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs[4],vecLerp3.inputs[1])
            finalScrollUVGroup.links.new(separate9.outputs[0],vecLerp3.inputs[2])
            finalScrollUVGroup.links.new(vecLerp2.outputs[0],vecLerp4.inputs[0])
            finalScrollUVGroup.links.new(vecLerp3.outputs[0],vecLerp4.inputs[1])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs[5],vecLerp4.inputs[2])
            finalScrollUVGroup.links.new(vecLerp4.outputs[0],finalScrollUVGroupO.inputs[0])


        finalScrollUV = create_node(CurMat.nodes,"ShaderNodeGroup",(-1350, -650), label="finalScrollUV")
        finalScrollUV.node_tree = finalScrollUVGroup
        CurMat.links.new(scrollUV2.outputs[0],finalScrollUV.inputs[0])
        CurMat.links.new(scrollUV1.outputs[0],finalScrollUV.inputs[1])
        CurMat.links.new(scrollMask.outputs[0],finalScrollUV.inputs[2])
        CurMat.links.new(scrollUV2X.outputs[0],finalScrollUV.inputs[3])
        CurMat.links.new(scrollUV1X.outputs[0],finalScrollUV.inputs[4])
        CurMat.links.new(scrollVerticalOrHorizontal.outputs[0],finalScrollUV.inputs[5])

        # scrollTex
        scrollTex = create_node(CurMat.nodes,"ShaderNodeTexImage",(-1200, -650), label="ParalaxTexture", image=parImg)
        CurMat.links.new(finalScrollUV.outputs[0],scrollTex.inputs[0])
        colorlessTex5 = create_node(CurMat.nodes,"ShaderNodeGroup",(-950, -650), label="colorlessTex")
        colorlessTex5.node_tree = colorlessTexG        
        CurMat.links.new(scrollTex.outputs[0],colorlessTex5.inputs[0])

        # lerp(m3, scrollTex, ( scrollMask.x + scrollMask.y))
        separate10 = create_node(CurMat.nodes,"ShaderNodeSeparateXYZ",(-1350, -700))
        add3 = create_node(CurMat.nodes,"ShaderNodeMath",(-1200, -700),operation= "ADD")
        vecLerpG = createVecLerpGroup()
        vecLerp2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-800, -650), label="lerp")
        vecLerp2.node_tree = vecLerpG 
        CurMat.links.new(scrollMask.outputs[0],separate10.inputs[0])
        CurMat.links.new(separate10.outputs[0],add3.inputs[0])
        CurMat.links.new(separate10.outputs[1],add3.inputs[1])
        CurMat.links.new(mixRGB4.outputs[0],vecLerp2.inputs[0])
        CurMat.links.new(colorlessTex5.outputs[0],vecLerp2.inputs[1])
        CurMat.links.new(add3.outputs[0],vecLerp2.inputs[2])

        # m3*clamp(Emissive) * EmissiveColor
        clamp8 = create_node(CurMat.nodes,"ShaderNodeClamp",(-800, -750))
        vecMul22 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-650, -675),operation="MULTIPLY")
        vecMul23 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-500, -675),operation="MULTIPLY")
        CurMat.links.new(emissive.outputs[0],clamp8.inputs[0])
        CurMat.links.new(vecLerp2.outputs[0],vecMul22.inputs[0])
        CurMat.links.new(clamp8.outputs[0],vecMul22.inputs[1])
        CurMat.links.new(vecMul22.outputs[0],vecMul23.inputs[0])
        CurMat.links.new(emissiveColor.outputs[0],vecMul23.inputs[1])

        # HSV
        separateHSV = create_node(CurMat.nodes,"ShaderNodeSeparateHSV",(-1350, -800))
        combine18 = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",(-1350, -850))
        combine18.inputs[0].default_value = 1
        combine18.inputs[2].default_value = 1
        combine19 = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",(-1200, -800))
        vecMul24 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-1050, -800),operation="MULTIPLY")
        combine20 = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",(-1050, -850))
        vecAdd12 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-900, -800),operation="ADD")
        separate11 = create_node(CurMat.nodes,"ShaderNodeSeparateXYZ",(-750, -800))
        combineHSV = create_node(CurMat.nodes,"ShaderNodeCombineHSV",(-600, -800))
        CurMat.links.new(vecMul23.outputs[0],separateHSV.inputs[0])
        CurMat.links.new(HSV_Mod_y.outputs[0],combine18.inputs[1])
        CurMat.links.new(separateHSV.outputs[0],combine19.inputs[0])
        CurMat.links.new(separateHSV.outputs[1],combine19.inputs[1])
        CurMat.links.new(separateHSV.outputs[2],combine19.inputs[2])
        CurMat.links.new(combine18.outputs[0],vecMul24.inputs[1])
        CurMat.links.new(combine19.outputs[0],vecMul24.inputs[0])
        CurMat.links.new(HSV_Mod_x.outputs[0],combine20.inputs[0])
        CurMat.links.new(vecMul24.outputs[0],vecAdd12.inputs[0])
        CurMat.links.new(combine20.outputs[0],vecAdd12.inputs[1])
        CurMat.links.new(vecAdd12.outputs[0],separate11.inputs[0])
        CurMat.links.new(separate11.outputs[0],combineHSV.inputs[0])
        CurMat.links.new(separate11.outputs[1],combineHSV.inputs[1])
        CurMat.links.new(separate11.outputs[2],combineHSV.inputs[2])

        # bright
        separate12 = create_node(CurMat.nodes,"ShaderNodeSeparateXYZ",(-1350, -900))
        maximum = create_node(CurMat.nodes,"ShaderNodeMath",(-1200, -886.5),operation="MAXIMUM")
        maximum2 = create_node(CurMat.nodes,"ShaderNodeMath",(-1050, -913.5),operation="MAXIMUM")
        CurMat.links.new(combineHSV.outputs[0],separate12.inputs[0])
        CurMat.links.new(separate12.outputs[0],maximum.inputs[0])
        CurMat.links.new(separate12.outputs[1],maximum.inputs[1])
        CurMat.links.new(maximum.outputs[0],maximum2.inputs[0])
        CurMat.links.new(separate12.outputs[2],maximum2.inputs[1])

        # clamp(bright * 0.75f)
        mul12 = create_node(CurMat.nodes,"ShaderNodeMath",(-900, -900),operation="MULTIPLY")
        mul12.use_clamp = True
        mul12.inputs[1].default_value = .75
        CurMat.links.new(maximum2.outputs[0],mul12.inputs[0])

        # lerp((0, 0, 0),(0.03, 0.03, 0.03) * (1.0 - bright),FixForBlack)
        sub = create_node(CurMat.nodes,"ShaderNodeMath",(-750, -900),operation="SUBTRACT")
        sub.inputs[0].default_value = 1
        combine21 = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",(-750, -850))
        vecLerp5 = create_node(CurMat.nodes,"ShaderNodeGroup",(-450, -900), label="lerp")
        vecLerp5.node_tree = vecLerpG
        combine22 = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",(-750, -950))
        combine22.inputs[0].default_value = .03
        combine22.inputs[1].default_value = .03
        combine22.inputs[2].default_value = .03
        vecMul25 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-600, -900),operation="MULTIPLY")
        vecAdd13 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-300, -900),operation="ADD")


        CurMat.links.new(mul12.outputs[0],sub.inputs[1])
        
        CurMat.links.new(sub.outputs[0],vecMul25.inputs[0])
        CurMat.links.new(combine22.outputs[0],vecMul25.inputs[1])
        CurMat.links.new(combine21.outputs[0],vecLerp5.inputs[0])
        CurMat.links.new(vecMul25.outputs[0],vecLerp5.inputs[1])
        CurMat.links.new(fixForBlack.outputs[0],vecLerp5.inputs[2])
        CurMat.links.new(combineHSV.outputs[0],vecAdd13.inputs[0])
        CurMat.links.new(vecLerp5.outputs[0],vecAdd13.inputs[1])

        # links to pBSDF
        CurMat.links.new(vecAdd13.outputs[0],pBSDF.inputs["Base Color"])
        CurMat.links.new(vecAdd13.outputs[0],pBSDF.inputs["Emission"])

        # metalness
        CurMat.links.new(roughness.outputs[0],pBSDF.inputs["Metallic"])

        # roughness
        CurMat.links.new(metalness.outputs[0],pBSDF.inputs["Roughness"])