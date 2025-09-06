import bpy
import os
from ..main.common import *


class Invisible:
    def __init__(self, BasePath, image_format, ProjPath):
        self.BasePath = BasePath
        self.ProjPath = ProjPath
        self.image_format = image_format

    def create(self, Data, Mat):
        mat_tree = Mat.node_tree
        # Clear existing nodes
        for node in list(mat_tree.nodes):
            mat_tree.nodes.remove(node)

        # Nodes: Transparent BSDF -> Material Output
        transparent = mat_tree.nodes.new("ShaderNodeBsdfTransparent")
        transparent.location = (0, 0)

        output = mat_tree.nodes.new("ShaderNodeOutputMaterial")
        output.location = (220, 0)

        mat_tree.links.new(transparent.outputs[0], output.inputs[0])

        # Ensure fully transparent rendering in viewport
        Mat.blend_method = 'HASHED'
        try:
            Mat.shadow_method = 'HASHED'
        except Exception:
            pass


