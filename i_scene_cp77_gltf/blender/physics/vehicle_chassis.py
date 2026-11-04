VEHICLE_CHASSIS_SOURCE_KIND = "VEHICLE_CHASSIS_PHYS"


def vehicle_chassis_phys_objects(scene, rig=None):
    rig_name = rig.name if rig is not None else ""
    result = []
    for item in getattr(getattr(scene, "physx", None), "actors", ()):
        obj = item.obj_ref
        if (
            obj is None
            or getattr(obj.physx, "source_kind", "") != VEHICLE_CHASSIS_SOURCE_KIND
        ):
            continue
        owner = str(obj.get("cp77_vehicle_chassis_rig", "") or "")
        if rig_name and owner and owner != rig_name:
            continue
        result.append(obj)
    return tuple(result)
