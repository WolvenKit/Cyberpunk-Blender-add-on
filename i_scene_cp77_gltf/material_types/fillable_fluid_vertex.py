from ..bartmoss.scalar import clamp01, lerp_three
from ..blender import shader_nodes
from .graph import mix_color_socket, set_transparent, value_socket
from .mat_common import (
    MaterialTypeBase,
    create_scene_time_value,
    find_input,
    new_labeled_node,
    param_color,
    param_float,
    param_vector,
)
from .normal_math import (
    decode_cp77_normal,
    encode_tangent_normal,
    tangent_to_normal_map,
)

TEMPLATE = "base\\materials\\fillable_fluid_vertex.mt"

_SCALAR_DEFAULTS = {
    "Opacity": 1.0,  # 0.0 .. 1.0
    "FrontFacesReflectionPower": 1.0,  # 0.0 .. 10.0
    "IOR": 1.33000004,  # 1.0 .. 2.0
    "FresnelBias": 1.0,  # 0.0 .. 2.0
    "BlurRadius": 0.0,  # 0.0 .. 1.0
    "ControlledByFx": 0.0,  # 0.0 .. 1.0
    "ControlledByFxMode": 1.0,  # 1.0 .. 2.0
    "PinchDeformation": 0.0,  # 0.0 .. 1.0 (vertex stage only)
    "FillAmount": 0.771318018,  # 0.0 .. 1.0
    "WaveAmplitude": 0.200000003,
    "WaveSpeed": 0.0500000007,
    "WaveSize": 0.200000003,
}

_WHITE = (1.0, 1.0, 1.0, 1.0)
# Dielectric response anchors used by the authored material family.
_GLASS_F0 = (0.25, 0.04, 0.0)


