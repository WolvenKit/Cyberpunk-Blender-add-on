from contextlib import contextmanager
from contextvars import ContextVar

from ..assetio.documents import DocumentSession
from ..assetio.resolver import resolve_asset_path
from .repository import MaterialRepository, MaterialResourceRepository

<<<<<<< Updated upstream

=======
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    return getattr(repository, "asset_indexes", None) if repository is not None else None


def load_material_document(reference, *, roots=(), expected_kind=None, extensions=()):
    resolved = resolve_asset_path(
        reference,
        roots=roots,
        extensions=extensions,
        warn=False,
    ) if roots or extensions else reference
=======
    return (
        getattr(repository, "asset_indexes", None) if repository is not None else None
    )


def load_material_document(
    reference, *, roots=(), expected_kind=None, extensions=(), required=False
):
    """The parsed document at reference, or None when it cannot be read"""
    resolved = (
        resolve_asset_path(
            reference,
            roots=roots,
            extensions=extensions,
            warn=False,
        )
        if roots or extensions
        else reference
    )
>>>>>>> Stashed changes
    if not resolved:
        return None
    repository = _ACTIVE_MATERIAL_RESOURCES.get()
    if repository is not None:
        return repository.load(
            resolved,
            expected_kind=expected_kind,
<<<<<<< Updated upstream
            required=False,
=======
            required=required,
>>>>>>> Stashed changes
        )
    with DocumentSession() as documents:
        return MaterialResourceRepository(documents).load(
            resolved,
            expected_kind=expected_kind,
<<<<<<< Updated upstream
            required=False,
=======
            required=required,
>>>>>>> Stashed changes
        )


def load_material_bundle(reference):
    with DocumentSession() as documents:
        return MaterialRepository(documents).load(reference, required=True)
