from __future__ import annotations

import os
import struct
from contextlib import contextmanager

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def file_size(path) -> int:
    """Return the size of a local asset through the filesystem boundary"""
    return os.path.getsize(os.fspath(path))


@contextmanager
def binary_reader(path):
    with open(os.fspath(path), "rb") as stream:
        yield stream


def read_bytes(path) -> bytes:
    with open(os.fspath(path), "rb") as stream:
        return stream.read()


def read_prefix(path, size: int) -> bytes:
    with open(os.fspath(path), "rb") as stream:
        return stream.read(max(0, int(size)))


def png_dimensions(data: bytes) -> tuple[int, int] | None:
    """(width, height) from the start of a PNG file, or None when data does not start one"""
    if len(data) < 24 or not data.startswith(_PNG_SIGNATURE):
        return None
    return struct.unpack(">II", data[16:24])


def png_size(path) -> tuple[int, int] | None:
    """(width, height) of the PNG file at path, or None for anything else"""
    return png_dimensions(read_prefix(path, 24))


def warm_file(path, *, chunk_size: int = 1024 * 1024) -> int:
    total = 0
    with open(os.fspath(path), "rb") as stream:
        while True:
            chunk = stream.read(max(4096, int(chunk_size)))
            if not chunk:
                break
            total += len(chunk)
    return total
