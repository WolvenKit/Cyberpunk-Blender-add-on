from ..assetio.resolver import full_suffix, resolve_rooted_path
from ..materials.blender.nodes import createOverrideTable
from ..materials.resources import load_material_document
from .state import find_palette_by_template


def _material_property(material, name, default=""):
    try:
        return material.get(name, default) if material is not None else default
    except (AttributeError, ReferenceError, TypeError):
        return default


def ensure_palette_for_template(template_path, material):
    template_path = str(template_path or "")
    if not template_path:
        return None
    existing = find_palette_by_template(template_path)
    if existing is not None:
        return existing
    reference = template_path if template_path.lower().endswith(".json") else template_path + ".json"
    extension = full_suffix(reference)
    resolved = resolve_rooted_path(
        reference,
        project_root=_material_property(material, "ProjPath"),
        depot_root=_material_property(material, "DepotPath"),
        extensions=(extension,),
    )
    if not resolved:
        return None
    document = load_material_document(resolved)
    root = getattr(document, "root", None)
    if not isinstance(root, dict):
        return None
    override_table = createOverrideTable(root)
    from ..materials.blender.multilayer import cp77_create_palette
    return cp77_create_palette(template_path, override_table)


def ensure_palette_for_state(state):
    if state is None or not getattr(state, "template_path", ""):
        return None
    return ensure_palette_for_template(state.template_path, state.material)
