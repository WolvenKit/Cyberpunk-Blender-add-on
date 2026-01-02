from ..main.common import *
from ..jsontool import JSONTool

class Hair:
    def __init__(self, BasePath,image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self,hair,Mat):
        CurMat = Mat.node_tree
        Ns=CurMat.nodes
        sockets=bsdf_socket_names()

        file = (self.BasePath + hair["HairProfile"] + ".json")
        profile = JSONTool.jsonload(file)
        if profile is None:
            return

        profile= profile["Data"]["RootChunk"]

        # JATO: this fixes some normal issues like judy's hair but it's very wrong... TODO: fix hair flipped normals issue
        #CurMat.nodes[loc('Principled BSDF')].inputs[sockets['Specular']].default_value = 0

        Mat.blend_method = 'HASHED'
        vers = bpy.app.version
        if vers[0] == 4 and vers[1] <= 2:
            Mat.shadow_method = 'HASHED'

        idImg=imageFromRelPath(hair["Strand_ID"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.image_format, isNormal=True)
        idImgNode = create_node(Ns,"ShaderNodeTexImage",  (-1400,350), label="Strand_ID", image=idImg)

        gradImg=imageFromRelPath(hair["Strand_Gradient"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.image_format, isNormal=True)
        gradImgNode = create_node(Ns,"ShaderNodeTexImage",  (-1400,50), label="Strand_Gradient", image=gradImg)

        alphaImg=imageFromRelPath(hair["Strand_Alpha"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.image_format, isNormal=True)
        alphaImgNode = create_node(Ns,"ShaderNodeTexImage",  (-1400,-300), label="Strand_Alpha", image=alphaImg)

        # JATO: redengine file for this says it's srgb? wtf?
        flowImg = imageFromRelPath(hair["Flow"],DepotPath=self.BasePath, ProjPath=self.ProjPath, image_format=self.image_format)
        flowImgNode = create_node(Ns,"ShaderNodeTexImage",  (-1400,-600), label="Flow", image=flowImg)


        ID = create_node(Ns,"ShaderNodeValToRGB", (-1000,350), label = "GradientEntriesID")
        ID.color_ramp.elements.remove(ID.color_ramp.elements[0])
        ID.hide = False
        counter = 0
        for Entry in profile["gradientEntriesID"]:
            if counter == 0:
                ID.color_ramp.elements[0].position = Entry.get("value",0)
                colr = Entry["color"]
                ID.color_ramp.elements[0].color = (float(colr["Red"])/255,float(colr["Green"])/255,float(colr["Blue"])/255,float(1))
            else:
                element = ID.color_ramp.elements.new(Entry.get("value",0))
                colr = Entry["color"]
                element.color = (float(colr["Red"])/255,float(colr["Green"])/255,float(colr["Blue"])/255,float(1))
            counter = counter + 1

        RootToTip = create_node(Ns,"ShaderNodeValToRGB", (-1000,50), label = "GradientEntriesRootToTip")
        RootToTip.color_ramp.elements.remove(RootToTip.color_ramp.elements[0])
        RootToTip.hide = False
        counter = 0
        for Entry in profile["gradientEntriesRootToTip"]:
            if counter == 0:
                RootToTip.color_ramp.elements[0].position = Entry.get("value",0)
                colr = Entry["color"]
                RootToTip.color_ramp.elements[0].color = (float(colr["Red"])/255,float(colr["Green"])/255,float(colr["Blue"])/255,float(1))
            else:
                element = RootToTip.color_ramp.elements.new(Entry.get("value",0))
                colr = Entry["color"]
                element.color =  (float(colr["Red"])/255,float(colr["Green"])/255,float(colr["Blue"])/255,float(1))
            counter = counter + 1


        mulNode = create_node(Ns,"ShaderNodeMixRGB", (-650,200), blend_type = 'MULTIPLY')
        mulNode.inputs[0].default_value = 1

        gamma0 = create_node(Ns,"ShaderNodeGamma",(-450,200))
        gamma0.inputs[1].default_value = 2.2

        CurMat.links.new(alphaImgNode.outputs[0],CurMat.nodes[loc('Principled BSDF')].inputs['Alpha'])

        CurMat.links.new(gradImgNode.outputs[0],RootToTip.inputs[0])

        CurMat.links.new(idImgNode.outputs[0],ID.inputs[0])

        CurMat.links.new(ID.outputs[0],mulNode.inputs[1])
        CurMat.links.new(RootToTip.outputs[0],mulNode.inputs[2])

        CurMat.links.new(mulNode.outputs[0],gamma0.inputs[0])
        CurMat.links.new(gamma0.outputs[0],CurMat.nodes[loc('Principled BSDF')].inputs['Base Color'])

