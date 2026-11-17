from __future__ import annotations

from ....bartmoss.vehicle import STANDARD_GRAVITY
from .schema.defaults import schema_resource_path

DYNG_TYPE = "animDangleConstraint_SimulationDyng"
CONSTRAINT_MULTI_TYPE = "animDyngConstraintMulti"


def authored_simulation(simulation_handle_id: str, constraint_handle_id: str) -> dict:
    return {
        "HandleId": str(simulation_handle_id),
        "Data": {
            "$type": DYNG_TYPE,
            "alpha": 1.0,
            "collisionRoundedShapes": [],
            "dangleAltersTransformsOfItsChildren": 0,
            "debugDrawingEnabled": 0,
            "drawDebugAxis": 1,
            "drawDebugCollisionCapsule": 1,
            "drawDebugCollisionShapes": 1,
            "drawDebugConstraint": 1,
            "drawDebugText": 1,
            "dyngConstraint": {
                "HandleId": str(constraint_handle_id),
                "Data": {"$type": CONSTRAINT_MULTI_TYPE, "innerConstraints": []},
            },
            "HACK_checkDangleTeleport": 0,
            "jsonCollisionShapes": {
                "DepotPath": schema_resource_path(),
                "Flags": "Default",
            },
            "jsonCollisionShapesLoadedSuccessfully": 1,
            "parentRotationAltersTransformsOfDangleAndItsChildren": 0,
            "parentRotationAltersTransformsOfNonDanglesAndItsChildren": 0,
            "particlesContainer": {
                "$type": "animDyngParticlesContainer",
                "externalForceWS": {"$type": "Vector3", "X": 0.0, "Y": 0.0, "Z": 0.0},
                "externalForceWsLink": {"$type": "animVectorLink", "node": None},
                "gravityWS": STANDARD_GRAVITY,
                "particles": [],
            },
            "rotateParentToLookAtDangle": 1,
            "solverIterations": 1,
            "substepTime": 0.01,
        },
    }
