import json
import math
import os


def _yaml_scalar(value):
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("ArchiveXL YAML cannot contain non-finite numbers.")
        return repr(value)
    if isinstance(value, str):
        # JSON double-quoted strings are valid YAML scalars and safely preserve
        # depot-path backslashes, punctuation, and Unicode.
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"Unsupported ArchiveXL YAML value: {type(value).__name__}")


def _yaml_lines(value, indent=0):
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            yield f"{prefix}{{}}"
            return
        for key, child in value.items():
            key_text = _yaml_scalar(str(key))
            if isinstance(child, (dict, list)):
                if child:
                    yield f"{prefix}{key_text}:"
                    yield from _yaml_lines(child, indent + 2)
                else:
                    empty = "{}" if isinstance(child, dict) else "[]"
                    yield f"{prefix}{key_text}: {empty}"
            else:
                yield f"{prefix}{key_text}: {_yaml_scalar(child)}"
        return
    if isinstance(value, list):
        if not value:
            yield f"{prefix}[]"
            return
        for child in value:
            if isinstance(child, (dict, list)):
                if child:
                    yield f"{prefix}-"
                    yield from _yaml_lines(child, indent + 2)
                else:
                    empty = "{}" if isinstance(child, dict) else "[]"
                    yield f"{prefix}- {empty}"
            else:
                yield f"{prefix}- {_yaml_scalar(child)}"
        return
    yield f"{prefix}{_yaml_scalar(value)}"


def serialize_archive_xl(data, *, use_yaml=False):
    if use_yaml:
        return "\n".join(_yaml_lines(data)) + "\n"
    return json.dumps(data, indent=4)


def build_archive_xl(xlfilename, deletions, expectedNodes):
    projectsector = os.path.splitext(os.path.basename(xlfilename))[0] + '.streamingsector'
    xlfile = {}
    xlfile['streaming'] = {'sectors': []}
    sectors = xlfile['streaming']['sectors']
    for sectorPath in deletions:
        if sectorPath == 'Decals' or sectorPath == 'Collisions':
            continue

        if sectorPath == projectsector:
            continue
        new_sector = {}
        new_sector['path'] = sectorPath
        if sectorPath in expectedNodes.keys():
            new_sector['expectedNodes'] = expectedNodes[sectorPath]
        else:
            continue
        new_sector['nodeDeletions'] = []
        sectorData = deletions[sectorPath]
        currentNodeIndex = -1
        currentNodeComment = ''
        currentNodeType = ''
        for empty_collection in sectorData:
            currentNodeIndex = empty_collection['nodeDataIndex']
            currentNodeComment = empty_collection.name
            currentNodeType = empty_collection['nodeType']
            if currentNodeIndex > -1:
                new_sector['nodeDeletions'].append(
                        {'index': currentNodeIndex, 'type': currentNodeType, 'debugName': currentNodeComment}
                        )
            # set instance variables
        for decal in deletions['Decals'][sectorPath]:
            print('Deleting ', decal)
            new_sector['nodeDeletions'].append(
                    {'index': decal['nodeIndex'], 'type': decal['NodeType'], 'debugName': decal['NodeComment']}
                    )
        for collision in deletions['Collisions'][sectorPath].keys():
            print('Deleting ', collision, ' Actors ', deletions['Collisions'][sectorPath][collision])
            new_sector['nodeDeletions'].append(
                    {'index': collision, "actorDeletions": deletions['Collisions'][sectorPath][collision],
                     'type': 'worldCollisionNode', 'debugName': collision,
                     'expectedActors': expectedNodes[sectorPath + '_NI_' + str(collision)]}
                    )
        sectors.append(new_sector)
    return xlfile


def to_archive_xl(xlfilename, deletions, expectedNodes, *, use_yaml=False):
    from ...common.atomic import atomic_write_text

    document = build_archive_xl(xlfilename, deletions, expectedNodes)
    atomic_write_text(
        xlfilename,
        serialize_archive_xl(document, use_yaml=use_yaml),
    )
