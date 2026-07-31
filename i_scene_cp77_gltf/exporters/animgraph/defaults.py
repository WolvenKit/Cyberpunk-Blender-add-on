from __future__ import annotations

import json
from typing import Any, Dict

from ...animation.animgraph_constants import ANIM_NODE_PREFIX
from ...animation.animgraph.schema import rtti
from ...animation.animgraph.schema.type_utils import unwrap_indirect_type
from .values import cname
from ...redSpace.qs_transform import encode_qs_transform, encode_wkit_quaternion

ANIM_BASE_SERIALIZED_DEFAULT_FIELDS = frozenset({
    'id',
    'poseInfoLogger',
    'visAxes',
    'visMask',
    'visNames',
    'visPostPose',
    'visPostPoseColor',
    'visPrePose',
    'visPrePoseColor',
    'visRigPartMask',
    'visWhenActive',
})


NULL_ARRAY_DEFAULT_FIELDS = frozenset({
    'visMask',
})


NON_SERIALIZED_DEFAULT_FIELDS = frozenset({
    'debug',
    'debugFlag',
    'debugValueProvider',
    'debugMotion',
    'drawFirstFrame',
    'drawLastFrame',
    'drawFootstepFrameRU',
    'drawFootstepFrameRF',
    'drawFootstepFrameLU',
    'drawFootstepFrameLF',
    'drawFootstepFrameTimeOffset',
    'jsonPropertiesLoadedSuccessfully',
    'jsonPropertiesInput',
    'visTransition',
    'visTransitionDuration',
    'isInTestMode',
    'testIdleA',
    'testIdleB',
    'testIdleTransitionWeight',
    'entries',
})


