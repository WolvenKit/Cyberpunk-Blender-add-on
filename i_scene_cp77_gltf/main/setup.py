import bpy
import os
from ..material_types.multilayer import Multilayered

def createMaterials(obj,BasePath):
        valueToIgnore = float(obj["valueToBeIgnored"])
        mulLayer = Multilayered(BasePath,valueToIgnore,obj["materialTemplates"])
        for rawMat in obj["rawMaterials"]:
            bpyMat = bpy.data.materials.new(rawMat["name"])
            bpyMat.use_nodes = True
            if int(rawMat["materialType"]) == 1:
                index = 0
                for i in range (0,len(obj["materialSetups"])):
                    if str(os.path.basename(rawMat["multiLayered"].get("multilayerSetup"))) == str(obj["materialSetups"][i]["name"]):
                        index = i
                globnormal = rawMat["multiLayered"].get("globalNormal")
                mlmask = rawMat["multiLayered"].get("multilayerMask")
                mulLayer.create(obj["materialSetups"][index],mlmask,bpyMat,globnormal)