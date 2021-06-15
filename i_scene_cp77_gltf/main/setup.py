import bpy
import os
from ..material_types.multilayer import Multilayered
from ..material_types.humanskin import Humanskin
from ..material_types.meshdecal import MeshDecal
from ..material_types.metalbase import MetalBase

def createMaterials(obj,BasePath,image_format):
        valueToIgnore = float(obj["valueToBeIgnored"])

        for rawMat in obj["rawMaterials"]:
            bpyMat = bpy.data.materials.new(rawMat["name"])
            bpyMat.use_nodes = True
            if int(rawMat["materialType"]) == 1:
                mulLayer = Multilayered(BasePath,valueToIgnore,obj["materialTemplates"],image_format)
                index = 0
                for i in range (0,len(obj["materialSetups"])):
                    if str(os.path.basename(rawMat["materialInstanceData"].get("multilayerSetup"))) == str(obj["materialSetups"][i]["name"]):
                        index = i
                globnormal = rawMat["materialInstanceData"].get("globalNormal")
                mlmask = rawMat["materialInstanceData"].get("multilayerMask")
                mulLayer.create(obj["materialSetups"][index],mlmask,bpyMat,globnormal)
            if int(rawMat["materialType"]) == 2:
                if rawMat.get("materialInstanceData"):
                    mesDec = MeshDecal(BasePath,valueToIgnore,image_format)
                    mesDec.create(rawMat["materialInstanceData"],bpyMat)
            if int(rawMat["materialType"]) == 3:
                if rawMat.get("materialInstanceData"):
                    humskin = Humanskin(BasePath,valueToIgnore,image_format)
                    humskin.create(rawMat["materialInstanceData"],bpyMat)
            if int(rawMat["materialType"]) == 4:
                if rawMat.get("materialInstanceData"):
                    metbase = MetalBase(BasePath,valueToIgnore,image_format)
                    metbase.create(rawMat["materialInstanceData"],bpyMat)