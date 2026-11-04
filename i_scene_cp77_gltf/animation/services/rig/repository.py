import copy
import os

from ....assetio.catalog import ResourceKind
from ....assetio.diagnostics import IssueSeverity, ResourceIssue
from ....assetio.documents import DocumentSession
from ....assetio.paths import is_local_absolute, local_path_key
from ....assetio.repository import ResourceLoadError, ResourceRepository
from ....core.log import debug_exception, get_logger
from .parser import RigParseMode, RigParseOptions, parse_rig_document, parse_rig_payload

RIG_PARSER_REVISION = 1
_LOG = get_logger(__name__)
_STORED_DOCUMENTS = None


def register_stored_rig_documents(provider) -> None:
    """Install provider(path), the rig document a MetaRig in the file carries for a part path"""
    global _STORED_DOCUMENTS
    _STORED_DOCUMENTS = provider


def unregister_stored_rig_documents(provider=None) -> None:
    global _STORED_DOCUMENTS
    if provider is None or _STORED_DOCUMENTS is provider:
        _STORED_DOCUMENTS = None


def stored_rig_document(reference):
    """The rig document a bundled MetaRig carries for the part path reference, or None"""
    value = os.fspath(reference) if reference else ""
    provider = _STORED_DOCUMENTS
    if (
        provider is None
        or not value
        or is_local_absolute(value)
        or not value.casefold().endswith(".rig.json")
    ):
        return None
    return provider(value)


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
        self._stored = {}

    def load(self, reference, *, required=False, mode=RigParseMode.IMPORT):
        options = RigParseOptions(RigParseMode(mode))
        stored = stored_rig_document(reference)
        if stored is not None:
            return self._load_stored(os.fspath(reference), stored, options, required)
        return super().load(
            reference,
            required=required,
            parser_options=(options.mode.value,),
            parser_kwargs={"options": options},
        )

    def _load_stored(self, reference, document, options, required):
        key = (local_path_key(reference), id(document), options.mode.value)
        parsed = self._stored.get(key)
        if parsed is None:
            try:
                parsed = parse_rig_payload(document, reference, options=options)
            except Exception as error:
                issue = ResourceIssue(
                    IssueSeverity.ERROR,
                    "repository.parse",
                    reference,
                    f"{reference}: {error}",
                    ResourceKind.RIG.value,
                )
                self._issues.append(issue)
                if required:
                    raise ResourceLoadError(
                        reference, ResourceKind.RIG, (issue,)
                    ) from error
                return None
            self._stored[key] = parsed
        return parsed


def rig_source_document(filepath):
    """A copy of the document a .rig.json export was parsed from, or None when the file cannot be read"""
    if not filepath or not str(filepath).casefold().endswith(".rig.json"):
        return None
    try:
        with DocumentSession() as documents:
            rig_data = RigRepository(documents).load(filepath, required=True)
    except Exception:
        debug_exception(_LOG, "Could not read the rig source document %s", filepath)
        return None
    return copy.deepcopy(rig_data.source_document)


def load_rigs(paths, *, mode=RigParseMode.IMPORT) -> tuple:
    """Parse each rig document in one document session"""
    with DocumentSession() as documents:
        repository = RigRepository(documents)
        return tuple(repository.load(path, required=True, mode=mode) for path in paths)
