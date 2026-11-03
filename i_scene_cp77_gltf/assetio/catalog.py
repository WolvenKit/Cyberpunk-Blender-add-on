from dataclasses import dataclass
from enum import Enum


class CachePolicy(str, Enum):
    NONE = "none"
    SESSION = "session"
    PROCESS = "process"


class ResourceFormat(str, Enum):
    JSON = "json"
    GLB = "glb"
    IMAGE = "image"
    DATA = "data"


class ResourceKind(str, Enum):
    MESH = "mesh"
    ANIMATION = "animation"
    RIG = "rig"
    FACIAL_SETUP = "facial_setup"
    TEXTURE = "texture"
    ENTITY = "entity"
    APPEARANCE = "appearance"
    STREAMING_SECTOR_INPLACE = "streaming_sector_inplace"
    STREAMING_SECTOR = "streaming_sector"
    PHYSICS = "physics"
    DTEX = "dtex"
    MATERIAL = "material"
    STREAMING_BLOCK = "streaming_block"
    GRADIENT = "gradient"
    FOLIAGE = "foliage"
    HAIR_PROFILE = "hair_profile"
    MLSETUP = "mlsetup"
    MLTEMPLATE = "mltemplate"
    MATERIAL_TEMPLATE = "material_template"
    MATERIAL_INSTANCE = "material_instance"
    PARTICLE = "particle"
    EFFECT = "effect"
    ACOUSTIC_DATA = "acoustic_data"
    ENVIRONMENT_PROBE = "environment_probe"
    MINIMAP = "minimap"
    GI_DATA = "gi_data"
    SMART_OBJECTS = "smart_objects"
    WORKSPOT = "cp77_workspot"
    ACTION_ANIM_DB = "action_anim_db"
    IES = "ies"
    ANIMGRAPH = "animgraph"
    CURVE_SET = "curve_set"
    INK_WIDGET = "ink_widget"
    INK_ATLAS = "ink_atlas"
    INK_STYLE = "ink_style"
    INK_ANIMATION = "ink_animation"
    INK_FONT_FAMILY = "ink_font_family"
    FONT = "font"


@dataclass(frozen=True, slots=True)
class ResourceExport:
    suffix: str
    format: ResourceFormat


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    kind: ResourceKind
    cooked_suffixes: tuple[str, ...]
    exports: tuple[ResourceExport, ...]
    validation_profile: str = "none"
    cache_policy: CachePolicy = CachePolicy.SESSION
    expected_root_types: tuple[str, ...] = ()

    @property
    def exported_suffixes(self):
        return tuple(export.suffix for export in self.exports)


def normalize_extension(value):
    value = str(value or "").strip().lower()
    if not value:
        return ""
    return value if value.startswith(".") else f".{value}"


def _export(suffix, format):
    return ResourceExport(normalize_extension(suffix), ResourceFormat(format))


def _spec(kind, cooked=(), exports=(), validation="none", cache=CachePolicy.SESSION, roots=()):
    return ResourceSpec(
        ResourceKind(kind),
        tuple(normalize_extension(value) for value in cooked),
        tuple(_export(suffix, format) for suffix, format in exports),
        str(validation),
        CachePolicy(cache),
        tuple(str(value) for value in roots),
    )


