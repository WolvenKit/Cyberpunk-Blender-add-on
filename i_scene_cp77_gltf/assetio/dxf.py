import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Entity:
    kind: str
    tags: tuple
    vertices: tuple = ()

    def value(self, code, default=None):
        return next((value for key, value in self.tags if key == code), default)

    def number(self, code, default=0.0):
        value = float(self.value(code, default))
        if not math.isfinite(value):
            raise ValueError("DXF contains a non-finite coordinate")
        return value

    @property
    def layer(self):
        return self.value(8, "0").strip()


@dataclass(frozen=True)
class Drawing:
    units: int
    blocks: dict
    entities: tuple


def _entities(records):
    result = []
    index = 0
    while index < len(records):
        item = records[index]
        index += 1
        if item.kind == "POLYLINE":
            vertices = []
            while index < len(records) and records[index].kind == "VERTEX":
                vertices.append(records[index])
                index += 1
            if index == len(records) or records[index].kind != "SEQEND":
                raise ValueError("DXF POLYLINE is missing SEQEND")
            index += 1
            item = Entity(item.kind, item.tags, tuple(vertices))
        result.append(item)
    return tuple(result)


def parse_ascii_dxf(data):
    if data.startswith(b"AutoCAD Binary DXF"):
        raise ValueError("Export an ASCII DXF file")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    lines = text.splitlines()
    if len(lines) % 2:
        raise ValueError("DXF has an incomplete group-code/value pair")
    try:
        tags = [
            (int(lines[i].strip()), lines[i + 1].strip())
            for i in range(0, len(lines), 2)
        ]
    except ValueError as error:
        raise ValueError("DXF group codes must be integers") from error
    if not tags or tags[-1] != (0, "EOF"):
        raise ValueError("DXF is missing its EOF record")
    units = 0
    for i, tag in enumerate(tags[:-1]):
        if tag == (9, "$INSUNITS"):
            units = int(tags[i + 1][1])
    records = []
    for code, value in tags:
        if code == 0:
            records.append([value, []])
        elif records:
            records[-1][1].append((code, value))
    records = [Entity(kind, tuple(values)) for kind, values in records]
    section, blocks, entities, block, content = "", {}, [], None, []
    for item in records:
        if item.kind == "SECTION":
            section = item.value(2, "")
        elif item.kind == "ENDSEC":
            section = ""
        elif section == "BLOCKS":
            if item.kind == "BLOCK":
                if block is not None:
                    raise ValueError("Nested DXF BLOCK declarations")
                block, content = item, []
            elif item.kind == "ENDBLK":
                if block is None:
                    raise ValueError("Unexpected DXF ENDBLK")
                name = block.value(2)
                if not name or name in blocks:
                    raise ValueError("DXF block names must be present and unique")
                blocks[name] = (block, _entities(content))
                block = None
            elif block is not None:
                content.append(item)
        elif section == "ENTITIES":
            entities.append(item)
    if block is not None:
        raise ValueError("Unclosed DXF BLOCK")
    return Drawing(units, blocks, _entities(entities))
