import bpy
import os
from ..material_types.multilayered import Multilayered
from ..material_types.vehicleDestrBlendshape import VehicleDestrBlendshape
from ..material_types.skin import Skin
from ..material_types.meshDecal import MeshDecal
from ..material_types.meshDecalDoubleDiffuse import MeshDecalDoubleDiffuse
from ..material_types.vehicleMeshDecal import VehicleMeshDecal
from ..material_types.metalBase import MetalBase
from ..material_types.hair import Hair
from ..material_types.meshDecalGradientMapReColor import MeshDecalGradientMapReColor
from ..material_types.eye import Eye
from ..material_types.eyeGradient import EyeGradient
from ..material_types.eyeShadow import EyeShadow
from ..material_types.meshDecalEmissive import MeshDecalEmissive
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

        if rawMat["MaterialTemplate"] == "engine\\materials\\multilayered.mt":
            multilayered = Multilayered(self.BasePath,self.image_format)
            multilayered.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "base\\materials\\vehicle_destr_blendshape.mt":
            vehicleDestrBlendshape = VehicleDestrBlendshape(self.BasePath,self.image_format)
            vehicleDestrBlendshape.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "base\\materials\\mesh_decal.mt":
            meshDecal = MeshDecal(self.BasePath,self.image_format)
            meshDecal.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "base\\materials\\mesh_decal_double_diffuse.mt":
            meshDecalDoubleDiffuse = MeshDecalDoubleDiffuse(self.BasePath,self.image_format)
            meshDecalDoubleDiffuse.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "base\\materials\\vehicle_mesh_decal.mt":
            vehicleMeshDecal = VehicleMeshDecal(self.BasePath,self.image_format)
            vehicleMeshDecal.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "base\\materials\\skin.mt":
            skin = Skin(self.BasePath,self.image_format)
            skin.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "engine\\materials\\metal_base.remt":
            metalBase = MetalBase(self.BasePath,self.image_format)
            metalBase.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "base\\materials\\hair.mt":
            hair = Hair(self.BasePath,self.image_format)
            hair.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "base\\materials\\mesh_decal_gradientmap_recolor.mt":
            meshDecalGradientMapReColor = MeshDecalGradientMapReColor(self.BasePath,self.image_format)
            meshDecalGradientMapReColor.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "base\\materials\\eye.mt":
            eye = Eye(self.BasePath,self.image_format)
            eye.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "base\\materials\\eye_gradient.mt":
            eyeGradient = EyeGradient(self.BasePath,self.image_format)
            eyeGradient.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "base\\materials\\eye_shadow.mt":
            eyeShadow = EyeShadow(self.BasePath,self.image_format)
            eyeShadow.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "base\\materials\\mesh_decal_emissive.mt":
            meshDecalEmissive = MeshDecalEmissive(self.BasePath,self.image_format)
            meshDecalEmissive.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "base\\materials\\mesh_decal_wet_character.mt":
            meshDecal = MeshDecal(self.BasePath,self.image_format)
            meshDecal.create(rawMat["Data"],bpyMat)

        if rawMat["MaterialTemplate"] == "base\\materials\\glass.mt":
            glass = Glass(self.BasePath,self.image_format)
            glass.create(rawMat["Data"],bpyMat)

        return bpyMat