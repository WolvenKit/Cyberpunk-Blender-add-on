from .bundles import additive_normal_blend_socket
from .mat_common import new_labeled_node
from .skin_regions import DEFAULT_FACE_REGIONS

TRACK_NODE_PREFIX = "CP77 Wrinkle Track:"
WRINKLE_SQUASH_ATTRIBUTE = "cp77_skin_wrinkle_squash"
WRINKLE_STRETCH_ATTRIBUTE = "cp77_skin_wrinkle_stretch"
WRINKLE_REGION_COUNT = len(DEFAULT_FACE_REGIONS)


def _float_attribute(tree, name, label, location):
    node = new_labeled_node(tree.nodes, "ShaderNodeAttribute", label, location)
    node.attribute_name = name
    return node.outputs["Factor"]


def build_wrinkle_influence(tree, *, location=(-3000, -2200)):
    base_x, base_y = location
    squash = _float_attribute(
        tree,
        WRINKLE_SQUASH_ATTRIBUTE,
        "Wrinkle Squash Influence",
        (base_x, base_y + 90),
    )
    stretch = _float_attribute(
        tree,
        WRINKLE_STRETCH_ATTRIBUTE,
        "Wrinkle Stretch Influence",
        (base_x, base_y - 90),
    )
    return squash, stretch


def blend_wrinkle_normal(tree, base, detail, factor, label, location):
    if detail is None:
        return base
    if base is None:
        base = (0.0, 0.0, 1.0)
    return additive_normal_blend_socket(
        tree,
        base,
        detail,
        factor,
        location,
        label,
    )
