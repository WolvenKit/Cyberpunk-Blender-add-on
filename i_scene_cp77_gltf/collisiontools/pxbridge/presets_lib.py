# Collision Layers

COLLISION_LAYERS = [
    "Player",
    "AI",
    "Static",
    "Dynamic",
    "Vehicle",
    "Tank",
    "Destructible",
    "Terrain",
    "Collider",
    "Particle",
    "Ragdoll",
    "Ragdoll Inner",
    "Debris",
    "Cloth",
    "PlayerBlocker",
    "VehicleBlocker",
    "TankBlocker",
    "DestructibleCluster",
    "NPCBlocker"
]

# Query Layers

QUERY_LAYERS = [
    "Visibility",
    "Audible",
    "Interaction",
    "Shooting",
    "Water",
    "NetworkDevice",
    "NPCTraceObstacle",
    "PhotoModeCamera",
    "FoliageDestructible",
    "NPCNameplate",
    "NPCCollision"
]

# Filtering Presets
# Structure: "PresetName": ( [MyLayers], [CollidesWith], [QueryableBy] )
_RAW_PRESETS = {
    "None": (
        [],
        [],
        []
        ),
    "No Collision": (
        [], 
        [], 
        []
    ),
    "World Dynamic": (
        ["Dynamic", "PlayerBlocker", "VehicleBlocker", "TankBlocker"],
        ["Player", "AI", "Static", "Dynamic", "Destructible", "Terrain", "Collider", "Particle", "Debris"],
        ["Dynamic", "Visibility", "PhotoModeCamera", "VehicleBlocker", "TankBlocker", "Shooting"]
    ),
    "Player Collision": (
        ["Player"],
        ["AI", "Static", "Dynamic", "Destructible", "Terrain", "Collider", "PlayerBlocker"],
        ["Visibility"]
    ),
    "Player Hitbox": (
        [],
        [],
        ["Player", "Shooting"]
    ),
    "NPC Collision": (
        ["AI"],
        ["Static", "Dynamic", "Destructible", "Terrain", "Collider", "Ragdoll", "Ragdoll Inner"],
        ["AI", "PhotoModeCamera", "NPCCollision"]
    ),
    "NPC Trace Obstacle": (
        [],
        [],
        ["NPCTraceObstacle"]
    ),
    "NPC Hitbox": (
        [],
        [],
        ["AI"]
    ),
    "Big NPC Collision": (
        ["AI", "VehicleBlocker", "TankBlocker"],
        ["Static", "Dynamic", "Destructible", "Terrain", "Collider", "Ragdoll", "Ragdoll Inner"],
        ["AI", "PhotoModeCamera", "VehicleBlocker", "TankBlocker", "NPCCollision"]
    ),
    "Player Blocker": (
        ["PlayerBlocker"],
        [],
        ["PlayerBlocker"]
    ),
    "Block Player and Vehicles": (
        ["PlayerBlocker", "VehicleBlocker", "TankBlocker"],
        [],
        ["PlayerBlocker", "VehicleBlocker", "TankBlocker"]
    ),
    "Vehicle Blocker": (
        ["VehicleBlocker", "TankBlocker"],
        [],
        ["VehicleBlocker", "TankBlocker"]
    ),
    "Block PhotoMode Camera": (
        [],
        [],
        ["PhotoModeCamera"]
    ),
    "Ragdoll": (
        ["Ragdoll"],
        ["Ragdoll", "Dynamic", "Static", "Terrain", "Destructible"],
        ["Ragdoll", "Shooting"]
    ),
    "Ragdoll Inner": (
        ["Ragdoll Inner"],
        ["Dynamic", "Static", "Terrain", "Destructible"],
        ["Ragdoll Inner"]
    ),
    "RagdollVehicle": (
        [],
        ["Static", "Terrain"],
        ["Ragdoll", "Shooting"]
    ),
    "Terrain": (
        ["Terrain", "PlayerBlocker", "VehicleBlocker", "TankBlocker"],
        ["AI", "Dynamic", "Destructible", "Debris"],
        ["Terrain", "Visibility", "Shooting", "PhotoModeCamera", "VehicleBlocker", "TankBlocker", "PlayerBlocker"]
    ),
    "Sight Blocker": (
        [],
        [],
        ["Visibility"]
    ),
    "Moving Kinematic": (
        ["Dynamic", "VehicleBlocker", "TankBlocker", "PlayerBlocker"],
        ["Player", "AI", "Dynamic", "Vehicle", "Tank", "Destructible"],
        ["Dynamic", "PhotoModeCamera", "Visibility", "VehicleBlocker", "TankBlocker", "PlayerBlocker"]
    ),
    "Interaction Object": (
        [],
        [],
        ["Interaction"]
    ),
    "Particle": (
        ["Particle"],
        ["Static", "Dynamic", "Vehicle", "Tank", "Destructible", "Terrain", "Particle"],
        ["Particle"]
    ),
    "Destructible": (
        ["Destructible", "PlayerBlocker"],
        ["Player", "Static", "Dynamic", "Vehicle", "Tank", "Destructible", "Terrain", "Particle"],
        ["Destructible", "PhotoModeCamera", "Visibility", "PlayerBlocker"]
    ),
    "Debris": (
        ["Debris"],
        ["Static", "Dynamic", "Tank", "Destructible", "Terrain"],
        ["Debris", "Visibility"]
    ),
    "Debris Cluster": (
        ["Debris", "PlayerBlocker"],
        ["Player", "Static", "Dynamic", "Vehicle", "Tank", "Terrain", "Particle"],
        ["Destructible", "PhotoModeCamera", "Visibility", "PlayerBlocker"]
    ),
    "Foliage Debris": (
        ["Debris"],
        ["Static", "Dynamic", "Tank", "Destructible", "Vehicle", "Terrain"],
        ["Debris", "Visibility"]
    ),
    "ItemDrop": (
        ["Debris"],
        ["Debris"],
        ["Interaction"]
    ),
    "Shooting": (
        [],
        [],
        ["Shooting"]
    ),
    "Moving Platform": (
        ["Dynamic", "VehicleBlocker", "TankBlocker", "PlayerBlocker"],
        ["Player", "AI", "Dynamic", "Vehicle", "Tank", "Destructible", "Particle", "Ragdoll", "Ragdoll Inner", "Debris"],
        ["Visibility", "Dynamic", "Shooting", "PhotoModeCamera", "NPCBlocker", "VehicleBlocker", "TankBlocker", "PlayerBlocker"]
    ),
    "Water": (
        [],
        [],
        ["Water"]
    ),
    "Window": (
        ["Collider"],
        [],
        ["Collider", "Visibility"]
    ),
    "Device transparent": (
        ["Collider", "PlayerBlocker", "VehicleBlocker", "TankBlocker"],
        ["Player", "AI", "Dynamic", "Destructible", "Ragdoll", "Ragdoll Inner", "PlayerBlocker"],
        ["Dynamic", "Collider", "Interaction", "PhotoModeCamera", "PlayerBlocker", "VehicleBlocker", "TankBlocker", "Visibility"]
    ),
    "Device solid visible": (
        ["Dynamic", "PlayerBlocker", "VehicleBlocker", "TankBlocker"],
        ["Player", "AI", "Dynamic", "Destructible", "Ragdoll", "Ragdoll Inner", "Debris", "PlayerBlocker"],
        ["Dynamic", "Collider", "VehicleBlocker", "TankBlocker", "Visibility", "Interaction", "PhotoModeCamera", "PlayerBlocker", "NPCBlocker"]
    ),
    "Vehicle Device": (
        ["PlayerBlocker"],
        ["Player", "AI", "Dynamic", "Destructible", "Ragdoll", "Debris", "PlayerBlocker"],
        ["Dynamic", "Collider", "Visibility", "Interaction", "PhotoModeCamera", "PlayerBlocker"]
    ),
    "Environment transparent": (
        ["Collider", "PlayerBlocker", "VehicleBlocker", "TankBlocker"],
        ["Player", "AI", "Dynamic", "Destructible", "PlayerBlocker"],
        ["Collider", "PlayerBlocker", "VehicleBlocker", "TankBlocker"]
    ),
    "Bullet logic": (
        [],
        [],
        ["Player", "AI", "Dynamic", "Destructible", "Terrain", "Collider", "Particle", "Ragdoll", "Debris", "Shooting"]
    ),
    "World Static": (
        ["Static", "VehicleBlocker", "TankBlocker", "PlayerBlocker", "NPCBlocker"],
        ["AI", "Static", "Dynamic", "Destructible", "Terrain", "Collider", "Particle", "Debris"],
        ["Static", "Visibility", "Shooting", "VehicleBlocker", "PhotoModeCamera", "VehicleBlocker", "TankBlocker", "PlayerBlocker"]
    ),
    "Simple Environment Collision": (
        ["Static", "VehicleBlocker", "TankBlocker", "PlayerBlocker", "NPCBlocker"],
        ["Ragdoll", "Ragdoll Inner", "Dynamic", "Destructible", "Debris", "Particle"],
        ["Static", "VehicleBlocker", "TankBlocker", "PlayerBlocker", "NPCBlocker", "PhotoModeCamera"]
    ),
    "Complex Environment Collision": (
        [],
        [],
        ["Shooting", "Visibility"]
    ),
    "Foliage Trunk": (
        ["Static", "VehicleBlocker", "PlayerBlocker"],
        ["Static", "Dynamic", "Particle", "Debris", "Ragdoll", "Ragdoll Inner"],
        ["Shooting", "PlayerBlocker", "VehicleBlocker", "Visibility", "PhotoModeCamera"]
    ),
    "Foliage Trunk Destructible": (
        ["Static", "VehicleBlocker", "PlayerBlocker"],
        ["Static", "Dynamic", "Particle", "Debris", "Ragdoll", "Ragdoll Inner"],
        ["Shooting", "PlayerBlocker", "VehicleBlocker", "Visibility", "PhotoModeCamera", "FoliageDestructible"]
    ),
    "Foliage Low Trunk": (
        ["Static", "PlayerBlocker"],
        ["Static", "Dynamic", "Particle", "Debris", "Ragdoll", "Ragdoll Inner"],
        ["Shooting", "PlayerBlocker", "Visibility", "PhotoModeCamera"]
    ),
    "Foliage Crown": (
        [],
        [],
        ["Visibility"]
    ),
    "Vehicle Part": (
        ["VehicleBlocker", "TankBlocker"],
        ["AI", "Static", "Dynamic", "Debris", "Destructible", "Terrain", "Collider", "Vehicle", "Tank"],
        ["Vehicle", "Visibility", "Shooting", "PhotoModeCamera", "Interaction"]
    ),
    "Vehicle Proxy": (
        [],
        [],
        ["Visibility", "Shooting", "PhotoModeCamera"]
    ),
    "Vehicle Part Query Only Exception": (
        ["PlayerBlocker"],
        ["Dynamic"],
        ["PlayerBlocker", "Shooting", "Visibility", "Interaction"]
    ),
    "Vehicle Chassis": (
        ["Vehicle"],
        ["Destructible", "Ragdoll Inner", "Ragdoll", "Tank", "Terrain", "Vehicle", "VehicleBlocker"],
        ["Vehicle", "Interaction"]
    ),
    "Chassis Bottom": (
        [],
        ["Destructible", "Dynamic", "Vehicle"],
        ["Vehicle"]
    ),
    "Chassis Bottom Traffic": (
        [],
        ["Destructible", "Dynamic"],
        ["Vehicle"]
    ),
    "Vehicle Chassis Traffic": (
        ["Vehicle"],
        ["Destructible", "Ragdoll Inner", "Ragdoll", "Tank", "Terrain", "VehicleBlocker"],
        ["Vehicle", "Interaction", "Shooting"]
    ),
    "AV Chassis": (
        ["Vehicle"],
        ["Destructible", "Tank", "Terrain", "Vehicle", "VehicleBlocker"],
        ["Vehicle", "Interaction"]
    ),
    "Tank Chassis": (
        ["Tank"],
        ["Vehicle", "Tank", "TankBlocker", "Destructible", "Terrain", "Ragdoll", "Ragdoll Inner"],
        ["Vehicle", "Tank", "Interaction", "Shooting"]
    ),
    "Vehicle Chassis LOD3": (
        ["Vehicle"],
        ["Destructible", "Ragdoll Inner", "Ragdoll", "Tank", "Terrain", "Vehicle", "VehicleBlocker"],
        ["Vehicle", "Interaction", "Shooting"]
    ),
    "Vehicle Chassis Traffic LOD3": (
        ["Vehicle"],
        ["Destructible", "Ragdoll Inner", "Ragdoll", "Tank", "Terrain", "VehicleBlocker"],
        ["Vehicle", "Interaction", "Shooting"]
    ),
    "Tank Chassis LOD3": (
        ["Tank"],
        ["Vehicle", "Tank", "TankBlocker", "Destructible", "Terrain", "Ragdoll", "Ragdoll Inner"],
        ["Vehicle", "Tank", "Interaction", "Shooting"]
    ),
    "Drone": (
        ["PlayerBlocker"],
        ["Player"],
        ["PlayerBlocker", "Visibility", "Shooting"]
    ),
    "Prop Interaction": (
        [],
        [],
        ["Interaction", "Visibility"]
    ),
    "Nameplate": (
        [],
        [],
        ["NPCNameplate", "Cloth"]
    ),
    "Road Barrier Simple Collision": (
        ["PlayerBlocker", "VehicleBlocker", "TankBlocker", "NPCBlocker"],
        ["NPCBlocker"],
        ["PlayerBlocker", "VehicleBlocker", "TankBlocker"]
    ),
    "Road Barrier Complex Collision": (
        ["Dynamic"],
        ["Static", "Dynamic", "Destructible", "Terrain", "Collider", "Particle", "Debris"],
        ["Dynamic", "Visibility", "Shooting", "PhotoModeCamera"]
    ),
    "Lootable Corpse": (
        [],
        ["AI", "Dynamic", "Destructible", "Ragdoll", "Debris"],
        ["Visibility", "Interaction", "PhotoModeCamera", "Shooting"]
    ),
    "Spider Tank": (
        ["Tank", "PlayerBlocker", "VehicleBlocker", "TankBlocker", "NPCBlocker"],
        ["Player", "Vehicle", "Tank", "PlayerBlocker", "VehicleBlocker", "TankBlocker", "Destructible", "Terrain", "Debris", "Ragdoll", "Ragdoll Inner"],
        ["Tank", "PlayerBlocker", "VehicleBlocker", "TankBlocker", "Visibility", "Shooting"]
    ),
}

