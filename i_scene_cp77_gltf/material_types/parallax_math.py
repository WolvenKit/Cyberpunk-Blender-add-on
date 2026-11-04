import hashlib

from ..blender import shader_nodes
from .bundles import material_bundle_node, scalar_lerp_socket, vector_lerp_socket
from .graph import cp77_bitangent_socket, cp77_uv_tangent_node
from .mat_common import (
    add_group_node,
    get_or_build_node_group,
    new_labeled_node,
    new_link,
    param_float,
    param_texture_path,
)

_LARGE_STEP_PASSES = 4
_BINARY_STEP_PASSES = 10
_GROUP_VERSION = "v7"


def _scalar_value(nodes, value, name, location):
    node = new_labeled_node(nodes, "ShaderNodeValue", name, location)
    node.outputs["Value"].default_value = float(value)
    return node.outputs["Value"]


def _vector_xy(tree, x_socket, y_socket, *, location, label):
    node = new_labeled_node(tree.nodes, "ShaderNodeCombineXYZ", label, location)
    new_link(tree.links, x_socket, node.inputs["X"])
    new_link(tree.links, y_socket, node.inputs["Y"])
    return node.outputs["Vector"]


def _group_io_nodes(group, *, input_location=(-1200, 0), output_location=(900, 0)):
    group_in = new_labeled_node(group.nodes, "NodeGroupInput", "Inputs", input_location)
    group_out = new_labeled_node(
        group.nodes, "NodeGroupOutput", "Outputs", output_location
    )
    return group_in, group_out


def _height_decode_group():
    def build(group):
        group_in, group_out = _group_io_nodes(group, output_location=(420, 0))
        separate = new_labeled_node(
            group.nodes, "ShaderNodeSeparateColor", "Height R", (-720, 0)
        )
        separate.mode = "RGB"
        new_link(group.links, group_in.outputs["Sample"], separate.inputs["Color"])
        height = shader_nodes.clamp(
            group.nodes,
            group.links,
            separate.outputs["Red"],
            name="Height Saturate",
            location=(-420, 0),
        )
        new_link(group.links, height, group_out.inputs["Height"])

    return get_or_build_node_group(
        f"CP77 Parallax Height Decode {_GROUP_VERSION}",
        (("NodeSocketColor", "Sample"),),
        (("NodeSocketFloat", "Height"),),
        build,
    )


def _large_candidate_group():
    def build(group):
        group_in, group_out = _group_io_nodes(group)
        active = shader_nodes.math(
            group.nodes,
            group.links,
            "GREATER_THAN",
            name="Ray Above Height",
            location=(-880, 360),
        ).node
        new_link(group.links, group_in.outputs["Depth"], active.inputs["Value"])
        new_link(
            group.links,
            group_in.outputs["Height"],
            shader_nodes.socket_by_identifier(active.inputs, "Value_001"),
        )

        eye_step = shader_nodes.vector_math(
            group.nodes, group.links, "SCALE", name="Eye UV Step", location=(-880, 120)
        ).node
        new_link(group.links, group_in.outputs["Eye XY"], eye_step.inputs["Vector"])
        new_link(group.links, group_in.outputs["UV Step"], eye_step.inputs["Scale"])
        candidate_uv = shader_nodes.vector_math(
            group.nodes,
            group.links,
            "SUBTRACT",
            name="Candidate UV",
            location=(-580, 120),
        ).node
        new_link(group.links, group_in.outputs["UV"], candidate_uv.inputs["Vector"])
        new_link(
            group.links,
            eye_step.outputs["Vector"],
            shader_nodes.socket_by_identifier(candidate_uv.inputs, "Vector_001"),
        )

        depth_raw = shader_nodes.math(
            group.nodes,
            group.links,
            "SUBTRACT",
            name="Candidate Depth",
            location=(-580, -180),
        ).node
        new_link(group.links, group_in.outputs["Depth"], depth_raw.inputs["Value"])
        new_link(
            group.links,
            group_in.outputs["Depth Step"],
            shader_nodes.socket_by_identifier(depth_raw.inputs, "Value_001"),
        )
        depth = shader_nodes.math(
            group.nodes,
            group.links,
            "MAXIMUM",
            None,
            0.0,
            name="Saturated Depth",
            location=(-280, -180),
        ).node
        new_link(group.links, depth_raw.outputs["Value"], depth.inputs["Value"])

        new_link(
            group.links,
            candidate_uv.outputs["Vector"],
            group_out.inputs["Candidate UV"],
        )
        new_link(
            group.links, depth.outputs["Value"], group_out.inputs["Candidate Depth"]
        )
        new_link(group.links, active.outputs["Value"], group_out.inputs["Active"])

    return get_or_build_node_group(
        f"CP77 Parallax Large Candidate {_GROUP_VERSION}",
        (
            ("NodeSocketVector", "UV"),
            ("NodeSocketFloat", "Depth"),
            ("NodeSocketFloat", "Height"),
            ("NodeSocketVector", "Eye XY"),
            ("NodeSocketFloat", "UV Step"),
            ("NodeSocketFloat", "Depth Step"),
        ),
        (
            ("NodeSocketVector", "Candidate UV"),
            ("NodeSocketFloat", "Candidate Depth"),
            ("NodeSocketFloat", "Active"),
        ),
        build,
    )


