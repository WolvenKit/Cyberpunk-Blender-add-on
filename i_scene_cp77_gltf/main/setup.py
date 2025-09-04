
import bpy
import os
import sys
from ..material_types.multilayered import Multilayered
from ..material_types.multilayeredclearcoat import MultilayeredClearCoat
from ..material_types.vehicledestrblendshape import VehicleDestrBlendshape
from ..material_types.skin import Skin
from ..material_types.meshdecal import MeshDecal
from ..material_types.meshdecaldoublediffuse import MeshDecalDoubleDiffuse
from ..material_types.vehiclemeshdecal import VehicleMeshDecal
from ..material_types.vehiclelights import VehicleLights
from ..material_types.metalbase import MetalBase
from ..material_types.metalbasedet import MetalBaseDet
from ..material_types.hair import Hair
from ..material_types.meshdecalgradientmaprecolor import MeshDecalGradientMapReColor
from ..material_types.eye import Eye
from ..material_types.eyegradient import EyeGradient
from ..material_types.eyeshadow import EyeShadow
from ..material_types.meshdecalemissive import MeshDecalEmissive
from ..material_types.glass import Glass
from ..material_types.glassdeferred import GlassDeferred
from ..material_types.signages import Signages
from ..material_types.meshdecalparallax import MeshDecalParallax
from ..material_types.parallaxscreen import ParallaxScreen
from ..material_types.parallaxscreentransparent import ParallaxScreenTransparent
from ..material_types.speedtree import SpeedTree
from ..material_types.decal import Decal
from ..material_types.decal_gradientmap_recolor import DecalGradientmapRecolor
from ..material_types.televisionad import TelevisionAd
from ..material_types.window_parallax_interior_proxy import windowParallaxIntProx
from ..material_types.hologram import Hologram
from ..material_types.unknown import unknownMaterial
from ..material_types.pbr_layer import pbr_layer
from .material_registry import REGISTRY, DECAL_REGISTRY

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class MaterialBuilder:
    def __init__(self, obj, BasePath,image_format,MeshPath):
        self.BasePath = BasePath
        self.image_format = image_format
        self.obj = obj # = Obj
        self.MeshPath= MeshPath
        before,mid,after=MeshPath.partition('source\\raw\\'.replace('\\',os.sep))
        self.ProjPath=before+mid
        self.addon_module = sys.modules["i_scene_cp77_gltf"]
        self.addon_ver = self.addon_module.bl_info['version']

    def create(self, mats, materialIndex):
        if mats:
            rawMat = mats[materialIndex]

            verbose=True

            bpyMat = bpy.data.materials.new(rawMat["Name"])
            bpyMat['MeshPath'] = self.MeshPath
            bpyMat['DepotPath'] = self.BasePath
            bpyMat['ProjPath']= self.ProjPath
            bpyMat['MaterialTemplate'] = rawMat["MaterialTemplate"]
            bpyMat['AddonVersion'] = self.addon_ver
            bpyMat.use_nodes = True
            no_shadows=False
            material_template = rawMat["MaterialTemplate"].replace('/','\\')
            rule = REGISTRY.resolve(material_template)
            if rule:
                instance = rule.factory(self, rawMat)
                instance.create(rawMat["Data"], bpyMat)
                no_shadows = rule.no_shadows
                bpyMat.blend_method='HASHED'
                bpyMat['no_shadows']=no_shadows
                return bpyMat
            print(f'{bcolors.WARNING}Unhandled mt - ', rawMat["MaterialTemplate"])
            context=bpy.context
            if context.preferences.addons[__name__.split('.')[0]].preferences.experimental_features:
                unkown = unknownMaterial(self.BasePath,self.image_format,self.ProjPath)
                unkown.create(rawMat["Data"],bpyMat)

            #set the viewport blend mode to hashed - no more black tattoos and cybergear
            bpyMat.blend_method='HASHED'
            bpyMat['no_shadows']=no_shadows
            return bpyMat

        else:
            self.obj["Data"]["RootChunk"].get("baseMaterial")
            if self.obj["Header"].get("ArchiveFileName"):
                name = self.obj["Header"]["ArchiveFileName"]
                name = os.path.basename(name)
            else:
                name = 'decal_material'

            bpyMat = bpy.data.materials.new(name)
            bpyMat.use_nodes = True

            base_path = self.obj["Data"]["RootChunk"]["baseMaterial"]["DepotPath"]['$value']
            drule = DECAL_REGISTRY.resolve(base_path)
            if drule:
                instance = drule.factory(self, self.obj["Data"]["RootChunk"]) 
                instance.create(self.obj["Data"]["RootChunk"], bpyMat)
                bpyMat.blend_method='HASHED'
                return bpyMat

            print(base_path, " | unimplemented yet")

            bpyMat.blend_method='HASHED'
            return bpyMat

    def createdecal(self,materialIndex):
        if self.obj["Data"]["RootChunk"].get("baseMaterial"):
            if self.obj["Header"].get("ArchiveFileName"):
                name = self.obj["Header"]["ArchiveFileName"]
                name = os.path.basename(name)
            else:
                name = 'decal_material'

            bpyMat = bpy.data.materials.new(name)
            bpyMat.use_nodes = True

            base_path = self.obj["Data"]["RootChunk"]["baseMaterial"]["DepotPath"]['$value']
            drule = DECAL_REGISTRY.resolve(base_path)
            if drule:
                instance = drule.factory(self, self.obj["Data"]["RootChunk"]) 
                instance.create(self.obj["Data"]["RootChunk"], bpyMat)
                bpyMat.blend_method='HASHED'
                return bpyMat

            print(base_path, " | unimplemented yet")

            bpyMat.blend_method='HASHED'
            return bpyMat
