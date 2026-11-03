import math

from ..assetio.paths import backslash_depot_key
from ..bartmoss.geometry import calc_subuv_offset
from ..blender import shader_nodes
from ..materials.blender.images import image_is_placeholder
from .bundles import decal_uv_transform_socket, smoothstep_socket
from .decal_nodes import _new_graph, _set_transparent
from .graph import mix_color_socket, mix_scalar_socket, rgb_socket, value_socket
from .mat_common import (
    MaterialTypeBase,
    find_input,
    material_property_socket,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
)
from .normal_math import (
    create_cp77_normal_texture,
    decode_cp77_normal,
    directx_tangent_to_normal_map,
    encode_tangent_normal,
    tangent_to_normal_map,
)


def _texture(owner, nodes, links, data, key, location, uv, *, non_color=False):
    path = param_texture_path(data, key)
    if not path:
        return None
    image = owner._load_relative_image(
        path,
        non_color=non_color,
        error_label=key,
    )
    if image is None or image_is_placeholder(image):
        return None
    node = new_labeled_node(nodes, "ShaderNodeTexImage", key, location)
    node.image = image
    node.extension = "REPEAT"
    links.new(uv, find_input(node, "Vector"))
    return node


def _red(nodes, links, source, name, location):
    separate = new_labeled_node(nodes, "ShaderNodeSeparateColor", name, location)
    separate.mode = "RGB"
    links.new(source, separate.inputs["Color"])
    return separate.outputs["Red"]


def _subuv(nodes, uv, frame, columns, rows, location, label):
    columns = max(1.0, float(columns))
    rows = max(1.0, float(rows))
    offset_u, offset_v = calc_subuv_offset(frame, columns, rows)
    return decal_uv_transform_socket(
        nodes.id_data,
        uv,
        location,
        frame_size=(columns, rows, 1.0),
        frame_offset=(offset_u, offset_v, 0.0),
        label=label,
    )


class TrailDecal(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        template = backslash_depot_key(Mat.get("MaterialTemplate"))
        has_color = not template.endswith("trail_decal_normal.mt")
        has_normal = not template.endswith("trail_decal.mt")

        tree, output, principled = _new_graph(Mat, "Trail Decal")
        nodes, links = tree.nodes, tree.links
        uv = new_labeled_node(nodes, "ShaderNodeUVMap", "UV", (-1800, 300)).outputs[
            "UV"
        ]
        uv = _subuv(
            nodes,
            uv,
            param_float(data, "Frame", 0.0) + param_float(data, "SubUVx", 1.0),
            param_float(data, "SubUVx", 1.0),
            param_float(data, "SubUVy", 1.0),
            (-1560, 300),
            "Trail SubUV",
        )
        vertex = new_labeled_node(
            nodes, "ShaderNodeVertexColor", "Vertex Color", (-1560, 760)
        )
        color_alpha = None

        if has_color:
            diffuse = _texture(
                self, nodes, links, data, "DiffuseTexture", (-1260, 560), uv
            )
            diffuse_color = (
                diffuse.outputs["Color"]
                if diffuse is not None
                else rgb_socket(
                    nodes, "Diffuse Fallback", (1.0, 1.0, 1.0, 1.0), (-1040, 560)
                )
            )
            color = mix_color_socket(
                nodes,
                links,
                "Trail DiffuseColor",
                diffuse_color,
                param_color(data, "DiffuseColor", (1.0, 1.0, 1.0, 1.0)),
                1.0,
                (-800, 620),
                blend_type="MULTIPLY",
            )
            color = mix_color_socket(
                nodes,
                links,
                "Trail Vertex Color",
                color,
                vertex.outputs["Color"],
                1.0,
                (-560, 620),
                blend_type="MULTIPLY",
            )
            links.new(color, find_input(principled, "Base Color"))
            texture_alpha = diffuse.outputs["Alpha"] if diffuse is not None else 1.0
            color_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                texture_alpha,
                vertex.outputs["Alpha"],
                name="Trail Texture x Vertex Alpha",
                location=(-560, 380),
            )
            color_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                color_alpha,
                param_color(data, "DiffuseColor", (1.0, 1.0, 1.0, 1.0))[3],
                name="Trail Color Alpha",
                location=(-340, 380),
            )
            find_input(principled, "Roughness").default_value = param_float(
                data, "Roughness", 1.0
            )

        normal_alpha = None
        if has_normal:
            normal = create_cp77_normal_texture(
                self,
                tree,
                data,
                key="NormalTexture",
                uv=uv,
                strength_key="NormalStrength",
                default_strength=1.0,
                location=(-1260, -100),
                label="Trail NormalTexture",
            )
            if normal is not None:
                links.new(normal, find_input(principled, "Normal"))
                normal_texture = nodes.get("Trail NormalTexture")
                sampled_alpha = (
                    normal_texture.outputs["Alpha"]
                    if normal_texture is not None
                    else 1.0
                )
                normal_alpha = color_alpha
                if normal_alpha is None:
                    normal_alpha = shader_nodes.math(
                        nodes,
                        links,
                        "MULTIPLY",
                        sampled_alpha,
                        vertex.outputs["Alpha"],
                        name="Trail Normal Alpha",
                        location=(-340, 120),
                    )

        alpha = color_alpha if color_alpha is not None else normal_alpha
        if alpha is None:
            alpha = value_socket(nodes, "Trail Alpha Fallback", 0.0, (1260, 260))
        links.new(alpha, find_input(principled, "Alpha"))

        depth_offset = param_float(data, "DepthOffset", 0.0)
        if abs(depth_offset) > 1.0e-12:
            displacement = new_labeled_node(
                nodes, "ShaderNodeDisplacement", "DepthOffset", (1780, -320)
            )
            displacement.inputs["Height"].default_value = depth_offset
            displacement.inputs["Midlevel"].default_value = 0.0
            displacement.inputs["Scale"].default_value = 1.0
            links.new(
                displacement.outputs["Displacement"], output.inputs["Displacement"]
            )
        _set_transparent(Mat)