def _state_commit_group():
    def build(group):
        group_in, group_out = _group_io_nodes(group, output_location=(1080, 0))
        sample = add_group_node(
            group, _height_decode_group(), (-900, -360), label="Candidate Height"
        )
        new_link(
            group.links, group_in.outputs["Candidate Sample"], sample.inputs["Sample"]
        )
        uv = vector_lerp_socket(
            group,
            group_in.outputs["UV"],
            group_in.outputs["Candidate UV"],
            group_in.outputs["Active"],
            location=(-600, 260),
            label="Selected UV",
        )
        depth = scalar_lerp_socket(
            group,
            group_in.outputs["Depth"],
            group_in.outputs["Candidate Depth"],
            group_in.outputs["Active"],
            location=(-600, 20),
            label="Selected Depth",
        )
        height = scalar_lerp_socket(
            group,
            group_in.outputs["Height"],
            sample.outputs["Height"],
            group_in.outputs["Active"],
            location=(-600, -220),
            label="Selected Height",
        )
        new_link(group.links, uv, group_out.inputs["UV"])
        new_link(group.links, depth, group_out.inputs["Depth"])
        new_link(group.links, height, group_out.inputs["Height"])

    return get_or_build_node_group(
        f"CP77 Parallax State Commit {_GROUP_VERSION}",
        (
            ("NodeSocketVector", "UV"),
            ("NodeSocketFloat", "Depth"),
            ("NodeSocketFloat", "Height"),
            ("NodeSocketVector", "Candidate UV"),
            ("NodeSocketFloat", "Candidate Depth"),
            ("NodeSocketColor", "Candidate Sample"),
            ("NodeSocketFloat", "Active"),
        ),
        (
            ("NodeSocketVector", "UV"),
            ("NodeSocketFloat", "Depth"),
            ("NodeSocketFloat", "Height"),
        ),
        build,
    )


