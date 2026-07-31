from .model import MaterialBundle, MaterialDocument


def parse_material_bundle(payload):
    return MaterialBundle(
        payload["MaterialRepo"] + "\\",
        payload["Appearances"],
        tuple(payload["Materials"]),
    )


def parse_material_document(document):
    root = document.payload["Data"]["RootChunk"]
    return MaterialDocument(
        document.source.value,
        document.resource_kind,
        document.payload,
        root,
    )
