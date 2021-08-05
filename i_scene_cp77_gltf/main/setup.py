import bpy
import os
from ..material_types.multilayer import Multilayered
from ..material_types.humanskin import HumanSkin
from ..material_types.meshdecal import MeshDecal
from ..material_types.metalbase import MetalBase
from ..material_types.hair import Hair
from ..material_types.meshdecalgradientmaprecolor import MeshDecalGradientMapReColor
from ..material_types.eye import Eye
from ..material_types.eyeshadow import EyeShadow
from ..material_types.meshdecalemissive import MeshDecalEmissive
from ..material_types.glass import Glass

class MaterialBuilder:
    def __init__(self,Obj,BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
        self.obj = Obj
    def create(self,materialIndex):
        rawMat = self.obj["Materials"][materialIndex]

        bpyMat = bpy.data.materials.new(rawMat["Name"])
        bpyMat.use_nodes = True

        if rawMat["MaterialType"] == "_multilayered":
            mulLayer = Multilayered(self.BasePath,self.image_format)
            mlsetup = rawMat["_multilayered"].get("MultilayerSetup")
            globnormal = rawMat["_multilayered"].get("GlobalNormal")
            mlmask = rawMat["_multilayered"].get("MultilayerMask")
            mulLayer.create(mlsetup,mlmask,bpyMat,globnormal)

        if rawMat["MaterialType"] == "_mesh_decal":
            if rawMat.get("_mesh_decal"):
                mesDec = MeshDecal(self.BasePath,self.image_format)
                mesDec.create(rawMat["_mesh_decal"],bpyMat)

        if rawMat["MaterialType"] == "_skin":
            if rawMat.get("_skin"):
                humskin = HumanSkin(self.BasePath,self.image_format)
                humskin.create(rawMat["_skin"],bpyMat)

        if rawMat["MaterialType"] == "_metal_base":
            if rawMat.get("_metal_base"):
                metbase = MetalBase(self.BasePath,self.image_format)
                metbase.create(rawMat["_metal_base"],bpyMat)

        if rawMat["MaterialType"] == "_hair":
            if rawMat.get("_hair"):
                h = Hair(self.BasePath,self.image_format)
                h.create(rawMat["_hair"],bpyMat)

        if rawMat["MaterialType"] == "_mesh_decal_gradientmap_recolor":
            if rawMat.get("_mesh_decal_gradientmap_recolor"):
                hC = MeshDecalGradientMapReColor(self.BasePath,self.image_format)
                hC.create(rawMat["_mesh_decal_gradientmap_recolor"],bpyMat)

        if rawMat["MaterialType"] == "_eye":
            if rawMat.get("_eye"):
                eye = Eye(self.BasePath,self.image_format)
                eye.create(rawMat["_eye"],bpyMat)

        if rawMat["MaterialType"] == "_eye_shadow":
            if rawMat.get("_eye_shadow"):
                eS = EyeShadow(self.BasePath,self.image_format)
                eS.create(rawMat["_eye_shadow"],bpyMat)

        if rawMat["MaterialType"] == "_mesh_decal_emissive":
            if rawMat.get("_mesh_decal_emissive"):
                decEmiss = MeshDecalEmissive(self.BasePath,self.image_format)
                decEmiss.create(rawMat["_mesh_decal_emissive"],bpyMat)

        if rawMat["MaterialType"] == "_mesh_decal_wet_character":
            if rawMat.get("_mesh_decal_wet_character"):
                mesDec = MeshDecal(self.BasePath,self.image_format)
                mesDec.create(rawMat["_mesh_decal_wet_character"],bpyMat)

        if rawMat["MaterialType"] == "_glass":
            if rawMat.get("_glass"):
                glass = Glass(self.BasePath,self.image_format)
                glass.create(rawMat["_glass"],bpyMat)

        return bpyMat