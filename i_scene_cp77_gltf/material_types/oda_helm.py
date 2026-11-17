from ..blender import shader_nodes
from .bundles import direct_ev_strength_socket
from .graph import (
    mix_color_socket,
    rgb_socket,
    separate_color_sockets,
    value_node,
    white_noise_socket,
)
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
from .parallax_common import (
    create_camera_forward_parallax_offset,
    create_camera_forward_vector,
)

TEMPLATE = r"base\fx\_shaders\oda_helm.mt"
_WHITE = (1.0, 1.0, 1.0, 1.0)
_BLACK = (0.0, 0.0, 0.0, 1.0)
_HIGHLIGHT = (0.94, 0.94, 0.94, 1.0)


def _contrast(tree, value, amount, name, location):
    """value pushed away from 0.5 by amount, kept within 0 to 1"""
    nodes, links = tree.nodes, tree.links
    centred = shader_nodes.math(
        nodes, links, "SUBTRACT", value, 0.5, name=f"{name} Centred", location=location
    )
    return shader_nodes.math(
        nodes,
        links,
        "MULTIPLY_ADD",
        centred,
        amount,
        0.5,
        name=name,
        location=(location[0] + 180, location[1]),
        use_clamp=True,
    )


class OdaHelm(MaterialTypeBase):
    # The glitch and swipe controls move while playing, so the material shows the helmet with both at rest.
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes, links = tree.nodes, tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (2600, 0)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Oda Helm", (2200, 0)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])
        uv = new_labeled_node(
            nodes, "ShaderNodeTexCoord", "Oda Helm Coordinates", (-3000, 200)
        ).outputs["UV"]
        uv_y = new_labeled_node(nodes, "ShaderNodeSeparateXYZ", "UV Y", (-2800, -200))
        links.new(uv, uv_y.inputs["Vector"])
        uv_y = uv_y.outputs["Y"]
        seconds = new_labeled_node(
            nodes, "ShaderNodeValue", "Scene Seconds", (-3000, -1100)
        )
        set_scene_fps_driver(
            seconds.outputs["Value"].driver_add("default_value").driver
        )
        seconds = seconds.outputs["Value"]
        colors = {
            key: rgb_socket(
                nodes, key, param_color(data, key, _WHITE), (400, 1100 - 160 * index)
            )
            for index, key in enumerate(
                ("PrimaryColor", "SecondaryColor", "BackgroundColor")
            )
        }
        broken = param_float(data, "NormalOrBroken", 0.0)

        hologram_uv = self._jittered_uv(tree, data, uv, uv_y, seconds, broken)
        red, green, blue = separate_color_sockets(
            nodes,
            links,
            self._hologram(tree, data, uv, hologram_uv, seconds),
            "Hologram Channels",
            (200, 300),
        )
        # At rest the second colour only reaches the texture's bottom edge, where the hologram's red is near full.
        swipe_position = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            uv_y,
            -1.0,
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                red,
                0.5,
                name="Half Red",
                location=(400, 100),
            ),
            name="Swipe Position",
            location=(600, 100),
        )
        swipe = new_labeled_node(nodes, "ShaderNodeMapRange", "Swipe", (800, 100))
        swipe.interpolation_type = "SMOOTHSTEP"
        links.new(swipe_position, swipe.inputs["Value"])
        swipe.inputs["From Min"].default_value = 0.45
        swipe.inputs["From Max"].default_value = 0.55
        swipe = swipe.outputs["Result"]

        alternate = mix_color_socket(
            nodes,
            links,
            "Alternate Colour",
            colors["BackgroundColor"],
            colors["SecondaryColor"],
            green,
            (800, 800),
        )
        alternate = mix_color_socket(
            nodes,
            links,
            "Alternate Highlight",
            alternate,
            colors["SecondaryColor"],
            blue,
            (1000, 800),
        )
        final = mix_color_socket(
            nodes,
            links,
            "Hologram Colour",
            colors["BackgroundColor"],
            colors["PrimaryColor"],
            red,
            (800, 550),
        )
        final = mix_color_socket(
            nodes, links, "Hologram Highlight", final, _HIGHLIGHT, blue, (1000, 550)
        )
        final = mix_color_socket(
            nodes, links, "Swiped Colour", final, alternate, swipe, (1200, 550)
        )

        packed = create_relative_texture_node(
            self,
            tree,
            data,
            "NormalRoughnessMetalness",
            uv,
            (-1400, -1300),
            non_color=True,
        )
        if packed is not None:
            # The normal sits in red and green, roughness in blue and metalness in alpha.
            _red, _green, roughness = separate_color_sockets(
                nodes, links, packed.outputs["Color"], "Roughness", (-1100, -1300)
            )
            links.new(roughness, principled.inputs["Roughness"])
            links.new(packed.outputs["Alpha"], principled.inputs["Metallic"])
        normal = create_cp77_normal_texture(
            self,
            tree,
            data,
            "NormalRoughnessMetalness",
            uv=uv,
            location=(-1400, -1600),
            label="Oda Helm Normal",
        )
        if normal is not None:
            links.new(normal, principled.inputs["Normal"])
        else:
            normal = new_labeled_node(
                nodes, "ShaderNodeNewGeometry", "Oda Helm Geometry", (-1400, -1600)
            ).outputs["Normal"]
        facing = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            normal,
            create_camera_forward_vector(tree, location=(-1100, -1900)),
            name="View · Normal",
            location=(-800, -1700),
        )
        facing = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            facing,
            -1.0,
            name="Facing",
            location=(-600, -1700),
            use_clamp=True,
        )
        primary = _contrast(
            tree,
            facing,
            param_float(data, "DotPower", 1.0),
            "Primary Facing",
            (-400, -1600),
        )
        secondary = _contrast(
            tree,
            facing,
            param_float(data, "SecondaryDotPower", 1.0),
            "Secondary Facing",
            (-400, -1800),
        )
        final = mix_color_socket(
            nodes,
            links,
            "Faded Colour",
            colors["BackgroundColor"],
            final,
            secondary,
            (1400, 550),
        )

        # The base colour's alpha marks the broken parts, which show the base colour and do not glow.
        base = create_relative_texture_node(
            self, tree, data, "BaseColor", uv, (1000, -300)
        )
        broken_mask = 0.0
        base_color = colors["BackgroundColor"]
        if base is not None:
            base_color = base.outputs["Color"]
            broken_mask = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                base.outputs["Alpha"],
                broken,
                name="Broken Mask",
                location=(1300, -400),
            )
        shown = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            primary,
            broken_mask,
            name="Hologram Shown",
            location=(1500, -200),
            use_clamp=True,
        )
        final = mix_color_socket(
            nodes, links, "Oda Helm Colour", base_color, final, shown, (1700, 300)
        )
        links.new(final, principled.inputs["Base Color"])
        links.new(final, principled.inputs["Emission Color"])
        links.new(
            direct_ev_strength_socket(
                tree,
                self._emissive_ev(
                    tree, data, (red, green, blue), swipe, primary, broken_mask
                ),
                (2000, -800),
            ),
            principled.inputs["Emission Strength"],
        )

    def _emissive_ev(self, tree, data, channels, swipe, primary, broken_mask):
        """EmissiveEV scaled by the hologram's red and blue, or green and blue where swiped, on facing unbroken parts"""
        nodes, links = tree.nodes, tree.links
        red, green, blue = channels
        ev = value_node(
            nodes, "EmissiveEV", param_float(data, "EmissiveEV", 0.0), (400, -700)
        ).outputs["Value"]
        steady = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            ev,
            shader_nodes.math(
                nodes, links, "ADD", red, blue, name="Red + Blue", location=(400, -900)
            ),
            name="Steady EV",
            location=(700, -800),
        )
        swiped = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            ev,
            shader_nodes.math(
                nodes,
                links,
                "ADD",
                shader_nodes.math(
                    nodes,
                    links,
                    "ADD",
                    green,
                    blue,
                    name="Green + Blue",
                    location=(400, -1100),
                ),
                0.5,
                name="Swiped Glow",
                location=(550, -1100),
                use_clamp=True,
            ),
            name="Swiped EV",
            location=(700, -1000),
        )
        emissive = shader_nodes.lerp(
            nodes,
            links,
            steady,
            swiped,
            swipe,
            name="Emissive EV",
            location=(900, -900),
        )
        emissive = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            emissive,
            primary,
            name="Facing EV",
            location=(1300, -800),
        )
        return shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            emissive,
            shader_nodes.math(
                nodes,
                links,
                "SUBTRACT",
                1.0,
                broken_mask,
                name="Unbroken",
                location=(1300, -1000),
            ),
            name="Unbroken EV",
            location=(1500, -800),
        )

    def _jittered_uv(self, tree, data, uv, uv_y, seconds, broken):
        """uv with its rows shifted at random on a broken helmet's flickers"""
        if broken <= 0.5:
            return uv
        nodes, links = tree.nodes, tree.links
        scale = param_vector(data, "NoiseScale", (1.0, 1.0, 0.0, 0.0))
        flicker = white_noise_socket(
            nodes,
            links,
            "Flicker Noise",
            (-2200, -1100),
            shader_nodes.math(
                nodes,
                links,
                "FLOOR",
                shader_nodes.math(
                    nodes,
                    links,
                    "MULTIPLY",
                    seconds,
                    9.42,
                    name="Flicker Rate",
                    location=(-2600, -1100),
                ),
                name="Flicker Step",
                location=(-2400, -1100),
            ),
        )
        flicker = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                flicker,
                broken,
                name="Broken Flicker",
                location=(-2000, -1100),
            ),
            0.5,
            name="Flickering",
            location=(-1800, -1100),
        )
        band = shader_nodes.math(
            nodes,
            links,
            "FLOOR",
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                shader_nodes.math(
                    nodes,
                    links,
                    "FRACT",
                    shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        seconds,
                        0.28,
                        name="Band Rate",
                        location=(-2600, -1400),
                    ),
                    name="Band Cycle",
                    location=(-2400, -1400),
                ),
                20.0,
                name="Band Steps",
                location=(-2200, -1400),
            ),
            name="Band Step",
            location=(-2000, -1400),
        )
        # Material V runs down the texture, Blender's up, so the rows count from the top.
        row = shader_nodes.math(
            nodes,
            links,
            "FLOOR",
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                shader_nodes.math(
                    nodes,
                    links,
                    "SUBTRACT",
                    shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY_ADD",
                        band,
                        0.05,
                        1.0,
                        name="Band Offset",
                        location=(-1800, -1400),
                    ),
                    uv_y,
                    name="Banded Row",
                    location=(-1600, -1600),
                ),
                float(scale[0]),
                name="Row Scale",
                location=(-1400, -1600),
            ),
            name="Row",
            location=(-1200, -1600),
        )
        shift = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            white_noise_socket(nodes, links, "Row Noise", (-1000, -1600), row),
            0.5,
            name="Row Shift",
            location=(-800, -1600),
        )
        shift = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            shift,
            shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                flicker,
                float(scale[3]),
                name="Shift Amount",
                location=(-1000, -1400),
            ),
            name="Row Jitter",
            location=(-600, -1500),
        )
        jitter = new_labeled_node(
            nodes, "ShaderNodeCombineXYZ", "Jitter", (-400, -1500)
        )
        links.new(shift, jitter.inputs["X"])
        return shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            uv,
            jitter.outputs["Vector"],
            name="Jittered UV",
            location=(-200, -1400),
        )

    def _hologram(self, tree, data, uv, hologram_uv, seconds):
        """The hologram's three layers screened together, drawn LayersSeparation apart along the view"""
        nodes, links = tree.nodes, tree.links
        first = create_relative_texture_node(
            self, tree, data, "Hologram", hologram_uv, (-800, 400), extension="EXTEND"
        )
        if first is None:
            return rgb_socket(nodes, "No Hologram", _BLACK, (0, 300))
        view = create_camera_forward_parallax_offset(
            tree, y_scale=-1.0, location=(-1800, 600)
        )
        separation = param_float(data, "LayersSeparation", 0.0)
        weights = param_vector(data, "LayersIntensity", (1.0, 1.0, 1.0, 0.0))
        scanlines = self._scanlines(tree, data, uv, seconds)
        layers = []
        for index in range(3):
            sample = first
            if index:
                sample = new_labeled_node(
                    nodes,
                    "ShaderNodeTexImage",
                    f"Hologram Layer {index + 1}",
                    (-800, 400 - 300 * index),
                )
                sample.image = first.image
                sample.extension = "EXTEND"
            offset = shader_nodes.vector_math(
                nodes,
                links,
                "MULTIPLY_ADD",
                view,
                (separation * (index + 1),) * 3,
                hologram_uv,
                name=f"Hologram Layer {index + 1} UV",
                location=(-1100, 400 - 300 * index),
            )
            links.new(offset, sample.inputs["Vector"])
            strength = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                scanlines,
                float(weights[index]),
                name=f"Hologram Layer {index + 1} Strength",
                location=(-600, 300 - 300 * index),
            )
            layers.append(
                shader_nodes.vector_math(
                    nodes,
                    links,
                    "SCALE",
                    sample.outputs["Color"],
                    scale=strength,
                    name=f"Hologram Layer {index + 1} Glow",
                    location=(-400, 400 - 300 * index),
                )
            )
        deep = mix_color_socket(
            nodes,
            links,
            "Deep Layers",
            layers[2],
            layers[1],
            1.0,
            (-200, 0),
            blend_type="SCREEN",
        )
        return mix_color_socket(
            nodes,
            links,
            "Hologram",
            deep,
            layers[0],
            1.0,
            (0, 200),
            blend_type="SCREEN",
        )

    def _scanlines(self, tree, data, uv, seconds):
        """The scanline texture's red lifted by ScanlinesIntensity, tiled by ScanlineTilingAndSpeed XY and scrolling at ZW"""
        nodes, links = tree.nodes, tree.links
        tiling = param_vector(data, "ScanlineTilingAndSpeed", (1.0, 1.0, 0.0, 0.0))
        tile_u, tile_v, speed_u, speed_v = (float(value) for value in tiling[:4])
        # Material V runs down the texture, Blender's up: v' = v * tiling + time * speed becomes 1 - ((1 - v) * tiling + time * speed).
        scroll = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY_ADD",
            (speed_u, -speed_v, 0.0),
            seconds,
            (0.0, 1.0 - tile_v, 0.0),
            name="Scanline Scroll",
            location=(-1400, -400),
        )
        coordinate = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY_ADD",
            uv,
            (tile_u, tile_v, 0.0),
            scroll,
            name="Scanline Coordinates",
            location=(-1200, -300),
        )
        lines = create_relative_texture_node(
            self,
            tree,
            data,
            "ScanlineTexture",
            coordinate,
            (-1000, -300),
            non_color=True,
        )
        if lines is None:
            return 1.0
        red = separate_color_sockets(
            nodes, links, lines.outputs["Color"], "Scanline Red", (-700, -300)
        )[0]
        return shader_nodes.math(
            nodes,
            links,
            "ADD",
            red,
            param_float(data, "ScanlinesIntensity", 0.0),
            name="Scanlines",
            location=(-500, -300),
            use_clamp=True,
        )
