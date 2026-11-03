import hashlib
import json
import os

from ..assetio.catalog import ResourceKind, resource_spec_for_path
from ..assetio.index import IndexPolicy, build_asset_index
from ..assetio.paths import (
    LOCAL_PATHS_IGNORE_CASE,
    LocalPath,
    depot_path_key,
    is_local_absolute,
)
from ..assetio.repository import ResourceRepository
from ..assetio.resolver import resolve_mirrored_export
from .model import MaterialDocument
from .parser import parse_material_bundle, parse_material_document

MATERIAL_PARSER_REVISION = 3
MATERIAL_RESOURCE_KINDS = (
    ResourceKind.MATERIAL_INSTANCE,
    ResourceKind.MATERIAL_TEMPLATE,
    ResourceKind.MLSETUP,
    ResourceKind.MLTEMPLATE,
    ResourceKind.DTEX,
    ResourceKind.GRADIENT,
    ResourceKind.HAIR_PROFILE,
    ResourceKind.MESH,
)

_RESOURCE_SUFFIX_KIND_PAIRS = (
    (".mi", ResourceKind.MATERIAL_INSTANCE),
    (".mt", ResourceKind.MATERIAL_TEMPLATE),
    (".mlsetup", ResourceKind.MLSETUP),
    (".mltemplate", ResourceKind.MLTEMPLATE),
    (".dtex", ResourceKind.DTEX),
    (".gradient", ResourceKind.GRADIENT),
    (".hp", ResourceKind.HAIR_PROFILE),
    (".mesh", ResourceKind.MESH),
)

_EXPORT_SUFFIXES = {
    ResourceKind.MATERIAL_INSTANCE: ".mi.json",
    ResourceKind.MATERIAL_TEMPLATE: ".mt.json",
    ResourceKind.MLSETUP: ".mlsetup.json",
    ResourceKind.MLTEMPLATE: ".mltemplate.json",
    ResourceKind.DTEX: ".dtex.json",
    ResourceKind.GRADIENT: ".gradient.json",
    ResourceKind.HAIR_PROFILE: ".hp.json",
    ResourceKind.MESH: ".mesh.json",
}

MATERIAL_IMAGE_EXTENSIONS = (
    ".png",
    ".dds",
    ".jpg",
    ".jpeg",
    ".tga",
    ".bmp",
)


class MaterialAssetIndexes:
    def __init__(self, primary=None, *, policy=IndexPolicy.REUSE):
        self.primary = primary
        self.policy = IndexPolicy(policy)
        self._indexes = {}
        self._resolved = {}

    def resolve(self, reference, root, extension):
        if not reference or not root or not extension:
            return None
        root_identity = LocalPath.from_value(root)
        extension = str(extension).casefold()
        cache_key = (
            root_identity.key,
            depot_path_key(reference),
            extension,
        )
        if cache_key in self._resolved:
            return self._resolved[cache_key]
        primary = self.primary
        if (
            primary is not None
            and primary.root.key == root_identity.key
            and extension in primary.extensions
        ):
            resolved = primary.resolve_expected(reference, extension, warn=False)
            self._resolved[cache_key] = resolved
            return resolved

        key = root_identity.key
        index = self._indexes.get(key)
        if index is None:
            # A file exported at its mirrored path is found without indexing the root, and where paths ignore case the
            # index (keyed by that same path) cannot find one the direct lookup missed. Indexing a depot takes seconds.
            resolved = resolve_mirrored_export(
                reference, root_identity.value, (extension,)
            )
            if resolved or LOCAL_PATHS_IGNORE_CASE:
                resolved = resolved or None
                self._resolved[cache_key] = resolved
                return resolved
            extensions = tuple(
                dict.fromkeys(
                    (
                        *MATERIAL_IMAGE_EXTENSIONS,
                        extension,
                    )
                )
            )
            index = build_asset_index(
                root_identity.value,
                extensions,
                policy=self.policy,
            )
            self._indexes[key] = index
        resolved = index.resolve_expected(reference, extension, warn=False)
        self._resolved[cache_key] = resolved
        return resolved

    @property
    def snapshots(self):
        values = []
        if self.primary is not None:
            values.append(self.primary)
        values.extend(self._indexes.values())
        return tuple(values)

    def clear(self):
        self._indexes.clear()
        self._resolved.clear()


class MaterialRepository(ResourceRepository):
    def __init__(self, documents, *, asset_index=None):
        super().__init__(
            documents,
            resource_kind=ResourceKind.MATERIAL,
            parser=parse_material_bundle,
            parser_revision=MATERIAL_PARSER_REVISION,
            asset_index=asset_index,
            export_suffix=".material.json",
        )


class MaterialResourceRepository:
    def __init__(
        self,
        documents,
        *,
        asset_index=None,
        asset_indexes=None,
        image_index_policy=IndexPolicy.REUSE,
    ):
        self.documents = documents
        self.asset_index = asset_index
        self.asset_indexes = asset_indexes or MaterialAssetIndexes(
            asset_index,
            policy=image_index_policy,
        )
        self._repositories = {}
        self._provided = {}

    def _repository_for(self, kind):
        kind = ResourceKind(kind)
        if kind not in MATERIAL_RESOURCE_KINDS:
            raise ValueError(f"Unsupported material resource kind: {kind}")
        repository = self._repositories.get(kind)
        if repository is None:
            repository = ResourceRepository(
                self.documents,
                resource_kind=kind,
                parser=parse_material_document,
                parser_revision=MATERIAL_PARSER_REVISION,
                asset_index=self.asset_index,
                export_suffix=_export_suffix(kind),
                parser_receives_document=True,
            )
            self._repositories[kind] = repository
        return repository

    @property
    def issues(self):
        return tuple(
            issue
            for repository in self._repositories.values()
            for issue in repository.issues
        )

    def clear(self):
        for repository in self._repositories.values():
            repository.clear()
        self._repositories.clear()
        self._provided.clear()
        self.asset_indexes.clear()

    def provide(self, path, payload):
        """Serve payload as the document at path until the repository is cleared"""
        local = LocalPath.from_value(path)
        digest = hashlib.blake2b(
            json.dumps(payload, sort_keys=True).encode("utf-8"), digest_size=16
        ).hexdigest()
        self._provided[local.key] = MaterialDocument(
            local.value,
            (local.key, "memory", digest),
            _kind_for_reference(local.value),
            payload,
            payload["Data"]["RootChunk"],
        )

    def load(self, reference, *, expected_kind=None, required=False):
        kind = (
            ResourceKind(expected_kind)
            if expected_kind is not None
            else _kind_for_reference(reference)
        )
        value = os.fspath(reference) if reference else ""
        if value and not value.casefold().endswith(".json"):
            if not is_local_absolute(value) or not os.path.isfile(value):
                value = f"{value}.json"
        provided = (
            self._provided.get(LocalPath.from_value(value).key)
            if self._provided and value
            else None
        )
        if provided is not None:
            return provided
        return self._repository_for(kind).load(value, required=required)


def _kind_for_reference(reference):
    spec = resource_spec_for_path(reference)
    if spec is not None and spec.kind in MATERIAL_RESOURCE_KINDS:
        return spec.kind
    value = depot_path_key(reference)
    for suffix, kind in _RESOURCE_SUFFIX_KIND_PAIRS:
        if value.endswith(suffix) or f"{suffix}.json" in value:
            return kind
    raise ValueError(f"Cannot infer material resource kind for {reference}")


def _export_suffix(kind):
    return _EXPORT_SUFFIXES[kind]
