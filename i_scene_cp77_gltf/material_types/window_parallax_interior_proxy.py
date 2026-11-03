<<<<<<< Updated upstream
import os
from ..materials.blender.images import imageFromRelPath
from ..materials.blender.nodes import CreateShaderNodeValue, create_node, loc
from .interior_mapping_nodegroups import andrew_willmotts_plane_interior_mapping_node_group, flipbook_function_node_group
import re

from .mat_common import MaterialTypeBase

def _positive_float(value):
    if isinstance(value, dict):
        value = value.get("$value", value.get("value"))
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0.0 else None


def _room_atlas_aspect_ratio(data, atlas_path):
    if isinstance(atlas_path, str):
        filename = os.path.splitext(os.path.basename(atlas_path.replace("\\", "/")))[0]
        pattern = r"(?:^|[_-])(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)(?=$|[_-])"
        match = re.search(pattern, filename)
        if match:
            width = _positive_float(match.group(1))
            height = _positive_float(match.group(2))
            if width is not None and height is not None:
                return width / height

    width = _positive_float(data.get("roomWidth"))
    height = _positive_float(data.get("roomHeight"))
    if width is not None and height is not None:
        return width / height

    return 1.0

class windowParallaxIntProx(MaterialTypeBase):
    def create(self,Data,Mat):
        CurMat = Mat.node_tree
        pBSDF=CurMat.nodes[loc('Principled BSDF')]
        CurMat.nodes.remove(pBSDF)
        room_atlas = Data.get("RoomAtlas")
        AspectRatio = _room_atlas_aspect_ratio(Data, room_atlas)
        AspectRatioVal = CreateShaderNodeValue(CurMat, AspectRatio, -1300, 400, "AspectRatio")

        bcolImg = None
        bColNode = None
        if room_atlas:
            bcolImg = imageFromRelPath(
                room_atlas,
                self.image_format,
                DepotPath=self.BasePath,
                ProjPath=self.ProjPath,
            )
            bColNode = create_node(
                CurMat.nodes,
                "ShaderNodeTexImage",
                (-600, 450),
                label="RoomAtlas",
                image=bcolImg,
            )
       
        # AtlasGridUvRatio
        # roomWidth
        if 'roomWidth' in Data:
            roomWidth = CreateShaderNodeValue(CurMat,Data["roomWidth"],-1200, 100,"roomWidth")
        # roomHeight
        if 'roomHeight' in Data:
            roomHeight = CreateShaderNodeValue(CurMat,Data["roomHeight"],-1200, 150,"roomHeight")
        # roomDepth
        if 'roomDepth' in Data:
            roomDepth = CreateShaderNodeValue(CurMat,Data["roomDepth"],-1200, 200,"roomDepth")

        AW_Int_Map = andrew_willmotts_plane_interior_mapping_node_group()
        InteriorMapping = create_node(CurMat.nodes,"ShaderNodeGroup", (-1130,620),hide=False)
        InteriorMapping.node_tree = AW_Int_Map
        InteriorMapping.name = "Interior Mapping"
        
        # input doenst like values =>1 need to work out what the dimension of this value is
        #AW_Int_Map.inputs[1].default_value=Data["roomDepth"]

       #Just need to populate this and it works.
        #AW_Int_Map.inputs[4].default_value=AspectRatio
        CurMat.links.new(AspectRatioVal.outputs[0],InteriorMapping.inputs[4])


        flip=flipbook_function_node_group()    
        flipbook = create_node(CurMat.nodes,"ShaderNodeGroup", (-910,575),hide=False)
        flipbook.node_tree = flip
        flipbook.name = "RoomAtlas"
        
        image_width = bcolImg.size[0] if bcolImg and len(bcolImg.size) > 1 else 0
        image_height = bcolImg.size[1] if bcolImg and len(bcolImg.size) > 1 else 0
        noCols = image_width / (image_height * AspectRatio) if image_width and image_height else 1.0
        noCols = max(1.0, noCols)
        noColsVal = CreateShaderNodeValue(CurMat, noCols, -1100, 250, "NoImages")        
        CurMat.links.new(noColsVal.outputs[0],flipbook.inputs[3])    
        CurMat.links.new(noColsVal.outputs[0],flipbook.inputs[4])

        UV=create_node(CurMat.nodes,"ShaderNodeUVMap",(-1650, 670))
        Vec_Frac=create_node(CurMat.nodes,"ShaderNodeVectorMath",(-1545, 448), operation='FRACTION')
        CurMat.links.new(UV.outputs[0],Vec_Frac.inputs[0])
        CurMat.links.new(Vec_Frac.outputs[0],InteriorMapping.inputs[0])
        CurMat.links.new(InteriorMapping.outputs[0],flipbook.inputs[0])
        if bColNode is not None:
            CurMat.links.new(flipbook.outputs[0], bColNode.inputs[0])
            CurMat.links.new(bColNode.outputs[0], CurMat.nodes['Material Output'].inputs[0])