RESOURCE_SPECS = (
    _spec(ResourceKind.MESH, (".mesh",), ((".glb", ResourceFormat.GLB), (".mesh.json", ResourceFormat.JSON)), "cr2w"),
    _spec(ResourceKind.MESH, (".physicalscene",), ((".physicalscene.glb", ResourceFormat.GLB), (".physicalscene.json", ResourceFormat.JSON)), "cr2w"),
    _spec(ResourceKind.MESH, (".w2mesh",), ((".w2mesh.glb", ResourceFormat.GLB), (".w2mesh.json", ResourceFormat.JSON)), "cr2w"),
    _spec(ResourceKind.ANIMATION, (".anims",), ((".anims.glb", ResourceFormat.GLB), (".anims.json", ResourceFormat.JSON)), "cr2w"),
    _spec(ResourceKind.ANIMGRAPH, (".animgraph",), ((".animgraph.json", ResourceFormat.JSON),), "cr2w", roots=("animAnimGraph",)),
    _spec(ResourceKind.CURVE_SET, (".curveset",), ((".curveset.json", ResourceFormat.JSON),), "cr2w"),
    _spec(ResourceKind.CURVE_SET, (".vehcurveset",), ((".vehcurveset.json", ResourceFormat.JSON),), "cr2w"),
    _spec(ResourceKind.RIG, (".rig",), ((".rig.json", ResourceFormat.JSON),), "cr2w", roots=("animRig",)),
    _spec(ResourceKind.FACIAL_SETUP, (".facialsetup",), ((".facialsetup.json", ResourceFormat.JSON),), "cr2w"),
    _spec(ResourceKind.TEXTURE, (".xbm",), ((".png", ResourceFormat.IMAGE),)),
    _spec(ResourceKind.ENTITY, (".ent",), ((".ent.json", ResourceFormat.JSON),), "cr2w"),
    _spec(ResourceKind.APPEARANCE, (".app",), ((".app.json", ResourceFormat.JSON),), "cr2w"),
    _spec(ResourceKind.STREAMING_SECTOR_INPLACE, (".streamingsector_inplace",), ((".streamingsector_inplace.json", ResourceFormat.JSON),), "cr2w"),
    _spec(ResourceKind.STREAMING_SECTOR, (".streamingsector",), ((".streamingsector.json", ResourceFormat.JSON),), "cr2w"),
    _spec(ResourceKind.PHYSICS, (".phys",), ((".phys.json", ResourceFormat.JSON),), "cr2w"),
    _spec(ResourceKind.DTEX, (".dtex",), ((".dtex.json", ResourceFormat.JSON),), "cr2w", cache=CachePolicy.PROCESS),
    _spec(ResourceKind.MATERIAL, exports=((".material.json", ResourceFormat.JSON),), validation="material_bundle", cache=CachePolicy.PROCESS),
    _spec(ResourceKind.STREAMING_BLOCK, exports=((".streamingblock.json", ResourceFormat.JSON),), validation="cr2w"),
    _spec(ResourceKind.GRADIENT, (".gradient",), ((".gradient.json", ResourceFormat.JSON),), validation="cr2w"),
    _spec(ResourceKind.FOLIAGE, exports=((".cfoliage.json", ResourceFormat.JSON),), validation="cr2w"),
    _spec(ResourceKind.HAIR_PROFILE, (".hp",), ((".hp.json", ResourceFormat.JSON),), validation="cr2w", roots=("CHairProfile",)),
    _spec(ResourceKind.MLSETUP, (".mlsetup",), ((".mlsetup.json", ResourceFormat.JSON),), validation="cr2w", cache=CachePolicy.PROCESS, roots=("Multilayer_Setup",)),
    _spec(ResourceKind.MLTEMPLATE, (".mltemplate",), ((".mltemplate.json", ResourceFormat.JSON),), validation="cr2w", cache=CachePolicy.PROCESS),
    _spec(ResourceKind.MATERIAL_TEMPLATE, (".mt",), ((".mt.json", ResourceFormat.JSON),), validation="cr2w", cache=CachePolicy.PROCESS),
    _spec(ResourceKind.MATERIAL_INSTANCE, (".mi",), ((".mi.json", ResourceFormat.JSON),), validation="cr2w", cache=CachePolicy.PROCESS, roots=("CMaterialInstance",)),
    _spec(ResourceKind.PARTICLE, exports=((".particle.json", ResourceFormat.JSON),), validation="cr2w"),
    _spec(ResourceKind.EFFECT, exports=((".effect.json", ResourceFormat.JSON),), validation="cr2w"),
    _spec(ResourceKind.ACOUSTIC_DATA, exports=((".acousticdata.json", ResourceFormat.JSON),), validation="cr2w"),
    _spec(ResourceKind.ENVIRONMENT_PROBE, exports=((".envprobe.json", ResourceFormat.JSON),), validation="cr2w"),
    _spec(ResourceKind.MINIMAP, exports=((".cminimap.json", ResourceFormat.JSON),), validation="cr2w"),
    _spec(ResourceKind.GI_DATA, exports=((".gidata.json", ResourceFormat.JSON),), validation="cr2w"),
    _spec(ResourceKind.SMART_OBJECTS, exports=((".smartobjects.json", ResourceFormat.JSON),), validation="cr2w"),
    _spec(ResourceKind.WORKSPOT, exports=((".workspot.json", ResourceFormat.JSON),), validation="cr2w"),
    _spec(ResourceKind.ACTION_ANIM_DB, exports=((".actionanimdb.json", ResourceFormat.JSON),), validation="cr2w"),
    _spec(ResourceKind.IES, exports=((".ies.json", ResourceFormat.JSON), (".ies", ResourceFormat.DATA))),
    _spec(ResourceKind.INK_WIDGET, (".inkwidget",), ((".inkwidget.json", ResourceFormat.JSON),), "cr2w",
          roots=("inkWidgetLibraryResource",)),
    _spec(ResourceKind.INK_ATLAS, (".inkatlas",), ((".inkatlas.json", ResourceFormat.JSON),), "cr2w",
          roots=("inkTextureAtlas",)),
    _spec(ResourceKind.INK_STYLE, (".inkstyle",), ((".inkstyle.json", ResourceFormat.JSON),), "cr2w",
          roots=("inkStyleResource",)),
    _spec(ResourceKind.INK_ANIMATION, (".inkanim",), ((".inkanim.json", ResourceFormat.JSON),), "cr2w",
          roots=("inkanimAnimationLibraryResource",)),
    _spec(ResourceKind.INK_FONT_FAMILY, (".inkfontfamily",), ((".inkfontfamily.json", ResourceFormat.JSON),), "cr2w",
          roots=("inkFontFamilyResource",)),
    _spec(ResourceKind.FONT, (".fnt",), ((".fnt.json", ResourceFormat.JSON), (".ttf", ResourceFormat.DATA)), "cr2w",
          roots=("rendFont",)),
)

