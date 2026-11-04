import struct

MAP = 22
LIST = 20


def _decode(data, kind, offset, length):
    if kind == MAP:
        count = data[offset]
        key_lengths = data[offset + 1 : offset + 1 + count]
        kinds = data[offset + 1 + count : offset + 1 + 2 * count]
        lengths = struct.unpack_from(f"<{count}I", data, offset + 1 + 2 * count)
        position = offset + 1 + 6 * count
        entries = []
        for key_length, value_kind, value_length in zip(key_lengths, kinds, lengths):
            key = bytes(data[position : position + key_length]).decode("latin-1")
            position += key_length
            entries.append(
                (key, value_kind, _decode(data, value_kind, position, value_length))
            )
            position += value_length
    elif kind == LIST:
        count = struct.unpack_from("<I", data, offset)[0]
        if count == 0:
            return []
        value_kind = data[offset + 4]
        lengths = struct.unpack_from(f"<{count}I", data, offset + 5)
        position = offset + 5 + 4 * count
        entries = []
        for value_length in lengths:
            entries.append(
                (value_kind, _decode(data, value_kind, position, value_length))
            )
            position += value_length
    else:
        return bytes(data[offset : offset + length])
    if position != offset + length:
        raise ValueError(f"Malformed .pac container at byte {offset}")
    return entries


def decode_pac(data):
    """The root map of a .pac file as a list of (key, type, value) entries"""
    return _decode(memoryview(data), MAP, 0, len(data))


def entry(node, key, default=None):
    return next((value for name, _kind, value in node if name == key), default)


def text(value):
    return bytes(value).decode("utf-8", "replace")


def integer(value):
    return struct.unpack("<i", value)[0]


def unsigned(value):
    return struct.unpack("<I", value)[0]


def number(value):
    return struct.unpack("<f", value)[0]


def flag(value):
    return bool(value[0])


def vector2(value):
    return struct.unpack("<2f", value)


def matrix3(value):
    return struct.unpack("<9f", value)
