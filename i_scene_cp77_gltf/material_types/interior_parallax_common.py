from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .graph import cp77_bitangent_socket, cp77_uv_tangent_node, mix_color_socket
from .mat_common import MaterialTypeBase, param_float, param_vector
from .parallax_math import tangent_view_vector

_ATLAS_DEPTHS = (0.5, 0.333, 0.25, 0.195)
_EPSILON = 1.0e-4


def atlas_depth(data, default=1.0):
    index = int(param_float(data, "AtlasDepth", default)) - 1
    return _ATLAS_DEPTHS[max(0, min(len(_ATLAS_DEPTHS) - 1, index))]


def _depth_scale(depth):
    depth = max(_EPSILON, min(0.999, float(depth)))
    return 1.0 / (1.0 - depth) - 1.0


def effective_room_depth(data, depth, room_depth_default=1.0):
    scale = _depth_scale(depth) / max(
        _EPSILON, param_float(data, "roomDepth", room_depth_default)
    )
    return scale / (1.0 + scale)


class InteriorParallaxCore(MaterialTypeBase):
    atlas_depth_default = 1.0
    room_width_default = 1.0
    room_height_default = 1.0
    room_depth_default = 1.0
    position_x_default = 0.0
    position_y_default = 0.0

    def _tangent_position(self, tree, *, location=(-2480, 420)):
        geometry = create_node(
            tree.nodes,
            "ShaderNodeNewGeometry",
            location,
            label="Interior Surface Position",
        )
        tangent = cp77_uv_tangent_node(
            tree.nodes, (location[0], location[1] - 180), label="Interior Tangent"
        )

        position = create_node(
            tree.nodes,
            "ShaderNodeVectorTransform",
            (location[0] + 180, location[1] + 20),
            label="Position Object Space",
        )
        position.vector_type = "POINT"
        position.convert_from = "WORLD"
        position.convert_to = "OBJECT"
        tree.links.new(geometry.outputs["Position"], position.inputs["Vector"])

        tangent_obj = create_node(
            tree.nodes,
            "ShaderNodeVectorTransform",
            (location[0] + 180, location[1] - 140),
            label="Tangent Object Space",
        )
        tangent_obj.vector_type = "VECTOR"
        tangent_obj.convert_from = "WORLD"
        tangent_obj.convert_to = "OBJECT"
        tree.links.new(tangent.outputs["Tangent"], tangent_obj.inputs["Vector"])

        normal_obj = create_node(
            tree.nodes,
            "ShaderNodeVectorTransform",
            (location[0] + 180, location[1] - 300),
            label="Normal Object Space",
        )
        normal_obj.vector_type = "NORMAL"
        normal_obj.convert_from = "WORLD"
        normal_obj.convert_to = "OBJECT"
        tree.links.new(geometry.outputs["Normal"], normal_obj.inputs["Vector"])

        bitangent = cp77_bitangent_socket(
            tree.nodes,
            tree.links,
            normal_obj.outputs["Vector"],
            tangent_obj.outputs["Vector"],
            (location[0] + 380, location[1] - 220),
            label="Object Bitangent",
        )

        dot_x = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "DOT_PRODUCT",
            label="tanPos.x",
            location=(location[0] + 580, location[1]),
            hide=True,
        ).node
        dot_y = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "DOT_PRODUCT",
            label="tanPos.y",
            location=(location[0] + 580, location[1] - 140),
            hide=True,
        ).node
        tree.links.new(position.outputs["Vector"], dot_x.inputs["Vector"])
        tree.links.new(
            tangent_obj.outputs["Vector"],
            shader_nodes.socket_by_identifier(dot_x.inputs, "Vector_001"),
        )
        tree.links.new(position.outputs["Vector"], dot_y.inputs["Vector"])
        tree.links.new(
            bitangent, shader_nodes.socket_by_identifier(dot_y.inputs, "Vector_001")
        )

        combine = create_node(
            tree.nodes,
            "ShaderNodeCombineXYZ",
            (location[0] + 780, location[1] - 60),
            label="Tangent Surface Position",
        )
        tree.links.new(dot_x.outputs["Value"], combine.inputs["X"])
        tree.links.new(dot_y.outputs["Value"], combine.inputs["Y"])
        return combine.outputs["Vector"]

    def _room_grid(self, tree, data, *, tangent_position=False, location=(-2200, 500)):
        width = max(_EPSILON, param_float(data, "roomWidth", self.room_width_default))
        height = max(
            _EPSILON, param_float(data, "roomHeight", self.room_height_default)
        )
        if tangent_position:
            source = self._tangent_position(
                tree, location=(location[0] - 400, location[1])
            )
        else:
            coord = create_node(
                tree.nodes, "ShaderNodeTexCoord", location, label="Room UV"
            )
            source = coord.outputs["UV"]

        divisor = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            label="Room Width / Height",
            location=(location[0] + 180, location[1]),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            divisor.inputs, "Vector_001"
        ).default_value = (width, height, 1.0)
        tree.links.new(source, divisor.inputs["Vector"])
        offset = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ADD",
            label="Room Position Offset",
            location=(location[0] + 360, location[1]),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(offset.inputs, "Vector_001").default_value = (
            param_float(data, "positionXoffset", self.position_x_default),
            param_float(data, "positionYoffset", self.position_y_default),
            0.0,
        )
        tree.links.new(divisor.outputs["Vector"], offset.inputs["Vector"])
        fraction = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "FRACTION",
            label="frac(Room Grid)",
            location=(location[0] + 540, location[1]),
            hide=True,
        ).node
        tree.links.new(offset.outputs["Vector"], fraction.inputs["Vector"])
        return fraction.outputs["Vector"], offset.outputs["Vector"]

    def _interior_uv(
        self,
        tree,
        room_uv,
        data,
        depth,
        *,
        label,
        location=(-1500, 500),
        plane="room",
        return_hit=False,
    ):
        width = max(_EPSILON, param_float(data, "roomWidth", self.room_width_default))
        height = max(
            _EPSILON, param_float(data, "roomHeight", self.room_height_default)
        )
        source_depth = (
            effective_room_depth(data, depth, self.room_depth_default)
            if plane == "room"
            else max(_EPSILON, min(0.999, float(depth)))
        )
        depth_scale = _depth_scale(source_depth)

        view = tangent_view_vector(
            tree,
            location=(location[0] - 980, location[1] - 520),
            label=f"{label} Tangent View",
            flip_y=False,
        )
        split_view = create_node(
            tree.nodes,
            "ShaderNodeSeparateXYZ",
            (location[0] - 760, location[1] - 420),
            label=f"{label} View Components",
        )
        tree.links.new(view, split_view.inputs["Vector"])
        vx = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            None,
            width,
            label=f"{label} View X / roomWidth",
            location=(location[0] - 580, location[1] - 340),
            hide=True,
        ).node
        vy = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            None,
            height,
            label=f"{label} View Y / roomHeight",
            location=(location[0] - 580, location[1] - 440),
            hide=True,
        ).node
        vz = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            -depth_scale,
            label=f"{label} View Z Depth",
            location=(location[0] - 580, location[1] - 540),
            hide=True,
        ).node
        tree.links.new(split_view.outputs["X"], vx.inputs["Value"])
        tree.links.new(split_view.outputs["Y"], vy.inputs["Value"])
        tree.links.new(split_view.outputs["Z"], vz.inputs["Value"])
        eye = create_node(
            tree.nodes,
            "ShaderNodeCombineXYZ",
            (location[0] - 380, location[1] - 440),
            label=f"{label} eyeVector",
        )
        tree.links.new(vx.outputs["Value"], eye.inputs["X"])
        tree.links.new(vy.outputs["Value"], eye.inputs["Y"])
        tree.links.new(vz.outputs["Value"], eye.inputs["Z"])

        split_uv = create_node(
            tree.nodes,
            "ShaderNodeSeparateXYZ",
            (location[0] - 760, location[1] - 80),
            label=f"{label} roomUV",
        )
        tree.links.new(room_uv, split_uv.inputs["Vector"])
        px = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            label=f"{label} roomPos.x",
            location=(location[0] - 580, location[1]),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(px.inputs, "Value_001").default_value = 2.0
        shader_nodes.socket_by_identifier(px.inputs, "Value_002").default_value = -1.0
        py = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            label=f"{label} roomPos.y",
            location=(location[0] - 580, location[1] - 100),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(py.inputs, "Value_001").default_value = 2.0
        shader_nodes.socket_by_identifier(py.inputs, "Value_002").default_value = -1.0
        tree.links.new(split_uv.outputs["X"], px.inputs["Value"])
        tree.links.new(split_uv.outputs["Y"], py.inputs["Value"])
        room_pos = create_node(
            tree.nodes,
            "ShaderNodeCombineXYZ",
            (location[0] - 380, location[1] - 40),
            label=f"{label} roomPos",
        )
        room_pos.inputs["Z"].default_value = -1.0
        tree.links.new(px.outputs["Value"], room_pos.inputs["X"])
        tree.links.new(py.outputs["Value"], room_pos.inputs["Y"])

        inv = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            label=f"{label} 1 / eyeVector",
            location=(location[0] - 180, location[1] - 300),
            hide=True,
        ).node
        inv.inputs["Vector"].default_value = (1.0, 1.0, 1.0)
        tree.links.new(
            eye.outputs["Vector"],
            shader_nodes.socket_by_identifier(inv.inputs, "Vector_001"),
        )
        abs_inv = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ABSOLUTE",
            label=f"{label} abs(id)",
            location=(location[0], location[1] - 300),
            hide=True,
        ).node
        tree.links.new(inv.outputs["Vector"], abs_inv.inputs["Vector"])
        pos_inv = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label=f"{label} roomPos * id",
            location=(location[0], location[1] - 120),
            hide=True,
        ).node
        tree.links.new(room_pos.outputs["Vector"], pos_inv.inputs["Vector"])
        tree.links.new(
            inv.outputs["Vector"],
            shader_nodes.socket_by_identifier(pos_inv.inputs, "Vector_001"),
        )
        k = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label=f"{label} k",
            location=(location[0] + 180, location[1] - 220),
            hide=True,
        ).node
        tree.links.new(abs_inv.outputs["Vector"], k.inputs["Vector"])
        tree.links.new(
            pos_inv.outputs["Vector"],
            shader_nodes.socket_by_identifier(k.inputs, "Vector_001"),
        )
        split_k = create_node(
            tree.nodes,
            "ShaderNodeSeparateXYZ",
            (location[0] + 360, location[1] - 220),
            label=f"{label} k components",
        )
        tree.links.new(k.outputs["Vector"], split_k.inputs["Vector"])

        if plane == "room":
            kxy = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MINIMUM",
                label=f"{label} min(k.x,k.y)",
                location=(location[0] + 540, location[1] - 200),
                hide=True,
            ).node
            tree.links.new(split_k.outputs["X"], kxy.inputs["Value"])
            tree.links.new(
                split_k.outputs["Y"],
                shader_nodes.socket_by_identifier(kxy.inputs, "Value_001"),
            )
            distance = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MINIMUM",
                label=f"{label} min(k.xy,k.z)",
                location=(location[0] + 700, location[1] - 200),
                hide=True,
            ).node
            tree.links.new(kxy.outputs["Value"], distance.inputs["Value"])
            tree.links.new(
                split_k.outputs["Z"],
                shader_nodes.socket_by_identifier(distance.inputs, "Value_001"),
            )
            distance_socket = distance.outputs["Value"]
        else:
            distance_socket = split_k.outputs["Z"]

        travel = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            label=f"{label} Ray Travel",
            location=(location[0] + 540, location[1] - 20),
            hide=True,
        ).node
        tree.links.new(eye.outputs["Vector"], travel.inputs["Vector"])
        tree.links.new(distance_socket, travel.inputs["Scale"])
        hit = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ADD",
            label=f"{label} Hit Position",
            location=(location[0] + 720, location[1]),
            hide=True,
        ).node
        tree.links.new(room_pos.outputs["Vector"], hit.inputs["Vector"])
        tree.links.new(
            travel.outputs["Vector"],
            shader_nodes.socket_by_identifier(hit.inputs, "Vector_001"),
        )

        if plane == "curtain":
            cover_shift = -(
                (1.0 - max(0.0, min(1.0, param_float(data, "CurtainMaxCover", 0.4))))
                * 2.0
            )
            shift = shader_nodes.vector_math(
                tree.nodes,
                tree.links,
                "ADD",
                label="Curtain Cover Offset",
                location=(location[0] + 900, location[1]),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                shift.inputs, "Vector_001"
            ).default_value = (0.0, cover_shift, 0.0)
            tree.links.new(hit.outputs["Vector"], shift.inputs["Vector"])
            hit_socket = shift.outputs["Vector"]
        else:
            hit_socket = hit.outputs["Vector"]

        split_hit = create_node(
            tree.nodes,
            "ShaderNodeSeparateXYZ",
            (location[0] + 900, location[1] - 180),
            label=f"{label} Hit Components",
        )
        tree.links.new(hit_socket, split_hit.inputs["Vector"])
        interp = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            label=f"{label} Depth Interp",
            location=(location[0] + 1080, location[1] - 180),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            interp.inputs, "Value_001"
        ).default_value = 0.5
        shader_nodes.socket_by_identifier(
            interp.inputs, "Value_002"
        ).default_value = 0.5
        tree.links.new(split_hit.outputs["Z"], interp.inputs["Value"])
        clamp = create_node(
            tree.nodes,
            "ShaderNodeClamp",
            (location[0] + 1240, location[1] - 180),
            label=f"{label} saturate(Interp)",
        )
        tree.links.new(interp.outputs["Value"], clamp.inputs["Value"])
        real_z = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            None,
            depth_scale,
            label=f"{label} Real Z",
            location=(location[0] + 1400, location[1] - 180),
            hide=True,
        ).node
        tree.links.new(clamp.outputs["Result"], real_z.inputs["Value"])
        real_z_add = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            None,
            1.0,
            label=f"{label} Real Z + 1",
            location=(location[0] + 1560, location[1] - 180),
            hide=True,
        ).node
        tree.links.new(real_z.outputs["Value"], real_z_add.inputs["Value"])
        reciprocal = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            label=f"{label} 1 / Real Z",
            location=(location[0] + 1720, location[1] - 180),
            hide=True,
        ).node
        reciprocal.inputs["Value"].default_value = 1.0
        tree.links.new(
            real_z_add.outputs["Value"],
            shader_nodes.socket_by_identifier(reciprocal.inputs, "Value_001"),
        )
        corrected = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label=f"{label} Perspective Interp",
            location=(location[0] + 1880, location[1] - 180),
            hide=True,
        ).node
        corrected.inputs["Value"].default_value = 1.0
        tree.links.new(
            reciprocal.outputs["Value"],
            shader_nodes.socket_by_identifier(corrected.inputs, "Value_001"),
        )
        corrected_scale = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            depth_scale + 1.0,
            label=f"{label} Perspective Interp Scale",
            location=(location[0] + 2040, location[1] - 180),
            hide=True,
        ).node
        tree.links.new(corrected.outputs["Value"], corrected_scale.inputs["Value"])
        interp_socket = corrected_scale.outputs["Value"]

        if plane == "room":
            ratio = param_vector(data, "AtlasGridUvRatio", (1.0, 1.0, 1.0, 1.0))
            max_size = max(_EPSILON, float(ratio[2]), float(ratio[3]))
            target = max_size / (max_size + (1.0 / depth_scale))
            factor = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY_ADD",
                label=f"{label} Perspective XY",
                location=(location[0] + 2040, location[1] + 20),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                factor.inputs, "Value_001"
            ).default_value = target - 1.0
            shader_nodes.socket_by_identifier(
                factor.inputs, "Value_002"
            ).default_value = 1.0
            tree.links.new(interp_socket, factor.inputs["Value"])
        else:
            factor = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY_ADD",
                label=f"{label} Plane Perspective XY",
                location=(location[0] + 2040, location[1] + 20),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                factor.inputs, "Value_001"
            ).default_value = 1.0 - source_depth
            shader_nodes.socket_by_identifier(
                factor.inputs, "Value_002"
            ).default_value = source_depth
            tree.links.new(interp_socket, factor.inputs["Value"])

        uv_x = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label=f"{label} UV X",
            location=(location[0] + 2200, location[1] + 80),
            hide=True,
        ).node
        uv_y = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label=f"{label} UV Y",
            location=(location[0] + 2200, location[1] - 20),
            hide=True,
        ).node
        tree.links.new(split_hit.outputs["X"], uv_x.inputs["Value"])
        tree.links.new(
            factor.outputs["Value"],
            shader_nodes.socket_by_identifier(uv_x.inputs, "Value_001"),
        )
        tree.links.new(split_hit.outputs["Y"], uv_y.inputs["Value"])
        tree.links.new(
            factor.outputs["Value"],
            shader_nodes.socket_by_identifier(uv_y.inputs, "Value_001"),
        )
        uv_x_half = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            label=f"{label} UV X 0..1",
            location=(location[0] + 2360, location[1] + 80),
            hide=True,
        ).node
        uv_y_half = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            label=f"{label} UV Y 0..1",
            location=(location[0] + 2360, location[1] - 20),
            hide=True,
        ).node
        for node in (uv_x_half, uv_y_half):
            shader_nodes.socket_by_identifier(
                node.inputs, "Value_001"
            ).default_value = 0.5
            shader_nodes.socket_by_identifier(
                node.inputs, "Value_002"
            ).default_value = 0.5
        tree.links.new(uv_x.outputs["Value"], uv_x_half.inputs["Value"])
        tree.links.new(uv_y.outputs["Value"], uv_y_half.inputs["Value"])
        uv_out = create_node(
            tree.nodes,
            "ShaderNodeCombineXYZ",
            (location[0] + 2520, location[1] + 20),
            label=f"{label} UV",
        )
        tree.links.new(uv_x_half.outputs["Value"], uv_out.inputs["X"])
        tree.links.new(uv_y_half.outputs["Value"], uv_out.inputs["Y"])

        mask = None
        if plane == "layer":
            sx = shader_nodes.math(
                tree.nodes,
                tree.links,
                "LESS_THAN",
                label=f"{label} k.z <= k.x",
                location=(location[0] + 720, location[1] - 380),
                hide=True,
            ).node
            sy = shader_nodes.math(
                tree.nodes,
                tree.links,
                "LESS_THAN",
                label=f"{label} k.z <= k.y",
                location=(location[0] + 720, location[1] - 460),
                hide=True,
            ).node
            tree.links.new(split_k.outputs["Z"], sx.inputs["Value"])
            tree.links.new(
                split_k.outputs["X"],
                shader_nodes.socket_by_identifier(sx.inputs, "Value_001"),
            )
            tree.links.new(split_k.outputs["Z"], sy.inputs["Value"])
            tree.links.new(
                split_k.outputs["Y"],
                shader_nodes.socket_by_identifier(sy.inputs, "Value_001"),
            )
            mask_node = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label=f"{label} Layer Mask",
                location=(location[0] + 900, location[1] - 420),
                hide=True,
            ).node
            tree.links.new(sx.outputs["Value"], mask_node.inputs["Value"])
            tree.links.new(
                sy.outputs["Value"],
                shader_nodes.socket_by_identifier(mask_node.inputs, "Value_001"),
            )
            mask = mask_node.outputs["Value"]
        elif plane == "curtain":
            y01 = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY_ADD",
                label=f"{label} Curtain Y",
                location=(location[0] + 1080, location[1] - 380),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                y01.inputs, "Value_001"
            ).default_value = 0.5
            shader_nodes.socket_by_identifier(
                y01.inputs, "Value_002"
            ).default_value = 0.5
            tree.links.new(split_hit.outputs["Y"], y01.inputs["Value"])
            ymask = shader_nodes.math(
                tree.nodes,
                tree.links,
                "GREATER_THAN",
                None,
                0.01,
                label=f"{label} Curtain Y Mask",
                location=(location[0] + 1240, location[1] - 380),
                hide=True,
            ).node
            tree.links.new(y01.outputs["Value"], ymask.inputs["Value"])
            xmask = shader_nodes.math(
                tree.nodes,
                tree.links,
                "LESS_THAN",
                label=f"{label} Curtain X Mask",
                location=(location[0] + 1240, location[1] - 460),
                hide=True,
            ).node
            tree.links.new(split_k.outputs["Z"], xmask.inputs["Value"])
            tree.links.new(
                split_k.outputs["X"],
                shader_nodes.socket_by_identifier(xmask.inputs, "Value_001"),
            )
            mask_node = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label=f"{label} Curtain Mask",
                location=(location[0] + 1400, location[1] - 420),
                hide=True,
            ).node
            tree.links.new(ymask.outputs["Value"], mask_node.inputs["Value"])
            tree.links.new(
                xmask.outputs["Value"],
                shader_nodes.socket_by_identifier(mask_node.inputs, "Value_001"),
            )
            mask = mask_node.outputs["Value"]
        if return_hit:
            return uv_out.outputs["Vector"], mask, interp_socket, split_hit
        return uv_out.outputs["Vector"], mask, interp_socket

    def _atlas_uv(
        self,
        tree,
        interior_uv,
        grid_uv,
        data,
        *,
        location=(-1180, 500),
        label="Atlas UV",
        flip_x=False,
    ):
        ratio = param_vector(data, "AtlasGridUvRatio", (1.0, 1.0, 1.0, 1.0))
        columns = max(1, int(ratio[1]))
        rows = max(1, int(ratio[0]))
        if columns == 1 and rows == 1:
            return interior_uv, None

        floor_cell = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "FLOOR",
            label="Room Cell",
            location=(location[0] - 360, location[1] - 160),
            hide=True,
        ).node
        tree.links.new(grid_uv, floor_cell.inputs["Vector"])
        noise = create_node(
            tree.nodes,
            "ShaderNodeTexWhiteNoise",
            (location[0] - 180, location[1] - 160),
            label="Room Selection",
        )
        noise.noise_dimensions = "2D"
        tree.links.new(floor_cell.outputs["Vector"], noise.inputs["Vector"])
        split_random = create_node(
            tree.nodes,
            "ShaderNodeSeparateColor",
            (location[0], location[1] - 160),
            label="Room Random",
        )
        tree.links.new(noise.outputs["Color"], split_random.inputs["Color"])

        atlas_input_uv = interior_uv
        if flip_x:
            split_uv = create_node(
                tree.nodes,
                "ShaderNodeSeparateXYZ",
                (location[0] - 20, location[1] + 120),
                label=f"{label} Interior UV",
            )
            tree.links.new(interior_uv, split_uv.inputs["Vector"])
            random_100 = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                None,
                100.0,
                label=f"{label} Flip Random x100",
                location=(location[0] + 140, location[1] + 100),
                hide=True,
            ).node
            tree.links.new(split_random.outputs["Blue"], random_100.inputs["Value"])
            random_frac = shader_nodes.math(
                tree.nodes,
                tree.links,
                "FRACT",
                label=f"{label} Flip Random frac",
                location=(location[0] + 300, location[1] + 100),
                hide=True,
            ).node
            tree.links.new(random_100.outputs["Value"], random_frac.inputs["Value"])
            flip = shader_nodes.math(
                tree.nodes,
                tree.links,
                "GREATER_THAN",
                None,
                0.5,
                label=f"{label} Flip X",
                location=(location[0] + 460, location[1] + 100),
                hide=True,
            ).node
            tree.links.new(random_frac.outputs["Value"], flip.inputs["Value"])
            one_minus_x = shader_nodes.math(
                tree.nodes,
                tree.links,
                "SUBTRACT",
                label=f"{label} 1-X",
                location=(location[0] + 140, location[1] + 200),
                hide=True,
            ).node
            one_minus_x.inputs["Value"].default_value = 1.0
            tree.links.new(
                split_uv.outputs["X"],
                shader_nodes.socket_by_identifier(one_minus_x.inputs, "Value_001"),
            )
            x_delta = shader_nodes.math(
                tree.nodes,
                tree.links,
                "SUBTRACT",
                label=f"{label} Flipped-X Delta",
                location=(location[0] + 300, location[1] + 200),
                hide=True,
            ).node
            tree.links.new(one_minus_x.outputs["Value"], x_delta.inputs["Value"])
            tree.links.new(
                split_uv.outputs["X"],
                shader_nodes.socket_by_identifier(x_delta.inputs, "Value_001"),
            )
            x_flip_delta = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label=f"{label} X Flip Delta",
                location=(location[0] + 460, location[1] + 200),
                hide=True,
            ).node
            tree.links.new(x_delta.outputs["Value"], x_flip_delta.inputs["Value"])
            tree.links.new(
                flip.outputs["Value"],
                shader_nodes.socket_by_identifier(x_flip_delta.inputs, "Value_001"),
            )
            x_final = shader_nodes.math(
                tree.nodes,
                tree.links,
                "ADD",
                label=f"{label} Flipped X",
                location=(location[0] + 620, location[1] + 200),
                hide=True,
            ).node
            tree.links.new(split_uv.outputs["X"], x_final.inputs["Value"])
            tree.links.new(
                x_flip_delta.outputs["Value"],
                shader_nodes.socket_by_identifier(x_final.inputs, "Value_001"),
            )
            flipped_uv = create_node(
                tree.nodes,
                "ShaderNodeCombineXYZ",
                (location[0] + 780, location[1] + 160),
                label=f"{label} Source Flip",
            )
            tree.links.new(x_final.outputs["Value"], flipped_uv.inputs["X"])
            tree.links.new(split_uv.outputs["Y"], flipped_uv.inputs["Y"])
            tree.links.new(split_uv.outputs["Z"], flipped_uv.inputs["Z"])
            atlas_input_uv = flipped_uv.outputs["Vector"]

        col_mul = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            columns,
            label="Atlas Column",
            location=(location[0] + 160, location[1] - 120),
            hide=True,
        ).node
        tree.links.new(split_random.outputs["Red"], col_mul.inputs["Value"])
        col_floor = shader_nodes.math(
            tree.nodes,
            tree.links,
            "FLOOR",
            label="floor(Column)",
            location=(location[0] + 320, location[1] - 120),
            hide=True,
        ).node
        tree.links.new(col_mul.outputs["Value"], col_floor.inputs["Value"])
        row_mul = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            rows,
            label="Atlas Row",
            location=(location[0] + 160, location[1] - 220),
            hide=True,
        ).node
        tree.links.new(split_random.outputs["Green"], row_mul.inputs["Value"])
        row_floor = shader_nodes.math(
            tree.nodes,
            tree.links,
            "FLOOR",
            label="floor(Row)",
            location=(location[0] + 320, location[1] - 220),
            hide=True,
        ).node
        tree.links.new(row_mul.outputs["Value"], row_floor.inputs["Value"])

        scale = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Atlas Cell Scale",
            location=(location[0], location[1]),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(scale.inputs, "Vector_001").default_value = (
            1.0 / columns,
            1.0 / rows,
            1.0,
        )
        tree.links.new(atlas_input_uv, scale.inputs["Vector"])
        offset = create_node(
            tree.nodes,
            "ShaderNodeCombineXYZ",
            (location[0] + 500, location[1] - 160),
            label="Atlas Cell Offset",
        )
        col_uv = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            None,
            columns,
            label="Atlas Column UV",
            location=(location[0] + 460, location[1] - 100),
            hide=True,
        ).node
        row_uv = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            None,
            rows,
            label="Atlas Row UV",
            location=(location[0] + 460, location[1] - 240),
            hide=True,
        ).node
        tree.links.new(col_floor.outputs["Value"], col_uv.inputs["Value"])
        tree.links.new(row_floor.outputs["Value"], row_uv.inputs["Value"])
        tree.links.new(col_uv.outputs["Value"], offset.inputs["X"])
        tree.links.new(row_uv.outputs["Value"], offset.inputs["Y"])
        result = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ADD",
            label=label,
            location=(location[0] + 680, location[1]),
            hide=True,
        ).node
        tree.links.new(scale.outputs["Vector"], result.inputs["Vector"])
        tree.links.new(
            offset.outputs["Vector"],
            shader_nodes.socket_by_identifier(result.inputs, "Vector_001"),
        )
        return result.outputs["Vector"], split_random.outputs["Blue"]

    def _texture(
        self, tree, data, key, uv, location, *, non_color=False, extension="REPEAT"
    ):
        path = self._texture_path(data, key)
        if not path:
            return None
        image = self._load_relative_image(path, non_color=non_color, error_label=key)
        if image is None:
            return None
        node = create_node(
            tree.nodes, "ShaderNodeTexImage", location, label=key, image=image
        )
        node.extension = extension
        if uv is not None:
            tree.links.new(uv, node.inputs["Vector"])
        return node

    def _night_lit_color(
        self,
        tree,
        color_socket,
        alpha_socket,
        night_factor,
        *,
        location,
        label,
        alpha_power=1.0,
        lighting_scale=1.0,
    ):
        alpha = alpha_socket
        if alpha_power != 1.0:
            powered = shader_nodes.math(
                tree.nodes,
                tree.links,
                "POWER",
                None,
                alpha_power,
                label=f"{label} Alpha^{alpha_power:g}",
                location=location,
                hide=True,
            ).node
            tree.links.new(alpha_socket, powered.inputs["Value"])
            alpha = powered.outputs["Value"]
        if abs(float(lighting_scale) - 1.0) > 1.0e-6:
            scaled_alpha = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                None,
                lighting_scale,
                label=f"{label} Lighting Scale",
                location=(location[0] + 20, location[1] - 120),
                hide=True,
            ).node
            tree.links.new(alpha, scaled_alpha.inputs["Value"])
            alpha = scaled_alpha.outputs["Value"]
        alpha_rgb = create_node(
            tree.nodes,
            "ShaderNodeCombineXYZ",
            (location[0], location[1] - 110),
            label=f"{label} Lighting.xxx",
        )
        for socket in ("X", "Y", "Z"):
            tree.links.new(alpha, alpha_rgb.inputs[socket])
        lit = mix_color_socket(
            tree.nodes,
            tree.links,
            f"{label} Lit",
            color_socket,
            alpha_rgb.outputs["Vector"],
            1.0,
            (location[0] + 180, location[1]),
            blend_type="MULTIPLY",
            clamp=False,
        )
        mixed = mix_color_socket(
            tree.nodes,
            tree.links,
            f"{label} Day / Night",
            color_socket,
            lit,
            night_factor,
            (location[0] + 360, location[1]),
        )
        return mixed, alpha

    def _window_emission_strength(
        self,
        tree,
        data,
        *,
        room_alpha,
        room_hit_y,
        room_interp,
        curtain_alpha,
        curtain_mask,
        overlay,
        time_of_day,
        turned_on,
        emissive_ev_default,
        location=(700, -760),
    ):
        interior_sq = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Interior Alpha²",
            location=location,
            hide=True,
        ).node
        tree.links.new(room_alpha, interior_sq.inputs["Value"])
        tree.links.new(
            room_alpha,
            shader_nodes.socket_by_identifier(interior_sq.inputs, "Value_001"),
        )
        interior_lighting = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            1.5,
            label="Interior Lighting",
            location=(location[0] + 160, location[1]),
            hide=True,
        ).node
        tree.links.new(interior_sq.outputs["Value"], interior_lighting.inputs["Value"])

        curtain_product = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Curtain Alpha x Mask",
            location=(location[0], location[1] - 140),
            hide=True,
        ).node
        tree.links.new(curtain_alpha, curtain_product.inputs["Value"])
        if curtain_mask is not None:
            tree.links.new(
                curtain_mask,
                shader_nodes.socket_by_identifier(curtain_product.inputs, "Value_001"),
            )
        else:
            shader_nodes.socket_by_identifier(
                curtain_product.inputs, "Value_001"
            ).default_value = 1.0
        cutout_base = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            None,
            max(0.0, min(1.0, 1.0 - param_float(data, "CurtainAlpha", 0.899999976))),
            label="Curtain Cutout Base",
            location=(location[0] + 160, location[1] - 140),
            hide=True,
        ).node
        tree.links.new(curtain_product.outputs["Value"], cutout_base.inputs["Value"])
        cutout = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label="Curtain Mask Cutout",
            location=(location[0] + 320, location[1] - 140),
            hide=True,
        ).node
        cutout.inputs["Value"].default_value = 1.0
        tree.links.new(
            cutout_base.outputs["Value"],
            shader_nodes.socket_by_identifier(cutout.inputs, "Value_001"),
        )
        cutout.use_clamp = True

        day_term = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Night Interior Lighting",
            location=(location[0] + 320, location[1]),
            hide=True,
        ).node
        tree.links.new(time_of_day, day_term.inputs["Value"])
        tree.links.new(
            interior_lighting.outputs["Value"],
            shader_nodes.socket_by_identifier(day_term.inputs, "Value_001"),
        )
        inv_time = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label="1 - TimeOfDay",
            location=(location[0], location[1] - 280),
            hide=True,
        ).node
        inv_time.inputs["Value"].default_value = 1.0
        tree.links.new(
            time_of_day, shader_nodes.socket_by_identifier(inv_time.inputs, "Value_001")
        )
        alpha6 = shader_nodes.math(
            tree.nodes,
            tree.links,
            "POWER",
            None,
            6.0,
            label="Interior Alpha^6",
            location=(location[0] + 160, location[1] - 280),
            hide=True,
        ).node
        tree.links.new(room_alpha, alpha6.inputs["Value"])
        y4 = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            label="Room Y x4 -3",
            location=(location[0] + 160, location[1] - 380),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(y4.inputs, "Value_001").default_value = 4.0
        shader_nodes.socket_by_identifier(y4.inputs, "Value_002").default_value = -3.0
        y4.use_clamp = True
        tree.links.new(room_hit_y, y4.inputs["Value"])
        ypow = shader_nodes.math(
            tree.nodes,
            tree.links,
            "POWER",
            None,
            2.2,
            label="Room Y Gate^2.2",
            location=(location[0] + 320, location[1] - 380),
            hide=True,
        ).node
        tree.links.new(y4.outputs["Value"], ypow.inputs["Value"])
        day_alpha = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Day Alpha Lighting",
            location=(location[0] + 320, location[1] - 280),
            hide=True,
        ).node
        tree.links.new(alpha6.outputs["Value"], day_alpha.inputs["Value"])
        shader_nodes.socket_by_identifier(
            day_alpha.inputs, "Value_001"
        ).default_value = 4.0
        day_y = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Day Room Y Lighting",
            location=(location[0] + 480, location[1] - 280),
            hide=True,
        ).node
        tree.links.new(day_alpha.outputs["Value"], day_y.inputs["Value"])
        tree.links.new(
            ypow.outputs["Value"],
            shader_nodes.socket_by_identifier(day_y.inputs, "Value_001"),
        )
        day_weighted = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Day Weighted",
            location=(location[0] + 640, location[1] - 280),
            hide=True,
        ).node
        tree.links.new(inv_time.outputs["Value"], day_weighted.inputs["Value"])
        tree.links.new(
            day_y.outputs["Value"],
            shader_nodes.socket_by_identifier(day_weighted.inputs, "Value_001"),
        )
        ambient = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            0.1,
            label="Interior Ambient",
            location=(location[0] + 320, location[1] - 60),
            hide=True,
        ).node
        tree.links.new(interior_lighting.outputs["Value"], ambient.inputs["Value"])
        scaled_sum = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            label="Scaled EV Base",
            location=(location[0] + 800, location[1] - 160),
            hide=True,
        ).node
        tree.links.new(day_term.outputs["Value"], scaled_sum.inputs["Value"])
        tree.links.new(
            day_weighted.outputs["Value"],
            shader_nodes.socket_by_identifier(scaled_sum.inputs, "Value_001"),
        )
        scaled_ev = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            label="Scaled EV",
            location=(location[0] + 960, location[1] - 160),
            hide=True,
        ).node
        tree.links.new(scaled_sum.outputs["Value"], scaled_ev.inputs["Value"])
        tree.links.new(
            ambient.outputs["Value"],
            shader_nodes.socket_by_identifier(scaled_ev.inputs, "Value_001"),
        )

        interp_pow = shader_nodes.math(
            tree.nodes,
            tree.links,
            "POWER",
            None,
            2.2,
            label="RoomInterp^2.2",
            location=(location[0] + 800, location[1] - 360),
            hide=True,
        ).node
        tree.links.new(room_interp, interp_pow.inputs["Value"])
        term_a = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Emission Depth Term",
            location=(location[0] + 960, location[1] - 340),
            hide=True,
        ).node
        tree.links.new(scaled_ev.outputs["Value"], term_a.inputs["Value"])
        tree.links.new(
            interp_pow.outputs["Value"],
            shader_nodes.socket_by_identifier(term_a.inputs, "Value_001"),
        )
        term_a_scale = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            1.25,
            label="Emission Depth x1.25",
            location=(location[0] + 1120, location[1] - 340),
            hide=True,
        ).node
        tree.links.new(term_a.outputs["Value"], term_a_scale.inputs["Value"])
        scaled3 = shader_nodes.math(
            tree.nodes,
            tree.links,
            "POWER",
            None,
            3.0,
            label="Scaled EV^3",
            location=(location[0] + 960, location[1] - 460),
            hide=True,
        ).node
        tree.links.new(scaled_ev.outputs["Value"], scaled3.inputs["Value"])
        y_sat = create_node(
            tree.nodes,
            "ShaderNodeClamp",
            (location[0] + 800, location[1] - 500),
            label="saturate(Room Y)",
        )
        tree.links.new(room_hit_y, y_sat.inputs["Value"])
        y_upper = shader_nodes.math(
            tree.nodes,
            tree.links,
            "GREATER_THAN",
            None,
            0.85,
            label="Room Y > .85",
            location=(location[0] + 960, location[1] - 540),
            hide=True,
        ).node
        tree.links.new(y_sat.outputs["Result"], y_upper.inputs["Value"])
        term_b = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Upper Wall Emission",
            location=(location[0] + 1120, location[1] - 460),
            hide=True,
        ).node
        tree.links.new(scaled3.outputs["Value"], term_b.inputs["Value"])
        tree.links.new(
            y_upper.outputs["Value"],
            shader_nodes.socket_by_identifier(term_b.inputs, "Value_001"),
        )
        term_b_scale = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            2.0,
            label="Upper Wall x2",
            location=(location[0] + 1280, location[1] - 460),
            hide=True,
        ).node
        tree.links.new(term_b.outputs["Value"], term_b_scale.inputs["Value"])
        peak = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            label="Emission Peak",
            location=(location[0] + 1440, location[1] - 380),
            hide=True,
        ).node
        tree.links.new(term_a_scale.outputs["Value"], peak.inputs["Value"])
        tree.links.new(
            term_b_scale.outputs["Value"],
            shader_nodes.socket_by_identifier(peak.inputs, "Value_001"),
        )

        multiplier = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Emission x Rooms On",
            location=(location[0] + 1600, location[1] - 300),
            hide=True,
        ).node
        tree.links.new(peak.outputs["Value"], multiplier.inputs["Value"])
        tree.links.new(
            turned_on, shader_nodes.socket_by_identifier(multiplier.inputs, "Value_001")
        )
        cut = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Emission x Curtain Cutout",
            location=(location[0] + 1760, location[1] - 300),
            hide=True,
        ).node
        tree.links.new(multiplier.outputs["Value"], cut.inputs["Value"])
        tree.links.new(
            cutout.outputs["Value"],
            shader_nodes.socket_by_identifier(cut.inputs, "Value_001"),
        )
        scaled = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            0.75,
            label="Emission x .75",
            location=(location[0] + 1920, location[1] - 300),
            hide=True,
        ).node
        tree.links.new(cut.outputs["Value"], scaled.inputs["Value"])
        if overlay is not None:
            split = create_node(
                tree.nodes,
                "ShaderNodeSeparateColor",
                (location[0] + 1600, location[1] - 520),
                label="Overlay RGB",
            )
            tree.links.new(overlay, split.inputs["Color"])
            rg = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MAXIMUM",
                label="Overlay max RG",
                location=(location[0] + 1760, location[1] - 520),
                hide=True,
            ).node
            tree.links.new(split.outputs["Red"], rg.inputs["Value"])
            tree.links.new(
                split.outputs["Green"],
                shader_nodes.socket_by_identifier(rg.inputs, "Value_001"),
            )
            rgb = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MAXIMUM",
                label="Overlay max RGB",
                location=(location[0] + 1920, location[1] - 520),
                hide=True,
            ).node
            tree.links.new(rg.outputs["Value"], rgb.inputs["Value"])
            tree.links.new(
                split.outputs["Blue"],
                shader_nodes.socket_by_identifier(rgb.inputs, "Value_001"),
            )
            overlay_scale = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label="Emission x Overlay",
                location=(location[0] + 2080, location[1] - 300),
                hide=True,
            ).node
            tree.links.new(scaled.outputs["Value"], overlay_scale.inputs["Value"])
            tree.links.new(
                rgb.outputs["Value"],
                shader_nodes.socket_by_identifier(overlay_scale.inputs, "Value_001"),
            )
            multiplier_socket = overlay_scale.outputs["Value"]
        else:
            multiplier_socket = scaled.outputs["Value"]
        ev = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            max(0.0, param_float(data, "EmissiveEV", emissive_ev_default)),
            label="Output EmissiveEV",
            location=(location[0] + 2240, location[1] - 300),
            hide=True,
        ).node
        tree.links.new(multiplier_socket, ev.inputs["Value"])
        linear = shader_nodes.math(
            tree.nodes,
            tree.links,
            "POWER",
            label="2^EmissiveEV",
            location=(location[0] + 2400, location[1] - 300),
            hide=True,
        ).node
        linear.inputs["Value"].default_value = 2.0
        tree.links.new(
            ev.outputs["Value"],
            shader_nodes.socket_by_identifier(linear.inputs, "Value_001"),
        )
        strength = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            None,
            1.0,
            label="Eevee Emission Strength",
            location=(location[0] + 2560, location[1] - 300),
            hide=True,
        ).node
        tree.links.new(linear.outputs["Value"], strength.inputs["Value"])
        return strength.outputs["Value"], interior_lighting.outputs["Value"]


