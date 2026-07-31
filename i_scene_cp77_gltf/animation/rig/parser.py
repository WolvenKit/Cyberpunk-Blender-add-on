import os
from dataclasses import dataclass
from enum import Enum

from ...redSpace.qs_transform import parse_wkit_trs
from ...assetio.rig_validation import rig_array_errors
from ...assetio.values import cname_text
from .model import RigData


class RigParseMode(str, Enum):
    IMPORT = "import"
    FACIAL = "facial"


@dataclass(frozen=True, slots=True)
class RigParseOptions:
    mode: RigParseMode = RigParseMode.IMPORT


def parse_rig_document(document, *, options=RigParseOptions()):
    options = options if isinstance(options, RigParseOptions) else RigParseOptions(RigParseMode(options))
    root = document.payload["Data"]["RootChunk"]
    errors = rig_array_errors(root)
    if errors:
        raise ValueError("Invalid rig document: " + "; ".join(errors))
    bone_names = [cname_text(value) for value in root.get("boneNames", ())]
    track_names = [cname_text(value) for value in root.get("trackNames", ())]
    if options.mode is RigParseMode.FACIAL:
        transforms = root.get("boneTransforms") or root.get("aPoseLS") or ()
        rig_name = str(root.get("name", "") or "")
        disable_connect = bool(root.get("disableConnect", False))
        normalize_rotations = False
    else:
        transforms = root.get("boneTransforms", ())
        name = os.path.basename(document.source.value)
        rig_name = name[:-9] if name.casefold().endswith(".rig.json") else os.path.splitext(name)[0]
        disable_connect = True
        normalize_rotations = True
    transforms = list(transforms or ())
    rotations, translations, scales = parse_wkit_trs(
        transforms,
        len(bone_names),
        quaternion_order="xyzw",
        normalize_rotations=normalize_rotations,
    )
    return RigData(
        num_bones=len(bone_names),
        parent_indices=root.get("boneParentIndexes", ()),
        bone_names=bone_names,
        track_names=track_names,
        ls_q=rotations,
        ls_t=translations,
        ls_s=scales,
        rig_name=rig_name,
        disable_connect=disable_connect,
        apose_ms=list(root.get("aPoseMS", ())),
        apose_ls=list(root.get("aPoseLS", ())),
        bone_transforms=list(root.get("boneTransforms", ())),
        parts=list(root.get("parts", ())),
        track_names_extra=list(root.get("trackNamesExtra", ())),
        rig_extra_tracks=list(root.get("rigExtraTracks", ())),
        reference_tracks=list(root.get("referenceTracks", ())),
        cooking_platform=str(root.get("cookingPlatform", "")),
        distance_category_to_lod_map=list(root.get("distanceCategoryToLodMap", ())),
        ik_setups=list(root.get("ikSetups", ())),
        level_of_detail_start_indices=list(root.get("levelOfDetailStartIndices", ())),
        ragdoll_desc=list(root.get("ragdollDesc", ())),
        ragdoll_names=list(root.get("ragdollNames", ())),
        source_path=document.source.value,
        source_document=document.payload,
    )
