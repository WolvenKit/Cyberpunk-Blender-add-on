from ..blender import shader_nodes
from ..blender.shader_nodes import assign_socket
from .glass import _SCALAR_DEFAULTS, Glass
from .graph import grid_location
from .mat_common import (
    get_or_build_node_group,
    new_labeled_node,
    param_texture_path,
    scene_time_socket,
)
from .normal_math import (
    decode_cp77_normal,
    encode_tangent_normal,
    tangent_to_normal_map,
)
from .overlay_common import combine_vector, control, split_vector

_DEFAULTS = {
    **_SCALAR_DEFAULTS,
    "GlassTint": r"base\materials\placeholder\white.xbm",
    "TintColor": (162 / 255, 173 / 255, 180 / 255, 0.0),
    "TintSurface": (129 / 255, 131 / 255, 106 / 255, 1.0),
    "GlassSpecularColor": (1.0, 1.0, 1.0, 1.0),
    "GlassTintTileAndOffset": (1.0, 1.0, 0.0, 0.0),
    "RoughnessTileAndOffset": (1.0, 1.0, 0.0, 0.0),
    "NormalTileAndOffset": (1.0, 1.0, 0.0, 0.0),
    "MaskTexture": r"base\vehicles\common\textures\common_windows_dirt_d02.xbm",
    "Roughness": r"engine\textures\small_white.xbm",
    "Normal": r"engine\textures\small_flat_normal.xbm",
    "MaskOpacity": 0.100000001,
    "GlassRoughnessBias": -0.0299999993,
    "MaskRoughnessBias": 1.0,
    "RainTiling": 1.0,
    "FlowTiling": 1.10000002,
    "DotsNormalTxt": r"base\vehicles\common\textures\vehicle_glass_rain_drops_n.xbm",
    "DotsTxt": r"base\vehicles\common\textures\vehicle_glass_rain_drops.xbm",
    "FlowTxt": r"base\vehicles\common\textures\vehicle_glass_rain_flow.xbm",
}


def rain_coordinates_group():
    inputs = (("NodeSocketVector", "UV"), ("NodeSocketColor", "Flow")) + tuple(
        ("NodeSocketFloat", name) for name in ("Flow Tiling", "Rain Tiling", "Time")
    )

    def build(tree):
        values = tree.nodes.new("NodeGroupInput").outputs
        output = tree.nodes.new("NodeGroupOutput")
        flow = split_vector(tree, "Flow Channels", values["Flow"])
        uv = split_vector(tree, "Rain UV", values["UV"])
        components = []
        for axis, scale in (("X", 2.6), ("Y", 0.52)):
            coordinate = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                flow[axis],
                values["Flow Tiling"],
                name="Flow Tile " + axis,
                location=grid_location(tree, (200, 160)),
            )
            coordinate = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY_ADD",
                coordinate,
                0.06,
                -0.03,
                name="Flow Offset " + axis,
                location=grid_location(tree, (200, 160)),
            )
            coordinate = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY_ADD",
                uv[axis],
                scale,
                coordinate,
                name="Flow Sample " + axis,
                location=grid_location(tree, (200, 160)),
            )
            if axis == "Y":
                coordinate = shader_nodes.math(
                    tree.nodes,
                    tree.links,
                    "MULTIPLY_ADD",
                    values["Time"],
                    0.06,
                    coordinate,
                    name="Flow Scroll",
                    location=grid_location(tree, (200, 160)),
                )
            components.append(coordinate)
        flow_uv = combine_vector(tree, "Flow UV", *components)
        scale = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            values["Rain Tiling"],
            2.6,
            name="Droplet Scale",
            location=grid_location(tree, (200, 160)),
        )
        drops_uv = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            values["UV"],
            scale=scale,
            name="Drops UV",
            location=grid_location(tree, (200, 160)),
        )
        tree.links.new(flow_uv, output.inputs["Flow UV"])
        tree.links.new(drops_uv, output.inputs["Drops UV"])

    return get_or_build_node_group(
        "CP77 Window Rain Coordinates v2",
        inputs,
        (("NodeSocketVector", "Flow UV"), ("NodeSocketVector", "Drops UV")),
        build,
    )