class FillableFluidVertex(MaterialTypeBase):
    def _wave_normal(self, tree, data, location, world_xy, offset, direction, label):
        """Decode a two-channel tangent-space normal from the panning wave sample"""
        nodes = tree.nodes
        links = tree.links
        pan = new_labeled_node(
            nodes,
            "ShaderNodeCombineXYZ",
            f"{label} Pan",
            (location[0], location[1] - 150),
        )
        pan_x = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            offset,
            direction[0],
            name=f"{label} Pan X",
            location=(location[0] - 180, location[1] - 150),
        )
        pan_y = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            offset,
            direction[1],
            name=f"{label} Pan Y",
            location=(location[0] - 180, location[1] - 270),
        )
        links.new(pan_x, pan.inputs["X"])
        links.new(pan_y, pan.inputs["Y"])
        uv = shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            world_xy,
            pan.outputs["Vector"],
            name=f"{label} UV",
            location=(location[0] + 180, location[1]),
        )
        texture = self._parameter_texture_node(
            nodes,
            links,
            data,
            "Waves",
            (location[0] + 360, location[1]),
            uv,
            non_color=True,
            error_label="fillable fluid vertex",
        )
        decoder = decode_cp77_normal(
            tree,
            texture.outputs["Color"],
            strength=1.0,
            location=(location[0] + 620, location[1]),
            label=f"{label} DirectX Decode",
        )
        return decoder.outputs["Tangent"]

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        controlled_by_fx = param_float(data, "ControlledByFx", 0.0) > 0.5
        bbox_min = param_vector(data, "FluidBoundingBoxMin", (0.0, 0.0, 0.0, 0.0))
        bbox_max = param_vector(data, "FluidBoundingBoxMax", (0.0, 0.0, 0.0, 0.0))
        fresnel_bias = param_float(data, "FresnelBias", _SCALAR_DEFAULTS["FresnelBias"])

        time = create_scene_time_value(tree, -2200, 700, "CP77 Fluid Time")
        time_socket = time.outputs["Value"]

        label_suffix = " (fx-driven)" if controlled_by_fx else " (material value)"
        fill_amount = value_socket(
            nodes,
            "CP77 FillAmount",
            clamp01(param_float(data, "FillAmount", _SCALAR_DEFAULTS["FillAmount"])),
            (-2200, 560),
            f"FillAmount{label_suffix}",
        )
        wave_amplitude = value_socket(
            nodes,
            "CP77 WaveAmplitude",
            param_float(data, "WaveAmplitude", _SCALAR_DEFAULTS["WaveAmplitude"]),
            (-2200, 440),
            f"WaveAmplitude{label_suffix}",
        )
        wave_speed = value_socket(
            nodes,
            "CP77 WaveSpeed",
            param_float(data, "WaveSpeed", _SCALAR_DEFAULTS["WaveSpeed"]),
            (-2200, 320),
            f"WaveSpeed{label_suffix}",
        )
        wave_size = value_socket(
            nodes,
            "CP77 WaveSize",
            max(1.0e-4, param_float(data, "WaveSize", _SCALAR_DEFAULTS["WaveSize"])),
            (-2200, 200),
            f"WaveSize{label_suffix}",
        )

        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "Geometry", (-2200, -60)
        )
        world_position = geometry.outputs["Position"]
        geometric_normal = geometry.outputs["Normal"]
        texcoord = new_labeled_node(
            nodes, "ShaderNodeTexCoord", "Coordinates", (-2200, -300)
        )
        uv_socket = texcoord.outputs["UV"]
        object_split = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "Object XYZ", (-2020, -300)
        )
        links.new(texcoord.outputs["Object"], object_split.inputs["Vector"])
        object_z = object_split.outputs["Z"]

        # Scale world-space coordinates for wave sampling.
        wave_divisor = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            wave_size,
            0.1,
            name="WaveSize x 0.1",
            location=(-2020, 200),
        )
        wave_divisor = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            wave_divisor,
            1.0e-5,
            name="Guard Divisor",
            location=(-1840, 200),
        )
        wave_scale = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            1.0,
            wave_divisor,
            name="1 / Divisor",
            location=(-1660, 200),
        )
        world_xy = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY",
            world_position,
            (1.0, 1.0, 0.0),
            name="WorldPosition.xy",
            location=(-1660, 40),
        )
        world_xy = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            world_xy,
            scale=wave_scale,
            name="waveUvWorld",
            location=(-1480, 40),
        )
        wave_offset = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            time_socket,
            wave_speed,
            name="Time x WaveSpeed",
            location=(-1840, 320),
        )

        normal_1 = self._wave_normal(
            tree,
            data,
            (-1200, 320),
            world_xy,
            wave_offset,
            (1.0, 0.1),
            "Waves A",
        )
        normal_2 = self._wave_normal(
            tree,
            data,
            (-1200, -140),
            world_xy,
            wave_offset,
            (-0.6, -0.3),
            "Waves B",
        )
        blended = shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            normal_1,
            normal_2,
            name="N1 + N2",
            location=(-380, 100),
        )
        blended = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            blended,
            scale=0.5,
            name="lerp(N1, N2, 0.5)",
            location=(-200, 100),
        )
        amplitude = shader_nodes.math(
            nodes,
            links,
            "ADD",
            wave_amplitude,
            0.0,
            name="saturate(WaveAmplitude)",
            location=(-380, -60),
            use_clamp=True,
        )
        wave_normal = new_labeled_node(
            nodes, "ShaderNodeMix", "Flat to Waves", (-20, 100)
        )
        wave_normal.data_type = "VECTOR"
        links.new(amplitude, find_input(wave_normal, "Factor"))
        shader_nodes.socket_by_identifier(
            wave_normal.inputs, "A_Vector"
        ).default_value = (0.0, 0.0, 1.0)
        links.new(
            blended, shader_nodes.socket_by_identifier(wave_normal.inputs, "B_Vector")
        )
        wave_tangent = shader_nodes.vector_math(
            nodes,
            links,
            "NORMALIZE",
            wave_normal.outputs.get("Result")
            or shader_nodes.socket_by_identifier(wave_normal.outputs, "Result_Vector"),
            name="Normalize Wave Normal",
            location=(160, 100),
        )
        wave_encoded = encode_tangent_normal(
            tree, wave_tangent, location=(340, 100), label="Encode Wave Normal"
        )
        wave_normal_socket = tangent_to_normal_map(
            tree, wave_encoded, location=(520, 100), label="Wave Normal"
        )

        # fluidPositionZ reconstructed from the object-space bounding box.
        fluid_plane = new_labeled_node(
            nodes, "ShaderNodeMapRange", "fluidPositionZ", (-2020, -480)
        )
        fluid_plane.inputs["From Min"].default_value = 0.0
        fluid_plane.inputs["From Max"].default_value = 1.0
        fluid_plane.inputs["To Min"].default_value = float(bbox_min[2])
        fluid_plane.inputs["To Max"].default_value = float(bbox_max[2])
        links.new(fill_amount, fluid_plane.inputs["Value"])
        fluid_plane_socket = fluid_plane.outputs["Result"]

        # Derive the meniscus weight from distance to the fluid surface.
        distance = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            fluid_plane_socket,
            object_z,
            name="fluidZ - z",
            location=(-1840, -480),
        )
        distance = shader_nodes.math(
            nodes, links, "ABSOLUTE", distance, name="abs", location=(-1660, -480)
        )
        distance = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            distance,
            150.0,
            name="x150",
            location=(-1480, -480),
        )
        distance = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            distance,
            fill_amount,
            name="x FillAmount",
            location=(-1300, -480),
            use_clamp=True,
        )
        distance = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            distance,
            3.14,
            name="x pi",
            location=(-1120, -480),
        )
        menisk = shader_nodes.math(
            nodes, links, "COSINE", distance, name="cos", location=(-940, -480)
        )
        menisk = shader_nodes.math(
            nodes,
            links,
            "ADD",
            menisk,
            0.0,
            name="saturate",
            location=(-760, -480),
            use_clamp=True,
        )

        normal_mix = new_labeled_node(
            nodes, "ShaderNodeMix", "Meniscus Blend", (340, 100)
        )
        normal_mix.data_type = "VECTOR"
        links.new(menisk, find_input(normal_mix, "Factor"))
        links.new(
            geometric_normal,
            shader_nodes.socket_by_identifier(normal_mix.inputs, "A_Vector"),
        )
        links.new(
            wave_normal_socket,
            shader_nodes.socket_by_identifier(normal_mix.inputs, "B_Vector"),
        )
        surface_normal = shader_nodes.vector_math(
            nodes,
            links,
            "NORMALIZE",
            normal_mix.outputs.get("Result")
            or shader_nodes.socket_by_identifier(normal_mix.outputs, "Result_Vector"),
            name="Normalize Surface",
            location=(520, 100),
        )

        # Blend the sampled tint using the Fresnel response.
        tint = param_color(data, "TintColor", _WHITE)
        glass_tint = self._parameter_texture_node(
            nodes,
            links,
            data,
            "GlassTint",
            (340, -300),
            uv_socket,
            error_label="fillable fluid vertex",
        )
        tinted = mix_color_socket(
            nodes,
            links,
            "GlassTint x TintColor",
            glass_tint.outputs["Color"],
            tint,
            1.0,
            (620, -300),
            blend_type="MULTIPLY",
        )
        fresnel = new_labeled_node(
            nodes, "ShaderNodeFresnel", "Glass Tint Fresnel", (340, -520)
        )
        fresnel_ior = find_input(fresnel, "IOR")
        if fresnel_ior is not None:
            fresnel_ior.default_value = max(1.0, 1.0 + fresnel_bias * 0.5)
        links.new(surface_normal, find_input(fresnel, "Normal"))
        edge_weight = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            fresnel.outputs["Factor"],
            0.75,
            name="Edge Tint Multiplier",
            location=(520, -520),
            use_clamp=True,
        )
        refraction_tint = mix_color_socket(
            nodes,
            links,
            "Glass Tint Background",
            tinted,
            _WHITE,
            edge_weight,
            (800, -300),
        )

        # Scale opacity near the empty-fill threshold.
        fill_ramp = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            fill_amount,
            0.05,
            name="FillAmount / 0.05",
            location=(-760, -700),
            use_clamp=True,
        )
        opacity = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            fill_ramp,
            clamp01(param_float(data, "Opacity", _SCALAR_DEFAULTS["Opacity"])),
            name="opacityFinal",
            location=(-580, -700),
        )

        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Fillable Fluid Vertex", (1120, 100)
        )
        base_input = find_input(principled, "Base Color")
        if base_input is not None:
            links.new(refraction_tint, base_input)
        normal_input = find_input(principled, "Normal")
        if normal_input is not None:
            links.new(surface_normal, normal_input)
        for socket_name, value in (
            ("Metallic", 0.0),
            ("Roughness", 0.0),
            ("IOR", max(1.0, param_float(data, "IOR", _SCALAR_DEFAULTS["IOR"]))),
            ("Transmission Weight", 1.0),
            ("Specular IOR Level", clamp01(lerp_three(_GLASS_F0, fresnel_bias) * 2.0)),
        ):
            socket = find_input(principled, socket_name)
            if socket is not None:
                socket.default_value = value
        specular_tint = find_input(principled, "Specular Tint")
        if specular_tint is not None:
            specular_tint.default_value = param_color(
                data, "GlassSpecularColor", _WHITE
            )
        coat_weight = find_input(principled, "Coat Weight")
        if coat_weight is not None:
            coat_weight.default_value = clamp01(
                param_float(
                    data,
                    "FrontFacesReflectionPower",
                    _SCALAR_DEFAULTS["FrontFacesReflectionPower"],
                )
                / 10.0
            )
        alpha_input = find_input(principled, "Alpha")
        if alpha_input is not None:
            links.new(opacity, alpha_input)

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (1420, 100)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        set_transparent(Mat)
        Mat.diffuse_color = (*tint[:3], 1.0)