def _binary_candidate_group(*, final=False):
    def build(group):
        group_in, group_out = _group_io_nodes(group, output_location=(1260, 0))
        diff = shader_nodes.math(
            group.nodes,
            group.links,
            "SUBTRACT",
            name="Depth Error",
            location=(-960, 380),
        ).node
        new_link(group.links, group_in.outputs["Depth"], diff.inputs["Value"])
        new_link(
            group.links,
            group_in.outputs["Height"],
            shader_nodes.socket_by_identifier(diff.inputs, "Value_001"),
        )
        abs_diff = shader_nodes.math(
            group.nodes,
            group.links,
            "ABSOLUTE",
            name="Absolute Error",
            location=(-720, 380),
        ).node
        new_link(group.links, diff.outputs["Value"], abs_diff.inputs["Value"])
        not_converged = shader_nodes.math(
            group.nodes,
            group.links,
            "GREATER_THAN",
            None,
            0.001,
            name="Not Converged",
            location=(-480, 420),
        ).node
        new_link(group.links, abs_diff.outputs["Value"], not_converged.inputs["Value"])
        within_count = shader_nodes.math(
            group.nodes,
            group.links,
            "LESS_THAN",
            name="Within Step Count",
            location=(-480, 280),
        ).node
        new_link(
            group.links, group_in.outputs["Pass Index"], within_count.inputs["Value"]
        )
        new_link(
            group.links,
            group_in.outputs["Step Count"],
            shader_nodes.socket_by_identifier(within_count.inputs, "Value_001"),
        )
        active = shader_nodes.math(
            group.nodes, group.links, "MULTIPLY", name="Active", location=(-240, 360)
        ).node
        new_link(group.links, not_converged.outputs["Value"], active.inputs["Value"])
        new_link(
            group.links,
            within_count.outputs["Value"],
            shader_nodes.socket_by_identifier(active.inputs, "Value_001"),
        )

        sign = shader_nodes.math(
            group.nodes, group.links, "SIGN", name="Error Sign", location=(-720, 100)
        ).node
        new_link(group.links, diff.outputs["Value"], sign.inputs["Value"])
        signed_uv_step = shader_nodes.math(
            group.nodes,
            group.links,
            "MULTIPLY",
            name="Signed UV Step",
            location=(-480, 100),
        ).node
        new_link(
            group.links, group_in.outputs["UV Step"], signed_uv_step.inputs["Value"]
        )
        new_link(
            group.links,
            sign.outputs["Value"],
            shader_nodes.socket_by_identifier(signed_uv_step.inputs, "Value_001"),
        )
        eye_step = shader_nodes.vector_math(
            group.nodes, group.links, "SCALE", name="Eye UV Step", location=(-240, 100)
        ).node
        new_link(group.links, group_in.outputs["Eye XY"], eye_step.inputs["Vector"])
        new_link(group.links, signed_uv_step.outputs["Value"], eye_step.inputs["Scale"])
        candidate_uv = shader_nodes.vector_math(
            group.nodes,
            group.links,
            "SUBTRACT",
            name="Candidate UV",
            location=(20, 100),
        ).node
        new_link(group.links, group_in.outputs["UV"], candidate_uv.inputs["Vector"])
        new_link(
            group.links,
            eye_step.outputs["Vector"],
            shader_nodes.socket_by_identifier(candidate_uv.inputs, "Vector_001"),
        )

        if not final:
            signed_depth_step = shader_nodes.math(
                group.nodes,
                group.links,
                "MULTIPLY",
                name="Signed Depth Step",
                location=(-480, -160),
            ).node
            new_link(
                group.links,
                group_in.outputs["Depth Step"],
                signed_depth_step.inputs["Value"],
            )
            new_link(
                group.links,
                sign.outputs["Value"],
                shader_nodes.socket_by_identifier(
                    signed_depth_step.inputs, "Value_001"
                ),
            )
            candidate_depth = shader_nodes.math(
                group.nodes,
                group.links,
                "SUBTRACT",
                name="Candidate Depth",
                location=(20, -160),
            ).node
            new_link(
                group.links, group_in.outputs["Depth"], candidate_depth.inputs["Value"]
            )
            new_link(
                group.links,
                signed_depth_step.outputs["Value"],
                shader_nodes.socket_by_identifier(candidate_depth.inputs, "Value_001"),
            )

            half_uv = shader_nodes.math(
                group.nodes,
                group.links,
                "MULTIPLY",
                None,
                0.5,
                name="Half UV Step",
                location=(280, -300),
            ).node
            new_link(group.links, group_in.outputs["UV Step"], half_uv.inputs["Value"])
            half_depth = shader_nodes.math(
                group.nodes,
                group.links,
                "MULTIPLY",
                None,
                0.5,
                name="Half Depth Step",
                location=(520, -300),
            ).node
            new_link(
                group.links, group_in.outputs["Depth Step"], half_depth.inputs["Value"]
            )

        new_link(
            group.links,
            candidate_uv.outputs["Vector"],
            group_out.inputs["Candidate UV"],
        )
        if not final:
            new_link(
                group.links,
                candidate_depth.outputs["Value"],
                group_out.inputs["Candidate Depth"],
            )
        new_link(group.links, active.outputs["Value"], group_out.inputs["Active"])
        if not final:
            new_link(
                group.links, half_uv.outputs["Value"], group_out.inputs["Half UV Step"]
            )
        if not final:
            new_link(
                group.links,
                half_depth.outputs["Value"],
                group_out.inputs["Half Depth Step"],
            )

    return get_or_build_node_group(
        f"CP77 Parallax Binary {'Final UV' if final else 'Candidate'} {_GROUP_VERSION}",
        (
            ("NodeSocketVector", "UV"),
            ("NodeSocketFloat", "Depth"),
            ("NodeSocketFloat", "Height"),
            ("NodeSocketVector", "Eye XY"),
            ("NodeSocketFloat", "UV Step"),
            *(() if final else (("NodeSocketFloat", "Depth Step"),)),
            ("NodeSocketFloat", "Step Count"),
            ("NodeSocketFloat", "Pass Index"),
        ),
        (("NodeSocketVector", "Candidate UV"), ("NodeSocketFloat", "Active"))
        if final
        else (
            ("NodeSocketVector", "Candidate UV"),
            ("NodeSocketFloat", "Candidate Depth"),
            ("NodeSocketFloat", "Active"),
            ("NodeSocketFloat", "Half UV Step"),
            ("NodeSocketFloat", "Half Depth Step"),
        ),
        build,
    )


