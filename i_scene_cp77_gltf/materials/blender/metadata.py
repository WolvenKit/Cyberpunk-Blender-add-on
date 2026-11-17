def material_metadata(material_data):
    if "BaseMaterial" not in material_data:
        return None
    data = material_data.get("Data", {})
    return {
        "Name": material_data.get("Name", ""),
        "BaseMaterial": material_data["BaseMaterial"],
        "GlobalNormal": data.get("GlobalNormal", "None"),
        "MultilayerMask": data.get("MultilayerMask", "None"),
        "DiffuseMap": data.get(
            "DiffuseMap",
            data.get("BaseColor", data.get("DiffuseTexture", "None")),
        ),
    }


def apply_material_metadata(material, metadata):
    """Preserve source metadata without retagging unchanged shared materials"""
    values = {
        "cp77_source_material_name": metadata["Name"],
        "BaseMaterial": metadata["BaseMaterial"],
        "GlobalNormal": metadata["GlobalNormal"],
        "MultilayerMask": metadata["MultilayerMask"],
        "DiffuseMap": metadata["DiffuseMap"],
    }
    for key, value in values.items():
        if key not in material or material.get(key) != value:
            material[key] = value
