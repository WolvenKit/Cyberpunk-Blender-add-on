from __future__ import annotations

import os
from dataclasses import (
    dataclass,
    field,
)
from typing import Any

from ...assetio.catalog import normalize_extensions
from ...assetio.documents import DocumentSession
from ...assetio.index import (
    build_asset_index,
    indexed_files,
)
from ...assetio.paths import LocalPath
from ...materials.repository import MaterialResourceRepository
from ...materials.resources import material_resource_scope
from .options import MaterialToolsRequest


@dataclass(slots=True)
class MaterialToolsSession:
    """Own document, index, and material-resource lifetime for one tool operation"""

    request: MaterialToolsRequest
    documents: Any = None
    provided_asset_index: Any = None

    asset_index: Any = field(init=False, default=None)
    material_resources: MaterialResourceRepository | None = field(
        init=False, default=None
    )
    _owns_documents: bool = field(init=False, default=False)
    _resource_scope: Any = field(init=False, default=None)
    _entered: bool = field(init=False, default=False)

    def __enter__(self) -> MaterialToolsSession:
        if self._entered:
            return self
        if not self.request.root or not os.path.isdir(self.request.root):
            raise ValueError("Material Tools resource root is not a valid directory")
        if self.documents is None:
            self.documents = DocumentSession()
            self._owns_documents = True
        try:
            if self.provided_asset_index is not None:
                if (
                    self.provided_asset_index.root.key
                    != LocalPath.from_value(self.request.root).key
                ):
                    raise ValueError(
                        "Provided asset index root does not match Material Tools resource root"
                    )
                missing = set(self.request.extensions).difference(
                    self.provided_asset_index.extensions
                )
                if missing:
                    raise ValueError(
                        "Provided asset index is missing Material Tools suffixes: "
                        + ", ".join(sorted(missing))
                    )
                self.asset_index = self.provided_asset_index
            elif self.request.extensions:
                self.asset_index = build_asset_index(
                    self.request.root,
                    self.request.extensions,
                    policy=self.request.index_policy,
                )
            else:
                self.asset_index = None
            self.material_resources = MaterialResourceRepository(
                self.documents,
                asset_index=self.asset_index,
                image_index_policy=self.request.index_policy,
            )
            self._resource_scope = material_resource_scope(self.material_resources)
            self._resource_scope.__enter__()
            self._entered = True
            return self
        except Exception:
            self.close()
            raise

    def files(self, *extensions: str) -> tuple[str, ...]:
        self._require_entered()
        if self.asset_index is None:
            raise RuntimeError("MaterialToolsSession has no asset index")
        requested = normalize_extensions(extensions)
        return tuple(indexed_files(self.asset_index, *requested))

    @property
    def collisions(self):
        self._require_entered()
        if self.asset_index is None:
            return ()
        return tuple(self.asset_index.collisions)

    def close(self) -> None:
        if self._resource_scope is not None:
            self._resource_scope.__exit__(None, None, None)
            self._resource_scope = None
        if self.material_resources is not None:
            self.material_resources.clear()
            self.material_resources = None
        self.asset_index = None
        if self.documents is not None and self._owns_documents:
            self.documents.close()
            self.documents = None
        self._owns_documents = False
        self._entered = False

    def _require_entered(self) -> None:
        if not self._entered:
            raise RuntimeError("MaterialToolsSession must be entered before use")

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.close()
        return False
