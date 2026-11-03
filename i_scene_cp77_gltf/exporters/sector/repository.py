import os

from ...assetio.documents import DocumentLoadError
from ...importers.sector.parser import parse_sector_document


class SectorSourceRepository:
    """The source sectors of an export, each read and parsed once"""

    def __init__(self, documents):
        self.documents = documents
        self._parsed = {}

    def parsed(self, path):
        """The ParsedSector of the sector file path"""
        key = os.path.normcase(os.path.realpath(os.fspath(path)))
        parsed = self._parsed.get(key)
        if parsed is not None:
            return parsed
        document = self.documents.load(key)
        if document is None:
            # The session records why it read nothing.
            raise DocumentLoadError(self.documents.issues[-1])
        parsed = self._parsed[key] = parse_sector_document(
            document.payload, source_path=os.fspath(path)
        )
        return parsed
