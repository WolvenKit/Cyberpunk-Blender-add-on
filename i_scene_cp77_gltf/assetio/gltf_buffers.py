from __future__ import annotations

import base64
import binascii
import os
from urllib.parse import unquote, unquote_to_bytes, urlsplit

from .files import read_bytes
from .paths import confined_join


def read_gltf_buffer(source_path, uri, byte_length, *, max_bytes):
    """Resolve a local or embedded glTF buffer through the asset I/O boundary"""
    if not isinstance(uri, str) or not uri:
        raise ValueError("An external glTF buffer requires a URI.")
    if byte_length > max_bytes:
        raise ValueError("The glTF buffer exceeds the supported size limit.")
    if uri.startswith("data:"):
        header, separator, encoded = uri.partition(",")
        if not separator or header.split(";", 1)[0] not in {
            "data:application/octet-stream",
            "data:application/gltf-buffer",
        }:
            raise ValueError("Unsupported glTF buffer data URI.")
        if len(encoded) > max_bytes * 4 + 16:
            raise ValueError(
                "The embedded glTF buffer exceeds the supported size limit."
            )
        try:
            payload = (
                base64.b64decode(encoded, validate=True)
                if header.endswith(";base64")
                else unquote_to_bytes(encoded)
            )
        except (ValueError, binascii.Error) as error:
            raise ValueError("Invalid glTF buffer data URI.") from error
    else:
        parsed = urlsplit(uri)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("glTF buffer URIs must reference local relative files.")
        relative = unquote(parsed.path)
        if os.path.isabs(relative) or "\x00" in relative:
            raise ValueError("glTF buffer URIs must reference local relative files.")
        try:
            path = confined_join(
                os.path.dirname(os.path.abspath(source_path)), relative
            )
        except ValueError as error:
            raise ValueError(
                "glTF buffer URIs must stay inside the document's folder."
            ) from error
        if os.path.getsize(path) > max_bytes:
            raise ValueError("The glTF buffer exceeds the supported size limit.")
        payload = read_bytes(path)
    if len(payload) < byte_length or len(payload) > max_bytes:
        raise ValueError("glTF buffer length disagrees with the available data.")
    return payload[:byte_length]
