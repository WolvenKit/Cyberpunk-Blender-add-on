from ..assetio.paths import backslash_depot_key, split_source_raw_root
from ..bartmoss.scalar import clamp01
from ..blender import shader_nodes
from .bundles import (
    direct_ev_strength_socket,
    emissive_scale_bundle,
    four_way_color_socket,
)
from .graph import color_channel_socket, mix_color_socket, set_alpha_clip, value_socket
from .mat_common import (
    MaterialTypeBase,
    create_scene_time_value,
    find_input,
    lookup_param,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
)
from .normal_math import decode_cp77_normal, tangent_to_normal_map

_DEVICE_DEFAULTS = {
    "BaseColor": "base\\surfaces\\materials\\common\\plastic_common_01_300_d.xbm",
    "BaseColorScale": (150.0 / 255.0, 0.0, 0.0, 0.0),
    "Metalness": "engine\\textures\\editor\\black.xbm",
    "MetalnessScale": 1.0,
    "MetalnessBias": 0.0,
    "Roughness": "base\\surfaces\\materials\\plastic\\plastic_lightcover\\plastic_lightcover_01_50_r.xbm",
    "RoughnessScale": 1.0,
    "RoughnessBias": 0.0,
    "Normal": "base\\surfaces\\materials\\plastic\\plastic_lightcover\\plastic_lightcover_01_50_n.xbm",
    "Emissive": "base\\fx\\_textures\\masks\\gradients\\fx_reflected_vertical_gradient_01_d.xbm",
    "EmissiveEV": 5.0,
    "AlphaThreshold": 0.330000013,
    "Blinking": 0.0,
    "BlinkingSpeed": 8.0,
    "UseMaterialParameter": 1.0,
    "EmissiveColor1": (127.0 / 255.0, 0.0, 0.0, 1.0),
    "EmissiveColor2": (0.0, 12.0 / 255.0, 127.0 / 255.0, 1.0),
    "EmissiveInitialState": 0.0,
    "UseTwoEmissiveColors": 0.0,
    "SwitchingTwoEmissiveColorsSpeed": 0.0,
    "UseFresnel": 0.0,
}

_MULTI_STATE_DEFAULTS = {
    **_DEVICE_DEFAULTS,
    "EmissiveColor3": (1.0, 1.0, 1.0, 1.0),
    "EmissiveColor4": (1.0, 1.0, 1.0, 1.0),
    "EmissiveColorSelector": 1.0,
}

_MULTI_STATE_PARAMS = ("EmissiveColor3", "EmissiveColor4", "EmissiveColorSelector")
_PRINCIPLED_INPUTS = {"Metalness": "Metallic", "Roughness": "Roughness"}


def _param_float(data, name, defaults):
    return param_float(data, name, defaults[name])


def _param_color(data, name, defaults):
    return param_color(data, name, defaults[name])


def _link(links, source, target):
    if target is not None:
        links.new(source, target)


def _is_vehicle_mesh(mesh_path):
    """Whether a mesh sits in the depot's vehicles folders, whose meshes take the vehicle vertex streams"""
    _root, depot_path = split_source_raw_root(str(mesh_path or ""))
    return "vehicles" in backslash_depot_key(depot_path).split("\\")[:2]


