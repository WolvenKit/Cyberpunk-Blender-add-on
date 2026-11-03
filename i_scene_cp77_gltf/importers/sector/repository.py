from ...assetio.catalog import ResourceKind
from ...assetio.repository import ResourceRepository
from .parser import parse_sector_document


SECTOR_PARSER_REVISION = 2


class SectorRepository(ResourceRepository):
    def __init__(self, documents, *, asset_index=None):
        super().__init__(
            documents,
            resource_kind=ResourceKind.STREAMING_SECTOR,
            parser=parse_sector_document,
            parser_revision=SECTOR_PARSER_REVISION,
            asset_index=asset_index,
            export_suffix=".streamingsector.json",
            accepted_kinds=(ResourceKind.STREAMING_SECTOR_INPLACE,),
        )

    def resolve(self, reference):
        value = str(reference or "").replace("\\", "/").casefold()
        if (
            value.endswith((
                ".streamingsector_inplace",
                ".streamingsector_inplace.json",
            ))
            and self.asset_index is not None
        ):
            return self.asset_index.resolve_expected(
                reference,
                ".streamingsector_inplace.json",
            ) or ""
        return super().resolve(reference)

    def load_sector(
        self,
        reference,
        *,
        parent_sector="",
        parent_sector_path="",
        composition_depth=0,
        source_kind="root",
        source_depot_path="",
        required=False,
    ):
        source = self.resolve(reference)
        options = (
            source,
            parent_sector,
            parent_sector_path,
            int(composition_depth),
            source_kind,
            source_depot_path,
        )
        return self.load(
            source or reference,
            required=required,
            parser_options=options,
            parser_kwargs={
                "source_path": source,
                "parent_sector": parent_sector,
                "parent_sector_path": parent_sector_path,
                "composition_depth": composition_depth,
                "source_kind": source_kind,
                "source_depot_path": source_depot_path,
            },
        )
