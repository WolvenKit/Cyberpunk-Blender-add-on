import hashlib

from ..bartmoss.scalar import clamp01, clamp_scalar
from ..blender import shader_nodes
from .graph import set_transparent, value_socket
from .mat_common import (
    MaterialTypeBase,
    add_group_node,
    find_input,
    get_or_build_node_group,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
    param_vector,
    scene_time_socket,
)

TEMPLATE = "base\\materials\\fillable_fluid.mt"

_SCALAR_DEFAULTS = {
    "AdditiveAlphaBlend": 1.0,
    "RoughnessScale": 0.0500000007,  # 0.05 .. 1.0
    "MetalnessScale": 0.997566998,  # 0.0 .. 1.0
    "ObjectSize": 1.0,  # 0 selects the bounding-box path
    "ControlledByFx": 0.0,  # 0.0 .. 1.0
    "FillAmount": 0.472018987,  # 0.0 .. 1.0
    "WaveAmplitude": 0.200000003,
    "WaveSpeed": 0.0500000007,
    "WaveSize": 0.200000003,
}

_TINT = (85.0 / 255.0, 55.0 / 255.0, 55.0 / 255.0, 1.0)


class FillableFluid(MaterialTypeBase):
    def _wave_channel(self, nodes, links, data, name, location, uv_socket, channel):
        """Sample the shared Waves texture and split out a single channel"""
        node = self._parameter_texture_node(
            nodes,
            links,
            data,
            "Waves",
            location,
            uv_socket,
            non_color=True,
            error_label="fillable fluid waves",
        )
        node.label = name
        node.name = name
        split = new_labeled_node(
            nodes,
            "ShaderNodeSeparateColor",
            f"{name}.{channel}",
            (location[0] + 220, location[1]),
        )
        split.mode = "RGB"
        links.new(
            node.outputs["Color"],
            split.inputs["Color"],
        )
        return split.outputs.get(channel) or shader_nodes.socket_by_identifier(
            split.outputs, "Red"
        )

    def _wave_offset(self, nodes, links, name, location, offset, sign):
        signed_offset = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            offset,
            sign,
            name=f"{name} Offset",
            location=location,
        )
        vector = new_labeled_node(
            nodes,
            "ShaderNodeCombineXYZ",
            f"{name} Offset Vector",
            (location[0] + 180, location[1]),
        )
        links.new(signed_offset, vector.inputs["X"])
        links.new(signed_offset, vector.inputs["Y"])
        return vector.outputs["Vector"]

    def _wave_uv(self, nodes, links, name, location, scaled, offset_vector):
        return shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            scaled,
            offset_vector,
            name=f"{name} UV",
            location=location,
        )

    def _wave_normal_group(self, data):
        waves_path = param_texture_path(data, "Waves")
        identity = repr(
            (self.BasePath, self.ProjPath, self.image_format, waves_path)
        ).encode("utf-8")
        suffix = hashlib.blake2b(identity, digest_size=8).hexdigest()
        group_name = f"CP77 Fillable Fluid Wave Normal {suffix} v2"
        inputs = (
            ("NodeSocketVector", "Top Position"),
            ("NodeSocketFloat", "Wave Size"),
            ("NodeSocketFloat", "Wave Offset"),
            ("NodeSocketFloat", "Wave Amplitude"),
        )
        outputs = (("NodeSocketVector", "Normal"),)

        def build(group):
            nodes = group.nodes
            links = group.links
            group_in = new_labeled_node(nodes, "NodeGroupInput", "Inputs", (-2200, 0))
            group_out = new_labeled_node(nodes, "NodeGroupOutput", "Outputs", (2200, 0))
            amplitude_floor = shader_nodes.math(
                nodes,
                links,
                "MAXIMUM",
                group_in.outputs["Wave Amplitude"],
                0.001,
                name="max(WaveAmplitude, 0.001)",
                location=(-1950, -360),
            )
            offset_vector = self._wave_offset(
                nodes,
                links,
                "Kernel",
                (-1500, -720),
                group_in.outputs["Wave Offset"],
                1.0,
            )
            summed_normal = None
            sample_index = 0
            for kernel_y in (-1, 0, 1):
                for kernel_x in (-1, 0, 1):
                    y = 460 - sample_index * 115
                    sample_index += 1
                    sample_position = shader_nodes.vector_math(
                        nodes,
                        links,
                        "ADD",
                        group_in.outputs["Top Position"],
                        (kernel_x * 0.1, kernel_y * 0.1, 0.0),
                        name=f"Kernel {kernel_x},{kernel_y} Position",
                        location=(-1800, y),
                    )
                    scaled = shader_nodes.vector_math(
                        nodes,
                        links,
                        "SCALE",
                        sample_position,
                        scale=group_in.outputs["Wave Size"],
                        name=f"Kernel {kernel_x},{kernel_y} x WaveSize",
                        location=(-1500, y),
                    )
                    sample_uv = self._wave_uv(
                        nodes,
                        links,
                        f"Kernel {kernel_x},{kernel_y}",
                        (-1140, y),
                        scaled,
                        offset_vector,
                    )
                    wave_sample = self._wave_channel(
                        nodes,
                        links,
                        data,
                        f"Kernel {kernel_x},{kernel_y}",
                        (-950, y),
                        sample_uv,
                        "Red",
                    )
                    one_minus = shader_nodes.math(
                        nodes,
                        links,
                        "SUBTRACT",
                        1.0,
                        wave_sample,
                        name=f"Kernel {kernel_x},{kernel_y} 1-wave",
                        location=(-620, y),
                    )
                    nx = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        one_minus,
                        float(kernel_x),
                        name=f"Kernel {kernel_x},{kernel_y} X",
                        location=(-430, y + 35),
                    )
                    ny = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        one_minus,
                        float(kernel_y),
                        name=f"Kernel {kernel_x},{kernel_y} Y",
                        location=(-430, y - 35),
                    )
                    nz = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        wave_sample,
                        amplitude_floor,
                        name=f"Kernel {kernel_x},{kernel_y} Z amp",
                        location=(-430, y - 105),
                    )
                    nz = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        nz,
                        group_in.outputs["Wave Size"],
                        name=f"Kernel {kernel_x},{kernel_y} Z size",
                        location=(-240, y - 105),
                    )
                    nz = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        nz,
                        4.0,
                        name=f"Kernel {kernel_x},{kernel_y} Z x4",
                        location=(-50, y - 105),
                    )
                    sample_normal = new_labeled_node(
                        nodes,
                        "ShaderNodeCombineXYZ",
                        f"Kernel {kernel_x},{kernel_y} Normal",
                        (150, y),
                    )
                    links.new(nx, sample_normal.inputs["X"])
                    links.new(ny, sample_normal.inputs["Y"])
                    links.new(nz, sample_normal.inputs["Z"])
                    normalized = shader_nodes.vector_math(
                        nodes,
                        links,
                        "NORMALIZE",
                        sample_normal.outputs["Vector"],
                        name=f"Normalize Kernel {kernel_x},{kernel_y}",
                        location=(350, y),
                    )
                    if summed_normal is None:
                        summed_normal = normalized
                    else:
                        summed_normal = shader_nodes.vector_math(
                            nodes,
                            links,
                            "ADD",
                            summed_normal,
                            normalized,
                            name=f"Convolution Sum {sample_index}",
                            location=(700 + sample_index * 80, y),
                        )
            normalized_sum = shader_nodes.vector_math(
                nodes,
                links,
                "NORMALIZE",
                summed_normal,
                name="Normalize 3x3 Convolution",
                location=(1950, 0),
            )
            links.new(normalized_sum, group_out.inputs["Normal"])

        return get_or_build_node_group(group_name, inputs, outputs, build)

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        controlled_by_fx = param_float(data, "ControlledByFx", 0.0) > 0.5
        object_size = param_float(data, "ObjectSize", _SCALAR_DEFAULTS["ObjectSize"])
        bbox_min = param_vector(data, "FluidBoundingBoxMin", (0.0, 0.0, 0.0, 0.0))
        bbox_max = param_vector(data, "FluidBoundingBoxMax", (0.0, 0.0, 0.0, 0.0))

        time_socket = scene_time_socket(tree.nodes, (-2200, 760), "CP77 Fluid Time")

        # Runtime material-parameter slots 0..3 are used when ControlledByFx is set.
        suffix = " (fx-driven)" if controlled_by_fx else " (material value)"
        fill_amount = value_socket(
            nodes,
            "CP77 FillAmount",
            clamp01(param_float(data, "FillAmount", _SCALAR_DEFAULTS["FillAmount"])),
            (-2200, 620),
            f"FillAmount{suffix}",
        )
        wave_amplitude = value_socket(
            nodes,
            "CP77 WaveAmplitude",
            param_float(data, "WaveAmplitude", _SCALAR_DEFAULTS["WaveAmplitude"]),
            (-2200, 500),
            f"WaveAmplitude{suffix}",
        )
        wave_speed = value_socket(
            nodes,
            "CP77 WaveSpeed",
            param_float(data, "WaveSpeed", _SCALAR_DEFAULTS["WaveSpeed"]),
            (-2200, 380),
            f"WaveSpeed{suffix}",
        )
        wave_size = value_socket(
            nodes,
            "CP77 WaveSize",
            param_float(data, "WaveSize", _SCALAR_DEFAULTS["WaveSize"]),
            (-2200, 260),
            f"WaveSize{suffix}",
        )

        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "Geometry", (-2200, 40)
        )
        world_position = geometry.outputs["Position"]
        backfacing = geometry.outputs["Backfacing"]
        incoming = geometry.outputs["Incoming"]

        # ProxyTranslationSlot is the instance's world translation.
        object_info = new_labeled_node(
            nodes, "ShaderNodeObjectInfo", "ProxyTranslation", (-2200, -220)
        )
        proxy = object_info.outputs["Location"]
        proxy_split = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "ProxyTranslation.z", (-2020, -220)
        )
        links.new(proxy, proxy_split.inputs["Vector"])
        proxy_z = proxy_split.outputs["Z"]

        world_split = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "WorldPosition.z", (-2020, 40)
        )
        links.new(world_position, world_split.inputs["Vector"])
        world_z = world_split.outputs["Z"]

        wave_offset = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            time_socket,
            wave_speed,
            name="Time x WaveSpeed",
            location=(-2020, 380),
        )
        scaled_wave_position = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            world_position,
            scale=wave_size,
            name="Waves x WaveSize",
            location=(-1840, 260),
        )
        forward_offset = self._wave_offset(
            nodes, links, "Waves", (-1840, 120), wave_offset, 1.0
        )
        reverse_offset = self._wave_offset(
            nodes, links, "Waves Alt", (-1840, -160), wave_offset, -1.0
        )
        uv_forward = self._wave_uv(
            nodes, links, "Waves", (-1480, 260), scaled_wave_position, forward_offset
        )
        uv_reverse = self._wave_uv(
            nodes,
            links,
            "Waves Alt",
            (-1480, -20),
            scaled_wave_position,
            reverse_offset,
        )
        waves_x = self._wave_channel(
            nodes, links, data, "Waves", (-1300, 260), uv_forward, "Red"
        )
        waves_y = self._wave_channel(
            nodes, links, data, "Waves Alt", (-1300, -20), uv_reverse, "Green"
        )

        wave_height = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            waves_x,
            waves_y,
            name="Waves x WavesAlt",
            location=(-840, 180),
        )
        wave_height = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            wave_height,
            wave_amplitude,
            name="x WaveAmplitude",
            location=(-660, 180),
        )

        # filler / fillOffset: ObjectSize path when nonzero, bounding box otherwise.
        if object_size == 0.0:
            box = new_labeled_node(
                nodes, "ShaderNodeMapRange", "lerp(BottomZ, TopZ)", (-840, -300)
            )
            box.inputs["From Min"].default_value = 0.0
            box.inputs["From Max"].default_value = 1.0
            box.inputs["To Min"].default_value = float(bbox_min[2])
            box.inputs["To Max"].default_value = float(bbox_max[2])
            links.new(fill_amount, box.inputs["Value"])
            filler = box.outputs["Result"]
            fill_offset_local = filler
        else:
            filler = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                fill_amount,
                object_size * 2.0,
                name="ObjectSize x FillAmount x 2",
                location=(-840, -300),
            )
            centred = shader_nodes.math(
                nodes,
                links,
                "SUBTRACT",
                fill_amount,
                0.5,
                name="FillAmount - 0.5",
                location=(-840, -440),
            )
            centred = shader_nodes.math(
                nodes, links, "MULTIPLY", centred, 2.0, name="x2", location=(-660, -440)
            )
            fill_offset_local = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                centred,
                object_size,
                name="x ObjectSize",
                location=(-480, -440),
            )
        fill_offset = shader_nodes.math(
            nodes,
            links,
            "ADD",
            proxy_z,
            fill_offset_local,
            name="fillOffset",
            location=(-300, -440),
        )

        # Compute a sharp fill-plane mask from object-space height and wave displacement.
        delta = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            world_z,
            proxy_z,
            name="z - ProxyTranslation.z",
            location=(-480, 40),
        )
        delta = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            delta,
            wave_height,
            name="- Waves",
            location=(-300, 40),
        )
        if object_size != 0.0:
            delta = shader_nodes.math(
                nodes,
                links,
                "ADD",
                delta,
                object_size,
                name="+ ObjectSize",
                location=(-120, 40),
            )
        delta = shader_nodes.math(
            nodes, links, "SUBTRACT", delta, filler, name="- filler", location=(60, 40)
        )
        delta = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            delta,
            5000.0,
            name="x5000",
            location=(240, 40),
            use_clamp=True,
        )
        submerged = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            delta,
            name="1 - saturate",
            location=(420, 40),
            use_clamp=True,
        )

        # Back faces reproject the shading point onto the fill plane before sampling the wave field.
        camera = new_labeled_node(
            nodes, "ShaderNodeCameraData", "Camera", (-2200, -460)
        )
        eye_position = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY_ADD",
            incoming,
            camera.outputs["View Distance"],
            world_position,
            name="SC_CameraPosition",
            location=(-1840, -460),
        )
        eye_split = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "Camera.z", (-1660, -460)
        )
        links.new(eye_position, eye_split.inputs["Vector"])
        eye_z = eye_split.outputs["Z"]

        z_eye = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            eye_z,
            world_z,
            name="Camera.z - z",
            location=(-120, -600),
        )
        z_eye = shader_nodes.math(
            nodes, links, "ABSOLUTE", z_eye, name="zEyeDiff", location=(60, -600)
        )
        z_eye = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            z_eye,
            1.0e-5,
            name="Guard zEyeDiff",
            location=(240, -600),
        )
        z_fill = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            eye_z,
            fill_offset,
            name="Camera.z - fillOffset",
            location=(-120, -740),
        )
        z_fill = shader_nodes.math(
            nodes, links, "ABSOLUTE", z_fill, name="zFillEyeDiff", location=(60, -740)
        )
        ratio = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            z_fill,
            z_eye,
            name="zFill / zEye",
            location=(420, -600),
        )
        ratio = shader_nodes.math(
            nodes, links, "SUBTRACT", 1.0, ratio, name="1 - ratio", location=(600, -600)
        )

        to_eye = shader_nodes.vector_math(
            nodes,
            links,
            "SUBTRACT",
            eye_position,
            world_position,
            name="Eye - WorldPosition",
            location=(600, -460),
        )
        top_position = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY_ADD",
            to_eye,
            ratio,
            world_position,
            name="Top Surface Position",
            location=(960, -460),
        )
        lift = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            submerged,
            0.5,
            name="delta - 0.5",
            location=(600, -300),
        )
        lift = shader_nodes.math(
            nodes, links, "MULTIPLY", lift, 10.0, name="x10", location=(780, -300)
        )
        lift_vector = new_labeled_node(
            nodes, "ShaderNodeCombineXYZ", "Wave Lift", (960, -300)
        )
        links.new(lift, lift_vector.inputs["Z"])
        top_position = shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            top_position,
            lift_vector.outputs["Vector"],
            name="Reprojected Sample Point",
            location=(1140, -460),
        )

        # Apply the shared 3x3 convolution to the backface liquid surface.
        wave_normal_group = self._wave_normal_group(data)
        wave_normal = add_group_node(
            tree,
            wave_normal_group,
            (1500, -900),
            label="3x3 Wave Normal",
            name="CP77 Fillable Fluid Wave Normal",
        )
        links.new(top_position, wave_normal.inputs["Top Position"])
        links.new(wave_size, wave_normal.inputs["Wave Size"])
        links.new(wave_offset, wave_normal.inputs["Wave Offset"])
        links.new(wave_amplitude, wave_normal.inputs["Wave Amplitude"])
        top_normal_socket = wave_normal.outputs["Normal"]

        # The front-facing branch uses the authored placeholder behavior.
        front_normal = shader_nodes.vector_math(
            nodes,
            links,
            "NORMALIZE",
            world_position,
            name="Normalize World Position",
            location=(3180, -340),
        )
        normal_mix = new_labeled_node(
            nodes, "ShaderNodeMix", "Backface Selects Top", (3360, -440)
        )
        normal_mix.data_type = "VECTOR"
        links.new(backfacing, find_input(normal_mix, "Factor"))
        links.new(
            front_normal,
            shader_nodes.socket_by_identifier(normal_mix.inputs, "A_Vector"),
        )
        links.new(
            top_normal_socket,
            shader_nodes.socket_by_identifier(normal_mix.inputs, "B_Vector"),
        )
        normal_socket = normal_mix.outputs.get(
            "Result"
        ) or shader_nodes.socket_by_identifier(normal_mix.outputs, "Result_Vector")

        tint = param_color(data, "TintColor", _TINT)
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Fillable Fluid", (3640, 40)
        )
        base_input = find_input(principled, "Base Color")
        if base_input is not None:
            base_input.default_value = (*tint[:3], 1.0)
        metallic_input = find_input(principled, "Metallic")
        if metallic_input is not None:
            metallic_input.default_value = clamp01(
                param_float(data, "MetalnessScale", _SCALAR_DEFAULTS["MetalnessScale"])
            )
        roughness_input = find_input(principled, "Roughness")
        if roughness_input is not None:
            roughness_input.default_value = clamp_scalar(
                param_float(data, "RoughnessScale", _SCALAR_DEFAULTS["RoughnessScale"]),
                0.05,
                1.0,
            )
        normal_input = find_input(principled, "Normal")
        if normal_input is not None:
            links.new(normal_socket, normal_input)

        # Clip pixels above the fill plane.
        clip = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            submerged,
            0.5,
            name="Discard Above Surface",
            location=(3360, 40),
        )
        alpha_input = find_input(principled, "Alpha")
        if alpha_input is not None:
            links.new(clip, alpha_input)

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (3920, 40)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        set_transparent(Mat)
        Mat.diffuse_color = (*tint[:3], 1.0)
