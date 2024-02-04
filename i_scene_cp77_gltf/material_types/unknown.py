import bpy
import os
from ..main.common import *
from .interior_mapping_nodegroups import *
import re


class unknownMaterial:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self, Data, Mat):
        VERBOSE = True

        if VERBOSE:
            print("Importing parameters for ", Mat["MaterialTemplate"], "\n")

        # CMaterialParameterTexture
        # CMaterialParameterScalar
        # CMaterialParameterVector
        # CMaterialParameterColor

        x = -500
        y = 400
        ydelta = 100
        imgx = -800
        imgy = 500
        imgydelta = 300

        CurMat = Mat.node_tree

        nodes = CurMat.nodes

        for param in Data:
            current = Data[param]
            if isinstance(Data[param], str) and Data[param][-3:] == "xbm":
                text = imageFromRelPath(Data[param], self.image_format, DepotPath=self.BasePath, ProjPath=self.ProjPath)
                textNode = create_node(
                    CurMat.nodes, "ShaderNodeTexImage", (imgx, imgy), label=param, image=text, hide=False
                )

                if VERBOSE:
                    print(
                        "\t"
                        + param
                        + "Img=imageFromRelPath(Data['"
                        + param
                        + "'],self.image_format,DepotPath=self.BasePath, self.ProjPath=ProjPath)"
                    )
                    print(
                        "\t"
                        + param
                        + "ImgNode = create_node(CurMat.nodes,'ShaderNodeTexImage',  ("
                        + str(x)
                        + ","
                        + str(y)
                        + "), label='"
                        + param
                        + "', image="
                        + param
                        + "Img, hide=False)"
                    )
                if param == "GradientMap":
                    color_ramp_node = CreateGradMapRamp(CurMat, textNode)
                    color_ramp_node.location = (imgx + 500, imgy)
                    CurMat.links.new(textNode.outputs[0], color_ramp_node.inputs[0])
                imgy = imgy - imgydelta

            elif isinstance(Data[param], int) or isinstance(Data[param], float):
                scalar = CreateShaderNodeValue(CurMat, Data[param], x, y, param)
                y = y - ydelta
                if VERBOSE:
                    print(
                        "\t"
                        + param
                        + "Val = CreateShaderNodeValue(CurMat,Data['"
                        + param
                        + "'],"
                        + str(x)
                        + ","
                        + str(y)
                        + ",'"
                        + param
                        + "')"
                    )
            elif isinstance(Data[param], dict):
                if "Red" in Data[param]:
                    ColScale = CreateShaderNodeRGB(CurMat, Data[param], x, y, param, False)
                    if VERBOSE:
                        print(
                            "\t"
                            + param
                            + "Scale = CreateShaderNodeRGB(CurMat, Data['"
                            + param
                            + "'],"
                            + str(x)
                            + ","
                            + str(y)
                            + ",'"
                            + param
                            + "',False)"
                        )
                elif "Color" in param or "color" in param:
                    ColScale = CreateShaderNodeRGB(CurMat, Data[param], x, y, param, True)
                    if VERBOSE:
                        print(
                            "\t"
                            + param
                            + "Scale = CreateShaderNodeRGB(CurMat, Data['"
                            + param
                            + "'],"
                            + str(x)
                            + ","
                            + str(y)
                            + ",'"
                            + param
                            + "',True)"
                        )
                elif "Scale" in param or "scale" in param:
                    vector = create_node(CurMat.nodes, "ShaderNodeMapping", (x, y), label=param)
                    vector.inputs[0][0] = Data[param]["X"]
                    vector.inputs[0][1] = Data[param]["Y"]
                    vector.inputs[0][2] = Data[param]["Z"]
                    if VERBOSE:
                        print(
                            "\tvector=create_node(CurMat.nodes,'ShaderNodeMapping',  ("
                            + str(x)
                            + ","
                            + str(y)
                            + "), label='"
                            + param
                            + "')"
                        )
                        print("\tvector.inputs[0][0]=Data['" + param + "']['X']")
                        print("\tvector.inputs[0][1]=Data['" + param + "']['Y']")
                        print("\tvector.inputs[0][2]=Data['" + param + "']['Z']")
                else:
                    print("dict not captured ", param)
                y = y - ydelta
            else:
                print(param, " of type ", type(Data[param]), " not captured")
        if VERBOSE:
            print("Done with ", Mat["MaterialTemplate"], "\n")
