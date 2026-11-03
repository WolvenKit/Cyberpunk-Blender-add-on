import json
import struct


from ...animation.metadata import (
    validate_animation_extras,
)
from .document import DirectAnimationExportError


_ACCESSOR_WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _validate_cp77_animation_extras(extras, animation_name: str) -> None:
    try:
        validate_animation_extras(
            extras,
            label=f"{animation_name}.extras",
            error_type=DirectAnimationExportError,
        )
    except DirectAnimationExportError:
        raise
    except Exception as error:
        raise DirectAnimationExportError(
            f"Animation {animation_name!r} contains invalid metadata: {error}"
        ) from error


def validate_direct_animation_document(document: dict, binary: bytes) -> dict:
    """Validate the complete glTF 2.0 document and CP77 extras before encoding."""
    if not isinstance(document, dict):
        raise DirectAnimationExportError("The GLB JSON document is not an object.")
    asset = document.get("asset")
    if not isinstance(asset, dict) or str(asset.get("version")) != "2.0":
        raise DirectAnimationExportError("The GLB asset version must be 2.0.")

    buffers = document.get("buffers")
    if not isinstance(buffers, list) or len(buffers) != 1:
        raise DirectAnimationExportError("The animation GLB must contain exactly one embedded buffer.")
    if int(buffers[0].get("byteLength", -1)) != len(binary):
        raise DirectAnimationExportError("The GLB buffer byteLength does not match the BIN payload.")

    views = document.get("bufferViews")
    accessors = document.get("accessors")
    if not isinstance(views, list) or not isinstance(accessors, list):
        raise DirectAnimationExportError("The GLB must contain bufferViews and accessors arrays.")
    for index, view in enumerate(views):
        if not isinstance(view, dict) or int(view.get("buffer", -1)) != 0:
            raise DirectAnimationExportError(f"bufferViews[{index}] does not reference buffer 0.")
        offset = int(view.get("byteOffset", 0))
        length = int(view.get("byteLength", -1))
        if offset < 0 or length < 0 or offset + length > len(binary):
            raise DirectAnimationExportError(f"bufferViews[{index}] exceeds the BIN payload.")
        if offset % 4:
            raise DirectAnimationExportError(f"bufferViews[{index}] is not 4-byte aligned.")

    for index, accessor in enumerate(accessors):
        if not isinstance(accessor, dict):
            raise DirectAnimationExportError(f"accessors[{index}] is not an object.")
        view_index = int(accessor.get("bufferView", -1))
        if not 0 <= view_index < len(views):
            raise DirectAnimationExportError(f"accessors[{index}] has an invalid bufferView.")
        if int(accessor.get("componentType", -1)) != 5126:
            raise DirectAnimationExportError(f"accessors[{index}] must use FLOAT componentType 5126.")
        accessor_type = str(accessor.get("type", ""))
        width = _ACCESSOR_WIDTHS.get(accessor_type)
        count = int(accessor.get("count", -1))
        if width is None or count < 0:
            raise DirectAnimationExportError(f"accessors[{index}] has invalid type/count metadata.")
        accessor_offset = int(accessor.get("byteOffset", 0))
        required = accessor_offset + count * width * 4
        if accessor_offset < 0 or required > int(views[view_index]["byteLength"]):
            raise DirectAnimationExportError(f"accessors[{index}] exceeds its bufferView.")

    nodes = document.get("nodes")
    skins = document.get("skins")
    scenes = document.get("scenes")
    if not isinstance(nodes, list) or not nodes:
        raise DirectAnimationExportError("The animation GLB contains no nodes.")
    if not isinstance(skins, list) or len(skins) != 1:
        raise DirectAnimationExportError("The animation GLB must contain exactly one skin.")
    if not isinstance(scenes, list) or not scenes:
        raise DirectAnimationExportError("The animation GLB contains no scene.")
    for node_index, node in enumerate(nodes):
        for child in node.get("children", ()) if isinstance(node, dict) else ():
            if not isinstance(child, int) or not 0 <= child < len(nodes):
                raise DirectAnimationExportError(
                    f"nodes[{node_index}] contains an invalid child index."
                )

    skin = skins[0]
    joints = skin.get("joints")
    extras = skin.get("extras")
    if not isinstance(joints, list) or not joints:
        raise DirectAnimationExportError("The skin contains no joints.")
    if any(not isinstance(index, int) or not 0 <= index < len(nodes) for index in joints):
        raise DirectAnimationExportError("The skin contains an invalid joint node index.")
    if not isinstance(extras, dict):
        raise DirectAnimationExportError("The skin is missing its CP77 extras object.")
    bone_names = extras.get("boneNames")
    parent_indices = extras.get("boneParentIndexes")
    track_names = extras.get("trackNames", [])
    if not isinstance(bone_names, list) or len(bone_names) != len(joints):
        raise DirectAnimationExportError("skin.extras.boneNames does not match the joint count.")
    if not isinstance(parent_indices, list) or len(parent_indices) != len(joints):
        raise DirectAnimationExportError(
            "skin.extras.boneParentIndexes does not match the joint count."
        )
    if not isinstance(track_names, list):
        raise DirectAnimationExportError("skin.extras.trackNames must be a list.")
    for index, joint_node in enumerate(joints):
        if str(nodes[joint_node].get("name", "")) != str(bone_names[index]):
            raise DirectAnimationExportError(
                f"Joint {index} node name does not match skin.extras.boneNames."
            )
        parent = int(parent_indices[index])
        if parent >= index or parent < -1:
            raise DirectAnimationExportError(
                f"skin.extras.boneParentIndexes[{index}] is invalid."
            )
        if parent >= 0 and joint_node not in nodes[joints[parent]].get("children", ()):
            raise DirectAnimationExportError(
                f"Joint {index} hierarchy disagrees with boneParentIndexes."
            )
    inverse_bind_accessor = int(skin.get("inverseBindMatrices", -1))
    if not 0 <= inverse_bind_accessor < len(accessors):
        raise DirectAnimationExportError("The skin has no valid inverseBindMatrices accessor.")
    inverse_accessor = accessors[inverse_bind_accessor]
    if inverse_accessor.get("type") != "MAT4" or int(inverse_accessor.get("count", -1)) != len(joints):
        raise DirectAnimationExportError(
            "The inverseBindMatrices accessor must contain one MAT4 per joint."
        )

    animations = document.get("animations")
    if not isinstance(animations, list) or not animations:
        raise DirectAnimationExportError("The GLB contains no animations.")
    for animation_index, animation in enumerate(animations):
        if not isinstance(animation, dict):
            raise DirectAnimationExportError(f"animations[{animation_index}] is not an object.")
        name = str(animation.get("name", f"animation_{animation_index}"))
        _validate_cp77_animation_extras(animation.get("extras"), name)
        samplers = animation.get("samplers")
        channels = animation.get("channels")
        if not isinstance(samplers, list) or not isinstance(channels, list):
            raise DirectAnimationExportError(
                f"Animation {name!r} must contain samplers and channels arrays."
            )
        for sampler_index, sampler in enumerate(samplers):
            input_index = int(sampler.get("input", -1))
            output_index = int(sampler.get("output", -1))
            if not 0 <= input_index < len(accessors) or not 0 <= output_index < len(accessors):
                raise DirectAnimationExportError(
                    f"Animation {name!r} sampler {sampler_index} has invalid accessors."
                )
            if sampler.get("interpolation", "LINEAR") not in {"LINEAR", "STEP"}:
                raise DirectAnimationExportError(
                    f"Animation {name!r} sampler {sampler_index} uses unsupported interpolation."
                )
            if accessors[input_index].get("type") != "SCALAR":
                raise DirectAnimationExportError(
                    f"Animation {name!r} sampler {sampler_index} input must be SCALAR."
                )
            if int(accessors[input_index].get("count", -1)) != int(
                accessors[output_index].get("count", -2)
            ):
                raise DirectAnimationExportError(
                    f"Animation {name!r} sampler {sampler_index} input/output counts differ."
                )
        for channel_index, channel in enumerate(channels):
            sampler_index = int(channel.get("sampler", -1))
            target = channel.get("target")
            if not 0 <= sampler_index < len(samplers) or not isinstance(target, dict):
                raise DirectAnimationExportError(
                    f"Animation {name!r} channel {channel_index} is invalid."
                )
            node_index = int(target.get("node", -1))
            path = target.get("path")
            if node_index not in joints or path not in {"translation", "rotation", "scale"}:
                raise DirectAnimationExportError(
                    f"Animation {name!r} channel {channel_index} targets an invalid joint/path."
                )
            output_accessor = accessors[int(samplers[sampler_index]["output"])]
            expected_type = "VEC4" if path == "rotation" else "VEC3"
            if output_accessor.get("type") != expected_type:
                raise DirectAnimationExportError(
                    f"Animation {name!r} channel {channel_index} output must be {expected_type}."
                )

    json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    return {
        "valid": True,
        "animation_count": len(animations),
        "joint_count": len(joints),
        "accessor_count": len(accessors),
        "skin_extra_keys": tuple(extras.keys()),
        "animation_extra_keys": tuple(animations[0]["extras"].keys()),
    }


