from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import bpy


@dataclass
class RigifyBuildSession:
    source: bpy.types.Object
    context: object
    meta: Optional[bpy.types.Object] = None
    rig: Optional[bpy.types.Object] = None
    stats: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    source_collections: tuple = ()
    created_meta: bool = False
    created_rig: bool = False
    rig_original_collections: tuple = ()

    @classmethod
    def create(cls, source: bpy.types.Object, context):
        if source is None or source.type != "ARMATURE":
            raise ValueError("Valid armature required")
        return cls(
            source=source,
            context=context,
            source_collections=tuple(getattr(source, "users_collection", ()) or ()),
        )

    def log(self, message: str, level: str = "INFO") -> None:
        symbols = {"INFO": "✓", "WARN": "⚠", "ERROR": "✗", "STEP": "➡"}
        print(f"  {symbols.get(level, '•')} {message}")


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

    def log(self, message: str, level: str = "INFO") -> None:
        self.session.log(message, level)
