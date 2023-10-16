import bpy
import os
from ..main.common import *



class TelevisionAd:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    # (1-t)a+tb
    def createLerpNode(self):
        if 'lerp' in bpy.data.node_groups.keys():
            return bpy.data.node_groups['lerp']
        else:
            CurMat = bpy.data.node_groups.new('lerp', 'ShaderNodeTree')
            CurMat.inputs.new('NodeSocketFloat','A' )
            CurMat.inputs.new('NodeSocketFloat','B' )
            CurMat.inputs.new('NodeSocketFloat','t' )
            CurMat.outputs.new('NodeSocketFloat','result' )
            GroupInput = create_node(CurMat.nodes,"NodeGroupInput",(0, 0), label="Group Input")
            GroupOutput = create_node(CurMat.nodes,"NodeGroupOutput",(700, 0), label="Group Output")
            sub = create_node(CurMat.nodes,"ShaderNodeMath", (200,100) , operation = 'SUBTRACT')
            mul = create_node(CurMat.nodes,"ShaderNodeMath", (350,50) , operation = 'MULTIPLY')
            mul2 =create_node(CurMat.nodes,"ShaderNodeMath", (350,-50) , operation = 'MULTIPLY')
            add = create_node(CurMat.nodes,"ShaderNodeMath", (500,0) , operation = 'ADD')
            sub.inputs[0].default_value = 1.0
            CurMat.links.new(GroupInput.outputs[2],sub.inputs[1])
            CurMat.links.new(sub.outputs[0],mul.inputs[0])
            CurMat.links.new(GroupInput.outputs[0],mul.inputs[1])
            CurMat.links.new(GroupInput.outputs[2],mul2.inputs[0])
            CurMat.links.new(GroupInput.outputs[1],mul2.inputs[1])
            CurMat.links.new(GroupInput.outputs[1],mul2.inputs[1])
            CurMat.links.new(mul.outputs[0],add.inputs[0])
            CurMat.links.new(mul2.outputs[0],add.inputs[1])
            CurMat.links.new(add.outputs[0],GroupOutput.inputs[0])

            return CurMat
        
    def createVecLerpNode(self):
        if 'vecLerp' in bpy.data.node_groups.keys():
            return bpy.data.node_groups['vecLerp']
        else:
            CurMat = bpy.data.node_groups.new('vecLerp', 'ShaderNodeTree')
            CurMat.inputs.new('NodeSocketVector','A' )
            CurMat.inputs.new('NodeSocketVector','B' )
            CurMat.inputs.new('NodeSocketVector','t' )
            CurMat.outputs.new('NodeSocketVector','result' )
            GroupInput = create_node(CurMat.nodes,"NodeGroupInput",(0, 0), label="Group Input")
            GroupOutput = create_node(CurMat.nodes,"NodeGroupOutput",(700, 0), label="Group Output")
            sub = create_node(CurMat.nodes,"ShaderNodeVectorMath", (200,100) , operation = 'SUBTRACT')
            mul = create_node(CurMat.nodes,"ShaderNodeVectorMath", (350,50) , operation = 'MULTIPLY')
            mul2 =create_node(CurMat.nodes,"ShaderNodeVectorMath", (350,-50) , operation = 'MULTIPLY')
            add = create_node(CurMat.nodes,"ShaderNodeVectorMath", (500,0) , operation = 'ADD')
            sub.inputs[0].default_value = (1,1,1)
            CurMat.links.new(GroupInput.outputs[2],sub.inputs[1])
            CurMat.links.new(sub.outputs[0],mul.inputs[0])
            CurMat.links.new(GroupInput.outputs[0],mul.inputs[1])
            CurMat.links.new(GroupInput.outputs[2],mul2.inputs[0])
            CurMat.links.new(GroupInput.outputs[1],mul2.inputs[1])
            CurMat.links.new(GroupInput.outputs[1],mul2.inputs[1])
            CurMat.links.new(mul.outputs[0],add.inputs[0])
            CurMat.links.new(mul2.outputs[0],add.inputs[1])
            CurMat.links.new(add.outputs[0],GroupOutput.inputs[0])

            return CurMat

        
    def createHash12Node(self):
        if 'hash12' in bpy.data.node_groups.keys():
            return bpy.data.node_groups['hash12']
        else:     
            CurMat = bpy.data.node_groups.new('hash12', 'ShaderNodeTree')
            CurMat.inputs.new('NodeSocketVector','vector' )
            CurMat.outputs.new('NodeSocketFloat','result' )
            GroupInput = create_node(CurMat.nodes,"NodeGroupInput",(-500, 0), label="Group Input")
            GroupOutput = create_node(CurMat.nodes,"NodeGroupOutput",(1350, 0), label="Group Output")
            separate = create_node(CurMat.nodes,"ShaderNodeSeparateXYZ",  (-350,0))      
            combine = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",  (-200,0)) 
            combine2 = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",  (-200,-50)) 
            vecMul = create_node(CurMat.nodes,"ShaderNodeVectorMath",  (0,0), operation = "MULTIPLY") 
            frac = create_node(CurMat.nodes,"ShaderNodeVectorMath",  (150,0), operation = "FRACTION") 
            vecMul.inputs[1].default_value = (.1031,.1031,.1031)
            dot = create_node(CurMat.nodes,"ShaderNodeVectorMath",  (300,-50), operation = "DOT_PRODUCT") 
            vecAdd = create_node(CurMat.nodes,"ShaderNodeVectorMath",  (0,-50), operation = "ADD") 
            vecAdd2 = create_node(CurMat.nodes,"ShaderNodeVectorMath",  (600,0), operation = "ADD")
            combine3 = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",  (450,-50))
            separate2 = create_node(CurMat.nodes,"ShaderNodeSeparateXYZ",  (750,0)) 
            add = create_node(CurMat.nodes,"ShaderNodeMath",  (900,0), operation = "ADD")
            mul = create_node(CurMat.nodes,"ShaderNodeMath",  (1050,0), operation = "MULTIPLY")
            frac2 = create_node(CurMat.nodes,"ShaderNodeMath",  (1200,0), operation = "FRACT")
            CurMat.links.new(GroupInput.outputs[0],separate.inputs[0])
            CurMat.links.new(separate.outputs[0],combine.inputs[0])
            CurMat.links.new(separate.outputs[1],combine.inputs[1])
            CurMat.links.new(separate.outputs[0],combine.inputs[2])
            CurMat.links.new(combine.outputs[0],vecMul.inputs[0])
            CurMat.links.new(vecMul.outputs[0],frac.inputs[0])
            CurMat.links.new(separate.outputs[1],combine2.inputs[0])
            CurMat.links.new(separate.outputs[2],combine2.inputs[1])
            CurMat.links.new(separate.outputs[0],combine2.inputs[2])
            CurMat.links.new(combine2.outputs[0],vecAdd.inputs[0])
            vecAdd.inputs[1].default_value = (33.33,33.33,33.33)
            CurMat.links.new(frac.outputs[0],dot.inputs[0])
            CurMat.links.new(vecAdd.outputs[0],dot.inputs[1])
            CurMat.links.new(dot.outputs["Value"],combine3.inputs[0])
            CurMat.links.new(dot.outputs["Value"],combine3.inputs[1])
            CurMat.links.new(dot.outputs["Value"],combine3.inputs[2])
            CurMat.links.new(frac.outputs[0],vecAdd2.inputs[0])
            CurMat.links.new(combine3.outputs[0],vecAdd2.inputs[1])
            CurMat.links.new(vecAdd2.outputs[0],separate2.inputs[0])
            CurMat.links.new(separate2.outputs[0],add.inputs[0])
            CurMat.links.new(separate2.outputs[1],add.inputs[1])
            CurMat.links.new(add.outputs[0],mul.inputs[0])
            CurMat.links.new(separate2.outputs[2],mul.inputs[1])
            CurMat.links.new(mul.outputs[0],frac2.inputs[0])
            CurMat.links.new(frac2.outputs[0],GroupOutput.inputs[0])
            return CurMat   

    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF = CurMat.nodes['Principled BSDF']
        pBSDF.inputs["Specular"].default_value = 0

        # PARAMETERS
        if "TilesWidth" in Data:
            tilesW = CreateShaderNodeValue(CurMat,Data["TilesWidth"],-2000, 400,"TilesWidth")

        if "TilesHeight" in Data:
            tilesH = CreateShaderNodeValue(CurMat,Data["TilesHeight"],-2000, 350,"TilesHeight")

        if "PlaySpeed" in Data:
            playSpeed = CreateShaderNodeValue(CurMat,Data["PlaySpeed"],-2000, 300,"PlaySpeed")

        if "InterlaceLines" in Data:
            iLines = CreateShaderNodeValue(CurMat,Data["InterlaceLines"],-2000, 250,"InterlaceLines")
        
        if "PixelsHeight" in Data:
            pixH = CreateShaderNodeValue(CurMat,Data["PixelsHeight"],-2000, 200,"PixelsHeight")

        if "BlackLinesRatio" in Data:
            blRatio = CreateShaderNodeValue(CurMat,Data["BlackLinesRatio"],-2000, 150,"BlackLinesRatio")

        if "BlackLinesIntensity" in Data:
            blIntensity = CreateShaderNodeValue(CurMat,Data["BlackLinesIntensity"],-2000, 100,"BlackLinesIntensity")

        if "BlackLinesSize" in Data:
            blSize = CreateShaderNodeValue(CurMat,Data["BlackLinesSize"],-2000, 50,"BlackLinesSize")

        if "LinesOrDots" in Data:
            lOrDots = CreateShaderNodeValue(CurMat,Data["LinesOrDots"],-2000, 0,"LinesOrDots")

        if "DistanceDivision" in Data:
            dDivision = CreateShaderNodeValue(CurMat,Data["DistanceDivision"],-2000, -50,"DistanceDivision")

        if "Metalness" in Data:
            m = CreateShaderNodeValue(CurMat,Data["Metalness"],-2000, -100,"Metalness")

        if "Roughness" in Data:
            r = CreateShaderNodeValue(CurMat,Data["Roughness"],-2000, -150,"Roughness")

        if "IsBroken" in Data:
            isBroken = CreateShaderNodeValue(CurMat,Data["IsBroken"],-2000, -200,"IsBroken")

        if "UseFloatParameter" in Data:
            float0 = CreateShaderNodeValue(CurMat,Data["UseFloatParameter"],-2000, -250,"UseFloatParameter")

        if "AlphaThreshold" in Data:
            aThreshold = CreateShaderNodeValue(CurMat,Data["AlphaThreshold"],-2000, -300,"AlphaThreshold")

        if "UseFloatParameter1" in Data:
            float1 = CreateShaderNodeValue(CurMat,Data["UseFloatParameter1"],-2000, -350,"UseFloatParameter1")

        if "EmissiveEV" in Data:
            e = CreateShaderNodeValue(CurMat,Data["EmissiveEV"],-2000, -400,"EmissiveEV")

        # if "EmissiveDirectionality" in Data:
        #     eD = CreateShaderNodeValue(CurMat,Data["EmissiveDirectionality"],-1000, -450,"EmissiveDirectionality")

        # if "EnableRaytracedEmissive" in Data:
        #     eRE= CreateShaderNodeValue(CurMat,Data["EnableRaytracedEmissive"],-1000, -500,"EnableRaytracedEmissive")

        if "HUEChangeSpeed" in Data:
            HUEcSpeed = CreateShaderNodeValue(CurMat,Data["HUEChangeSpeed"],-2000, -550,"HUEChangeSpeed")

        if "DirtOpacityScale" in Data:
            dirtOS = CreateShaderNodeValue(CurMat,Data["DirtOpacityScale"],-2000, -600,"DirtOpacityScale")

        if "DirtRoughness" in Data:
            dirtR = CreateShaderNodeValue(CurMat,Data["DirtRoughness"],-2000, -650,"DirtRoughness")

        if "DirtUvScaleU" in Data:
            dirtUVScaleU = CreateShaderNodeValue(CurMat,Data["DirtUvScaleU"],-2000, -700,"DirtUvScaleU")

        if "DirtUvScaleV" in Data:
            dirtUVScaleV = CreateShaderNodeValue(CurMat,Data["DirtUvScaleV"],-2000, -750,"DirtUvScaleV")

        # time node
        time = CreateShaderNodeValue(CurMat,1,-2000, 550,"Time")
        timeDriver = time.outputs[0].driver_add("default_value")
        timeDriver.driver.expression = "frame / 24" #FIXME: frame / framerate variable

        # uv
        UVNode = create_node(CurMat.nodes,"ShaderNodeTexCoord",(-2000,650))

        if "DirtTexture" in Data:
            dirtImg=imageFromRelPath(Data["DirtTexture"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            dirtNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-2000,450), label="DirtTexture", image=dirtImg)
            # dirtUV
            combine11 = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",  (-1850,-725))
            vecMul9 = create_node(CurMat.nodes,"ShaderNodeVectorMath",  (-1700,-725))
            CurMat.links.new(dirtUVScaleU.outputs[0],combine11.inputs[0])
            CurMat.links.new(dirtUVScaleV.outputs[0],combine11.inputs[1])
            CurMat.links.new(UVNode.outputs[2],vecMul9.inputs[0])
            CurMat.links.new(combine11.outputs[0],vecMul9.inputs[1])
            # link dirtUV to dirt texture
            CurMat.links.new(vecMul9.outputs[0],dirtNode.inputs[0])

            # dirtOpacity
            mul12 = create_node(CurMat.nodes,"ShaderNodeMath", (-1850, -600))
            CurMat.links.new(dirtNode.outputs[1],mul12.inputs[0])
            CurMat.links.new(dirtOS.outputs[0],mul12.inputs[0])

        if "AdTexture" in Data and isinstance(Data["AdTexture"],str):
            print(Data["AdTexture"])
            adImg=imageFromRelPath(Data["AdTexture"],self.image_format,DepotPath=self.BasePath, ProjPath=self.ProjPath)
            adNode = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-100,1025), label="AdTexture", image=adImg) 
            adNode2 = create_node(CurMat.nodes,"ShaderNodeTexImage",(-1000,775), label="AdTexture", image=adImg) 
            adNode3 = create_node(CurMat.nodes,"ShaderNodeTexImage",  (-550,975), label="AdTexture", image=adImg) 

            

            # n
            if 'n' in bpy.data.node_groups.keys():
                ngroup = bpy.data.node_groups['n']
            else:
                ngroup = bpy.data.node_groups.new("n","ShaderNodeTree")   
                ngroup.inputs.new('NodeSocketFloat','TilesWidth')
                ngroup.inputs.new('NodeSocketFloat','TilesHeight')
                ngroup.inputs.new('NodeSocketFloat','PlaySpeed')
                ngroup.inputs.new('NodeSocketFloat','Time')
                GroupInput = create_node(ngroup.nodes, "NodeGroupInput",(-1400,0))
                ngroup.outputs.new('NodeSocketFloat','n')
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
                ngroup.links.new(mul3.outputs[0],GroupOutput.inputs[0]) # n
            
            n = create_node(CurMat.nodes,"ShaderNodeGroup",(-1700, 925), label="n")
            n.node_tree = ngroup

            CurMat.links.new(tilesW.outputs[0],n.inputs[0])
            CurMat.links.new(tilesH.outputs[0],n.inputs[1])
            CurMat.links.new(playSpeed.outputs[0],n.inputs[2])
            CurMat.links.new(time.outputs[0],n.inputs[3])

            

            # frameAdd
            if 'frameAdd' in bpy.data.node_groups.keys():
                frameGroup = bpy.data.node_groups['frameAdd']
            else:
                frameGroup = bpy.data.node_groups.new("frameAdd","ShaderNodeTree") 
                frameGroup.inputs.new('NodeSocketFloat','PixelsHeight')
                frameGroup.inputs.new('NodeSocketFloat','InterlaceLines')
                frameGroup.inputs.new('NodeSocketVector','UV')
                frameGroup.inputs.new('NodeSocketFloat','n')
                frameGroup.outputs.new('NodeSocketFloat','frameAdd')
                fGroupInput = create_node(frameGroup.nodes, "NodeGroupInput",(-1400,0))
                fGroupOutput = create_node(frameGroup.nodes, "NodeGroupOutput",(200,0))

                UVSeparate = create_node(frameGroup.nodes, "ShaderNodeSeparateXYZ",(-1300,100))
                mul4 = create_node(frameGroup.nodes,"ShaderNodeMath", (-1100,100) , operation = 'MULTIPLY')
                mul5 = create_node(frameGroup.nodes,"ShaderNodeMath", (-1100,150) , operation = 'MULTIPLY')
                div2 = create_node(frameGroup.nodes,"ShaderNodeMath", (-900,125) , operation = 'DIVIDE')
                mod = create_node(frameGroup.nodes,"ShaderNodeMath", (-750,125) , operation = 'MODULO')
                add = create_node(frameGroup.nodes,"ShaderNodeMath", (-600,125) , operation = 'ADD')
                mod2 = create_node(frameGroup.nodes,"ShaderNodeMath", (-900,75) , operation = 'MODULO')
                add2 = create_node(frameGroup.nodes,"ShaderNodeMath", (-750,75) , operation = 'ADD')
                floor = create_node(frameGroup.nodes,"ShaderNodeMath", (-600,75) , operation = 'FLOOR')
                add3 = create_node(frameGroup.nodes,"ShaderNodeMath", (-450,125) , operation = 'ADD')
                floor2 = create_node(frameGroup.nodes,"ShaderNodeMath", (-300,125) , operation = 'FLOOR')
                clamp = create_node(frameGroup.nodes,"ShaderNodeClamp", (-300,75))
                frameGroup.links.new(fGroupInput.outputs["InterlaceLines"],mul4.inputs[0])
                mul4.inputs[1].default_value = 8
                frameGroup.links.new(fGroupInput.outputs['UV'],UVSeparate.inputs[0])
                frameGroup.links.new(UVSeparate.outputs[1],mul5.inputs[0])
                frameGroup.links.new(fGroupInput.outputs['PixelsHeight'],mul5.inputs[1])
                frameGroup.links.new(mul5.outputs[0],div2.inputs[0])
                frameGroup.links.new(mul4.outputs[0],div2.inputs[1])
                frameGroup.links.new(div2.outputs[0],mod.inputs[0])
                mod.inputs[1].default_value = 1
                frameGroup.links.new(mod.outputs[0],add.inputs[0])
                add.inputs[1].default_value = .5
                frameGroup.links.new(fGroupInput.outputs['n'],mod2.inputs[0])
                mod2.inputs[1].default_value = 1
                frameGroup.links.new(mod2.outputs[0],add2.inputs[0])
                add2.inputs[1].default_value = .5
                frameGroup.links.new(add2.outputs[0],floor.inputs[0])
                frameGroup.links.new(add.outputs[0],add3.inputs[0])
                frameGroup.links.new(floor.outputs[0],add3.inputs[1])
                frameGroup.links.new(add3.outputs[0],floor2.inputs[0])
                frameGroup.links.new(floor2.outputs[0],clamp.inputs[0])
                frameGroup.links.new(clamp.outputs[0],fGroupOutput.inputs[0])  # frameAdd

            frameAdd = create_node(CurMat.nodes,"ShaderNodeGroup",(-1700, 825), label="frameAdd")
            frameAdd.node_tree = frameGroup

            CurMat.links.new(pixH.outputs[0],frameAdd.inputs[0])
            CurMat.links.new(iLines.outputs[0],frameAdd.inputs[1])
            CurMat.links.new(UVNode.outputs[2],frameAdd.inputs[2])
            CurMat.links.new(n.outputs[0],frameAdd.inputs[3])


            # subUV
            if 'subUV' in bpy.data.node_groups.keys():
                subUVGroup = bpy.data.node_groups['subUV']
            else:
                subUVGroup = bpy.data.node_groups.new("subUV","ShaderNodeTree") 
                subUVGroup.inputs.new('NodeSocketFloat','TilesWidth')
                subUVGroup.inputs.new('NodeSocketFloat','TilesHeight')
                subUVGroup.inputs.new('NodeSocketFloat','n')
                subUVGroup.inputs.new('NodeSocketFloat','frameAdd')
                subUVGroup.outputs.new('NodeSocketVector','subUV')
                subUVGroup.inputs.new('NodeSocketVector','UV')
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
                frac4 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-350,-250) , operation = 'FRACT')
                frac5 = create_node(subUVGroup.nodes,"ShaderNodeMath", (-350,-150) , operation = 'FRACT')
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
                subUVGroup.links.new(add5.outputs[0],frac4.inputs[0])
                subUVGroup.links.new(frac4.outputs[0],combine.inputs[0])
                sub2.inputs[0].default_value = 1.0
                subUVGroup.links.new(add6.outputs[0],sub2.inputs[1])
                subUVGroup.links.new(sub2.outputs[0],frac5.inputs[0])
                subUVGroup.links.new(frac5.outputs[0],combine.inputs[1])            
                subUVGroup.links.new(combine.outputs[0],subUVGroupO.inputs[0])

            subUV = create_node(CurMat.nodes,"ShaderNodeGroup",(-1500, 875), label="subUV")
            subUV.node_tree = subUVGroup
            subUV.name = "subUV"

            CurMat.links.new(tilesW.outputs[0],subUV.inputs[0])
            CurMat.links.new(tilesH.outputs[0],subUV.inputs[1])
            CurMat.links.new(UVNode.outputs[2],subUV.inputs[4])
            CurMat.links.new(n.outputs[0],subUV.inputs[2])
            CurMat.links.new(frameAdd.outputs[0],subUV.inputs[3])
            
            # AdTexture
            CurMat.links.new(subUV.outputs[0],adNode.inputs[0])

            # rndBlocks  
            lerpG = self.createLerpNode()
            lerp = create_node(CurMat.nodes,"ShaderNodeGroup",(-1400, 675), label="lerp")
            lerp.node_tree = lerpG 
            lerp.inputs[0].default_value = 2
            lerp.inputs[1].default_value = 8
            frac2 = create_node(CurMat.nodes,"ShaderNodeMath", (-1550,675) , operation = 'FRACT')
            add7 = create_node(CurMat.nodes,"ShaderNodeMath", (-1700,675) , operation = 'ADD')
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
                hash12G = self.createHash12Node()
                hash12 = create_node(brokenUVGroup.nodes,"ShaderNodeGroup",(-650,-50), label="hash12")
                hash12.node_tree = hash12G
                add8 = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-1250,0) , operation = 'ADD')
                add8.inputs[1].default_value = 0.35748
                mul6 = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-1100,0) , operation = 'MULTIPLY')
                mul6.inputs[1].default_value = 150
                floor5 = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-800,-50) , operation = 'FLOOR')
                separate = create_node(brokenUVGroup.nodes,"ShaderNodeSeparateXYZ", (-800,0))
                combine2 = create_node(brokenUVGroup.nodes,"ShaderNodeCombineXYZ", (-650,0))
                vecAdd = create_node(brokenUVGroup.nodes,"ShaderNodeVectorMath", (-350,0) , operation = 'ADD')
                vecFrac = create_node(brokenUVGroup.nodes,"ShaderNodeVectorMath", (-200,0) , operation = 'FRACTION')
                mul7 = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-1250,-100) , operation = 'MULTIPLY')
                floor6 = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-1100,-100) , operation = 'FLOOR')
                div8 = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-950,-100) , operation = 'DIVIDE')
                add9 = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-800,-100) , operation = 'ADD')
                add9.inputs[1].default_value = 1
                mul8 = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-650,-100) , operation = 'MULTIPLY')
                frac3 = create_node(brokenUVGroup.nodes,"ShaderNodeMath", (-500,-100) , operation = 'FRACT')
                clamp2 = create_node(brokenUVGroup.nodes,"ShaderNodeClamp", (-350,-100))
                lerp2 = create_node(brokenUVGroup.nodes,"ShaderNodeGroup",(-200,-100), label="lerp")
                lerp2.node_tree = lerpG 
                lerp2.inputs[0].default_value = 1
                lerp2.inputs[1].default_value = 4
                vecDiv = create_node(brokenUVGroup.nodes,"ShaderNodeVectorMath", (-50,0) , operation = 'DIVIDE')

                brokenUVGroup.links.new(brokenUVGroupI.outputs[1],add8.inputs[0])
                brokenUVGroup.links.new(add8.outputs[0],mul6.inputs[0])
                brokenUVGroup.links.new(mul6.outputs[0],floor5.inputs[0])
                brokenUVGroup.links.new(floor5.outputs[0],hash12.inputs[0])
                brokenUVGroup.links.new(brokenUVGroupI.outputs[2],separate.inputs[0])
                brokenUVGroup.links.new(separate.outputs[0],combine2.inputs[0])
                brokenUVGroup.links.new(separate.outputs[0],combine2.inputs[1])
                brokenUVGroup.links.new(combine2.outputs[0],vecAdd.inputs[0])
                brokenUVGroup.links.new(hash12.outputs[0],vecAdd.inputs[1])
                brokenUVGroup.links.new(vecAdd.outputs[0],vecFrac.inputs[0])
                brokenUVGroup.links.new(separate.outputs[0],mul7.inputs[0])
                brokenUVGroup.links.new(brokenUVGroupI.outputs[0],mul7.inputs[1])
                brokenUVGroup.links.new(mul7.outputs[0],floor6.inputs[0])
                brokenUVGroup.links.new(floor6.outputs[0],div8.inputs[0])
                brokenUVGroup.links.new(brokenUVGroupI.outputs[0],div8.inputs[1])
                brokenUVGroup.links.new(div8.outputs[0],add9.inputs[0])
                brokenUVGroup.links.new(add9.outputs[0],mul8.inputs[0])
                brokenUVGroup.links.new(brokenUVGroupI.outputs[1],mul8.inputs[0])
                brokenUVGroup.links.new(mul8.outputs[0],frac3.inputs[0])
                brokenUVGroup.links.new(frac3.outputs[0],clamp2.inputs[0])
                brokenUVGroup.links.new(clamp2.outputs[0],lerp2.inputs[2])
                brokenUVGroup.links.new(vecFrac.outputs[0],vecDiv.inputs[0])
                brokenUVGroup.links.new(lerp2.outputs[0],vecDiv.inputs[1])
                brokenUVGroup.links.new(vecDiv.outputs[0],brokenUVGroupO.inputs[0])

            brokenUV = create_node(CurMat.nodes,"ShaderNodeGroup",(-1200, 775), label="brokenUV")
            brokenUV.node_tree = brokenUVGroup

            CurMat.links.new(lerp.outputs[0],brokenUV.inputs[0])
            CurMat.links.new(time.outputs[0],brokenUV.inputs[1])
            CurMat.links.new(UVNode.outputs[2],brokenUV.inputs[2])

            # rndColorIndex
            if 'rndColorIndex' in bpy.data.node_groups.keys():
                rndColorIGroup = bpy.data.node_groups['rndColorIndex']
            else:       
                rndColorIGroup = bpy.data.node_groups.new("rndColorIndex","ShaderNodeTree") 
                rndColorIGroup.inputs.new('NodeSocketFloat','rndBlocks')
                rndColorIGroup.inputs.new('NodeSocketFloat','Time')
                rndColorIGroup.inputs.new('NodeSocketVector','UV')
                rndColorIGroup.outputs.new('NodeSocketInt','rndColorIndex')
                rndColorIGroupI = create_node(rndColorIGroup.nodes, "NodeGroupInput",(-1400,0))
                rndColorIGroupO = create_node(rndColorIGroup.nodes, "NodeGroupOutput",(200,0))  
                separate2 = create_node(rndColorIGroup.nodes,"ShaderNodeSeparateXYZ", (-1250,0))
                combine3 = create_node(rndColorIGroup.nodes,"ShaderNodeCombineXYZ", (-1100,0))
                vecMul = create_node(rndColorIGroup.nodes,"ShaderNodeVectorMath", (-950,0), operation="MULTIPLY")
                vecFloor = create_node(rndColorIGroup.nodes,"ShaderNodeVectorMath", (-800,0), operation="FLOOR")
                vecDiv2 = create_node(rndColorIGroup.nodes,"ShaderNodeVectorMath", (-650,0), operation="DIVIDE")
                frac6 = create_node(rndColorIGroup.nodes,"ShaderNodeMath", (-500,-50), operation="FRACT")
                vecMul2 = create_node(rndColorIGroup.nodes,"ShaderNodeVectorMath", (-350,-25), operation="MULTIPLY")
                vecSub = create_node(rndColorIGroup.nodes,"ShaderNodeVectorMath", (-200,-25), operation="SUBTRACT")
                vecSub.inputs[1].default_value = (0.1625,0.1625,0.1625)
                hash12G = self.createHash12Node()
                hash12_2 = create_node(rndColorIGroup.nodes,"ShaderNodeGroup",(-50,-25), label="hash12")
                hash12_2.node_tree = hash12G
                mul9 = create_node(rndColorIGroup.nodes,"ShaderNodeMath", (100,-25), operation="MULTIPLY")
                mul9.inputs[1].default_value = 4
                rndColorIGroup.links.new(rndColorIGroupI.outputs[2],separate2.inputs[0])
                rndColorIGroup.links.new(separate2.outputs[0],combine3.inputs[0])
                rndColorIGroup.links.new(separate2.outputs[0],combine3.inputs[1])
                rndColorIGroup.links.new(combine3.outputs[0],vecMul.inputs[0])
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
                

            rndColorIndex = create_node(CurMat.nodes,"ShaderNodeGroup",(-1200, 575), label="rndColorIndex")
            rndColorIndex.node_tree = rndColorIGroup
            CurMat.links.new(lerp.outputs[0],rndColorIndex.inputs[0])
            CurMat.links.new(time.outputs[0],rndColorIndex.inputs[1])
            CurMat.links.new(UVNode.outputs[2],rndColorIndex.inputs[2])
            

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
                combine4 = create_node(rndColorGroup.nodes,"ShaderNodeCombineXYZ", (-900,175)) # float3 (1,1,1)
                combine4.inputs[0].default_value = 1
                combine4.inputs[1].default_value = 1
                combine4.inputs[2].default_value = 1
                combine5 = create_node(rndColorGroup.nodes,"ShaderNodeCombineXYZ", (-900,75)) # float3 (.2,0,0)
                combine5.inputs[0].default_value = .2
                combine5.inputs[1].default_value = 0
                combine5.inputs[2].default_value = 0
                combine6 = create_node(rndColorGroup.nodes,"ShaderNodeCombineXYZ", (-900,-25)) # float3 (0,1,0)
                combine6.inputs[0].default_value = 0
                combine6.inputs[1].default_value = 1
                combine6.inputs[2].default_value = 0
                combine7 = create_node(rndColorGroup.nodes,"ShaderNodeCombineXYZ", (-900,-125)) # float3 (0,0,1)
                combine7.inputs[0].default_value = 0
                combine7.inputs[1].default_value = 0
                combine7.inputs[2].default_value = 1
                vecMul3 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-700,150), operation="MULTIPLY")
                vecMul4 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-700,50), operation="MULTIPLY")
                vecMul5 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-700,-50), operation="MULTIPLY")
                vecMul6 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-700,-150), operation="MULTIPLY")
                vecAdd2 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-500,100), operation="ADD")
                vecAdd3 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-500,-100), operation="ADD")
                vecAdd4 = create_node(rndColorGroup.nodes,"ShaderNodeVectorMath", (-300,0), operation="ADD")
                rndColorGroup.links.new(rndColorGroupI.outputs[0],compare.inputs[0])
                rndColorGroup.links.new(rndColorGroupI.outputs[0],compare2.inputs[0])
                rndColorGroup.links.new(rndColorGroupI.outputs[0],compare3.inputs[0])
                rndColorGroup.links.new(rndColorGroupI.outputs[0],compare4.inputs[0])
                rndColorGroup.links.new(compare.outputs[0],vecMul3.inputs[1])
                rndColorGroup.links.new(compare2.outputs[0],vecMul4.inputs[1])
                rndColorGroup.links.new(compare3.outputs[0],vecMul5.inputs[1])
                rndColorGroup.links.new(compare4.outputs[0],vecMul6.inputs[1])
                rndColorGroup.links.new(combine4.outputs[0],vecMul3.inputs[0])
                rndColorGroup.links.new(combine5.outputs[0],vecMul4.inputs[0])
                rndColorGroup.links.new(combine6.outputs[0],vecMul5.inputs[0])
                rndColorGroup.links.new(combine7.outputs[0],vecMul6.inputs[0])
                rndColorGroup.links.new(vecMul3.outputs[0],vecAdd2.inputs[0])
                rndColorGroup.links.new(vecMul4.outputs[0],vecAdd2.inputs[1])
                rndColorGroup.links.new(vecMul5.outputs[0],vecAdd3.inputs[0])
                rndColorGroup.links.new(vecMul6.outputs[0],vecAdd3.inputs[1])
                rndColorGroup.links.new(vecAdd2.outputs[0],vecAdd4.inputs[0])
                rndColorGroup.links.new(vecAdd3.outputs[0],vecAdd4.inputs[1])
                rndColorGroup.links.new(vecAdd4.outputs[0],rndColorGroupO.inputs[0])

            rndColor = create_node(CurMat.nodes,"ShaderNodeGroup",(-1000, 575), label="rndColor")
            rndColor.node_tree = rndColorGroup

            CurMat.links.new(rndColorIndex.outputs[0],rndColor.inputs[0])

            # position of glitches
            separate3 = create_node(CurMat.nodes,"ShaderNodeSeparateXYZ", (-1700,400))
            greaterThan = create_node(CurMat.nodes,"ShaderNodeMath", (-1500,450),operation="GREATER_THAN")
            greaterThan.inputs[1].default_value = .02
            lessThan = create_node(CurMat.nodes,"ShaderNodeMath", (-1500,350),operation="LESS_THAN")
            lessThan.inputs[1].default_value = .12
            minimum = create_node(CurMat.nodes,"ShaderNodeMath", (-1300,400),operation="MINIMUM")
            greaterThan2 = create_node(CurMat.nodes,"ShaderNodeMath", (-1500,250),operation="GREATER_THAN")
            greaterThan2.inputs[1].default_value = .28
            lessThan2 = create_node(CurMat.nodes,"ShaderNodeMath", (-1500,150),operation="LESS_THAN")
            lessThan2.inputs[1].default_value = .543
            minimum2 = create_node(CurMat.nodes,"ShaderNodeMath", (-1300,200),operation="MINIMUM")
            greaterThan3 = create_node(CurMat.nodes,"ShaderNodeMath", (-1500,50),operation="GREATER_THAN")
            greaterThan3.inputs[1].default_value = .78
            lessThan3 = create_node(CurMat.nodes,"ShaderNodeMath", (-1500,-50),operation="LESS_THAN")
            lessThan3.inputs[1].default_value = .85
            minimum3 = create_node(CurMat.nodes,"ShaderNodeMath", (-1300, 0),operation="MINIMUM")
            add10 = create_node(CurMat.nodes,"ShaderNodeMath", (-1100,300),operation="ADD")
            add11 = create_node(CurMat.nodes,"ShaderNodeMath", (-900,200),operation="ADD")
            CurMat.links.new(UVNode.outputs[2],separate3.inputs[0])
            CurMat.links.new(separate3.outputs[0],greaterThan.inputs[0])
            CurMat.links.new(separate3.outputs[0],lessThan.inputs[0])
            CurMat.links.new(greaterThan.outputs[0],minimum.inputs[0])
            CurMat.links.new(lessThan.outputs[0],minimum.inputs[1])
            CurMat.links.new(separate3.outputs[0],greaterThan2.inputs[0])
            CurMat.links.new(separate3.outputs[0],lessThan2.inputs[0])
            CurMat.links.new(greaterThan2.outputs[0],minimum2.inputs[0])
            CurMat.links.new(lessThan2.outputs[0],minimum2.inputs[1])
            CurMat.links.new(separate3.outputs[0],greaterThan3.inputs[0])
            CurMat.links.new(separate3.outputs[0],lessThan3.inputs[0])
            CurMat.links.new(greaterThan3.outputs[0],minimum3.inputs[0])
            CurMat.links.new(lessThan3.outputs[0],minimum3.inputs[1])
            CurMat.links.new(minimum.outputs[0],add10.inputs[0])
            CurMat.links.new(minimum2.outputs[0],add10.inputs[1])
            CurMat.links.new(add10.outputs[0],add11.inputs[0])
            CurMat.links.new(minimum3.outputs[0],add11.inputs[1])

            # sampling the AdTexture and glitches in one texture node
            
            CurMat.links.new(brokenUV.outputs[0],adNode2.inputs[0])
            vecMul7 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-700,675),operation="MULTIPLY")
            CurMat.links.new(adNode2.outputs[0],vecMul7.inputs[0])
            CurMat.links.new(rndColor.outputs[0],vecMul7.inputs[1])
            mixRGB = create_node(CurMat.nodes,"ShaderNodeMixRGB",(-500,487.5))
            CurMat.links.new(add11.outputs[0],mixRGB.inputs[0])
            mixRGB.inputs[1].default_value = (0,0,0,0)
            CurMat.links.new(vecMul7.outputs[0],mixRGB.inputs[2])

            
            div9 = create_node(CurMat.nodes,"ShaderNodeMath",(-1300,975),operation="DIVIDE")
            div9.inputs[1].default_value = 20
            frac7 = create_node(CurMat.nodes,"ShaderNodeMath",(-1150,975),operation="FRACT")
            mul10 = create_node(CurMat.nodes,"ShaderNodeMath",(-1000,975),operation="MULTIPLY")
            mul10.inputs[0].default_value = -.01
            combine9 = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",(-850,975))
            combine9.inputs[0].default_value = .01
            vecAdd5 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-700,975),operation="ADD")
            
            vecMul8 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-300,975),operation="MULTIPLY")
            vecMul8.inputs[0].default_value = (.4,.4,.4)
            mixRGB3 = create_node(CurMat.nodes,"ShaderNodeMixRGB",(-150,975))
            vecAdd6 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(0,975),operation="ADD")
            
            CurMat.links.new(time.outputs[0],div9.inputs[0])
            CurMat.links.new(div9.outputs[0],frac7.inputs[0])
            CurMat.links.new(frac7.outputs[0],mul10.inputs[1])
            CurMat.links.new(mul10.outputs[0],combine9.inputs[1])
            CurMat.links.new(subUV.outputs[0],vecAdd5.inputs[0])
            CurMat.links.new(combine9.outputs[0],vecAdd5.inputs[1])
            CurMat.links.new(vecAdd5.outputs[0],adNode3.inputs[0])
            CurMat.links.new(adNode3.outputs[0],vecMul8.inputs[1])
            CurMat.links.new(add11.outputs[0],mixRGB3.inputs[0])
            CurMat.links.new(vecMul8.outputs[0],mixRGB3.inputs[2])
            CurMat.links.new(adNode.outputs[0],mixRGB3.inputs[1])
            CurMat.links.new(mixRGB3.outputs[0],vecAdd6.inputs[0])
            CurMat.links.new(mixRGB.outputs[0],vecAdd6.inputs[1])


            # isBroken 
            mixRGB2 = create_node(CurMat.nodes,"ShaderNodeMixRGB",(150,975))
            CurMat.links.new(isBroken.outputs[0],mixRGB2.inputs[0])
            CurMat.links.new(adNode.outputs[0],mixRGB2.inputs[1])
            CurMat.links.new(vecAdd6.outputs[0],mixRGB2.inputs[2])

            # HUE
            separate4 = create_node(CurMat.nodes,"ShaderNodeSeparateColor",(300,975))
            separate4.mode = "HSV"
            mul11 = create_node(CurMat.nodes,"ShaderNodeMath",(0,925),operation="MULTIPLY")
            frac8 = create_node(CurMat.nodes,"ShaderNodeMath",(150,925),operation="FRACT")
            add12 = create_node(CurMat.nodes,"ShaderNodeMath",(450,975),operation="ADD")
            combine10 = create_node(CurMat.nodes,"ShaderNodeCombineColor",(600,975))
            combine10.mode = "HSV"
            CurMat.links.new(mixRGB2.outputs[0],separate4.inputs[0])
            CurMat.links.new(time.outputs[0],mul11.inputs[0])
            CurMat.links.new(HUEcSpeed.outputs[0],mul11.inputs[1])
            CurMat.links.new(mul11.outputs[0],frac8.inputs[0])
            CurMat.links.new(separate4.outputs[0],add12.inputs[0])
            CurMat.links.new(frac8.outputs[0],add12.inputs[1])
            CurMat.links.new(add12.outputs[0],combine10.inputs[0])
            CurMat.links.new(separate4.outputs[1],combine10.inputs[1])
            CurMat.links.new(separate4.outputs[2],combine10.inputs[2])

            # lerp(adTex, dirtTex, dirtOpacity) and link to pBSFD
            vecLerpG = self.createVecLerpNode()
            vecLerp = create_node(CurMat.nodes,"ShaderNodeGroup",(-200,200), label="vecLerp")
            vecLerp.node_tree = vecLerpG   
            CurMat.links.new(combine10.outputs[0],vecLerp.inputs[0])
            CurMat.links.new(dirtNode.outputs[0],vecLerp.inputs[1])
            CurMat.links.new(mul12.outputs[0],vecLerp.inputs[2])
            CurMat.links.new(vecLerp.outputs[0],pBSDF.inputs["Base Color"])
            CurMat.links.new(combine10.outputs[0],pBSDF.inputs["Emission"]) # it will be like this before i implement the blackDots

        # metalness
        CurMat.links.new(m.outputs[0],pBSDF.inputs["Metallic"])

        # lerp(Roughness, DirtRoughness, dirtOpacity) and link to pBSFD
        lerpG = self.createLerpNode()
        lerp3 = create_node(CurMat.nodes,"ShaderNodeGroup",(-200,0), label="lerp")
        lerp3.node_tree = lerpG
        CurMat.links.new(r.outputs[0],lerp3.inputs[0])
        CurMat.links.new(dirtR.outputs[0],lerp3.inputs[1])
        CurMat.links.new(mul12.outputs[0],lerp3.inputs[2])
        CurMat.links.new(lerp3.outputs[0],pBSDF.inputs["Roughness"])

        # emissive
        CurMat.links.new(e.outputs[0],pBSDF.inputs["Emission Strength"])







