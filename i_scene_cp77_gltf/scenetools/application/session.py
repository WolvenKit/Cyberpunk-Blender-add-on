from __future__ import annotations

from ...blender.transactions import (
    BlenderImportTransaction,
    raise_if_rollback_incomplete,
)
from ..blender.weather import weather_collection
from ..runtime.ownership import (
    ensure_scene_owner_id,
    find_owned,
    scene_has_owned_runtime,
)


class SceneToolsSession:
    __slots__ = (
        "_scope",
        "context",
        "owner_id",
        "scene",
        "settings",
        "transaction",
        "transactional",
    )

    def __init__(self, scene, settings, *, context=None, transactional=False):
        self.scene = scene
        self.settings = settings
        self.context = context
        self.transactional = bool(transactional)
        self.owner_id = ""
        self.transaction = None
        self._scope = None

    def __enter__(self):
        if self.transactional:
            self.transaction = BlenderImportTransaction(
                capture_existing_state=True,
                restore_context=True,
            )
            self._scope = self.transaction.scope()
            self._scope.__enter__()
        self.owner_id = ensure_scene_owner_id(self.scene)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        scope = self._scope
        transaction = self.transaction
        self._scope = None
        if scope is not None:
            scope.__exit__(exc_type, exc_value, traceback)
        if transaction is None:
            return False
        if exc_type is None:
            transaction.commit()
            return False
        raise_if_rollback_incomplete(
            transaction.rollback(), exc_value, label="SceneTools"
        )
        return False

    @property
    def world(self):
        return find_owned("worlds", self.scene, "WORLD")

    @property
    def global_light(self):
        return find_owned("objects", self.scene, "GLOBAL_LIGHT")

    @property
    def global_specular_light(self):
        return find_owned("objects", self.scene, "GLOBAL_SPECULAR_LIGHT")

    @property
    def weather_collection(self):
        return weather_collection(self.scene, create=False)

    @property
    def has_runtime(self):
        return scene_has_owned_runtime(self.scene)