=======
from bpy.app.translations import pgettext

from ..blender import shader_nodes
from ..materials.blender.nodes import create_node
from .graph import mix_color_socket
from .interior_parallax_common import atlas_depth, window_day_night_factors
from .mat_common import param_color
from .window_parallax_interior import WindowParallaxInterior, _replicate
from .window_parallax_source import build_window_parallax_coordinates, color_overlay_uv


class WindowParallaxInteriorProxy(WindowParallaxInterior):
    texture_defaults = {
        "RoomAtlas": r"base\surfaces\parallax\placeholder\parallax_day.xbm",
        "Curtain": r"base\surfaces\parallax\placeholder\blinds.xbm",
        "ColorOverlayTexture": r"base\surfaces\parallax\coloroverlay.xbm",
    }
    atlas_depth_default = 0.0
    room_width_default = 6.0
    room_height_default = 4.0
    room_depth_default = 4.0

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        tree = Mat.node_tree
        bsdf = tree.nodes[pgettext("Principled BSDF")]
        coords = build_window_parallax_coordinates(
            self,
            tree,
            data,
            atlas_depth(data, self.atlas_depth_default),
            include_layer=False,
        )
>>>>>>> Stashed changes

        room = self._texture(
            tree,
            data,
            "RoomAtlas",
            coords.room_atlas_uv,
            (-900, 620),
            extension="EXTEND",
        )
        curtain = self._texture(
            tree,
            data,
            "Curtain",
            coords.curtain_atlas_uv,
            (-900, 260),
            extension="EXTEND",
        )
        overlay_uv = color_overlay_uv(tree, coords.object_pivot, location=(-1200, -900))
        overlay_node = self._texture(
            tree,
            data,
            "ColorOverlayTexture",
            overlay_uv,
            (-80, -900),
            extension="EXTEND",
        )
        overlay = overlay_node.outputs["Color"] if overlay_node is not None else None

        room_lighting_factor, final_night_factor, time_of_day, room_on_floor = (
            window_day_night_factors(tree, data, coords.room_on_random, (-740, -620))
        )

        if room is not None:
            color, _ = self._night_lit_color(
                tree,
                room.outputs["Color"],
                room.outputs["Alpha"],
                room_lighting_factor.outputs["Value"],
                location=(-700, 700),
                label="Room",
                alpha_power=2.0,
                lighting_scale=1.5,
            )
        else:
            black = create_node(
                tree.nodes, "ShaderNodeRGB", (-700, 700), label="Missing RoomAtlas"
            )
            black.outputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
            color = black.outputs["Color"]

        if curtain is not None:
            curtain_alpha = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label="Curtain Alpha x Geometry Mask",
                location=(-520, 260),
                hide=True,
            ).node
            tree.links.new(curtain.outputs["Alpha"], curtain_alpha.inputs["Value"])
            tree.links.new(
                coords.curtain_mask,
                shader_nodes.socket_by_identifier(curtain_alpha.inputs, "Value_001"),
            )
            curtain_mix = create_node(
                tree.nodes, "ShaderNodeMix", (-160, 520), label="Interior / Curtain"
            )
            curtain_mix.data_type = "RGBA"
            tree.links.new(
                curtain_alpha.outputs["Value"],
                shader_nodes.socket_by_identifier(curtain_mix.inputs, "Factor_Float"),
            )
            tree.links.new(
                color, shader_nodes.socket_by_identifier(curtain_mix.inputs, "A_Color")
            )
            tree.links.new(
                curtain.outputs["Color"],
                shader_nodes.socket_by_identifier(curtain_mix.inputs, "B_Color"),
            )
            color = shader_nodes.socket_by_identifier(
                curtain_mix.outputs, "Result_Color"
            )

        interp_rgb = _replicate(tree, coords.room_interp, (20, 620), "roomInterp.xxx")
        depth_color = mix_color_socket(
            tree.nodes,
            tree.links,
            "FinalBaseColor x roomInterp",
            color,
            interp_rgb,
            1.0,
            (200, 520),
            blend_type="MULTIPLY",
            clamp=False,
        )
        tint = create_node(
            tree.nodes, "ShaderNodeRGB", (240, 180), label="TintColorAtNight"
        )
        tint.outputs["Color"].default_value = param_color(
            data, "TintColorAtNight", (1.0, 1.0, 1.0, 0.0)
        )
        temp_color = self._light_temperature(
            tree, coords.random, data, location=(240, 40)
        )
        final_color = self._source_window_color(
            tree,
            depth_color,
            overlay,
            tint.outputs["Color"],
            temp_color,
            coords.view_angle,
            final_night_factor.outputs["Value"],
            location=(520, 520),
        )
        tree.links.new(final_color, bsdf.inputs["Base Color"])
        tree.links.new(final_color, bsdf.inputs["Emission Color"])

        roughness = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            0.2,
            label="Proxy Roughness = ViewAngle x 0.2",
            location=(620, -240),
            use_clamp=True,
            hide=True,
        ).node
        tree.links.new(coords.view_angle, roughness.inputs["Value"])
        tree.links.new(roughness.outputs["Value"], bsdf.inputs["Roughness"])
        bsdf.inputs["Metallic"].default_value = 1.0
        geometry = create_node(
            tree.nodes, "ShaderNodeNewGeometry", (400, -420), label="Proxy World Normal"
        )
        tree.links.new(geometry.outputs["Normal"], bsdf.inputs["Normal"])

        if curtain is not None:
            curtain_alpha_socket = curtain.outputs["Alpha"]
        else:
            curtain_default = create_node(
                tree.nodes,
                "ShaderNodeValue",
                (700, -760),
                label="Curtain Alpha Default",
            )
            curtain_default.outputs["Value"].default_value = 0.0
            curtain_alpha_socket = curtain_default.outputs["Value"]
        if room is not None:
            room_alpha_socket = room.outputs["Alpha"]
        else:
            room_default = create_node(
                tree.nodes, "ShaderNodeValue", (700, -640), label="Room Alpha Default"
            )
            room_default.outputs["Value"].default_value = 0.0
            room_alpha_socket = room_default.outputs["Value"]

        emission_strength, _ = self._window_emission_strength(
            tree,
            data,
            room_alpha=room_alpha_socket,
            room_hit_y=coords.room_hit_y,
            room_interp=coords.room_interp,
            curtain_alpha=curtain_alpha_socket,
            curtain_mask=coords.curtain_mask,
            overlay=overlay,
            time_of_day=time_of_day.outputs["Value"],
            turned_on=room_on_floor.outputs["Value"],
            emissive_ev_default=4.0,
            location=(900, -780),
        )
        tree.links.new(emission_strength, bsdf.inputs["Emission Strength"])
        bsdf.inputs["Alpha"].default_value = 1.0
