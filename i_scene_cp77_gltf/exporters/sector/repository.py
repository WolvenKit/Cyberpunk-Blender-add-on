<<<<<<< Updated upstream
import json
import os


class SectorSourceRepository:
    def __init__(self):
        self._documents = {}
        self._node_data = {}

    def load(self, path):
        key = os.path.normcase(os.path.realpath(os.fspath(path)))
        document = self._documents.get(key)
        if document is None:
            with open(key, "r", encoding="utf-8") as stream:
                document = json.load(stream)
            self._documents[key] = document
        return document

    def node_data(self, path, node_index):
        key = os.path.normcase(os.path.realpath(os.fspath(path)))
        document = self.load(key)
        index = self._node_data.get(key)
        if index is None:
            index = {}
            entries = document["Data"]["RootChunk"]["nodeData"]["Data"]
            for entry in entries:
                index.setdefault(int(entry["NodeIndex"]), []).append(entry)
            self._node_data[key] = index
        return tuple(index.get(int(node_index), ()))
=======
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
>>>>>>> Stashed changes