class AnimatedDecal(MaterialTypeBase):
    @staticmethod
    def _animated_uv(nodes, links, scaled_uv, frame, label, location):
        frame = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            frame,
            2.0,
            name=f"{label} Frame - 2",
            location=(location[0] + 160, location[1]),
        )
        frame_floor = shader_nodes.math(
            nodes,
            links,
            "FLOOR",
            frame,
            name=f"{label} Frame Floor",
            location=(location[0] + 320, location[1]),
        )
        offset_u = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            frame_floor,
            0.5,
            name=f"{label} U Offset",
            location=(location[0] + 480, location[1] + 80),
        )
        half_frame = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            frame,
            0.5,
            name=f"{label} Half Frame",
            location=(location[0] + 320, location[1] - 100),
        )
        offset_v = shader_nodes.math(
            nodes,
            links,
            "FLOOR",
            half_frame,
            name=f"{label} V Row",
            location=(location[0] + 480, location[1] - 100),
        )
        offset_v = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            offset_v,
            0.5,
            name=f"{label} V Offset",
            location=(location[0] + 640, location[1] - 100),
        )
        offset = new_labeled_node(
            nodes,
            "ShaderNodeCombineXYZ",
            f"{label} Offset",
            (location[0] + 680, location[1]),
        )
        links.new(offset_u, offset.inputs["X"])
        links.new(offset_v, offset.inputs["Y"])
        return shader_nodes.vector_math(
            nodes,
            links,
            "ADD",
            scaled_uv,
            offset.outputs["Vector"],
            name=f"{label} UV",
            location=(location[0] + 880, location[1] + 80),
        )

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree, _, principled = _new_graph(Mat, "Animated Decal")
        nodes, links = tree.nodes, tree.links
        uv = new_labeled_node(nodes, "ShaderNodeUVMap", "UV", (-2600, 260)).outputs[
            "UV"
        ]
        runtime = material_property_socket(
            nodes, Mat, "cp77_MaterialParam0", 0.76, (-2600, 900)
        )
        is_zero = shader_nodes.math(
            nodes,
            links,
            "LESS_THAN",
            runtime,
            1.0e-8,
            name="Animated Decal Zero Fallback",
            location=(-2400, 900),
        )
        runtime = mix_scalar_socket(
            nodes, links, "Animated Decal Runtime", (-2200, 900), runtime, 0.76, is_zero
        )
        phase = shader_nodes.math(
            nodes,
            links,
            "FRACT",
            runtime,
            name="Animated Decal Phase",
            location=(-2000, 900),
        )
        next_phase = shader_nodes.math(
            nodes,
            links,
            "ADD",
            phase,
            0.25,
            name="Animated Decal Next Phase",
            location=(-2000, 760),
        )
        next_phase = shader_nodes.math(
            nodes,
            links,
            "FRACT",
            next_phase,
            name="Animated Decal Next Fraction",
            location=(-1820, 760),
        )
        scaled_uv = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            uv,
            scale=0.5,
            name="Animated UV Scale",
            location=(-1340, 700),
        )
        current_frame = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            phase,
            4.0,
            name="Current Frame x 4",
            location=(-1820, 520),
        )
        next_frame = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            next_phase,
            4.0,
            name="Next Frame x 4",
            location=(-1820, 160),
        )
        current_uv = self._animated_uv(
            nodes, links, scaled_uv, current_frame, "Current", (-1820, 520)
        )
        next_uv = self._animated_uv(
            nodes, links, scaled_uv, next_frame, "Next", (-1820, 160)
        )

        reveal = _texture(
            self,
            nodes,
            links,
            data,
            "RevealMasks",
            (-900, -200),
            next_uv,
            non_color=True,
        )
        reveal_red = (
            _red(nodes, links, reveal.outputs["Color"], "RevealMasks.r", (-680, -200))
            if reveal
            else 1.0
        )
        within_frame = shader_nodes.math(
            nodes,
            links,
            "FRACT",
            current_frame,
            name="Reveal Frame Fraction",
            location=(-720, -380),
        )
        reveal_factor = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            within_frame,
            2.0,
            name="Reveal Progress x 2",
            location=(-520, -380),
        )
        reveal_factor = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            reveal_factor,
            reveal_red,
            name="Reveal Progress - Mask",
            location=(-340, -300),
            use_clamp=True,
        )
        reveal_factor = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            reveal_factor,
            0.5,
            name="Reveal Contrast Center",
            location=(-160, -300),
        )
        reveal_factor = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            reveal_factor,
            100.0,
            name="Reveal Contrast",
            location=(20, -300),
        )
        reveal_factor = shader_nodes.math(
            nodes,
            links,
            "ADD",
            reveal_factor,
            0.5,
            name="Reveal Mask",
            location=(200, -300),
            use_clamp=True,
        )
        last_frame = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            current_frame,
            3.0,
            name="Animated Blank Fourth Frame",
            location=(-700, -520),
        )

        diffuse_current = _texture(
            self, nodes, links, data, "DiffuseTexture", (-900, 620), current_uv
        )
        diffuse_next = _texture(
            self, nodes, links, data, "DiffuseTexture", (-900, 420), next_uv
        )
        current_color = (
            diffuse_current.outputs["Color"]
            if diffuse_current
            else (0.0, 0.0, 0.0, 0.0)
        )
        current_color = mix_color_socket(
            nodes,
            links,
            "Blank Animated Current Frame",
            current_color,
            (0.0, 0.0, 0.0, 0.0),
            last_frame,
            (-640, 620),
        )
        next_color = (
            diffuse_next.outputs["Color"] if diffuse_next else (0.0, 0.0, 0.0, 0.0)
        )
        diffuse = mix_color_socket(
            nodes,
            links,
            "Animated Diffuse Blend",
            current_color,
            next_color,
            reveal_factor,
            (-380, 560),
        )
        links.new(diffuse, find_input(principled, "Base Color"))

        current_alpha = diffuse_current.outputs.get("Alpha") if diffuse_current else 0.0
        next_alpha = diffuse_next.outputs.get("Alpha") if diffuse_next else 0.0
        current_alpha = mix_scalar_socket(
            nodes,
            links,
            "Blank Animated Texture Alpha",
            (80, 300),
            current_alpha,
            0.0,
            last_frame,
        )
        texture_alpha = mix_scalar_socket(
            nodes,
            links,
            "Animated Texture Alpha",
            (280, 300),
            current_alpha,
            next_alpha,
            reveal_factor,
        )
        diffuse_alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            texture_alpha,
            param_float(data, "DiffuseAlpha", 0.0),
            name="Animated Diffuse Alpha",
            location=(560, 420),
        )

        normal_alpha = 0.0
        normal_current = _texture(
            self,
            nodes,
            links,
            data,
            "NormalTexture",
            (-900, 80),
            current_uv,
            non_color=True,
        )
        normal_next = _texture(
            self,
            nodes,
            links,
            data,
            "NormalTexture",
            (-900, -100),
            next_uv,
            non_color=True,
        )
        if normal_current is not None and normal_next is not None:
            current_tangent = decode_cp77_normal(
                tree,
                normal_current.outputs["Color"],
                location=(-640, 80),
                label="Current Animated Normal",
            ).outputs["Tangent"]
            next_tangent = decode_cp77_normal(
                tree,
                normal_next.outputs["Color"],
                location=(-640, -100),
                label="Next Animated Normal",
            ).outputs["Tangent"]
            current_tangent = shader_nodes.vector_lerp(
                nodes,
                links,
                current_tangent,
                (0.0, 0.0, 0.0),
                last_frame,
                name="Blank Animated Normal",
                location=(-340, 40),
            )
            tangent = shader_nodes.vector_lerp(
                nodes,
                links,
                current_tangent,
                next_tangent,
                reveal_factor,
                name="Animated Normal Blend",
                location=(40, 40),
            )
            encoded = encode_tangent_normal(
                tree, tangent, location=(440, 40), label="Animated Normal Encode"
            )
            normal = tangent_to_normal_map(
                tree, encoded, location=(640, 40), label="Animated Decal Normal"
            )
            links.new(normal, find_input(principled, "Normal"))
            normal_alpha = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                texture_alpha,
                param_float(data, "NormalAlpha", 0.0),
                name="Animated Normal Influence",
                location=(880, 40),
            )

        material_alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            texture_alpha,
            param_float(data, "RoughnessMetalnessAlpha", 0.0),
            name="Animated Material Influence",
            location=(880, -180),
        )
        for key, target, y in (
            ("RoughnessTexture", "Roughness", -420),
            ("MetalnessTexture", "Metallic", -620),
        ):
            current = _texture(
                self, nodes, links, data, key, (-900, y), current_uv, non_color=True
            )
            following = _texture(
                self, nodes, links, data, key, (-900, y - 140), next_uv, non_color=True
            )
            current_value = (
                _red(
                    nodes,
                    links,
                    current.outputs["Color"],
                    f"Current {key}.r",
                    (-660, y),
                )
                if current
                else 0.0
            )
            next_value = (
                _red(
                    nodes,
                    links,
                    following.outputs["Color"],
                    f"Next {key}.r",
                    (-660, y - 140),
                )
                if following
                else 0.0
            )
            current_value = mix_scalar_socket(
                nodes,
                links,
                f"Blank Current {key}",
                (-420, y),
                current_value,
                0.0,
                last_frame,
            )
            value = mix_scalar_socket(
                nodes,
                links,
                f"Animated {key}",
                (-180, y),
                current_value,
                next_value,
                reveal_factor,
            )
            links.new(value, find_input(principled, target))

        alpha = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            diffuse_alpha,
            normal_alpha,
            name="Animated Diffuse or Normal Alpha",
            location=(1160, 260),
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            alpha,
            material_alpha,
            name="Animated Decal Preview Alpha",
            location=(1360, 260),
        )
        links.new(alpha, find_input(principled, "Alpha"))
        _set_transparent(Mat)