# Map simplified names to the actual names
_OVERRIDES = {
    "Device": "Device solid visible",
    "Door": "Device solid visible",
    "Wall": "World Static",
    "Vehicle": "Vehicle Part",
    "vehicle": "Vehicle Part",
    "Vehicle Interaction Object": "Vehicle Part",
    "All Collision Block All": "World Dynamic",
    "All Collision Touch All": "World Dynamic",
    "Block All": "World Dynamic",
    "debris": "Debris",
    "destructible": "Destructible",
    "Advertisement Node": "World Static",
    "Static": "No Collision",
    "Dynamic": "No Collision",
    "Vehicle & Player Blocker": "Block Player and Vehicles"
}

# Combine everything for easy use

COLLISION_PRESETS = _RAW_PRESETS.copy()
for alias, target in _OVERRIDES.items():
    if target in _RAW_PRESETS:
        COLLISION_PRESETS[alias] = _RAW_PRESETS[target]

# Helper to find bit index
def get_layer_bit(name, is_query=False):
    lookup = QUERY_LAYERS if is_query else COLLISION_LAYERS
    try:
        return lookup.index(name)
    except ValueError:
        return -1

def get_preset_items(self, context):
    items = []
    # Sort for UI readability
    for name in sorted(COLLISION_PRESETS.keys()):
        items.append((name, name, ""))
    return items