def _sample_height_color(tree, image, uv, *, location, label):
    texture = new_labeled_node(tree.nodes, "ShaderNodeTexImage", label, location)
    texture.image = image
    texture.extension = "REPEAT"
    new_link(tree.links, uv, texture.inputs["Vector"])
    return texture.outputs["Color"]


def _build_tangent_view_vector(
    tree,
    *,
    location=(-1800, -900),
    label="Parallax Tangent View",
    flip_y=True,
    return_surface_normal=False,
):
    nodes = tree.nodes
    links = tree.links
    geometry = new_labeled_node(
        nodes, "ShaderNodeNewGeometry", f"{label} Geometry", location
    )
    tangent = cp77_uv_tangent_node(
        nodes, (location[0] + 180, location[1] - 120), label=f"{label} Tangent"
    )

    # Incoming points from the shading point toward the camera in world space.

    view = geometry.outputs["Incoming"]

    # Flip only the normal for back-facing parallax evaluation.

    normal_scale = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY_ADD",
        None,
        -2.0,
        name=f"{label} Backface Normal Sign",
        location=(location[0] + 180, location[1] - 260),
    ).node
    shader_nodes.socket_by_identifier(
        normal_scale.inputs, "Value_002"
    ).default_value = 1.0
    new_link(links, geometry.outputs["Backfacing"], normal_scale.inputs["Value"])
    faced_normal = shader_nodes.vector_math(
        nodes,
        links,
        "SCALE",
        name=f"{label} Faced Normal",
        location=(location[0] + 380, location[1] - 260),
    ).node
    new_link(links, geometry.outputs["Normal"], faced_normal.inputs["Vector"])
    new_link(links, normal_scale.outputs["Value"], faced_normal.inputs["Scale"])

    bitangent = cp77_bitangent_socket(
        nodes,
        links,
        geometry.outputs["Normal"],
        tangent.outputs["Tangent"],
        (location[0] + 380, location[1] - 80),
        label=f"{label} Bitangent",
    )

    components = []
    for basis, name, y in (
        (tangent.outputs["Tangent"], "X", 100),
        (bitangent, "Y", 0),
        (faced_normal.outputs["Vector"], "Z", -100),
    ):
        dot = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            name=f"{label} {name}",
            location=(location[0] + 580, location[1] + y),
        ).node
        new_link(links, view, dot.inputs["Vector"])
        new_link(
            links, basis, shader_nodes.socket_by_identifier(dot.inputs, "Vector_001")
        )
        components.append(dot.outputs["Value"])

    y_component = components[1]
    if flip_y:
        y_flip = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            None,
            -1.0,
            name=f"{label} DirectX Y",
            location=(location[0] + 760, location[1]),
        ).node
        new_link(links, y_component, y_flip.inputs["Value"])
        y_component = y_flip.outputs["Value"]

    combine = new_labeled_node(
        nodes, "ShaderNodeCombineXYZ", label, (location[0] + 940, location[1])
    )
    new_link(links, components[0], combine.inputs["X"])
    new_link(links, y_component, combine.inputs["Y"])
    new_link(links, components[2], combine.inputs["Z"])
    normalize = shader_nodes.vector_math(
        nodes,
        links,
        "NORMALIZE",
        name=f"{label} Normalize",
        location=(location[0] + 1120, location[1]),
    ).node
    new_link(links, combine.outputs["Vector"], normalize.inputs["Vector"])
    if not return_surface_normal:
        return normalize.outputs["Vector"]

    surface_normal = shader_nodes.vector_math(
        nodes,
        links,
        "NORMALIZE",
        name=f"{label} Surface Normal",
        location=(location[0] + 1120, location[1] - 180),
    ).node
    new_link(links, faced_normal.outputs["Vector"], surface_normal.inputs["Vector"])
    return normalize.outputs["Vector"], surface_normal.outputs["Vector"]


