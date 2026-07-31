ROOT_NODE_NAME = "Multilayered 1.8.0"
ROOT_ROLE_PROPERTY = "cp77MaterialToolsRole"
ROOT_ROLE = "multilayer_root"
LAYER_ROLE = "multilayer_layer"
LAYER_INDEX_PROPERTY = "cp77MaterialToolsLayer"
LAYER_INTERNAL_ROLE_PROPERTY = "cp77MultilayerRole"
BASE_MATERIAL_ROLE = "base_material"
MICROBLEND_ROLE = "microblend"
GROUP_INPUT_ROLE = "group_input"
VIEW_MASK_NODE_NAME = "Multilayered Mask Output"
VIEW_MASK_ROLE = "view_mask_output"
PREVIOUS_OUTPUT_PROPERTY = "cp77MaterialToolsPreviousOutput"
MASK_OWNER_PROPERTY = "cp77MaterialToolsMaskOwner"
MASK_LAYER_PROPERTY = "cp77MaterialToolsMaskLayer"
MASK_NODE_ROLE = "mask_image"
LOCAL_LAYER_OWNER_PROPERTY = "cp77MaterialToolsLocalOwner"
ENUM_NONE = "__CP77_NONE__"
MAX_LAYERS = 20
MATCH_TOLERANCE = 0.00001

LAYER_EDITABLE_SOCKETS = (
    ("MatTile", "MatTile"),
    ("OffsetU", "OffsetU"),
    ("OffsetV", "OffsetV"),
    ("MicroblendNormalStrength", "MicroblendNormalStrength"),
    ("MicroblendContrast", "MicroblendContrast"),
    ("MbTile", "MbTile"),
    ("MicroblendOffsetU", "MicroblendOffsetU"),
    ("MicroblendOffsetV", "MicroblendOffsetV"),
    ("Opacity", "Opacity"),
)

OVERRIDE_SOCKET_NAMES = {
    "normalstr": "NormalStrength",
    "metalin": "MetalLevelsIn",
    "metalout": "MetalLevelsOut",
    "roughin": "RoughLevelsIn",
    "roughout": "RoughLevelsOut",
}

OVERRIDE_ENUM_KEYS = {
    "normalstr": "NormalStrengthList",
    "metalin": "MetalLevelsInList",
    "metalout": "MetalLevelsOutList",
    "roughin": "RoughLevelsInList",
    "roughout": "RoughLevelsOutList",
}
