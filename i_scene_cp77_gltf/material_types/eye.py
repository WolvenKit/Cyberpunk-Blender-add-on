from ..assetio.catalog import ResourceKind
from ..assetio.resolver import resolve_rooted_path
from ..blender import shader_nodes
from ..materials.resources import load_material_document
from .graph import mix_color_socket, mix_scalar_socket
from .mat_common import (
    MaterialTypeBase,
    create_relative_texture_node,
    find_input,
    new_labeled_node,
    param_float,
    populate_color_ramp,
)
from .normal_math import create_cp77_normal_texture


def _transformed_uv(tree, uv, location=(-1200, -300)):
    nodes = tree.nodes
    links = tree.links
    split = new_labeled_node(nodes, "ShaderNodeSeparateXYZ", "Eye UV", location)
    links.new(uv, split.inputs["Vector"])
    x_minus = shader_nodes.math(
        nodes,
        links,
        "SUBTRACT",
        split.outputs["X"],
        1.0,
        name="Eye U - 1",
        location=(location[0] + 180, location[1] + 120),
    )
    x_plus = shader_nodes.math(
        nodes,
        links,
        "ADD",
        split.outputs["X"],
        1.0,
        name="Eye U + 1",
        location=(location[0] + 180, location[1]),
    )
    positive = shader_nodes.math(
        nodes,
        links,
        "GREATER_THAN",
        split.outputs["X"],
        0.0,
        name="Eye U > 0",
        location=(location[0] + 180, location[1] - 120),
    )
    out_x = mix_scalar_socket(
        nodes,
        links,
        "Transform Eye U",
        (location[0] + 380, location[1] + 70),
        x_plus,
        x_minus,
        positive,
    )
    out_y = shader_nodes.math(
        nodes,
        links,
        "SUBTRACT",
        1.0,
        split.outputs["Y"],
        name="1 - Eye V",
        location=(location[0] + 380, location[1] - 80),
    )
    combine = new_labeled_node(
        nodes,
        "ShaderNodeCombineXYZ",
        "Eye UV Transform",
        (location[0] + 580, location[1]),
    )
    links.new(out_x, combine.inputs["X"])
    links.new(out_y, combine.inputs["Y"])
    return combine.outputs["Vector"]


class Eye(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        principled = shader_nodes.principled_bsdf(nodes)
        if principled is None:
            return

        texcoord = new_labeled_node(nodes, "ShaderNodeTexCoord", "Eye UV", (-1500, 200))
        uv = texcoord.outputs["UV"]
        transformed_uv = _transformed_uv(tree, uv, (-1280, -300))

        albedo = create_relative_texture_node(
            self, tree, data, "Albedo", uv, (-1060, 520)
        )
        base_color = albedo.outputs.get("Color") if albedo is not None else None

        iris_mask = create_relative_texture_node(
            self, tree, data, "IrisMask", uv, (-1060, 800), non_color=True
        )
        gradient_ref = data.get("IrisColorGradient")
        if iris_mask is not None and gradient_ref:
            profile_path = resolve_rooted_path(
                str(gradient_ref) + ".json",
                project_root=self.ProjPath,
                depot_root=self.BasePath,
                extensions=(".gradient.json",),
            )
            resource = (
                load_material_document(
                    profile_path, expected_kind=ResourceKind.GRADIENT
                )
                if profile_path
                else None
            )
            if resource is not None:
                split = new_labeled_node(
                    nodes, "ShaderNodeSeparateColor", "Iris Mask", (-820, 800)
                )
                split.mode = "RGB"
                links.new(iris_mask.outputs["Color"], split.inputs["Color"])
                ramp = new_labeled_node(
                    nodes, "ShaderNodeValToRGB", "IrisColorGradient", (-580, 820)
                )
                populate_color_ramp(ramp, resource.root.get("gradientEntries", []))
                links.new(split.outputs["Red"], ramp.inputs["Factor"])
                if base_color is not None:
                    base_color = mix_color_socket(
                        nodes,
                        links,
                        "Iris Gradient",
                        base_color,
                        ramp.outputs["Color"],
                        iris_mask.outputs["Alpha"],
                        (-300, 620),
                    )

        if base_color is not None:
            links.new(base_color, find_input(principled, "Base Color"))

        roughness = create_relative_texture_node(
            self, tree, data, "Roughness", uv, (-1060, 180), non_color=True
        )
        if roughness is not None:
            split = new_labeled_node(
                nodes, "ShaderNodeSeparateColor", "Roughness R", (-820, 180)
            )
            split.mode = "RGB"
            links.new(roughness.outputs["Color"], split.inputs["Color"])
            rough = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                split.outputs["Red"],
                max(0.0, param_float(data, "RoughnessScale", 0.2)),
                name="Eye Roughness",
                location=(-580, 180),
            )
            links.new(rough, find_input(principled, "Roughness"))

        metallic = find_input(principled, "Metallic")
        if metallic is not None:
            metallic.default_value = max(
                0.0, min(1.0, param_float(data, "Specularity", 0.18))
            )

        normal = create_cp77_normal_texture(
            self,
            tree,
            data,
            "Normal",
            uv=transformed_uv,
            strength_key="__eye_normal_strength_unused",
            default_strength=1.0,
            location=(-1020, -180),
            label="Eye Normal",
        )
        if normal is not None:
            links.new(normal, find_input(principled, "Normal"))

        alpha = find_input(principled, "Alpha")
        if alpha is not None:
            alpha.default_value = 1.0
        transmission = find_input(principled, "Transmission Weight", "Transmission")
        if transmission is not None:
            transmission.default_value = 0.0
        subsurface = find_input(principled, "Subsurface Weight")
        if subsurface is not None:
            subsurface.default_value = 0.0
        coat = find_input(principled, "Coat Weight")
        if coat is not None:
            coat.default_value = 0.0

        Mat.surface_render_method = "DITHERED"
