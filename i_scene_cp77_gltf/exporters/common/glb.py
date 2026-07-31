from __future__ import annotations

import json
import struct

import numpy as np

from .errors import ExportError


class GLBBuilder:
    """Shared binary-buffer and accessor builder for direct GLB exporters."""

    def __init__(self):
        self.binary = bytearray()
        self.buffer_views: list[dict] = []
        self.accessors: list[dict] = []

    def _align(self, alignment: int = 4) -> None:
        padding = (-len(self.binary)) % alignment
        if padding:
            self.binary.extend(b"\x00" * padding)

    def add_float_accessor(
        self,
        values,
        accessor_type: str,
        *,
        name: str | None = None,
        matrix_column_major: bool = False,
        include_bounds: bool = True,
    ) -> int:
        array = np.asarray(values, dtype=np.float32)
        if accessor_type == "SCALAR":
            array = array.reshape(-1)
            count, width = len(array), 1
            payload_array = array
            bounds_array = array.reshape(-1, 1)
        else:
            width = {"VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}.get(accessor_type)
            if width is None:
                raise ExportError(f"Unsupported accessor type {accessor_type!r}.")
            if accessor_type == "MAT4":
                array = array.reshape(-1, 4, 4)
                count = len(array)
                payload_array = (
                    np.swapaxes(array, 1, 2).reshape(count, 16)
                    if matrix_column_major
                    else array.reshape(count, 16)
                )
                bounds_array = payload_array
            else:
                array = array.reshape(-1, width)
                count = len(array)
                payload_array = bounds_array = array

        self._align()
        byte_offset = len(self.binary)
        payload = np.asarray(payload_array, dtype="<f4").tobytes(order="C")
        self.binary.extend(payload)
        view_index = len(self.buffer_views)
        self.buffer_views.append(
            {"buffer": 0, "byteOffset": byte_offset, "byteLength": len(payload)}
        )
        accessor = {
            "bufferView": view_index,
            "componentType": 5126,
            "count": count,
            "type": accessor_type,
        }
        if name:
            accessor["name"] = name
        if include_bounds and count:
            accessor["min"] = [float(value) for value in np.min(bounds_array, axis=0)]
            accessor["max"] = [float(value) for value in np.max(bounds_array, axis=0)]
            if width == 1:
                accessor["min"] = accessor["min"][:1]
                accessor["max"] = accessor["max"][:1]
        accessor_index = len(self.accessors)
        self.accessors.append(accessor)
        return accessor_index


def encode_glb(document: dict, binary: bytes) -> bytes:
    json_payload = json.dumps(
        document, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    json_payload += b" " * ((-len(json_payload)) % 4)
    padded_binary = binary + (b"\x00" * ((-len(binary)) % 4))
    total_length = 12 + 8 + len(json_payload)
    if padded_binary:
        total_length += 8 + len(padded_binary)

    output = bytearray(struct.pack("<4sII", b"glTF", 2, total_length))
    output.extend(struct.pack("<II", len(json_payload), 0x4E4F534A))
    output.extend(json_payload)
    if padded_binary:
        output.extend(struct.pack("<II", len(padded_binary), 0x004E4942))
        output.extend(padded_binary)
    return bytes(output)


__all__ = ("GLBBuilder", "encode_glb")
