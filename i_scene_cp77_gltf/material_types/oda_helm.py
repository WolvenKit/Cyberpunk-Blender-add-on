from ..blender import shader_nodes
from .graph import combine_xyz_socket, rgb_socket, separate_color_sockets
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    new_labeled_node,
    param_color,
    param_float,
    param_vector,
    set_scene_fps_driver,
)
from .normal_math import create_cp77_normal_texture
from .parallax_math import tangent_view_vector
from .shader_math import emissive_strength_from_ev

TEMPLATE = r"base\fx\_shaders\oda_helm.mt"
_WHITE = (1.0, 1.0, 1.0, 1.0)
_COLORS = ("PrimaryColor", "SecondaryColor", "BackgroundColor", "NoiseColor")


class OdaHelm(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes, links = tree.nodes, tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (1900, 0)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Oda Helm", (1500, 0)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
        texcoord = new_labeled_node(
            nodes, "ShaderNodeTexCoord", "Oda Helm Coordinates", (-2600, 200)
        )
        uv = texcoord.outputs["UV"]
        colors = {
            key: rgb_socket(
                nodes, key, param_color(data, key, _WHITE), (-600, 900 - 160 * index)
            )
            for index, key in enumerate(_COLORS)
        }

        base = create_relative_texture_node(
            self, tree, data, "BaseColor", uv, (-1400, 700)
        )
        links.new(
            base.outputs["Color"] if base is not None else colors["BackgroundColor"],
            principled.inputs["Base Color"],
        )
        packed = create_relative_texture_node(
            self,
            tree,
            data,
            "NormalRoughnessMetalness",
            uv,
            (-1400, 380),
            non_color=True,
        )
        if packed is not None:
            # The normal sits in red and green, roughness in blue and metalness in alpha.
            _red, _green, blue = separate_color_sockets(
                nodes, links, packed.outputs["Color"], "Roughness", (-1100, 380)
            )
            links.new(blue, principled.inputs["Roughness"])
            links.new(packed.outputs["Alpha"], principled.inputs["Metallic"])
        normal = create_cp77_normal_texture(
            self,
            tree,
            data,
            "NormalRoughnessMetalness",
            uv=uv,
            location=(-1400, 80),
            label="Oda Helm Normal",
        )
        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "Oda Helm Geometry", (-2600, -300)
        )
        surface_normal = normal if normal is not None else geometry.outputs["Normal"]
        if normal is not None:
            links.new(normal, principled.inputs["Normal"])

        seconds = new_labeled_node(
            nodes, "ShaderNodeValue", "Scene Seconds", (-2600, -700)
        )
        set_scene_fps_driver(
            seconds.outputs["Value"].driver_add("default_value").driver
        )
        seconds = seconds.outputs["Value"]

        hologram = self._hologram_mask(tree, data, uv)
        facing = self._facing(tree, geometry.outputs["Incoming"], surface_normal)
        glow = None
        for key, power_key, default, location in (
            ("PrimaryColor", "DotPower", 1.0, (-200, 600)),
            ("SecondaryColor", "SecondaryDotPower", 1.0, (-200, 400)),
        ):
            # Each colour shows where the hologram is drawn, weighted by how squarely the surface faces the view.
            weight = shader_nodes.math(
                nodes,
                links,
                "POWER",
                facing,
                max(0.0, param_float(data, power_key, default)),
                name=f"{key} Facing",
                location=location,
            )
            weight = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                weight,
                hologram,
                name=f"{key} Weight",
                location=(location[0] + 180, location[1]),
            )
            part = shader_nodes.vector_math(
                nodes,
                links,
                "SCALE",
                colors[key],
                scale=weight,
                name=f"{key} Glow",
                location=(location[0] + 360, location[1]),
            )
            glow = (
                part
                if glow is None
                else shader_nodes.vector_math(
                    nodes,
                    links,
                    "ADD",
                    glow,
                    part,
                    name="Hologram Glow",
                    location=(location[0] + 540, location[1]),
                )
            )
        glow = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            glow,
            scale=self._scanlines(tree, data, uv, seconds),
            name="Scanned Glow",
            location=(700, 500),
        )
        noise = self._noise(tree, data, uv, seconds)
        glow = shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            glow,
            shader_nodes.vector_math(
                nodes,
                links,
                "SCALE",
                colors["NoiseColor"],
                scale=noise,
                name="Noise Glow",
                location=(700, 200),
            ),
            name="Oda Helm Glow",
            location=(900, 400),
        )
        links.new(glow, principled.inputs["Emission Color"])
        # A broken helmet glows at its glitched exposure.
        broken = param_float(data, "NormalOrBroken", 0.0) >= 0.5
        ev = param_float(data, "EmissiveEVGlitched" if broken else "EmissiveEV", 0.0)
        principled.inputs[
            "Emission Strength"
        ].default_value = emissive_strength_from_ev(ev)

    def _hologram_mask(self, tree, data, uv):
        """The hologram's three channels as layers drawn LayersSeparation apart in depth, weighted by LayersIntensity"""
        nodes, links = tree.nodes, tree.links
        first = create_relative_texture_node(
            self, tree, data, "Hologram", uv, (-1400, -400)
        )
        if first is None:
            return 0.0
        view = tangent_view_vector(tree, location=(-2200, -500))
        separation = param_float(data, "LayersSeparation", 0.0)
        weights = param_vector(data, "LayersIntensity", (1.0, 1.0, 1.0, 0.0))
        mask = None
        for layer in range(3):
            sample = first
            if layer:
                offset = shader_nodes.vector_math(
                    nodes,
                    links,
                    "MULTIPLY_ADD",
                    view,
                    (separation * layer,) * 3,
                    uv,
                    name=f"Hologram Layer {layer + 1} UV",
                    location=(-1700, -400 - 300 * layer),
                )
                sample = new_labeled_node(
                    nodes,
                    "ShaderNodeTexImage",
                    f"Hologram Layer {layer + 1}",
                    (-1400, -400 - 300 * layer),
                )
                sample.image = first.image
                sample.extension = first.extension
                links.new(offset, sample.inputs["Vector"])
            channel = separate_color_sockets(
                nodes,
                links,
                sample.outputs["Color"],
                f"Hologram Layer {layer + 1} Channels",
                (-1100, -400 - 300 * layer),
            )[layer]
            weighted = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                channel,
                float(weights[layer]),
                name=f"Hologram Layer {layer + 1} Weight",
                location=(-900, -400 - 300 * layer),
            )
            mask = (
                weighted
                if mask is None
                else shader_nodes.math(
                    nodes,
                    links,
                    "ADD",
                    mask,
                    weighted,
                    name="Hologram Mask",
                    location=(-700, -400 - 300 * layer),
                )
            )
        return mask

    def _facing(self, tree, incoming, normal):
        """How squarely the surface faces the view, 0 to 1"""
        nodes, links = tree.nodes, tree.links
        view = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            incoming,
            scale=-1.0,
            name="View Direction",
            location=(-1100, -1400),
        )
        facing = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            view,
            normal,
            name="View · Normal",
            location=(-900, -1400),
        )
        return shader_nodes.math(
            nodes, links, "MAXIMUM", facing, 0.0, name="Facing", location=(-700, -1400)
        )

    def _scanlines(self, tree, data, uv, seconds):
        """1 off the scanlines, falling by ScanlinesIntensity on them, the lines scrolling at ScanlineTilingAndSpeed W"""
        nodes, links = tree.nodes, tree.links
        tiling = param_vector(data, "ScanlineTilingAndSpeed", (1.0, 1.0, 0.0, 0.0))
        intensity = max(0.0, min(1.0, param_float(data, "ScanlinesIntensity", 0.0)))
        u, v, _w = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "Scanline UV", (-1700, -1800)
        ).outputs
        links.new(uv, u.node.inputs["Vector"])
        scroll = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            v,
            float(tiling[1]),
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                seconds,
                float(tiling[3]),
                name="Scanline Scroll",
                location=(-1500, -2000),
            ),
            name="Scanline V",
            location=(-1300, -1900),
        )
        coordinate = combine_xyz_socket(
            tree,
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                u,
                float(tiling[0]),
                name="Scanline U",
                location=(-1300, -1750),
            ),
            scroll,
            location=(-1100, -1800),
            label="Scanline Coordinates",
        )
        lines = create_relative_texture_node(
            self, tree, data, "ScanlineTexture", coordinate, (-900, -1800)
        )
        if lines is None or intensity <= 0.0:
            return 1.0
        return shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            lines.outputs["Color"],
            intensity,
            1.0 - intensity,
            name="Scanlines",
            location=(-600, -1800),
        )

    def _noise(self, tree, data, uv, seconds):
        """Moving noise, NoiseScale X and Y across the surface, Z its amount and W its speed"""
        nodes, links = tree.nodes, tree.links
        scale = param_vector(data, "NoiseScale", (1.0, 1.0, 0.0, 0.0))
        if float(scale[2]) <= 0.0:
            return 0.0
        stretched = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY",
            uv,
            (float(scale[0]), float(scale[1]), 0.0),
            name="Noise Coordinates",
            location=(-1100, -2300),
        )
        texture = new_labeled_node(
            nodes, "ShaderNodeTexNoise", "Oda Helm Noise", (-900, -2300)
        )
        texture.noise_dimensions = "4D"
        links.new(stretched, texture.inputs["Vector"])
        time = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            seconds,
            float(scale[3]),
            name="Noise Time",
            location=(-1100, -2500),
        )
        links.new(time, texture.inputs["W"])
        return shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            texture.outputs["Fac"],
            float(scale[2]),
            name="Noise Amount",
            location=(-700, -2300),
        )
