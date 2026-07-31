from ..assetio.catalog import ResourceKind
from ..assetio.repository import ResourceRepository
from .parser import parse_physics_document


PHYSICS_PARSER_REVISION = 1


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