def _schema_vector3(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Dict[str, Any]:
    return {'$type': 'Vector3', 'X': float(x), 'Y': float(y), 'Z': float(z)}

def _schema_vector4(x: float = 0.0, y: float = 0.0, z: float = 0.0, w: float = 0.0) -> Dict[str, Any]:
    return {'$type': 'Vector4', 'X': float(x), 'Y': float(y), 'Z': float(z), 'W': float(w)}

def _schema_quaternion() -> Dict[str, Any]:
    return encode_wkit_quaternion((0.0, 0.0, 0.0, 1.0), quaternion_order='xyzw')

def _schema_qstransform() -> Dict[str, Any]:
    return encode_qs_transform(
        (0.0, 0.0, 0.0, 1.0),
        (0.0, 0.0, 0.0),
        (1.0, 1.0, 1.0),
        translation_w=1.0,
        scale_w=1.0,
        quaternion_order='xyzw',
    )

def _schema_color() -> Dict[str, Any]:
    return {'$type': 'Color', 'Alpha': 0, 'Blue': 0, 'Green': 0, 'Red': 0}

def _schema_resource_path() -> Dict[str, Any]:
    return {'$type': 'ResourcePath', '$storage': 'uint64', '$value': '0'}


def _is_schema_link_type(type_name: str) -> bool:
    if rtti is not None:
        try:
            return bool(rtti.is_link_type(type_name))
        except Exception:
            pass
    return str(type_name or '') in {
        'animPoseLink', 'animFloatLink', 'animVectorLink', 'animIntLink',
        'animBoolLink', 'animQuaternionLink', 'animTransformLink',
    }

def _default_link_wrapper(link_type: str) -> Dict[str, Any]:
    return {'$type': str(link_type or 'animPoseLink'), 'node': None}

def schema_default_value(type_name: str, *, field_name: str = '', parent_type: str = '', _depth: int = 0) -> Any:
    """Return the deterministic REDengine default for one RTTI field."""
    t = str(type_name or '')
    if _depth > 8:
        return None

    if t.startswith('array:'):
        if field_name in NULL_ARRAY_DEFAULT_FIELDS:
            return None
        return []
    if _is_schema_link_type(t):
        return _default_link_wrapper(t)


    if t.startswith('handle:'):
        return None
    if t.startswith('rRef:'):
        return {'DepotPath': _schema_resource_path(), 'Flags': 'Default'}

    if rtti is not None:
        try:
            enum_type = rtti.resolve_enum_type(t, field_name=field_name, parent_type=parent_type, json_path=field_name, value=None)
            if enum_type:
                return rtti.enum_default(enum_type)
        except Exception:
            pass

    if t == 'Bool':
        return 0
    if t in {'Int8', 'Int16', 'Int32', 'Int64'}:
        return 0
    if t in {'Uint8', 'Uint16', 'Uint32', 'Uint64'}:
        if field_name == 'id':
            return 4294967295
        return 0
    if t in {'Float', 'Double'}:
        return 0
    if t == 'String':
        return ''
    if t == 'CName':
        return cname('None')
    if t == 'ResourcePath':
        return _schema_resource_path()
    if t == 'Color':
        return _schema_color()
    if t == 'Vector2':
        return {'$type': 'Vector2', 'X': 0.0, 'Y': 0.0}
    if t == 'Vector3':
        return _schema_vector3()
    if t == 'Vector4':
        return _schema_vector4()
    if t == 'EulerAngles':
        return {'$type': 'EulerAngles', 'Pitch': 0.0, 'Yaw': 0.0, 'Roll': 0.0}
    if t == 'Quaternion':
        return _schema_quaternion()
    if t == 'QsTransform':
        return _schema_qstransform()
    if t == 'animTransformIndex':
        return {'$type': 'animTransformIndex', 'name': cname('None')}
    if t == 'animNamedTrackIndex':
        return {'$type': 'animNamedTrackIndex', 'name': cname('None')}
    if t == 'animVisualTagCondition':
        return {'$type': 'animVisualTagCondition', 'visualTag': cname('None')}
    if t == 'animFloatClamp':
        return {'$type': 'animFloatClamp', 'min': 0.0, 'max': 1.0}
    if t == 'curveData:Float':
        try:
            from ...animation.animgraph.schema.metadata import DEFAULT_FLOAT_CURVE
            return json.loads(json.dumps(DEFAULT_FLOAT_CURVE))
        except Exception:
            return {'InterpolationType': 'BezierCubic', 'LinkType': 'ESLT_Normal', 'Elements': [{'Point': 0.0, 'Value': 0.0}, {'Point': 1.0, 'Value': 1.0}]}


    if rtti is not None:
        inner = unwrap_indirect_type(t)
        try:
            if inner and rtti.has_class(inner) and not rtti.is_graph_node_class(inner):
                return schema_default_struct_for_type(inner, _depth=_depth + 1)
        except Exception:
            pass

    return None

def schema_default_struct_for_type(red_type: str, *, _depth: int = 0) -> Dict[str, Any]:
    out: Dict[str, Any] = {'$type': str(red_type or '')}
    if rtti is None or not red_type:
        return out
    try:
        props = rtti.all_properties(red_type)
    except Exception:
        return out
    for prop in props:
        if not isinstance(prop, dict):
            continue
        name = str(prop.get('name', '') or '')
        ptype = str(prop.get('type', '') or '')
        if not name or name == '$type':
            continue
        if name in NON_SERIALIZED_DEFAULT_FIELDS:
            continue
        out[name] = schema_default_value(ptype, field_name=name, parent_type=red_type, _depth=_depth + 1)
    return out

def schema_default_data_for_type(red_type: str) -> Dict[str, Any]:
    """Materialize current-schema default Data for one runtime node type."""
    data: Dict[str, Any] = {'$type': str(red_type or 'animAnimNode_Unknown')}
    if rtti is None or not red_type:
        return data
    try:
        chain = rtti.parent_chain(red_type, include_self=True)
    except Exception:
        chain = (red_type,)
    for owner_type in chain:
        try:
            props = rtti.declared_properties(owner_type)
        except Exception:
            props = ()
        for prop in props:
            if not isinstance(prop, dict):
                continue
            name = str(prop.get('name', '') or '')
            ptype = str(prop.get('type', '') or '')
            if not name or name == '$type':
                continue
            if name in NON_SERIALIZED_DEFAULT_FIELDS:
                continue


            if owner_type == f'{ANIM_NODE_PREFIX}Base' and name not in ANIM_BASE_SERIALIZED_DEFAULT_FIELDS:
                continue
            data[name] = schema_default_value(ptype, field_name=name, parent_type=owner_type)


        if owner_type == f'{ANIM_NODE_PREFIX}Base':
            data.setdefault('visWhenActive', 0)

    data['$type'] = str(red_type or data.get('$type', 'animAnimNode_Unknown'))
    return data
