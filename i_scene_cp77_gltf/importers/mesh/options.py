from dataclasses import dataclass
from typing import Any

from ...materials.blender.images import DEFAULT_IMAGE_FORMAT


@dataclass(frozen=True, slots=True)
class GlbImportOptions:
    with_materials: bool = False
    remap_depot: bool = False
    exclude_unused_mats: bool = True
    image_format: str = DEFAULT_IMAGE_FORMAT
    hide_armatures: bool = True
    import_garmentsupport: bool = True
    appearances: tuple[str, ...] = ()
    import_tracks: bool = True
    animation_target: Any = "AUTO"
    content_kind: str | None = None
    bulk_import: bool = False
    collection_name: str = ""
    select_objects: bool = True
    appearance_variants: bool = True
