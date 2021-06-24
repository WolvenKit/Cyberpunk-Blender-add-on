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

def createMaterials(obj,BasePath,image_format):

        for rawMat in obj["Materials"]:
            bpyMat = bpy.data.materials.new(rawMat["Name"])
            bpyMat.use_nodes = True
            if rawMat["MaterialType"] == "_multilayered":
                mulLayer = Multilayered(BasePath,obj["MaterialTemplates"],image_format)
                index = 0
                for i in range (0,len(obj["MaterialSetups"])):
                    if str(os.path.basename(rawMat["_multilayered"].get("MultilayerSetup"))) == str(obj["MaterialSetups"][i]["Name"]):
                        index = i
                globnormal = rawMat["_multilayered"].get("GlobalNormal")
                mlmask = rawMat["_multilayered"].get("MultilayerMask")
                mulLayer.create(obj["MaterialSetups"][index],mlmask,bpyMat,globnormal)

            if rawMat["MaterialType"] == "_mesh_decal":
                if rawMat.get("_mesh_decal"):
                    mesDec = MeshDecal(BasePath,image_format)
                    mesDec.create(rawMat["_mesh_decal"],bpyMat)
            if rawMat["MaterialType"] == "_skin":
                if rawMat.get("_skin"):
                    humskin = HumanSkin(BasePath,image_format)
                    humskin.create(rawMat["_skin"],bpyMat)
            if rawMat["MaterialType"] == "_metal_base":
                if rawMat.get("_metal_base"):
                    metbase = MetalBase(BasePath,image_format)
                    metbase.create(rawMat["_metal_base"],bpyMat)
            if rawMat["MaterialType"] == "_hair":
                if rawMat.get("_hair"):
                    h = Hair(BasePath,obj["HairProfiles"],image_format)
                    h.create(rawMat["_hair"],bpyMat)
            if rawMat["MaterialType"] == "_mesh_decal_gradientmap_recolor":
                if rawMat.get("_mesh_decal_gradientmap_recolor"):
                    hC = MeshDecalGradientMapReColor(BasePath,image_format)
                    hC.create(rawMat["_mesh_decal_gradientmap_recolor"],bpyMat)
            if rawMat["MaterialType"] == "_eye":
                if rawMat.get("_eye"):
                    eye = Eye(BasePath,image_format)
                    eye.create(rawMat["_eye"],bpyMat)
            if rawMat["MaterialType"] == "_eye_shadow":
                if rawMat.get("_eye_shadow"):
                    eS = EyeShadow(BasePath,image_format)
                    eS.create(rawMat["_eye_shadow"],bpyMat)
            if rawMat["MaterialType"] == "_mesh_decal_emissive":
                if rawMat.get("_mesh_decal_emissive"):
                    decEmiss = MeshDecalEmissive(BasePath,image_format)
                    decEmiss.create(rawMat["_mesh_decal_emissive"],bpyMat)