def rain_tangent_group():
    """Blend rain details after all texture normals have entered the plugin's tangent convention"""
    inputs = tuple(
        ("NodeSocketVector", name)
        for name in ("Base Normal", "Drops Normal", "Flow Normal")
    ) + tuple(
        ("NodeSocketFloat", name)
        for name in ("Dots", "Flow Blue", "Normal Strength", "Rain Amount", "Time")
    )

    def build(tree):
        values = tree.nodes.new("NodeGroupInput").outputs
        output = tree.nodes.new("NodeGroupOutput")
        phase = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            values["Time"],
            1.5,
            values["Dots"],
            name="Droplet Phase",
            location=grid_location(tree, (200, 160)),
        )
        phase = shader_nodes.math(
            tree.nodes,
            tree.links,
            "FRACT",
            phase,
            name="Droplet Cycle",
            location=grid_location(tree, (200, 160)),
        )
        phase = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            phase,
            0.3,
            name="Droplet Range",
            location=grid_location(tree, (200, 160)),
        )
        early = shader_nodes.math(
            tree.nodes,
            tree.links,
            "LESS_THAN",
            phase,
            1.0,
            name="Early Droplet",
            location=grid_location(tree, (200, 160)),
        )
        late = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            early,
            name="Late Droplet",
            location=grid_location(tree, (200, 160)),
        )
        tail = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            phase,
            late,
            name="Droplet Tail",
            location=grid_location(tree, (200, 160)),
        )
        tail = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            tail,
            name="Droplet Tail Complement",
            location=grid_location(tree, (200, 160)),
        )
        alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            phase,
            tail,
            name="Droplet Envelope",
            location=grid_location(tree, (200, 160)),
        )
        alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            alpha,
            values["Dots"],
            name="Droplet Mask",
            location=grid_location(tree, (200, 160)),
        )
        alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            alpha,
            0.001,
            name="Droplet Lower Bound",
            location=grid_location(tree, (200, 160)),
        )
        alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            alpha,
            1.999,
            name="Droplet Remap",
            location=grid_location(tree, (200, 160)),
            use_clamp=True,
        )
        alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            alpha,
            12.0,
            name="Droplet Strength",
            location=grid_location(tree, (200, 160)),
        )
        details = []
        for name, strength in (
            ("Flow Normal", values["Flow Blue"]),
            ("Drops Normal", alpha),
        ):
            weights = combine_vector(tree, name + " Strength", strength, strength, 1.0)
            normal = shader_nodes.vector_math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                values[name],
                weights,
                name=name + " Weighted",
                location=grid_location(tree, (200, 160)),
            )
            details.append(
                shader_nodes.vector_math(
                    tree.nodes,
                    tree.links,
                    "NORMALIZE",
                    normal,
                    name=name + " Unit",
                    location=grid_location(tree, (200, 160)),
                )
            )
        detail = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ADD",
            *details,
            name="Combined Rain Detail",
            location=grid_location(tree, (200, 160)),
        )
        enabled = shader_nodes.math(
            tree.nodes,
            tree.links,
            "GREATER_THAN",
            values["Rain Amount"],
            0.001,
            name="Rain Enabled",
            location=grid_location(tree, (200, 160)),
        )
        amount = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            values["Rain Amount"],
            enabled,
            name="Rain Strength",
            location=grid_location(tree, (200, 160)),
        )
        detail = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            detail,
            scale=amount,
            name="Weighted Rain Detail",
            location=grid_location(tree, (200, 160)),
        )
        blended = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            values["Base Normal"],
            values["Normal Strength"],
            detail,
            name="Combined",
            location=grid_location(tree, (200, 160)),
        )
        blended = split_vector(tree, "Combined Components", blended)
        combined = [blended["X"], blended["Y"]]
        squares = [
            shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                value,
                value,
                name="Squared " + axis,
                location=grid_location(tree, (200, 160)),
            )
            for axis, value in zip("XY", combined)
        ]
        length = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            *squares,
            name="Squared Tangent Length",
            location=grid_location(tree, (200, 160)),
        )
        z = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            1.0,
            length,
            name="Normal Height Squared",
            location=grid_location(tree, (200, 160)),
        )
        z = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            z,
            0.0,
            name="Safe Normal Height",
            location=grid_location(tree, (200, 160)),
        )
        z = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SQRT",
            z,
            name="Normal Height",
            location=grid_location(tree, (200, 160)),
        )
        tangent = combine_vector(tree, "Rain Tangent", *combined, z)
        tangent = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "NORMALIZE",
            tangent,
            name="Tangent",
            location=grid_location(tree, (200, 160)),
        )
        tree.links.new(tangent, output.inputs["Tangent"])

    return get_or_build_node_group(
        "CP77 Window Rain Tangent v2", inputs, (("NodeSocketVector", "Tangent"),), build
    )


