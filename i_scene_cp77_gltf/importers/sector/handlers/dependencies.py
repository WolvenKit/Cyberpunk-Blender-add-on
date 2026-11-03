from __future__ import annotations

<<<<<<< Updated upstream
from ..model import ImportDependency
from ..options import OPTIONAL_SECTOR_NODE_TYPES
from ..registry import NODE_HANDLERS
from ...common.paths import depot_path_from_value
from ....assetio.values import nested_dict


STANDARD_PHASE = 20
PROXY_PHASE = 30
=======
from ....assetio.values import nested_dict
from ...common.paths import depot_path_from_value
from ..model import PROXY_PHASE, STANDARD_PHASE, ImportDependency
from ..options import ENTITY_NODE_TYPES, PROXY_NODE_TYPES
from ..registry import NODE_HANDLERS
>>>>>>> Stashed changes

_DEFAULT_APPEARANCE = {
    "$type": "CName",
    "$storage": "string",
    "$value": "default",
}

<<<<<<< Updated upstream
ENTITY_NODE_TYPES = frozenset({
    "worldEntityNode",
    "worldDeviceNode",
})

DIRECT_MESH_NODE_TYPES = frozenset({
    "worldInstancedMeshNode",
})

STANDARD_MESH_NODE_TYPES = frozenset({
    "worldStaticMeshNode",
    "worldRotatingMeshNode",
    "worldAdvertisingNode",
    "worldAdvertisementNode",
    "worldPhysicalDestructionNode",
    "worldBakedDestructionNode",
    "worldTerrainMeshNode",
    "worldBendedMeshNode",
    "worldCableMeshNode",
    "worldClothMeshNode",
    "worldDynamicMeshNode",
    "worldMeshNode",
    "worldStaticOccluderMeshNode",
    "worldDecorationMeshNode",
    "worldFoliageNode",
    "worldWaterPatchNode",
    "worldInstancedOccluderNode",
})

INSTANCED_DESTRUCTIBLE_NODE_TYPES = frozenset({
    "worldInstancedDestructibleMeshNode",
})

PROXY_NODE_TYPES = OPTIONAL_SECTOR_NODE_TYPES["proxies"]
=======
DIRECT_MESH_NODE_TYPES = frozenset(
    {
        "worldInstancedMeshNode",
    }
)

STANDARD_MESH_NODE_TYPES = frozenset(
    {
        "worldStaticMeshNode",
        "worldRotatingMeshNode",
        "worldAdvertisingNode",
        "worldAdvertisementNode",
        "worldPhysicalDestructionNode",
        "worldBakedDestructionNode",
        "worldTerrainMeshNode",
        "worldBendedMeshNode",
        "worldCableMeshNode",
        "worldClothMeshNode",
        "worldDynamicMeshNode",
        "worldMeshNode",
        "worldStaticOccluderMeshNode",
        "worldDecorationMeshNode",
        "worldFoliageNode",
        "worldWaterPatchNode",
        "worldInstancedOccluderNode",
    }
)

INSTANCED_DESTRUCTIBLE_NODE_TYPES = frozenset(
    {
        "worldInstancedDestructibleMeshNode",
    }
)
>>>>>>> Stashed changes


def _default_appearance():
    return dict(_DEFAULT_APPEARANCE)


def _raw_mesh_appearance(data):
    return data["meshAppearance"] if "meshAppearance" in data else _default_appearance()


def _has_direct_mesh(data):
    mesh = data.get("mesh") if isinstance(data, dict) else None
<<<<<<< Updated upstream
    return (
        isinstance(mesh, dict)
        and isinstance(mesh.get("DepotPath"), (dict, str))
    )
=======
    return isinstance(mesh, dict) and isinstance(mesh.get("DepotPath"), (dict, str))
>>>>>>> Stashed changes


def _mesh_dependency(node, sector_name, appearance, phase):
    if not node.mesh_path:
        return ()
<<<<<<< Updated upstream
    return (ImportDependency(
        kind="mesh",
        depot_path=node.mesh_path,
        appearance=appearance,
        source_sector=sector_name,
        source_node_index=node.index,
        placement_phase=phase,
    ),)
=======
    return (
        ImportDependency(
            kind="mesh",
            depot_path=node.mesh_path,
            appearance=appearance,
            source_sector=sector_name,
            source_node_index=node.index,
            placement_phase=phase,
        ),
    )
>>>>>>> Stashed changes


class EntityDependencyHandler:
    placement_phase = STANDARD_PHASE

    def collect_dependencies(self, parsed_sector, node):
