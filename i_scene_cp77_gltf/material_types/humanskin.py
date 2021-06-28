import bpy
import os
from ..main.common import imageFromPath
from ..main.common import crop_image

class HumanSkin:
    def __init__(self, BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
    def create(self,Skin,Mat):

        CurMat = Mat.node_tree
        CurMat.nodes['Principled BSDF'].inputs['Subsurface'].default_value = 0.012

        # Creating Normal
        nImg = imageFromPath(self.BasePath + Skin["Normal"],self.image_format,True)

        nImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        nImgNode.location = (-1300,-200)
        nImgNode.hide = True
        nImgNode.image = nImg
        nImgNode.label = "Normal"

        Sep = CurMat.nodes.new("ShaderNodeSeparateRGB")
        Sep.location = (-1050,-200)
        Sep.hide = True
            
        Comb = CurMat.nodes.new("ShaderNodeCombineRGB")
        Comb.location = (-900,-200)
        Comb.hide = True
            
        CurMat.links.new(nImgNode.outputs[0],Sep.inputs[0])
        CurMat.links.new(Sep.outputs[0],Comb.inputs[0])
        CurMat.links.new(Sep.outputs[1],Comb.inputs[1])
        Comb.inputs[2].default_value = 1
            
        nMap = CurMat.nodes.new("ShaderNodeNormalMap")
        nMap.location = (-750,-200)
        nMap.hide = True
        CurMat.links.new(Comb.outputs[0],nMap.inputs[1])

        # Creating DetailNormal
        ndImg = imageFromPath(self.BasePath + Skin["DetailNormal"],self.image_format,True)
            
        ndImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        ndImgNode.location = (-1400,-400)
        ndImgNode.image = ndImg
        ndImgNode.hide = True
        ndImgNode.label = "DetailNormal"

        Sep1 = CurMat.nodes.new("ShaderNodeSeparateRGB")
        Sep1.location = (-1150,-400)
        Sep1.hide = True
            
        Comb1 = CurMat.nodes.new("ShaderNodeCombineRGB")
        Comb1.location = (-1000,-400)
        Comb1.hide = True
            
        CurMat.links.new(ndImgNode.outputs[0],Sep1.inputs[0])
        CurMat.links.new(Sep1.outputs[0],Comb1.inputs[0])
        CurMat.links.new(Sep1.outputs[1],Comb1.inputs[1])
        Comb1.inputs[2].default_value = 1

        nMap1 = CurMat.nodes.new("ShaderNodeNormalMap")
        nMap1.location = (-850,-400)
        nMap1.hide = True
        CurMat.links.new(Comb1.outputs[0],nMap1.inputs[1])

        dnInfluence = CurMat.nodes.new("ShaderNodeValue")
        dnInfluence.location = (-900,-350)
        dnInfluence.outputs[0].default_value = float(Skin["DetailNormalInfluence"])
        dnInfluence.hide = True
        dnInfluence.label = "DetailNormalInfluence"
        CurMat.links.new(dnInfluence.outputs[0],nMap1.inputs[0])

        # Combining Normal and DetailNormal
        SubVec = CurMat.nodes.new("ShaderNodeVectorMath")
        SubVec.hide = True
        SubVec.location = (-650,-400)
        SubVec.operation = 'SUBTRACT'
        CurMat.links.new(nMap1.outputs[0],SubVec.inputs[0])

        Geo = CurMat.nodes.new("ShaderNodeNewGeometry")
        Geo.hide = True
        Geo.location = (-750,-500)
        CurMat.links.new(Geo.outputs[1],SubVec.inputs[1])

        AddVec = CurMat.nodes.new("ShaderNodeVectorMath")
        AddVec.hide = True
        AddVec.location = (-550,-300)
        AddVec.operation = 'ADD'
        CurMat.links.new(SubVec.outputs[0],AddVec.inputs[0])
        CurMat.links.new(nMap.outputs[0],AddVec.inputs[1])

        # Creating MicroDetail
        mdImg = bpy.data.images.get(os.path.basename(Skin["MicroDetail"])[:-4] + "01")
        #mdImg = imageFromPath(self.BasePath + Skin["MicroDetail"],self.image_format, True)
        if not mdImg:
            tempImg = imageFromPath(self.BasePath + Skin["MicroDetail"],self.image_format, True)
            mdImg = crop_image(tempImg,os.path.basename(Skin["MicroDetail"])[:-4] + "01",0,512,0,512)
            mdImg.filepath_raw = self.BasePath + Skin["MicroDetail"][:-4] + "01.png"
            mdImg.file_format = 'PNG'
            mdImg.save()
            mdImg.source = 'FILE'
            mdImg.colorspace_settings.name = 'Non-Color'
        mdImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        mdImgNode.location = (-1400,-600)
        mdImgNode.image = mdImg
        mdImgNode.hide = True
        mdImgNode.label = "MicroDetail"

        mDetailUVScale01 = CurMat.nodes.new("ShaderNodeVectorMath")
        mDetailUVScale01.location = (-1500,-600)
        mDetailUVScale01.inputs[1].default_value[0] = float(Skin["MicroDetailUVScale01"])
        mDetailUVScale01.inputs[1].default_value[1] = float(Skin["MicroDetailUVScale01"])
        mDetailUVScale01.hide = True
        mDetailUVScale01.label = "MicroDetailUVScale01"
        mDetailUVScale01.operation = 'MULTIPLY'
        CurMat.links.new(mDetailUVScale01.outputs[0],mdImgNode.inputs[0])

        Sep2 = CurMat.nodes.new("ShaderNodeSeparateRGB")
        Sep2.location = (-1150,-600)
        Sep2.hide = True
            
        Comb2 = CurMat.nodes.new("ShaderNodeCombineRGB")
        Comb2.location = (-1000,-600)
        Comb2.hide = True
            
        CurMat.links.new(mdImgNode.outputs[0],Sep2.inputs[0])
        CurMat.links.new(Sep2.outputs[0],Comb2.inputs[0])
        CurMat.links.new(Sep2.outputs[1],Comb2.inputs[1])
        Comb2.inputs[2].default_value = 1

        nMap2 = CurMat.nodes.new("ShaderNodeNormalMap")
        nMap2.location = (-850,-600)
        nMap2.hide = True
        CurMat.links.new(Comb2.outputs[0],nMap2.inputs[1])

        mdInfluence = CurMat.nodes.new("ShaderNodeValue")
        mdInfluence.location = (-1100,-700)
        mdInfluence.outputs[0].default_value = float(Skin["MicroDetailInfluence"])
        mdInfluence.hide = True
        mdInfluence.label = "MicroDetailInfluence"
        mulNode = CurMat.nodes.new("ShaderNodeMath")
        mulNode.operation = 'MULTIPLY'
        mulNode.hide = True
        mulNode.location = (-1000,-700)
        mulNode.inputs[0].default_value = 0.5
        CurMat.links.new(mdInfluence.outputs[0],mulNode.inputs[1])
        mulNode1 = CurMat.nodes.new("ShaderNodeMath")
        mulNode1.operation = 'MULTIPLY'
        mulNode1.hide = True
        mulNode1.location = (-900,-700)
        CurMat.links.new(mulNode.outputs[0],mulNode1.inputs[1])
        CurMat.links.new(mulNode1.outputs[0],nMap2.inputs[0])

        # Creating MicroDetail
        mdImg1 = bpy.data.images.get(os.path.basename(Skin["MicroDetail"])[:-4] + "02")
        if not mdImg1:
            tempImg1 = imageFromPath(self.BasePath + Skin["MicroDetail"],self.image_format, True)
            mdImg1 = crop_image(tempImg1,os.path.basename(Skin["MicroDetail"])[:-4] + "02",512,1024,0,512)
            mdImg1.filepath_raw = self.BasePath + Skin["MicroDetail"][:-4] + "02.png"
            mdImg1.file_format = 'PNG'
            mdImg1.save()
            mdImg1.source = 'FILE'
            mdImg1.colorspace_settings.name = 'Non-Color'

        mdImgNode1 = CurMat.nodes.new("ShaderNodeTexImage")
        mdImgNode1.location = (-1330,-800)
        mdImgNode1.image = mdImg1
        mdImgNode1.hide = True
        mdImgNode1.label = "MicroDetail"

        mDetailUVScale02 = CurMat.nodes.new("ShaderNodeVectorMath")
        mDetailUVScale02.location = (-1400,-800)
        mDetailUVScale02.inputs[1].default_value[0] = float(Skin["MicroDetailUVScale02"])
        mDetailUVScale02.inputs[1].default_value[1] = float(Skin["MicroDetailUVScale02"])
        mDetailUVScale02.hide = True
        mDetailUVScale02.label = "MicroDetailUVScale02"
        mDetailUVScale02.operation = 'MULTIPLY'
        CurMat.links.new(mDetailUVScale02.outputs[0],mdImgNode1.inputs[0])

        Sep3 = CurMat.nodes.new("ShaderNodeSeparateRGB")
        Sep3.location = (-1050,-800)
        Sep3.hide = True
            
        Comb3 = CurMat.nodes.new("ShaderNodeCombineRGB")
        Comb3.location = (-900,-800)
        Comb3.hide = True
            
        CurMat.links.new(mdImgNode1.outputs[0],Sep3.inputs[0])
        CurMat.links.new(Sep3.outputs[0],Comb3.inputs[0])
        CurMat.links.new(Sep3.outputs[1],Comb3.inputs[1])
        Comb3.inputs[2].default_value = 1

        nMap3 = CurMat.nodes.new("ShaderNodeNormalMap")
        nMap3.location = (-750,-800)
        nMap3.hide = True
        CurMat.links.new(Comb3.outputs[0],nMap3.inputs[1])

        CurMat.links.new(mulNode1.outputs[0],nMap3.inputs[0])
        #Combining both MicroDetails

        UVMap = CurMat.nodes.new("ShaderNodeUVMap")
        UVMap.hide = True
        UVMap.location = (-1500,0)
        CurMat.links.new(UVMap.outputs[0],mDetailUVScale01.inputs[0])
        CurMat.links.new(UVMap.outputs[0],mDetailUVScale02.inputs[0])

        SubVec1 = CurMat.nodes.new("ShaderNodeVectorMath")
        SubVec1.hide = True
        SubVec1.location = (-650,-600)
        SubVec1.operation = 'SUBTRACT'
        CurMat.links.new(nMap2.outputs[0],SubVec1.inputs[0])

        Geo1 = CurMat.nodes.new("ShaderNodeNewGeometry")
        Geo1.hide = True
        Geo1.location = (-750,-700)
        CurMat.links.new(Geo1.outputs[1],SubVec1.inputs[1])

        AddVec1 = CurMat.nodes.new("ShaderNodeVectorMath")
        AddVec1.hide = True
        AddVec1.location = (-550,-700)
        AddVec1.operation = 'ADD'

        CurMat.links.new(SubVec1.outputs[0],AddVec1.inputs[0])
        CurMat.links.new(nMap3.outputs[0],AddVec1.inputs[1])

        # Combining microdetails and macrodetails
        SubVec2 = CurMat.nodes.new("ShaderNodeVectorMath")
        SubVec2.hide = True
        SubVec2.location = (-400,-400)
        SubVec2.operation = 'SUBTRACT'
        CurMat.links.new(AddVec1.outputs[0],SubVec2.inputs[0])

        Geo2 = CurMat.nodes.new("ShaderNodeNewGeometry")
        Geo2.hide = True
        Geo2.location = (-500,-500)
        CurMat.links.new(Geo2.outputs[1],SubVec2.inputs[1])

        AddVec2 = CurMat.nodes.new("ShaderNodeVectorMath")
        AddVec2.hide = True
        AddVec2.location = (-300,-300)
        AddVec2.operation = 'ADD'

        CurMat.links.new(SubVec2.outputs[0],AddVec2.inputs[1])
        CurMat.links.new(AddVec.outputs[0],AddVec2.inputs[0])

        Normalize = CurMat.nodes.new("ShaderNodeVectorMath")
        Normalize.hide = True
        Normalize.location = (-200,-300)
        Normalize.operation = 'NORMALIZE'

        CurMat.links.new(AddVec2.outputs[0],Normalize.inputs[0])
        CurMat.links.new(Normalize.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Normal'])
        
        #
        aImg = imageFromPath(self.BasePath + Skin["Albedo"],self.image_format)
            
        aImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        aImgNode.location = (-400,250)
        aImgNode.image = aImg
        aImgNode.label = "Albedo"

        CurMat.links.new(aImgNode.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])
            
        tColor = CurMat.nodes.new("ShaderNodeRGB")
        tColor.location = (-300,300)
        tColor.hide = True
        tColor.label = "TintColor"
        tColor.outputs[0].default_value = (float(Skin["TintColor"]["Red"])/255,float(Skin["TintColor"]["Green"])/255,float(Skin["TintColor"]["Blue"])/255,float(Skin["TintColor"]["Alpha"])/255)
        
        tmaskImg = imageFromPath(self.BasePath + Skin["TintColorMask"],self.image_format,True)
            
        tmaskNode = CurMat.nodes.new("ShaderNodeTexImage")
        tmaskNode.location = (-400,350)
        tmaskNode.image = tmaskImg
        tmaskNode.hide = True
        tmaskNode.label = "TintColorMask"

        mixRGB = CurMat.nodes.new("ShaderNodeMixRGB")
        mixRGB.location = (-150,200)
        mixRGB.hide = True
        mixRGB.blend_type = 'MULTIPLY'

        CurMat.links.new(tmaskNode.outputs[0],mixRGB.inputs[0])
        CurMat.links.new(tColor.outputs[0],mixRGB.inputs[2])
        CurMat.links.new(aImgNode.outputs[0],mixRGB.inputs[1])
        CurMat.links.new(mixRGB.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Base Color'])


        rImg = imageFromPath(self.BasePath + Skin["Roughness"],self.image_format,True)
            
        rImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        rImgNode.location = (-600,-50)
        rImgNode.image = rImg
        rImgNode.hide = True
        rImgNode.label = "Roughness"

        Sep = CurMat.nodes.new("ShaderNodeSeparateRGB")
        Sep.location = (-200,0)
        Sep.hide = True
        CurMat.links.new(rImgNode.outputs[0],Sep.inputs[0])
        CurMat.links.new(Sep.outputs[0],CurMat.nodes['Principled BSDF'].inputs['Roughness'])
        #CurMat.links.new(Sep.outputs[2],CurMat.nodes['Principled BSDF'].inputs['Specular'])
        CurMat.links.new(Sep.outputs[2],mulNode1.inputs[0])

        ndSqImg = imageFromPath(self.BasePath + Skin["Detailmap_Squash"],self.image_format)
            
        ndSqImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        ndSqImgNode.location = (-1100,0)
        ndSqImgNode.image = ndSqImg
        ndSqImgNode.hide = True
        ndSqImgNode.label = "Detailmap_Squash"


        ndStImg = imageFromPath(self.BasePath + Skin["Detailmap_Stretch"],self.image_format)
            
        ndStImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        ndStImgNode.location = (-1100,-100)
        ndStImgNode.image = ndStImg
        ndStImgNode.hide = True
        ndStImgNode.label = "Detailmap_Stretch"


        bfColor = CurMat.nodes.new("ShaderNodeRGB")
        bfColor.location = (-900,300)
        bfColor.hide = True
        bfColor.label = "BloodColor"
        bfColor.outputs[0].default_value = (float(Skin["BloodColor"]["Red"])/255,float(Skin["BloodColor"]["Green"])/255,float(Skin["BloodColor"]["Blue"])/255,float(Skin["BloodColor"]["Alpha"])/255)

        bfImg = imageFromPath(self.BasePath + Skin["Bloodflow"],self.image_format)

        bfImgNode = CurMat.nodes.new("ShaderNodeTexImage")
        bfImgNode.location = (-800,450)
        bfImgNode.image = bfImg
        bfImgNode.hide = True
        bfImgNode.label = "Bloodflow"