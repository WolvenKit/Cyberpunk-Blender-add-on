from __future__ import annotations

from ...assetio.catalog import ResourceKind
from ...assetio.repository import ResourceRepository
from ...assetio.values import collect_handle_data, resolve_handle_reference
from ..model.resource import PhysicsResource

PHYSICS_PARSER_REVISION = 1


def parse_physics_document(document):
    root = document.payload["Data"]["RootChunk"]
    bodies = root.get("bodies")
    if not isinstance(bodies, list):
        raise ValueError("Data.RootChunk.bodies must be a list")
    handles = {}
    collect_handle_data(root, handles)
    return PhysicsResource(root, tuple(bodies), handles, document.source.value)


def physics_resources_from_mesh_root(mesh_root, source_path=""):
    if not isinstance(mesh_root, dict):
        return ()
    handles = {}
    collect_handle_data(mesh_root, handles)
    resources = []
    for parameter_ref in mesh_root.get("parameters", ()) or ():
        parameter = resolve_handle_reference(parameter_ref, handles)
        if (
            not isinstance(parameter, dict)
            or parameter.get("$type") != "meshMeshParamPhysics"
        ):
            continue
        physics_data = resolve_handle_reference(parameter.get("physicsData"), handles)
        if (
            not isinstance(physics_data, dict)
            or physics_data.get("$type") != "physicsSystemResource"
        ):
            continue
        bodies = physics_data.get("bodies")
        if not isinstance(bodies, list):
            continue
        resources.append(
            PhysicsResource(
                physics_data, tuple(bodies), handles, str(source_path or "")
            )
        )
    return tuple(resources)


class PhysicsRepository(ResourceRepository):
    def __init__(self, documents, *, asset_index=None):
        super().__init__(
            documents,
            resource_kind=ResourceKind.PHYSICS,
            parser=parse_physics_document,
            parser_revision=PHYSICS_PARSER_REVISION,
            asset_index=asset_index,
            export_suffix=".phys.json",
            parser_receives_document=True,
        )
