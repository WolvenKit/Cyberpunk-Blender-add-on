from ..blender import shader_nodes
from ..materials.cache_identity import filtered_material_data_identity
from .graph import mix_color_socket, set_alpha_clip
from .mat_common import (
    MaterialTypeBase,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
)
from .normal_math import create_cp77_normal_texture
from .shader_math import emissive_strength_from_ev

TEMPLATE = r"base\materials\circuit_wires.mt"
WIRE_COLOR_LAYER = "Color"
WIRE_COLOR_PRESENCE_ATTRIBUTE = "CP77_CircuitWireColorPresent"


def _combine_rgb(tree, red, green, blue, name, location):
    node = new_labeled_node(tree.nodes, "ShaderNodeCombineColor", name, location)
    node.mode = "RGB"
    for value, socket_name in ((red, "Red"), (green, "Green"), (blue, "Blue")):
        socket = node.inputs[socket_name]
        if hasattr(value, "is_output"):
            tree.links.new(value, socket)
        else:
            socket.default_value = float(value)
    return node.outputs["Color"]


class CircuitWires(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (1040, 80)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Circuit Wires", (760, 80)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        vertex = new_labeled_node(
            nodes, "ShaderNodeVertexColor", "Wire Vertex Color", (-1180, 520)
        )
        vertex.layer_name = WIRE_COLOR_LAYER
        split = new_labeled_node(
            nodes, "ShaderNodeSeparateColor", "Wire Vertex Channels", (-960, 520)
        )
        split.mode = "RGB"
        links.new(vertex.outputs["Color"], split.inputs["Color"])
        presence = new_labeled_node(
            nodes,
            "ShaderNodeAttribute",
            "Wire Vertex Color Present",
            (-1180, 760),
        )
        presence.attribute_name = WIRE_COLOR_PRESENCE_ATTRIBUTE
        has_vertex_color = presence.outputs["Fac"]

        base_color = param_color(data, "BaseColor", (1.0, 1.0, 1.0, 1.0))
        red = split.outputs["Red"]
        green = split.outputs["Green"]
        blue = split.outputs["Blue"]

        one_minus_red = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            red,
            name="1 - Bevel Coordinate",
            location=(-740, 620),
        )
        bevel = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            red,
            one_minus_red,
            name="Bevel Parabola",
            location=(-560, 620),
        )
        bevel = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            bevel,
            max(0.0, param_float(data, "BevelStrenght", 2.0)),
            name="Bevel Strength",
            location=(-380, 620),
            use_clamp=True,
        )
        vertex_shaded = mix_color_socket(
            nodes,
            links,
            "Base × Bevel",
            base_color,
            (1.0, 1.0, 1.0, 1.0),
            1.0,
            (-180, 520),
            blend_type="MULTIPLY",
            clamp=False,
        )
        vertex_shaded = mix_color_socket(
            nodes,
            links,
            "Bevel Apply",
            (0.0, 0.0, 0.0, 1.0),
            vertex_shaded,
            bevel,
            (40, 520),
            clamp=True,
        )
        shaded = mix_color_socket(
            nodes,
            links,
            "Vertex Color Fallback",
            base_color,
            vertex_shaded,
            has_vertex_color,
            (240, 520),
            clamp=True,
        )

        if param_float(data, "DebugVC", 0.0) >= 0.5:
            debug_color = _combine_rgb(
                tree, red, green, 0.0, "Vertex Color Debug", (40, 700)
            )
            shaded = mix_color_socket(
                nodes,
                links,
                "Vertex Debug Fallback",
                base_color,
                debug_color,
                has_vertex_color,
                (260, 700),
                clamp=True,
            )
        if param_float(data, "DebugID", 0.0) >= 0.5:
            debug_id = _combine_rgb(tree, blue, blue, blue, "Wire ID Debug", (240, 700))
            shaded = mix_color_socket(
                nodes,
                links,
                "Wire ID Fallback",
                base_color,
                debug_id,
                has_vertex_color,
                (460, 700),
                clamp=True,
            )

        links.new(shaded, find_input(principled, "Base Color"))
        find_input(principled, "Metallic").default_value = max(
            0.0, min(1.0, param_float(data, "Metalness", 0.0))
        )
        find_input(principled, "Roughness").default_value = max(
            0.0, min(1.0, param_float(data, "Roughness", 0.5))
        )

        texcoord = new_labeled_node(
            nodes, "ShaderNodeTexCoord", "Wire UV", (-1180, -80)
        )
        normal = create_cp77_normal_texture(
            self,
            tree,
            data,
            "Normal",
            uv=texcoord.outputs["UV"],
            strength_key=None,
            default_strength=1.0,
            location=(-940, -120),
            label="Wire Normal",
        )
        if normal is not None:
            links.new(normal, find_input(principled, "Normal"))

        threshold = max(0.0, min(1.0, param_float(data, "AlphaThreshold", 0.0)))
        base_visible = 1.0 if base_color[3] > threshold else 0.0
        id_visible = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            blue,
            0.999999,
            name="Valid Wire Segment",
            location=(-160, -180),
        )
        missing_vertex_color = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            has_vertex_color,
            name="Missing Wire Vertex Color",
            location=(-160, -260),
            use_clamp=True,
        )
        gated_id = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            has_vertex_color,
            id_visible,
            name="Authored Wire Visibility",
            location=(40, -260),
            use_clamp=True,
        )
        segment_visible = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            missing_vertex_color,
            gated_id,
            name="Wire Segment Fallback",
            location=(220, -220),
            use_clamp=True,
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            segment_visible,
            base_visible,
            name="Wire Alpha",
            location=(400, -180),
            use_clamp=True,
        )
        links.new(alpha, find_input(principled, "Alpha"))
        set_alpha_clip(Mat, threshold if threshold > 0.0 else 0.001)

        emission_color = find_input(principled, "Emission Color", "Emission")
        if emission_color is not None:
            links.new(shaded, emission_color)
        emission_strength_socket = find_input(principled, "Emission Strength")
        if emission_strength_socket is not None:
            emission_strength_socket.default_value = emissive_strength_from_ev(
                param_float(data, "EmissiveEV", 0.0),
                3.0,
            )

        Mat.diffuse_color = base_color
        Mat["cp77_circuit_wires_vertex_color_layer"] = WIRE_COLOR_LAYER


used_params = [
    "BevelStrenght",
    "DebugVC",
    "DebugID",
    "BaseColor",
    "Metalness",
    "Roughness",
    "Normal",
    "EmissiveEV",
    "AlphaThreshold",
]


def material_cache_identity(raw_material):
    return filtered_material_data_identity(raw_material, used_params)
