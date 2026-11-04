import base64
import struct

_HEAD = b"NXS\x01HFHF"
_GRID = struct.Struct("<II")
# The row and column counts follow the head's magic and a version number.
_GRID_OFFSET = 12
# A grid needs two samples along each side to hold a cell.
_MINIMUM_SIDE = 2
# The base64 text of the first 21 bytes, which hold the head and the counts.
_HEAD_TEXT = 28


def heightfield_grid(encoded: str) -> tuple[int, int]:
    """The (rows, columns) of the samples of a cooked PhysX heightfield"""
    try:
        head = base64.b64decode(encoded[:_HEAD_TEXT])
    except ValueError as error:
        raise ValueError("the heightfield geometry is not base64 text") from error
    if len(head) < _GRID_OFFSET + _GRID.size or not head.startswith(_HEAD):
        raise ValueError("the heightfield geometry is not a cooked PhysX heightfield")
    rows, columns = _GRID.unpack_from(head, _GRID_OFFSET)
    if rows < _MINIMUM_SIDE or columns < _MINIMUM_SIDE:
        raise ValueError(
            f"the heightfield geometry has {rows} rows and {columns} columns, but a grid needs at least "
            f"{_MINIMUM_SIDE} of each"
        )
    return rows, columns
