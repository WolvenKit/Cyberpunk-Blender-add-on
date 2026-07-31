from ...assetio.catalog import ResourceKind
from ...assetio.repository import ResourceRepository
from .parser import RigParseMode, RigParseOptions, parse_rig_document


RIG_PARSER_REVISION = 1


class RigRepository(ResourceRepository):
    def __init__(self, documents, *, asset_index=None):
        super().__init__(
            documents,
            resource_kind=ResourceKind.RIG,
            parser=parse_rig_document,
            parser_revision=RIG_PARSER_REVISION,
            asset_index=asset_index,
            export_suffix=".rig.json",
            parser_receives_document=True,
        )

    def load(self, reference, *, required=False, mode=RigParseMode.IMPORT):
        options = RigParseOptions(RigParseMode(mode))
        return super().load(
            reference,
            required=required,
            parser_options=(options.mode.value,),
            parser_kwargs={"options": options},
        )
