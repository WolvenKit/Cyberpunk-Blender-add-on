from __future__ import annotations

import os
import struct
import zlib
from dataclasses import dataclass

import numpy as np

from .files import read_bytes

TWEAKDB_MAGIC = 0x0BB1DB47
_ID_MASK = (1 << 40) - 1
_CACHE = {}


def tweakdb_id(name: str) -> int:
    """The 40-bit identity of a TweakDB record or flat name"""
    return zlib.crc32(name.encode("utf-8")) | ((len(name) & 0xFF) << 32)


def _cname_hash(name: str) -> int:
    value = 0xCBF29CE484222325
    for byte in name.encode("utf-8"):
        value = ((value ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value


_TWEAKDBID = _cname_hash("TweakDBID")
_TWEAKDBID_ARRAY = _cname_hash("array:TweakDBID")


@dataclass(frozen=True, slots=True)
class CompiledTweakDB:
    path: str
    keys: np.ndarray
    targets: np.ndarray
    arrays: dict

    def foreign_key(self, flat_name: str) -> int | None:
        """Identity of the record a single foreign-key flat names, or None when the flat is not one"""
        key = tweakdb_id(flat_name)
        index = int(np.searchsorted(self.keys, key))
        if index < len(self.keys) and int(self.keys[index]) == key:
            return int(self.targets[index])
        return None

    def foreign_keys(self, flat_name: str) -> tuple[int, ...] | None:
        """Identities of the records an array foreign-key flat names, or None when the flat is not one"""
        return self.arrays.get(tweakdb_id(flat_name))


def _type_table(data, offset):
    (count,) = struct.unpack_from("<I", data, offset)
    table = {}
    for index in range(count):
        type_hash, _values, _keys, block = struct.unpack_from(
            "<QIII", data, offset + 4 + index * 20
        )
        table[type_hash] = block
    return table


def _single_references(data, block):
    (value_count,) = struct.unpack_from("<I", data, block)
    values = (
        np.frombuffer(data, dtype="<u8", count=value_count, offset=block + 4) & _ID_MASK
    )
    keys_at = block + 4 + 8 * value_count
    (key_count,) = struct.unpack_from("<I", data, keys_at)
    pairs = np.frombuffer(
        data,
        dtype=np.dtype([("key", "<u8"), ("index", "<i4")]),
        count=key_count,
        offset=keys_at + 4,
    )
    keys = pairs["key"] & _ID_MASK
    order = np.argsort(keys, kind="stable")
    return keys[order], values[pairs["index"][order]]


def _vlq(data, offset):
    """A variable-length signed integer"""
    byte = data[offset]
    offset += 1
    value = byte & 0x3F
    shift = 6
    more = byte & 0x40
    while more:
        following = data[offset]
        offset += 1
        value |= (following & 0x7F) << shift
        shift += 7
        more = following & 0x80
    return (-value if byte & 0x80 else value), offset


def _array_references(data, block):
    (value_count,) = struct.unpack_from("<I", data, block)
    offset = block + 4
    values = []
    for _index in range(value_count):
        length, offset = _vlq(data, offset)
        items = np.frombuffer(data, dtype="<u8", count=length, offset=offset) & _ID_MASK
        values.append(tuple(int(item) for item in items))
        offset += 8 * length
    (key_count,) = struct.unpack_from("<I", data, offset)
    pairs = np.frombuffer(
        data,
        dtype=np.dtype([("key", "<u8"), ("index", "<i4")]),
        count=key_count,
        offset=offset + 4,
    )
    return {
        int(key) & _ID_MASK: values[int(index)]
        for key, index in zip(pairs["key"], pairs["index"])
    }


def read_compiled_tweakdb(path) -> CompiledTweakDB:
    """Loads the foreign-key flats of a compiled TweakDB"""
    path = os.fspath(path)
    stat = os.stat(path)
    signature = (
        os.path.normcase(os.path.abspath(path)),
        stat.st_size,
        stat.st_mtime_ns,
    )
    cached = _CACHE.get(signature)
    if cached is not None:
        return cached
    data = read_bytes(path)
    magic, _blob, _parser, _checksum, flats, _records, _queries, _tags = (
        struct.unpack_from("<8I", data, 0)
    )
    if magic != TWEAKDB_MAGIC:
        raise ValueError(f"{path} is not a compiled TweakDB")
    table = _type_table(data, flats)
    if _TWEAKDBID not in table:
        raise ValueError(f"{path} has no record-reference flats")
    keys, targets = _single_references(data, table[_TWEAKDBID])
    arrays = (
        _array_references(data, table[_TWEAKDBID_ARRAY])
        if _TWEAKDBID_ARRAY in table
        else {}
    )
    result = CompiledTweakDB(path, keys, targets, arrays)
    _CACHE.clear()
    _CACHE[signature] = result
    return result
