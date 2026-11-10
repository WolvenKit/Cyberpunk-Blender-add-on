from functools import partial

import bpy

from ..blender import shader_nodes
from ..blender.transactions import new_tracked_datablock
from ..materials.blender.nodes import (
    CreateShaderNodeValue,
    bsdf_socket_names,
    create_node,
    createLerpGroup,
    createVecLerpGroup,
)
from ..materials.cache_identity import filtered_material_data_identity
from .graph import (
    combine_bundle_node,
    cp77_bitangent_socket,
    cp77_uv_tangent_node,
    separate_bundle_node,
)
from .mat_common import (
    MaterialTypeBase,
    add_group_node,
    create_param_value_nodes,
    get_or_build_node_group,
    param_value_rows,
    set_scene_fps_driver,
    write_slot_values,
)
from .parallax_common import (
    create_camera_forward_vector,
    create_mip_sampled_texture,
    create_scroll_group,
    create_scroll_uv_group,
    retarget_mip_sampler,
)
from .scalar_params import component_value, scalar_parameter_data, scalar_value
from .shader_hash import screen_hash12_group

_LAYER_MIP_LEVELS = {2: 2, 3: 3}
_LAYER_MIP_TAPS = 9

_create_scroll_group = partial(create_scroll_group, transparent=False)
_create_scroll_uv_group = partial(create_scroll_uv_group, transparent=False)

_RANDOM_OFFSET_BUNDLE_ITEMS = (
    ("FLOAT", "Min X"),
    ("FLOAT", "Max X"),
    ("FLOAT", "Min Y"),
    ("FLOAT", "Max Y"),
)

_VALUE_PARAM_SPECS = (
    ("BlinkingSpeed", "blinkingSpeed", 450, "BlinkingSpeed", 0.0),
    ("LayersSeparation", "layersSeparation", 100, "LayersSeparation", 0.100000001),
    ("ScanlinesIntensity", "scanlinesIntensity", 0, "ScanlinesIntensity", 0.25),
    ("ImageScale", "imageScale", -200, "ImageScale", 1.04999995),
    ("ScrollSpeed1", "scrollSpeed1", -250, "ScrollSpeed1", 0.25),
    ("ScrollStepFactor1", "scrollStepFactor1", -300, "ScrollStepFactor1", 30.0),
    ("ScrollMaskHeight1", "scrollMaskHeight1", -350, "ScrollMaskHeight1", 0.5),
    (
        "ScrollMaskStartPoint1",
        "scrollMaskStartPoint1",
        -400,
        "ScrollMaskStartPoint1",
        0.0199999996,
    ),
    ("ScrollSpeed2", "scrollSpeed2", -500, "ScrollSpeed2", 1.5),
    ("ScrollStepFactor2", "scrollStepFactor2", -550, "ScrollStepFactor2", 10.0),
    ("ScrollMaskHeight2", "scrollMaskHeight2", -600, "ScrollMaskHeight2", 0.200000003),
    (
        "ScrollMaskStartPoint2",
        "scrollMaskStartPoint2",
        -650,
        "ScrollMaskStartPoint2",
        0.400000006,
    ),
    ("IsBroken", "isBroken", -700, "IsBroken", 0.0),
    (
        "ScrollVerticalOrHorizontal",
        "scrollVerticalOrHorizontal",
        -750,
        "ScrollVerticalOrHorizontal",
        0.0,
    ),
    ("Emissive", "emissive", -800, "Emissive", 7.0),
    ("FixForBlack", "fixForBlack", -1000, "FixForBlack", 1.0),
    ("Metalness", "metalness", -1050, "Metalness", 0.899999976),
    ("Roughness", "roughness", -1100, "Roughness", 0.100000001),
)

_IMAGE_PARAM_SPECS = (
    ("ParalaxTexture", "parImg"),
    ("BlinkingMaskTexture", "blinkImg"),
    ("ScanlineTexture", "scanLineImg"),
    ("ScrollMaskTexture", "scrollMaskImg"),
)

_CACHE_PARAMETERS = frozenset(
    {spec[0] for spec in _VALUE_PARAM_SPECS}
    | {spec[0] for spec in _IMAGE_PARAM_SPECS}
    | {"HSV_Mod", "ScanlinesDensity", "IntensityPerLayer", "EmissiveColor", "Tint"}
)


def material_cache_identity(raw_material):
    return filtered_material_data_identity(raw_material, _CACHE_PARAMETERS)


def _scanlines_density(Data):
    """Whether the ScanlinesDensity node takes a vector parameter's X, and the value it takes"""
    density = Data.get("ScanlinesDensity", 125.0)
    if density is None:
        return False, 1.0
    if isinstance(density, dict) and any(
        axis in density for axis in ("X", "Y", "Z", "W")
    ):
        return True, scalar_value(density.get("X"), 1.0, "X")
    return False, scalar_value(density, 1.0, "ScanlinesDensity")


def _emissive_color(Data):
    for key in ("EmissiveColor", "Tint"):
        if key in Data:
            color = Data[key]
            return (
                float(color["Red"]) / 255,
                float(color["Green"]) / 255,
                float(color["Blue"]) / 255,
                float(color["Alpha"]) / 255,
            )
    return (1.0, 1.0, 1.0, 1.0)


def _create_l1_group():
    inputs = (("NodeSocketVector", "newUV"),)
    outputs = (("NodeSocketVector", "l1"),)

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-800, 0))
        group_out = create_node(group.nodes, "NodeGroupOutput", (200, 0))
        separate = create_node(group.nodes, "ShaderNodeSeparateXYZ", (-650, 0))
        clamp_x = create_node(group.nodes, "ShaderNodeClamp", (-500, 25))
        clamp_y = create_node(group.nodes, "ShaderNodeClamp", (-500, -25))
        combine = create_node(group.nodes, "ShaderNodeCombineXYZ", (-350, 0))
        group.links.new(group_in.outputs["newUV"], separate.inputs["Vector"])
        group.links.new(separate.outputs["X"], clamp_x.inputs["Value"])
        group.links.new(separate.outputs["Y"], clamp_y.inputs["Value"])
        group.links.new(clamp_x.outputs["Result"], combine.inputs["X"])
        group.links.new(clamp_y.outputs["Result"], combine.inputs["Y"])
        group.links.new(combine.outputs["Vector"], group_out.inputs["l1"])

    return get_or_build_node_group("CP77 Opaque Screen l1 v1", inputs, outputs, build)


def _create_layer_uv_group(layer):
    group_name = f"CP77 Opaque Screen Layer {layer} UV v1"
    scale_socket = "l2" if layer == 2 else "LayersSeparation"
    output_name = "newRandomOffset" if layer == 2 else "l3"
    inputs = (
        ("NodeSocketVector", "modUV"),
        ("NodeSocketVector", "newUV"),
        ("NodeSocketFloat", scale_socket),
    )
    outputs = (("NodeSocketVector", output_name),)

    def build(group):
        group_in = create_node(group.nodes, "NodeGroupInput", (-800, 0))
        group_out = create_node(
            group.nodes, "NodeGroupOutput", (300 if layer == 3 else 200, 0)
        )
        vec_mul = shader_nodes.vector_math(
            group.nodes, group.links, "MULTIPLY", location=(-600, 0), hide=True
        ).node
        offset = vec_mul
        if layer == 3:
            vec_mul2 = shader_nodes.vector_math(
                group.nodes, group.links, "MULTIPLY", location=(-450, 0), hide=True
            ).node
            shader_nodes.socket_by_identifier(
                vec_mul2.inputs, "Vector_001"
            ).default_value = (2, 2, 2)
            offset = vec_mul2
        vec_add = shader_nodes.vector_math(
            group.nodes,
            group.links,
            "ADD",
            location=(-300 if layer == 3 else -450, 0),
            hide=True,
        ).node
        separate = create_node(
            group.nodes, "ShaderNodeSeparateXYZ", (-150 if layer == 3 else -300, 0)
        )
        clamp_x = create_node(
            group.nodes, "ShaderNodeClamp", (0 if layer == 3 else -150, 25)
        )
        clamp_y = create_node(
            group.nodes, "ShaderNodeClamp", (0 if layer == 3 else -150, -25)
        )
        combine = create_node(
            group.nodes, "ShaderNodeCombineXYZ", (150 if layer == 3 else 0, 0)
        )
        group.links.new(group_in.outputs["modUV"], vec_mul.inputs["Vector"])
        group.links.new(
            group_in.outputs[scale_socket],
            shader_nodes.socket_by_identifier(vec_mul.inputs, "Vector_001"),
        )
        if layer == 3:
            group.links.new(vec_mul.outputs["Vector"], offset.inputs["Vector"])
        group.links.new(group_in.outputs["newUV"], vec_add.inputs["Vector"])
        group.links.new(
            offset.outputs["Vector"],
            shader_nodes.socket_by_identifier(vec_add.inputs, "Vector_001"),
        )
        group.links.new(vec_add.outputs["Vector"], separate.inputs["Vector"])
        group.links.new(separate.outputs["X"], clamp_x.inputs["Value"])
        group.links.new(separate.outputs["Y"], clamp_y.inputs["Value"])
        group.links.new(clamp_x.outputs["Result"], combine.inputs["X"])
        group.links.new(clamp_y.outputs["Result"], combine.inputs["Y"])
        group.links.new(combine.outputs["Vector"], group_out.inputs[output_name])

    return get_or_build_node_group(group_name, inputs, outputs, build)


def _create_blink_group():
    """Apply the masked pulse only for positive speeds, retaining the clamped waveform"""

    def build(group):
        nodes, links = group.nodes, group.links
        incoming = create_node(nodes, "NodeGroupInput", (-1000, 0))
        outgoing = create_node(nodes, "NodeGroupOutput", (600, 0))
        enabled = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            label="Blink Enabled",
            location=(-800, -200),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            enabled.inputs, "Value_001"
        ).default_value = 0.0
        phase = shader_nodes.math(
            nodes, links, "MULTIPLY", location=(-800, 200), hide=True
        ).node
        sine = shader_nodes.math(
            nodes, links, "SINE", location=(-620, 200), hide=True
        ).node
        pulse = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            label="Clamped Blink Pulse",
            location=(-440, 200),
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            pulse.inputs, "Value_001"
        ).default_value = 100.0
        pulse.use_clamp = True
        mask = create_node(nodes, "ShaderNodeSeparateColor", (-800, 0))
        mask_floor = shader_nodes.math(
            nodes, links, "FLOOR", location=(-620, 0), use_clamp=True, hide=True
        ).node
        difference = shader_nodes.math(
            nodes, links, "SUBTRACT", location=(-440, 0), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            difference.inputs, "Value_001"
        ).default_value = 1.0
        masked_pulse = shader_nodes.math(
            nodes, links, "MULTIPLY", location=(-260, 100), hide=True
        ).node
        active_pulse = shader_nodes.math(
            nodes, links, "MULTIPLY", location=(-80, 0), hide=True
        ).node
        multiplier = shader_nodes.math(
            nodes, links, "ADD", label="Blink Multiplier", location=(100, 0), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            multiplier.inputs, "Value_001"
        ).default_value = 1.0
        color = shader_nodes.vector_math(
            nodes, links, "SCALE", location=(300, 0), hide=True
        ).node
        links.new(incoming.outputs["BlinkingSpeed"], enabled.inputs["Value"])
        links.new(incoming.outputs["BlinkingSpeed"], phase.inputs["Value"])
        links.new(
            incoming.outputs["time"],
            shader_nodes.socket_by_identifier(phase.inputs, "Value_001"),
        )
        links.new(phase.outputs["Value"], sine.inputs["Value"])
        links.new(sine.outputs["Value"], pulse.inputs["Value"])
        links.new(incoming.outputs["iA"], mask.inputs["Color"])
        links.new(mask.outputs["Red"], mask_floor.inputs["Value"])
        links.new(mask_floor.outputs["Value"], difference.inputs["Value"])
        links.new(difference.outputs["Value"], masked_pulse.inputs["Value"])
        links.new(
            pulse.outputs["Value"],
            shader_nodes.socket_by_identifier(masked_pulse.inputs, "Value_001"),
        )
        links.new(masked_pulse.outputs["Value"], active_pulse.inputs["Value"])
        links.new(
            enabled.outputs["Value"],
            shader_nodes.socket_by_identifier(active_pulse.inputs, "Value_001"),
        )
        links.new(active_pulse.outputs["Value"], multiplier.inputs["Value"])
        links.new(incoming.outputs["i1"], color.inputs["Vector"])
        links.new(multiplier.outputs["Value"], color.inputs["Scale"])
        links.new(color.outputs["Vector"], outgoing.inputs["new_i1"])

    return get_or_build_node_group(
        "CP77 Opaque Screen Masked Blink v2",
        (
            ("NodeSocketFloat", "BlinkingSpeed"),
            ("NodeSocketFloat", "time"),
            ("NodeSocketColor", "iA"),
            ("NodeSocketColor", "i1"),
        ),
        (("NodeSocketColor", "new_i1"),),
        build,
    )


