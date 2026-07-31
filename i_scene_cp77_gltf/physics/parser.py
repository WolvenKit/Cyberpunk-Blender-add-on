from .model import PhysicsResource


def _collect_handles(value, lookup):
    if isinstance(value, dict):
        data = value.get("Data")
        handle_id = value.get("HandleId")
        if handle_id is not None and isinstance(data, dict):
            lookup.setdefault(str(handle_id), data)
        for child in value.values():
            _collect_handles(child, lookup)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _collect_handles(child, lookup)


def parse_physics_document(document):
    root = document.payload["Data"]["RootChunk"]
    bodies = root.get("bodies")
    if not isinstance(bodies, list):
        raise ValueError("Data.RootChunk.bodies must be a list")
    handles = {}
    _collect_handles(root, handles)
    return PhysicsResource(root, tuple(bodies), handles, document.source.value)
