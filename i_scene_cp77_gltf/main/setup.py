
import bpy
import os
from ..material_types.multilayered import Multilayered
from ..material_types.multilayeredclearcoat import MultilayeredClearCoat
from ..material_types.vehicledestrblendshape import VehicleDestrBlendshape
from ..material_types.skin import Skin
from ..material_types.meshdecal import MeshDecal
from ..material_types.meshdecaldoublediffuse import MeshDecalDoubleDiffuse
from ..material_types.vehiclemeshdecal import VehicleMeshDecal
from ..material_types.metalbase import MetalBase
from ..material_types.hair import Hair
from ..material_types.meshdecalgradientmaprecolor import MeshDecalGradientMapReColor
from ..material_types.eye import Eye
from ..material_types.eyegradient import EyeGradient
from ..material_types.eyeshadow import EyeShadow
from ..material_types.meshdecalemissive import MeshDecalEmissive
from ..material_types.glass import Glass
from ..material_types.signages import Signages
from ..material_types.meshdecalparallax import MeshDecalParallax
from ..material_types.multilayeredTerrain import MultilayeredTerrain
from ..material_types.speedtree import SpeedTree


class MaterialBuilder:
    def __init__(self,Obj,BasePath,image_format):
        self.BasePath = BasePath
        self.image_format = image_format
        self.obj = Obj
    def create(self,materialIndex):
        rawMat = self.obj["Materials"][materialIndex]
        
        

        verbose=True

        bpyMat = bpy.data.materials.new(rawMat["Name"])
        bpyMat.use_nodes = True
        match rawMat["MaterialTemplate"]:
            case "engine\\materials\\multilayered.mt":
                multilayered = Multilayered(self.BasePath,self.image_format)
                multilayered.create(rawMat["Data"],bpyMat)

            case "base\\materials\\multilayered_clear_coat.mt":
                multilayered = Multilayered(self.BasePath,self.image_format)
                multilayered.create(rawMat["Data"],bpyMat)

            case "base\\materials\\vehicle_destr_blendshape.mt":
                vehicleDestrBlendshape = VehicleDestrBlendshape(self.BasePath,self.image_format)
                vehicleDestrBlendshape.create(rawMat["Data"],bpyMat)

            case "base\\materials\\mesh_decal.mt":
                meshDecal = MeshDecal(self.BasePath,self.image_format)
                meshDecal.create(rawMat["Data"],bpyMat)

            case "base\\materials\\mesh_decal_double_diffuse.mt":
                meshDecalDoubleDiffuse = MeshDecalDoubleDiffuse(self.BasePath,self.image_format)
                meshDecalDoubleDiffuse.create(rawMat["Data"],bpyMat)

            case "base\\materials\\vehicle_mesh_decal.mt":
                vehicleMeshDecal = VehicleMeshDecal(self.BasePath,self.image_format)
                vehicleMeshDecal.create(rawMat["Data"],bpyMat)

            case "base\\materials\\skin.mt":
                skin = Skin(self.BasePath,self.image_format)
                skin.create(rawMat["Data"],bpyMat)

            case "engine\\materials\\metal_base.remt":
                metalBase = MetalBase(self.BasePath,self.image_format)
                metalBase.create(rawMat["Data"],bpyMat)

            case "base\\materials\\hair.mt":
                hair = Hair(self.BasePath,self.image_format)
                hair.create(rawMat["Data"],bpyMat)

            case "base\\materials\\mesh_decal_gradientmap_recolor.mt":
                meshDecalGradientMapReColor = MeshDecalGradientMapReColor(self.BasePath,self.image_format)
                meshDecalGradientMapReColor.create(rawMat["Data"],bpyMat)

            case "base\\materials\\eye.mt":
                eye = Eye(self.BasePath,self.image_format)
                eye.create(rawMat["Data"],bpyMat)

            case "base\\materials\\eye_gradient.mt":
                eyeGradient = EyeGradient(self.BasePath,self.image_format)
                eyeGradient.create(rawMat["Data"],bpyMat)

            case "base\\materials\\eye_shadow.mt":
                eyeShadow = EyeShadow(self.BasePath,self.image_format)
                eyeShadow.create(rawMat["Data"],bpyMat)

            case "base\\materials\\mesh_decal_emissive.mt":
                meshDecalEmissive = MeshDecalEmissive(self.BasePath,self.image_format)
                meshDecalEmissive.create(rawMat["Data"],bpyMat)

            case "base\\materials\\mesh_decal_wet_character.mt":
                meshDecal = MeshDecal(self.BasePath,self.image_format)
                meshDecal.create(rawMat["Data"],bpyMat)

            case "base\\materials\\glass.mt":
                glass = Glass(self.BasePath,self.image_format)
                glass.create(rawMat["Data"],bpyMat)
            
            case "base\\fx\\shaders\\signages.mt":
                signages= Signages(self.BasePath,self.image_format)
                signages.create(rawMat["Data"],bpyMat)
            
            case "base\\materials\\glass_onesided.mt":
                glass = Glass(self.BasePath,self.image_format)
                glass.create(rawMat["Data"],bpyMat)
            
            case "base\\materials\\mesh_decal_parallax.mt":
                meshDecalParallax = MeshDecalParallax(self.BasePath,self.image_format)
                meshDecalParallax.create(rawMat["Data"],bpyMat)
            
            case "base\\materials\\multilayered_terrain.mt":
                multilayeredTerrain = MultilayeredTerrain(self.BasePath,self.image_format)
                multilayeredTerrain.create(rawMat["Data"],bpyMat)
                
            case "base\\materials\\speedtree_3d_v8_twosided.mt":
                speedtree = SpeedTree(self.BasePath,self.image_format)
                speedtree.create(rawMat["Data"],bpyMat)

            case _:
                print('Unhandled mt - ', rawMat["MaterialTemplate"])

        #set the viewport blend mode to hashed - no more black tattoos and cybergear
        bpyMat.blend_method='HASHED'
        return bpyMat

