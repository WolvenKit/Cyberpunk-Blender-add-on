from contextlib import contextmanager
from contextvars import ContextVar

from ..assetio.documents import DocumentSession
from ..assetio.resolver import resolve_asset_path
from .repository import MaterialRepository, MaterialResourceRepository


_ACTIVE_MATERIAL_RESOURCES = ContextVar("cp77_material_resources", default=None)


@contextmanager
def material_resource_scope(repository):
    token = _ACTIVE_MATERIAL_RESOURCES.set(repository)
    try:
        yield repository
    finally:
        _ACTIVE_MATERIAL_RESOURCES.reset(token)


def active_material_asset_indexes():
    repository = _ACTIVE_MATERIAL_RESOURCES.get()
    return getattr(repository, "asset_indexes", None) if repository is not None else None


def load_material_document(reference, *, roots=(), expected_kind=None, extensions=()):
    resolved = resolve_asset_path(
        reference,
        roots=roots,
        extensions=extensions,
        warn=False,
    ) if roots or extensions else reference
    if not resolved:
        return None
    repository = _ACTIVE_MATERIAL_RESOURCES.get()
    if repository is not None:
        return repository.load(
            resolved,
            expected_kind=expected_kind,
            required=False,
        )
    with DocumentSession() as documents:
        return MaterialResourceRepository(documents).load(
            resolved,
            expected_kind=expected_kind,
            required=False,
        )


def load_material_bundle(reference):
    with DocumentSession() as documents:
        return MaterialRepository(documents).load(reference, required=True)
