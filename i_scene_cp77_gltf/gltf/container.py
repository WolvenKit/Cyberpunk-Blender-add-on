from __future__ import annotations

import json
import os
import struct
from dataclasses import dataclass


GLB_MAGIC = b"glTF"
GLB_VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_BINARY_BYTES = 8 * 1024 * 1024 * 1024


class GLBContainerError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GLBContainer:
    document: dict
    binary: bytes
    filepath: str
    declared_length: int


def read_glb_container(
    filepath: str,
    *,
    max_json_bytes: int = MAX_JSON_BYTES,
    max_binary_bytes: int = MAX_BINARY_BYTES,
) -> GLBContainer:
    """Read one strict GLB 2.0 container.

    The reader verifies the complete envelope, requires exactly one first JSON
    chunk, accepts at most one BIN chunk, caps chunk sizes, and rejects trailing
    or undeclared bytes.
    """

    path = os.path.abspath(os.fspath(filepath))
    try:
        file_size = os.path.getsize(path)
    except OSError as error:
        raise GLBContainerError(f"Could not stat GLB: {error}") from error
    if file_size < 20:
        raise GLBContainerError("The file is too short to be a GLB 2.0 container.")

    json_chunk = None
    binary_chunk = b""
    binary_seen = False
    chunk_index = 0
    try:
        with open(path, "rb") as stream:
            header = stream.read(12)
            if len(header) != 12:
                raise GLBContainerError("The GLB header is truncated.")
            magic, version, declared_length = struct.unpack("<4sII", header)
            if magic != GLB_MAGIC:
                raise GLBContainerError("The file does not contain the GLB magic header.")
            if version != GLB_VERSION:
                raise GLBContainerError(
                    f"Unsupported GLB version {version}; expected {GLB_VERSION}."
                )
            if declared_length != file_size:
                raise GLBContainerError(
                    f"GLB declared length {declared_length} does not match "
                    f"file size {file_size}."
                )

            while stream.tell() < declared_length:
                remaining = declared_length - stream.tell()
                if remaining < 8:
                    raise GLBContainerError("The GLB has a truncated chunk header.")
                chunk_header = stream.read(8)
                chunk_length, chunk_type = struct.unpack("<II", chunk_header)
                if chunk_length % 4:
                    raise GLBContainerError(
                        "GLB chunk lengths must be aligned to four bytes."
                    )
                if chunk_length > declared_length - stream.tell():
                    raise GLBContainerError("A GLB chunk exceeds the declared file length.")
                if chunk_index == 0 and chunk_type != JSON_CHUNK:
                    raise GLBContainerError("The first GLB chunk is not JSON.")
                if chunk_type == JSON_CHUNK:
                    if json_chunk is not None:
                        raise GLBContainerError("The GLB contains more than one JSON chunk.")
                    if chunk_length <= 0 or chunk_length > max_json_bytes:
                        raise GLBContainerError(
                            f"GLB JSON chunk size {chunk_length} is outside the "
                            "supported range."
                        )
                elif chunk_type == BIN_CHUNK:
                    if binary_seen:
                        raise GLBContainerError("The GLB contains more than one BIN chunk.")
                    binary_seen = True
                    if chunk_length > max_binary_bytes:
                        raise GLBContainerError(
                            f"GLB BIN chunk size {chunk_length} exceeds the "
                            "supported limit."
                        )
                elif chunk_length > max_binary_bytes:
                    raise GLBContainerError(
                        f"GLB extension chunk size {chunk_length} exceeds the "
                        "supported limit."
                    )

                payload = stream.read(chunk_length)
                if len(payload) != chunk_length:
                    raise GLBContainerError("A GLB chunk payload is truncated.")
                if chunk_type == JSON_CHUNK:
                    json_chunk = payload
                elif chunk_type == BIN_CHUNK:
                    binary_chunk = payload
                chunk_index += 1

            if stream.tell() != declared_length:
                raise GLBContainerError("The GLB chunk table does not end at declared length.")
    except OSError as error:
        raise GLBContainerError(f"Could not read GLB: {error}") from error

    if json_chunk is None:
        raise GLBContainerError("The GLB has no JSON chunk.")
    try:
        document = json.loads(
            json_chunk.decode("utf-8").rstrip("\x00 \t\r\n")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GLBContainerError(f"Invalid GLB JSON chunk: {error}") from error
    if not isinstance(document, dict):
        raise GLBContainerError("The GLB JSON root must be an object.")
    asset = document.get("asset")
    if not isinstance(asset, dict):
        raise GLBContainerError("The GLB JSON header has no asset object.")
    if str(asset.get("version", "")) != "2.0":
        raise GLBContainerError("The GLB asset.version is not 2.0.")

    return GLBContainer(
        document=document,
        binary=binary_chunk,
        filepath=path,
        declared_length=declared_length,
    )
