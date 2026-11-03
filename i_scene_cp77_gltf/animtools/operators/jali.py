import bpy
from bpy.types import Operator

from ...blender.animation_context import active_armature
from ...notifications import show_message
from ..model import JALIGenerationRequest
from ..services import jali


def _finish(operator, result):
    for warning in result.warnings:
        operator.report({"WARNING"}, warning)
    if result.message:
        operator.report({result.level}, result.message)
    return result.blender_status


class CP77_OT_PreviewFacialPose(Operator):
    bl_idname = "cp77.preview_facial_pose"
    bl_label = "Preview Facial Pose"
    bl_description = "Apply a test facial pose to verify rig setup"
    bl_options = {"REGISTER", "UNDO"}

    pose_type: bpy.props.EnumProperty(
        name="Pose Type",
        items=[
            ("NEUTRAL", "Neutral", "Relaxed neutral face"),
            ("AA", "AA - 'father'", "Open jaw, neutral lips"),
            ("IY", "IY - 'beet'", "Slight jaw, wide lips"),
            ("UW", "UW - 'boot'", "Slight jaw, puckered lips"),
            ("M", "M - 'mom'", "Closed jaw, lip closure"),
            ("F", "F - 'fun'", "Slight jaw, lip-teeth"),
            ("S", "S - 'sun'", "Narrow jaw, stretched"),
            ("TH", "TH - 'think'", "Slight jaw, tongue forward"),
            ("SMILE", "Smile", "Wide lips, raised corners"),
            ("POUT", "Pout", "Puckered lips"),
            ("JAW_OPEN", "Jaw Open", "Max jaw opening"),
            ("CUSTOM", "Custom JALI", "Manual JA/LI control"),
        ],
        default="NEUTRAL",
    )
    custom_jaw: bpy.props.FloatProperty(
        name="Jaw (JA)", default=0.5, min=0.0, max=1.0,
        description="Jaw opening (0 = closed, 1 = max open)",
    )
    custom_lip: bpy.props.FloatProperty(
        name="Lip (LI)", default=0.0, min=-1.0, max=1.0,
        description="Lip shaping (-1 = pucker, 0 = neutral, 1 = wide)",
    )
    intensity: bpy.props.FloatProperty(
        name="Intensity", default=1.0, min=0.0, max=2.0,
        description="Pose intensity multiplier",
    )

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        return _finish(
            self,
            jali.preview_pose(
                context,
                pose_type=self.pose_type,
                custom_jaw=float(self.custom_jaw),
                custom_lip=float(self.custom_lip),
                intensity=float(self.intensity),
            ),
        )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "pose_type", text="")
        if self.pose_type == "CUSTOM":
            box = layout.box()
            box.label(text="JALI Parameters:", icon="SETTINGS")
            box.prop(self, "custom_jaw", slider=True)
            box.prop(self, "custom_lip", slider=True)
        layout.separator()
        layout.prop(self, "intensity", slider=True)


class CP77_OT_GenerateJALILipSync(Operator):
    bl_idname = "cp77.generate_jali_lipsync"
    bl_label = "Generate JALI Lipsync"
    bl_description = "Analyze audio and generate procedural facial animation using JALI"
    bl_options = {"REGISTER", "UNDO"}

    audio_path: bpy.props.StringProperty(
        name="Audio File",
        subtype="FILE_PATH",
        description="Audio file to analyze (.wav, .mp3, .ogg)",
    )
    transcript: bpy.props.StringProperty(
        name="Transcript (Optional)",
        description="Text transcript for better accuracy",
    )
    use_transcript: bpy.props.BoolProperty(
        name="Use Transcript",
        default=False,
        description="Use transcript for forced alignment",
    )
    jaw_multiplier: bpy.props.FloatProperty(
        name="Jaw Multiplier", default=1.0, min=0.0, max=2.0,
        description="Scale jaw opening",
    )
    lip_multiplier: bpy.props.FloatProperty(
        name="Lip Multiplier", default=1.0, min=0.0, max=2.0,
        description="Scale lip shaping",
    )

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        request = JALIGenerationRequest(
            audio_path=self.audio_path,
            transcript=self.transcript,
            use_transcript=bool(self.use_transcript),
            jaw_multiplier=float(self.jaw_multiplier),
            lip_multiplier=float(self.lip_multiplier),
        )
        return _finish(self, jali.generate_lipsync(context, request))

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Audio Input:", icon="SPEAKER")
        layout.prop(self, "audio_path", text="")
        layout.separator()
        layout.prop(self, "use_transcript")
        if self.use_transcript:
            box = layout.box()
            box.label(text="Transcript:", icon="TEXT")
            box.prop(self, "transcript", text="")
        layout.separator()
        layout.label(text="JALI Parameters:", icon="SETTINGS")
        col = layout.column(align=True)
        col.prop(self, "jaw_multiplier", slider=True)
        col.prop(self, "lip_multiplier", slider=True)


class JALI_OT_InstallDependencies(Operator):
    bl_idname = "cp77_facial.install_jali_deps"
    bl_label = "Install JALI Dependencies"
    bl_description = "Install parselmouth and g2p_en via pip"
    bl_options = {"REGISTER"}

    def execute(self, context):
        result = jali.install_dependencies()
        status = _finish(self, result)
        if result.ok and result.details.get("installed"):
            show_message(result.message)
        return status