class ParallaxScreen(MaterialTypeBase):
    texture_defaults = {
        "ParalaxTexture": r"base\surfaces\textures\screens\generic\display_block_02.xbm",
        "BlinkingMaskTexture": r"base\surfaces\materials\default\black.xbm",
        "ScanlineTexture": r"base\fx\_textures\masks\gradients\fx_reflected_vertical_gradient_02_d.xbm",
        "ScrollMaskTexture": r"base\surfaces\materials\default\black.xbm",
    }

    def createStepGroup(self):
        def build(group):
            incoming = create_node(group.nodes, "NodeGroupInput", (-500, 0))
            outgoing = create_node(group.nodes, "NodeGroupOutput", (100, 0))
            below = shader_nodes.math(
                group.nodes, group.links, "LESS_THAN", location=(-300, 0), hide=True
            ).node
            result = shader_nodes.math(
                group.nodes, group.links, "SUBTRACT", location=(-100, 0), hide=True
            ).node
            result.inputs["Value"].default_value = 1.0
            group.links.new(incoming.outputs["x"], below.inputs["Value"])
            group.links.new(
                incoming.outputs["y"],
                shader_nodes.socket_by_identifier(below.inputs, "Value_001"),
            )
            group.links.new(
                below.outputs["Value"],
                shader_nodes.socket_by_identifier(result.inputs, "Value_001"),
            )
            group.links.new(result.outputs["Value"], outgoing.inputs["result"])

        return get_or_build_node_group(
            "CP77 Opaque Screen Threshold v2",
            (("NodeSocketFloat", "y"), ("NodeSocketFloat", "x")),
            (("NodeSocketFloat", "result"),),
            build,
        )

    def colorlessTexGroup(self):
        colorlessTexGroup = bpy.data.node_groups.get(
            "CP77 Opaque Screen colorlessTex v1"
        )
        if colorlessTexGroup is not None:
            return colorlessTexGroup
        else:
            colorlessTexGroup = new_tracked_datablock(
                "node_groups", "CP77 Opaque Screen colorlessTex v1", "ShaderNodeTree"
            )
            colorlessTexGroup.interface.new_socket(
                name="Color", socket_type="NodeSocketColor", in_out="INPUT"
            )
            colorlessTexGroup.interface.new_socket(
                name="Color", socket_type="NodeSocketColor", in_out="OUTPUT"
            )

            colorlessTexGroupI = create_node(
                colorlessTexGroup.nodes, "NodeGroupInput", (-1400, 0)
            )
            colorlessTexGroupO = create_node(
                colorlessTexGroup.nodes, "NodeGroupOutput", (-200, 0)
            )
            separate = create_node(
                colorlessTexGroup.nodes, "ShaderNodeSeparateColor", (-1200, 0)
            )
            compare = shader_nodes.math(
                colorlessTexGroup.nodes,
                colorlessTexGroup.links,
                "COMPARE",
                location=(-1000, 25),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                compare.inputs, "Value_002"
            ).default_value = 0
            compare2 = shader_nodes.math(
                colorlessTexGroup.nodes,
                colorlessTexGroup.links,
                "COMPARE",
                location=(-1000, -25),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                compare2.inputs, "Value_002"
            ).default_value = 0
            add = shader_nodes.math(
                colorlessTexGroup.nodes,
                colorlessTexGroup.links,
                "ADD",
                location=(-800, 0),
                hide=True,
            ).node
            compare3 = shader_nodes.math(
                colorlessTexGroup.nodes,
                colorlessTexGroup.links,
                "COMPARE",
                location=(-650, 0),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                compare3.inputs, "Value_001"
            ).default_value = 2
            shader_nodes.socket_by_identifier(
                compare3.inputs, "Value_002"
            ).default_value = 0
            combine = create_node(
                colorlessTexGroup.nodes, "ShaderNodeCombineColor", (-1000, -75)
            )
            mixRGB = create_node(colorlessTexGroup.nodes, "ShaderNodeMix", (-400, 0))
            mixRGB.data_type = "RGBA"
            colorlessTexGroup.links.new(
                colorlessTexGroupI.outputs["Color"], separate.inputs["Color"]
            )
            colorlessTexGroup.links.new(separate.outputs["Red"], combine.inputs["Red"])
            colorlessTexGroup.links.new(
                separate.outputs["Red"], compare.inputs["Value"]
            )
            colorlessTexGroup.links.new(
                separate.outputs["Green"],
                shader_nodes.socket_by_identifier(compare.inputs, "Value_001"),
            )
            colorlessTexGroup.links.new(
                separate.outputs["Red"], compare2.inputs["Value"]
            )
            colorlessTexGroup.links.new(
                separate.outputs["Blue"],
                shader_nodes.socket_by_identifier(compare2.inputs, "Value_001"),
            )
            colorlessTexGroup.links.new(compare.outputs["Value"], add.inputs["Value"])
            colorlessTexGroup.links.new(
                compare2.outputs["Value"],
                shader_nodes.socket_by_identifier(add.inputs, "Value_001"),
            )
            colorlessTexGroup.links.new(add.outputs["Value"], compare3.inputs["Value"])
            colorlessTexGroup.links.new(
                compare3.outputs["Value"],
                shader_nodes.socket_by_identifier(mixRGB.inputs, "Factor_Float"),
            )
            colorlessTexGroup.links.new(
                colorlessTexGroupI.outputs["Color"],
                shader_nodes.socket_by_identifier(mixRGB.inputs, "A_Color"),
            )
            colorlessTexGroup.links.new(
                combine.outputs["Color"],
                shader_nodes.socket_by_identifier(mixRGB.inputs, "B_Color"),
            )
            colorlessTexGroup.links.new(
                shader_nodes.socket_by_identifier(mixRGB.outputs, "Result_Color"),
                colorlessTexGroupO.inputs["Color"],
            )
            return colorlessTexGroup

    def _images(self, Data):
        images = {}
        for key, var_name in _IMAGE_PARAM_SPECS:
            reference = self._texture_path(Data, key)
            if reference:
                images[var_name] = self._image_from_rel_path(reference)
        return images

    def _values(self, Data):
        """Each Value and RGB node's value, by structure slot"""
        values = {
            f"value:{var_name}": float(value)
            for var_name, _y, _label, value in param_value_rows(
                scalar_parameter_data(Data, _VALUE_PARAM_SPECS), _VALUE_PARAM_SPECS
            )
        }
        hsv_mod = Data.get("HSV_Mod") or {"X": 0.0, "Y": 1.0, "Z": 0.0, "W": -1.0}
        for axis in ("W", "X", "Y"):
            values[f"HSV_Mod.{axis.lower()}"] = float(
                component_value(hsv_mod, axis, 0.0)
            )
        values["ScanlinesDensity"] = float(_scanlines_density(Data)[1])
        intensity = Data.get(
            "IntensityPerLayer", {"X": 1.0, "Y": 0.25, "Z": 0.0599999987, "W": 0.0}
        )
        for axis in ("X", "Y", "Z"):
            values[f"IntensityPerLayer.{axis.lower()}"] = float(
                component_value(intensity, axis, 1.0)
            )
        values["EmissiveColor"] = _emissive_color(Data)
        return values

    def structure_key(self, Data):
        # Only which textures load and the form of the scanline density shape the graph; the build reads every other
        # parameter into a Value or RGB node.
        images = self._images(Data)
        return (
            tuple(
                images.get(var_name) is not None
                for _key, var_name in _IMAGE_PARAM_SPECS
            ),
            _scanlines_density(Data)[0],
        )

    def apply_structure_values(self, Data, Mat, slots):
        nodes = Mat.node_tree.nodes
        write_slot_values(nodes, slots, self._values(Data))
        images = self._images(Data)
        for _key, var_name in _IMAGE_PARAM_SPECS:
            image = images.get(var_name)
            for name in slots.get(f"image:{var_name}", ()):
                node = nodes[name]
                if node.image is not image:
                    node.image = image
        for layer in (2, 3):
            name = slots.get(f"mip:{layer}")
            if name is not None:
                retarget_mip_sampler(
                    nodes[name],
                    images.get("parImg"),
                    _LAYER_MIP_LEVELS[layer],
                    taps=_LAYER_MIP_TAPS,
                )

    def _slot_image(self, var_name, node):
        self.structure_slots.setdefault(f"image:{var_name}", []).append(node.name)

    def create(self, Data, Mat):
        CurMat = Mat.node_tree
        pBSDF = shader_nodes.principled_bsdf(CurMat.nodes)
        sockets = bsdf_socket_names()
        pBSDF.inputs[sockets["Specular"]].default_value = 0
        values = self._values(Data)

        param_nodes = create_param_value_nodes(
            CurMat, scalar_parameter_data(Data, _VALUE_PARAM_SPECS), _VALUE_PARAM_SPECS
        )
        slots = self.structure_slots = {
            f"value:{var_name}": (node.name, None)
            for var_name, node in param_nodes.items()
        }

        blinkingSpeed = param_nodes.get("blinkingSpeed")
        layersSeparation = param_nodes.get("layersSeparation")
        scanlinesIntensity = param_nodes.get("scanlinesIntensity")
        imageScale = param_nodes.get("imageScale")
        scrollSpeed1 = param_nodes.get("scrollSpeed1")
        scrollStepFactor1 = param_nodes.get("scrollStepFactor1")
        scrollMaskHeight1 = param_nodes.get("scrollMaskHeight1")
        scrollMaskStartPoint1 = param_nodes.get("scrollMaskStartPoint1")
        scrollSpeed2 = param_nodes.get("scrollSpeed2")
        scrollStepFactor2 = param_nodes.get("scrollStepFactor2")
        scrollMaskHeight2 = param_nodes.get("scrollMaskHeight2")
        scrollMaskStartPoint2 = param_nodes.get("scrollMaskStartPoint2")
        isBroken = param_nodes.get("isBroken")
        scrollVerticalOrHorizontal = param_nodes.get("scrollVerticalOrHorizontal")
        emissive = param_nodes.get("emissive")
        fixForBlack = param_nodes.get("fixForBlack")
        metalness = param_nodes.get("metalness")
        roughness = param_nodes.get("roughness")

        HSV_Mod_w = CreateShaderNodeValue(
            CurMat, values["HSV_Mod.w"], -2000, 150, "HSV_Mod.w"
        )
        HSV_Mod_x = CreateShaderNodeValue(
            CurMat, values["HSV_Mod.x"], -2000, -950, "HSV_Mod.x"
        )
        HSV_Mod_y = CreateShaderNodeValue(
            CurMat, values["HSV_Mod.y"], -2000, -900, "HSV_Mod.y"
        )

        if _scanlines_density(Data)[0]:
            scanlinesDensity = CreateShaderNodeValue(
                CurMat, values["ScanlinesDensity"], -2200, -50, "ScanlinesDensity.x"
            )
        else:
            scanlinesDensity = CreateShaderNodeValue(
                CurMat, values["ScanlinesDensity"], -2000, 50, "ScanlinesDensity"
            )

        intensityPerLayer_x = CreateShaderNodeValue(
            CurMat, values["IntensityPerLayer.x"], -2000, -50, "IntensityPerLayer.x"
        )
        intensityPerLayer_y = CreateShaderNodeValue(
            CurMat, values["IntensityPerLayer.y"], -2000, -100, "IntensityPerLayer.y"
        )
        intensityPerLayer_z = CreateShaderNodeValue(
            CurMat, values["IntensityPerLayer.z"], -2000, -150, "IntensityPerLayer.z"
        )

        emissiveColor = create_node(
            CurMat.nodes, "ShaderNodeRGB", (-2000, -850), label="EmissiveColor"
        )
        emissiveColor.outputs["Color"].default_value = values["EmissiveColor"]
        for slot, node in (
            ("HSV_Mod.w", HSV_Mod_w),
            ("HSV_Mod.x", HSV_Mod_x),
            ("HSV_Mod.y", HSV_Mod_y),
            ("ScanlinesDensity", scanlinesDensity),
            ("IntensityPerLayer.x", intensityPerLayer_x),
            ("IntensityPerLayer.y", intensityPerLayer_y),
            ("IntensityPerLayer.z", intensityPerLayer_z),
            ("EmissiveColor", emissiveColor),
        ):
            slots[slot] = (node.name, None)

        images = self._images(Data)
        parImg = images.get("parImg")
        blinkImg = images.get("blinkImg")
        scanLineImg = images.get("scanLineImg")
        scrollMaskImg = images.get("scrollMaskImg")

        tangent = cp77_uv_tangent_node(
            CurMat.nodes, (-2000, 400), label="Parallax Screen Tangent"
        )
        geometry = create_node(CurMat.nodes, "ShaderNodeNewGeometry", (-2000, 300))
        UVMap = create_node(CurMat.nodes, "ShaderNodeUVMap", (-2000, 200))

        vecCross = cp77_bitangent_socket(
            CurMat.nodes,
            CurMat.links,
            geometry.outputs["Normal"],
            tangent.outputs["Tangent"],
            (-1850, 350),
            label="Parallax Screen Binormal",
        )

        cameraForward = create_camera_forward_vector(CurMat, location=(-1850, 250))

        vecDot = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "DOT_PRODUCT", location=(-1500, 200), hide=True
        ).node
        CurMat.links.new(cameraForward, vecDot.inputs["Vector"])
        CurMat.links.new(
            tangent.outputs["Tangent"],
            shader_nodes.socket_by_identifier(vecDot.inputs, "Vector_001"),
        )

        vecDot2 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "DOT_PRODUCT", location=(-1500, 150), hide=True
        ).node
        CurMat.links.new(cameraForward, vecDot2.inputs["Vector"])
        CurMat.links.new(
            vecCross, shader_nodes.socket_by_identifier(vecDot2.inputs, "Vector_001")
        )

        vecMul = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-1350, 150), hide=True
        ).node
        combine = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-1200, 175))
        CurMat.links.new(vecDot2.outputs["Value"], vecMul.inputs["Vector"])
        CurMat.links.new(
            HSV_Mod_w.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMul.inputs, "Vector_001"),
        )
        CurMat.links.new(vecDot.outputs["Value"], combine.inputs["X"])
        CurMat.links.new(vecMul.outputs["Vector"], combine.inputs["Y"])

        vecSub = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "SUBTRACT", location=(-1500, 0), hide=True
        ).node
        shader_nodes.socket_by_identifier(vecSub.inputs, "Vector_001").default_value = (
            0.5,
            0.5,
            0.5,
        )
        vecMul2 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-1350, 0), hide=True
        ).node
        vecAdd = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "ADD", location=(-1200, 0), hide=True
        ).node
        shader_nodes.socket_by_identifier(vecAdd.inputs, "Vector_001").default_value = (
            0.5,
            0.5,
            0.5,
        )
        CurMat.links.new(UVMap.outputs["UV"], vecSub.inputs["Vector"])
        CurMat.links.new(vecSub.outputs["Vector"], vecMul2.inputs["Vector"])
        CurMat.links.new(
            imageScale.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMul2.inputs, "Vector_001"),
        )
        CurMat.links.new(vecMul2.outputs["Vector"], vecAdd.inputs["Vector"])

        time = CreateShaderNodeValue(CurMat, 1, -2000, -450, "Time")
        timeDriver = time.outputs["Value"].driver_add("default_value")
        set_scene_fps_driver(timeDriver.driver)

        scroll1Group = _create_scroll_group(1)
        scroll1 = add_group_node(
            CurMat, scroll1Group, (-1500, -200), label="scroll1", name="scroll1"
        )
        CurMat.links.new(scrollSpeed1.outputs["Value"], scroll1.inputs["ScrollSpeed1"])
        CurMat.links.new(
            scrollStepFactor1.outputs["Value"], scroll1.inputs["ScrollStepFactor1"]
        )
        CurMat.links.new(time.outputs["Value"], scroll1.inputs["Time"])

        scrollUV1Group = _create_scroll_uv_group(1, False)
        scrollUV1 = add_group_node(
            CurMat, scrollUV1Group, (-1350, -200), label="scrollUV1", name="scrollUV1"
        )
        CurMat.links.new(vecAdd.outputs["Vector"], scrollUV1.inputs["newUV"])
        CurMat.links.new(
            scrollMaskHeight1.outputs["Value"], scrollUV1.inputs["ScrollMaskHeight1"]
        )
        CurMat.links.new(scroll1.outputs["scroll1"], scrollUV1.inputs["scroll1"])
        CurMat.links.new(
            scrollMaskStartPoint1.outputs["Value"],
            scrollUV1.inputs["ScrollMaskStartPoint1"],
        )

        scrollUV1XGroup = _create_scroll_uv_group(1, True)
        scrollUV1X = add_group_node(
            CurMat,
            scrollUV1XGroup,
            (-1350, -250),
            label="scrollUV1X",
            name="scrollUV1X",
        )
        CurMat.links.new(vecAdd.outputs["Vector"], scrollUV1X.inputs["newUV"])
        CurMat.links.new(
            scrollMaskHeight1.outputs["Value"], scrollUV1X.inputs["ScrollMaskHeight1"]
        )
        CurMat.links.new(scroll1.outputs["scroll1"], scrollUV1X.inputs["scroll1"])
        CurMat.links.new(
            scrollMaskStartPoint1.outputs["Value"],
            scrollUV1X.inputs["ScrollMaskStartPoint1"],
        )

        scroll2Group = _create_scroll_group(2)
        scroll2 = add_group_node(
            CurMat, scroll2Group, (-1500, -300), label="scroll2", name="scroll2"
        )
        CurMat.links.new(scrollSpeed2.outputs["Value"], scroll2.inputs["ScrollSpeed2"])
        CurMat.links.new(
            scrollStepFactor2.outputs["Value"], scroll2.inputs["ScrollStepFactor2"]
        )
        CurMat.links.new(time.outputs["Value"], scroll2.inputs["Time"])

        scrollUV2Group = _create_scroll_uv_group(2, False)
        scrollUV2 = add_group_node(
            CurMat, scrollUV2Group, (-1350, -300), label="scrollUV2", name="scrollUV2"
        )
        CurMat.links.new(vecAdd.outputs["Vector"], scrollUV2.inputs["newUV"])
        CurMat.links.new(
            scrollMaskHeight2.outputs["Value"], scrollUV2.inputs["ScrollMaskHeight2"]
        )
        CurMat.links.new(scroll2.outputs["scroll2"], scrollUV2.inputs["scroll2"])
        CurMat.links.new(
            scrollMaskStartPoint2.outputs["Value"],
            scrollUV2.inputs["ScrollMaskStartPoint2"],
        )

        scrollUV2XGroup = _create_scroll_uv_group(2, True)
        scrollUV2X = add_group_node(
            CurMat,
            scrollUV2XGroup,
            (-1350, -350),
            label="scrollUV2X",
            name="scrollUV2X",
        )
        CurMat.links.new(vecAdd.outputs["Vector"], scrollUV2X.inputs["newUV"])
        CurMat.links.new(
            scrollMaskHeight2.outputs["Value"], scrollUV2X.inputs["ScrollMaskHeight2"]
        )
        CurMat.links.new(scroll2.outputs["scroll2"], scrollUV2X.inputs["scroll2"])
        CurMat.links.new(
            scrollMaskStartPoint2.outputs["Value"],
            scrollUV2X.inputs["ScrollMaskStartPoint2"],
        )

        lerpG = createLerpGroup()
        vecLerpG = createVecLerpGroup()
        lerp = create_node(CurMat.nodes, "ShaderNodeGroup", (-1050, -450), label="lerp")
        lerp.node_tree = lerpG
        lerp.inputs["A"].default_value = 2
        lerp.inputs["B"].default_value = 8
        frac2 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "FRACT", location=(-1200, -450), hide=True
        ).node
        add7 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "ADD", location=(-1350, -450), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            add7.inputs, "Value_001"
        ).default_value = 0.375
        CurMat.links.new(time.outputs["Value"], add7.inputs["Value"])
        CurMat.links.new(add7.outputs["Value"], frac2.inputs["Value"])
        CurMat.links.new(frac2.outputs["Value"], lerp.inputs["t"])

        brokenUVGroup = bpy.data.node_groups.get("CP77 Opaque Screen brokenUV v2")
        if brokenUVGroup is None:
            brokenUVGroup = new_tracked_datablock(
                "node_groups", "CP77 Opaque Screen brokenUV v2", "ShaderNodeTree"
            )
            brokenUVGroup.interface.new_socket(
                name="rndBlocks", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            brokenUVGroup.interface.new_socket(
                name="Time", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            brokenUVGroup.interface.new_socket(
                name="UV", socket_type="NodeSocketVector", in_out="INPUT"
            )
            brokenUVGroup.interface.new_socket(
                name="brokenUV", socket_type="NodeSocketVector", in_out="OUTPUT"
            )

            brokenUVGroupI = create_node(
                brokenUVGroup.nodes, "NodeGroupInput", (-1400, 0)
            )
            brokenUVGroupO = create_node(
                brokenUVGroup.nodes, "NodeGroupOutput", (200, 0)
            )
            hash12G = screen_hash12_group()
            hash12 = create_node(
                brokenUVGroup.nodes, "ShaderNodeGroup", (-650, -50), label="hash12"
            )
            hash12.node_tree = hash12G
            add = shader_nodes.math(
                brokenUVGroup.nodes,
                brokenUVGroup.links,
                "ADD",
                location=(-1250, 0),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                add.inputs, "Value_001"
            ).default_value = 0.35748
            mul = shader_nodes.math(
                brokenUVGroup.nodes,
                brokenUVGroup.links,
                "MULTIPLY",
                location=(-1100, 0),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                mul.inputs, "Value_001"
            ).default_value = 60
            floor = shader_nodes.math(
                brokenUVGroup.nodes,
                brokenUVGroup.links,
                "FLOOR",
                location=(-800, -50),
                hide=True,
            ).node
            separate = create_node(
                brokenUVGroup.nodes, "ShaderNodeSeparateXYZ", (-800, 0)
            )
            combine15 = create_node(
                brokenUVGroup.nodes, "ShaderNodeCombineXYZ", (-650, 0)
            )
            vecAdd2 = shader_nodes.vector_math(
                brokenUVGroup.nodes,
                brokenUVGroup.links,
                "ADD",
                location=(-350, 0),
                hide=True,
            ).node
            vecFrac = shader_nodes.vector_math(
                brokenUVGroup.nodes,
                brokenUVGroup.links,
                "FRACTION",
                location=(-200, 0),
                hide=True,
            ).node
            mul2 = shader_nodes.math(
                brokenUVGroup.nodes,
                brokenUVGroup.links,
                "MULTIPLY",
                location=(-1250, -100),
                hide=True,
            ).node
            floor2 = shader_nodes.math(
                brokenUVGroup.nodes,
                brokenUVGroup.links,
                "FLOOR",
                location=(-1100, -100),
                hide=True,
            ).node
            div = shader_nodes.math(
                brokenUVGroup.nodes,
                brokenUVGroup.links,
                "DIVIDE",
                location=(-950, -100),
                hide=True,
            ).node
            add2 = shader_nodes.math(
                brokenUVGroup.nodes,
                brokenUVGroup.links,
                "ADD",
                location=(-800, -100),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                add2.inputs, "Value_001"
            ).default_value = 1
            mul3 = shader_nodes.math(
                brokenUVGroup.nodes,
                brokenUVGroup.links,
                "MULTIPLY",
                location=(-650, -100),
                hide=True,
            ).node
            frac = shader_nodes.math(
                brokenUVGroup.nodes,
                brokenUVGroup.links,
                "FRACT",
                location=(-500, -100),
                hide=True,
            ).node
            clamp = create_node(brokenUVGroup.nodes, "ShaderNodeClamp", (-350, -100))
            lerp2 = create_node(
                brokenUVGroup.nodes, "ShaderNodeGroup", (-200, -100), label="lerp"
            )
            lerp2.node_tree = lerpG
            lerp2.inputs["A"].default_value = 1
            lerp2.inputs["B"].default_value = 4
            vecDiv = shader_nodes.vector_math(
                brokenUVGroup.nodes,
                brokenUVGroup.links,
                "DIVIDE",
                location=(-50, 0),
                hide=True,
            ).node

            brokenUVGroup.links.new(brokenUVGroupI.outputs["Time"], add.inputs["Value"])
            brokenUVGroup.links.new(add.outputs["Value"], mul.inputs["Value"])
            brokenUVGroup.links.new(mul.outputs["Value"], floor.inputs["Value"])
            brokenUVGroup.links.new(floor.outputs["Value"], hash12.inputs["vector"])
            brokenUVGroup.links.new(
                brokenUVGroupI.outputs["UV"], separate.inputs["Vector"]
            )
            brokenUVGroup.links.new(separate.outputs["X"], combine15.inputs["X"])
            brokenUVGroup.links.new(separate.outputs["X"], combine15.inputs["Y"])
            brokenUVGroup.links.new(
                combine15.outputs["Vector"], vecAdd2.inputs["Vector"]
            )
            brokenUVGroup.links.new(
                hash12.outputs["result"],
                shader_nodes.socket_by_identifier(vecAdd2.inputs, "Vector_001"),
            )
            brokenUVGroup.links.new(vecAdd2.outputs["Vector"], vecFrac.inputs["Vector"])
            brokenUVGroup.links.new(separate.outputs["X"], mul2.inputs["Value"])
            brokenUVGroup.links.new(
                brokenUVGroupI.outputs["rndBlocks"],
                shader_nodes.socket_by_identifier(mul2.inputs, "Value_001"),
            )
            brokenUVGroup.links.new(mul2.outputs["Value"], floor2.inputs["Value"])
            brokenUVGroup.links.new(floor2.outputs["Value"], div.inputs["Value"])
            brokenUVGroup.links.new(
                brokenUVGroupI.outputs["rndBlocks"],
                shader_nodes.socket_by_identifier(div.inputs, "Value_001"),
            )
            brokenUVGroup.links.new(div.outputs["Value"], add2.inputs["Value"])
            brokenUVGroup.links.new(add2.outputs["Value"], mul3.inputs["Value"])
            brokenUVGroup.links.new(
                brokenUVGroupI.outputs["Time"],
                shader_nodes.socket_by_identifier(mul3.inputs, "Value_001"),
            )
            brokenUVGroup.links.new(mul3.outputs["Value"], frac.inputs["Value"])
            brokenUVGroup.links.new(frac.outputs["Value"], clamp.inputs["Value"])
            brokenUVGroup.links.new(clamp.outputs["Result"], lerp2.inputs["t"])
            brokenUVGroup.links.new(vecFrac.outputs["Vector"], vecDiv.inputs["Vector"])
            brokenUVGroup.links.new(
                lerp2.outputs["result"],
                shader_nodes.socket_by_identifier(vecDiv.inputs, "Vector_001"),
            )
            brokenUVGroup.links.new(
                vecDiv.outputs["Vector"], brokenUVGroupO.inputs["brokenUV"]
            )

        brokenUV = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-1050, -500), label="brokenUV"
        )
        brokenUV.node_tree = brokenUVGroup

        CurMat.links.new(lerp.outputs["result"], brokenUV.inputs["rndBlocks"])
        CurMat.links.new(time.outputs["Value"], brokenUV.inputs["Time"])
        CurMat.links.new(UVMap.outputs["UV"], brokenUV.inputs["UV"])

        rndColorIGroup = bpy.data.node_groups.get("CP77 Opaque Screen rndColorIndex v1")
        if rndColorIGroup is None:
            rndColorIGroup = new_tracked_datablock(
                "node_groups", "CP77 Opaque Screen rndColorIndex v1", "ShaderNodeTree"
            )
            rndColorIGroup.interface.new_socket(
                name="rndBlocks", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            rndColorIGroup.interface.new_socket(
                name="Time", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            rndColorIGroup.interface.new_socket(
                name="brokenUV", socket_type="NodeSocketVector", in_out="INPUT"
            )
            rndColorIGroup.interface.new_socket(
                name="rndColorIndex", socket_type="NodeSocketFloat", in_out="OUTPUT"
            )

            rndColorIGroupI = create_node(
                rndColorIGroup.nodes, "NodeGroupInput", (-1400, 0)
            )
            rndColorIGroupO = create_node(
                rndColorIGroup.nodes, "NodeGroupOutput", (400, 0)
            )
            separate2 = create_node(
                rndColorIGroup.nodes, "ShaderNodeSeparateXYZ", (-1250, 0)
            )
            combine5 = create_node(
                rndColorIGroup.nodes, "ShaderNodeCombineXYZ", (-1100, 0)
            )
            vecMul = shader_nodes.vector_math(
                rndColorIGroup.nodes,
                rndColorIGroup.links,
                "MULTIPLY",
                location=(-950, 0),
                hide=True,
            ).node
            vecFloor = shader_nodes.vector_math(
                rndColorIGroup.nodes,
                rndColorIGroup.links,
                "FLOOR",
                location=(-800, 0),
                hide=True,
            ).node
            vecDiv2 = shader_nodes.vector_math(
                rndColorIGroup.nodes,
                rndColorIGroup.links,
                "DIVIDE",
                location=(-650, 0),
                hide=True,
            ).node
            frac6 = shader_nodes.math(
                rndColorIGroup.nodes,
                rndColorIGroup.links,
                "FRACT",
                location=(-500, -50),
                hide=True,
            ).node
            vecMul2 = shader_nodes.vector_math(
                rndColorIGroup.nodes,
                rndColorIGroup.links,
                "MULTIPLY",
                location=(-350, -25),
                hide=True,
            ).node
            vecSub = shader_nodes.vector_math(
                rndColorIGroup.nodes,
                rndColorIGroup.links,
                "SUBTRACT",
                location=(-200, -25),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                vecSub.inputs, "Vector_001"
            ).default_value = (0.1625, 0.1625, 0.1625)
            hash12G = screen_hash12_group()
            hash12_2 = create_node(
                rndColorIGroup.nodes, "ShaderNodeGroup", (-50, -25), label="hash12"
            )
            hash12_2.node_tree = hash12G
            mul9 = shader_nodes.math(
                rndColorIGroup.nodes,
                rndColorIGroup.links,
                "MULTIPLY",
                location=(100, -25),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                mul9.inputs, "Value_001"
            ).default_value = 4
            palette_index = shader_nodes.math(
                rndColorIGroup.nodes,
                rndColorIGroup.links,
                "FLOOR",
                location=(250, -25),
                hide=True,
            ).node
            rndColorIGroup.links.new(
                rndColorIGroupI.outputs["brokenUV"], separate2.inputs["Vector"]
            )
            rndColorIGroup.links.new(separate2.outputs["X"], combine5.inputs["X"])
            rndColorIGroup.links.new(separate2.outputs["X"], combine5.inputs["Y"])
            rndColorIGroup.links.new(
                combine5.outputs["Vector"], vecMul.inputs["Vector"]
            )
            rndColorIGroup.links.new(
                rndColorIGroupI.outputs["rndBlocks"],
                shader_nodes.socket_by_identifier(vecMul.inputs, "Vector_001"),
            )
            rndColorIGroup.links.new(
                vecMul.outputs["Vector"], vecFloor.inputs["Vector"]
            )
            rndColorIGroup.links.new(
                vecFloor.outputs["Vector"], vecDiv2.inputs["Vector"]
            )
            rndColorIGroup.links.new(
                rndColorIGroupI.outputs["rndBlocks"],
                shader_nodes.socket_by_identifier(vecDiv2.inputs, "Vector_001"),
            )
            rndColorIGroup.links.new(
                rndColorIGroupI.outputs["Time"], frac6.inputs["Value"]
            )
            rndColorIGroup.links.new(
                vecDiv2.outputs["Vector"], vecMul2.inputs["Vector"]
            )
            rndColorIGroup.links.new(
                frac6.outputs["Value"],
                shader_nodes.socket_by_identifier(vecMul2.inputs, "Vector_001"),
            )
            rndColorIGroup.links.new(vecMul2.outputs["Vector"], vecSub.inputs["Vector"])
            rndColorIGroup.links.new(
                vecSub.outputs["Vector"], hash12_2.inputs["vector"]
            )
            rndColorIGroup.links.new(hash12_2.outputs["result"], mul9.inputs["Value"])
            rndColorIGroup.links.new(
                mul9.outputs["Value"], palette_index.inputs["Value"]
            )
            rndColorIGroup.links.new(
                palette_index.outputs["Value"], rndColorIGroupO.inputs["rndColorIndex"]
            )

        rndColorIndex = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-900, -475), label="rndColorIndex"
        )
        rndColorIndex.node_tree = rndColorIGroup
        CurMat.links.new(lerp.outputs["result"], rndColorIndex.inputs["rndBlocks"])
        CurMat.links.new(time.outputs["Value"], rndColorIndex.inputs["Time"])
        CurMat.links.new(brokenUV.outputs["brokenUV"], rndColorIndex.inputs["brokenUV"])

        rndColorGroup = bpy.data.node_groups.get("CP77 Opaque Screen rndColor v1")
        if rndColorGroup is None:
            rndColorGroup = new_tracked_datablock(
                "node_groups", "CP77 Opaque Screen rndColor v1", "ShaderNodeTree"
            )
            rndColorGroup.interface.new_socket(
                name="rndColorIndex", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            rndColorGroup.interface.new_socket(
                name="rndColor", socket_type="NodeSocketColor", in_out="OUTPUT"
            )

            rndColorGroupI = create_node(
                rndColorGroup.nodes, "NodeGroupInput", (-1400, 0)
            )
            rndColorGroupO = create_node(
                rndColorGroup.nodes, "NodeGroupOutput", (200, 0)
            )
            compare = shader_nodes.math(
                rndColorGroup.nodes,
                rndColorGroup.links,
                "COMPARE",
                location=(-1100, 150),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                compare.inputs, "Value_001"
            ).default_value = 0
            shader_nodes.socket_by_identifier(
                compare.inputs, "Value_002"
            ).default_value = 0
            compare2 = shader_nodes.math(
                rndColorGroup.nodes,
                rndColorGroup.links,
                "COMPARE",
                location=(-1100, 50),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                compare2.inputs, "Value_001"
            ).default_value = 1
            shader_nodes.socket_by_identifier(
                compare2.inputs, "Value_002"
            ).default_value = 0
            compare3 = shader_nodes.math(
                rndColorGroup.nodes,
                rndColorGroup.links,
                "COMPARE",
                location=(-1100, -50),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                compare3.inputs, "Value_001"
            ).default_value = 2
            shader_nodes.socket_by_identifier(
                compare3.inputs, "Value_002"
            ).default_value = 0
            compare4 = shader_nodes.math(
                rndColorGroup.nodes,
                rndColorGroup.links,
                "COMPARE",
                location=(-1100, -150),
                hide=True,
            ).node
            shader_nodes.socket_by_identifier(
                compare4.inputs, "Value_001"
            ).default_value = 3
            shader_nodes.socket_by_identifier(
                compare4.inputs, "Value_002"
            ).default_value = 0
            combine5 = create_node(
                rndColorGroup.nodes, "ShaderNodeCombineXYZ", (-900, 175)
            )
            combine5.inputs["X"].default_value = 1
            combine5.inputs["Y"].default_value = 1
            combine5.inputs["Z"].default_value = 1
            combine6 = create_node(
                rndColorGroup.nodes, "ShaderNodeCombineXYZ", (-900, 75)
            )
            combine6.inputs["X"].default_value = 0.2
            combine6.inputs["Y"].default_value = 0
            combine6.inputs["Z"].default_value = 0
            combine7 = create_node(
                rndColorGroup.nodes, "ShaderNodeCombineXYZ", (-900, -25)
            )
            combine7.inputs["X"].default_value = 0
            combine7.inputs["Y"].default_value = 1
            combine7.inputs["Z"].default_value = 0
            combine8 = create_node(
                rndColorGroup.nodes, "ShaderNodeCombineXYZ", (-900, -125)
            )
            combine8.inputs["X"].default_value = 0
            combine8.inputs["Y"].default_value = 0
            combine8.inputs["Z"].default_value = 1
            vecMul3 = shader_nodes.vector_math(
                rndColorGroup.nodes,
                rndColorGroup.links,
                "MULTIPLY",
                location=(-700, 150),
                hide=True,
            ).node
            vecMul4 = shader_nodes.vector_math(
                rndColorGroup.nodes,
                rndColorGroup.links,
                "MULTIPLY",
                location=(-700, 50),
                hide=True,
            ).node
            vecMul5 = shader_nodes.vector_math(
                rndColorGroup.nodes,
                rndColorGroup.links,
                "MULTIPLY",
                location=(-700, -50),
                hide=True,
            ).node
            vecMul6 = shader_nodes.vector_math(
                rndColorGroup.nodes,
                rndColorGroup.links,
                "MULTIPLY",
                location=(-700, -150),
                hide=True,
            ).node
            vecAdd3 = shader_nodes.vector_math(
                rndColorGroup.nodes,
                rndColorGroup.links,
                "ADD",
                location=(-500, 100),
                hide=True,
            ).node
            vecAdd4 = shader_nodes.vector_math(
                rndColorGroup.nodes,
                rndColorGroup.links,
                "ADD",
                location=(-500, -100),
                hide=True,
            ).node
            vecAdd5 = shader_nodes.vector_math(
                rndColorGroup.nodes,
                rndColorGroup.links,
                "ADD",
                location=(-300, 0),
                hide=True,
            ).node
            rndColorGroup.links.new(
                rndColorGroupI.outputs["rndColorIndex"], compare.inputs["Value"]
            )
            rndColorGroup.links.new(
                rndColorGroupI.outputs["rndColorIndex"], compare2.inputs["Value"]
            )
            rndColorGroup.links.new(
                rndColorGroupI.outputs["rndColorIndex"], compare3.inputs["Value"]
            )
            rndColorGroup.links.new(
                rndColorGroupI.outputs["rndColorIndex"], compare4.inputs["Value"]
            )
            rndColorGroup.links.new(
                compare.outputs["Value"],
                shader_nodes.socket_by_identifier(vecMul3.inputs, "Vector_001"),
            )
            rndColorGroup.links.new(
                compare2.outputs["Value"],
                shader_nodes.socket_by_identifier(vecMul4.inputs, "Vector_001"),
            )
            rndColorGroup.links.new(
                compare3.outputs["Value"],
                shader_nodes.socket_by_identifier(vecMul5.inputs, "Vector_001"),
            )
            rndColorGroup.links.new(
                compare4.outputs["Value"],
                shader_nodes.socket_by_identifier(vecMul6.inputs, "Vector_001"),
            )
            rndColorGroup.links.new(
                combine5.outputs["Vector"], vecMul3.inputs["Vector"]
            )
            rndColorGroup.links.new(
                combine6.outputs["Vector"], vecMul4.inputs["Vector"]
            )
            rndColorGroup.links.new(
                combine7.outputs["Vector"], vecMul5.inputs["Vector"]
            )
            rndColorGroup.links.new(
                combine8.outputs["Vector"], vecMul6.inputs["Vector"]
            )
            rndColorGroup.links.new(vecMul3.outputs["Vector"], vecAdd3.inputs["Vector"])
            rndColorGroup.links.new(
                vecMul4.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecAdd3.inputs, "Vector_001"),
            )
            rndColorGroup.links.new(vecMul5.outputs["Vector"], vecAdd4.inputs["Vector"])
            rndColorGroup.links.new(
                vecMul6.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecAdd4.inputs, "Vector_001"),
            )
            rndColorGroup.links.new(vecAdd3.outputs["Vector"], vecAdd5.inputs["Vector"])
            rndColorGroup.links.new(
                vecAdd4.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecAdd5.inputs, "Vector_001"),
            )
            rndColorGroup.links.new(
                vecAdd5.outputs["Vector"], rndColorGroupO.inputs["rndColor"]
            )

        rndColor = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-750, -475), label="rndColor"
        )
        rndColor.node_tree = rndColorGroup

        CurMat.links.new(
            rndColorIndex.outputs["rndColorIndex"], rndColor.inputs["rndColorIndex"]
        )

        hash12G = screen_hash12_group()
        hash12 = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-1550, -550), label="hash12"
        )
        hash12.node_tree = hash12G
        combine9 = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-1700, -550))
        CurMat.links.new(time.outputs["Value"], combine9.inputs["X"])
        CurMat.links.new(time.outputs["Value"], combine9.inputs["Y"])
        CurMat.links.new(combine9.outputs["Vector"], hash12.inputs["vector"])

        rndOffGroup = bpy.data.node_groups.get("CP77 Opaque Screen rndOff_bundle_v2 v1")
        if rndOffGroup is None:
            rndOffGroup = new_tracked_datablock(
                "node_groups",
                "CP77 Opaque Screen rndOff_bundle_v2 v1",
                "ShaderNodeTree",
            )
            rndOffGroup.interface.new_socket(
                name="Range", socket_type="NodeSocketBundle", in_out="OUTPUT"
            )

            rndOffGroupO = create_node(rndOffGroup.nodes, "NodeGroupOutput", (200, 0))
            range_bundle = combine_bundle_node(
                rndOffGroup,
                _RANDOM_OFFSET_BUNDLE_ITEMS,
                (-100, 0),
                name="CP77 Random Offset Range",
                label="Random Offset Range",
            )
            range_bundle.inputs["Min X"].default_value = -0.01
            range_bundle.inputs["Max X"].default_value = 0.015
            range_bundle.inputs["Min Y"].default_value = -0.02
            range_bundle.inputs["Max Y"].default_value = 0.01
            rndOffGroup.links.new(
                range_bundle.outputs["Bundle"], rndOffGroupO.inputs["Range"]
            )

        rndOff = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-1550, -600), label="rndOff"
        )
        rndOff.node_tree = rndOffGroup

        randomOffsetGroup = bpy.data.node_groups.get(
            "CP77 Opaque Screen randomOffset_bundle_v2 v2"
        )
        if randomOffsetGroup is None:
            randomOffsetGroup = new_tracked_datablock(
                "node_groups",
                "CP77 Opaque Screen randomOffset_bundle_v2 v2",
                "ShaderNodeTree",
            )
            randomOffsetGroup.interface.new_socket(
                name="rand", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            randomOffsetGroup.interface.new_socket(
                name="Range", socket_type="NodeSocketBundle", in_out="INPUT"
            )
            randomOffsetGroup.interface.new_socket(
                name="randomOffset", socket_type="NodeSocketVector", in_out="OUTPUT"
            )
            randomOffsetGroupI = create_node(
                randomOffsetGroup.nodes, "NodeGroupInput", (-600, 0)
            )
            randomOffsetGroupO = create_node(
                randomOffsetGroup.nodes, "NodeGroupOutput", (200, 0)
            )
            range_values = separate_bundle_node(
                randomOffsetGroup,
                _RANDOM_OFFSET_BUNDLE_ITEMS,
                (-450, -100),
                name="CP77 Random Offset Range",
                label="Random Offset Range",
            )
            randomOffsetGroup.links.new(
                randomOffsetGroupI.outputs["Range"], range_values.inputs["Bundle"]
            )
            lerp3 = create_node(
                randomOffsetGroup.nodes, "ShaderNodeGroup", (-200, 0), label="lerp"
            )
            lerp3.node_tree = lerpG
            lerp4 = create_node(
                randomOffsetGroup.nodes, "ShaderNodeGroup", (-200, -50), label="lerp"
            )
            lerp4.node_tree = lerpG
            combine10 = create_node(
                randomOffsetGroup.nodes, "ShaderNodeCombineXYZ", (0, -25)
            )
            randomOffsetGroup.links.new(
                range_values.outputs["Min X"], lerp3.inputs["A"]
            )
            randomOffsetGroup.links.new(
                range_values.outputs["Max X"], lerp3.inputs["B"]
            )
            randomOffsetGroup.links.new(
                randomOffsetGroupI.outputs["rand"], lerp3.inputs["t"]
            )
            randomOffsetGroup.links.new(
                range_values.outputs["Min Y"], lerp4.inputs["A"]
            )
            randomOffsetGroup.links.new(
                range_values.outputs["Max Y"], lerp4.inputs["B"]
            )
            randomOffsetGroup.links.new(
                randomOffsetGroupI.outputs["rand"], lerp4.inputs["t"]
            )
            randomOffsetGroup.links.new(lerp3.outputs["result"], combine10.inputs["X"])
            randomOffsetGroup.links.new(lerp4.outputs["result"], combine10.inputs["Y"])
            randomOffsetGroup.links.new(
                combine10.outputs["Vector"], randomOffsetGroupO.inputs["randomOffset"]
            )

        randomOffset = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-1350, -575), label="randomOffset"
        )
        randomOffset.node_tree = randomOffsetGroup

        CurMat.links.new(hash12.outputs["result"], randomOffset.inputs["rand"])
        CurMat.links.new(rndOff.outputs["Range"], randomOffset.inputs["Range"])

        newRandomOffsetGroup = bpy.data.node_groups.get(
            "CP77 Opaque Screen newRandomOffset v2"
        )
        if newRandomOffsetGroup is None:
            newRandomOffsetGroup = new_tracked_datablock(
                "node_groups", "CP77 Opaque Screen newRandomOffset v2", "ShaderNodeTree"
            )
            newRandomOffsetGroup.interface.new_socket(
                name="rand", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            newRandomOffsetGroup.interface.new_socket(
                name="randomOffset", socket_type="NodeSocketVector", in_out="INPUT"
            )
            newRandomOffsetGroup.interface.new_socket(
                name="newRandomOffset", socket_type="NodeSocketVector", in_out="OUTPUT"
            )

            newRandomOffsetGroupI = create_node(
                newRandomOffsetGroup.nodes, "NodeGroupInput", (-800, 0)
            )
            newRandomOffsetGroupO = create_node(
                newRandomOffsetGroup.nodes, "NodeGroupOutput", (200, 0)
            )
            stepG = self.createStepGroup()
            step = create_node(
                newRandomOffsetGroup.nodes, "ShaderNodeGroup", (-200, 0), label="step"
            )
            step.node_tree = stepG
            step.inputs["y"].default_value = 0.7
            vecLerp = create_node(
                newRandomOffsetGroup.nodes, "ShaderNodeGroup", (0, 0), label="lerp"
            )
            vecLerp.node_tree = vecLerpG
            vecLerp.inputs["A"].default_value = (0.01, -0.01, 0)
            newRandomOffsetGroup.links.new(
                newRandomOffsetGroupI.outputs["rand"], step.inputs["x"]
            )
            newRandomOffsetGroup.links.new(
                newRandomOffsetGroupI.outputs["randomOffset"], vecLerp.inputs["B"]
            )
            newRandomOffsetGroup.links.new(step.outputs["result"], vecLerp.inputs["t"])
            newRandomOffsetGroup.links.new(
                vecLerp.outputs["result"],
                newRandomOffsetGroupO.inputs["newRandomOffset"],
            )

        newRandomOffset = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-1200, -575), label="newRandomOffset"
        )
        newRandomOffset.node_tree = newRandomOffsetGroup
        CurMat.links.new(hash12.outputs["result"], newRandomOffset.inputs["rand"])
        CurMat.links.new(
            randomOffset.outputs["randomOffset"], newRandomOffset.inputs["randomOffset"]
        )

        l1Group = _create_l1_group()
        l1 = add_group_node(CurMat, l1Group, (-950, 300), label="l1")
        CurMat.links.new(vecAdd.outputs["Vector"], l1.inputs["newUV"])

        l2Group = _create_layer_uv_group(2)
        l2 = add_group_node(CurMat, l2Group, (-950, 250), label="l2")
        CurMat.links.new(vecAdd.outputs["Vector"], l2.inputs["newUV"])
        CurMat.links.new(combine.outputs["Vector"], l2.inputs["modUV"])
        CurMat.links.new(layersSeparation.outputs["Value"], l2.inputs["l2"])

        l3Group = _create_layer_uv_group(3)
        l3 = add_group_node(CurMat, l3Group, (-950, 200), label="l3")
        CurMat.links.new(vecAdd.outputs["Vector"], l3.inputs["newUV"])
        CurMat.links.new(combine.outputs["Vector"], l3.inputs["modUV"])
        CurMat.links.new(
            layersSeparation.outputs["Value"], l3.inputs["LayersSeparation"]
        )

        if parImg is not None:
            i1 = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-800, 300),
                label="i1",
                image=parImg,
            )
            self._slot_image("parImg", i1)
            colorlessTexG = self.colorlessTexGroup()
            colorlessTex = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-550, 300), label="colorlessTex"
            )
            colorlessTex.node_tree = colorlessTexG
            CurMat.links.new(l1.outputs["l1"], i1.inputs["Vector"])
            CurMat.links.new(i1.outputs["Color"], colorlessTex.inputs["Color"])

        if parImg is not None:
            i2Color, _ = create_mip_sampled_texture(
                CurMat,
                parImg,
                l2.outputs["newRandomOffset"],
                _LAYER_MIP_LEVELS[2],
                taps=_LAYER_MIP_TAPS,
                location=(-800, 250),
                label="i2",
            )
            colorlessTex2 = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-550, 250), label="colorlessTex"
            )
            colorlessTex2.node_tree = colorlessTexG
            if i2Color is not None:
                CurMat.links.new(i2Color, colorlessTex2.inputs["Color"])
                slots["mip:2"] = i2Color.node.name

        if parImg is not None:
            i3Color, _ = create_mip_sampled_texture(
                CurMat,
                parImg,
                l3.outputs["l3"],
                _LAYER_MIP_LEVELS[3],
                taps=_LAYER_MIP_TAPS,
                location=(-800, 200),
                label="i3",
            )
            colorlessTex3 = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-550, 200), label="colorlessTex"
            )
            colorlessTex3.node_tree = colorlessTexG
            if i3Color is not None:
                CurMat.links.new(i3Color, colorlessTex3.inputs["Color"])
                slots["mip:3"] = i3Color.node.name

        if blinkImg is not None:
            iA = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-800, 350),
                label="iA",
                image=blinkImg,
            )
            self._slot_image("blinkImg", iA)

            CurMat.links.new(l1.outputs["l1"], iA.inputs["Vector"])

        bl1Group = _create_blink_group()

        bl1 = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-350, 325), label="if BlinkingSpeed > 0"
        )
        bl1.node_tree = bl1Group
        bl1.inputs["iA"].default_value = (0.0, 0.0, 0.0, 1.0)
        bl1.inputs["i1"].default_value = (0.0, 0.0, 0.0, 1.0)
        CurMat.links.new(blinkingSpeed.outputs["Value"], bl1.inputs["BlinkingSpeed"])
        CurMat.links.new(time.outputs["Value"], bl1.inputs["time"])
        if blinkImg is not None:
            CurMat.links.new(iA.outputs["Color"], bl1.inputs["iA"])
        if parImg is not None:
            CurMat.links.new(colorlessTex.outputs["Color"], bl1.inputs["i1"])

        scanlineUVGroup = bpy.data.node_groups.get("CP77 Opaque Screen scanlineUV v1")
        if scanlineUVGroup is None:
            scanlineUVGroup = new_tracked_datablock(
                "node_groups", "CP77 Opaque Screen scanlineUV v1", "ShaderNodeTree"
            )
            scanlineUVGroup.interface.new_socket(
                name="ScanlinesDensity", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            scanlineUVGroup.interface.new_socket(
                name="time", socket_type="NodeSocketFloat", in_out="INPUT"
            )
            scanlineUVGroup.interface.new_socket(
                name="UV", socket_type="NodeSocketVector", in_out="INPUT"
            )
            scanlineUVGroup.interface.new_socket(
                name="scanlineUV", socket_type="NodeSocketVector", in_out="OUTPUT"
            )

            scanlineUVGroupI = create_node(
                scanlineUVGroup.nodes, "NodeGroupInput", (-1050, 0)
            )
            scanlineUVGroupO = create_node(
                scanlineUVGroup.nodes, "NodeGroupOutput", (300, 0)
            )
            combine16 = create_node(
                scanlineUVGroup.nodes, "ShaderNodeCombineXYZ", (-900, 100)
            )
            combine16.inputs["X"].default_value = 1
            vecMul11 = shader_nodes.vector_math(
                scanlineUVGroup.nodes,
                scanlineUVGroup.links,
                "MULTIPLY",
                location=(-750, 100),
                hide=True,
            ).node
            combine17 = create_node(
                scanlineUVGroup.nodes, "ShaderNodeCombineXYZ", (-900, 50)
            )
            combine17.inputs["X"].default_value = 2
            combine17.inputs["Y"].default_value = 2
            vecMul12 = shader_nodes.vector_math(
                scanlineUVGroup.nodes,
                scanlineUVGroup.links,
                "MULTIPLY",
                location=(-750, 50),
                hide=True,
            ).node
            vecAdd9 = shader_nodes.vector_math(
                scanlineUVGroup.nodes,
                scanlineUVGroup.links,
                "ADD",
                location=(-600, 75),
                hide=True,
            ).node
            scanlineUVGroup.links.new(
                scanlineUVGroupI.outputs["ScanlinesDensity"], combine16.inputs["Y"]
            )
            scanlineUVGroup.links.new(
                scanlineUVGroupI.outputs["UV"], vecMul11.inputs["Vector"]
            )
            scanlineUVGroup.links.new(
                combine16.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecMul11.inputs, "Vector_001"),
            )
            scanlineUVGroup.links.new(
                combine17.outputs["Vector"], vecMul12.inputs["Vector"]
            )
            scanlineUVGroup.links.new(
                scanlineUVGroupI.outputs["time"],
                shader_nodes.socket_by_identifier(vecMul12.inputs, "Vector_001"),
            )
            scanlineUVGroup.links.new(
                vecMul11.outputs["Vector"], vecAdd9.inputs["Vector"]
            )
            scanlineUVGroup.links.new(
                vecMul12.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecAdd9.inputs, "Vector_001"),
            )
            scanlineUVGroup.links.new(
                vecAdd9.outputs["Vector"], scanlineUVGroupO.inputs["scanlineUV"]
            )

        scanlineUV = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-950, 100), label="scanlineUV"
        )
        scanlineUV.node_tree = scanlineUVGroup
        CurMat.links.new(
            scanlinesDensity.outputs["Value"], scanlineUV.inputs["ScanlinesDensity"]
        )
        CurMat.links.new(time.outputs["Value"], scanlineUV.inputs["time"])
        CurMat.links.new(UVMap.outputs["UV"], scanlineUV.inputs["UV"])

        scanlineTexture = create_node(
            CurMat.nodes,
            "ShaderNodeTexImage",
            (-800, 100),
            label="ScanlineTexture",
            image=scanLineImg,
        )
        self._slot_image("scanLineImg", scanlineTexture)
        separate7 = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (-550, 100))
        CurMat.links.new(
            scanlineUV.outputs["scanlineUV"], scanlineTexture.inputs["Vector"]
        )
        CurMat.links.new(scanlineTexture.outputs["Color"], separate7.inputs["Vector"])

        lerp5 = create_node(CurMat.nodes, "ShaderNodeGroup", (-400, 100), label="lerp")
        lerp5.node_tree = lerpG
        lerp5.inputs["B"].default_value = 1
        CurMat.links.new(scanlinesIntensity.outputs["Value"], lerp5.inputs["A"])
        CurMat.links.new(separate7.outputs["X"], lerp5.inputs["t"])

        vecMul13 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-950, 25), hide=True
        ).node
        CurMat.links.new(bl1.outputs["new_i1"], vecMul13.inputs["Vector"])
        CurMat.links.new(
            intensityPerLayer_x.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMul13.inputs, "Vector_001"),
        )

        vecMul14 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-950, -25), hide=True
        ).node
        vecMul15 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-800, -25), hide=True
        ).node
        if parImg is not None:
            CurMat.links.new(colorlessTex2.outputs["Color"], vecMul14.inputs["Vector"])
        CurMat.links.new(
            intensityPerLayer_y.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMul14.inputs, "Vector_001"),
        )
        CurMat.links.new(vecMul14.outputs["Vector"], vecMul15.inputs["Vector"])
        CurMat.links.new(
            lerp5.outputs["result"],
            shader_nodes.socket_by_identifier(vecMul15.inputs, "Vector_001"),
        )

        vecMul16 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-950, -75), hide=True
        ).node
        vecMul17 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-800, -75), hide=True
        ).node
        if parImg is not None:
            CurMat.links.new(colorlessTex3.outputs["Color"], vecMul16.inputs["Vector"])
        CurMat.links.new(
            intensityPerLayer_z.outputs["Value"],
            shader_nodes.socket_by_identifier(vecMul16.inputs, "Vector_001"),
        )
        CurMat.links.new(vecMul16.outputs["Vector"], vecMul17.inputs["Vector"])
        CurMat.links.new(
            lerp5.outputs["result"],
            shader_nodes.socket_by_identifier(vecMul17.inputs, "Vector_001"),
        )

        m2Group = bpy.data.node_groups.get("CP77 Opaque Screen parallax_screen_m2 v1")
        if m2Group is None:
            m2Group = new_tracked_datablock(
                "node_groups",
                "CP77 Opaque Screen parallax_screen_m2 v1",
                "ShaderNodeTree",
            )
            m2Group.interface.new_socket(
                name="i3", socket_type="NodeSocketVector", in_out="INPUT"
            )
            m2Group.interface.new_socket(
                name="i2", socket_type="NodeSocketVector", in_out="INPUT"
            )
            m2Group.interface.new_socket(
                name="m2", socket_type="NodeSocketVector", in_out="OUTPUT"
            )

            m2GroupI = create_node(m2Group.nodes, "NodeGroupInput", (-1050, 0))
            m2GroupO = create_node(m2Group.nodes, "NodeGroupOutput", (300, 0))
            vecSub2 = shader_nodes.vector_math(
                m2Group.nodes, m2Group.links, "SUBTRACT", location=(-900, 25), hide=True
            ).node
            vecSub2.inputs["Vector"].default_value = (1, 1, 1)
            vecSub3 = shader_nodes.vector_math(
                m2Group.nodes,
                m2Group.links,
                "SUBTRACT",
                location=(-900, -25),
                hide=True,
            ).node
            vecSub3.inputs["Vector"].default_value = (1, 1, 1)
            vecMul18 = shader_nodes.vector_math(
                m2Group.nodes, m2Group.links, "MULTIPLY", location=(-750, 0), hide=True
            ).node
            vecSub4 = shader_nodes.vector_math(
                m2Group.nodes, m2Group.links, "SUBTRACT", location=(-600, 0), hide=True
            ).node
            vecSub4.inputs["Vector"].default_value = (1, 1, 1)
            m2Group.links.new(
                m2GroupI.outputs["i3"],
                shader_nodes.socket_by_identifier(vecSub2.inputs, "Vector_001"),
            )
            m2Group.links.new(
                m2GroupI.outputs["i2"],
                shader_nodes.socket_by_identifier(vecSub3.inputs, "Vector_001"),
            )
            m2Group.links.new(vecSub2.outputs["Vector"], vecMul18.inputs["Vector"])
            m2Group.links.new(
                vecSub3.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecMul18.inputs, "Vector_001"),
            )
            m2Group.links.new(
                vecMul18.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecSub4.inputs, "Vector_001"),
            )
            m2Group.links.new(vecSub4.outputs["Vector"], m2GroupO.inputs["m2"])

        m2 = create_node(CurMat.nodes, "ShaderNodeGroup", (-650, -25), label="m2")
        m2.node_tree = m2Group
        CurMat.links.new(vecMul17.outputs["Vector"], m2.inputs["i3"])
        CurMat.links.new(vecMul15.outputs["Vector"], m2.inputs["i2"])

        m3Group = bpy.data.node_groups.get("CP77 Opaque Screen parallax_screen_m3 v1")
        if m3Group is None:
            m3Group = new_tracked_datablock(
                "node_groups",
                "CP77 Opaque Screen parallax_screen_m3 v1",
                "ShaderNodeTree",
            )
            m3Group.interface.new_socket(
                name="m2", socket_type="NodeSocketVector", in_out="INPUT"
            )
            m3Group.interface.new_socket(
                name="i1", socket_type="NodeSocketVector", in_out="INPUT"
            )
            m3Group.interface.new_socket(
                name="m3", socket_type="NodeSocketVector", in_out="OUTPUT"
            )

            m3GroupI = create_node(m3Group.nodes, "NodeGroupInput", (-1050, 0))
            m3GroupO = create_node(m3Group.nodes, "NodeGroupOutput", (300, 0))
            vecSub5 = shader_nodes.vector_math(
                m3Group.nodes, m3Group.links, "SUBTRACT", location=(-900, 25), hide=True
            ).node
            vecSub5.inputs["Vector"].default_value = (1, 1, 1)
            vecSub6 = shader_nodes.vector_math(
                m3Group.nodes,
                m3Group.links,
                "SUBTRACT",
                location=(-900, -25),
                hide=True,
            ).node
            vecSub6.inputs["Vector"].default_value = (1, 1, 1)
            vecMul19 = shader_nodes.vector_math(
                m3Group.nodes, m3Group.links, "MULTIPLY", location=(-750, 0), hide=True
            ).node
            vecSub7 = shader_nodes.vector_math(
                m3Group.nodes, m3Group.links, "SUBTRACT", location=(-600, 0), hide=True
            ).node
            vecSub7.inputs["Vector"].default_value = (1, 1, 1)
            m3Group.links.new(
                m3GroupI.outputs["m2"],
                shader_nodes.socket_by_identifier(vecSub5.inputs, "Vector_001"),
            )
            m3Group.links.new(
                m3GroupI.outputs["i1"],
                shader_nodes.socket_by_identifier(vecSub6.inputs, "Vector_001"),
            )
            m3Group.links.new(vecSub5.outputs["Vector"], vecMul19.inputs["Vector"])
            m3Group.links.new(
                vecSub6.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecMul19.inputs, "Vector_001"),
            )
            m3Group.links.new(
                vecMul19.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecSub7.inputs, "Vector_001"),
            )
            m3Group.links.new(vecSub7.outputs["Vector"], m3GroupO.inputs["m3"])
        m3 = create_node(CurMat.nodes, "ShaderNodeGroup", (-500, -25), label="m3")
        m3.node_tree = m3Group
        CurMat.links.new(m2.outputs["m2"], m3.inputs["m2"])
        CurMat.links.new(vecMul13.outputs["Vector"], m3.inputs["i1"])

        separate8 = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (-1150, -125))
        greaterThan = shader_nodes.math(
            CurMat.nodes, CurMat.links, "GREATER_THAN", location=(-950, -125), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            greaterThan.inputs, "Value_001"
        ).default_value = 0.02
        lessThan = shader_nodes.math(
            CurMat.nodes, CurMat.links, "LESS_THAN", location=(-950, -175), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            lessThan.inputs, "Value_001"
        ).default_value = 0.12
        minimum = shader_nodes.math(
            CurMat.nodes, CurMat.links, "MINIMUM", location=(-800, -150), hide=True
        ).node
        greaterThan2 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "GREATER_THAN", location=(-950, -225), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            greaterThan2.inputs, "Value_001"
        ).default_value = 0.28
        lessThan2 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "LESS_THAN", location=(-950, -275), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            lessThan2.inputs, "Value_001"
        ).default_value = 0.543
        minimum2 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "MINIMUM", location=(-800, -250), hide=True
        ).node
        greaterThan3 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "GREATER_THAN", location=(-950, -325), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            greaterThan3.inputs, "Value_001"
        ).default_value = 0.78
        lessThan3 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "LESS_THAN", location=(-950, -375), hide=True
        ).node
        shader_nodes.socket_by_identifier(
            lessThan3.inputs, "Value_001"
        ).default_value = 0.85
        minimum3 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "MINIMUM", location=(-800, -350), hide=True
        ).node
        add10 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "ADD", location=(-650, -200), hide=True
        ).node
        add11 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "ADD", location=(-650, -300), hide=True
        ).node
        mixRGB2 = create_node(CurMat.nodes, "ShaderNodeMix", (-600, -475))
        mixRGB2.data_type = "RGBA"
        shader_nodes.socket_by_identifier(mixRGB2.inputs, "A_Color").default_value = (
            0,
            0,
            0,
            0,
        )
        CurMat.links.new(UVMap.outputs["UV"], separate8.inputs["Vector"])
        CurMat.links.new(separate8.outputs["X"], greaterThan.inputs["Value"])
        CurMat.links.new(separate8.outputs["X"], lessThan.inputs["Value"])
        CurMat.links.new(greaterThan.outputs["Value"], minimum.inputs["Value"])
        CurMat.links.new(
            lessThan.outputs["Value"],
            shader_nodes.socket_by_identifier(minimum.inputs, "Value_001"),
        )
        CurMat.links.new(separate8.outputs["X"], greaterThan2.inputs["Value"])
        CurMat.links.new(separate8.outputs["X"], lessThan2.inputs["Value"])
        CurMat.links.new(greaterThan2.outputs["Value"], minimum2.inputs["Value"])
        CurMat.links.new(
            lessThan2.outputs["Value"],
            shader_nodes.socket_by_identifier(minimum2.inputs, "Value_001"),
        )
        CurMat.links.new(separate8.outputs["X"], greaterThan3.inputs["Value"])
        CurMat.links.new(separate8.outputs["X"], lessThan3.inputs["Value"])
        CurMat.links.new(greaterThan3.outputs["Value"], minimum3.inputs["Value"])
        CurMat.links.new(
            lessThan3.outputs["Value"],
            shader_nodes.socket_by_identifier(minimum3.inputs, "Value_001"),
        )
        CurMat.links.new(minimum.outputs["Value"], add10.inputs["Value"])
        CurMat.links.new(
            minimum2.outputs["Value"],
            shader_nodes.socket_by_identifier(add10.inputs, "Value_001"),
        )
        CurMat.links.new(add10.outputs["Value"], add11.inputs["Value"])
        CurMat.links.new(
            minimum3.outputs["Value"],
            shader_nodes.socket_by_identifier(add11.inputs, "Value_001"),
        )
        CurMat.links.new(
            rndColor.outputs["rndColor"],
            shader_nodes.socket_by_identifier(mixRGB2.inputs, "B_Color"),
        )
        CurMat.links.new(
            add11.outputs["Value"],
            shader_nodes.socket_by_identifier(mixRGB2.inputs, "Factor_Float"),
        )

        if parImg is not None:
            parTex = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-900, -525),
                label="ParalaxTexture",
                image=parImg,
            )
            self._slot_image("parImg", parTex)
            CurMat.links.new(brokenUV.outputs["brokenUV"], parTex.inputs["Vector"])
            colorlessTex4 = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-650, -525), label="colorlessTex"
            )
            colorlessTex4.node_tree = colorlessTexG
            CurMat.links.new(parTex.outputs["Color"], colorlessTex4.inputs["Color"])
            vecMul20 = shader_nodes.vector_math(
                CurMat.nodes, CurMat.links, "MULTIPLY", location=(-500, -550), hide=True
            ).node
            CurMat.links.new(
                shader_nodes.socket_by_identifier(mixRGB2.outputs, "Result_Color"),
                vecMul20.inputs["Vector"],
            )
            CurMat.links.new(
                colorlessTex4.outputs["Color"],
                shader_nodes.socket_by_identifier(vecMul20.inputs, "Vector_001"),
            )

        if parImg is not None:
            parTex2 = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-900, -575),
                label="ParalaxTexture",
                image=parImg,
            )
            self._slot_image("parImg", parTex2)
            colorlessTex6 = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-650, -575), label="colorlessTex"
            )
            colorlessTex6.node_tree = colorlessTexG
            CurMat.links.new(parTex2.outputs["Color"], colorlessTex6.inputs["Color"])
            vecAdd10 = shader_nodes.vector_math(
                CurMat.nodes, CurMat.links, "ADD", location=(-1050, -575), hide=True
            ).node
            vecMul21 = shader_nodes.vector_math(
                CurMat.nodes, CurMat.links, "MULTIPLY", location=(-500, -600), hide=True
            ).node
            vecMul21.inputs["Vector"].default_value = (0.4, 0.4, 0.4)
            vecAdd11 = shader_nodes.vector_math(
                CurMat.nodes, CurMat.links, "ADD", location=(-350, -512.5), hide=True
            ).node

        if parImg is not None:
            CurMat.links.new(vecAdd.outputs["Vector"], vecAdd10.inputs["Vector"])
            CurMat.links.new(
                newRandomOffset.outputs["newRandomOffset"],
                shader_nodes.socket_by_identifier(vecAdd10.inputs, "Vector_001"),
            )
            CurMat.links.new(vecAdd10.outputs["Vector"], parTex2.inputs["Vector"])
            CurMat.links.new(
                colorlessTex6.outputs["Color"],
                shader_nodes.socket_by_identifier(vecMul21.inputs, "Vector_001"),
            )
            CurMat.links.new(vecMul20.outputs["Vector"], vecAdd11.inputs["Vector"])
            CurMat.links.new(
                vecMul21.outputs["Vector"],
                shader_nodes.socket_by_identifier(vecAdd11.inputs, "Vector_001"),
            )

        mixRGB3 = create_node(CurMat.nodes, "ShaderNodeMix", (-350, -25))
        mixRGB3.data_type = "RGBA"
        mixRGB4 = create_node(CurMat.nodes, "ShaderNodeMix", (-350, -75))
        mixRGB4.data_type = "RGBA"
        CurMat.links.new(
            isBroken.outputs["Value"],
            shader_nodes.socket_by_identifier(mixRGB3.inputs, "Factor_Float"),
        )
        CurMat.links.new(
            m3.outputs["m3"],
            shader_nodes.socket_by_identifier(mixRGB3.inputs, "A_Color"),
        )
        if parImg is not None:
            CurMat.links.new(
                vecAdd11.outputs["Vector"],
                shader_nodes.socket_by_identifier(mixRGB3.inputs, "B_Color"),
            )
            CurMat.links.new(
                add11.outputs["Value"],
                shader_nodes.socket_by_identifier(mixRGB4.inputs, "Factor_Float"),
            )
        CurMat.links.new(
            m3.outputs["m3"],
            shader_nodes.socket_by_identifier(mixRGB4.inputs, "A_Color"),
        )
        CurMat.links.new(
            shader_nodes.socket_by_identifier(mixRGB3.outputs, "Result_Color"),
            shader_nodes.socket_by_identifier(mixRGB4.inputs, "B_Color"),
        )

        if scrollMaskImg is not None:
            scrollMask = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-1700, -650),
                label="ScrollMaskTexture",
                image=scrollMaskImg,
            )
            self._slot_image("scrollMaskImg", scrollMask)
            CurMat.links.new(l1.outputs["l1"], scrollMask.inputs["Vector"])

        finalScrollUVGroup = bpy.data.node_groups.get(
            "CP77 Opaque Screen finalScrollUV v2"
        )
        if finalScrollUVGroup is None:
            finalScrollUVGroup = new_tracked_datablock(
                "node_groups", "CP77 Opaque Screen finalScrollUV v2", "ShaderNodeTree"
            )
            finalScrollUVGroup.interface.new_socket(
                name="scrollUV2", socket_type="NodeSocketVector", in_out="INPUT"
            )
            finalScrollUVGroup.interface.new_socket(
                name="scrollUV1", socket_type="NodeSocketVector", in_out="INPUT"
            )
            finalScrollUVGroup.interface.new_socket(
                name="scrollMask", socket_type="NodeSocketColor", in_out="INPUT"
            )
            finalScrollUVGroup.interface.new_socket(
                name="scrollUV2X", socket_type="NodeSocketVector", in_out="INPUT"
            )
            finalScrollUVGroup.interface.new_socket(
                name="scrollUV1X", socket_type="NodeSocketVector", in_out="INPUT"
            )
            finalScrollUVGroup.interface.new_socket(
                name="ScrollVerticalOrHorizontal",
                socket_type="NodeSocketVector",
                in_out="INPUT",
            )
            finalScrollUVGroup.interface.new_socket(
                name="finalScrollUV", socket_type="NodeSocketVector", in_out="OUTPUT"
            )

            finalScrollUVGroupI = create_node(
                finalScrollUVGroup.nodes, "NodeGroupInput", (-1050, 0)
            )
            finalScrollUVGroupO = create_node(
                finalScrollUVGroup.nodes, "NodeGroupOutput", (-150, 0)
            )
            vecLerp2 = create_node(
                finalScrollUVGroup.nodes, "ShaderNodeGroup", (-750, 0), label="lerp"
            )
            vecLerp2.node_tree = vecLerpG
            separate9 = create_node(
                finalScrollUVGroup.nodes, "ShaderNodeSeparateXYZ", (-900, -50)
            )
            vecLerp3 = create_node(
                finalScrollUVGroup.nodes, "ShaderNodeGroup", (-750, -100), label="lerp"
            )
            vecLerp3.node_tree = vecLerpG
            vecLerp4 = create_node(
                finalScrollUVGroup.nodes, "ShaderNodeGroup", (-600, 0), label="lerp"
            )
            vecLerp4.node_tree = vecLerpG
            finalScrollUVGroup.links.new(
                finalScrollUVGroupI.outputs["scrollUV2"], vecLerp2.inputs["A"]
            )
            finalScrollUVGroup.links.new(
                finalScrollUVGroupI.outputs["scrollUV1"], vecLerp2.inputs["B"]
            )
            finalScrollUVGroup.links.new(separate9.outputs["X"], vecLerp2.inputs["t"])
            finalScrollUVGroup.links.new(
                finalScrollUVGroupI.outputs["scrollMask"], separate9.inputs["Vector"]
            )
            finalScrollUVGroup.links.new(
                finalScrollUVGroupI.outputs["scrollUV2X"], vecLerp3.inputs["A"]
            )
            finalScrollUVGroup.links.new(
                finalScrollUVGroupI.outputs["scrollUV1X"], vecLerp3.inputs["B"]
            )
            finalScrollUVGroup.links.new(separate9.outputs["X"], vecLerp3.inputs["t"])
            finalScrollUVGroup.links.new(
                vecLerp2.outputs["result"], vecLerp4.inputs["A"]
            )
            finalScrollUVGroup.links.new(
                vecLerp3.outputs["result"], vecLerp4.inputs["B"]
            )
            finalScrollUVGroup.links.new(
                finalScrollUVGroupI.outputs["ScrollVerticalOrHorizontal"],
                vecLerp4.inputs["t"],
            )
            finalScrollUVGroup.links.new(
                vecLerp4.outputs["result"], finalScrollUVGroupO.inputs["finalScrollUV"]
            )

        finalScrollUV = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-1350, -650), label="finalScrollUV"
        )
        finalScrollUV.node_tree = finalScrollUVGroup
        CurMat.links.new(
            scrollUV2.outputs["scrollUV2"], finalScrollUV.inputs["scrollUV2"]
        )
        CurMat.links.new(
            scrollUV1.outputs["scrollUV1"], finalScrollUV.inputs["scrollUV1"]
        )
        if scrollMaskImg is not None:
            CurMat.links.new(
                scrollMask.outputs["Color"], finalScrollUV.inputs["scrollMask"]
            )
        CurMat.links.new(
            scrollUV2X.outputs["scrollUV2X"], finalScrollUV.inputs["scrollUV2X"]
        )
        CurMat.links.new(
            scrollUV1X.outputs["scrollUV1X"], finalScrollUV.inputs["scrollUV1X"]
        )
        CurMat.links.new(
            scrollVerticalOrHorizontal.outputs["Value"],
            finalScrollUV.inputs["ScrollVerticalOrHorizontal"],
        )

        if parImg is not None:
            scrollTex = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-1200, -650),
                label="ParalaxTexture",
                image=parImg,
            )
            self._slot_image("parImg", scrollTex)
            CurMat.links.new(
                finalScrollUV.outputs["finalScrollUV"], scrollTex.inputs["Vector"]
            )
            colorlessTex5 = create_node(
                CurMat.nodes, "ShaderNodeGroup", (-950, -650), label="colorlessTex"
            )
            colorlessTex5.node_tree = colorlessTexG
            CurMat.links.new(scrollTex.outputs["Color"], colorlessTex5.inputs["Color"])

        separate10 = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (-1350, -700))
        add3 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "ADD", location=(-1200, -700), hide=True
        ).node
        vecLerp2 = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-800, -650), label="lerp"
        )
        vecLerp2.node_tree = vecLerpG
        if scrollMaskImg is not None:
            CurMat.links.new(scrollMask.outputs["Color"], separate10.inputs["Vector"])
            CurMat.links.new(separate10.outputs["X"], add3.inputs["Value"])
            CurMat.links.new(
                separate10.outputs["Y"],
                shader_nodes.socket_by_identifier(add3.inputs, "Value_001"),
            )
            CurMat.links.new(add3.outputs["Value"], vecLerp2.inputs["t"])
        CurMat.links.new(
            shader_nodes.socket_by_identifier(mixRGB4.outputs, "Result_Color"),
            vecLerp2.inputs["A"],
        )
        if parImg is not None:
            CurMat.links.new(colorlessTex5.outputs["Color"], vecLerp2.inputs["B"])

        clamp8 = create_node(CurMat.nodes, "ShaderNodeClamp", (-800, -750))
        vecMul22 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-650, -675), hide=True
        ).node
        vecMul23 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-500, -675), hide=True
        ).node
        CurMat.links.new(emissive.outputs["Value"], clamp8.inputs["Value"])
        CurMat.links.new(vecLerp2.outputs["result"], vecMul22.inputs["Vector"])
        CurMat.links.new(
            clamp8.outputs["Result"],
            shader_nodes.socket_by_identifier(vecMul22.inputs, "Vector_001"),
        )
        CurMat.links.new(vecMul22.outputs["Vector"], vecMul23.inputs["Vector"])
        CurMat.links.new(
            emissiveColor.outputs["Color"],
            shader_nodes.socket_by_identifier(vecMul23.inputs, "Vector_001"),
        )

        separateHSV = create_node(
            CurMat.nodes, "ShaderNodeSeparateColor", (-1350, -800)
        )
        separateHSV.mode = "HSV"
        combine18 = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-1350, -850))
        combine18.inputs["X"].default_value = 1
        combine18.inputs["Z"].default_value = 1
        combine19 = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-1200, -800))
        vecMul24 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-1050, -800), hide=True
        ).node
        combine20 = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-1050, -850))
        vecAdd12 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "ADD", location=(-900, -800), hide=True
        ).node
        separate11 = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (-750, -800))
        combineHSV = create_node(CurMat.nodes, "ShaderNodeCombineColor", (-600, -800))
        combineHSV.mode = "HSV"
        CurMat.links.new(vecMul23.outputs["Vector"], separateHSV.inputs["Color"])
        CurMat.links.new(HSV_Mod_y.outputs["Value"], combine18.inputs["Y"])
        CurMat.links.new(separateHSV.outputs["Red"], combine19.inputs["X"])
        CurMat.links.new(separateHSV.outputs["Green"], combine19.inputs["Y"])
        CurMat.links.new(separateHSV.outputs["Blue"], combine19.inputs["Z"])
        CurMat.links.new(
            combine18.outputs["Vector"],
            shader_nodes.socket_by_identifier(vecMul24.inputs, "Vector_001"),
        )
        CurMat.links.new(combine19.outputs["Vector"], vecMul24.inputs["Vector"])
        CurMat.links.new(HSV_Mod_x.outputs["Value"], combine20.inputs["X"])
        CurMat.links.new(vecMul24.outputs["Vector"], vecAdd12.inputs["Vector"])
        CurMat.links.new(
            combine20.outputs["Vector"],
            shader_nodes.socket_by_identifier(vecAdd12.inputs, "Vector_001"),
        )
        CurMat.links.new(vecAdd12.outputs["Vector"], separate11.inputs["Vector"])
        CurMat.links.new(separate11.outputs["X"], combineHSV.inputs["Red"])
        CurMat.links.new(separate11.outputs["Y"], combineHSV.inputs["Green"])
        CurMat.links.new(separate11.outputs["Z"], combineHSV.inputs["Blue"])

        separate12 = create_node(CurMat.nodes, "ShaderNodeSeparateXYZ", (-1350, -900))
        maximum = shader_nodes.math(
            CurMat.nodes, CurMat.links, "MAXIMUM", location=(-1200, -886.5), hide=True
        ).node
        maximum2 = shader_nodes.math(
            CurMat.nodes, CurMat.links, "MAXIMUM", location=(-1050, -913.5), hide=True
        ).node
        CurMat.links.new(combineHSV.outputs["Color"], separate12.inputs["Vector"])
        CurMat.links.new(separate12.outputs["X"], maximum.inputs["Value"])
        CurMat.links.new(
            separate12.outputs["Y"],
            shader_nodes.socket_by_identifier(maximum.inputs, "Value_001"),
        )
        CurMat.links.new(maximum.outputs["Value"], maximum2.inputs["Value"])
        CurMat.links.new(
            separate12.outputs["Z"],
            shader_nodes.socket_by_identifier(maximum2.inputs, "Value_001"),
        )

        mul12 = shader_nodes.math(
            CurMat.nodes,
            CurMat.links,
            "MULTIPLY",
            location=(-900, -900),
            use_clamp=True,
            hide=True,
        ).node
        shader_nodes.socket_by_identifier(
            mul12.inputs, "Value_001"
        ).default_value = 0.75
        CurMat.links.new(maximum2.outputs["Value"], mul12.inputs["Value"])

        sub = shader_nodes.math(
            CurMat.nodes, CurMat.links, "SUBTRACT", location=(-750, -900), hide=True
        ).node
        sub.inputs["Value"].default_value = 1
        combine21 = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-750, -850))
        vecLerp5 = create_node(
            CurMat.nodes, "ShaderNodeGroup", (-450, -900), label="lerp"
        )
        vecLerp5.node_tree = vecLerpG
        combine22 = create_node(CurMat.nodes, "ShaderNodeCombineXYZ", (-750, -950))
        combine22.inputs["X"].default_value = 0.03
        combine22.inputs["Y"].default_value = 0.03
        combine22.inputs["Z"].default_value = 0.03
        vecMul25 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "MULTIPLY", location=(-600, -900), hide=True
        ).node
        vecAdd13 = shader_nodes.vector_math(
            CurMat.nodes, CurMat.links, "ADD", location=(-300, -900), hide=True
        ).node

        CurMat.links.new(
            mul12.outputs["Value"],
            shader_nodes.socket_by_identifier(sub.inputs, "Value_001"),
        )

        CurMat.links.new(sub.outputs["Value"], vecMul25.inputs["Vector"])
        CurMat.links.new(
            combine22.outputs["Vector"],
            shader_nodes.socket_by_identifier(vecMul25.inputs, "Vector_001"),
        )
        CurMat.links.new(combine21.outputs["Vector"], vecLerp5.inputs["A"])
        CurMat.links.new(vecMul25.outputs["Vector"], vecLerp5.inputs["B"])
        CurMat.links.new(fixForBlack.outputs["Value"], vecLerp5.inputs["t"])
        CurMat.links.new(combineHSV.outputs["Color"], vecAdd13.inputs["Vector"])
        CurMat.links.new(
            vecLerp5.outputs["result"],
            shader_nodes.socket_by_identifier(vecAdd13.inputs, "Vector_001"),
        )

        CurMat.links.new(vecAdd13.outputs["Vector"], pBSDF.inputs["Base Color"])
        CurMat.links.new(vecAdd13.outputs["Vector"], pBSDF.inputs[sockets["Emission"]])
        pBSDF.inputs["Emission Strength"].default_value = 1.0

        CurMat.links.new(metalness.outputs["Value"], pBSDF.inputs["Metallic"])

        CurMat.links.new(roughness.outputs["Value"], pBSDF.inputs["Roughness"])