<<<<<<< Updated upstream
        dependencies = list(_mesh_dependency(
            node,
            parsed_sector.sector_name,
            _raw_mesh_appearance(node.data),
            self.placement_phase,
        ))
        if node.entity_template_path:
            dependencies.append(ImportDependency(
                kind="entity",
                depot_path=node.entity_template_path,
                appearance=node.entity_appearance or "default",
                source_sector=parsed_sector.sector_name,
                source_node_index=node.index,
                placement_phase=self.placement_phase,
            ))
=======
        dependencies = list(
            _mesh_dependency(
                node,
                parsed_sector.sector_name,
                _raw_mesh_appearance(node.data),
                self.placement_phase,
            )
        )
        if node.entity_template_path:
            dependencies.append(
                ImportDependency(
                    kind="entity",
                    depot_path=node.entity_template_path,
                    appearance=node.entity_appearance or "default",
                    source_sector=parsed_sector.sector_name,
                    source_node_index=node.index,
                    placement_phase=self.placement_phase,
                )
            )
>>>>>>> Stashed changes
        return tuple(dependencies)


class DirectMeshDependencyHandler:
    placement_phase = STANDARD_PHASE

    def collect_dependencies(self, parsed_sector, node):
        return _mesh_dependency(
            node,
            parsed_sector.sector_name,
            _raw_mesh_appearance(node.data),
            self.placement_phase,
        )


class StandardMeshDependencyHandler:
    placement_phase = STANDARD_PHASE

    def collect_dependencies(self, parsed_sector, node):
        data = node.data
        if _has_direct_mesh(data):
            appearance = _raw_mesh_appearance(data)
        elif "meshRef" in data:
            appearance = _default_appearance()
        else:
            return ()
        return _mesh_dependency(
            node,
            parsed_sector.sector_name,
            appearance,
            self.placement_phase,
        )


class InstancedDestructibleDependencyHandler:
    placement_phase = STANDARD_PHASE

    def collect_dependencies(self, parsed_sector, node):
        if "mesh" not in node.data:
            return ()
        return _mesh_dependency(
            node,
            parsed_sector.sector_name,
            _raw_mesh_appearance(node.data),
            self.placement_phase,
        )


class ProxyMeshDependencyHandler(StandardMeshDependencyHandler):
    placement_phase = PROXY_PHASE


def _resource_depot_path(data, key):
<<<<<<< Updated upstream
    return depot_path_from_value(
        data.get(key) if isinstance(data, dict) else None
    )
=======
    return depot_path_from_value(data.get(key) if isinstance(data, dict) else None)
>>>>>>> Stashed changes


def _resource_dependency(parsed_sector, node, kind, depot_path, phase):
    if not depot_path:
        return ()
<<<<<<< Updated upstream
    return (ImportDependency(
        kind=kind,
        depot_path=depot_path,
        appearance="",
        source_sector=parsed_sector.sector_name,
        source_node_index=node.index,
        placement_phase=phase,
    ),)
=======
    return (
        ImportDependency(
            kind=kind,
            depot_path=depot_path,
            appearance="",
            source_sector=parsed_sector.sector_name,
            source_node_index=node.index,
            placement_phase=phase,
        ),
    )
>>>>>>> Stashed changes


class SingleResourceDependencyHandler:
    placement_phase = STANDARD_PHASE
    resource_kind = ""
    resource_key = ""

    def collect_dependencies(self, parsed_sector, node):
        return _resource_dependency(
            parsed_sector,
            node,
            self.resource_kind,
            _resource_depot_path(node.data, self.resource_key),
            self.placement_phase,
        )


class GIResourceDependencyHandler(SingleResourceDependencyHandler):
    resource_kind = "gi"
    resource_key = "data"


class SemanticResourceDependencyHandler:
    placement_phase = STANDARD_PHASE

    def collect_dependencies(self, parsed_sector, node):
        data = node.data
        dependencies = []

        if node.node_type == "worldAISpotNode":
            spot_data = nested_dict(data, "spot", "Data")
            workspot = _resource_depot_path(
                spot_data,
                "resource",
            )
            if workspot:
<<<<<<< Updated upstream
                dependencies.append(ImportDependency(
                    kind="workspot",
                    depot_path=workspot,
                    appearance="",
                    source_sector=parsed_sector.sector_name,
                    source_node_index=node.index,
                    placement_phase=self.placement_phase,
                ))
=======
                dependencies.append(
                    ImportDependency(
                        kind="cp77_workspot",
                        depot_path=workspot,
                        appearance="",
                        source_sector=parsed_sector.sector_name,
                        source_node_index=node.index,
                        placement_phase=self.placement_phase,
                    )
                )
>>>>>>> Stashed changes

        elif node.node_type == "worldCompiledSmartObjectsNode":
            resource = _resource_depot_path(
                data,
                "resource",
            )
            if resource:
<<<<<<< Updated upstream
                dependencies.append(ImportDependency(
                    kind="smartobjects",
                    depot_path=resource,
                    appearance="",
                    source_sector=parsed_sector.sector_name,
                    source_node_index=node.index,
                    placement_phase=self.placement_phase,
                ))