RESOURCE_SPEC_BY_COOKED_SUFFIX = {
    cooked: spec
    for spec in RESOURCE_SPECS
    for cooked in spec.cooked_suffixes
}
RESOURCE_EXPORTS_BY_SUFFIX = {
    export.suffix: (spec, export)
    for spec in RESOURCE_SPECS
    for export in spec.exports
}
COOKED_RESOURCE_EXPORTS = {
    cooked: spec.exported_suffixes
    for cooked, spec in RESOURCE_SPEC_BY_COOKED_SUFFIX.items()
}
EXPORTED_RESOURCE_EXTENSIONS = tuple(
    sorted(RESOURCE_EXPORTS_BY_SUFFIX, key=len, reverse=True)
)
IMAGE_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".tga",
    ".dds",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
)
COOKED_RESOURCE_SUFFIXES = tuple(sorted(COOKED_RESOURCE_EXPORTS, key=len, reverse=True))
EXPORT_GROUPS_BY_OUTPUT_EXTENSION = {
    export_extension: exports
    for exports in COOKED_RESOURCE_EXPORTS.values()
    for export_extension in exports
}
EXPORTED_RESOURCE_SUFFIXES = tuple(sorted(EXPORT_GROUPS_BY_OUTPUT_EXTENSION, key=len, reverse=True))
COOKED_DEPOT_EXTENSIONS = frozenset(COOKED_RESOURCE_EXPORTS)


def normalize_extensions(extensions):
    if isinstance(extensions, str):
        extensions = (extensions,)
    return tuple(
        sorted(
            {
                suffix
                for suffix in (normalize_extension(extension) for extension in (extensions or ()))
                if suffix and suffix not in COOKED_DEPOT_EXTENSIONS
            },
            key=len,
            reverse=True,
        )
    )


def resource_spec_for_cooked_suffix(suffix):
    return RESOURCE_SPEC_BY_COOKED_SUFFIX.get(normalize_extension(suffix))


def resource_export_for_suffix(suffix):
    return RESOURCE_EXPORTS_BY_SUFFIX.get(normalize_extension(suffix))


def resource_spec_for_path(path):
    value = str(path or "").replace("\\", "/").casefold()
    for suffix in EXPORTED_RESOURCE_EXTENSIONS:
        if value.endswith(suffix):
            return RESOURCE_EXPORTS_BY_SUFFIX[suffix][0]
    return None
