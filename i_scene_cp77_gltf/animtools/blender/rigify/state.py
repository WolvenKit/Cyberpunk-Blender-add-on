from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

import bpy

from ....core.log import get_logger

_LOG = get_logger(__name__)


@dataclass
class RigifyBuildSession:
    source: bpy.types.Object
    context: object
    meta: bpy.types.Object | None = None
    rig: bpy.types.Object | None = None
    stats: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    source_collections: tuple = ()

    @classmethod
    def create(cls, source: bpy.types.Object, context):
        if source is None or source.type != "ARMATURE":
            raise ValueError("Valid armature required")
        return cls(
            source=source,
            context=context,
            source_collections=tuple(getattr(source, "users_collection", ()) or ()),
        )

    def log(self, message: str, *args, level: int = logging.DEBUG, **kwargs) -> None:
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        _LOG.log(level, message, *args, **kwargs)


class RigifyStage:
    def __init__(self, session: RigifyBuildSession):
        self.session = session

    @property
    def source(self):
        return self.session.source

    @property
    def context(self):
        return self.session.context

    @property
    def meta(self):
        return self.session.meta

    @meta.setter
    def meta(self, value):
        self.session.meta = value

    @property
    def rig(self):
        return self.session.rig

    @rig.setter
    def rig(self, value):
        self.session.rig = value

    @property
    def stats(self):
        return self.session.stats

    @property
    def source_collections(self):
        return self.session.source_collections

    def log(self, message: str, *args, level: int = logging.DEBUG, **kwargs) -> None:
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        self.session.log(message, *args, level=level, **kwargs)
