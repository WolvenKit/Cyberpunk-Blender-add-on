import os

from ...assetio.catalog import ResourceKind
from ...assetio.index import IndexPolicy
from ...assetio.paths import LocalPath
from ...assetio.resolver import resolve_rooted_path
from ...materials.blender.multilayer import (
    find_override_palette,
    queue_override_palette,
)
from ...materials.blender.nodes import createOverrideTable
from ..application.options import MULTILAYER_TEMPLATE_EXTENSION, MaterialToolsRequest
from ..application.session import MaterialToolsSession
from ..common.access import material_property


def ensure_palette_for_template(template_path, material):
    template_path = str(template_path or "")
    if not template_path:
        return None
    existing = find_override_palette(template_path)
    if existing is not None:
        if "ColorScaleList" not in existing:
            existing["ColorScaleList"] = [
                str(tuple(float(component) for component in color.color[:3]))
                for color in existing.colors
            ]
        return existing
    reference = template_path
    depot_root = material_property(material, "DepotPath", "")
    resolved = resolve_rooted_path(
        reference,
        project_root=material_property(material, "cp77_project_path", ""),
        depot_root=depot_root,
        extensions=(MULTILAYER_TEMPLATE_EXTENSION,),
    )
    if not resolved:
        return existing
    session_root = (
        LocalPath.from_value(depot_root).value
        if depot_root and os.path.isdir(depot_root)
        else LocalPath.from_value(os.path.dirname(resolved)).value
    )
    request = MaterialToolsRequest(
        root=session_root,
        extensions=(),
        index_policy=IndexPolicy.REUSE,
    )
    with MaterialToolsSession(request) as session:
        document = session.material_resources.load(
            resolved,
            expected_kind=ResourceKind.MLTEMPLATE,
            required=False,
        )
        root = getattr(document, "root", None)
        if not isinstance(root, dict):
            return existing
        override_table = createOverrideTable(root)
    return queue_override_palette(template_path, override_table)


def ensure_palette_for_state(state):
    if state is None or not getattr(state, "template_path", ""):
        return None
    return ensure_palette_for_template(state.template_path, state.material)
