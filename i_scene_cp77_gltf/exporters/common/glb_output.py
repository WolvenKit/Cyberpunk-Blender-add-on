import os

from ...assetio.atomic import atomic_replace_staged, staged_binary_output
from ...gltf.container import encode_glb


def write_validated_glb(filepath, document, binary, validate_file):
    """Commit an encoded GLB only after its staged file passes domain validation"""
    filepath = os.path.abspath(filepath)
    if not filepath.lower().endswith(".glb"):
        filepath += ".glb"
    payload = encode_glb(document, binary)
    with staged_binary_output(filepath, payload) as temporary:
        validation = validate_file(temporary)
        atomic_replace_staged({filepath: temporary})
    return {
        "filepath": filepath,
        "file_bytes": len(payload),
        "file_validation": validation,
    }
