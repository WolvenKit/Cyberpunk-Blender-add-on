from __future__ import annotations

import json
import os
import struct
from dataclasses import dataclass
<<<<<<< Updated upstream

=======
from io import BytesIO

from ..assetio.files import binary_reader, file_size, read_bytes
from ..assetio.gltf_buffers import read_gltf_buffer
>>>>>>> Stashed changes

GLB_MAGIC = b"glTF"
GLB_VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_BINARY_BYTES = 8 * 1024 * 1024 * 1024


<<<<<<< Updated upstream
=======
def _reject_nonfinite_json(value):
    raise ValueError(f"Non-finite JSON number {value!r} is not valid glTF.")


>>>>>>> Stashed changes
class GLBContainerError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GLBContainer:
    document: dict
    binary: bytes
    filepath: str
    declared_length: int
<<<<<<< Updated upstream
=======
    json_chunk_bytes: int = 0
    binary_chunk_bytes: int = 0
>>>>>>> Stashed changes


def read_glb_container(
    filepath: str,
    *,
    max_json_bytes: int = MAX_JSON_BYTES,
    max_binary_bytes: int = MAX_BINARY_BYTES,
<<<<<<< Updated upstream
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
=======
    include_binary: bool = True,
) -> GLBContainer:
    """Read one strict GLB 2.0 container"""

    path = os.path.abspath(os.fspath(filepath))
    try:
        length = file_size(path)
    except OSError as error:
        raise GLBContainerError(f"Could not stat GLB: {error}") from error
    try:
        with binary_reader(path) as stream:
            return _read_glb_stream(
                stream, length, path, max_json_bytes, max_binary_bytes, include_binary
            )
    except OSError as error:
        raise GLBContainerError(f"Could not read GLB: {error}") from error


def parse_glb_container(payload: bytes) -> GLBContainer:
    """Parse an in-memory GLB through the same envelope checks used for files"""
    return _read_glb_stream(
        BytesIO(payload), len(payload), "", MAX_JSON_BYTES, MAX_BINARY_BYTES, True
    )


def _read_glb_stream(
    stream, file_size, path, max_json_bytes, max_binary_bytes, include_binary
):
>>>>>>> Stashed changes
    if file_size < 20:
        raise GLBContainerError("The file is too short to be a GLB 2.0 container.")

    json_chunk = None
    binary_chunk = b""
    binary_seen = False
    chunk_index = 0
    try:
<<<<<<< Updated upstream
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
=======
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
                    raise GLBContainerError(
                        "The GLB contains more than one JSON chunk."
                    )
                if chunk_length <= 0 or chunk_length > max_json_bytes:
                    raise GLBContainerError(
                        f"GLB JSON chunk size {chunk_length} is outside the "
                        "supported range."
                    )
            elif chunk_type == BIN_CHUNK:
                if chunk_index != 1:
                    raise GLBContainerError(
                        "The GLB BIN chunk must follow the JSON chunk."
                    )
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
            if chunk_type == JSON_CHUNK or (chunk_type == BIN_CHUNK and include_binary):
                payload = stream.read(chunk_length)
                if len(payload) != chunk_length:
                    raise GLBContainerError("A GLB chunk payload is truncated.")
            else:
                stream.seek(chunk_length, os.SEEK_CUR)
                payload = b""
            if chunk_type == JSON_CHUNK:
                json_chunk = payload
            elif chunk_type == BIN_CHUNK:
                binary_chunk = payload
            chunk_index += 1
        if stream.tell() != declared_length:
            raise GLBContainerError(
                "The GLB chunk table does not end at declared length."
            )
>>>>>>> Stashed changes
    except OSError as error:
        raise GLBContainerError(f"Could not read GLB: {error}") from error

    if json_chunk is None:
        raise GLBContainerError("The GLB has no JSON chunk.")
    try:
        document = json.loads(
<<<<<<< Updated upstream
            json_chunk.decode("utf-8").rstrip("\x00 \t\r\n")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
=======
            json_chunk.decode("utf-8").rstrip("\x00 \t\r\n"),
            parse_constant=_reject_nonfinite_json,
        )
    except (UnicodeDecodeError, ValueError) as error:
>>>>>>> Stashed changes
        raise GLBContainerError(f"Invalid GLB JSON chunk: {error}") from error
    if not isinstance(document, dict):
        raise GLBContainerError("The GLB JSON root must be an object.")
    asset = document.get("asset")
    if not isinstance(asset, dict):
        raise GLBContainerError("The GLB JSON header has no asset object.")
    if str(asset.get("version", "")) != "2.0":
        raise GLBContainerError("The GLB asset.version is not 2.0.")
<<<<<<< Updated upstream
=======
    if asset.get("minVersion") not in (None, "2.0"):
        raise GLBContainerError(
            "The GLB requires an unsupported glTF asset.minVersion."
        )
