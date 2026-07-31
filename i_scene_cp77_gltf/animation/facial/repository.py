from dataclasses import dataclass

from ...assetio.catalog import ResourceKind
from ...assetio.repository import ResourceRepository
from ..rig import RigParseMode, RigRepository
from .loader import parse_facial_setup


FACIAL_PARSER_REVISION = 1


@dataclass(frozen=True, slots=True)
class FacialResource:
    setup: object
    rig: object
    setup_path: str
    rig_path: str


class FacialRepository:
    def __init__(self, documents, *, asset_index=None, rig_repository=None):
        self.documents = documents
        self.setups = ResourceRepository(
            documents,
            resource_kind=ResourceKind.FACIAL_SETUP,
            parser=parse_facial_setup,
            parser_revision=FACIAL_PARSER_REVISION,
            asset_index=asset_index,
            export_suffix=".facialsetup.json",
        )
        self.rigs = rig_repository or RigRepository(documents, asset_index=asset_index)
        self._cache = {}

    @property
    def issues(self):
        return (*self.setups.issues, *self.rigs.issues)

    def clear(self):
        self.setups.clear()
        self.rigs.clear()
        self._cache.clear()

    def load(self, setup_reference, rig_reference, *, required=False):
        setup = self.setups.load(setup_reference, required=required)
        rig = self.rigs.load(rig_reference, required=required, mode=RigParseMode.FACIAL)
        if setup is None or rig is None:
            return None
        key = (id(setup), id(rig))
        resource = self._cache.get(key)
        if resource is None:
            setup_path = self.setups.resolve(setup_reference)
            rig_path = self.rigs.resolve(rig_reference)
            resource = FacialResource(setup, rig, setup_path, rig_path)
            self._cache[key] = resource
        return resource