class BloodPuddleDecal(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree, _, principled = _new_graph(Mat, "Blood Puddle Decal")
        nodes, links = tree.nodes, tree.links
        uv = new_labeled_node(nodes, "ShaderNodeUVMap", "UV", (-2200, 300)).outputs[
            "UV"
        ]
        vertex = new_labeled_node(
            nodes, "ShaderNodeVertexColor", "Vertex Color", (-2200, 760)
        )
        centered = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY_ADD",
            uv,
            (2.0, 2.0, 1.0),
            name="Puddle UV -1 to 1",
            location=(-1980, 300),
        )
        shader_nodes.socket_by_identifier(
            centered.node.inputs, "Vector_002"
        ).default_value = (-1.0, -1.0, 0.0)
        details = param_float(data, "Details", 0.5)
        noise_uv = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            uv,
            scale=details,
            name="Puddle Noise UV",
            location=(-1980, 80),
        )
        noise = _texture(
            self,
            nodes,
            links,
            data,
            "NoiseTexture",
            (-1740, 80),
            noise_uv,
            non_color=True,
        )
        noise_value = (
            _red(nodes, links, noise.outputs["Color"], "Puddle Noise.r", (-1520, 80))
            if noise
            else 0.0
        )
        angle = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            noise_value,
            -math.pi * param_float(data, "Curls", 1.6),
            name="Puddle Curl Angle",
            location=(-1320, 80),
        )
        rotate = new_labeled_node(
            nodes, "ShaderNodeVectorRotate", "Puddle Curl Rotation", (-1540, 300)
        )
        rotate.rotation_type = "Z_AXIS"
        links.new(centered, find_input(rotate, "Vector"))
        links.new(angle, find_input(rotate, "Angle"))
        squashed = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY",
            rotate.outputs["Vector"],
            (1.0, param_float(data, "Squash", 1.4), 1.0),
            name="Puddle Squash",
            location=(-1300, 300),
        )
        radius_squared = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            squashed,
            squashed,
            name="Puddle Radius Squared",
            location=(-1080, 300),
        )
        distance = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            radius_squared,
            name="Puddle Distance",
            location=(-880, 300),
        )
        distance = shader_nodes.math(
            nodes,
            links,
            "MAXIMUM",
            distance,
            0.0,
            name="Puddle Distance Clamp",
            location=(-700, 300),
        )
        cutoff = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            vertex.outputs["Alpha"],
            name="Puddle Growth Cutoff",
            location=(-1080, 520),
        )
        cutoff_edge = shader_nodes.math(
            nodes,
            links,
            "ADD",
            cutoff,
            0.04,
            name="Puddle Cutoff Edge",
            location=(-880, 520),
        )
        shape_alpha = smoothstep_socket(
            tree,
            distance,
            cutoff,
            cutoff_edge,
            (-460, 380),
            "Puddle Shape Alpha",
        )

        color = mix_color_socket(
            nodes,
            links,
            "Puddle Color",
            param_color(data, "Color", (0.4, 0.05, 0.05, 1.0)),
            vertex.outputs["Color"],
            1.0,
            (-460, 720),
            blend_type="MULTIPLY",
        )
        links.new(color, find_input(principled, "Base Color"))
        color_alpha = param_color(data, "Color", (0.4, 0.05, 0.05, 1.0))[3]
        opacity_drop = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            vertex.outputs["Alpha"],
            param_float(data, "ProgressiveOpacity", 0.0),
            name="Progressive Puddle Opacity",
            location=(-260, 560),
        )
        center_opacity = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            color_alpha,
            opacity_drop,
            name="Puddle Center Opacity",
            location=(-60, 560),
            use_clamp=True,
        )
        opacity = mix_scalar_socket(
            nodes,
            links,
            "Puddle Progressive Opacity",
            (160, 560),
            color_alpha,
            center_opacity,
            distance,
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            shape_alpha,
            opacity,
            name="Puddle Surface Alpha",
            location=(380, 480),
        )
        links.new(alpha, find_input(principled, "Alpha"))
        find_input(principled, "Roughness").default_value = param_float(
            data, "Roughness", 0.110465
        )

        normal_edge = shader_nodes.math(
            nodes,
            links,
            "ADD",
            cutoff,
            1.0,
            name="Puddle Normal Cutoff",
            location=(-460, 40),
        )
        normal_z = smoothstep_socket(
            tree,
            distance,
            cutoff,
            normal_edge,
            (-240, 40),
            "Puddle Normal Height",
        )
        normal_z = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            normal_z,
            param_float(data, "Thickness", 150.0),
            name="Puddle Normal Thickness",
            location=(-40, 40),
        )
        vertex_alpha = vertex.outputs["Alpha"]
        normal_xy = shader_nodes.vector_math(
            nodes,
            links,
            "SCALE",
            centered,
            scale=vertex_alpha,
            name="Puddle Normal XY",
            location=(-240, -120),
        )
        split = new_labeled_node(
            nodes, "ShaderNodeSeparateXYZ", "Puddle Normal XY Components", (-40, -120)
        )
        links.new(normal_xy, split.inputs["Vector"])
        combine = new_labeled_node(
            nodes, "ShaderNodeCombineXYZ", "Puddle Tangent Normal", (180, -40)
        )
        links.new(split.outputs["X"], combine.inputs["X"])
        links.new(split.outputs["Y"], combine.inputs["Y"])
        links.new(normal_z, combine.inputs["Z"])
        tangent = shader_nodes.vector_math(
            nodes,
            links,
            "NORMALIZE",
            combine.outputs["Vector"],
            name="Puddle Normalized Tangent",
            location=(380, -40),
        )
        normal = directx_tangent_to_normal_map(
            tree,
            tangent,
            location=(580, -40),
            label="Puddle Normal",
        )
        links.new(normal, find_input(principled, "Normal"))
        _set_transparent(Mat)


