from ...assetio.catalog import ResourceKind
from ...assetio.repository import ResourceRepository
from .parser import parse_entity_document


ENTITY_PARSER_REVISION = 1


class EntityRepository(ResourceRepository):
    def __init__(self, documents, *, asset_index=None):
        super().__init__(
            documents,
            resource_kind=ResourceKind.ENTITY,
            parser=parse_entity_document,
            parser_revision=ENTITY_PARSER_REVISION,
            asset_index=asset_index,
            export_suffix=".ent.json",
        )