>>>>>>> Stashed changes

    return GLBContainer(
        document=document,
        binary=binary_chunk,
        filepath=path,
        declared_length=declared_length,
<<<<<<< Updated upstream
    )
=======
        json_chunk_bytes=len(json_chunk),
        binary_chunk_bytes=len(binary_chunk),
    )


def read_gltf_container(filepath: str, *, include_binary: bool = True) -> GLBContainer:
    """Read GLB or JSON glTF and resolve all binary views into one local buffer"""
    path = os.path.abspath(os.fspath(filepath))
    try:
        if path.casefold().endswith(".glb"):
            container = read_glb_container(path, include_binary=include_binary)
            document, embedded = container.document, container.binary
        elif path.casefold().endswith(".gltf"):
            length = file_size(path)
            if length > MAX_JSON_BYTES:
                raise GLBContainerError(
                    "The glTF JSON document exceeds the supported size limit."
                )
            document = json.loads(
                read_bytes(path).decode("utf-8-sig"),
                parse_constant=_reject_nonfinite_json,
            )
            if (
                not isinstance(document, dict)
                or (document.get("asset") or {}).get("version") != "2.0"
            ):
                raise GLBContainerError("The document is not glTF 2.0.")
            if document["asset"].get("minVersion") not in (None, "2.0"):
                raise GLBContainerError(
                    "The document requires an unsupported glTF asset.minVersion."
                )
            container = GLBContainer(document, b"", path, length)
            embedded = b""
        else:
            raise GLBContainerError("Select a .glb or .gltf file.")
        if not include_binary:
            return container
        buffers = document.get("buffers") or ()
        offsets, payloads, total = [], [], 0
        for index, buffer in enumerate(buffers):
            length = buffer.get("byteLength")
            if isinstance(length, bool) or not isinstance(length, int) or length < 1:
                raise GLBContainerError(
                    "glTF buffer byteLength must be a positive integer."
                )
            padding = (-total) % 4
            total += padding
            offsets.append(total)
            if "uri" in buffer:
                payload = read_gltf_buffer(
                    path, buffer["uri"], length, max_bytes=MAX_BINARY_BYTES - total
                )
            else:
                if index != 0 or not path.casefold().endswith(".glb"):
                    raise GLBContainerError(
                        "Only the first GLB buffer may omit its URI."
                    )
                if not length <= len(embedded) <= length + 3:
                    raise GLBContainerError(
                        "GLB buffer byteLength disagrees with its BIN chunk."
                    )
                payload = embedded[:length]
            payloads.extend((b"\x00" * padding, payload))
            total += length
            if total > MAX_BINARY_BYTES:
                raise GLBContainerError(
                    "Combined glTF buffers exceed the supported size limit."
                )
        if not buffers:
            if embedded:
                raise GLBContainerError(
                    "GLB contains a BIN chunk without a buffer declaration."
                )
            return container
        for view in document.get("bufferViews") or ():
            index = view.get("buffer")
            start, length = view.get("byteOffset", 0), view.get("byteLength")
            if any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in (index, start, length)
            ):
                raise GLBContainerError(
                    "glTF bufferView references and ranges must be integers."
                )
            if (
                not 0 <= index < len(buffers)
                or start < 0
                or length < 1
                or start + length > buffers[index]["byteLength"]
            ):
                raise GLBContainerError("glTF bufferView exceeds its declared buffer.")
            view["buffer"] = 0
            view["byteOffset"] = offsets[index] + start
        document["buffers"] = [{"byteLength": total}]
        binary = payloads[1] if len(payloads) == 2 else b"".join(payloads)
        return GLBContainer(document, binary, path, container.declared_length)
    except (OSError, ValueError, UnicodeError) as error:
        raise GLBContainerError(f"Could not read glTF: {error}") from error


def embedded_glb_binary(container):
    """Validate the embedded buffer declaration and expose its unpadded bytes"""
    buffers = container.document.get("buffers")
    if not isinstance(buffers, list) or len(buffers) != 1 or "uri" in buffers[0]:
        raise GLBContainerError("The GLB must declare exactly one embedded buffer.")
    length = buffers[0].get("byteLength")
    if isinstance(length, bool) or not isinstance(length, int) or length < 1:
        raise GLBContainerError("GLB buffer byteLength must be a positive integer.")
    if not length <= len(container.binary) <= length + 3:
        raise GLBContainerError(
            "The BIN chunk padding disagrees with buffers[0].byteLength."
        )
    return memoryview(container.binary)[:length]


def encode_glb(document: dict, binary: bytes) -> bytes:
    json_payload = json.dumps(
        document, ensure_ascii=False, allow_nan=False, separators=(",", ":")
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
>>>>>>> Stashed changes
