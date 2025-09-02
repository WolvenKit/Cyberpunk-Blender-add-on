
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
            match material_template:
                case "engine\\materials\\multilayered.mt" | "base\\materials\\vehicle_destr_blendshape.mt" | "base\\materials\\multilayered_clear_coat.mt" |  "base\\materials\\multilayered_terrain.mt":
                    multilayered = Multilayered(self.BasePath,self.image_format,self.ProjPath)
                    multilayered.create(rawMat["Data"],bpyMat)


                #case  "base\\materials\\multilayered_terrain.mt":
                 #   multilayeredTerrain = Multilayered(self.BasePath,self.image_format, self.ProjPath)
                  #  multilayeredTerrain.create(rawMat["Data"],bpyMat)

                # This material should be handled within the main multilayered.py file. Commenting this out for now in case I broke something - jato
                #case "base\\materials\\multilayered_clear_coat.mt":
                    #multilayered = MultilayeredClearCoat(self.BasePath,self.image_format)
                    #multilayered.create(rawMat["Data"],bpyMat)

                # This material should be handled within the main multilayered.py file. Commenting this out for now in case I broke something - jato
                #case "base\\materials\\vehicle_destr_blendshape.mt":
                    #vehicleDestrBlendshape = VehicleDestrBlendshape(self.BasePath, self.image_format)
                    #vehicleDestrBlendshape.create(rawMat["Data"],bpyMat)

                case "base\\materials\\mesh_decal.mt" | "base\\materials\\mesh_decal_wet_character.mt":
                    if 'EnableMask' in rawMat.keys():
                        enableMask=rawMat['EnableMask']
                    else:
                        enableMask=False
                    no_shadows=True
                    meshDecal = MeshDecal(self.BasePath, self.image_format, self.ProjPath,enableMask)
                    meshDecal.create(rawMat["Data"],bpyMat)

                case "base\\materials\\mesh_decal_double_diffuse.mt":
                    no_shadows=True
                    meshDecalDoubleDiffuse = MeshDecalDoubleDiffuse(self.BasePath, self.image_format)
                    meshDecalDoubleDiffuse.create(rawMat["Data"],bpyMat)

                case "base\\materials\\vehicle_mesh_decal.mt" :
                    no_shadows=True
                    if 'EnableMask' in rawMat.keys():
                        enableMask=rawMat['EnableMask']
                    else:
                        enableMask=False
                    vehicleMeshDecal = VehicleMeshDecal(self.BasePath, self.image_format, self.ProjPath, enableMask)
                    vehicleMeshDecal.create(rawMat["Data"],bpyMat)

                case "base\\materials\\vehicle_lights.mt":
                    vehicleLights = VehicleLights(self.BasePath, self.image_format, self.ProjPath)
                    vehicleLights.create(rawMat["Data"],bpyMat)

                case "base\\materials\\skin.mt":
                    skin = Skin(self.BasePath, self.image_format, self.ProjPath)
                    skin.create(rawMat["Data"],bpyMat)

                case "engine\\materials\\metal_base.remt" | "engine\\materials\\metal_base_proxy.mt" |\
                    'base\\materials\\metal_base_parallax.mt' | 'base\materials\metal_base_gradientmap_recolor.mt':
                    if 'EnableMask' in rawMat.keys():
                        enableMask=rawMat['EnableMask']
                    else:
                        enableMask=False
                    metalBase = MetalBase(self.BasePath,self.image_format, self.ProjPath, enableMask)
                    metalBase.create(rawMat["Data"],bpyMat)

                case "base\\materials\\metal_base_det.mt" | "base\materials\lights_interactive.mt":
                    metalBaseDet = MetalBaseDet(self.BasePath,self.image_format, self.ProjPath)
                    metalBaseDet.create(rawMat["Data"],bpyMat)

                case "base\\materials\\pbr_layer.remt":
                    pbrLayer = pbr_layer(self.BasePath,self.image_format, self.ProjPath)
                    pbrLayer.create(rawMat["Data"],bpyMat)

                case "base\\materials\\hair.mt":
                    hair = Hair(self.BasePath,self.image_format, self.ProjPath)
                    hair.create(rawMat["Data"],bpyMat)

                case "base\\materials\\mesh_decal_gradientmap_recolor.mt":
                    no_shadows=True
                    meshDecalGradientMapReColor = MeshDecalGradientMapReColor(self.BasePath,self.image_format, self.ProjPath)
                    meshDecalGradientMapReColor.create(rawMat["Data"],bpyMat)

                case "base\\materials\\eye.mt":
                    eye = Eye(self.BasePath,self.image_format, self.ProjPath)
                    eye.create(rawMat["Data"],bpyMat)

                case "base\\materials\\eye_gradient.mt":
                    eyeGradient = EyeGradient(self.BasePath,self.image_format, self.ProjPath)
                    eyeGradient.create(rawMat["Data"],bpyMat)

                case "base\\materials\\eye_shadow.mt":
                    eyeShadow = EyeShadow(self.BasePath,self.image_format, self.ProjPath)
                    eyeShadow.create(rawMat["Data"],bpyMat)

                case "base\\materials\\mesh_decal_emissive.mt" :
                    no_shadows=True
                    meshDecalEmissive = MeshDecalEmissive(self.BasePath,self.image_format, self.ProjPath)
                    meshDecalEmissive.create(rawMat["Data"],bpyMat)

                case "base\\materials\\glass.mt" | "base\\materials\\vehicle_glass.mt":
                    glass = Glass(self.BasePath,self.image_format, self.ProjPath)
                    glass.create(rawMat["Data"],bpyMat)

                case "base\\materials\\glass_deferred.mt":
                    glassdef = GlassDeferred(self.BasePath,self.image_format, self.ProjPath)
                    glassdef.create(rawMat["Data"],bpyMat)

                case "base\\fx\\shaders\\signages.mt" :
                    signages= Signages(self.BasePath,self.image_format, self.ProjPath)
                    signages.create(rawMat["Data"],bpyMat)

                case "base\\materials\\glass_onesided.mt" | "base\\materials\\vehicle_glass_onesided.mt":
                    glass = Glass(self.BasePath,self.image_format, self.ProjPath)
                    glass.create(rawMat["Data"],bpyMat)

                case "base\\materials\\mesh_decal_parallax.mt" | "base\\materials\\vehicle_mesh_decal_parallax.mt":
                    no_shadows=True
                    meshDecalParallax = MeshDecalParallax(self.BasePath,self.image_format, self.ProjPath)
                    meshDecalParallax.create(rawMat["Data"],bpyMat)

                case  "base\\fx\\shaders\\parallaxscreen.mt" :
                    parallaxScreen = ParallaxScreen(self.BasePath,self.image_format,self.ProjPath)
                    parallaxScreen.create(rawMat["Data"],bpyMat)

                case  "base\\fx\\shaders\\parallaxscreen_transparent.mt" :
                    parallaxScreenTransparent = ParallaxScreenTransparent(self.BasePath,self.image_format,self.ProjPath)
                    parallaxScreenTransparent.create(rawMat["Data"],bpyMat)

                case "base\\materials\\speedtree_3d_v8_twosided.mt" |  "base\\materials\\speedtree_3d_v8_onesided.mt" |  "base\\materials\\speedtree_3d_v8_seams.mt":
                    speedtree = SpeedTree(self.BasePath,self.image_format, self.ProjPath)
                    speedtree.create(rawMat["Data"],bpyMat)

                case  "base\\fx\\shaders\\television_ad.mt" :
                    televisionAd = TelevisionAd(self.BasePath,self.image_format,self.ProjPath)
                    televisionAd.create(rawMat["Data"],bpyMat)

                case "base\\materials\\window_parallax_interior_proxy.mt" | "base\\materials\\window_parallax_interior.mt":
                    window = windowParallaxIntProx(self.BasePath,self.image_format,self.ProjPath)
                    window.create(rawMat["Data"],bpyMat)

                case  "base\\fx\\shaders\\hologram.mt" :
                    hologram = Hologram(self.BasePath,self.image_format,self.ProjPath)
                    hologram.create(rawMat["Data"],bpyMat)

                case _:
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

            match self.obj["Data"]["RootChunk"]["baseMaterial"]["DepotPath"]['$value']:
                case "base\\materials\\decal.remt" | "base\\materials\\decal_roughness.mt" | "base\\materials\\decal_puddle.mt" | "base\materials\decal_normal_roughness_metalness.mt":
                    print('decal.remt')
                    decal = Decal(self.BasePath,self.image_format)
                    decal.create(self.obj["Data"]["RootChunk"],bpyMat)

                case "base\\materials\\decal_gradientmap_recolor.mt":
                    print('decal_gradientmap_recolor.mt')
                    decalGradientMapRecolor = DecalGradientmapRecolor(self.BasePath,self.image_format, self.ProjPath)
                    decalGradientMapRecolor.create(self.obj["Data"]["RootChunk"],bpyMat)


                case _:
                    print(self.obj["Data"]["RootChunk"]["baseMaterial"]["DepotPath"]['$value']," | unimplemented yet")

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

            match self.obj["Data"]["RootChunk"]["baseMaterial"]["DepotPath"]['$value']:
                case "base\\materials\\decal.remt" | "base\\materials\\decal_roughness.mt" | "base\\materials\\decal_puddle.mt" | "base\\materials\\decal_normal_roughness_metalness.mt"|  \
                    'base\\materials\\decal_normal_roughness.mt' | 'base\\surfaces\\textures\\decals\\road_markings\\materials\\road_markings_white.mi' | 'base\\materials\\decal_parallax.mt' |  \
                    'base\\materials\\decal_normal_roughness_metalness.mt' | 'base\\materials\\decal_normal_roughness_metalness_2.mt' | 'base\\materials\\decal_terrain_projected.mt' | 'base\\materials\\decal_normal.remt' :
                    print('decal.remt')
                    decal = Decal(self.BasePath,self.image_format)
                    decal.create(self.obj["Data"]["RootChunk"],bpyMat)

                case "base\\materials\\decal_gradientmap_recolor.mt":
                    print('decal_gradientmap_recolor.mt')
                    decalGradientMapRecolor = DecalGradientmapRecolor(self.BasePath,self.image_format, self.ProjPath)
                    decalGradientMapRecolor.create(self.obj["Data"]["RootChunk"],bpyMat)


                case _:
                    print(self.obj["Data"]["RootChunk"]["baseMaterial"]["DepotPath"]['$value']," | unimplemented yet")

            bpyMat.blend_method='HASHED'
            return bpyMat
