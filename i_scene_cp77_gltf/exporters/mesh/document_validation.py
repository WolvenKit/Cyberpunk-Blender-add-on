from __future__ import annotations

import numpy as np

from ...gltf.accessors import GLTFAccessorReader
from ...gltf.container import (
    GLBContainer,
    GLBContainerError,
    embedded_glb_binary,
    parse_glb_container,
    read_glb_container,
)
from ...gltf.garment_support import GARMENT_SUPPORT_MORPH
from ...gltf.mesh_contract import (
    JOINT_ATTRIBUTES,
    WEIGHT_ATTRIBUTES,
    validate_mesh_arrays,
    validate_primitive_accessors,
    validate_wolvenkit_channels,
)
from ...gltf.nodes import node_reference
from .errors import DirectMeshExportError


def validate_direct_mesh_document(document: dict, binary: bytes) -> dict:
    """Check the emitted document against the constraints direct_mesh_import enforces"""
    if "materials" in document:
        raise DirectMeshExportError(
            "CP77 mesh GLTF must not contain a top-level materials array; "
            "material names and appearance assignments belong in mesh.extras.materialNames."
        )

    accessors = document.get("accessors") or []
    views = document.get("bufferViews") or []
    nodes = document.get("nodes") or []
    meshes = document.get("meshes") or []
    if not meshes:
        raise DirectMeshExportError("The document contains no meshes.")

    declared = int(document.get("buffers", [{}])[0].get("byteLength", -1))
    if declared != len(binary):
        raise DirectMeshExportError(
            "buffers[0].byteLength disagrees with the BIN payload."
        )
    for index, view in enumerate(views):
        if int(view.get("buffer", 0)) != 0:
            raise DirectMeshExportError(
                f"bufferViews[{index}] targets a non-embedded buffer."
            )
        start = int(view.get("byteOffset", 0))
        length = int(view.get("byteLength", 0))
        end = start + length
        if start < 0 or length < 0 or end > len(binary):
            raise DirectMeshExportError(
                f"bufferViews[{index}] overruns the BIN payload."
            )

    widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
    sizes = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
    for index, accessor in enumerate(accessors):
        width = widths.get(accessor.get("type"))
        size = sizes.get(int(accessor.get("componentType", 0)))
        if width is None or size is None:
            raise DirectMeshExportError(
                f"accessors[{index}] has an unsupported layout."
            )
        view_index = int(accessor.get("bufferView", -1))
        if not 0 <= view_index < len(views):
            raise DirectMeshExportError(
                f"accessors[{index}] references an invalid bufferView."
            )
        count = int(accessor.get("count", 0))
        offset = int(accessor.get("byteOffset", 0))
        if count < 0 or offset < 0 or views[view_index].get("byteStride") is not None:
            raise DirectMeshExportError(
                f"accessors[{index}] has an invalid direct-export layout."
            )
        required = count * width * size
        available = int(views[view_index].get("byteLength", 0)) - int(
            accessor.get("byteOffset", 0)
        )
        if required > available:
            raise DirectMeshExportError(f"accessors[{index}] overruns its bufferView.")

    reader = GLTFAccessorReader(
        GLBContainer(document, binary, "", 0), error_type=DirectMeshExportError
    )

    def array_for(accessor_index):
        values = reader.read(
            accessor_index,
            dtype=np.float64 if accessors[accessor_index].get("normalized") else None,
        )
        return values.reshape(len(values), -1)

    skins = document.get("skins") or []
    joint_count = 0
    if skins:
        if len(skins) != 1:
            raise DirectMeshExportError("Direct mesh export writes exactly one skin.")
        skin = skins[0]
        joints = [int(value) for value in (skin.get("joints") or ())]
        if not joints or len(set(joints)) != len(joints):
            raise DirectMeshExportError(
                "The skin joint list is empty or contains duplicates."
            )
        if any(index < 0 or index >= len(nodes) for index in joints):
            raise DirectMeshExportError("The skin references an invalid joint node.")
        extras = skin.get("extras") or {}
        bone_names = [str(value) for value in (extras.get("boneNames") or ())]
        node_names = [str(nodes[joint].get("name", "")) for joint in joints]
        if bone_names:
            if bone_names != node_names:
                raise DirectMeshExportError(
                    "skin.extras.boneNames disagree with the joint node names."
                )
            if len(set(bone_names)) != len(bone_names) or not all(bone_names):
                raise DirectMeshExportError("skin.extras.boneNames are not unique.")

        parents = [int(value) for value in (extras.get("boneParentIndexes") or ())]
        if parents:
            if len(parents) != len(joints):
                raise DirectMeshExportError(
                    "boneParentIndexes length disagrees with the joint count."
                )
            for index, parent in enumerate(parents):
                if parent >= index or parent < -1:
                    raise DirectMeshExportError(
                        f"boneParentIndexes[{index}] is not topologically ordered."
                    )
                if parent >= 0 and joints[index] not in nodes[joints[parent]].get(
                    "children", ()
                ):
                    raise DirectMeshExportError(
                        f"Joint {index} disagrees with the node hierarchy."
                    )

        inverse_bind = int(skin.get("inverseBindMatrices", -1))
        if not 0 <= inverse_bind < len(accessors):
            raise DirectMeshExportError(
                "The skin has no valid inverseBindMatrices accessor."
            )
        if accessors[inverse_bind].get("type") != "MAT4" or int(
            accessors[inverse_bind].get("count", -1)
        ) != len(joints):
            raise DirectMeshExportError(
                "inverseBindMatrices must hold one MAT4 per joint."
            )
        joint_count = len(joints)
        if not np.all(np.isfinite(array_for(inverse_bind))):
            raise DirectMeshExportError(
                "Inverse bind matrices contain non-finite values."
            )

    for mesh_index, mesh in enumerate(meshes):
        primitives = mesh.get("primitives") or ()
        if len(primitives) != 1:
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] must contain exactly one primitive."
            )
        primitive = primitives[0]
        attributes = primitive.get("attributes") or {}
        try:
            validate_primitive_accessors(accessors, primitive)
            validate_wolvenkit_channels(attributes)
        except ValueError as error:
            raise DirectMeshExportError(f"meshes[{mesh_index}]: {error}") from error
        vertex_count = accessors[attributes["POSITION"]]["count"]

        joint_blocks = tuple(
            index for index, name in enumerate(JOINT_ATTRIBUTES) if name in attributes
        )
        weight_blocks = tuple(
            index for index, name in enumerate(WEIGHT_ATTRIBUTES) if name in attributes
        )
        if joint_blocks != weight_blocks:
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] JOINTS/WEIGHTS blocks are not paired."
            )
        if joint_blocks and joint_blocks != tuple(range(len(joint_blocks))):
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] skinning blocks are not contiguous from zero."
            )
        if joint_blocks and not joint_count:
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] carries skinning data without a skin."
            )
        for block in joint_blocks:
            accessor = accessors[int(attributes[JOINT_ATTRIBUTES[block]])]
            bounds = accessor.get("max")
            if bounds is None:
                raise DirectMeshExportError(
                    f"meshes[{mesh_index}] {JOINT_ATTRIBUTES[block]} has no bounds to verify."
                )
            if int(max(bounds)) >= joint_count:
                raise DirectMeshExportError(
                    f"meshes[{mesh_index}] {JOINT_ATTRIBUTES[block]} references joint "
                    f"{int(max(bounds))} outside the {joint_count}-joint skin."
                )

        indices = primitive.get("indices")
        if indices is None:
            raise DirectMeshExportError(f"meshes[{mesh_index}] is not indexed.")
        if (
            not 0 <= int(indices) < len(accessors)
            or accessors[int(indices)].get("type") != "SCALAR"
        ):
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] has an invalid index accessor."
            )
        index_count = int(accessors[int(indices)].get("count", 0))
        if index_count % 3:
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] index count is not divisible by three."
            )
        try:
            validate_mesh_arrays(
                {name: array_for(index) for name, index in attributes.items()},
                array_for(indices),
                joint_count=joint_count,
            )
        except ValueError as error:
            raise DirectMeshExportError(f"meshes[{mesh_index}]: {error}") from error
        if "material" in primitive:
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] contains a glTF material reference; "
                "CP77 material assignments must be stored in mesh.extras.materialNames."
            )

        targets = primitive.get("targets") or ()
        names = (mesh.get("extras") or {}).get("targetNames") or ()
        if targets and len(names) != len(targets):
            raise DirectMeshExportError(
                f"meshes[{mesh_index}] targetNames disagree with its morph target count."
            )
        for target_index, target in enumerate(targets):
            # GarmentSupport may carry positions alone, as WolvenKit writes it.
            positions_only = (
                names[target_index] == GARMENT_SUPPORT_MORPH
                and "NORMAL" not in target
                and "TANGENT" not in target
            )
            for semantic in (
                ("POSITION",) if positions_only else ("POSITION", "NORMAL", "TANGENT")
            ):
                target_accessor = target.get(semantic)
                if target_accessor is None or not 0 <= int(target_accessor) < len(
                    accessors
                ):
                    raise DirectMeshExportError(
                        f"meshes[{mesh_index}] target {target_index} has no valid {semantic} delta accessor."
                    )
                layout = accessors[int(target_accessor)]
                if (
                    layout.get("type") != "VEC3"
                    or layout.get("componentType") != 5126
                    or int(layout.get("count", -1)) != vertex_count
                ):
                    raise DirectMeshExportError(
                        f"meshes[{mesh_index}] target {target_index} {semantic} layout disagrees with its base vertices."
                    )
                target_values = array_for(target_accessor)
                if not np.all(np.isfinite(target_values)):
                    raise DirectMeshExportError(
                        f"meshes[{mesh_index}] target {target_index} has non-finite {semantic} deltas."
                    )

    mesh_nodes = [node for node in nodes if "mesh" in node]
    for node in mesh_nodes:
        try:
            node_reference(node["mesh"], len(meshes), "Mesh node mesh")
            if "skin" in node:
                node_reference(node["skin"], len(skins), "Mesh node skin")
        except ValueError as error:
            raise DirectMeshExportError(str(error)) from error
        if (
            "matrix" in node
            or "translation" in node
            or "rotation" in node
            or "scale" in node
        ):
            raise DirectMeshExportError(
                f"Mesh node {node.get('name')!r} must carry an identity transform for "
                "WolvenKit mesh export; enable Apply Transform."
            )

    return {
        "valid": True,
        "mesh_count": len(meshes),
        "joint_count": joint_count,
        "accessor_count": len(accessors),
        "vertex_count": sum(
            int(
                accessors[int(mesh["primitives"][0]["attributes"]["POSITION"])]["count"]
            )
            for mesh in meshes
        ),
    }


def validate_direct_mesh_glb_file(filepath: str) -> dict:
    """Validate a staged mesh export through the shared strict container reader"""
    try:
        container = read_glb_container(filepath)
    except GLBContainerError as error:
        raise DirectMeshExportError(str(error)) from error
    return _validate_mesh_container(container)


def validate_direct_mesh_glb_payload(payload: bytes) -> dict:
    """Validate encoded mesh GLB bytes with the same strict container checks as a staged file"""
    try:
        container = parse_glb_container(payload)
    except GLBContainerError as error:
        raise DirectMeshExportError(str(error)) from error
    return _validate_mesh_container(container)


def _validate_mesh_container(container: GLBContainer) -> dict:
    try:
        binary = embedded_glb_binary(container)
    except GLBContainerError as error:
        raise DirectMeshExportError(str(error)) from error
    validation = validate_direct_mesh_document(container.document, binary)
    validation["file_bytes"] = container.declared_length
    validation["binary_chunk_bytes"] = len(container.binary)
    return validation
