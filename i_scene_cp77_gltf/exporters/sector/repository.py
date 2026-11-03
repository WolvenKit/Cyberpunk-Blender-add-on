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