def _parallax_solver_group(image):
    image_name = str(getattr(image, "name_full", "") or getattr(image, "name", ""))
    image_path = str(
        getattr(image, "filepath_raw", "") or getattr(image, "filepath", "") or ""
    )
    identity = f"{image_path}\0{image_name}".encode("utf-8", "surrogatepass")
    digest = hashlib.blake2b(identity, digest_size=8).hexdigest()
    group_name = f"CP77 Parallax Solver v5 {digest}"

    def build(group):
        nodes = group.nodes
        links = group.links
        group_in, group_out = _group_io_nodes(
            group,
            input_location=(-2200, 0),
            output_location=(9200, 0),
        )
        uv = group_in.outputs["UV"]
        strength = group_in.outputs["Strength"]

        generated_view, generated_surface_normal = tangent_view_vector(
            group,
            location=(-1900, -320),
            label="Parallax View",
            return_surface_normal=True,
        )
        view = vector_lerp_socket(
            group,
            generated_view,
            group_in.outputs["Eye Override"],
            group_in.outputs["Use Frame Override"],
            location=(-620, -40),
            label="Parallax Eye Frame",
        )
        surface_normal = vector_lerp_socket(
            group,
            generated_surface_normal,
            group_in.outputs["Surface Normal Override"],
            group_in.outputs["Use Frame Override"],
            location=(-620, -180),
            label="Parallax Surface Normal Frame",
        )
        split = new_labeled_node(
            nodes,
            "ShaderNodeSeparateXYZ",
            "Parallax Eye",
            (-620, -320),
        )
        new_link(links, view, split.inputs["Vector"])
        eye_xy = _vector_xy(
            group,
            split.outputs["X"],
            split.outputs["Y"],
            location=(-460, -300),
            label="Parallax Eye XY",
        )

        angle_dot = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            name="Parallax Eye dot SurfaceNormal",
            location=(-600, -520),
        ).node
        new_link(links, view, angle_dot.inputs["Vector"])
        new_link(
            links,
            surface_normal,
            shader_nodes.socket_by_identifier(angle_dot.inputs, "Vector_001"),
        )
        abs_dot = shader_nodes.math(
            nodes,
            links,
            "ABSOLUTE",
            name="Parallax abs(Eye dot Normal)",
            location=(-430, -520),
        ).node
        new_link(links, angle_dot.outputs["Value"], abs_dot.inputs["Value"])
        grazing = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            name="Parallax 1 - abs(Eye dot Normal)",
            location=(-260, -520),
        ).node
        new_link(
            links,
            abs_dot.outputs["Value"],
            shader_nodes.socket_by_identifier(grazing.inputs, "Value_001"),
        )
        large_raw = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            None,
            8.0,
            name="Parallax Large Steps Raw",
            location=(-90, -520),
        ).node
        new_link(links, grazing.outputs["Value"], large_raw.inputs["Value"])
        num_large = shader_nodes.clamp(
            nodes,
            links,
            large_raw.outputs["Value"],
            2.0,
            8.0,
            name="Parallax Large Steps",
            location=(80, -520),
        ).node

        uv_step_numerator = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            None,
            0.075,
            name="Parallax UV Step Strength",
            location=(220, -400),
        ).node
        new_link(links, strength, uv_step_numerator.inputs["Value"])
        large_step_size = shader_nodes.math(
            nodes, links, "DIVIDE", name="Parallax UV Large Step", location=(440, -400)
        ).node
        new_link(
            links, uv_step_numerator.outputs["Value"], large_step_size.inputs["Value"]
        )
        new_link(
            links,
            num_large.outputs["Result"],
            shader_nodes.socket_by_identifier(large_step_size.inputs, "Value_001"),
        )
        large_step_depth = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            1.0,
            name="Parallax Depth Large Step",
            location=(440, -620),
        ).node
        new_link(
            links,
            num_large.outputs["Result"],
            shader_nodes.socket_by_identifier(large_step_depth.inputs, "Value_001"),
        )

        current_uv = uv
        current_depth = _scalar_value(
            nodes,
            0.5,
            "Parallax Initial Ray Depth",
            (460, -760),
        )
        initial_sample = _sample_height_color(
            group,
            image,
            current_uv,
            location=(660, 180),
            label="Parallax Height 0",
        )
        initial_height = add_group_node(
            group,
            _height_decode_group(),
            (840, 180),
            label="Parallax Height Decode 0",
        )
        new_link(links, initial_sample, initial_height.inputs["Sample"])
        current_height = initial_height.outputs["Height"]

        large_candidate_group = _large_candidate_group()
        state_commit_group = _state_commit_group()
        for index in range(_LARGE_STEP_PASSES):
            x = 1200 + index * 620
            candidate = add_group_node(
                group,
                large_candidate_group,
                (x, -300),
                label=f"Parallax Large Candidate {index + 1}",
            )
            for source, name in (
                (current_uv, "UV"),
                (current_depth, "Depth"),
                (current_height, "Height"),
                (eye_xy, "Eye XY"),
                (large_step_size.outputs["Value"], "UV Step"),
                (large_step_depth.outputs["Value"], "Depth Step"),
            ):
                new_link(links, source, candidate.inputs[name])
            candidate_sample = _sample_height_color(
                group,
                image,
                candidate.outputs["Candidate UV"],
                location=(x + 200, 120),
                label=f"Parallax Large Height {index + 1}",
            )
            commit = add_group_node(
                group,
                state_commit_group,
                (x + 400, -300),
                label=f"Parallax Large Commit {index + 1}",
            )
            for source, name in (
                (current_uv, "UV"),
                (current_depth, "Depth"),
                (current_height, "Height"),
                (candidate.outputs["Candidate UV"], "Candidate UV"),
                (candidate.outputs["Candidate Depth"], "Candidate Depth"),
                (candidate_sample, "Candidate Sample"),
                (candidate.outputs["Active"], "Active"),
            ):
                new_link(links, source, commit.inputs[name])
            current_uv = commit.outputs["UV"]
            current_depth = commit.outputs["Depth"]
            current_height = commit.outputs["Height"]

        small_delta = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            8.0,
            name="Parallax 8 - Large Steps",
            location=(720, -700),
        ).node
        new_link(
            links,
            num_large.outputs["Result"],
            shader_nodes.socket_by_identifier(small_delta.inputs, "Value_001"),
        )
        small_sqrt = shader_nodes.math(
            nodes, links, "SQRT", name="Parallax Small Step Extra", location=(890, -700)
        ).node
        new_link(links, small_delta.outputs["Value"], small_sqrt.inputs["Value"])
        small_raw = shader_nodes.math(
            nodes,
            links,
            "ADD",
            None,
            7.0,
            name="Parallax Small Steps Raw",
            location=(1060, -700),
        ).node
        new_link(links, small_sqrt.outputs["Value"], small_raw.inputs["Value"])
        num_small = shader_nodes.clamp(
            nodes,
            links,
            small_raw.outputs["Value"],
            7.0,
            10.0,
            name="Parallax Small Steps",
            location=(1230, -700),
        ).node

        binary_candidate_group = _binary_candidate_group()
        final_binary_candidate_group = _binary_candidate_group(final=True)
        binary_step_size = large_step_size.outputs["Value"]
        binary_step_depth = large_step_depth.outputs["Value"]
        for index in range(_BINARY_STEP_PASSES):
            x = 4100 + index * 440
            candidate = add_group_node(
                group,
                final_binary_candidate_group
                if index == _BINARY_STEP_PASSES - 1
                else binary_candidate_group,
                (x, -300),
                label=f"Parallax Binary Candidate {index + 1}",
            )
            for source, name in (
                (current_uv, "UV"),
                (current_depth, "Depth"),
                (current_height, "Height"),
                (eye_xy, "Eye XY"),
                (binary_step_size, "UV Step"),
                (num_small.outputs["Result"], "Step Count"),
            ):
                new_link(links, source, candidate.inputs[name])
            if index < _BINARY_STEP_PASSES - 1:
                new_link(links, binary_step_depth, candidate.inputs["Depth Step"])
            candidate.inputs["Pass Index"].default_value = float(index)
            if index == _BINARY_STEP_PASSES - 1:
                current_uv = vector_lerp_socket(
                    group,
                    current_uv,
                    candidate.outputs["Candidate UV"],
                    candidate.outputs["Active"],
                    location=(x + 280, -300),
                    label="Parallax Final Selected UV",
                )
                break
            candidate_sample = _sample_height_color(
                group,
                image,
                candidate.outputs["Candidate UV"],
                location=(x + 140, 120),
                label=f"Parallax Binary Height {index + 1}",
            )
            commit = add_group_node(
                group,
                state_commit_group,
                (x + 280, -300),
                label=f"Parallax Binary Commit {index + 1}",
            )
            for source, name in (
                (current_uv, "UV"),
                (current_depth, "Depth"),
                (current_height, "Height"),
                (candidate.outputs["Candidate UV"], "Candidate UV"),
                (candidate.outputs["Candidate Depth"], "Candidate Depth"),
                (candidate_sample, "Candidate Sample"),
                (candidate.outputs["Active"], "Active"),
            ):
                new_link(links, source, commit.inputs[name])
            current_uv = commit.outputs["UV"]
            current_depth = commit.outputs["Depth"]
            current_height = commit.outputs["Height"]
            binary_step_size = candidate.outputs["Half UV Step"]
            binary_step_depth = candidate.outputs["Half Depth Step"]

        new_link(links, current_uv, group_out.inputs["UV"])

    return get_or_build_node_group(
        group_name,
        (
            ("NodeSocketVector", "UV"),
            ("NodeSocketFloat", "Strength"),
            ("NodeSocketVector", "Eye Override"),
            ("NodeSocketVector", "Surface Normal Override"),
            ("NodeSocketFloat", "Use Frame Override"),
        ),
        (("NodeSocketVector", "UV"),),
        build,
    )