=======
                dependencies.append(
                    ImportDependency(
                        kind="smartobjects",
                        depot_path=resource,
                        appearance="",
                        source_sector=parsed_sector.sector_name,
                        source_node_index=node.index,
                        placement_phase=self.placement_phase,
                    )
                )
>>>>>>> Stashed changes

        elif node.node_type == "worldSmartObjectNode":
            smart_data = nested_dict(data, "object", "Data")
            for kind, key in (
<<<<<<< Updated upstream
                ("workspot", "workspotTemplate"),
=======
                ("cp77_workspot", "workspotTemplate"),
>>>>>>> Stashed changes
                ("actionanimdb", "motionActionDatabase"),
            ):
                depot_path = _resource_depot_path(
                    smart_data,
                    key,
                )
                if not depot_path:
                    continue
<<<<<<< Updated upstream
                dependencies.append(ImportDependency(
                    kind=kind,
                    depot_path=depot_path,
                    appearance="",
                    source_sector=parsed_sector.sector_name,
                    source_node_index=node.index,
                    placement_phase=self.placement_phase,
                ))
=======
                dependencies.append(
                    ImportDependency(
                        kind=kind,
                        depot_path=depot_path,
                        appearance="",
                        source_sector=parsed_sector.sector_name,
                        source_node_index=node.index,
                        placement_phase=self.placement_phase,
                    )
                )
>>>>>>> Stashed changes

        return tuple(dependencies)


class AcousticResourceDependencyHandler(SingleResourceDependencyHandler):
    resource_kind = "acoustic"
    resource_key = "data"


class MinimapResourceDependencyHandler(SingleResourceDependencyHandler):
    resource_kind = "minimap"
    resource_key = "encodedShapesRef"


class EffectResourceDependencyHandler:
    placement_phase = STANDARD_PHASE

    def collect_dependencies(self, parsed_sector, node):
        if node.node_type == "worldStaticParticleNode":
            resource_kind = "particle"
            resource_key = "particleSystem"
        elif node.node_type == "worldEffectNode":
            resource_kind = "effect"
            resource_key = "effect"
        else:
            return ()

        depot_path = _resource_depot_path(
            node.data,
            resource_key,
        )
        return _resource_dependency(
            parsed_sector,
            node,
            resource_kind,
            depot_path,
            self.placement_phase,
        )


class StaticLightDependencyHandler(SingleResourceDependencyHandler):
    resource_kind = "ies"
    resource_key = "iesProfile"


class ReflectionProbeDependencyHandler(SingleResourceDependencyHandler):
    resource_kind = "environment_probe"
    resource_key = "probeDataRef"


class DecalMaterialDependencyHandler(SingleResourceDependencyHandler):
    resource_kind = "material"
    resource_key = "material"


NODE_HANDLERS.register(EntityDependencyHandler(), *ENTITY_NODE_TYPES)
NODE_HANDLERS.register(DirectMeshDependencyHandler(), *DIRECT_MESH_NODE_TYPES)
NODE_HANDLERS.register(StandardMeshDependencyHandler(), *STANDARD_MESH_NODE_TYPES)
NODE_HANDLERS.register(
    InstancedDestructibleDependencyHandler(),
    *INSTANCED_DESTRUCTIBLE_NODE_TYPES,
)
NODE_HANDLERS.register(ProxyMeshDependencyHandler(), *PROXY_NODE_TYPES)


NODE_HANDLERS.register_dependencies(
    DecalMaterialDependencyHandler(),
    "worldStaticDecalNode",
)


NODE_HANDLERS.register_dependencies(
    StaticLightDependencyHandler(),
    "worldStaticLightNode",
)
NODE_HANDLERS.register_dependencies(
    ReflectionProbeDependencyHandler(),
    "worldReflectionProbeNode",
)


NODE_HANDLERS.register_dependencies(
    EffectResourceDependencyHandler(),
    "worldStaticParticleNode",
    "worldEffectNode",
)


NODE_HANDLERS.register_dependencies(
    AcousticResourceDependencyHandler(),
    "worldAcousticSectorNode",
)
NODE_HANDLERS.register_dependencies(
    MinimapResourceDependencyHandler(),
    "MinimapDataNode",
)


NODE_HANDLERS.register_dependencies(
    SemanticResourceDependencyHandler(),
    "worldAISpotNode",
    "worldPopulationSpawnerNode",
    "worldCompiledSmartObjectsNode",
    "worldSmartObjectNode",
    "worldStaticGpsLocationEntranceMarkerNode",
)


NODE_HANDLERS.register_dependencies(
    GIResourceDependencyHandler(),
    "worldGINode",
)
