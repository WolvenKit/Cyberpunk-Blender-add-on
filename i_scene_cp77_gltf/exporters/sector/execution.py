import os
from collections import Counter

import bpy

from ...assetio.archive_xl import archive_xl_document, serialize_archive_xl
from ...assetio.atomic import atomic_write_many
from ...assetio.documents import DocumentSession
from ...assetio.json_style import JsonStyle, styled_dumps
from ...assetio.paths import depot_path_key
from ...assetio.project_layout import cpmodproj_layout
from ...assetio.streaming_block import streaming_block_document
from ...blender.operator_results import OperationResult
from ...core.log import get_logger
from .buffers import ScenePlacements
from .edits import edited_lights, scaled_objects, sector_edits
from .new_sectors import new_sector_collections
from .repository import SectorSourceRepository
from .writer import skipped_objects, write_generated_sector, write_new_sector

_LOG = get_logger(__name__)
# How many skipped objects a warning names.
_NAMED = 3
# The sectors written for each source sector of what the export deletes from it for a copy: the suffix of their name,
# what they hold and how the objects are found.
_GENERATED = (
    ("_lights", "the edited lights", edited_lights),
    ("_scaled", "the scaled placements", scaled_objects),
)


def _sources_by_name(parsed):
    """The parsed source sectors by name"""
    counts = Counter(source.sector_name for _collection, source in parsed)
    return {
        source.sector_name: source
        for _collection, source in parsed
        if counts[source.sector_name] == 1
    }


def _skipped_warning(collection, skipped):
    names = ", ".join(obj.name for obj in skipped[:_NAMED])
    more = f" and {len(skipped) - _NAMED} more" if len(skipped) > _NAMED else ""
    return (
        f"{collection.name} holds objects that are not copies of imported placements, so they are not written: "
        f"{names}{more}."
    )


def _written_sectors(scene, placements, parsed, layout, include_heightfields):
    """(written for, JSON text, descriptor) per sector written, and warnings"""
    sources = _sources_by_name(parsed)
    written, warnings = [], []
    for collection in new_sector_collections(scene):
        sector = write_new_sector(
            collection, sources, layout, include_heightfields=include_heightfields
        )
        if sector is not None:
            written.append((collection.name, *sector))
        skipped = skipped_objects(collection)
        if skipped:
            warnings.append(_skipped_warning(collection, skipped))
    for collection, source in parsed:
        for suffix, what, found in _GENERATED:
            objects = found(collection, source, placements)
            if objects:
                written.append(
                    (
                        f"{what} of {source.sector_name}",
                        *write_generated_sector(
                            source.sector_name, objects, source, layout, suffix
                        ),
                    )
                )
    owners = {}
    for owner, _text, descriptor in written:
        key = depot_path_key(descriptor.depot_path)
        if key in owners:
            raise ValueError(
                f"{owners[key]} and {owner} would both be written to {descriptor.depot_path}; rename the "
                "new sector."
            )
        owners[key] = owner
    return written, warnings


def _export(filename, use_yaml, include_heightfields):
    """Write the scene's sector edits for the project filename"""
    if not os.path.isdir(os.path.dirname(filename)):
        raise FileNotFoundError(
            f"Project path does not exist: {os.path.dirname(filename)}"
        )
    layout = cpmodproj_layout(filename)
    scene = bpy.context.scene
    placements = ScenePlacements(scene)
    with DocumentSession() as documents:
        repository = SectorSourceRepository(documents)
        parsed = [
            (collection, repository.parsed(collection["cp77_sector_path"]))
            for collection in placements.sectors
        ]
        sectors = tuple(
            sector_edits(collection, source, placements)
            for collection, source in parsed
        )
        written, warnings = _written_sectors(
            scene, placements, parsed, layout, include_heightfields
        )
    payloads = {}
    for _owner, text, descriptor in written:
        payloads[layout.raw_file(descriptor.depot_path, ".streamingsector.json")] = (
            text.encode("utf-8")
        )
    sector_paths = tuple(payloads)
    block_path, blocks = None, ()
    if written:
        # One block lists the sectors this export writes; files of new sectors since removed stay, unlisted.
        block = f"{layout.name}\\{layout.name}.streamingblock"
        block_path = layout.raw_file(block, ".streamingblock.json")
        document = streaming_block_document(
            [descriptor for _owner, _text, descriptor in written],
            archive_file_name=layout.archive_file(block),
        )
        payloads[block_path] = styled_dumps(document, JsonStyle()).encode("utf-8")
        blocks = (block,)
    archive_xl_path = os.path.join(
        layout.root, "source", "resources", f"{layout.name}.archive.xl"
    )
    payloads[archive_xl_path] = serialize_archive_xl(
        archive_xl_document(sectors, blocks), use_yaml=use_yaml
    ).encode("utf-8")
    atomic_write_many(payloads)
    _LOG.info(
        "Exported sector edits to %s and %d sectors", archive_xl_path, len(sector_paths)
    )
    paths = {
        "archive_xl_path": archive_xl_path,
        "sector_paths": sector_paths,
        "block_path": block_path,
    }
    return paths, sectors, tuple(warnings)


def export_project_sectors(
    filename, use_yaml, *, include_heightfields=False
) -> OperationResult:
    """Write the project's sector edits and new sectors, writing nothing on failure"""
    try:
        paths, sectors, warnings = _export(filename, use_yaml, include_heightfields)
    except Exception as error:
        # The log keeps the traceback; the author is shown the message alone.
        return OperationResult.cancelled(f"Sector export failed: {error}", error=error)
    edited = [sector for sector in sectors if sector.deletions or sector.mutations]
    moved = sum(len(sector.mutations) for sector in edited)
    deleted = sum(len(sector.deletions) for sector in edited)
    return OperationResult.finished(
        f"Exported {os.path.basename(paths['archive_xl_path'])}: {len(edited)} sectors edited, {moved} placements "
        f"moved, {deleted} deleted, {len(paths['sector_paths'])} new sectors.",
        warnings=warnings,
        paths=paths,
    )