def window_day_night_factors(tree, data, room_on_random, location):
    """Build the shared editable day/night selector and room lighting gates"""
    x, y = location
    time = create_node(
        tree.nodes,
        "ShaderNodeValue",
        location,
        label="Time Of Day Preview (0 Day / 1 Night)",
    )
    time.outputs["Value"].default_value = 1.0
    room_on = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        None,
        param_float(data, "AmountTurnOffAtNight", 0.200000003),
        label="AmountTurnOffAtNight Gate",
        location=(x + 180, y),
        hide=True,
    ).node
    tree.links.new(room_on_random, room_on.inputs["Value"])
    floor = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MAXIMUM",
        None,
        0.0005,
        label="turnedOnOffSmoothness",
        location=(x + 350, y),
        hide=True,
    ).node
    tree.links.new(room_on.outputs["Value"], floor.inputs["Value"])
    lighting = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        label="timeOfDayBlend x Rooms On",
        location=(x + 520, y),
        hide=True,
    ).node
    tree.links.new(time.outputs["Value"], lighting.inputs["Value"])
    tree.links.new(
        floor.outputs["Value"],
        shader_nodes.socket_by_identifier(lighting.inputs, "Value_001"),
    )
    night = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MINIMUM",
        label="min(Rooms On, TimeOfDay)",
        location=(x + 690, y),
        hide=True,
    ).node
    tree.links.new(floor.outputs["Value"], night.inputs["Value"])
    tree.links.new(
        time.outputs["Value"],
        shader_nodes.socket_by_identifier(night.inputs, "Value_001"),
    )
    return lighting, night, time, floor
