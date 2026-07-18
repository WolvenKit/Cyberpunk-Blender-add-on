from __future__ import annotations

def merged_rig_bone_name(name: str) -> str:
    """Map authored MetaRig plug names to their merged slot names."""
    value = str(name)
    return f"{value[:-5]}_slot" if value.endswith("_plug") else value