def parallax_uv(
    owner,
    tree,
    data,
    uv,
    *,
    height_key="HeightTexture",
    strength_key="HeightStrength",
    height_path=None,
    strength=None,
    location=(-1500, -900),
    label="Parallax",
    eye_override=None,
    surface_normal_override=None,
    use_frame_override=None,
    frame_factory=None,
):
    """Build the cached image-bound parallax UV solver"""
    if height_path is not None:
        path = height_path
    else:
        resolver = getattr(owner, "_texture_path", None)
        path = (
            resolver(data, height_key)
            if callable(resolver)
            else param_texture_path(data, height_key)
        )
    if strength is None:
        strength = param_float(data, strength_key, 0.0)
    strength = max(0.0, float(strength))
    if not path or strength <= 0.0:
        return uv

    image = owner._load_relative_image(path, non_color=True, error_label=height_key)
    if image is None:
        return uv

    if frame_factory is not None:
        eye_override, surface_normal_override, use_frame_override = frame_factory()

    solver = add_group_node(
        tree,
        _parallax_solver_group(image),
        location,
        label=label,
    )
    new_link(tree.links, uv, solver.inputs["UV"])
    solver.inputs["Strength"].default_value = strength
    if eye_override is not None and surface_normal_override is not None:
        new_link(tree.links, eye_override, solver.inputs["Eye Override"])
        new_link(
            tree.links,
            surface_normal_override,
            solver.inputs["Surface Normal Override"],
        )
        if use_frame_override is None:
            solver.inputs["Use Frame Override"].default_value = 1.0
        elif hasattr(use_frame_override, "is_output"):
            new_link(
                tree.links,
                use_frame_override,
                solver.inputs["Use Frame Override"],
            )
        else:
            solver.inputs["Use Frame Override"].default_value = float(
                use_frame_override
            )
    return solver.outputs["UV"]


def tangent_view_vector(
    tree,
    *,
    location=(-1800, -900),
    label="Parallax Tangent View",
    flip_y=True,
    return_surface_normal=False,
):
    outputs = (("NodeSocketVector", "View Direction"),)
    if return_surface_normal:
        outputs += (("NodeSocketVector", "Surface Normal"),)

    def build(group):
        output = group.nodes.new("NodeGroupOutput")
        result = _build_tangent_view_vector(
            group,
            location=(0, 0),
            label="Tangent View",
            flip_y=flip_y,
            return_surface_normal=return_surface_normal,
        )
        values = result if return_surface_normal else (result,)
        for (_, name), value in zip(outputs, values):
            group.links.new(value, output.inputs[name])

    convention = "DirectX" if flip_y else "Native"
    normal = " and Normal" if return_surface_normal else ""
    group = get_or_build_node_group(
        f"CP77 Parallax {convention} Tangent View{normal} Bundle v1",
        (),
        outputs,
        build,
    )
    node = material_bundle_node(tree, group, location, label, {})
    if return_surface_normal:
        return node.outputs["View Direction"], node.outputs["Surface Normal"]
    return node.outputs["View Direction"]
