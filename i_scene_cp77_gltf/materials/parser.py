from .appearances import normalize_material_appearances
from .model import MaterialBundle, MaterialDocument


def parse_material_bundle(payload):
    return MaterialBundle(
        payload["MaterialRepo"] + "\\",
        normalize_material_appearances(payload["Appearances"]),
        tuple(payload["Materials"]),
    )


def parse_material_document(document):
    root = document.payload["Data"]["RootChunk"]
    return MaterialDocument(
        document.source.value,
        document.identity.key,
        document.resource_kind,
        document.payload,
        root,
    )


def base_material_path(root):
    """The depot path a material document's RootChunk inherits from (its baseMaterial), or ''"""
    base = root.get("baseMaterial") if isinstance(root, dict) else None
    depot = base.get("DepotPath") if isinstance(base, dict) else None
    if isinstance(depot, dict):
        return str(depot.get("$value", "") or "")
    return str(depot or "")
