<<<<<<< Updated upstream
import json
import os

import bpy

from ..common.atomic import atomic_write_json


def cp77_hp_export(filepath):
    script_directory = os.path.dirname(os.path.abspath(__file__))
    template_relative_path = os.path.join(
        '..',
        '..',
        'resources',
        'hair_profile_template.hp.json',
    )

    # Get the absolute path to the template file
    template_hp_file = os.path.normpath(os.path.join(script_directory, template_relative_path))

    if not filepath:
        return {'CANCELLED'}
    obj = bpy.context.active_object
    if obj is None or obj.active_material is None:
        return {'CANCELLED'}

    # Detect the active material slot
    active_slot = obj.active_material_index

    if active_slot is None:
        print("No active material")

    else:
        mat = obj.active_material
        hair = []
        if mat.get('MaterialTemplate') == r"base\materials\hair.mt":
            hair = mat.get('MaterialTemplate')
        if not hair:
            print("Active Material is not a Hair Profile")
            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Active Material is not a Hair Profile")
            return {'CANCELLED'}
        else:
            # Load the template hair profile JSON
            with open(template_hp_file, 'r') as template_f:
                j = json.load(template_f)

            crs = ['Color Ramp', 'Color Ramp.001']

            nodes = mat.node_tree.nodes
            print(' ')
            print('Gradient Stops for', mat.name)

            for crname in crs:
                cr = nodes.get(crname)
                if cr:
                    print(' ')
                    print('Stop info for', cr.label)
                    grad = ''
                    if cr.label == 'GradientEntriesRootToTip':
                        grad = 'gradientEntriesRootToTip'
                    elif cr.label == 'GradientEntriesID':
                        grad = 'gradientEntriesID'

                    j_data = j['Data']['RootChunk'][grad]
                    elements = list(cr.color_ramp.elements)
                    elements.reverse()

                    for i, stop in enumerate(elements):
                        print('Stop #', i)
                        print('Position -', stop.position)
                        print('Color -', int(stop.color[0] * 255), int(stop.color[1] * 255), int(stop.color[2] * 255))
                        print(' ')

                        # Create a new entry for each stop
                        new_entry = {
                            "$type": "rendGradientEntry",
                            "color": {
                                "$type": "Color",
                                "Alpha": int(stop.color[3] * 255),
                                "Blue": int(stop.color[2] * 255),
                                "Green": int(stop.color[1] * 255),
                                "Red": int(stop.color[0] * 255),
                                },
                            "value": stop.position,
                            }

                        j_data.append(new_entry)

            outpath = os.path.abspath(os.fspath(filepath))
            atomic_write_json(outpath, j, indent=2)
            bpy.ops.cp77.message_box(
                'INVOKE_DEFAULT',
                message=os.path.basename(outpath) + " exported successfully",
            )
            return {'FINISHED'}
=======
import copy
import math
import os

from ...assetio.atomic import atomic_write_json
from ...assetio.catalog import ResourceKind
from ...assetio.diagnostics import IssueSeverity
from ...assetio.documents import load_json_payload
from ...assetio.headers import cr2w_header
from ...assetio.paths import backslash_depot_key
from ...assetio.validation import ValidationProfile, validate_payload
from ...bartmoss.scalar import clamp01, linear_channel_to_srgb
from ...blender.operator_results import OperationResult
from ...core.log import get_logger
from ...materials.hair_profile_contract import (
    SAMPLE_COUNT_PROP,
    decode_source_entries,
    source_entries_property,
)

_LOG = get_logger(__name__)

_HAIR_TEMPLATES = {
    r"base\materials\hair.mt",
    r"base\materials\hair_blendable.mt",
    r"base\fx\_shaders\blackwall_blendable_hair.mt",
}

_GRADIENT_NODE_IDENTITIES = {
    "gradientEntriesID": {
        "Hair Profile ID",
        "GradientEntriesID",
    },
    "gradientEntriesRootToTip": {
        "Hair Profile Root To Tip",
        "GradientEntriesRootToTip",
    },
}


class HairProfileExportError(RuntimeError):
    pass


def _channel_to_byte(value, *, srgb=False):
    normalized = linear_channel_to_srgb(value) if srgb else clamp01(value)
    return max(0, min(255, int(round(normalized * 255.0))))


def _gradient_entries_from_elements(elements):
    serialized = []
    for stop in sorted(elements, key=lambda item: float(item.position)):
        position = float(stop.position)
        if not math.isfinite(position):
            raise HairProfileExportError(
                "Hair profile gradient contains a non-finite stop position."
            )
        color = stop.color
        if len(color) < 4:
            raise HairProfileExportError(
                "Hair profile gradient stop has no RGBA color."
            )
        serialized.append(
            {
                "$type": "rendGradientEntry",
                "color": {
                    "$type": "Color",
                    "Alpha": _channel_to_byte(color[3]),
                    "Blue": _channel_to_byte(color[2], srgb=True),
                    "Green": _channel_to_byte(color[1], srgb=True),
                    "Red": _channel_to_byte(color[0], srgb=True),
                },
                "value": clamp01(position),
            }
        )
    if not serialized:
        raise HairProfileExportError("Hair profile gradient contains no stops.")
    return serialized


def _entry_color_bytes(entry):
    color = entry.get("color") if isinstance(entry, dict) else None
    if not isinstance(color, dict):
        return None
    try:
        return tuple(
            int(color.get(key, 255 if key == "Alpha" else 0))
            for key in ("Red", "Green", "Blue", "Alpha")
        )
    except (TypeError, ValueError):
        return None