class GlassWindowRain(Glass):
    """Reuse the glass surface with animated rain normals in the established tangent convention"""

    def _material_defaults(self, template):
        return _DEFAULTS

    def _uses_surface_tint(self, template):
        return True

    def _tiled_texture(
        self,
        nodes,
        links,
        data,
        key,
        location,
        *,
        tile_offset,
        non_color,
        defaults,
        aliases=None,
        uv_source=None,
    ):
        if key in {"GlassTint", "Normal"}:
            tile_offset = (1.0, 1.0, 0.0, 0.0)
        if key == "Normal":
            mapping = nodes.get("Mask UV")
            uv_source = (
                mapping.outputs["Vector"]
                if mapping is not None
                else self._mask_uv(nodes, links, data, (-2000, 200), defaults)
            )
        return super()._tiled_texture(
            nodes,
            links,
            data,
            key,
            location,
            tile_offset=tile_offset,
            non_color=non_color,
            defaults=defaults,
            aliases=aliases,
            uv_source=uv_source,
        )

    def _normal_sockets(self, nodes, links, data, normal_texture, scalar, material):
        tree = material.node_tree
        mapping = nodes.get("Mask UV")
        uv = (
            mapping.outputs["Vector"]
            if mapping is not None
            else self._mask_uv(nodes, links, data, (-2000, 200), _DEFAULTS)
        )
        amount = control(tree, data, "RainAmount", 0.0)
        clock = scene_time_socket(tree.nodes, (-1800, -1200), "Simulation Time")
        flow_tiling = control(tree, data, "FlowTiling", _DEFAULTS["FlowTiling"])
        rain_tiling = control(tree, data, "RainTiling", _DEFAULTS["RainTiling"])

        def texture(key, label, coordinates):
            path = param_texture_path(data, key) or _DEFAULTS[key]
            node = self._relative_texture_node(
                nodes, path, label, (-1400, -900), non_color=True, extension="REPEAT"
            )
            links.new(coordinates, node.inputs["Vector"])
            return node

        flow_scale = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            flow_tiling,
            2.0,
            name="Flow Texture Scale",
            location=grid_location(tree, (200, 160)),
        )
        flow_uv = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            uv,
            scale=flow_scale,
            name="Flow Texture UV",
            location=grid_location(tree, (200, 160)),
        )
        flow = texture("FlowTxt", "Flow Texture", flow_uv)
        coordinates = new_labeled_node(
            nodes, "ShaderNodeGroup", "Rain Coordinates", (-900, -900)
        )
        coordinates.node_tree = rain_coordinates_group()
        for name, value in {
            "UV": uv,
            "Flow": flow.outputs["Color"],
            "Flow Tiling": flow_tiling,
            "Rain Tiling": rain_tiling,
            "Time": clock,
        }.items():
            links.new(value, coordinates.inputs[name])
        dots = texture("DotsTxt", "Droplet Mask", coordinates.outputs["Drops UV"])
        drops = texture(
            "DotsNormalTxt", "Droplet Normal", coordinates.outputs["Drops UV"]
        )
        flowing = texture(
            "DotsNormalTxt", "Flowing Droplet Normal", coordinates.outputs["Flow UV"]
        )
        tangent_inputs = {}
        for name, sample in (
            ("Base Normal", normal_texture),
            ("Drops Normal", drops),
            ("Flow Normal", flowing),
        ):
            if sample is not None:
                decoded = decode_cp77_normal(
                    tree,
                    sample.outputs["Color"],
                    location=(-600, -1200),
                    label="Window " + name,
                )
                tangent_inputs[name] = decoded.outputs["Tangent"]
            else:
                tangent_inputs[name] = (0.0, 0.0, 1.0)
        tangent = new_labeled_node(
            nodes, "ShaderNodeGroup", "Rain Tangent", (-200, -1000)
        )
        tangent.node_tree = rain_tangent_group()
        dots_red = split_vector(tree, "Droplet Mask Channels", dots.outputs["Color"])[
            "X"
        ]
        flow_blue = split_vector(tree, "Flow Channels", flow.outputs["Color"])["Z"]
        for name, value in {
            **tangent_inputs,
            "Dots": dots_red,
            "Flow Blue": flow_blue,
            "Normal Strength": scalar("NormalStrength"),
            "Rain Amount": amount,
            "Time": clock,
        }.items():
            assign_socket(links, value, tangent.inputs[name])
        encoded = encode_tangent_normal(
            tree,
            tangent.outputs["Tangent"],
            location=(200, -1000),
            label="Window Normal Encoding",
        )
        normal = tangent_to_normal_map(
            tree, encoded, location=(400, -1000), label="Window Normal"
        )
        return normal, normal


used_params = tuple(
    key
    for key in _DEFAULTS
    if key not in {"GlassTintTileAndOffset", "NormalTileAndOffset"}
) + ("RainAmount",)
