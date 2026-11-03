from .mat_common import MaterialTypeBase

<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes
class Invisible(MaterialTypeBase):
    def create(self, Data, Mat):
        mat_tree = Mat.node_tree

        for node in list(mat_tree.nodes):
            mat_tree.nodes.remove(node)

        # Nodes: Transparent BSDF -> Material Output
        transparent = mat_tree.nodes.new("ShaderNodeBsdfTransparent")
        transparent.location = (0, 0)

        output = mat_tree.nodes.new("ShaderNodeOutputMaterial")
        output.location = (220, 0)

        mat_tree.links.new(transparent.outputs["BSDF"], output.inputs["Surface"])

        # Render method is applied by setup._set_hashed_render_method after
<<<<<<< Updated upstream
        # create(); only backface culling is shader-specific, matching the game.
=======
        # Keep backface culling enabled for invisible surfaces.
>>>>>>> Stashed changes
        Mat.use_backface_culling = True
