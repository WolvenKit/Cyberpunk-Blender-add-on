import os

from ..assetio.index import IndexPolicy, build_asset_index
from ..assetio.paths import LocalPath

from ..assetio.catalog import ResourceKind, resource_spec_for_path
from ..assetio.repository import ResourceRepository
from .model import ResolvedMaterialChain
from .parser import parse_material_bundle, parse_material_document


MATERIAL_PARSER_REVISION = 2
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
    def __init__(self, primary=None, *, policy=IndexPolicy.REFRESH):
        self.primary = primary
        self.policy = IndexPolicy(policy)
        self._indexes = {}

    def resolve(self, reference, root, extension):
        if not reference or not root or not extension:
            return None
        root_identity = LocalPath.from_value(root)
        extension = str(extension).casefold()
        primary = self.primary
        if (
            primary is not None
            and primary.root.key == root_identity.key
            and extension in primary.extensions
        ):
            return primary.resolve_expected(reference, extension, warn=False)

        key = (root_identity.key, extension)
        index = self._indexes.get(key)
        if index is None:
            index = build_asset_index(
                root_identity.value,
                (extension,),
                policy=self.policy,
            )
            self._indexes[key] = index
        return index.resolve_expected(reference, extension, warn=False)

    @property
    def snapshots(self):
        values = []
        if self.primary is not None:
            values.append(self.primary)
        values.extend(self._indexes.values())
        return tuple(values)

    def clear(self):
        self._indexes.clear()


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
        image_index_policy=IndexPolicy.REFRESH,
    ):
        self.documents = documents
        self.asset_index = asset_index
        self.asset_indexes = asset_indexes or MaterialAssetIndexes(
            asset_index,
            policy=image_index_policy,
        )
        self._repositories = {}

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
        self.asset_indexes.clear()

    def load(self, reference, *, expected_kind=None, required=False):
        kind = (
            ResourceKind(expected_kind)
            if expected_kind is not None
            else _kind_for_reference(reference)
        )
        value = os.fspath(reference) if reference else ""
        if value and not os.path.isfile(value) and not value.casefold().endswith(".json"):
            value = f"{value}.json"
        return self._repository_for(kind).load(value, required=required)

    def resolve_chain(self, reference, *, required=False):
        first = self.load(reference, required=required)
        if first is None:
            return ResolvedMaterialChain(())
        documents = []
        seen = set()
        current = first
        while current is not None:
            source_key = os.path.normcase(os.path.abspath(current.source_path))
            if source_key in seen:
                raise ValueError(f"Material inheritance cycle at {current.source_path}")
            seen.add(source_key)
            documents.append(current)
            base = _base_material_path(current.root)
            if not base:
                break
            current = self.load(base, required=required)
        return ResolvedMaterialChain(tuple(documents))


def _kind_for_reference(reference):
    spec = resource_spec_for_path(reference)
    if spec is not None and spec.kind in MATERIAL_RESOURCE_KINDS:
        return spec.kind
    value = str(reference or "").replace("\\", "/").casefold()
    for suffix, kind in _RESOURCE_SUFFIX_KIND_PAIRS:
        if value.endswith(suffix) or f"{suffix}.json" in value:
            return kind
    raise ValueError(f"Cannot infer material resource kind for {reference}")


def _export_suffix(kind):
    return _EXPORT_SUFFIXES[kind]


def _base_material_path(root):
    base = root.get("baseMaterial") if isinstance(root, dict) else None
    depot = base.get("DepotPath") if isinstance(base, dict) else None
    if isinstance(depot, dict):
        return str(depot.get("$value", "") or "")
    return str(depot or "")
