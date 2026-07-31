from __future__ import annotations

from typing import Optional

import bpy

from ....blender.animation_context import active_armature
from ....blender.context import restore_previous_context, store_current_context
from .binding import RigifyBindingService
from .generated import GeneratedRigBuilder
from .metarig import MetarigBuilder
from .state import RigifyBuildSession
from .pairing import find_metarig


class RigifyConversionService:
    def __init__(self, source_armature: bpy.types.Object, context):
        self.session = RigifyBuildSession.create(source_armature, context)
        self.metarig = MetarigBuilder(self.session)
        self.generated = GeneratedRigBuilder(self.session)
        self.binding = RigifyBindingService(self.session)

    def convert(self) -> bpy.types.Object:
        session = self.session
        session.log(f"Converting '{session.source.name}'", "STEP")
        store_current_context()
        try:
            existing_meta = find_metarig(session.source)
            existing_rig_name = session.source.data.get("cp77_rigify_rig")
            existing_rig = bpy.data.objects.get(existing_rig_name) if existing_rig_name else None

            if existing_meta is not None:
                session.meta = existing_meta
                session.log(f"Reusing metarig '{session.meta.name}'")
            else:
                self.metarig.create()
                self.metarig.prepare()

            self.generated.generate(existing_rig=existing_rig)
            self.binding.link_metadata()
            self.binding.bind_forward_constraints()
            self.binding.hide_metarig()
            return session.rig
        except Exception as error:
            session.log(f"FAILED: {error}", "ERROR")
            self.binding.cleanup_on_failure()
            raise
        finally:
            restore_previous_context()


def cp77_to_rigify(context) -> Optional[bpy.types.Object]:
    obj = active_armature(context)
    if obj is None or obj.type != "ARMATURE":
        print("ERROR: Select an armature")
        return None
    return RigifyConversionService(obj, context).convert()