class DeviceDiode(MaterialTypeBase):
    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        template = backslash_depot_key(
            Mat.get("MaterialTemplate", "") or self.material_template
        )
        multi_state = template.endswith("device_diode_multi_state.mt") or any(
            lookup_param(data, key) is not None for key in _MULTI_STATE_PARAMS
        )
        defaults = _MULTI_STATE_DEFAULTS if multi_state else _DEVICE_DEFAULTS

        Mat.use_nodes = True
        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()
        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (1700, 180)
        )
        principled = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Device Diode", (1420, 180)
        )
        links.new(principled.outputs["BSDF"], output.inputs["Surface"])

        base_scale = _param_color(data, "BaseColorScale", defaults)
        Mat.diffuse_color = (*base_scale[:3], 1.0)
        base_node = self._texture(nodes, data, defaults, "BaseColor", (-1500, 540))
        sampled_base = (
            base_node.outputs["Color"]
            if base_node is not None
            else (1.0, 1.0, 1.0, 1.0)
        )
        scaled_base = mix_color_socket(
            nodes,
            links,
            "Scaled Base Color",
            sampled_base,
            base_scale,
            1.0,
            (-1180, 540),
            blend_type="MULTIPLY",
            clamp=False,
        )

        for key, fallback, y in (("Metalness", 0.0, 260), ("Roughness", 0.5, 60)):
            _link(
                links,
                self._scaled_red(nodes, links, data, defaults, key, fallback, y),
                find_input(principled, _PRINCIPLED_INPUTS[key]),
            )

        normal = None
        normal_node = self._texture(
            nodes, data, defaults, "Normal", (-1500, -220), non_color=True
        )
        if normal_node is not None:
            decoded = decode_cp77_normal(
                tree,
                normal_node.outputs["Color"],
                strength=1.0,
                location=(-1260, -220),
                label="DirectX Normal",
            )
            normal = tangent_to_normal_map(
                tree, decoded.outputs["Color"], location=(-980, -220), label="Normal"
            )
            _link(links, normal, find_input(principled, "Normal"))

        final_base = scaled_base
        emissive_ev = max(0.0, _param_float(data, "EmissiveEV", defaults))
        mask_node = None
        if emissive_ev > 0.0:
            mask_node = self._texture(
                nodes, data, defaults, "Emissive", (-1500, -1000), non_color=True
            )
        if mask_node is not None:
            final_base, strength = self._emissive(
                tree,
                data,
                defaults,
                Mat,
                multi_state,
                mask_node,
                sampled_base,
                scaled_base,
                normal,
                emissive_ev,
            )
            _link(
                links, final_base, find_input(principled, "Emission Color", "Emission")
            )
            _link(links, strength, find_input(principled, "Emission Strength"))
        _link(links, final_base, find_input(principled, "Base Color"))

        threshold = clamp01(_param_float(data, "AlphaThreshold", defaults))
        if base_node is not None and threshold > 0.0:
            below = shader_nodes.math(
                nodes,
                links,
                "LESS_THAN",
                base_node.outputs["Alpha"],
                threshold,
                name="Below AlphaThreshold",
                location=(900, 180),
            )
            kept = shader_nodes.math(
                nodes,
                links,
                "SUBTRACT",
                1.0,
                below,
                name="Alpha Test",
                location=(1100, 180),
            )
            _link(links, kept, find_input(principled, "Alpha"))
            set_alpha_clip(Mat, 0.5)

    def _texture(self, nodes, data, defaults, key, location, *, non_color=False):
        return self._relative_texture_node(
            nodes,
            param_texture_path(data, key) or defaults[key],
            key,
            location,
            non_color=non_color,
            error_label="device diode",
            require_image=True,
            extension="REPEAT",
            interpolation="Linear",
        )

    def _scaled_red(self, nodes, links, data, defaults, key, fallback, y):
        """The texture's red channel times its scale plus its bias"""
        node = self._texture(nodes, data, defaults, key, (-1500, y), non_color=True)
        source = fallback
        if node is not None:
            source = color_channel_socket(
                nodes,
                links,
                node.outputs["Color"],
                f"{key} Red",
                (-1260, y),
                channel="Red",
                mode="RGB",
            )
        scale = _param_float(data, f"{key}Scale", defaults)
        bias = _param_float(data, f"{key}Bias", defaults)
        return shader_nodes.math(
            nodes,
            links,
            "MULTIPLY_ADD",
            source,
            scale,
            bias,
            name=f"{key}Bias",
            location=(-780, y),
            use_clamp=True,
        )

    def _emissive(
        self,
        tree,
        data,
        defaults,
        Mat,
        multi_state,
        mask_node,
        sampled_base,
        scaled_base,
        normal,
        emissive_ev,
    ):
        """The base colour with the glow's tint, and the emission strength"""
        nodes, links = tree.nodes, tree.links
        mask = color_channel_socket(
            nodes,
            links,
            mask_node.outputs["Color"],
            "Emissive Red",
            (-1260, -1000),
            channel="Red",
            mode="RGB",
        )
        time = create_scene_time_value(tree, -1500, -600, "Time").outputs["Value"]
        speed = _param_float(data, "BlinkingSpeed", defaults)
        phase = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            time,
            speed,
            name="Blink Phase",
            location=(-1240, -600),
        )
        cosine = shader_nodes.math(
            nodes, links, "COSINE", phase, name="Blink Cosine", location=(-1060, -600)
        )
        half = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            cosine,
            0.5,
            name="Half Blink Cosine",
            location=(-880, -600),
        )
        steady = 1.5 - _param_float(data, "Blinking", defaults)
        blink = shader_nodes.math(
            nodes,
            links,
            "ADD",
            half,
            steady,
            name="Blink",
            location=(-700, -600),
            use_clamp=True,
        )

        use_parameter = clamp01(_param_float(data, "UseMaterialParameter", defaults))
        parameter = value_socket(
            nodes,
            "CP77 Material Parameter 0",
            0.0,
            (-1500, -760),
            "Material Parameter 0",
        )
        switch = shader_nodes.lerp(
            nodes,
            links,
            1.0,
            parameter,
            use_parameter,
            name="Material Parameter",
            location=(-1240, -760),
        )
        flipped = shader_nodes.math(
            nodes,
            links,
            "SUBTRACT",
            1.0,
            switch,
            name="Flipped Material Parameter",
            location=(-820, -820),
        )
        initial_state = clamp01(_param_float(data, "EmissiveInitialState", defaults))
        state = shader_nodes.lerp(
            nodes,
            links,
            switch,
            flipped,
            initial_state,
            name="Emissive State",
            location=(-640, -760),
        )

        masked = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            mask,
            blink,
            name="Mask x Blink",
            location=(-480, -1000),
        )
        scale = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            masked,
            state,
            name="Emissive Scale",
            location=(-300, -1000),
        )
        tint_factor = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            scale,
            1.0,
            name="Saturated Emissive Scale",
            location=(-120, -1000),
            use_clamp=True,
        )
        ev = emissive_scale_bundle(tree, scale, emissive_ev, (900, -900), "Emissive EV")

        if multi_state:
            authored = _param_float(data, "EmissiveColorSelector", defaults)
            runtime = value_socket(
                nodes,
                "CP77 Material Parameter 1",
                authored,
                (-900, -1450),
                "Material Parameter 1",
            )
            selector = shader_nodes.lerp(
                nodes,
                links,
                authored,
                runtime,
                use_parameter,
                name="Emissive Color Selector",
                location=(-660, -1450),
            )
            floor = shader_nodes.math(
                nodes,
                links,
                "FLOOR",
                selector,
                name="Floor Selector",
                location=(-240, -1450),
            )
            index = shader_nodes.math(
                nodes,
                links,
                "SUBTRACT",
                floor,
                1.0,
                name="Emissive Color Index",
                location=(-60, -1450),
            )
            colors = [
                _param_color(data, f"EmissiveColor{number}", defaults)
                for number in range(1, 5)
            ]
            emissive_color = four_way_color_socket(
                tree, index, colors, (160, -1450), "Emissive Color"
            )
        else:
            emissive_color = self._two_colors(nodes, links, data, defaults, time)
            vehicle = value_socket(
                nodes,
                "CP77 Vehicle Mesh",
                float(_is_vehicle_mesh(Mat.get("sourcePath", ""))),
                (-300, -1250),
                "Vehicle Mesh",
            )
            device = shader_nodes.math(
                nodes,
                links,
                "SUBTRACT",
                1.0,
                vehicle,
                name="Device Mesh",
                location=(-120, -1250),
            )
            tint_factor = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                tint_factor,
                device,
                name="Device Tint",
                location=(60, -1100),
            )

        tint = mix_color_socket(
            nodes,
            links,
            "Emissive Tint",
            sampled_base,
            emissive_color,
            1.0,
            (600, 470),
            blend_type="MULTIPLY",
            clamp=False,
        )
        final_base = mix_color_socket(
            nodes, links, "Final Base Color", scaled_base, tint, tint_factor, (900, 470)
        )

        use_fresnel = (
            0.0 if multi_state else clamp01(_param_float(data, "UseFresnel", defaults))
        )
        if use_fresnel <= 0.0:
            return final_base, ev.outputs["Strength"]
        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "Geometry", (660, -760)
        )
        surface_normal = normal if normal is not None else geometry.outputs["Normal"]
        facing = shader_nodes.vector_math(
            nodes,
            links,
            "DOT_PRODUCT",
            geometry.outputs["Incoming"],
            surface_normal,
            name="Facing",
            location=(880, -760),
        )
        fresnel = shader_nodes.math(
            nodes, links, "POWER", facing, 4.0, name="Facing^4", location=(1060, -760)
        )
        weighted = shader_nodes.lerp(
            nodes,
            links,
            1.0,
            fresnel,
            use_fresnel,
            name="Fresnel",
            location=(1240, -760),
        )
        fresnel_ev = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            ev.outputs["Scaled EV"],
            weighted,
            name="Fresnel EV",
            location=(1300, -900),
        )
        return final_base, direct_ev_strength_socket(
            tree, fresnel_ev, (1480, -900), "Emission Strength"
        )

    def _two_colors(self, nodes, links, data, defaults, time):
        """EmissiveColor1, swinging toward EmissiveColor2 over time when UseTwoEmissiveColors is set"""
        first = _param_color(data, "EmissiveColor1", defaults)
        use_two = clamp01(_param_float(data, "UseTwoEmissiveColors", defaults))
        if use_two <= 0.0:
            return first
        speed = _param_float(data, "SwitchingTwoEmissiveColorsSpeed", defaults)
        phase = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            time,
            speed,
            name="Two Color Phase",
            location=(-900, -1390),
        )
        sine = shader_nodes.math(
            nodes, links, "SINE", phase, name="Two Color Sine", location=(-720, -1390)
        )
        half = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            sine,
            0.5,
            name="Half Two Color Sine",
            location=(-540, -1390),
        )
        wave = shader_nodes.math(
            nodes,
            links,
            "ADD",
            half,
            0.5,
            name="Two Color Wave",
            location=(-360, -1390),
        )
        factor = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            wave,
            use_two,
            name="UseTwoEmissiveColors",
            location=(-180, -1390),
        )
        second = _param_color(data, "EmissiveColor2", defaults)
        return mix_color_socket(
            nodes, links, "Emissive Color", first, second, factor, (0, -1280)
        )