def _same_gradient_semantics(
    current_entries, source_entries, position_tolerance=1.0e-6
):
    if len(current_entries) != len(source_entries):
        return False
    source_sorted = sorted(
        enumerate(source_entries),
        key=lambda item: (float(item[1].get("value", 0.0)), item[0]),
    )
    for current, (_, source) in zip(current_entries, source_sorted):
        try:
            source_value = float(source.get("value", 0.0))
        except (TypeError, ValueError):
            return False
        if abs(float(current["value"]) - source_value) > position_tolerance:
            return False
        if _entry_color_bytes(current) != _entry_color_bytes(source):
            return False
    return True


def _source_order_permutation(source_entries):
    sorted_source = sorted(
        enumerate(source_entries),
        key=lambda item: (float(item[1].get("value", 0.0)), item[0]),
    )
    rank_by_source_index = {
        source_index: rank for rank, (source_index, _) in enumerate(sorted_source)
    }
    return [rank_by_source_index[index] for index in range(len(source_entries))]


def _gradient_entries_for_export(elements, source_entries=None):
    current = _gradient_entries_from_elements(elements)
    if not source_entries or len(source_entries) != len(current):
        return current
    if _same_gradient_semantics(current, source_entries):
        return copy.deepcopy(source_entries)
    permutation = _source_order_permutation(source_entries)
    return [current[rank] for rank in permutation]


def _node_identity(node):
    return {
        str(getattr(node, "name", "") or ""),
        str(getattr(node, "label", "") or ""),
    }


def _find_gradient_node(nodes, gradient_key):
    identities = _GRADIENT_NODE_IDENTITIES[gradient_key]
    matches = []
    for node in nodes:
        if getattr(node, "bl_idname", "") != "ShaderNodeValToRGB":
            continue
        if _node_identity(node) & identities:
            matches.append(node)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(sorted(str(node.name) for node in matches))
        raise HairProfileExportError(
            f"Multiple nodes identify the {gradient_key} hair gradient: {names}."
        )
    expected = " / ".join(sorted(identities))
    raise HairProfileExportError(
        f"Could not find the {gradient_key} hair gradient node ({expected})."
    )


def _hair_profile_payload(material, template_payload):
    template = backslash_depot_key(material.get("MaterialTemplate", ""))
    if template not in _HAIR_TEMPLATES:
        raise HairProfileExportError(
            "Active material is not a supported Cyberpunk hair material."
        )

    tree = getattr(material, "node_tree", None)
    if tree is None:
        raise HairProfileExportError("Active hair material has no node tree.")

    payload = template_payload
    root = payload.get("Data", {}).get("RootChunk")
    if not isinstance(root, dict) or root.get("$type") != "CHairProfile":
        raise HairProfileExportError(
            "Bundled hair-profile template is not a CHairProfile document."
        )

    for gradient_key in ("gradientEntriesID", "gradientEntriesRootToTip"):
        node = _find_gradient_node(tree.nodes, gradient_key)
        ramp = getattr(node, "color_ramp", None)
        if ramp is None:
            raise HairProfileExportError(f"{gradient_key} node has no ColorRamp data.")
        source_entries = decode_source_entries(
            material.get(source_entries_property(gradient_key))
        )
        entries = _gradient_entries_for_export(ramp.elements, source_entries)
        root[gradient_key] = entries
        _LOG.debug(
            "Hair profile %s: exported %d stop(s) from %s",
            gradient_key,
            len(entries),
            node.name,
        )

    sample_count = material.get(SAMPLE_COUNT_PROP)
    if sample_count is not None:
        try:
            sample_count = int(sample_count)
        except (TypeError, ValueError):
            sample_count = None
        if sample_count is not None and sample_count > 0:
            root["sampleCount"] = sample_count

    if not root.get("gradientEntriesID") or not root.get("gradientEntriesRootToTip"):
        raise HairProfileExportError(
            "Hair profile export produced an empty required gradient."
        )
    return payload


def _validate_hair_profile_payload(payload, filepath):
    result = validate_payload(
        payload,
        path=os.fspath(filepath),
        kind=ResourceKind.HAIR_PROFILE,
        profile=ValidationProfile.CR2W,
        expected_root_types=("CHairProfile",),
    )
    errors = result.messages(minimum=IssueSeverity.ERROR)
    if errors:
        raise HairProfileExportError(
            "Invalid hair profile export: " + "; ".join(errors)
        )


def cp77_hp_export(context, filepath):
    """Write the active hair material as a WolvenKit hair profile (.hp.json)"""
    if not filepath:
        return OperationResult.cancelled("No output path was selected.")

    obj = context.active_object
    if obj is None or obj.active_material is None:
        return OperationResult.cancelled(
            "Select an object with an active Cyberpunk hair material."
        )

    script_directory = os.path.dirname(os.path.abspath(__file__))
    template_hp_file = os.path.normpath(
        os.path.join(
            script_directory, "..", "..", "resources", "hair_profile_template.hp.json"
        )
    )
    template_payload = load_json_payload(template_hp_file)
    if not isinstance(template_payload, dict):
        raise HairProfileExportError(
            "Could not load the bundled hair-profile template."
        )

    payload = _hair_profile_payload(obj.active_material, template_payload)
    outpath = os.path.abspath(os.fspath(filepath))
    payload["Header"] = cr2w_header(outpath)
    _validate_hair_profile_payload(payload, outpath)
    atomic_write_json(outpath, payload, indent=2)
    return OperationResult.finished(f"Exported {os.path.basename(outpath)}.")
>>>>>>> Stashed changes