def validate_glb_payload(payload: bytes) -> dict:
    """Parse and validate an encoded GLB 2.0 payload, including CP77 extras."""
    if len(payload) < 20:
        raise DirectAnimationExportError("GLB payload is truncated.")
    magic, version, total_length = struct.unpack_from("<4sII", payload, 0)
    if magic != b"glTF" or version != 2 or total_length != len(payload):
        raise DirectAnimationExportError("GLB header is invalid.")
    offset = 12
    json_document = None
    binary = b""
    chunk_order = []
    while offset < len(payload):
        if offset + 8 > len(payload):
            raise DirectAnimationExportError("GLB chunk header is truncated.")
        chunk_length, chunk_type = struct.unpack_from("<II", payload, offset)
        offset += 8
        end = offset + chunk_length
        if chunk_length % 4 or end > len(payload):
            raise DirectAnimationExportError("GLB chunk length or alignment is invalid.")
        chunk = payload[offset:end]
        offset = end
        chunk_order.append(chunk_type)
        if chunk_type == 0x4E4F534A:
            if json_document is not None:
                raise DirectAnimationExportError("GLB contains multiple JSON chunks.")
            try:
                json_document = json.loads(chunk.decode("utf-8").rstrip(" \t\r\n\0"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise DirectAnimationExportError("GLB JSON chunk is invalid.") from error
        elif chunk_type == 0x004E4942:
            if binary:
                raise DirectAnimationExportError("GLB contains multiple BIN chunks.")
            binary = chunk
    if not chunk_order or chunk_order[0] != 0x4E4F534A or json_document is None:
        raise DirectAnimationExportError("The first GLB chunk must be JSON.")
    declared_binary_length = int(json_document.get("buffers", [{}])[0].get("byteLength", -1))
    if declared_binary_length < 0 or len(binary) - declared_binary_length not in {0, 1, 2, 3}:
        raise DirectAnimationExportError("The BIN chunk padding does not match buffers[0].byteLength.")
    validation = validate_direct_animation_document(
        json_document,
        binary[:declared_binary_length],
    )
    validation["file_bytes"] = len(payload)
    validation["json_chunk_bytes"] = next(
        length for length, chunk_type in _iter_glb_chunk_headers(payload) if chunk_type == 0x4E4F534A
    )
    validation["binary_chunk_bytes"] = len(binary)
    return validation


def _iter_glb_chunk_headers(payload: bytes):
    offset = 12
    while offset < len(payload):
        chunk_length, chunk_type = struct.unpack_from("<II", payload, offset)
        yield chunk_length, chunk_type
        offset += 8 + chunk_length


def validate_direct_animation_glb_file(filepath: str) -> dict:
    with open(filepath, "rb") as stream:
        return validate_glb_payload(stream.read())
