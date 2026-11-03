from .metalbase_common import COLUMN_TEXTURE, MetalBaseCore


class MetalBaseGarment(MetalBaseCore):
    normal_strength_param = None
    texture_defaults = {"Normal": r"engine\textures\small_flat_normal.xbm"}
    colour_defaults = {
        "BaseColorScale": (1.0, 1.0, 1.0, 1.0),
        "EmissiveColor": (0.0, 0.0, 0.0, 0.0),
    }
    layer_tile_default = 1.0
    alpha_threshold_default = 0.0

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        bsdf, sockets = self._bsdf(tree)
        uv = self._uv_source(tree, data)

        base = self._texture(tree, data, "BaseColor", (COLUMN_TEXTURE, 640), uv)
        self._pbr_channel(
            tree, data, "Metalness", bsdf.inputs["Metallic"], uv, 260, clamp=False
        )
        self._pbr_channel(
            tree, data, "Roughness", bsdf.inputs["Roughness"], uv, 80, clamp=False
        )
        self._normal(tree, data, bsdf, uv)

        surface, components = self._scaled_base_color(
            tree, data, base, y=520, clamp=True
        )
        surface = self._emissive_block(
            tree,
            data,
            bsdf,
            sockets,
            surface,
            base.outputs["Color"] if base is not None else None,
            uv=None,
        )
        tree.links.new(surface, bsdf.inputs["Base Color"])

        self._alpha_mask(
            tree,
            data,
            bsdf,
            base.outputs["Alpha"] if base is not None else None,
            base.image if base is not None else None,
        )
        Mat.diffuse_color = (*components[:3], 1.0)
