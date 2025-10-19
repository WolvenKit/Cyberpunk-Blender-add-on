import bpy
import os
from ..main.common import *


class ParallaxScreenTransparent:
    def __init__(self, BasePath,image_format,ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def createScanlinesGroup(self):
        if 'scanlines' in bpy.data.node_groups.keys():
            stepGroup = bpy.data.node_groups['scanlines']
            return stepGroup
        else:
            scanlinesGroup = bpy.data.node_groups.new("scanlines","ShaderNodeTree")
            vers=bpy.app.version
            if vers[0]<4:
                scanlinesGroup.inputs.new('NodeSocketFloat','density')
                scanlinesGroup.inputs.new('NodeSocketFloat','uv')
                scanlinesGroup.outputs.new('NodeSocketFloat','result')
            else:
                scanlinesGroup.interface.new_socket(name="density", socket_type='NodeSocketFloat', in_out='INPUT')
                scanlinesGroup.interface.new_socket(name="uv", socket_type='NodeSocketFloat', in_out='INPUT')
                scanlinesGroup.interface.new_socket(name="result", socket_type='NodeSocketFloat', in_out='OUTPUT')

            scanlinesGroupI = create_node(scanlinesGroup.nodes, "NodeGroupInput",(-1400,0))
            scanlinesGroupO = create_node(scanlinesGroup.nodes, "NodeGroupOutput",(-200,0))
            mul = create_node(scanlinesGroup.nodes, "ShaderNodeMath",(-1200,0),operation="MULTIPLY")
            cos = create_node(scanlinesGroup.nodes, "ShaderNodeMath",(-1000,0),operation="COSINE")
            div = create_node(scanlinesGroup.nodes, "ShaderNodeMath",(-800,0),operation="DIVIDE")
            div.inputs[1].default_value = 2
            add = create_node(scanlinesGroup.nodes, "ShaderNodeMath",(-800,0))
            add.inputs[1].default_value = 1
            scanlinesGroup.links.new(scanlinesGroupI.outputs[0],mul.inputs[1])
            scanlinesGroup.links.new(scanlinesGroupI.outputs[1],mul.inputs[0])
            scanlinesGroup.links.new(mul.outputs[0],cos.inputs[0])
            scanlinesGroup.links.new(cos.outputs[0],add.inputs[0])
            scanlinesGroup.links.new(add.outputs[0],div.inputs[0])
            scanlinesGroup.links.new(div.outputs[0],scanlinesGroupO.inputs[0])

            return scanlinesGroup

    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        vers=bpy.app.version
        pBSDF=CurMat.nodes[loc('Principled BSDF')]
        sockets=bsdf_socket_names()
        pBSDF.inputs[sockets['Specular']].default_value = 0

        # PARAMETERS
        if "SeparateLayersFromTexture" in Data:
            separateLayersFromTex = CreateShaderNodeValue(CurMat,Data["SeparateLayersFromTexture"],-2000, 500,
                                                          "SeparateLayersFromTexture")

        if "LayersSeparation" in Data:
            layersSeparation = CreateShaderNodeValue(CurMat,Data["LayersSeparation"],-2000, 650,"LayersSeparation")

        if "LayersScrollSpeed" in Data:
            layersScrollSpeed_x = CreateShaderNodeValue(CurMat,Data["LayersScrollSpeed"]["X"],-2000, 450,
                                                        "LayersScrollSpeed.x")
            layersScrollSpeed_y = CreateShaderNodeValue(CurMat,Data["LayersScrollSpeed"]["Y"],-2000, 500,
                                                        "LayersScrollSpeed.y")
            layersScrollSpeed_z = CreateShaderNodeValue(CurMat,Data["LayersScrollSpeed"]["Z"],-2000, 550,
                                                        "LayersScrollSpeed.z")
            layersScrollSpeed_w = CreateShaderNodeValue(CurMat,Data["LayersScrollSpeed"]["W"],-2000, 600,
                                                        "LayersScrollSpeed.w")
            
        if "ScanlinesSpeed" in Data:
            scanlinesSpeed = CreateShaderNodeValue(CurMat,Data["ScanlinesSpeed"],-2000, 150,"ScanlinesSpeed")

        if "TilesWidth" in Data:
            tilesW = CreateShaderNodeValue(CurMat,Data["TilesWidth"],-2000, 100,"TilesWidth")

        if "TilesHeight" in Data:
            tilesH = CreateShaderNodeValue(CurMat,Data["TilesHeight"],-2000, 50,"TilesHeight")

        if "PlaySpeed" in Data:
            playSpeed = CreateShaderNodeValue(CurMat,Data["PlaySpeed"],-2000, 0,"PlaySpeed")

        if "InterlaceLines" in Data:
            iLines = CreateShaderNodeValue(CurMat,Data["InterlaceLines"],-2000, -100,"InterlaceLines")

        if "TextureOffsetX" in Data:
            textureOffsetX = CreateShaderNodeValue(CurMat,Data["TextureOffsetX"],-2000, -150,"TextureOffsetX")

        if "TextureOffsetY" in Data:
            textureOffsetY = CreateShaderNodeValue(CurMat,Data["TextureOffsetY"],-2000, -200,"TextureOffsetY")

        if "ImageScale" in Data:
            imageScale_x = CreateShaderNodeValue(CurMat,Data["ImageScale"]["X"],-2000, -250,"ImageScale.x")
            imageScale_y = CreateShaderNodeValue(CurMat,Data["ImageScale"]["Y"],-2000, -300,"ImageScale.y")

        if "ScrollSpeed1" in Data:
            scrollSpeed1 = CreateShaderNodeValue(CurMat,Data["ScrollSpeed1"],-2000, -350,"ScrollSpeed1")

        if "ScrollStepFactor1" in Data:
            scrollStepFactor1 = CreateShaderNodeValue(CurMat,Data["ScrollStepFactor1"],-2000, -400,"ScrollStepFactor1")  

        if "ScrollMaskHeight1" in Data:
            scrollMaskHeight1 = CreateShaderNodeValue(CurMat,Data["ScrollMaskHeight1"],-2000, -450,"ScrollMaskHeight1")  

        if "ScrollMaskStartPoint1" in Data:
            scrollMaskStartPoint1 = CreateShaderNodeValue(CurMat,Data["ScrollMaskStartPoint1"],-2000, -500,"ScrollMaskStartPoint1")  

        if "ScrollSpeed2" in Data:
            scrollSpeed2 = CreateShaderNodeValue(CurMat,Data["ScrollSpeed2"],-2000, -550,"ScrollSpeed2")

        if "ScrollStepFactor2" in Data:
            scrollStepFactor2 = CreateShaderNodeValue(CurMat,Data["ScrollStepFactor2"],-2000, -600,"ScrollStepFactor2")  

        if "ScrollMaskHeight2" in Data:
            scrollMaskHeight2 = CreateShaderNodeValue(CurMat,Data["ScrollMaskHeight2"],-2000, -650,"ScrollMaskHeight2")  

        if "ScrollMaskStartPoint2" in Data:
            scrollMaskStartPoint2 = CreateShaderNodeValue(CurMat,Data["ScrollMaskStartPoint2"],-2000, -700,"ScrollMaskStartPoint2")  

        if "ScrollVerticalOrHorizontal" in Data:
            scrollVerticalOrHorizontal = CreateShaderNodeValue(CurMat,Data["ScrollVerticalOrHorizontal"],
                                                               -2000, -750,"ScrollVerticalOrHorizontal")
        
        if "IntensityPerLayer" in Data:
            intensityPerLayer_x = CreateShaderNodeValue(CurMat,Data["IntensityPerLayer"]["X"],-2000, -800,"IntensityPerLayer.x")  
            intensityPerLayer_y = CreateShaderNodeValue(CurMat,Data["IntensityPerLayer"]["Y"],-2000, -850,"IntensityPerLayer.y")  
            intensityPerLayer_z = CreateShaderNodeValue(CurMat,Data["IntensityPerLayer"]["Z"],-2000, -900,"IntensityPerLayer.z")  
            intensityPerLayer_w = CreateShaderNodeValue(CurMat,Data["IntensityPerLayer"]["W"],-2000, -950,"IntensityPerLayer.w")  

        if "ScanlinesIntensity" in Data:
            scanlinesIntensity = CreateShaderNodeValue(CurMat,Data["ScanlinesIntensity"],-2000, -1000,"ScanlinesIntensity")  

        if "ScanlinesDensity" in Data:
            scanlinesDensity = CreateShaderNodeValue(CurMat,Data["ScanlinesDensity"],-2000, -1050,"ScanlinesDensity")  

        if "Emissive" in Data:
            emissive = CreateShaderNodeValue(CurMat,Data["Emissive"],-2000, -1100,"Emissive")  

        if "TexHSVControl" in Data:
            texHSVControl_x = CreateShaderNodeValue(CurMat,Data["TexHSVControl"]["X"],-2000, -1150,"TexHSVControl.x")  
            texHSVControl_y = CreateShaderNodeValue(CurMat,Data["TexHSVControl"]["Y"],-2000, -1200,"TexHSVControl.y")  
            texHSVControl_z = CreateShaderNodeValue(CurMat,Data["TexHSVControl"]["Z"],-2000, -1250,"TexHSVControl.z")  

        if "Color" in Data:
            color = CreateShaderNodeRGB(CurMat,Data["Color"],-2000, -1300,"Color")
            color_a = CreateShaderNodeValue(CurMat,Data["Color"]["Alpha"]/255,-2000, -1350,"Color.a")  

        if "EdgesMask" in Data:
            edgesMaskValue = CreateShaderNodeValue(CurMat,Data["EdgesMask"],-2000, -1400,"EdgesMask")  

        if "ScrollMaskTexture" in Data:
            scrollMaskImg=imageFromRelPath(Data["ScrollMaskTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.image_format)

        if "ParalaxTexture" in Data:
            parImg=imageFromRelPath(Data["ParalaxTexture"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.image_format)

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

        # topDownDot float topDownDot = -1.0f * dot(viewVector,worldBinormal);
        vecDot2 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-1500,150), operation= "DOT_PRODUCT")
        vecMul = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-1350,150), operation= "MULTIPLY")
        vecMul.inputs[0].default_value = (-1,-1,-1)
        CurMat.links.new(geometry.outputs[4], vecDot2.inputs[0])
        CurMat.links.new(vecCross.outputs[0], vecDot2.inputs[1])
        CurMat.links.new(vecDot2.outputs["Value"], vecMul.inputs[1])

        # modUV
        combine = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",(-1200,175))
        CurMat.links.new(vecDot.outputs["Value"], combine.inputs[0])
        CurMat.links.new(vecMul.outputs[0], combine.inputs[1])

        # time node
        time = CreateShaderNodeValue(CurMat,1,-2000, -50,"Time")
        timeDriver = time.outputs[0].driver_add("default_value")
        timeDriver.driver.expression = "frame / 24" #FIXME: frame / framerate variable

        # vector lerp group
        vecLerpG = createVecLerpGroup()

        # gamma node to color
        gamma = create_node(CurMat.nodes,"ShaderNodeGamma", (-1800, -1300))
        gamma.inputs[1].default_value = 2
        CurMat.links.new(color.outputs[0], gamma.inputs[0])

        # n
        if 'n_ps_t' in bpy.data.node_groups.keys():
            ngroup = bpy.data.node_groups['n_ps_t']
        else:
            ngroup = bpy.data.node_groups.new("n_ps_t","ShaderNodeTree")   
            if vers[0]<4:
                ngroup.inputs.new('NodeSocketFloat','TilesWidth')
                ngroup.inputs.new('NodeSocketFloat','TilesHeight')
                ngroup.inputs.new('NodeSocketFloat','PlaySpeed')
                ngroup.inputs.new('NodeSocketFloat','Time')
                ngroup.outputs.new('NodeSocketFloat','n')
            else:
                ngroup.interface.new_socket(name="TilesWidth", socket_type='NodeSocketFloat', in_out='INPUT')
                ngroup.interface.new_socket(name="TilesHeight", socket_type='NodeSocketFloat', in_out='INPUT')
                ngroup.interface.new_socket(name="PlaySpeed", socket_type='NodeSocketFloat', in_out='INPUT')
                ngroup.interface.new_socket(name="Time", socket_type='NodeSocketFloat', in_out='INPUT')
                ngroup.interface.new_socket(name="n", socket_type='NodeSocketFloat', in_out='OUTPUT')
            GroupInput = create_node(ngroup.nodes, "NodeGroupInput",(-1400,0))
            GroupOutput = create_node(ngroup.nodes, "NodeGroupOutput",(200,0))
            mul = create_node(ngroup.nodes,"ShaderNodeMath", (-1000,0) , operation = 'MULTIPLY')
            div = create_node(ngroup.nodes,"ShaderNodeMath", (-850,0) , operation = 'DIVIDE')
            mul1 = create_node(ngroup.nodes,"ShaderNodeMath", (-700,0) , operation = 'MULTIPLY')
            frac = create_node(ngroup.nodes,"ShaderNodeMath", (-550,0) , operation = 'FRACT')  
            mul2 = create_node(ngroup.nodes,"ShaderNodeMath", (-400,0) , operation = 'MULTIPLY')
            mul3 = create_node(ngroup.nodes,"ShaderNodeMath", (-250,0) , operation = 'MULTIPLY')
                
            ngroup.links.new(GroupInput.outputs['TilesWidth'],mul.inputs[0])
            ngroup.links.new(GroupInput.outputs['TilesHeight'],mul.inputs[1])
            ngroup.links.new(GroupInput.outputs['PlaySpeed'],div.inputs[0])
            ngroup.links.new(mul.outputs[0],div.inputs[1])
            ngroup.links.new(GroupInput.outputs['Time'],mul1.inputs[0])
            ngroup.links.new(div.outputs[0],mul1.inputs[1])
            ngroup.links.new(mul1.outputs[0],frac.inputs[0])
            ngroup.links.new(frac.outputs[0],mul2.inputs[0])
            ngroup.links.new(GroupInput.outputs['TilesWidth'],mul2.inputs[1])
            ngroup.links.new(mul2.outputs[0],mul3.inputs[0])
            ngroup.links.new(GroupInput.outputs['TilesHeight'],mul3.inputs[1])
            ngroup.links.new(mul3.outputs[0],GroupOutput.inputs[0])
            
        n = create_node(CurMat.nodes,"ShaderNodeGroup",(-1700, 75), label="n_ps_t")
        n.node_tree = ngroup

        CurMat.links.new(tilesW.outputs[0],n.inputs[0])
        CurMat.links.new(tilesH.outputs[0],n.inputs[1])
        CurMat.links.new(playSpeed.outputs[0],n.inputs[2])
        CurMat.links.new(time.outputs[0],n.inputs[3])

        # frameAdd	
        if 'frameAdd_ps_t' in bpy.data.node_groups.keys():
            frameGroup = bpy.data.node_groups['frameAdd_ps_t']
        else:
            frameGroup = bpy.data.node_groups.new("frameAdd_ps_t","ShaderNodeTree") 
            if vers[0]<4:
                frameGroup.inputs.new('NodeSocketVector','UV')
                frameGroup.inputs.new('NodeSocketFloat','n')
                frameGroup.inputs.new('NodeSocketFloat','InterlaceLines')
                frameGroup.outputs.new('NodeSocketFloat','frameAdd')
            else:
                frameGroup.interface.new_socket(name="UV", socket_type='NodeSocketVector', in_out='INPUT')
                frameGroup.interface.new_socket(name="n", socket_type='NodeSocketFloat', in_out='INPUT')
                frameGroup.interface.new_socket(name="InterlaceLines", socket_type='NodeSocketFloat', in_out='INPUT')
                frameGroup.interface.new_socket(name="frameAdd", socket_type='NodeSocketFloat', in_out='OUTPUT')
            fGroupInput = create_node(frameGroup.nodes, "NodeGroupInput",(-1400,0))
            fGroupOutput = create_node(frameGroup.nodes, "NodeGroupOutput",(200,0))

            UVSeparate = create_node(frameGroup.nodes, "ShaderNodeSeparateXYZ",(-1300,100))
            div2 = create_node(frameGroup.nodes,"ShaderNodeMath", (-900,125) , operation = 'DIVIDE')
            mod = create_node(frameGroup.nodes,"ShaderNodeMath", (-750,125) , operation = 'MODULO')
            mod.inputs[1].default_value = 1
            add = create_node(frameGroup.nodes,"ShaderNodeMath", (-600,125) , operation = 'ADD')
            add.inputs[1].default_value = .5
            mod2 = create_node(frameGroup.nodes,"ShaderNodeMath", (-900,75) , operation = 'MODULO')
            mod2.inputs[1].default_value = 1
            add2 = create_node(frameGroup.nodes,"ShaderNodeMath", (-750,75) , operation = 'ADD')
            add2.inputs[1].default_value = .5
            floor = create_node(frameGroup.nodes,"ShaderNodeMath", (-600,75) , operation = 'FLOOR')
            add3 = create_node(frameGroup.nodes,"ShaderNodeMath", (-450,125) , operation = 'ADD')
            add3.use_clamp = True
            floor2 = create_node(frameGroup.nodes,"ShaderNodeMath", (-300,125) , operation = 'FLOOR')
            #clamp = create_node(frameGroup.nodes,"ShaderNodeClamp", (-300,75))
            frameGroup.links.new(fGroupInput.outputs["InterlaceLines"],div2.inputs[1])
            frameGroup.links.new(fGroupInput.outputs['UV'],UVSeparate.inputs[0])
            frameGroup.links.new(UVSeparate.outputs[1],div2.inputs[0])
            frameGroup.links.new(div2.outputs[0],mod.inputs[0])
            frameGroup.links.new(mod.outputs[0],add.inputs[0])
            frameGroup.links.new(add.outputs[0],floor.inputs[0])
            frameGroup.links.new(fGroupInput.outputs["n"],mod2.inputs[0])
            frameGroup.links.new(mod2.outputs[0],add2.inputs[0])
            frameGroup.links.new(add2.outputs[0],floor2.inputs[0])
            frameGroup.links.new(floor.outputs[0],add3.inputs[0])
            frameGroup.links.new(floor2.outputs[0],add3.inputs[1])
            frameGroup.links.new(add3.outputs[0],fGroupOutput.inputs[0])


        frameAdd = create_node(CurMat.nodes,"ShaderNodeGroup",(-1500, 75), label="frameAdd_ps_t")
        frameAdd.node_tree = frameGroup

        CurMat.links.new(iLines.outputs[0],frameAdd.inputs["InterlaceLines"])
        CurMat.links.new(UVMap.outputs[0],frameAdd.inputs["UV"])
        CurMat.links.new(n.outputs[0],frameAdd.inputs["n"])

        # subUV
        if 'subUV' in bpy.data.node_groups.keys():
            subUVGroup = bpy.data.node_groups['subUV']
        else:
            subUVGroup = bpy.data.node_groups.new("subUV","ShaderNodeTree") 
            if vers[0]<4:
                subUVGroup.inputs.new('NodeSocketFloat','TilesWidth')
                subUVGroup.inputs.new('NodeSocketFloat','TilesHeight')
                subUVGroup.inputs.new('NodeSocketFloat','n')
                subUVGroup.inputs.new('NodeSocketFloat','frameAdd')
                subUVGroup.inputs.new('NodeSocketVector','UV')
                subUVGroup.outputs.new('NodeSocketVector','subUV')
            else:
                subUVGroup.interface.new_socket(name="TilesWidth", socket_type='NodeSocketFloat', in_out='INPUT')
                subUVGroup.interface.new_socket(name="TilesHeight", socket_type='NodeSocketFloat', in_out='INPUT')
                subUVGroup.interface.new_socket(name="n", socket_type='NodeSocketFloat', in_out='INPUT')
                subUVGroup.interface.new_socket(name="frameAdd", socket_type='NodeSocketFloat', in_out='INPUT')
                subUVGroup.interface.new_socket(name="UV", socket_type='NodeSocketVector', in_out='INPUT')
                subUVGroup.interface.new_socket(name="subUV", socket_type='NodeSocketVector', in_out='OUTPUT')
            subUVGroupI = create_node(subUVGroup.nodes, "NodeGroupInput",(-1400,0))
            subUVGroupO = create_node(subUVGroup.nodes, "NodeGroupOutput",(200,0))

            UVSeparate = create_node(subUVGroup.nodes, "ShaderNodeSeparateXYZ",(-1300,100))
            div3 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-900,0) , operation = 'DIVIDE')
            sub = create_node(subUVGroup.nodes,"ShaderNodeMath", (-1100,-50) , operation = 'SUBTRACT')
            div4 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-900,-50) , operation = 'DIVIDE')
            add4 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-800,-100) , operation = 'ADD')
            mod3 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-900,-150) , operation = 'MODULO')
            floor3 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-750,-150) , operation = 'FLOOR')
            div5 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-500,-150) , operation = 'DIVIDE')
            div6 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-900,-200) , operation = 'DIVIDE')
            mod4 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-750,-200) , operation = 'MODULO')
            floor4 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-600,-200) , operation = 'FLOOR')
            div7 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-450,-200) , operation = 'DIVIDE')
            add5 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-500,-250) , operation = 'ADD')
            add6 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-750,-250) , operation = 'ADD')
            sub2 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-500,-150) , operation = 'SUBTRACT')
            combine = create_node(subUVGroup.nodes,"ShaderNodeCombineXYZ", (-200,-200), label = "newUV")
            subUVGroup.links.new(subUVGroupI.outputs[4],UVSeparate.inputs[0])
            subUVGroup.links.new(UVSeparate.outputs[0],div3.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[0],div3.inputs[1]) #sizeX
            sub.inputs[0].default_value = 1.0
            subUVGroup.links.new(UVSeparate.outputs[1],sub.inputs[1])
            subUVGroup.links.new(sub.outputs[0],div4.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[1],div4.inputs[1]) #sizeY
            subUVGroup.links.new(subUVGroupI.outputs[2],add4.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[3],add4.inputs[1]) # CurrentFrame
            subUVGroup.links.new(add4.outputs[0],mod3.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[0],mod3.inputs[1])
            subUVGroup.links.new(mod3.outputs[0],floor3.inputs[0])
            subUVGroup.links.new(floor3.outputs[0],div5.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[0],div5.inputs[1]) # blockX
            subUVGroup.links.new(add4.outputs[0],div6.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[0],div6.inputs[1])
            subUVGroup.links.new(div6.outputs[0],mod4.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[1],mod4.inputs[1])
            subUVGroup.links.new(mod4.outputs[0],floor4.inputs[0])
            subUVGroup.links.new(floor4.outputs[0],div7.inputs[0])
            subUVGroup.links.new(subUVGroupI.outputs[1],div7.inputs[1]) # rowY
            subUVGroup.links.new(div3.outputs[0],add5.inputs[0])
            subUVGroup.links.new(div5.outputs[0],add5.inputs[1])
            subUVGroup.links.new(div4.outputs[0],add6.inputs[0])
            subUVGroup.links.new(div7.outputs[0],add6.inputs[1])
            subUVGroup.links.new(add5.outputs[0],combine.inputs[0])
            sub2.inputs[0].default_value = 1.0
            subUVGroup.links.new(add6.outputs[0],sub2.inputs[1])
            subUVGroup.links.new(sub2.outputs[0],combine.inputs[1])            
            subUVGroup.links.new(combine.outputs[0],subUVGroupO.inputs[0])

        subUV = create_node(CurMat.nodes,"ShaderNodeGroup",(-1350, 75), label="subUV")
        subUV.node_tree = subUVGroup
        subUV.name = "subUV"

        CurMat.links.new(tilesW.outputs[0],subUV.inputs[0])
        CurMat.links.new(tilesH.outputs[0],subUV.inputs[1])
        CurMat.links.new(UVMap.outputs[0],subUV.inputs[4])
        CurMat.links.new(n.outputs[0],subUV.inputs[2])
        CurMat.links.new(frameAdd.outputs[0],subUV.inputs[3])

        # newUV

        if 'newUV_ps_t' in bpy.data.node_groups.keys():
            newUVGroup = bpy.data.node_groups['newUV_ps_t']
        else:
            newUVGroup = bpy.data.node_groups.new("newUV_ps_t","ShaderNodeTree") 
            if vers[0]<4:
                newUVGroup.inputs.new('NodeSocketVector','subUV')
                newUVGroup.inputs.new('NodeSocketFloat','TextureOffsetX')
                newUVGroup.inputs.new('NodeSocketFloat','TextureOffsetY')
                newUVGroup.inputs.new('NodeSocketFloat','ImageScale.x')
                newUVGroup.inputs.new('NodeSocketFloat','ImageScale.y')
                newUVGroup.outputs.new('NodeSocketVector','newUV')
            else:
                newUVGroup.interface.new_socket(name="subUV", socket_type='NodeSocketVector', in_out='INPUT')
                newUVGroup.interface.new_socket(name="TextureOffsetX", socket_type='NodeSocketFloat', in_out='INPUT')
                newUVGroup.interface.new_socket(name="TextureOffsetY", socket_type='NodeSocketFloat', in_out='INPUT')
                newUVGroup.interface.new_socket(name="ImageScale.x", socket_type='NodeSocketFloat', in_out='INPUT')
                newUVGroup.interface.new_socket(name="ImageScale.y", socket_type='NodeSocketFloat', in_out='INPUT')
                newUVGroup.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='OUTPUT')
            newUVGroupI = create_node(newUVGroup.nodes, "NodeGroupInput",(-1400,0))
            newUVGroupO = create_node(newUVGroup.nodes, "NodeGroupOutput",(-300,0))
            vecSub = create_node(newUVGroup.nodes,"ShaderNodeVectorMath", (-1200,25), operation = 'SUBTRACT')
            vecSub.inputs[1].default_value = (.5,.5,.5)
            combine2 = create_node(newUVGroup.nodes, "ShaderNodeCombineXYZ", (-1200,-25))
            vecAdd = create_node(newUVGroup.nodes,"ShaderNodeVectorMath", (-1050,0))
            combine3 = create_node(newUVGroup.nodes, "ShaderNodeCombineXYZ", (-1050,-75))
            vecMul2 = create_node(newUVGroup.nodes,"ShaderNodeVectorMath", (-900,-50), operation = 'MULTIPLY')
            vecAdd2 = create_node(newUVGroup.nodes,"ShaderNodeVectorMath", (-750,0))
            vecAdd2.inputs[1].default_value = (.5,.5,.5)
            vecFrac = create_node(newUVGroup.nodes,"ShaderNodeVectorMath", (-500,0),operation="FRACTION")
            newUVGroup.links.new(newUVGroupI.outputs["subUV"],vecSub.inputs[0])
            newUVGroup.links.new(newUVGroupI.outputs["TextureOffsetX"],combine2.inputs[0])
            newUVGroup.links.new(newUVGroupI.outputs["TextureOffsetY"],combine2.inputs[1])
            newUVGroup.links.new(newUVGroupI.outputs["ImageScale.x"],combine3.inputs[0])
            newUVGroup.links.new(newUVGroupI.outputs["ImageScale.y"],combine3.inputs[1])
            newUVGroup.links.new(vecSub.outputs[0],vecAdd.inputs[0])
            newUVGroup.links.new(combine2.outputs[0],vecAdd.inputs[1])
            newUVGroup.links.new(vecAdd.outputs[0],vecMul2.inputs[0])
            newUVGroup.links.new(combine3.outputs[0],vecMul2.inputs[1])
            newUVGroup.links.new(vecMul2.outputs[0],vecAdd2.inputs[0])
            newUVGroup.links.new(vecAdd2.outputs[0],vecFrac.inputs[0])
            newUVGroup.links.new(vecFrac.outputs[0],newUVGroupO.inputs[0])

        newUV = create_node(CurMat.nodes,"ShaderNodeGroup",(-1200, 75), label="newUV_ps_t")
        newUV.node_tree = newUVGroup
        newUV.name = "newUV_ps_t"

        CurMat.links.new(subUV.outputs[0],newUV.inputs[0])
        CurMat.links.new(textureOffsetX.outputs[0],newUV.inputs[1])
        CurMat.links.new(textureOffsetY.outputs[0],newUV.inputs[2])
        CurMat.links.new(imageScale_x.outputs[0],newUV.inputs[3])
        CurMat.links.new(imageScale_y.outputs[0],newUV.inputs[4])

        # scroll1
        if 'scroll1_ps_t' in bpy.data.node_groups.keys():
            scroll1Group = bpy.data.node_groups['scroll1_ps_t']
        else:
            scroll1Group = bpy.data.node_groups.new("scroll1_ps_t","ShaderNodeTree") 
            if vers[0]<4:
                scroll1Group.inputs.new('NodeSocketFloat','ScrollSpeed1')
                scroll1Group.inputs.new('NodeSocketFloat','ScrollStepFactor1')
                scroll1Group.inputs.new('NodeSocketFloat','Time')
                scroll1Group.outputs.new('NodeSocketFloat','scroll1')
            else:
                scroll1Group.interface.new_socket(name="ScrollSpeed1", socket_type='NodeSocketFloat', in_out='INPUT')
                scroll1Group.interface.new_socket(name="ScrollStepFactor1", socket_type='NodeSocketFloat', in_out='INPUT')
                scroll1Group.interface.new_socket(name="Time", socket_type='NodeSocketFloat', in_out='INPUT')
                scroll1Group.interface.new_socket(name="scroll1", socket_type='NodeSocketFloat', in_out='OUTPUT')

            scroll1GroupI = create_node(scroll1Group.nodes, "NodeGroupInput",(-1400,0))
            scroll1GroupO = create_node(scroll1Group.nodes, "NodeGroupOutput",(-600,0))
            mul = create_node(scroll1Group.nodes, "ShaderNodeMath",(-1250,0),operation="MULTIPLY")
            mul2 = create_node(scroll1Group.nodes, "ShaderNodeMath",(-1100,0),operation="MULTIPLY")
            div = create_node(scroll1Group.nodes, "ShaderNodeMath",(-950,0),operation="DIVIDE")
            floor = create_node(scroll1Group.nodes, "ShaderNodeMath",(-800,0),operation="FLOOR")
            scroll1Group.links.new(scroll1GroupI.outputs[2],mul.inputs[0])
            scroll1Group.links.new(scroll1GroupI.outputs[0],mul.inputs[1])
            scroll1Group.links.new(mul.outputs[0],mul2.inputs[0])
            scroll1Group.links.new(scroll1GroupI.outputs[1],mul2.inputs[1])
            scroll1Group.links.new(mul2.outputs[0],div.inputs[0])
            scroll1Group.links.new(scroll1GroupI.outputs[1],div.inputs[1])
            scroll1Group.links.new(div.outputs[0],floor.inputs[0])
            scroll1Group.links.new(floor.outputs[0],scroll1GroupO.inputs[0])

        scroll1 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1500, -200), label="scroll1_ps_t")
        scroll1.node_tree = scroll1Group
        scroll1.name = "scroll1_ps_t"
        CurMat.links.new(scrollSpeed1.outputs[0], scroll1.inputs[0])
        CurMat.links.new(scrollStepFactor1.outputs[0], scroll1.inputs[1])
        CurMat.links.new(time.outputs[0], scroll1.inputs[2])
        # scrollUV1
        if 'scrollUV1_ps_t' in bpy.data.node_groups.keys():
            scrollUV1Group = bpy.data.node_groups['scrollUV1_ps_t']
        else:
            scrollUV1Group = bpy.data.node_groups.new("scrollUV1_ps_t","ShaderNodeTree") 
            if vers[0]<4:
                scrollUV1Group.inputs.new('NodeSocketVector','newUV')
                scrollUV1Group.inputs.new('NodeSocketFloat','ScrollMaskHeight1')
                scrollUV1Group.inputs.new('NodeSocketFloat','scroll1')
                scrollUV1Group.inputs.new('NodeSocketFloat','ScrollMaskStartPoint1')
                scrollUV1Group.outputs.new('NodeSocketVector','scrollUV1')
            else:
                scrollUV1Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
                scrollUV1Group.interface.new_socket(name="ScrollMaskHeight1", socket_type='NodeSocketFloat', in_out='INPUT')
                scrollUV1Group.interface.new_socket(name="scroll1", socket_type='NodeSocketFloat', in_out='INPUT')
                scrollUV1Group.interface.new_socket(name="ScrollMaskStartPoint1", socket_type='NodeSocketFloat', in_out='INPUT')
                scrollUV1Group.interface.new_socket(name="scrollUV1", socket_type='NodeSocketVector', in_out='OUTPUT')

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

        scrollUV1 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1350, -200), label="scrollUV1_ps_t")
        scrollUV1.node_tree = scrollUV1Group
        scrollUV1.name = "scrollUV1_ps_t"
        CurMat.links.new(newUV.outputs[0], scrollUV1.inputs[0])
        CurMat.links.new(scrollMaskHeight1.outputs[0], scrollUV1.inputs[1])
        CurMat.links.new(scroll1.outputs[0], scrollUV1.inputs[2])
        CurMat.links.new(scrollMaskStartPoint1.outputs[0], scrollUV1.inputs[3])

        # scrollUV1X
        if 'scrollUV1X' in bpy.data.node_groups.keys():
            scrollUV1XGroup = bpy.data.node_groups['scrollUV1X']
        else:
            scrollUV1XGroup = bpy.data.node_groups.new("scrollUV1X","ShaderNodeTree") 
            if vers[0]<4:
                scrollUV1XGroup.inputs.new('NodeSocketVector','newUV')
                scrollUV1XGroup.inputs.new('NodeSocketFloat','ScrollMaskHeight1')
                scrollUV1XGroup.inputs.new('NodeSocketFloat','scroll1')
                scrollUV1XGroup.inputs.new('NodeSocketFloat','ScrollMaskStartPoint1')
                scrollUV1XGroup.outputs.new('NodeSocketVector','scrollUV1X')
            else:
                scrollUV1XGroup.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
                scrollUV1XGroup.interface.new_socket(name="ScrollMaskHeight1", socket_type='NodeSocketFloat', in_out='INPUT')
                scrollUV1XGroup.interface.new_socket(name="scroll1", socket_type='NodeSocketFloat', in_out='INPUT')
                scrollUV1XGroup.interface.new_socket(name="ScrollMaskStartPoint1", socket_type='NodeSocketFloat', in_out='INPUT')
                scrollUV1XGroup.interface.new_socket(name="scrollUV1X", socket_type='NodeSocketVector', in_out='OUTPUT')

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
        CurMat.links.new(newUV.outputs[0], scrollUV1X.inputs[0])
        CurMat.links.new(scrollMaskHeight1.outputs[0], scrollUV1X.inputs[1])
        CurMat.links.new(scroll1.outputs[0], scrollUV1X.inputs[2])
        CurMat.links.new(scrollMaskStartPoint1.outputs[0], scrollUV1X.inputs[3])

        # scroll2
        if 'scroll2_ps_t' in bpy.data.node_groups.keys():
            scroll2Group = bpy.data.node_groups['scroll2_ps_t']
        else:
            scroll2Group = bpy.data.node_groups.new("scroll2_ps_t","ShaderNodeTree") 
            if vers[0]<4:
                scroll2Group.inputs.new('NodeSocketFloat','ScrollSpeed2')
                scroll2Group.inputs.new('NodeSocketFloat','ScrollStepFactor2')
                scroll2Group.inputs.new('NodeSocketFloat','Time')
                scroll2Group.outputs.new('NodeSocketFloat','scroll2')
            else:
                scroll2Group.interface.new_socket(name="ScrollSpeed2", socket_type='NodeSocketFloat', in_out='INPUT')
                scroll2Group.interface.new_socket(name="ScrollStepFactor2", socket_type='NodeSocketFloat', in_out='INPUT')
                scroll2Group.interface.new_socket(name="Time", socket_type='NodeSocketFloat', in_out='INPUT')
                scroll2Group.interface.new_socket(name="scroll2", socket_type='NodeSocketFloat', in_out='OUTPUT')

            scroll2GroupI = create_node(scroll2Group.nodes, "NodeGroupInput",(-1400,0))
            scroll2GroupO = create_node(scroll2Group.nodes, "NodeGroupOutput",(-600,0))
            mul = create_node(scroll2Group.nodes, "ShaderNodeMath",(-1250,0),operation="MULTIPLY")
            mul2 = create_node(scroll2Group.nodes, "ShaderNodeMath",(-1100,0),operation="MULTIPLY")
            div = create_node(scroll2Group.nodes, "ShaderNodeMath",(-950,0),operation="DIVIDE")
            floor = create_node(scroll2Group.nodes, "ShaderNodeMath",(-800,0),operation="FLOOR")
            scroll2Group.links.new(scroll2GroupI.outputs[2],mul.inputs[0])
            scroll2Group.links.new(scroll2GroupI.outputs[0],mul.inputs[1])
            scroll2Group.links.new(mul.outputs[0],mul2.inputs[0])
            scroll2Group.links.new(scroll2GroupI.outputs[1],mul2.inputs[1])
            scroll2Group.links.new(mul2.outputs[0],div.inputs[0])
            scroll2Group.links.new(scroll2GroupI.outputs[1],div.inputs[1])
            scroll2Group.links.new(div.outputs[0],floor.inputs[0])
            scroll2Group.links.new(floor.outputs[0],scroll2GroupO.inputs[0])

        scroll2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1500, -300), label="scroll2_ps_t")
        scroll2.node_tree = scroll2Group
        scroll2.name = "scroll2_ps_t"
        CurMat.links.new(scrollSpeed2.outputs[0], scroll2.inputs[0])
        CurMat.links.new(scrollStepFactor2.outputs[0], scroll2.inputs[1])
        CurMat.links.new(time.outputs[0], scroll2.inputs[2])

        # scrollUV2
        if 'scrollUV2_ps_t' in bpy.data.node_groups.keys():
            scrollUV2Group = bpy.data.node_groups['scrollUV2_ps_t']
        else:
            scrollUV2Group = bpy.data.node_groups.new("scrollUV2_ps_t","ShaderNodeTree") 
            if vers[0]<4:
                scrollUV2Group.inputs.new('NodeSocketVector','newUV')
                scrollUV2Group.inputs.new('NodeSocketFloat','ScrollMaskHeight2')
                scrollUV2Group.inputs.new('NodeSocketFloat','scroll2')
                scrollUV2Group.inputs.new('NodeSocketFloat','ScrollMaskStartPoint2')
                scrollUV2Group.outputs.new('NodeSocketVector','scrollUV2')
            else:
                scrollUV2Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
                scrollUV2Group.interface.new_socket(name="ScrollMaskHeight2", socket_type='NodeSocketFloat', in_out='INPUT')
                scrollUV2Group.interface.new_socket(name="scroll2", socket_type='NodeSocketFloat', in_out='INPUT')
                scrollUV2Group.interface.new_socket(name="ScrollMaskStartPoint2", socket_type='NodeSocketFloat', in_out='INPUT')
                scrollUV2Group.interface.new_socket(name="scrollUV2", socket_type='NodeSocketVector', in_out='OUTPUT')

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

        scrollUV2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1350, -300), label="scrollUV2_ps_t")
        scrollUV2.node_tree = scrollUV2Group
        scrollUV2.name = "scrollUV2_ps_t"
        CurMat.links.new(newUV.outputs[0], scrollUV2.inputs[0])
        CurMat.links.new(scrollMaskHeight2.outputs[0], scrollUV2.inputs[1])
        CurMat.links.new(scroll2.outputs[0], scrollUV2.inputs[2])
        CurMat.links.new(scrollMaskStartPoint2.outputs[0], scrollUV2.inputs[3])

        # scrollUV2X
        if 'scrollUV2X' in bpy.data.node_groups.keys():
            scrollUV2XGroup = bpy.data.node_groups['scrollUV2X']
        else:
            scrollUV2XGroup = bpy.data.node_groups.new("scrollUV2X","ShaderNodeTree") 
            if vers[0]<4:
                scrollUV2XGroup.inputs.new('NodeSocketVector','newUV')
                scrollUV2XGroup.inputs.new('NodeSocketFloat','ScrollMaskHeight2')
                scrollUV2XGroup.inputs.new('NodeSocketFloat','scroll2')
                scrollUV2XGroup.inputs.new('NodeSocketFloat','ScrollMaskStartPoint2')
                scrollUV2XGroup.outputs.new('NodeSocketVector','scrollUV2X')
            else:
                scrollUV2XGroup.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
                scrollUV2XGroup.interface.new_socket(name="ScrollMaskHeight2", socket_type='NodeSocketFloat', in_out='INPUT')
                scrollUV2XGroup.interface.new_socket(name="scroll2", socket_type='NodeSocketFloat', in_out='INPUT')
                scrollUV2XGroup.interface.new_socket(name="ScrollMaskStartPoint2", socket_type='NodeSocketFloat', in_out='INPUT')
                scrollUV2XGroup.interface.new_socket(name="scrollUV2X", socket_type='NodeSocketVector', in_out='OUTPUT')
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
        CurMat.links.new(newUV.outputs[0], scrollUV2X.inputs[0])
        CurMat.links.new(scrollMaskHeight2.outputs[0], scrollUV2X.inputs[1])
        CurMat.links.new(scroll2.outputs[0], scrollUV2X.inputs[2])
        CurMat.links.new(scrollMaskStartPoint2.outputs[0], scrollUV2X.inputs[3])

        # TODO ClampUV
        # l1
        if 'l1_ps_t' in bpy.data.node_groups.keys():
            l1Group = bpy.data.node_groups['l1_ps_t']
        else:     
            l1Group = bpy.data.node_groups.new("l1_ps_t","ShaderNodeTree")   
            if vers[0]<4:
                l1Group.inputs.new('NodeSocketVector','newUV') 
                l1Group.outputs.new('NodeSocketVector','l1')    
            else:
                l1Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
                l1Group.interface.new_socket(name="l1", socket_type='NodeSocketVector', in_out='OUTPUT')

            l1GroupI = create_node(l1Group.nodes, "NodeGroupInput",(-800,0))
            l1GroupO = create_node(l1Group.nodes, "NodeGroupOutput",(200,0))  
            vecMul3 =  create_node(l1Group.nodes,"ShaderNodeVectorMath",(-650,0),operation="MULTIPLY")
            vecMul3.inputs[1].default_value = (.5,.5, 0)
            separate3 = create_node(l1Group.nodes,"ShaderNodeSeparateXYZ",(-500,0))                              
            clamp2 = create_node(l1Group.nodes,"ShaderNodeClamp",(-350,25))
            clamp2.inputs[1].default_value = (0)
            clamp2.inputs[2].default_value = (.5)
            clamp3 = create_node(l1Group.nodes,"ShaderNodeClamp",(-350,-25))
            clamp3.inputs[1].default_value = (0)
            clamp3.inputs[2].default_value = (.5)
            combine11 = create_node(l1Group.nodes,"ShaderNodeCombineXYZ",(-200,0))   
            l1Group.links.new(l1GroupI.outputs[0],vecMul3.inputs[0])
            l1Group.links.new(vecMul3.outputs[0],separate3.inputs[0])
            l1Group.links.new(separate3.outputs[0],clamp2.inputs[0])
            l1Group.links.new(separate3.outputs[1],clamp3.inputs[0])
            l1Group.links.new(clamp2.outputs[0],combine11.inputs[0])
            l1Group.links.new(clamp3.outputs[0],combine11.inputs[1])
            l1Group.links.new(combine11.outputs[0],l1GroupO.inputs[0])

        l1 = create_node(CurMat.nodes,"ShaderNodeGroup",(-950,500), label="l1_ps_t")
        l1.node_tree = l1Group 
        CurMat.links.new(newUV.outputs[0],l1.inputs[0])

        # l2
        if 'l2_ps_t' in bpy.data.node_groups.keys():
            l2Group = bpy.data.node_groups['l2_ps_t']
        else:     
            l2Group = bpy.data.node_groups.new("l2_ps_t","ShaderNodeTree")
            if vers[0]<4:
                l2Group.inputs.new('NodeSocketVector','modUV')
                l2Group.inputs.new('NodeSocketVector','newUV')
                l2Group.inputs.new('NodeSocketFloat','LayersSeparation')
                l2Group.outputs.new('NodeSocketVector','l2')   
            else:
                l2Group.interface.new_socket(name="modUV", socket_type='NodeSocketVector', in_out='INPUT')
                l2Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
                l2Group.interface.new_socket(name="LayersSeparation", socket_type='NodeSocketFloat', in_out='INPUT')
                l2Group.interface.new_socket(name="l2", socket_type='NodeSocketVector', in_out='OUTPUT')

            l2GroupI = create_node(l2Group.nodes, "NodeGroupInput",(-1000,0))
            l2GroupO = create_node(l2Group.nodes, "NodeGroupOutput",(200,0))
            vecMul7 = create_node(l2Group.nodes,"ShaderNodeVectorMath",(-800,-25),operation="MULTIPLY")
            vecMul8 = create_node(l2Group.nodes,"ShaderNodeVectorMath",(-800,25),operation="MULTIPLY")
            vecMul8.inputs[1].default_value = (.5,.5, 0)
            vecAdd6 = create_node(l2Group.nodes,"ShaderNodeVectorMath",(-600,0),operation="ADD")
            vecAdd6.inputs[1].default_value = (.5, 0, 0)
            vecAdd7 = create_node(l2Group.nodes,"ShaderNodeVectorMath",(-450,0),operation="ADD")
            separate4 = create_node(l2Group.nodes,"ShaderNodeSeparateXYZ",(-300,0))  
            clamp4 = create_node(l2Group.nodes,"ShaderNodeClamp",(-150,25))
            clamp4.inputs[1].default_value = .5
            clamp4.inputs[2].default_value = 0
            clamp5 = create_node(l2Group.nodes,"ShaderNodeClamp",(-150,-25))
            clamp5.inputs[1].default_value = 1
            clamp5.inputs[2].default_value = .5
            combine12 = create_node(l2Group.nodes,"ShaderNodeCombineXYZ",(0,0))   
            l2Group.links.new(l2GroupI.outputs[0],vecMul7.inputs[0])
            l2Group.links.new(l2GroupI.outputs[2],vecMul7.inputs[1])
            l2Group.links.new(l2GroupI.outputs[1],vecMul8.inputs[0])
            l2Group.links.new(vecMul8.outputs[0],vecAdd6.inputs[0])
            l2Group.links.new(vecAdd6.outputs[0],vecAdd7.inputs[0])
            l2Group.links.new(vecMul7.outputs[0],vecAdd7.inputs[1])
            l2Group.links.new(vecAdd7.outputs[0],separate4.inputs[0])
            l2Group.links.new(separate4.outputs[0],clamp4.inputs[0])
            l2Group.links.new(separate4.outputs[1],clamp5.inputs[0])
            l2Group.links.new(clamp4.outputs[0],combine12.inputs[0])
            l2Group.links.new(clamp5.outputs[0],combine12.inputs[1])
            l2Group.links.new(combine12.outputs[0],l2GroupO.inputs[0])

        l2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-950,450), label="l2_ps_t")
        l2.node_tree = l2Group 

        CurMat.links.new(newUV.outputs[0],l2.inputs[1])
        CurMat.links.new(combine.outputs[0],l2.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0],l2.inputs[2])

        # l3

        if 'l3_ps_t' in bpy.data.node_groups.keys():
            l3Group = bpy.data.node_groups['l3_ps_t']
        else:     
            l3Group = bpy.data.node_groups.new("l3_ps_t","ShaderNodeTree")
            if vers[0]<4:
                l3Group.inputs.new('NodeSocketVector','modUV')
                l3Group.inputs.new('NodeSocketVector','newUV')
                l3Group.inputs.new('NodeSocketFloat','LayersSeparation')
                l3Group.outputs.new('NodeSocketVector','l3')    
            else:
                l3Group.interface.new_socket(name="modUV", socket_type='NodeSocketVector', in_out='INPUT')
                l3Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
                l3Group.interface.new_socket(name="LayersSeparation", socket_type='NodeSocketFloat', in_out='INPUT')
                l3Group.interface.new_socket(name="l3", socket_type='NodeSocketVector', in_out='OUTPUT')

            l3GroupI = create_node(l3Group.nodes, "NodeGroupInput",(-1000,0))
            l3GroupO = create_node(l3Group.nodes, "NodeGroupOutput",(200,0))
            vecMul7 = create_node(l3Group.nodes,"ShaderNodeVectorMath",(-800,-25),operation="MULTIPLY")
            vecMul8 = create_node(l3Group.nodes,"ShaderNodeVectorMath",(-800,25),operation="MULTIPLY")
            vecMul8.inputs[1].default_value = (.5,.5, 0)
            vecMul9 = create_node(l3Group.nodes,"ShaderNodeVectorMath",(-600,-25),operation="MULTIPLY")
            vecMul9.inputs[1].default_value = (2,2,2)
            vecAdd6 = create_node(l3Group.nodes,"ShaderNodeVectorMath",(-600,25),operation="ADD")
            vecAdd6.inputs[1].default_value = (.5, 0, 0)
            vecAdd7 = create_node(l3Group.nodes,"ShaderNodeVectorMath",(-450,0),operation="ADD")
            separate4 = create_node(l3Group.nodes,"ShaderNodeSeparateXYZ",(-300,0))  
            clamp4 = create_node(l3Group.nodes,"ShaderNodeClamp",(-150,25))
            clamp4.inputs[1].default_value = 0
            clamp4.inputs[2].default_value = .5
            clamp5 = create_node(l3Group.nodes,"ShaderNodeClamp",(-150,-25))
            clamp5.inputs[1].default_value = .5
            clamp5.inputs[2].default_value = 1
            combine12 = create_node(l3Group.nodes,"ShaderNodeCombineXYZ",(0,0))   
            l3Group.links.new(l3GroupI.outputs[0],vecMul7.inputs[0])
            l3Group.links.new(l3GroupI.outputs[2],vecMul7.inputs[1])
            l3Group.links.new(vecMul7.outputs[0],vecMul9.inputs[0])
            l3Group.links.new(l3GroupI.outputs[1],vecMul8.inputs[0])
            l3Group.links.new(vecMul8.outputs[0],vecAdd6.inputs[0])
            l3Group.links.new(vecAdd6.outputs[0],vecAdd7.inputs[0])
            l3Group.links.new(vecMul9.outputs[0],vecAdd7.inputs[1])
            l3Group.links.new(vecAdd7.outputs[0],separate4.inputs[0])
            l3Group.links.new(separate4.outputs[0],clamp4.inputs[0])
            l3Group.links.new(separate4.outputs[1],clamp5.inputs[0])
            l3Group.links.new(clamp4.outputs[0],combine12.inputs[0])
            l3Group.links.new(clamp5.outputs[0],combine12.inputs[1])
            l3Group.links.new(combine12.outputs[0],l3GroupO.inputs[0])

        l3 = create_node(CurMat.nodes,"ShaderNodeGroup",(-950,400), label="l3_ps_t")
        l3.node_tree = l3Group 

        CurMat.links.new(newUV.outputs[0],l3.inputs[1])
        CurMat.links.new(combine.outputs[0],l3.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0],l3.inputs[2])

        # l4

        if 'l4' in bpy.data.node_groups.keys():
            l4Group = bpy.data.node_groups['l4_ps_t']
        else:     
            l4Group = bpy.data.node_groups.new("l4_ps_t","ShaderNodeTree")
            if vers[0]<4:
                l4Group.inputs.new('NodeSocketVector','modUV')
                l4Group.inputs.new('NodeSocketVector','newUV')
                l4Group.inputs.new('NodeSocketFloat','LayersSeparation')
                l4Group.outputs.new('NodeSocketVector','l4')    
            else:
                l4Group.interface.new_socket(name="modUV", socket_type='NodeSocketVector', in_out='INPUT')
                l4Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
                l4Group.interface.new_socket(name="LayersSeparation", socket_type='NodeSocketFloat', in_out='INPUT')
                l4Group.interface.new_socket(name="l4", socket_type='NodeSocketVector', in_out='OUTPUT')

            l4GroupI = create_node(l4Group.nodes, "NodeGroupInput",(-1000,0))
            l4GroupO = create_node(l4Group.nodes, "NodeGroupOutput",(200,0))
            vecMul7 = create_node(l4Group.nodes,"ShaderNodeVectorMath",(-800,-25),operation="MULTIPLY")
            vecMul8 = create_node(l4Group.nodes,"ShaderNodeVectorMath",(-800,25),operation="MULTIPLY")
            vecMul8.inputs[1].default_value = (.5,.5, 0)
            vecMul9 = create_node(l4Group.nodes,"ShaderNodeVectorMath",(-600,-25),operation="MULTIPLY")
            vecMul9.inputs[1].default_value = (3,3,3)
            vecAdd6 = create_node(l4Group.nodes,"ShaderNodeVectorMath",(-600,25),operation="ADD")
            vecAdd6.inputs[1].default_value = (.5, 0, 0)
            vecAdd7 = create_node(l4Group.nodes,"ShaderNodeVectorMath",(-450,0),operation="ADD")
            separate4 = create_node(l4Group.nodes,"ShaderNodeSeparateXYZ",(-300,0))  
            clamp4 = create_node(l4Group.nodes,"ShaderNodeClamp",(-150,25))
            clamp4.inputs[1].default_value = .5
            clamp4.inputs[2].default_value = 1
            clamp5 = create_node(l4Group.nodes,"ShaderNodeClamp",(-150,-25))
            clamp5.inputs[1].default_value = .5
            clamp5.inputs[2].default_value = 1
            combine12 = create_node(l4Group.nodes,"ShaderNodeCombineXYZ",(0,0))   
            l4Group.links.new(l4GroupI.outputs[0],vecMul7.inputs[0])
            l4Group.links.new(l4GroupI.outputs[2],vecMul7.inputs[1])
            l4Group.links.new(vecMul7.outputs[0],vecMul9.inputs[0])
            l4Group.links.new(l4GroupI.outputs[1],vecMul8.inputs[0])
            l4Group.links.new(vecMul8.outputs[0],vecAdd6.inputs[0])
            l4Group.links.new(vecAdd6.outputs[0],vecAdd7.inputs[0])
            l4Group.links.new(vecMul9.outputs[0],vecAdd7.inputs[1])
            l4Group.links.new(vecAdd7.outputs[0],separate4.inputs[0])
            l4Group.links.new(separate4.outputs[0],clamp4.inputs[0])
            l4Group.links.new(separate4.outputs[1],clamp5.inputs[0])
            l4Group.links.new(clamp4.outputs[0],combine12.inputs[0])
            l4Group.links.new(clamp5.outputs[0],combine12.inputs[1])
            l4Group.links.new(combine12.outputs[0],l4GroupO.inputs[0])

        l4 = create_node(CurMat.nodes,"ShaderNodeGroup",(-950,350), label="l4_ps_t")
        l4.node_tree = l4Group 

        CurMat.links.new(newUV.outputs[0],l4.inputs[1])
        CurMat.links.new(combine.outputs[0],l4.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0],l4.inputs[2])

        # l1_2
        if 'l1_2' in bpy.data.node_groups.keys():
            l1_2Group = bpy.data.node_groups['l1_2']
        else:     
            l1_2Group = bpy.data.node_groups.new("l1_2","ShaderNodeTree")   
            if vers[0]<4:
                l1_2Group.inputs.new('NodeSocketVector','newUV') 
                l1_2Group.outputs.new('NodeSocketVector','l1_2')    
            else:
                l1_2Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
                l1_2Group.interface.new_socket(name="l1_2", socket_type='NodeSocketVector', in_out='OUTPUT')

            l1_2GroupI = create_node(l1_2Group.nodes, "NodeGroupInput",(-800,0))
            l1_2GroupO = create_node(l1_2Group.nodes, "NodeGroupOutput",(200,0))  
            separate3 = create_node(l1_2Group.nodes,"ShaderNodeSeparateXYZ",(-650,0))                              
            clamp2 = create_node(l1_2Group.nodes,"ShaderNodeClamp",(-500,25))
            clamp3 = create_node(l1_2Group.nodes,"ShaderNodeClamp",(-500,-25))
            combine11 = create_node(l1_2Group.nodes,"ShaderNodeCombineXYZ",(-350,0))   
            l1_2Group.links.new(l1_2GroupI.outputs[0],separate3.inputs[0])
            l1_2Group.links.new(separate3.outputs[0],clamp2.inputs[0])
            l1_2Group.links.new(separate3.outputs[1],clamp3.inputs[0])
            l1_2Group.links.new(clamp2.outputs[0],combine11.inputs[0])
            l1_2Group.links.new(clamp3.outputs[0],combine11.inputs[1])
            l1_2Group.links.new(combine11.outputs[0],l1_2GroupO.inputs[0])

        l1_2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-950,300), label="l1_2")
        l1_2.node_tree = l1_2Group 
        CurMat.links.new(newUV.outputs[0],l1_2.inputs[0])

        # l2_2
        if 'l2_2' in bpy.data.node_groups.keys():
            l2_2Group = bpy.data.node_groups['l2_2']
        else:     
            l2_2Group = bpy.data.node_groups.new("l2_2","ShaderNodeTree")
            if vers[0]<4:
                l2_2Group.inputs.new('NodeSocketVector','modUV')
                l2_2Group.inputs.new('NodeSocketVector','newUV')
                l2_2Group.inputs.new('NodeSocketFloat','LayersSeparation')
                l2_2Group.outputs.new('NodeSocketVector','l2_2')   
            else:
                l2_2Group.interface.new_socket(name="modUV", socket_type='NodeSocketVector', in_out='INPUT')
                l2_2Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
                l2_2Group.interface.new_socket(name="LayersSeparation", socket_type='NodeSocketFloat', in_out='INPUT')
                l2_2Group.interface.new_socket(name="l2_2", socket_type='NodeSocketVector', in_out='OUTPUT')

            l2_2GroupI = create_node(l2_2Group.nodes, "NodeGroupInput",(-800,0))
            l2_2GroupO = create_node(l2_2Group.nodes, "NodeGroupOutput",(200,0))
            vecMul7 = create_node(l2_2Group.nodes,"ShaderNodeVectorMath",(-600,0),operation="MULTIPLY")
            vecAdd6 = create_node(l2_2Group.nodes,"ShaderNodeVectorMath",(-450,0),operation="ADD")
            separate4 = create_node(l2_2Group.nodes,"ShaderNodeSeparateXYZ",(-300,0))  
            clamp4 = create_node(l2_2Group.nodes,"ShaderNodeClamp",(-150,25))
            clamp5 = create_node(l2_2Group.nodes,"ShaderNodeClamp",(-150,-25))
            combine12 = create_node(l2_2Group.nodes,"ShaderNodeCombineXYZ",(0,0))   
            l2_2Group.links.new(l2_2GroupI.outputs[0],vecMul7.inputs[0])
            l2_2Group.links.new(l2_2GroupI.outputs[2],vecMul7.inputs[1])
            l2_2Group.links.new(l2_2GroupI.outputs[1],vecAdd6.inputs[0])
            l2_2Group.links.new(vecMul7.outputs[0],vecAdd6.inputs[1])
            l2_2Group.links.new(vecAdd6.outputs[0],separate4.inputs[0])
            l2_2Group.links.new(separate4.outputs[0],clamp4.inputs[0])
            l2_2Group.links.new(separate4.outputs[1],clamp5.inputs[0])
            l2_2Group.links.new(clamp4.outputs[0],combine12.inputs[0])
            l2_2Group.links.new(clamp5.outputs[0],combine12.inputs[1])
            l2_2Group.links.new(combine12.outputs[0],l2_2GroupO.inputs[0])

        l2_2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-950,250), label="l2_2")
        l2_2.node_tree = l2_2Group 

        CurMat.links.new(newUV.outputs[0],l2_2.inputs[1])
        CurMat.links.new(combine.outputs[0],l2_2.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0],l2_2.inputs[2])

        # l3_2
        if 'l3_2' in bpy.data.node_groups.keys():
            l3_2Group = bpy.data.node_groups['l3_2']
        else:     
            l3_2Group = bpy.data.node_groups.new("l3_2","ShaderNodeTree")
            if vers[0]<4:
                l3_2Group.inputs.new('NodeSocketVector','modUV')
                l3_2Group.inputs.new('NodeSocketVector','newUV')
                l3_2Group.inputs.new('NodeSocketFloat','LayersSeparation')
                l3_2Group.outputs.new('NodeSocketVector','l3_2')   
            else:
                l3_2Group.interface.new_socket(name="modUV", socket_type='NodeSocketVector', in_out='INPUT')
                l3_2Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
                l3_2Group.interface.new_socket(name="LayersSeparation", socket_type='NodeSocketFloat', in_out='INPUT')
                l3_2Group.interface.new_socket(name="l3_2", socket_type='NodeSocketVector', in_out='OUTPUT')

            l3_2GroupI = create_node(l3_2Group.nodes, "NodeGroupInput",(-800,0))
            l3_2GroupO = create_node(l3_2Group.nodes, "NodeGroupOutput",(300,0))
            vecMul8 = create_node(l3_2Group.nodes,"ShaderNodeVectorMath",(-600,0),operation="MULTIPLY")
            vecMul9 = create_node(l3_2Group.nodes,"ShaderNodeVectorMath",(-450,0),operation="MULTIPLY")
            vecMul9.inputs[1].default_value = (2,2,2)
            vecAdd7 = create_node(l3_2Group.nodes,"ShaderNodeVectorMath",(-300,0),operation="ADD")
            separate5 = create_node(l3_2Group.nodes,"ShaderNodeSeparateXYZ",(-150,0))  
            clamp6 = create_node(l3_2Group.nodes,"ShaderNodeClamp",(-0,25))
            clamp7 = create_node(l3_2Group.nodes,"ShaderNodeClamp",(-0,-25))
            combine13 = create_node(l3_2Group.nodes,"ShaderNodeCombineXYZ",(150,0)) 
            l3_2Group.links.new(l3_2GroupI.outputs[0],vecMul8.inputs[0])
            l3_2Group.links.new(l3_2GroupI.outputs[2],vecMul8.inputs[1])
            l3_2Group.links.new(vecMul8.outputs[0],vecMul9.inputs[0])
            l3_2Group.links.new(l3_2GroupI.outputs[1],vecAdd7.inputs[0])
            l3_2Group.links.new(vecMul9.outputs[0],vecAdd7.inputs[1])
            l3_2Group.links.new(vecAdd7.outputs[0],separate5.inputs[0])
            l3_2Group.links.new(separate5.outputs[0],clamp6.inputs[0])
            l3_2Group.links.new(separate5.outputs[1],clamp7.inputs[0])
            l3_2Group.links.new(clamp6.outputs[0],combine13.inputs[0])
            l3_2Group.links.new(clamp7.outputs[0],combine13.inputs[1])
            l3_2Group.links.new(combine13.outputs[0],l3_2GroupO.inputs[0])

        l3_2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-950,200), label="l3_2")
        l3_2.node_tree = l3_2Group 

        CurMat.links.new(newUV.outputs[0],l3_2.inputs[1])
        CurMat.links.new(combine.outputs[0],l3_2.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0],l3_2.inputs[2])

        # l4_2
        if 'l4_2' in bpy.data.node_groups.keys():
            l4_2Group = bpy.data.node_groups['l4_2']
        else:     
            l4_2Group = bpy.data.node_groups.new("l4_2","ShaderNodeTree")
            if vers[0]<4:
                l4_2Group.inputs.new('NodeSocketVector','modUV')
                l4_2Group.inputs.new('NodeSocketVector','newUV')
                l4_2Group.inputs.new('NodeSocketFloat','LayersSeparation')
                l4_2Group.outputs.new('NodeSocketVector','l4_2')   
            else:
                l4_2Group.interface.new_socket(name="modUV", socket_type='NodeSocketVector', in_out='INPUT')
                l4_2Group.interface.new_socket(name="newUV", socket_type='NodeSocketVector', in_out='INPUT')
                l4_2Group.interface.new_socket(name="LayersSeparation", socket_type='NodeSocketFloat', in_out='INPUT')
                l4_2Group.interface.new_socket(name="l4_2", socket_type='NodeSocketVector', in_out='OUTPUT')
            l4_2GroupI = create_node(l4_2Group.nodes, "NodeGroupInput",(-800,0))
            l4_2GroupO = create_node(l4_2Group.nodes, "NodeGroupOutput",(300,0))
            vecMul8 = create_node(l4_2Group.nodes,"ShaderNodeVectorMath",(-600,0),operation="MULTIPLY")
            vecMul9 = create_node(l4_2Group.nodes,"ShaderNodeVectorMath",(-450,0),operation="MULTIPLY")
            vecMul9.inputs[1].default_value = (3,3,3)
            vecAdd7 = create_node(l4_2Group.nodes,"ShaderNodeVectorMath",(-300,0),operation="ADD")
            separate5 = create_node(l4_2Group.nodes,"ShaderNodeSeparateXYZ",(-150,0))  
            clamp6 = create_node(l4_2Group.nodes,"ShaderNodeClamp",(-0,25))
            clamp7 = create_node(l4_2Group.nodes,"ShaderNodeClamp",(-0,-25))
            combine13 = create_node(l4_2Group.nodes,"ShaderNodeCombineXYZ",(150,0)) 
            l4_2Group.links.new(l4_2GroupI.outputs[0],vecMul8.inputs[0])
            l4_2Group.links.new(l4_2GroupI.outputs[2],vecMul8.inputs[1])
            l4_2Group.links.new(vecMul8.outputs[0],vecMul9.inputs[0])
            l4_2Group.links.new(l4_2GroupI.outputs[1],vecAdd7.inputs[0])
            l4_2Group.links.new(vecMul9.outputs[0],vecAdd7.inputs[1])
            l4_2Group.links.new(vecAdd7.outputs[0],separate5.inputs[0])
            l4_2Group.links.new(separate5.outputs[0],clamp6.inputs[0])
            l4_2Group.links.new(separate5.outputs[1],clamp7.inputs[0])
            l4_2Group.links.new(clamp6.outputs[0],combine13.inputs[0])
            l4_2Group.links.new(clamp7.outputs[0],combine13.inputs[1])
            l4_2Group.links.new(combine13.outputs[0],l4_2GroupO.inputs[0])

        l4_2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-950,150), label="l4_2")
        l4_2.node_tree = l4_2Group 

        CurMat.links.new(newUV.outputs[0],l4_2.inputs[1])
        CurMat.links.new(combine.outputs[0],l4_2.inputs[0])
        CurMat.links.new(layersSeparation.outputs[0],l4_2.inputs[2])

        # SeparateLayersFromTexture
        vecMix = create_node(CurMat.nodes,"ShaderNodeMix",(-775,425))
        vecMix.data_type = "VECTOR"
        vecMix2 = create_node(CurMat.nodes,"ShaderNodeMix",(-775,375))
        vecMix2.data_type = "VECTOR"
        vecMix3 = create_node(CurMat.nodes,"ShaderNodeMix",(-775,325))
        vecMix3.data_type = "VECTOR"
        vecMix4 = create_node(CurMat.nodes,"ShaderNodeMix",(-775,275))
        vecMix4.data_type = "VECTOR"
        CurMat.links.new(separateLayersFromTex.outputs[0],vecMix.inputs[0])
        CurMat.links.new(l1.outputs[0],vecMix.inputs[5])
        CurMat.links.new(l1_2.outputs[0],vecMix.inputs[4])
        CurMat.links.new(separateLayersFromTex.outputs[0],vecMix2.inputs[0])
        CurMat.links.new(l2.outputs[0],vecMix2.inputs[5])
        CurMat.links.new(l2_2.outputs[0],vecMix2.inputs[4])
        CurMat.links.new(separateLayersFromTex.outputs[0],vecMix3.inputs[0])
        CurMat.links.new(l3.outputs[0],vecMix3.inputs[5])
        CurMat.links.new(l3_2.outputs[0],vecMix3.inputs[4])
        CurMat.links.new(separateLayersFromTex.outputs[0],vecMix4.inputs[0])
        CurMat.links.new(l4.outputs[0],vecMix4.inputs[5])
        CurMat.links.new(l4_2.outputs[0],vecMix4.inputs[4])

        if 'l1scrollspeed' in bpy.data.node_groups.keys():
            l1ssGroup = bpy.data.node_groups['l1scrollspeed']
        else:     
            l1ssGroup = bpy.data.node_groups.new("l1scrollspeed","ShaderNodeTree")
            if vers[0]<4:
                l1ssGroup.inputs.new('NodeSocketVector','l1')
                l1ssGroup.inputs.new('NodeSocketFloat','LayersScrollSpeed.x')
                l1ssGroup.inputs.new('NodeSocketFloat','time')
                l1ssGroup.outputs.new('NodeSocketVector','l1scrollspeed')
            else:
                l1ssGroup.interface.new_socket(name="l1", socket_type='NodeSocketVector', in_out='INPUT')
                l1ssGroup.interface.new_socket(name="LayersScrollSpeed.x", socket_type='NodeSocketFloat', in_out='INPUT')
                l1ssGroup.interface.new_socket(name="time", socket_type='NodeSocketFloat', in_out='INPUT')
                l1ssGroup.interface.new_socket(name="l1scrollspeed", socket_type='NodeSocketVector', in_out='OUTPUT')

            l1ssGroupI = create_node(l1ssGroup.nodes, "NodeGroupInput",(-1000,0))
            l1ssGroupO = create_node(l1ssGroup.nodes, "NodeGroupOutput",(200,0))
            separate = create_node(l1ssGroup.nodes, "ShaderNodeSeparateXYZ",(-800,25))
            mul = create_node(l1ssGroup.nodes, "ShaderNodeMath",(-800,-25),operation="MULTIPLY")
            add = create_node(l1ssGroup.nodes, "ShaderNodeMath",(-600,0))
            combine = create_node(l1ssGroup.nodes, "ShaderNodeCombineXYZ",(-400,0))
            l1ssGroup.links.new(l1ssGroupI.outputs[0],separate.inputs[0])
            l1ssGroup.links.new(l1ssGroupI.outputs[2],mul.inputs[0])
            l1ssGroup.links.new(l1ssGroupI.outputs[1],mul.inputs[1])
            l1ssGroup.links.new(separate.outputs[1],add.inputs[0])
            l1ssGroup.links.new(mul.outputs[0],add.inputs[1])
            l1ssGroup.links.new(add.outputs[0],combine.inputs[1])
            l1ssGroup.links.new(separate.outputs[0],combine.inputs[0])
            l1ssGroup.links.new(combine.outputs[0],l1ssGroupO.inputs[0])

        l1ss = create_node(CurMat.nodes,"ShaderNodeGroup",(-625,425), label="l1scrollspeed")
        l1ss.node_tree = l1ssGroup 
        CurMat.links.new(vecMix.outputs[1],l1ss.inputs[0])
        CurMat.links.new(layersScrollSpeed_x.outputs[0],l1ss.inputs[1])
        CurMat.links.new(time.outputs[0],l1ss.inputs[2])


        if 'l2scrollspeed' in bpy.data.node_groups.keys():
            l2ssGroup = bpy.data.node_groups['l2scrollspeed']
        else:     
            l2ssGroup = bpy.data.node_groups.new("l2scrollspeed","ShaderNodeTree")
            if vers[0]<4:
                l2ssGroup.inputs.new('NodeSocketVector','l2')
                l2ssGroup.inputs.new('NodeSocketFloat','LayersScrollSpeed.y')
                l2ssGroup.inputs.new('NodeSocketFloat','time')
                l2ssGroup.outputs.new('NodeSocketVector','l2scrollspeed')
            else:
                l2ssGroup.interface.new_socket(name="l2", socket_type='NodeSocketVector', in_out='INPUT')
                l2ssGroup.interface.new_socket(name="LayersScrollSpeed.y", socket_type='NodeSocketFloat', in_out='INPUT')
                l2ssGroup.interface.new_socket(name="time", socket_type='NodeSocketFloat', in_out='INPUT')
                l2ssGroup.interface.new_socket(name="l2scrollspeed", socket_type='NodeSocketVector', in_out='OUTPUT')

            l2ssGroupI = create_node(l2ssGroup.nodes, "NodeGroupInput",(-1000,0))
            l2ssGroupO = create_node(l2ssGroup.nodes, "NodeGroupOutput",(200,0))
            separate = create_node(l2ssGroup.nodes, "ShaderNodeSeparateXYZ",(-800,25))
            mul = create_node(l2ssGroup.nodes, "ShaderNodeMath",(-800,-25),operation="MULTIPLY")
            add = create_node(l2ssGroup.nodes, "ShaderNodeMath",(-600,0))
            combine = create_node(l2ssGroup.nodes, "ShaderNodeCombineXYZ",(-400,0))
            l2ssGroup.links.new(l2ssGroupI.outputs[0],separate.inputs[0])
            l2ssGroup.links.new(l2ssGroupI.outputs[2],mul.inputs[0])
            l2ssGroup.links.new(l2ssGroupI.outputs[1],mul.inputs[1])
            l2ssGroup.links.new(separate.outputs[1],add.inputs[0])
            l2ssGroup.links.new(mul.outputs[0],add.inputs[1])
            l2ssGroup.links.new(add.outputs[0],combine.inputs[1])
            l2ssGroup.links.new(separate.outputs[0],combine.inputs[0])
            l2ssGroup.links.new(combine.outputs[0],l2ssGroupO.inputs[0])

        l2ss = create_node(CurMat.nodes,"ShaderNodeGroup",(-625,375), label="l2scrollspeed")
        l2ss.node_tree = l2ssGroup
        CurMat.links.new(vecMix2.outputs[1],l2ss.inputs[0])
        CurMat.links.new(layersScrollSpeed_y.outputs[0],l2ss.inputs[1])
        CurMat.links.new(time.outputs[0],l2ss.inputs[2]) 

        if 'l3scrollspeed' in bpy.data.node_groups.keys():
            l3ssGroup = bpy.data.node_groups['l3scrollspeed']
        else:     
            l3ssGroup = bpy.data.node_groups.new("l3scrollspeed","ShaderNodeTree")
            if vers[0]<4:
                l3ssGroup.inputs.new('NodeSocketVector','l3')
                l3ssGroup.inputs.new('NodeSocketFloat','LayersScrollSpeed.z')
                l3ssGroup.inputs.new('NodeSocketFloat','time')
                l3ssGroup.outputs.new('NodeSocketVector','l3scrollspeed')
            else:
                l3ssGroup.interface.new_socket(name="l3", socket_type='NodeSocketVector', in_out='INPUT')
                l3ssGroup.interface.new_socket(name="LayersScrollSpeed.z", socket_type='NodeSocketFloat', in_out='INPUT')
                l3ssGroup.interface.new_socket(name="time", socket_type='NodeSocketFloat', in_out='INPUT')
                l3ssGroup.interface.new_socket(name="l3scrollspeed", socket_type='NodeSocketVector', in_out='OUTPUT')

            l3ssGroupI = create_node(l3ssGroup.nodes, "NodeGroupInput",(-1000,0))
            l3ssGroupO = create_node(l3ssGroup.nodes, "NodeGroupOutput",(200,0))
            separate = create_node(l3ssGroup.nodes, "ShaderNodeSeparateXYZ",(-800,25))
            mul = create_node(l3ssGroup.nodes, "ShaderNodeMath",(-800,-25),operation="MULTIPLY")
            add = create_node(l3ssGroup.nodes, "ShaderNodeMath",(-600,0))
            combine = create_node(l3ssGroup.nodes, "ShaderNodeCombineXYZ",(-400,0))
            l3ssGroup.links.new(l3ssGroupI.outputs[0],separate.inputs[0])
            l3ssGroup.links.new(l3ssGroupI.outputs[2],mul.inputs[0])
            l3ssGroup.links.new(l3ssGroupI.outputs[1],mul.inputs[1])
            l3ssGroup.links.new(separate.outputs[1],add.inputs[0])
            l3ssGroup.links.new(mul.outputs[0],add.inputs[1])
            l3ssGroup.links.new(add.outputs[0],combine.inputs[1])
            l3ssGroup.links.new(separate.outputs[0],combine.inputs[0])
            l3ssGroup.links.new(combine.outputs[0],l3ssGroupO.inputs[0])

        l3ss = create_node(CurMat.nodes,"ShaderNodeGroup",(-625,325), label="l3scrollspeed")
        l3ss.node_tree = l3ssGroup
        CurMat.links.new(vecMix3.outputs[1],l3ss.inputs[0])
        CurMat.links.new(layersScrollSpeed_z.outputs[0],l3ss.inputs[1])
        CurMat.links.new(time.outputs[0],l3ss.inputs[2]) 

        if 'l4scrollspeed' in bpy.data.node_groups.keys():
            l4ssGroup = bpy.data.node_groups['l4scrollspeed']
        else:     
            l4ssGroup = bpy.data.node_groups.new("l4scrollspeed","ShaderNodeTree")
            if vers[0]<4:
                l4ssGroup.inputs.new('NodeSocketVector','l4')
                l4ssGroup.inputs.new('NodeSocketFloat','LayersScrollSpeed.w')
                l4ssGroup.inputs.new('NodeSocketFloat','time')
                l4ssGroup.outputs.new('NodeSocketVector','l4scrollspeed')
            else:
                l4ssGroup.interface.new_socket(name="l4", socket_type='NodeSocketVector', in_out='INPUT')
                l4ssGroup.interface.new_socket(name="LayersScrollSpeed.w", socket_type='NodeSocketFloat', in_out='INPUT')
                l4ssGroup.interface.new_socket(name="time", socket_type='NodeSocketFloat', in_out='INPUT')
                l4ssGroup.interface.new_socket(name="l4scrollspeed", socket_type='NodeSocketVector', in_out='OUTPUT')

            l4ssGroupI = create_node(l4ssGroup.nodes, "NodeGroupInput",(-1000,0))
            l4ssGroupO = create_node(l4ssGroup.nodes, "NodeGroupOutput",(200,0))
            separate = create_node(l4ssGroup.nodes, "ShaderNodeSeparateXYZ",(-800,25))
            mul = create_node(l4ssGroup.nodes, "ShaderNodeMath",(-800,-25),operation="MULTIPLY")
            add = create_node(l4ssGroup.nodes, "ShaderNodeMath",(-600,0))
            combine = create_node(l4ssGroup.nodes, "ShaderNodeCombineXYZ",(-400,0))
            l4ssGroup.links.new(l4ssGroupI.outputs[0],separate.inputs[0])
            l4ssGroup.links.new(l4ssGroupI.outputs[2],mul.inputs[0])
            l4ssGroup.links.new(l4ssGroupI.outputs[1],mul.inputs[1])
            l4ssGroup.links.new(separate.outputs[1],add.inputs[0])
            l4ssGroup.links.new(mul.outputs[0],add.inputs[1])
            l4ssGroup.links.new(add.outputs[0],combine.inputs[1])
            l4ssGroup.links.new(separate.outputs[0],combine.inputs[0])
            l4ssGroup.links.new(combine.outputs[0],l4ssGroupO.inputs[0])

        l4ss = create_node(CurMat.nodes,"ShaderNodeGroup",(-625,275), label="l4scrollspeed")
        l4ss.node_tree = l4ssGroup
        CurMat.links.new(vecMix4.outputs[1],l4ss.inputs[0])
        CurMat.links.new(layersScrollSpeed_w.outputs[0],l4ss.inputs[1])
        CurMat.links.new(time.outputs[0],l4ss.inputs[2]) 


        # scrollMask
        scrollMask = create_node(CurMat.nodes,"ShaderNodeTexImage",(-950,100), label="ScrollMaskTexture", 
                                 image=scrollMaskImg)
        CurMat.links.new(l1ss.outputs[0],scrollMask.inputs[0]) 

        # scrollMaskMask
        if 'scrollMaskMask' in bpy.data.node_groups.keys():
            scrollMMGroup = bpy.data.node_groups['scrollMaskMask']
        else:     
            scrollMMGroup = bpy.data.node_groups.new("scrollMaskMask","ShaderNodeTree")
            if vers[0]<4:
                scrollMMGroup.inputs.new('NodeSocketColor','scrollMask')
                scrollMMGroup.outputs.new('NodeSocketFloat','scrollMaskMask')
            else:
                scrollMMGroup.interface.new_socket(name="scrollMask", socket_type='NodeSocketColor', in_out='INPUT')
                scrollMMGroup.interface.new_socket(name="scrollMaskMask", socket_type='NodeSocketVector', in_out='OUTPUT')

            scrollMMGroupI = create_node(scrollMMGroup.nodes, "NodeGroupInput",(-1000,0))
            scrollMMGroupO = create_node(scrollMMGroup.nodes, "NodeGroupOutput",(200,0))
            separate = create_node(scrollMMGroup.nodes, "ShaderNodeSeparateXYZ",(-800,0))
            add = create_node(scrollMMGroup.nodes, "ShaderNodeMath",(-650,0))
            scrollMMGroup.links.new(scrollMMGroupI.outputs[0],separate.inputs[0])
            scrollMMGroup.links.new(separate.outputs[0],add.inputs[0])
            scrollMMGroup.links.new(separate.outputs[1],add.inputs[1])
            scrollMMGroup.links.new(add.outputs[0],scrollMMGroupO.inputs[0])

        scrollMaskMask = create_node(CurMat.nodes,"ShaderNodeGroup",(-700,100), label="scrollMaskMask")
        scrollMaskMask.node_tree = scrollMMGroup
        CurMat.links.new(scrollMask.outputs[0],scrollMaskMask.inputs[0]) 

        # scanlineSpeed
        mul5 = create_node(CurMat.nodes, "ShaderNodeMath",(-950,50),operation="MULTIPLY")
        frac2 = create_node(CurMat.nodes, "ShaderNodeMath",(-800,50),operation="FRACT")
        CurMat.links.new(time.outputs[0],mul5.inputs[0]) 
        CurMat.links.new(scanlinesSpeed.outputs[0],mul5.inputs[1]) 
        CurMat.links.new(mul5.outputs[0],frac2.inputs[0]) 


        # finalScrollUV
        if 'finalScrollUV1' in bpy.data.node_groups.keys():
            finalScrollUVGroup = bpy.data.node_groups['finalScrollUV1']
        else:           
            finalScrollUVGroup = bpy.data.node_groups.new("finalScrollUV1","ShaderNodeTree")
            if vers[0]<4:
                finalScrollUVGroup.inputs.new('NodeSocketColor','scrollMask')  
                finalScrollUVGroup.inputs.new('NodeSocketVector','scrollUV1') 
                finalScrollUVGroup.inputs.new('NodeSocketVector','scrollUV1X')
                finalScrollUVGroup.inputs.new('NodeSocketVector','scrollUV2')
                finalScrollUVGroup.inputs.new('NodeSocketVector','scrollUV2X')
                finalScrollUVGroup.inputs.new('NodeSocketVector','ScrollVerticalOrHorizontal')
                finalScrollUVGroup.outputs.new('NodeSocketVector','finalScrollUV1')    
            else:
                finalScrollUVGroup.interface.new_socket(name="scrollMask", socket_type='NodeSocketColor', in_out='INPUT')
                finalScrollUVGroup.interface.new_socket(name="scrollUV1", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUVGroup.interface.new_socket(name="scrollUV1X", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUVGroup.interface.new_socket(name="scrollUV2", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUVGroup.interface.new_socket(name="scrollUV2X", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUVGroup.interface.new_socket(name="ScrollVerticalOrHorizontal", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUVGroup.interface.new_socket(name="finalScrollUV1", socket_type='NodeSocketVector', in_out='OUTPUT')

            finalScrollUVGroupI = create_node(finalScrollUVGroup.nodes, "NodeGroupInput",(-1050,0))
            finalScrollUVGroupO = create_node(finalScrollUVGroup.nodes, "NodeGroupOutput",(-150,0))   
            vecLerp2 = create_node(finalScrollUVGroup.nodes,"ShaderNodeGroup",(-750, 0), label="lerp")
            vecLerp2.node_tree = vecLerpG 
            separate9 = create_node(finalScrollUVGroup.nodes,"ShaderNodeSeparateXYZ",(-900, -50))
            vecLerp3 = create_node(finalScrollUVGroup.nodes,"ShaderNodeGroup",(-750, -100), label="lerp")
            vecLerp3.node_tree = vecLerpG  
            vecLerp4 = create_node(finalScrollUVGroup.nodes,"ShaderNodeGroup",(-600, 0), label="lerp")
            vecLerp4.node_tree = vecLerpG                      
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs['scrollUV2'],vecLerp2.inputs[0])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs['scrollUV1'],vecLerp2.inputs[1])
            finalScrollUVGroup.links.new(separate9.outputs[0],vecLerp2.inputs[2])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs['scrollMask'],separate9.inputs[0])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs['scrollUV2X'],vecLerp3.inputs[0])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs['scrollUV1X'],vecLerp3.inputs[1])
            finalScrollUVGroup.links.new(separate9.outputs[0],vecLerp3.inputs[2])
            finalScrollUVGroup.links.new(vecLerp2.outputs[0],vecLerp4.inputs[0])
            finalScrollUVGroup.links.new(vecLerp3.outputs[0],vecLerp4.inputs[1])
            finalScrollUVGroup.links.new(finalScrollUVGroupI.outputs['ScrollVerticalOrHorizontal'],vecLerp4.inputs[2])
            finalScrollUVGroup.links.new(vecLerp4.outputs[0],finalScrollUVGroupO.inputs[0])


        finalScrollUV1 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1200, -200), label="finalScrollUV1")
        finalScrollUV1.node_tree = finalScrollUVGroup
        CurMat.links.new(scrollUV2.outputs[0],finalScrollUV1.inputs[3])
        CurMat.links.new(scrollUV1.outputs[0],finalScrollUV1.inputs[1])
        CurMat.links.new(scrollMask.outputs[0],finalScrollUV1.inputs[0])
        CurMat.links.new(scrollUV2X.outputs[0],finalScrollUV1.inputs[4])
        CurMat.links.new(scrollUV1X.outputs[0],finalScrollUV1.inputs[2])
        CurMat.links.new(scrollVerticalOrHorizontal.outputs[0],finalScrollUV1.inputs[5])

        # finalScrollUV2
        if 'finalScrollUV2' in bpy.data.node_groups.keys():
            finalScrollUV2Group = bpy.data.node_groups['finalScrollUV2']
        else:           
            finalScrollUV2Group = bpy.data.node_groups.new("finalScrollUV2","ShaderNodeTree") 
            if vers[0]<4:
                finalScrollUV2Group.inputs.new('NodeSocketVector','finalScrollUV1') 
                finalScrollUV2Group.inputs.new('NodeSocketVector','l1')
                finalScrollUV2Group.inputs.new('NodeSocketVector','l2')
                finalScrollUV2Group.outputs.new('NodeSocketVector','finalScrollUV2')   
            else:
                finalScrollUV2Group.interface.new_socket(name="finalScrollUV1", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUV2Group.interface.new_socket(name="l1", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUV2Group.interface.new_socket(name="l2", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUV2Group.interface.new_socket(name="finalScrollUV2", socket_type='NodeSocketVector', in_out='OUTPUT')

            finalScrollUV2GroupI = create_node(finalScrollUV2Group.nodes, "NodeGroupInput",(-1050,0))
            finalScrollUV2GroupO = create_node(finalScrollUV2Group.nodes, "NodeGroupOutput",(-150,0))   
            vecSub = create_node(finalScrollUV2Group.nodes, "ShaderNodeVectorMath",(-900,-25))
            vecAdd = create_node(finalScrollUV2Group.nodes, "ShaderNodeVectorMath",(-750,0))
            finalScrollUV2Group.links.new(finalScrollUV2GroupI.outputs[2],vecSub.inputs[0])
            finalScrollUV2Group.links.new(finalScrollUV2GroupI.outputs[1],vecSub.inputs[1])
            finalScrollUV2Group.links.new(finalScrollUV2GroupI.outputs[0],vecAdd.inputs[0])
            finalScrollUV2Group.links.new(vecSub.outputs[0],vecAdd.inputs[1])
            finalScrollUV2Group.links.new(vecAdd.outputs[0],finalScrollUV2GroupO.inputs[0])

        finalScrollUV2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1200, -250), label="finalScrollUV2")
        finalScrollUV2.node_tree = finalScrollUV2Group
        CurMat.links.new(finalScrollUV1.outputs[0],finalScrollUV2.inputs[0])
        CurMat.links.new(l1ss.outputs[0],finalScrollUV2.inputs[1])
        CurMat.links.new(l2ss.outputs[0],finalScrollUV2.inputs[2])

        # finalScrollUV3
        if 'finalScrollUV3' in bpy.data.node_groups.keys():
            finalScrollUV3Group = bpy.data.node_groups['finalScrollUV3']
        else:           
            finalScrollUV3Group = bpy.data.node_groups.new("finalScrollUV3","ShaderNodeTree") 
            if vers[0]<4:
                finalScrollUV3Group.inputs.new('NodeSocketVector','finalScrollUV1') 
                finalScrollUV3Group.inputs.new('NodeSocketVector','l1')
                finalScrollUV3Group.inputs.new('NodeSocketVector','l3')
                finalScrollUV3Group.outputs.new('NodeSocketVector','finalScrollUV3')   
            else:
                finalScrollUV3Group.interface.new_socket(name="finalScrollUV1", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUV3Group.interface.new_socket(name="l1", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUV3Group.interface.new_socket(name="l3", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUV3Group.interface.new_socket(name="finalScrollUV3", socket_type='NodeSocketVector', in_out='OUTPUT')

            finalScrollUV3GroupI = create_node(finalScrollUV3Group.nodes, "NodeGroupInput",(-1050,0))
            finalScrollUV3GroupO = create_node(finalScrollUV3Group.nodes, "NodeGroupOutput",(-150,0))   
            vecSub = create_node(finalScrollUV3Group.nodes, "ShaderNodeVectorMath",(-900,-25))
            vecAdd = create_node(finalScrollUV3Group.nodes, "ShaderNodeVectorMath",(-750,0))
            finalScrollUV3Group.links.new(finalScrollUV3GroupI.outputs[2],vecSub.inputs[0])
            finalScrollUV3Group.links.new(finalScrollUV3GroupI.outputs[1],vecSub.inputs[1])
            finalScrollUV3Group.links.new(finalScrollUV3GroupI.outputs[0],vecAdd.inputs[0])
            finalScrollUV3Group.links.new(vecSub.outputs[0],vecAdd.inputs[1])
            finalScrollUV3Group.links.new(vecAdd.outputs[0],finalScrollUV3GroupO.inputs[0])

        finalScrollUV3 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1200, -300), label="finalScrollUV3")
        finalScrollUV3.node_tree = finalScrollUV3Group
        CurMat.links.new(finalScrollUV1.outputs[0],finalScrollUV3.inputs[0])
        CurMat.links.new(l1ss.outputs[0],finalScrollUV3.inputs[1])
        CurMat.links.new(l3ss.outputs[0],finalScrollUV3.inputs[2])

        # finalScrollUV4
        if 'finalScrollUV4' in bpy.data.node_groups.keys():
            finalScrollUV4Group = bpy.data.node_groups['finalScrollUV4']
        else:
            finalScrollUV4Group = bpy.data.node_groups.new("finalScrollUV4","ShaderNodeTree") 
            if vers[0]<4:
                finalScrollUV4Group.inputs.new('NodeSocketVector','finalScrollUV1') 
                finalScrollUV4Group.inputs.new('NodeSocketVector','l1')
                finalScrollUV4Group.inputs.new('NodeSocketVector','l4')
                finalScrollUV4Group.outputs.new('NodeSocketVector','finalScrollUV4')   
            else:
                finalScrollUV4Group.interface.new_socket(name="finalScrollUV1", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUV4Group.interface.new_socket(name="l1", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUV4Group.interface.new_socket(name="l4", socket_type='NodeSocketVector', in_out='INPUT')
                finalScrollUV4Group.interface.new_socket(name="finalScrollUV4", socket_type='NodeSocketVector', in_out='OUTPUT')
            finalScrollUV4GroupI = create_node(finalScrollUV4Group.nodes, "NodeGroupInput",(-1050,0))
            finalScrollUV4GroupO = create_node(finalScrollUV4Group.nodes, "NodeGroupOutput",(-150,0))   
            vecSub = create_node(finalScrollUV4Group.nodes, "ShaderNodeVectorMath",(-900,-25))
            vecAdd = create_node(finalScrollUV4Group.nodes, "ShaderNodeVectorMath",(-750,0))
            finalScrollUV4Group.links.new(finalScrollUV4GroupI.outputs[2],vecSub.inputs[0])
            finalScrollUV4Group.links.new(finalScrollUV4GroupI.outputs[1],vecSub.inputs[1])
            finalScrollUV4Group.links.new(finalScrollUV4GroupI.outputs[0],vecAdd.inputs[0])
            finalScrollUV4Group.links.new(vecSub.outputs[0],vecAdd.inputs[1])
            finalScrollUV4Group.links.new(vecAdd.outputs[0],finalScrollUV4GroupO.inputs[0])

        finalScrollUV4 = create_node(CurMat.nodes,"ShaderNodeGroup",(-1200, -350), label="finalScrollUV4")
        finalScrollUV4.node_tree = finalScrollUV4Group
        CurMat.links.new(finalScrollUV1.outputs[0],finalScrollUV4.inputs[0])
        CurMat.links.new(l1ss.outputs[0],finalScrollUV4.inputs[1])
        CurMat.links.new(l4ss.outputs[0],finalScrollUV4.inputs[2])
        
        # l1Sampled 
        parTex = create_node(CurMat.nodes,"ShaderNodeTexImage",(-1050, -100), label="ParalaxTexture", image=parImg)
        parTex2 = create_node(CurMat.nodes,"ShaderNodeTexImage",(-1050, -150), label="ParalaxTexture", image=parImg)
        vecLerp = create_node(CurMat.nodes,"ShaderNodeGroup",(-700, -200), label="lerp")
        vecLerp.node_tree = vecLerpG 
        lerpG = createLerpGroup()
        lerp = create_node(CurMat.nodes,"ShaderNodeGroup",(-700, -250), label="lerp")
        lerp.node_tree = lerpG 
        CurMat.links.new(finalScrollUV1.outputs[0],parTex2.inputs[0])
        CurMat.links.new(l1ss.outputs[0],parTex.inputs[0])
        CurMat.links.new(parTex.outputs[0],vecLerp.inputs[0])
        CurMat.links.new(parTex2.outputs[0],vecLerp.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0],vecLerp.inputs[2])
        CurMat.links.new(parTex.outputs[1],lerp.inputs[0])
        CurMat.links.new(parTex2.outputs[1],lerp.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0],lerp.inputs[2])

        # l2Sampled
        parTex = create_node(CurMat.nodes,"ShaderNodeTexImage",(-1050, -200), label="ParalaxTexture", image=parImg)
        parTex2 = create_node(CurMat.nodes,"ShaderNodeTexImage",(-1050, -250), label="ParalaxTexture", image=parImg)
        vecLerp2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-700, -300), label="lerp")
        vecLerp2.node_tree = vecLerpG 
        lerp2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-700, -350), label="lerp")
        lerp2.node_tree = lerpG 
        CurMat.links.new(finalScrollUV2.outputs[0],parTex2.inputs[0])
        CurMat.links.new(l2ss.outputs[0],parTex.inputs[0])
        CurMat.links.new(parTex.outputs[0],vecLerp2.inputs[0])
        CurMat.links.new(parTex2.outputs[0],vecLerp2.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0],vecLerp2.inputs[2])
        CurMat.links.new(parTex.outputs[1],lerp2.inputs[0])
        CurMat.links.new(parTex2.outputs[1],lerp2.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0],lerp2.inputs[2])

        # l3Sampled
        parTex = create_node(CurMat.nodes,"ShaderNodeTexImage",(-1050, -300), label="ParalaxTexture", image=parImg)
        parTex2 = create_node(CurMat.nodes,"ShaderNodeTexImage",(-1050, -350), label="ParalaxTexture", image=parImg)
        vecLerp3 = create_node(CurMat.nodes,"ShaderNodeGroup",(-700, -400), label="lerp")
        vecLerp3.node_tree = vecLerpG 
        lerp3 = create_node(CurMat.nodes,"ShaderNodeGroup",(-700, -450), label="lerp")
        lerp3.node_tree = lerpG 
        CurMat.links.new(finalScrollUV3.outputs[0],parTex2.inputs[0])
        CurMat.links.new(l3ss.outputs[0],parTex.inputs[0])
        CurMat.links.new(parTex.outputs[0],vecLerp3.inputs[0])
        CurMat.links.new(parTex2.outputs[0],vecLerp3.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0],vecLerp3.inputs[2])
        CurMat.links.new(parTex.outputs[1],lerp3.inputs[0])
        CurMat.links.new(parTex2.outputs[1],lerp3.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0],lerp3.inputs[2])

        # l4Sampled
        parTex = create_node(CurMat.nodes,"ShaderNodeTexImage",(-1050, -400), label="ParalaxTexture", image=parImg)
        parTex2 = create_node(CurMat.nodes,"ShaderNodeTexImage",(-1050, -450), label="ParalaxTexture", image=parImg)
        vecLerp4 = create_node(CurMat.nodes,"ShaderNodeGroup",(-700, -500), label="lerp")
        vecLerp4.node_tree = vecLerpG 
        lerp4 = create_node(CurMat.nodes,"ShaderNodeGroup",(-700, -550), label="lerp")
        lerp4.node_tree = lerpG 
        CurMat.links.new(finalScrollUV4.outputs[0],parTex2.inputs[0])
        CurMat.links.new(l4ss.outputs[0],parTex.inputs[0])
        CurMat.links.new(parTex.outputs[0],vecLerp4.inputs[0])
        CurMat.links.new(parTex2.outputs[0],vecLerp4.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0],vecLerp4.inputs[2])
        CurMat.links.new(parTex.outputs[1],lerp4.inputs[0])
        CurMat.links.new(parTex2.outputs[1],lerp4.inputs[1])
        CurMat.links.new(scrollMaskMask.outputs[0],lerp4.inputs[2])

        # i1
        if 'i1_ps_t' in bpy.data.node_groups.keys():
            i1Group = bpy.data.node_groups['i1_ps_t']
        else:           
            i1Group = bpy.data.node_groups.new("i1_ps_t","ShaderNodeTree") 
            if vers[0]<4:
                i1Group.inputs.new('NodeSocketVector','l1Sampled')
                i1Group.inputs.new('NodeSocketFloat','Alpha')
                i1Group.inputs.new('NodeSocketFloat','IntensityPerLayer.x')
                i1Group.outputs.new('NodeSocketVector','i1')
                i1Group.outputs.new('NodeSocketFloat','Alpha')
            else:
                i1Group.interface.new_socket(name="l1Sampled", socket_type='NodeSocketVector', in_out='INPUT')
                i1Group.interface.new_socket(name="Alpha", socket_type='NodeSocketFloat', in_out='INPUT')
                i1Group.interface.new_socket(name="IntensityPerLayer.x", socket_type='NodeSocketFloat', in_out='INPUT')
                i1Group.interface.new_socket(name="i1", socket_type='NodeSocketVector', in_out='OUTPUT')
                i1Group.interface.new_socket(name="Alpha", socket_type='NodeSocketFloat', in_out='OUTPUT')   

            i1GroupI = create_node(i1Group.nodes, "NodeGroupInput",(-1050,0))
            i1GroupO = create_node(i1Group.nodes, "NodeGroupOutput",(-150,0))   
            vecMul = create_node(i1Group.nodes, "ShaderNodeVectorMath",(-900,0),operation="MULTIPLY")
            mul = create_node(i1Group.nodes, "ShaderNodeMath",(-900,-100),operation="MULTIPLY")
            i1Group.links.new(i1GroupI.outputs['l1Sampled'],vecMul.inputs[0])
            i1Group.links.new(i1GroupI.outputs['Alpha'],mul.inputs[0])
            i1Group.links.new(i1GroupI.outputs['IntensityPerLayer.x'],vecMul.inputs[1])
            i1Group.links.new(i1GroupI.outputs['IntensityPerLayer.x'],mul.inputs[1])
            i1Group.links.new(vecMul.outputs[0],i1GroupO.inputs[0])
            i1Group.links.new(mul.outputs[0],i1GroupO.inputs[1])

        i1 = create_node(CurMat.nodes,"ShaderNodeGroup",(-550, -200), label="i1_ps_t")
        i1.node_tree = i1Group
        CurMat.links.new(vecLerp.outputs[0],i1.inputs[0])
        CurMat.links.new(lerp.outputs[0],i1.inputs[1])
        CurMat.links.new(intensityPerLayer_x.outputs[0],i1.inputs[2])

        # i2
        if 'i2_ps_t' in bpy.data.node_groups.keys():
            i2Group = bpy.data.node_groups['i2_ps_t']
        else:           
            i2Group = bpy.data.node_groups.new("i2_ps_t","ShaderNodeTree") 
            if vers[0]<4:
                i2Group.inputs.new('NodeSocketVector','l2Sampled') 
                i2Group.inputs.new('NodeSocketFloat','Alpha') 
                i2Group.inputs.new('NodeSocketVector','l2') 
                i2Group.inputs.new('NodeSocketVector','finalScrollUV2')
                i2Group.inputs.new('NodeSocketFloat','IntensityPerLayer.y')
                i2Group.inputs.new('NodeSocketFloat','ScanlinesIntensity')
                i2Group.inputs.new('NodeSocketFloat','ScanlinesDensity')
                i2Group.inputs.new('NodeSocketFloat','scanlineSpeed')
                i2Group.inputs.new('NodeSocketFloat','scrollMaskMask')
                i2Group.outputs.new('NodeSocketVector','i2')   
                i2Group.outputs.new('NodeSocketFloat','Alpha')   
            else:
                i2Group.interface.new_socket(name="l2Sampled", socket_type='NodeSocketVector', in_out='INPUT')
                i2Group.interface.new_socket(name="Alpha", socket_type='NodeSocketFloat', in_out='INPUT')
                i2Group.interface.new_socket(name="l2", socket_type='NodeSocketVector', in_out='INPUT')
                i2Group.interface.new_socket(name="finalScrollUV2", socket_type='NodeSocketVector', in_out='INPUT')
                i2Group.interface.new_socket(name="IntensityPerLayer.y", socket_type='NodeSocketFloat', in_out='INPUT')
                i2Group.interface.new_socket(name="ScanlinesIntensity", socket_type='NodeSocketFloat', in_out='INPUT')
                i2Group.interface.new_socket(name="ScanlinesDensity", socket_type='NodeSocketFloat', in_out='INPUT')
                i2Group.interface.new_socket(name="scanlineSpeed", socket_type='NodeSocketFloat', in_out='INPUT')
                i2Group.interface.new_socket(name="scrollMaskMask", socket_type='NodeSocketFloat', in_out='INPUT')
                i2Group.interface.new_socket(name="i2", socket_type='NodeSocketVector', in_out='OUTPUT')
                i2Group.interface.new_socket(name="Alpha", socket_type='NodeSocketFloat', in_out='OUTPUT')     

            i2GroupI = create_node(i2Group.nodes, "NodeGroupInput",(-1050,0))
            i2GroupO = create_node(i2Group.nodes, "NodeGroupOutput",(200,0))   
            vecMul = create_node(i2Group.nodes, "ShaderNodeVectorMath",(-900,0),operation="MULTIPLY")
            separate = create_node(i2Group.nodes, "ShaderNodeSeparateXYZ",(-750,-50))
            add = create_node(i2Group.nodes, "ShaderNodeMath",(-600,-50))
            scanlineG = self.createScanlinesGroup()
            scanline = create_node(i2Group.nodes,"ShaderNodeGroup",(-450,-50), label="scanline")
            scanline.node_tree = scanlineG
            separate2 = create_node(i2Group.nodes, "ShaderNodeSeparateXYZ",(-750,0))
            add2 = create_node(i2Group.nodes, "ShaderNodeMath",(-600,0))
            scanline2 = create_node(i2Group.nodes,"ShaderNodeGroup",(-450,0), label="scanline")
            scanline2.node_tree = scanlineG
            lerpG = createLerpGroup()
            lerp = create_node(i2Group.nodes,"ShaderNodeGroup",(-300,-25), label="lerp")
            lerp.node_tree = lerpG
            lerp2 = create_node(i2Group.nodes,"ShaderNodeGroup",(-150,0), label="lerp")
            lerp2.node_tree = lerpG
            lerp2.inputs[1].default_value = 1
            vecMul2 = create_node(i2Group.nodes, "ShaderNodeVectorMath",(0,0),operation="MULTIPLY")

            i2Group.links.new(i2GroupI.outputs['l2Sampled'],vecMul.inputs[0])
            i2Group.links.new(i2GroupI.outputs['IntensityPerLayer.y'],vecMul.inputs[1])
            i2Group.links.new(i2GroupI.outputs['finalScrollUV2'],separate.inputs[0])
            i2Group.links.new(separate.outputs[1],add.inputs[0])
            i2Group.links.new(i2GroupI.outputs['scanlineSpeed'],add.inputs[1])
            i2Group.links.new(i2GroupI.outputs['ScanlinesDensity'],scanline.inputs[0])
            i2Group.links.new(add.outputs[0],scanline.inputs[1])
            i2Group.links.new(i2GroupI.outputs['l2'],separate2.inputs[0])
            i2Group.links.new(separate2.outputs[1],add2.inputs[0])
            i2Group.links.new(i2GroupI.outputs['scanlineSpeed'],add2.inputs[1])
            i2Group.links.new(i2GroupI.outputs['ScanlinesDensity'],scanline2.inputs[0])
            i2Group.links.new(scanline.outputs[0],lerp.inputs[0])
            i2Group.links.new(scanline2.outputs[0],lerp.inputs[1])
            i2Group.links.new(i2GroupI.outputs['scrollMaskMask'],lerp.inputs[2])
            i2Group.links.new(i2GroupI.outputs['ScanlinesIntensity'],lerp2.inputs[0])
            i2Group.links.new(lerp.outputs[0],lerp2.inputs[2])
            i2Group.links.new(vecMul.outputs[0],vecMul2.inputs[0])
            i2Group.links.new(lerp2.outputs[0],vecMul2.inputs[1])
            i2Group.links.new(vecMul2.outputs[0],i2GroupO.inputs[0])
            # alpha
            mul = create_node(i2Group.nodes, "ShaderNodeMath",(-900,-150),operation="MULTIPLY")
            mul2 = create_node(i2Group.nodes, "ShaderNodeMath",(0,-150),operation="MULTIPLY")
            i2Group.links.new(i2GroupI.outputs['Alpha'],mul.inputs[0])
            i2Group.links.new(i2GroupI.outputs['IntensityPerLayer.y'],mul.inputs[1])
            i2Group.links.new(mul.outputs[0],mul2.inputs[0])
            i2Group.links.new(lerp2.outputs[0],mul2.inputs[1])
            i2Group.links.new(mul2.outputs[0],i2GroupO.inputs[1])
            

        i2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-550, -275), label="i2_ps_t")
        i2.node_tree = i2Group
        CurMat.links.new(vecLerp2.outputs[0],i2.inputs[0])
        CurMat.links.new(lerp2.outputs[0],i2.inputs[1])
        CurMat.links.new(l2ss.outputs[0],i2.inputs[2])
        CurMat.links.new(finalScrollUV2.outputs[0],i2.inputs[3])
        CurMat.links.new(intensityPerLayer_y.outputs[0],i2.inputs[4])
        CurMat.links.new(scanlinesIntensity.outputs[0],i2.inputs[5])
        CurMat.links.new(scanlinesDensity.outputs[0],i2.inputs[6])
        CurMat.links.new(frac2.outputs[0],i2.inputs[7])
        CurMat.links.new(scrollMaskMask.outputs[0],i2.inputs[8])


        # i3
        # TODO NoPostORPost
        if 'i3_ps_t' in bpy.data.node_groups.keys():
            i3Group = bpy.data.node_groups['i3_ps_t']
        else:
            i3Group = bpy.data.node_groups.new("i3_ps_t","ShaderNodeTree") 
            if vers[0]<4:
                i3Group.inputs.new('NodeSocketVector','l3Sampled') 
                i3Group.inputs.new('NodeSocketFloat','Alpha') 
                i3Group.inputs.new('NodeSocketVector','l3') 
                i3Group.inputs.new('NodeSocketVector','finalScrollUV3')
                i3Group.inputs.new('NodeSocketFloat','IntensityPerLayer.z')
                i3Group.inputs.new('NodeSocketFloat','ScanlinesIntensity')
                i3Group.inputs.new('NodeSocketFloat','ScanlinesDensity')
                i3Group.inputs.new('NodeSocketFloat','scanlineSpeed')
                i3Group.inputs.new('NodeSocketFloat','scrollMaskMask')
                i3Group.outputs.new('NodeSocketVector','i3')   
                i3Group.outputs.new('NodeSocketFloat','Alpha') 
            else:
                i3Group.interface.new_socket(name="l3Sampled", socket_type='NodeSocketVector', in_out='INPUT')
                i3Group.interface.new_socket(name="Alpha", socket_type='NodeSocketFloat', in_out='INPUT')
                i3Group.interface.new_socket(name="l3", socket_type='NodeSocketVector', in_out='INPUT')
                i3Group.interface.new_socket(name="finalScrollUV3", socket_type='NodeSocketVector', in_out='INPUT')
                i3Group.interface.new_socket(name="IntensityPerLayer.z", socket_type='NodeSocketFloat', in_out='INPUT')
                i3Group.interface.new_socket(name="ScanlinesIntensity", socket_type='NodeSocketFloat', in_out='INPUT')
                i3Group.interface.new_socket(name="ScanlinesDensity", socket_type='NodeSocketFloat', in_out='INPUT')
                i3Group.interface.new_socket(name="scanlineSpeed", socket_type='NodeSocketFloat', in_out='INPUT')
                i3Group.interface.new_socket(name="scrollMaskMask", socket_type='NodeSocketFloat', in_out='INPUT')
                i3Group.interface.new_socket(name="i3", socket_type='NodeSocketVector', in_out='OUTPUT')
                i3Group.interface.new_socket(name="Alpha", socket_type='NodeSocketFloat', in_out='OUTPUT')     
            
            i3GroupI = create_node(i3Group.nodes, "NodeGroupInput",(-1050,0))
            i3GroupO = create_node(i3Group.nodes, "NodeGroupOutput",(200,0))   
            vecMul = create_node(i3Group.nodes, "ShaderNodeVectorMath",(-900,0),operation="MULTIPLY")
            separate = create_node(i3Group.nodes, "ShaderNodeSeparateXYZ",(-750,-50))
            add = create_node(i3Group.nodes, "ShaderNodeMath",(-600,-50))
            scanlineG = self.createScanlinesGroup()
            scanline = create_node(i3Group.nodes,"ShaderNodeGroup",(-450,-50), label="scanline")
            scanline.node_tree = scanlineG
            separate2 = create_node(i3Group.nodes, "ShaderNodeSeparateXYZ",(-750,0))
            add2 = create_node(i3Group.nodes, "ShaderNodeMath",(-600,0))
            scanline2 = create_node(i3Group.nodes,"ShaderNodeGroup",(-450,0), label="scanline")
            scanline2.node_tree = scanlineG
            lerpG = createLerpGroup()
            lerp = create_node(i3Group.nodes,"ShaderNodeGroup",(-300,-25), label="lerp")
            lerp.node_tree = lerpG
            lerp2 = create_node(i3Group.nodes,"ShaderNodeGroup",(-150,0), label="lerp")
            lerp2.node_tree = lerpG
            lerp2.inputs[1].default_value = 1
            vecMul2 = create_node(i3Group.nodes, "ShaderNodeVectorMath",(0,0),operation="MULTIPLY")
            mul = create_node(i3Group.nodes, "ShaderNodeMath",(-900,-150),operation="MULTIPLY")
            mul2 = create_node(i3Group.nodes, "ShaderNodeMath",(0,-150),operation="MULTIPLY")
            i3Group.links.new(i3GroupI.outputs['l3Sampled'],vecMul.inputs[0])
            i3Group.links.new(i3GroupI.outputs['IntensityPerLayer.z'],vecMul.inputs[1])
            i3Group.links.new(i3GroupI.outputs['finalScrollUV3'],separate.inputs[0])
            i3Group.links.new(separate.outputs[1],add.inputs[0])
            i3Group.links.new(i3GroupI.outputs['scanlineSpeed'],add.inputs[1])
            i3Group.links.new(i3GroupI.outputs['ScanlinesDensity'],scanline.inputs[0])
            i3Group.links.new(add.outputs[0],scanline.inputs[1])
            i3Group.links.new(i3GroupI.outputs['l3'],separate2.inputs[0])
            i3Group.links.new(separate2.outputs[1],add2.inputs[0])
            i3Group.links.new(i3GroupI.outputs['scanlineSpeed'],add2.inputs[1])
            i3Group.links.new(i3GroupI.outputs['ScanlinesDensity'],scanline2.inputs[0])
            i3Group.links.new(scanline.outputs[0],lerp.inputs[0])
            i3Group.links.new(scanline2.outputs[0],lerp.inputs[1])
            i3Group.links.new(i3GroupI.outputs['scrollMaskMask'],lerp.inputs[2])
            i3Group.links.new(i3GroupI.outputs['ScanlinesIntensity'],lerp2.inputs[0])
            i3Group.links.new(lerp.outputs[0],lerp2.inputs[2])
            i3Group.links.new(vecMul.outputs[0],vecMul2.inputs[0])
            i3Group.links.new(lerp2.outputs[0],vecMul2.inputs[1])
            i3Group.links.new(vecMul2.outputs[0],i3GroupO.inputs[0])
            # alpha
            mul = create_node(i3Group.nodes, "ShaderNodeMath",(-900,-150),operation="MULTIPLY")
            mul2 = create_node(i3Group.nodes, "ShaderNodeMath",(0,-150),operation="MULTIPLY")
            i3Group.links.new(i3GroupI.outputs['Alpha'],mul.inputs[0])
            i3Group.links.new(i3GroupI.outputs['IntensityPerLayer.z'],mul.inputs[1])
            i3Group.links.new(mul.outputs[0],mul2.inputs[0])
            i3Group.links.new(lerp2.outputs[0],mul2.inputs[1])
            i3Group.links.new(mul2.outputs[0],i3GroupO.inputs[1])
            

        i3 = create_node(CurMat.nodes,"ShaderNodeGroup",(-550, -375), label="i3_ps_t")
        i3.node_tree = i3Group
        CurMat.links.new(vecLerp3.outputs[0],i3.inputs[0])
        CurMat.links.new(lerp3.outputs[0],i3.inputs[1])
        CurMat.links.new(l3ss.outputs[0],i3.inputs[2])
        CurMat.links.new(finalScrollUV3.outputs[0],i3.inputs[3])
        CurMat.links.new(intensityPerLayer_z.outputs[0],i3.inputs[4])
        CurMat.links.new(scanlinesIntensity.outputs[0],i3.inputs[5])
        CurMat.links.new(scanlinesDensity.outputs[0],i3.inputs[6])
        CurMat.links.new(frac2.outputs[0],i3.inputs[7])
        CurMat.links.new(scrollMaskMask.outputs[0],i3.inputs[8])

        # i4
        if 'i4_ps_t' in bpy.data.node_groups.keys():
            i4Group = bpy.data.node_groups['i4_ps_t']
        else:           
            i4Group = bpy.data.node_groups.new("i4_ps_t","ShaderNodeTree") 
            if vers[0]<4:
                i4Group.inputs.new('NodeSocketVector','l4Sampled') 
                i4Group.inputs.new('NodeSocketFloat','Alpha') 
                i4Group.inputs.new('NodeSocketVector','l4') 
                i4Group.inputs.new('NodeSocketVector','finalScrollUV4')
                i4Group.inputs.new('NodeSocketFloat','IntensityPerLayer.w')
                i4Group.inputs.new('NodeSocketFloat','ScanlinesIntensity')
                i4Group.inputs.new('NodeSocketFloat','ScanlinesDensity')
                i4Group.inputs.new('NodeSocketFloat','scanlineSpeed')
                i4Group.inputs.new('NodeSocketFloat','scrollMaskMask')
                i4Group.outputs.new('NodeSocketVector','i4')   
                i4Group.outputs.new('NodeSocketFloat','Alpha') 
            else:
                i4Group.interface.new_socket(name="l4Sampled", socket_type='NodeSocketVector', in_out='INPUT')
                i4Group.interface.new_socket(name="Alpha", socket_type='NodeSocketFloat', in_out='INPUT')
                i4Group.interface.new_socket(name="l4", socket_type='NodeSocketVector', in_out='INPUT')
                i4Group.interface.new_socket(name="finalScrollUV4", socket_type='NodeSocketVector', in_out='INPUT')
                i4Group.interface.new_socket(name="IntensityPerLayer.w", socket_type='NodeSocketFloat', in_out='INPUT')
                i4Group.interface.new_socket(name="ScanlinesIntensity", socket_type='NodeSocketFloat', in_out='INPUT')
                i4Group.interface.new_socket(name="ScanlinesDensity", socket_type='NodeSocketFloat', in_out='INPUT')
                i4Group.interface.new_socket(name="scanlineSpeed", socket_type='NodeSocketFloat', in_out='INPUT')
                i4Group.interface.new_socket(name="scrollMaskMask", socket_type='NodeSocketFloat', in_out='INPUT')
                i4Group.interface.new_socket(name="i4", socket_type='NodeSocketVector', in_out='OUTPUT')
                i4Group.interface.new_socket(name="Alpha", socket_type='NodeSocketFloat', in_out='OUTPUT')

            i4GroupI = create_node(i4Group.nodes, "NodeGroupInput",(-1050,0))
            i4GroupO = create_node(i4Group.nodes, "NodeGroupOutput",(200,0))   
            vecMul = create_node(i4Group.nodes, "ShaderNodeVectorMath",(-900,0),operation="MULTIPLY")
            separate = create_node(i4Group.nodes, "ShaderNodeSeparateXYZ",(-750,-50))
            add = create_node(i4Group.nodes, "ShaderNodeMath",(-600,-50))
            scanlineG = self.createScanlinesGroup()
            scanline = create_node(i4Group.nodes,"ShaderNodeGroup",(-450,-50), label="scanline")
            scanline.node_tree = scanlineG
            separate2 = create_node(i4Group.nodes, "ShaderNodeSeparateXYZ",(-750,0))
            add2 = create_node(i4Group.nodes, "ShaderNodeMath",(-600,0))
            scanline2 = create_node(i4Group.nodes,"ShaderNodeGroup",(-450,0), label="scanline")
            scanline2.node_tree = scanlineG
            lerpG = createLerpGroup()
            lerp = create_node(i4Group.nodes,"ShaderNodeGroup",(-300,-25), label="lerp")
            lerp.node_tree = lerpG
            lerp2 = create_node(i4Group.nodes,"ShaderNodeGroup",(-150,0), label="lerp")
            lerp2.node_tree = lerpG
            lerp2.inputs[1].default_value = 1
            vecMul2 = create_node(i4Group.nodes, "ShaderNodeVectorMath",(0,0),operation="MULTIPLY")

            i4Group.links.new(i4GroupI.outputs['l4Sampled'],vecMul.inputs[0])
            i4Group.links.new(i4GroupI.outputs['IntensityPerLayer.w'],vecMul.inputs[1])
            i4Group.links.new(i4GroupI.outputs['finalScrollUV4'],separate.inputs[0])
            i4Group.links.new(separate.outputs[1],add.inputs[0])
            i4Group.links.new(i4GroupI.outputs['scanlineSpeed'],add.inputs[1])
            i4Group.links.new(i4GroupI.outputs['ScanlinesDensity'],scanline.inputs[0])
            i4Group.links.new(add.outputs[0],scanline.inputs[1])
            i4Group.links.new(i4GroupI.outputs['l4'],separate2.inputs[0])
            i4Group.links.new(separate2.outputs[1],add2.inputs[0])
            i4Group.links.new(i4GroupI.outputs['scanlineSpeed'],add2.inputs[1])
            i4Group.links.new(i4GroupI.outputs['ScanlinesDensity'],scanline2.inputs[0])
            i4Group.links.new(scanline.outputs[0],lerp.inputs[0])
            i4Group.links.new(scanline2.outputs[0],lerp.inputs[1])
            i4Group.links.new(i4GroupI.outputs['scrollMaskMask'],lerp.inputs[2])
            i4Group.links.new(i4GroupI.outputs['ScanlinesIntensity'],lerp2.inputs[0])
            i4Group.links.new(lerp.outputs[0],lerp2.inputs[2])
            i4Group.links.new(vecMul.outputs[0],vecMul2.inputs[0])
            i4Group.links.new(lerp2.outputs[0],vecMul2.inputs[1])
            i4Group.links.new(vecMul2.outputs[0],i4GroupO.inputs[0])
            # alpha
            mul = create_node(i3Group.nodes, "ShaderNodeMath",(-900,-150),operation="MULTIPLY")
            mul2 = create_node(i3Group.nodes, "ShaderNodeMath",(0,-150),operation="MULTIPLY")
            i4Group.links.new(i4GroupI.outputs['Alpha'],mul.inputs[0])
            i4Group.links.new(i4GroupI.outputs['IntensityPerLayer.w'],mul.inputs[1])
            i4Group.links.new(mul.outputs[0],mul2.inputs[0])
            i4Group.links.new(lerp2.outputs[0],mul2.inputs[1])
            i4Group.links.new(mul2.outputs[0],i4GroupO.inputs[1])
            

        i4 = create_node(CurMat.nodes,"ShaderNodeGroup",(-550, -475), label="i4_ps_t")
        i4.node_tree = i4Group
        CurMat.links.new(vecLerp4.outputs[0],i4.inputs[0])
        CurMat.links.new(lerp4.outputs[0],i4.inputs[1])
        CurMat.links.new(l4ss.outputs[0],i4.inputs[2])
        CurMat.links.new(finalScrollUV4.outputs[0],i4.inputs[3])
        CurMat.links.new(intensityPerLayer_w.outputs[0],i4.inputs[4])
        CurMat.links.new(scanlinesIntensity.outputs[0],i4.inputs[5])
        CurMat.links.new(scanlinesDensity.outputs[0],i4.inputs[6])
        CurMat.links.new(frac2.outputs[0],i4.inputs[7])
        CurMat.links.new(scrollMaskMask.outputs[0],i4.inputs[8])
        
    # TODO AdditiveOrAlphaBlened

        # m1
        if 'm1' in bpy.data.node_groups.keys():
            m1Group = bpy.data.node_groups['m1']
        else:      
            m1Group = bpy.data.node_groups.new("m1","ShaderNodeTree")
            if vers[0]<4:
                m1Group.inputs.new('NodeSocketVector','i4')
                m1Group.inputs.new('NodeSocketVector','i3')
                m1Group.inputs.new('NodeSocketFloat','i4.a')
                m1Group.inputs.new('NodeSocketFloat','i3.a')
                m1Group.outputs.new('NodeSocketVector','m1')
                m1Group.outputs.new('NodeSocketFloat','Alpha')
            else:
                m1Group.interface.new_socket(name="i4", socket_type='NodeSocketVector', in_out='INPUT')
                m1Group.interface.new_socket(name="i3", socket_type='NodeSocketVector', in_out='INPUT')
                m1Group.interface.new_socket(name="i4.a", socket_type='NodeSocketFloat', in_out='INPUT')
                m1Group.interface.new_socket(name="i3.a", socket_type='NodeSocketFloat', in_out='INPUT')
                m1Group.interface.new_socket(name="m1", socket_type='NodeSocketVector', in_out='OUTPUT')
                m1Group.interface.new_socket(name="Alpha", socket_type='NodeSocketFloat', in_out='OUTPUT')    

            m1GroupI = create_node(m1Group.nodes, "NodeGroupInput",(-1050,0))
            m1GroupO = create_node(m1Group.nodes, "NodeGroupOutput",(300,0))
            vecSub2 =  create_node(m1Group.nodes,"ShaderNodeVectorMath",(-900,25),operation = "SUBTRACT")
            vecSub2.inputs[0].default_value = (1,1,1)
            vecSub3 =  create_node(m1Group.nodes,"ShaderNodeVectorMath",(-900,-25),operation = "SUBTRACT")
            vecSub3.inputs[0].default_value = (1,1,1)
            vecMul18 = create_node(m1Group.nodes,"ShaderNodeVectorMath",(-750,0),operation = "MULTIPLY")
            vecSub4 =  create_node(m1Group.nodes,"ShaderNodeVectorMath",(-600,0),operation = "SUBTRACT")
            vecSub4.inputs[0].default_value = (1,1,1)

            m1Group.links.new(m1GroupI.outputs[0],vecSub2.inputs[1])
            m1Group.links.new(m1GroupI.outputs[1],vecSub3.inputs[1])
            m1Group.links.new(vecSub2.outputs[0],vecMul18.inputs[0])
            m1Group.links.new(vecSub3.outputs[0],vecMul18.inputs[1])
            m1Group.links.new(vecMul18.outputs[0],vecSub4.inputs[1])
            m1Group.links.new(vecSub4.outputs[0],m1GroupO.inputs[0])
            # alpha
            sub = create_node(m1Group.nodes,"ShaderNodeMath",(-900,-150),operation = "SUBTRACT")
            sub.inputs[0].default_value = 1
            sub2 = create_node(m1Group.nodes,"ShaderNodeMath",(-900,-200),operation = "SUBTRACT")
            sub2.inputs[0].default_value = 1
            mul = create_node(m1Group.nodes,"ShaderNodeMath",(-750,-150),operation = "MULTIPLY")
            sub3 = create_node(m1Group.nodes,"ShaderNodeMath",(-600,-150),operation = "SUBTRACT")
            sub3.inputs[0].default_value = 1
            m1Group.links.new(m1GroupI.outputs[2],sub.inputs[0])
            m1Group.links.new(m1GroupI.outputs[3],sub2.inputs[0])
            m1Group.links.new(sub.outputs[0],mul.inputs[0])
            m1Group.links.new(sub2.outputs[0],mul.inputs[1])
            m1Group.links.new(mul.outputs[0],sub3.inputs[1])
            m1Group.links.new(sub3.outputs[0],m1GroupO.inputs[1])

        m1 = create_node(CurMat.nodes,"ShaderNodeGroup",(-550, -500), label="m1")
        m1.node_tree = m1Group
        CurMat.links.new(i4.outputs[0],m1.inputs[0])
        CurMat.links.new(i3.outputs[0],m1.inputs[1])
        CurMat.links.new(i4.outputs[1],m1.inputs[2])
        CurMat.links.new(i3.outputs[1],m1.inputs[3])

        # m2
        if 'parallax_screen_trans_m2' in bpy.data.node_groups.keys():
            m2Group = bpy.data.node_groups['parallax_screen_trans_m2']
        else:           
            m2Group = bpy.data.node_groups.new("parallax_screen_trans_m2","ShaderNodeTree")
            if vers[0]<4:
                m2Group.inputs.new('NodeSocketVector','m1')
                m2Group.inputs.new('NodeSocketVector','i2')    
                m2Group.inputs.new('NodeSocketFloat','m1.a')
                m2Group.inputs.new('NodeSocketFloat','i2.a')    
                m2Group.outputs.new('NodeSocketVector','m2')
                m2Group.outputs.new('NodeSocketFloat','Alpha')
            else:
                m2Group.interface.new_socket(name="m1", socket_type='NodeSocketVector', in_out='INPUT')
                m2Group.interface.new_socket(name="i2", socket_type='NodeSocketVector', in_out='INPUT')
                m2Group.interface.new_socket(name="m1.a", socket_type='NodeSocketFloat', in_out='INPUT')
                m2Group.interface.new_socket(name="i2.a", socket_type='NodeSocketFloat', in_out='INPUT')
                m2Group.interface.new_socket(name="m2", socket_type='NodeSocketVector', in_out='OUTPUT')
                m2Group.interface.new_socket(name="Alpha", socket_type='NodeSocketFloat', in_out='OUTPUT')

            m2GroupI = create_node(m2Group.nodes, "NodeGroupInput",(-1050,0))
            m2GroupO = create_node(m2Group.nodes, "NodeGroupOutput",(300,0))   
            vecSub5 =  create_node(m2Group.nodes,"ShaderNodeVectorMath",(-900,25),operation = "SUBTRACT")
            vecSub5.inputs[0].default_value = (1,1,1)
            vecSub6 =  create_node(m2Group.nodes,"ShaderNodeVectorMath",(-900,-25),operation = "SUBTRACT")
            vecSub6.inputs[0].default_value = (1,1,1)
            vecMul19 = create_node(m2Group.nodes,"ShaderNodeVectorMath",(-750,0),operation = "MULTIPLY")
            vecSub7 =  create_node(m2Group.nodes,"ShaderNodeVectorMath",(-600,0),operation = "SUBTRACT")
            vecSub7.inputs[0].default_value = (1,1,1)
            m2Group.links.new(m2GroupI.outputs[0],vecSub5.inputs[1])
            m2Group.links.new(m2GroupI.outputs[1],vecSub6.inputs[1])
            m2Group.links.new(vecSub5.outputs[0],vecMul19.inputs[0])
            m2Group.links.new(vecSub6.outputs[0],vecMul19.inputs[1])
            m2Group.links.new(vecMul19.outputs[0],vecSub7.inputs[1])
            m2Group.links.new(vecSub7.outputs[0],m2GroupO.inputs[0])
            # alpha
            sub = create_node(m2Group.nodes,"ShaderNodeMath",(-900,-150),operation = "SUBTRACT")
            sub.inputs[0].default_value = 1
            sub2 = create_node(m2Group.nodes,"ShaderNodeMath",(-900,-200),operation = "SUBTRACT")
            sub2.inputs[0].default_value = 1
            mul = create_node(m2Group.nodes,"ShaderNodeMath",(-750,-150),operation = "MULTIPLY")
            sub3 = create_node(m2Group.nodes,"ShaderNodeMath",(-600,-150),operation = "SUBTRACT")
            sub3.inputs[0].default_value = 1
            m2Group.links.new(m2GroupI.outputs[2],sub.inputs[0])
            m2Group.links.new(m2GroupI.outputs[3],sub2.inputs[0])
            m2Group.links.new(sub.outputs[0],mul.inputs[0])
            m2Group.links.new(sub2.outputs[0],mul.inputs[1])
            m2Group.links.new(mul.outputs[0],sub3.inputs[1])
            m2Group.links.new(sub3.outputs[0],m2GroupO.inputs[1])
        m2 = create_node(CurMat.nodes,"ShaderNodeGroup",(-550,-550), label="m2")
        m2.node_tree = m2Group 
        CurMat.links.new(m1.outputs[0],m2.inputs[0])
        CurMat.links.new(i2.outputs[0],m2.inputs[1])
        if len(m2.outputs) > 1:
            CurMat.links.new(m1.outputs[1],m2.inputs[2])
            CurMat.links.new(i2.outputs[1],m2.inputs[3])

        # m3
        if 'parallax_screen_trans_m3' in bpy.data.node_groups.keys():
            m3Group = bpy.data.node_groups['parallax_screen_trans_m3']
        else:
            m3Group = bpy.data.node_groups.new("parallax_screen_trans_m3","ShaderNodeTree")
            if vers[0]<4:
                m3Group.inputs.new('NodeSocketVector','m2')
                m3Group.inputs.new('NodeSocketVector','i1')    
                m3Group.inputs.new('NodeSocketFloat','m2.a')
                m3Group.inputs.new('NodeSocketFloat','i1.a')  
                m3Group.outputs.new('NodeSocketVector','m3')
                m3Group.outputs.new('NodeSocketFloat','Alpha')
            else:
                m3Group.interface.new_socket(name="m2", socket_type='NodeSocketVector', in_out='INPUT')
                m3Group.interface.new_socket(name="i1", socket_type='NodeSocketVector', in_out='INPUT')
                m3Group.interface.new_socket(name="m2.a", socket_type='NodeSocketFloat', in_out='INPUT')
                m3Group.interface.new_socket(name="i1.a", socket_type='NodeSocketFloat', in_out='INPUT')
                m3Group.interface.new_socket(name="m3", socket_type='NodeSocketVector', in_out='OUTPUT')
                m3Group.interface.new_socket(name="Alpha", socket_type='NodeSocketFloat', in_out='OUTPUT')

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

            # alpha
            sub = create_node(m3Group.nodes,"ShaderNodeMath",(-900,-150),operation = "SUBTRACT")
            sub.inputs[0].default_value = 1
            sub2 = create_node(m3Group.nodes,"ShaderNodeMath",(-900,-200),operation = "SUBTRACT")
            sub2.inputs[0].default_value = 1
            mul = create_node(m3Group.nodes,"ShaderNodeMath",(-750,-150),operation = "MULTIPLY")
            sub3 = create_node(m3Group.nodes,"ShaderNodeMath",(-600,-150),operation = "SUBTRACT")
            sub3.inputs[0].default_value = 1
            m3Group.links.new(m3GroupI.outputs[2],sub.inputs[0])
            m3Group.links.new(m3GroupI.outputs[3],sub2.inputs[0])
            m3Group.links.new(sub.outputs[0],mul.inputs[0])
            m3Group.links.new(sub2.outputs[0],mul.inputs[1])
            m3Group.links.new(mul.outputs[0],sub3.inputs[1])
            m3Group.links.new(sub3.outputs[0],m3GroupO.inputs[1])
        m3 = create_node(CurMat.nodes,"ShaderNodeGroup",(-550,-600), label="m3")
        m3.node_tree = m3Group 
        CurMat.links.new(m2.outputs[0],m3.inputs[0])
        CurMat.links.new(i1.outputs[0],m3.inputs[1])
        if len(m2.outputs) > 1:
            CurMat.links.new(m2.outputs[1],m3.inputs[2])
        CurMat.links.new(i1.outputs[1],m3.inputs[3])


        # if EdgesMask > 0
        greater_than = create_node(CurMat.nodes,"ShaderNodeMath",(-550,-800),operation="GREATER_THAN")
        greater_than.inputs[1].default_value = 0
        mix = create_node(CurMat.nodes,"ShaderNodeMix",(-400,-800))
        mix.inputs[2].default_value = 1.0
        CurMat.links.new(edgesMaskValue.outputs[0],greater_than.inputs[0])
        CurMat.links.new(greater_than.outputs[0],mix.inputs[0])

        # edgesMask
        if 'edgesMask' in bpy.data.node_groups.keys():
            edgesMaskGroup = bpy.data.node_groups['edgesMask']
        else:
            edgesMaskGroup = bpy.data.node_groups.new("edgesMask","ShaderNodeTree")
            if vers[0]<4:
                edgesMaskGroup.inputs.new('NodeSocketVector','UV')
                edgesMaskGroup.inputs.new('NodeSocketFloat','EdgesMask')
                edgesMaskGroup.outputs.new('NodeSocketFloat','edgesMask')
            else:
                edgesMaskGroup.interface.new_socket(name="UV", socket_type='NodeSocketVector', in_out='INPUT')
                edgesMaskGroup.interface.new_socket(name="EdgesMask", socket_type='NodeSocketFloat', in_out='INPUT')
                edgesMaskGroup.interface.new_socket(name="edgesMask", socket_type='NodeSocketFloat', in_out='OUTPUT')

            edgesMaskGroupI = create_node(edgesMaskGroup.nodes, "NodeGroupInput",(-1050,0))
            edgesMaskGroupO = create_node(edgesMaskGroup.nodes, "NodeGroupOutput",(300,0))   
            separate = create_node(edgesMaskGroup.nodes,"ShaderNodeSeparateXYZ",(-900, 0))
            sub = create_node(edgesMaskGroup.nodes,"ShaderNodeMath",(-750,0),operation = "SUBTRACT")
            sub.inputs[1].default_value = .5
            mul = create_node(edgesMaskGroup.nodes,"ShaderNodeMath",(-600,0),operation = "MULTIPLY")
            mul.inputs[1].default_value = 2
            absolute = create_node(edgesMaskGroup.nodes,"ShaderNodeMath",(-450,0),operation = "ABSOLUTE")
            sub2 = create_node(edgesMaskGroup.nodes,"ShaderNodeMath",(-300,0),operation = "SUBTRACT")
            sub2.inputs[0].default_value = 1
            sub2.use_clamp = True
            mul2 = create_node(edgesMaskGroup.nodes,"ShaderNodeMath",(-150,0),operation = "MULTIPLY")

            edgesMaskGroup.links.new(edgesMaskGroupI.outputs[0],separate.inputs[0])
            edgesMaskGroup.links.new(separate.outputs[1],sub.inputs[0])
            edgesMaskGroup.links.new(sub.outputs[0],mul.inputs[0])
            edgesMaskGroup.links.new(mul.outputs[0],absolute.inputs[0])
            edgesMaskGroup.links.new(absolute.outputs[0],sub2.inputs[1])
            edgesMaskGroup.links.new(sub2.outputs[0],mul2.inputs[0])
            edgesMaskGroup.links.new(edgesMaskGroupI.outputs[1],mul2.inputs[1])
            edgesMaskGroup.links.new(mul2.outputs[0],edgesMaskGroupO.inputs[0])

        edgesMask = create_node(CurMat.nodes,"ShaderNodeGroup",(-550,-850), label="edgesMask")
        edgesMask.node_tree = edgesMaskGroup
        CurMat.links.new(UVMap.outputs[0],edgesMask.inputs[0])
        CurMat.links.new(edgesMaskValue.outputs[0],edgesMask.inputs[1])
        CurMat.links.new(edgesMask.outputs[0],mix.inputs[3])
        

        # HSV
        if 'hsv' in bpy.data.node_groups.keys():
            hsvGroup = bpy.data.node_groups['hsv']
        else:  
            hsvGroup = bpy.data.node_groups.new("hsv","ShaderNodeTree") 
            if vers[0]<4:
                hsvGroup.inputs.new('NodeSocketVector','m3')
                hsvGroup.inputs.new('NodeSocketVector','scroll1')
                hsvGroup.inputs.new('NodeSocketFloat','TexHSVControl.x')
                hsvGroup.inputs.new('NodeSocketFloat','TexHSVControl.y')
                hsvGroup.inputs.new('NodeSocketFloat','TexHSVControl.z')
                hsvGroup.inputs.new('NodeSocketVector','scrollMask')
                hsvGroup.inputs.new('NodeSocketFloat','EdgesMask')
                hsvGroup.outputs.new('NodeSocketColor','color')
            else: 
                hsvGroup.interface.new_socket(name="m3", socket_type='NodeSocketVector', in_out='INPUT')
                hsvGroup.interface.new_socket(name="scroll1", socket_type='NodeSocketVector', in_out='INPUT')
                hsvGroup.interface.new_socket(name="TexHSVControl.x", socket_type='NodeSocketFloat', in_out='INPUT')
                hsvGroup.interface.new_socket(name="TexHSVControl.y", socket_type='NodeSocketFloat', in_out='INPUT')
                hsvGroup.interface.new_socket(name="TexHSVControl.z", socket_type='NodeSocketFloat', in_out='INPUT')
                hsvGroup.interface.new_socket(name="scrollMask", socket_type='NodeSocketVector', in_out='INPUT')
                hsvGroup.interface.new_socket(name="EdgesMask", socket_type='NodeSocketFloat', in_out='INPUT')
                hsvGroup.interface.new_socket(name="color", socket_type='NodeSocketColor', in_out='OUTPUT')

            hsvGroupI = create_node(hsvGroup.nodes, "NodeGroupInput",(-1650,0))
            hsvGroupO = create_node(hsvGroup.nodes, "NodeGroupOutput",(150,0))  
            hsv_pos_x = -1500
            vecMul10 = create_node(hsvGroup.nodes,"ShaderNodeVectorMath",(hsv_pos_x, 0),operation = "MULTIPLY")
            separateHSV = create_node(hsvGroup.nodes,"ShaderNodeSeparateColor",(hsv_pos_x+150, 0))
            separateHSV.mode = 'HSV'
            combine5 = create_node(hsvGroup.nodes,"ShaderNodeCombineXYZ",(hsv_pos_x+150, 0))
            combine6 = create_node(hsvGroup.nodes,"ShaderNodeCombineXYZ",(hsv_pos_x+300, 0))
            vecAdd3 = create_node(hsvGroup.nodes,"ShaderNodeVectorMath",(hsv_pos_x+450, 0))
            combine7 = create_node(hsvGroup.nodes,"ShaderNodeCombineXYZ",(hsv_pos_x+450, -50))
            combine7.inputs[0].default_value = 1
            vecMul11 = create_node(hsvGroup.nodes,"ShaderNodeVectorMath",(hsv_pos_x+600, 0),operation = "MULTIPLY")
            separate11 = create_node(hsvGroup.nodes,"ShaderNodeSeparateXYZ",(hsv_pos_x+750, 0))
            combineHSV = create_node(hsvGroup.nodes,"ShaderNodeCombineColor",(hsv_pos_x+900, 0))
            combineHSV.mode='HSV'
            vecMul12 = create_node(hsvGroup.nodes,"ShaderNodeVectorMath",(hsv_pos_x+1050, 0),operation = "MULTIPLY")
            combine8 = create_node(hsvGroup.nodes,"ShaderNodeCombineXYZ",(hsv_pos_x+1200, -50))
            vecMul13 = create_node(hsvGroup.nodes,"ShaderNodeVectorMath",(hsv_pos_x+1350, 0),operation = "MULTIPLY")
            hsvGroup.links.new(hsvGroupI.outputs[0],vecMul10.inputs[0])
            hsvGroup.links.new(hsvGroupI.outputs[1],vecMul10.inputs[1])
            hsvGroup.links.new(hsvGroupI.outputs[2],combine5.inputs[0])
            hsvGroup.links.new(vecMul10.outputs[0],separateHSV.inputs[0])
            hsvGroup.links.new(separateHSV.outputs[0],combine6.inputs[0])
            hsvGroup.links.new(separateHSV.outputs[1],combine6.inputs[1])
            hsvGroup.links.new(separateHSV.outputs[2],combine6.inputs[2])
            hsvGroup.links.new(combine6.outputs[0],vecAdd3.inputs[0])
            hsvGroup.links.new(combine5.outputs[0],vecAdd3.inputs[1])
            hsvGroup.links.new(hsvGroupI.outputs[3],combine7.inputs[1])
            hsvGroup.links.new(hsvGroupI.outputs[4],combine7.inputs[2])
            hsvGroup.links.new(vecAdd3.outputs[0],vecMul11.inputs[0])
            hsvGroup.links.new(combine7.outputs[0],vecMul11.inputs[1])
            hsvGroup.links.new(vecMul11.outputs[0],separate11.inputs[0])
            hsvGroup.links.new(separate11.outputs[0],combineHSV.inputs[0])
            hsvGroup.links.new(separate11.outputs[1],combineHSV.inputs[1])
            hsvGroup.links.new(separate11.outputs[2],combineHSV.inputs[2])
            hsvGroup.links.new(combineHSV.outputs[0],vecMul12.inputs[0])
            hsvGroup.links.new(hsvGroupI.outputs[5],vecMul12.inputs[1])
            hsvGroup.links.new(hsvGroupI.outputs[6],combine8.inputs[0])
            hsvGroup.links.new(hsvGroupI.outputs[6],combine8.inputs[1])
            hsvGroup.links.new(hsvGroupI.outputs[6],combine8.inputs[2])
            hsvGroup.links.new(vecMul12.outputs[0],vecMul13.inputs[0])
            hsvGroup.links.new(combine8.outputs[0],vecMul13.inputs[1])
            hsvGroup.links.new(vecMul13.outputs[0],hsvGroupO.inputs[0])

        # TODO scroll1 = lerp(emissive, emissive*2, ?)
        #      scrollMask = lerp(color, (.98,0,.05), ?)
        hsv = create_node(CurMat.nodes,"ShaderNodeGroup",(-400,-650), label="hsv")
        hsv.node_tree = hsvGroup
        CurMat.links.new(m3.outputs[0],hsv.inputs[0])
        CurMat.links.new(emissive.outputs[0],hsv.inputs[1])
        CurMat.links.new(texHSVControl_x.outputs[0],hsv.inputs[2])
        CurMat.links.new(texHSVControl_y.outputs[0],hsv.inputs[3])
        CurMat.links.new(texHSVControl_z.outputs[0],hsv.inputs[4])
        CurMat.links.new(gamma.outputs[0],hsv.inputs[5])
        CurMat.links.new(mix.outputs[0],hsv.inputs[6])

        # cameraPos
        vecTform = create_node(CurMat.nodes,"ShaderNodeVectorTransform",(-1050,-1050))
        vecTform.inputs[0].default_value = (0,0,0)
        vecTform.convert_from = "CAMERA"
        vecTform.convert_to = "OBJECT"
        vecTform.vector_type = "POINT"

        # viewDir
        vecSub9 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-900,-1050),operation="SUBTRACT")
        normalize = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-750,-1050),operation="NORMALIZE")
        CurMat.links.new(geometry.outputs[0],vecSub9.inputs[1])
        CurMat.links.new(vecTform.outputs[0],vecSub9.inputs[0])
        CurMat.links.new(vecSub9.outputs[0],normalize.inputs[0])

        # TODO AdditiveAlphaBlend 
        # fresnelValue
        dot = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-600,-1050),operation="DOT_PRODUCT")
        subtract = create_node(CurMat.nodes,"ShaderNodeMath",(-450,-1050),operation="SUBTRACT")
        subtract.inputs[0].default_value = 1
        mix2 = create_node(CurMat.nodes,"ShaderNodeMix",(-300,-1050))
        mix2.inputs[3].default_value = 1
        mul = create_node(CurMat.nodes,"ShaderNodeMath",(-150,-1050),operation="MULTIPLY")
        mul2 = create_node(CurMat.nodes,"ShaderNodeMath",(-0,-1050),operation="MULTIPLY")
        compare = create_node(CurMat.nodes,"ShaderNodeMath",(-450,-1100),operation="COMPARE")
        compare.inputs[0].default_value = 1
        compare.inputs[2].default_value = 0

        CurMat.links.new(geometry.outputs[1],dot.inputs[0])
        CurMat.links.new(normalize.outputs[0],dot.inputs[1])
        CurMat.links.new(dot.outputs["Value"],subtract.inputs[1])
        CurMat.links.new(m3.outputs[1],mul.inputs[0])
        CurMat.links.new(color_a.outputs[0],compare.inputs[1])
        CurMat.links.new(compare.outputs[0],mix2.inputs[0])
        CurMat.links.new(subtract.outputs[0],mix2.inputs[2])
        CurMat.links.new(mix2.outputs[0],mul.inputs[1])
        CurMat.links.new(mul.outputs[0],mul2.inputs[1])
        CurMat.links.new(mix.outputs[0],mul2.inputs[0])


        # to pBSDF
        CurMat.links.new(hsv.outputs[0],pBSDF.inputs["Base Color"])
        CurMat.links.new(hsv.outputs[0],pBSDF.inputs[sockets["Emission"]])
        pBSDF.inputs["Emission Strength"].default_value = 1.0
        CurMat.links.new(mul2.outputs[0],pBSDF.inputs["Alpha"])
