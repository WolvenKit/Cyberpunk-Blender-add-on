from ...assetio.catalog import ResourceKind
from ...assetio.repository import ResourceRepository
from .parser import parse_appearance_document


APPEARANCE_PARSER_REVISION = 1


class AppearanceRepository(ResourceRepository):
    def __init__(self, documents, *, asset_index=None):
        super().__init__(
            documents,
            resource_kind=ResourceKind.APPEARANCE,
            parser=parse_appearance_document,
            parser_revision=APPEARANCE_PARSER_REVISION,
            asset_index=asset_index,
            export_suffix=".app.json",
        )
