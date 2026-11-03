from ...assetio.catalog import ResourceKind
<<<<<<< Updated upstream
from ...assetio.repository import ResourceRepository
from .parser import parse_sector_document


SECTOR_PARSER_REVISION = 2
=======
from ...assetio.paths import depot_path_key
from ...assetio.repository import ResourceLoadError, ResourceRepository
from ...assetio.streaming_sector import SectorLayoutError
from .parser import parse_sector_document

SECTOR_PARSER_REVISION = 3
>>>>>>> Stashed changes


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
<<<<<<< Updated upstream
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
=======
        value = depot_path_key(reference)
        if (
            value.endswith(
                (
                    ".streamingsector_inplace",
                    ".streamingsector_inplace.json",
                )
            )
            and self.asset_index is not None
        ):
            return (
                self.asset_index.resolve_expected(
                    reference,
                    ".streamingsector_inplace.json",
                )
                or ""
            )
>>>>>>> Stashed changes
        return super().resolve(reference)

    def load_sector(
        self,
        reference,
        *,
        parent_sector="",
        parent_sector_path="",
<<<<<<< Updated upstream
        composition_depth=0,
        source_kind="root",
        source_depot_path="",
=======
>>>>>>> Stashed changes
        required=False,
    ):
        source = self.resolve(reference)
        options = (
            source,
            parent_sector,
            parent_sector_path,
<<<<<<< Updated upstream
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
=======
        )
        try:
            return self.load(
                source or reference,
                required=required,
                parser_options=options,
                parser_kwargs={
                    "source_path": source,
                    "parent_sector": parent_sector,
                    "parent_sector_path": parent_sector_path,
                },
            )
        except ResourceLoadError as error:
            # A sector in another layout stops the import with its own message, which names the file.
            if isinstance(error.__cause__, SectorLayoutError):
                raise SectorLayoutError(str(error.__cause__)) from error
            raise
>>>>>>> Stashed changes