class SimpleEmissiveDecal(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree, _, principled = _new_graph(Mat, "Simple Emissive Decal")
        nodes, links = tree.nodes, tree.links
        uv = new_labeled_node(nodes, "ShaderNodeUVMap", "UV", (-1800, 260)).outputs[
            "UV"
        ]
        flipped = shader_nodes.vector_math(
            nodes,
            links,
            "MULTIPLY_ADD",
            uv,
            (-1.0, -1.0, 1.0),
            name="Simple Emissive UV Flip",
            location=(-1560, 260),
        )
        shader_nodes.socket_by_identifier(
            flipped.node.inputs, "Vector_002"
        ).default_value = (1.0, 0.0, 0.0)
        uv = _subuv(
            nodes,
            flipped,
            param_float(data, "FrameNum", 0.0),
            param_float(data, "SubUVWidth", 1.0),
            param_float(data, "SubUVHeight", 1.0),
            (-1320, 260),
            "Simple Emissive SubUV",
        )
        texture = _texture(self, nodes, links, data, "Diffuse", (-1000, 420), uv)
        sampled = (
            texture.outputs["Color"]
            if texture
            else rgb_socket(
                nodes, "Diffuse Fallback", (0.0, 0.0, 0.0, 0.0), (-780, 420)
            )
        )
        gray = _red(nodes, links, sampled, "Simple Emissive Diffuse.r", (-760, 560))
        combine = new_labeled_node(
            nodes, "ShaderNodeCombineColor", "Simple Emissive Grayscale", (-540, 560)
        )
        combine.mode = "RGB"
        for socket in ("Red", "Green", "Blue"):
            links.new(gray, combine.inputs[socket])
        color = mix_color_socket(
            nodes,
            links,
            "Simple Emissive Tint",
            combine.outputs["Color"],
            param_color(data, "EmissiveColor", (1.0, 1.0, 1.0, 1.0)),
            1.0,
            (-300, 560),
            blend_type="MULTIPLY",
        )
        color = mix_color_socket(
            nodes,
            links,
            "Simple Emissive ColorMultiply",
            color,
            (param_float(data, "ColorMultiply", 1.0),) * 3 + (1.0,),
            1.0,
            (-60, 560),
            blend_type="MULTIPLY",
        )
        vertex = new_labeled_node(
            nodes, "ShaderNodeVertexColor", "Vertex Color", (-540, 800)
        )
        color = mix_color_socket(
            nodes,
            links,
            "Simple Emissive Vertex Color",
            color,
            vertex.outputs["Color"],
            1.0,
            (180, 560),
            blend_type="MULTIPLY",
        )
        links.new(color, find_input(principled, "Base Color"))
        links.new(color, find_input(principled, "Emission Color", "Emission"))
        find_input(principled, "Emission Strength").default_value = 1.0
        texture_alpha = texture.outputs.get("Alpha") if texture else 0.0
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            texture_alpha,
            param_color(data, "EmissiveColor", (1.0, 1.0, 1.0, 1.0))[3],
            name="Simple Emissive Texture Alpha",
            location=(180, 300),
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            alpha,
            param_float(data, "ColorMultiply", 1.0),
            name="Simple Emissive ColorMultiply Alpha",
            location=(300, 220),
        )
        alpha = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            alpha,
            vertex.outputs["Alpha"],
            name="Simple Emissive Vertex Alpha",
            location=(400, 300),
        )
        links.new(alpha, find_input(principled, "Alpha"))
        _set_transparent(Mat)
