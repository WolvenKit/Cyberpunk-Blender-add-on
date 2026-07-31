from __future__ import annotations

import re
import typing

import bpy


EDGE_SEMANTICS_ITEMS = (
    ('dataflow', 'Dataflow', 'Real REDengine pose/value dependency link'),
    ('container_boundary', 'Container Boundary', 'Editor projection across an enterable subgraph boundary'),
    ('root_output', 'Root Output', 'Editor projection of Root.outputNode'),
    ('state_summary', 'State Summary', 'Editor-only state aggregation socket'),
    ('transition_summary', 'Transition Summary', 'Editor-only state transition aggregation socket'),
    ('editor_dangle', 'Editor Dangle', 'Editor-only dangle particle/constraint relationship'),
    ('editor_dangle_constraint', 'Editor Dangle Constraint', 'Editor-only dangle constraint edge between particles'),
    ('editor_collision_shape', 'Editor Collision Shape', 'Editor-only dangle collision-shape relationship'),
    ('layout_only', 'Layout Only', 'Layout-only relationship; never serialized'),
    ('unknown', 'Unknown', 'Unclassified socket binding'),
)


def _draw_socket_label(socket, _context, layout, _node, text):
    layout.label(text=text)


def _safe_setattr(obj, name: str, value: typing.Any) -> None:
    try:
        setattr(obj, name, value)
    except Exception:
        try:
            obj[name] = value
        except Exception:
            pass


def split_field_path(path: str) -> typing.Tuple[str, int]:
    """Split a REDengine field path into base name and optional array index."""
    if not path:
        return "", -1
    tail = path.rsplit('.', 1)[-1]
    match = re.match(r'^([^\[]+)\[(\d+)\]$', tail)
    if match:
        return match.group(1), int(match.group(2))
    return tail.split('[', 1)[0], -1


def bind_red_socket(
    socket: bpy.types.NodeSocket,
    *,
    role: str,
    owner_handle: str = "",
    field_name: str = "",
    json_path: str = "",
    link_type: str = "",
    array_index: int = -1,
    exportable: bool = True,
    edge_semantics: str = 'dataflow',
    source_handle: str = "",
    target_handle: str = "",
    ref_style: str = "",
    pseudo: bool = False,
) -> bpy.types.NodeSocket:
    """Attach REDengine serialization metadata to a socket."""
    if not field_name and json_path:
        field_name, parsed_index = split_field_path(json_path)
        if array_index < 0:
            array_index = parsed_index
    if edge_semantics not in {item[0] for item in EDGE_SEMANTICS_ITEMS}:
        edge_semantics = 'unknown'

    _safe_setattr(socket, 'red_socket_role', role or '')
    _safe_setattr(socket, 'red_owner_handle', str(owner_handle or ''))
    _safe_setattr(socket, 'red_field_name', str(field_name or ''))
    _safe_setattr(socket, 'red_json_path', str(json_path or ''))
    _safe_setattr(socket, 'red_link_type', str(link_type or ''))
    _safe_setattr(socket, 'red_array_index', int(array_index))
    _safe_setattr(socket, 'red_exportable', bool(exportable))
    _safe_setattr(socket, 'red_edge_semantics', edge_semantics)
    _safe_setattr(socket, 'red_source_handle', str(source_handle or ''))
    _safe_setattr(socket, 'red_target_handle', str(target_handle or ''))
    _safe_setattr(socket, 'red_ref_style', str(ref_style or ''))
    _safe_setattr(socket, 'red_pseudo', bool(pseudo))
    return socket


def bind_input_socket(
    socket: bpy.types.NodeSocket,
    *,
    owner_handle: str,
    json_path: str,
    link_type: str,
    exportable: bool = True,
    edge_semantics: str = 'dataflow',
    source_handle: str = "",
    ref_style: str = "",
    pseudo: bool = False,
) -> bpy.types.NodeSocket:
    field_name, array_index = split_field_path(json_path)
    return bind_red_socket(
        socket,
        role='input',
        owner_handle=owner_handle,
        field_name=field_name,
        json_path=json_path,
        link_type=link_type,
        array_index=array_index,
        exportable=exportable,
        edge_semantics=edge_semantics,
        source_handle=source_handle,
        target_handle=owner_handle,
        ref_style=ref_style,
        pseudo=pseudo,
    )


def bind_output_socket(
    socket: bpy.types.NodeSocket,
    *,
    owner_handle: str,
    link_type: str,
    exportable: bool = True,
    edge_semantics: str = 'dataflow',
    pseudo: bool = False,
) -> bpy.types.NodeSocket:
    return bind_red_socket(
        socket,
        role='output',
        owner_handle=owner_handle,
        link_type=link_type,
        exportable=exportable,
        edge_semantics=edge_semantics,
        source_handle=owner_handle,
        pseudo=pseudo,
    )


def socket_binding(socket: bpy.types.NodeSocket) -> dict:
    """Return a plain snapshot of a socket REDengine binding."""
    return {
        'role': getattr(socket, 'red_socket_role', ''),
        'owner_handle': getattr(socket, 'red_owner_handle', ''),
        'field_name': getattr(socket, 'red_field_name', ''),
        'json_path': getattr(socket, 'red_json_path', ''),
        'link_type': getattr(socket, 'red_link_type', ''),
        'array_index': getattr(socket, 'red_array_index', -1),
        'exportable': getattr(socket, 'red_exportable', True),
        'edge_semantics': getattr(socket, 'red_edge_semantics', 'unknown'),
        'source_handle': getattr(socket, 'red_source_handle', ''),
        'target_handle': getattr(socket, 'red_target_handle', ''),
        'ref_style': getattr(socket, 'red_ref_style', ''),
        'pseudo': getattr(socket, 'red_pseudo', False),
    }


class _REDengineSocketMetadata:
    pass


def _metadata_annotations():
    return {
        'red_socket_role': bpy.props.EnumProperty(
            name='Socket Role',
            items=(('input', 'Input', ''), ('output', 'Output', ''), ('internal', 'Internal', '')),
            default='input',
        ),
        'red_owner_handle': bpy.props.StringProperty(
            name='Owner HandleId',
            description='HandleId of the REDengine node that owns this socket',
            default='',
        ),
        'red_field_name': bpy.props.StringProperty(
            name='REDengine Field',
            description='Declared REDengine field represented by this input socket',
            default='',
        ),
        'red_json_path': bpy.props.StringProperty(
            name='REDengine JSON Path',
            description='Path from the owning node Data object to the link field',
            default='',
        ),
        'red_link_type': bpy.props.StringProperty(
            name='REDengine Link Type',
            description='Serialized anim*Link wrapper type for this socket',
            default='',
        ),
        'red_array_index': bpy.props.IntProperty(
            name='Array Index',
            description='Array index for sockets representing array link fields; -1 otherwise',
            default=-1,
        ),
        'red_exportable': bpy.props.BoolProperty(
            name='Exportable',
            description='False for editor-only sockets that must not serialize as game dataflow links',
            default=True,
        ),
        'red_edge_semantics': bpy.props.EnumProperty(
            name='Edge Semantics',
            items=EDGE_SEMANTICS_ITEMS,
            default='dataflow',
        ),
        'red_source_handle': bpy.props.StringProperty(
            name='Source HandleId',
            description='Cached source HandleId for imported/reconstructed dataflow links',
            default='',
        ),
        'red_target_handle': bpy.props.StringProperty(
            name='Target HandleId',
            description='Cached target HandleId for imported/reconstructed dataflow links',
            default='',
        ),
        'red_ref_style': bpy.props.StringProperty(
            name='Reference Style',
            description='Original reference wrapper style, e.g. HandleRefId or HandleIdInline',
            default='',
        ),
        'red_pseudo': bpy.props.BoolProperty(
            name='Editor Socket',
            description='True for editor-derived sockets that have no direct REDengine field',
            default=False,
        ),
    }


class REDengine_AnimGraphSocket_Pose(bpy.types.NodeSocket):
    bl_idname = 'REDengine_AnimGraphSocket_Pose'
    bl_label = 'Pose Socket'
    color = (1.0, 1.0, 1.0, 1.0)
    __annotations__ = _metadata_annotations()

    def draw(self, context, layout, node, text):
        _draw_socket_label(self, context, layout, node, text)

    def draw_color(self, context, node):
        return self.color


class REDengine_AnimGraphSocket_Float(bpy.types.NodeSocket):
    bl_idname = 'REDengine_AnimGraphSocket_Float'
    bl_label = 'Float Socket'
    color = (0.25, 0.85, 0.25, 1.0)
    __annotations__ = _metadata_annotations()

    def draw(self, context, layout, node, text):
        _draw_socket_label(self, context, layout, node, text)

    def draw_color(self, context, node):
        return self.color


class REDengine_AnimGraphSocket_Vector(bpy.types.NodeSocket):
    bl_idname = 'REDengine_AnimGraphSocket_Vector'
    bl_label = 'Vector Socket'
    color = (0.2, 0.45, 1.0, 1.0)
    __annotations__ = _metadata_annotations()

    def draw(self, context, layout, node, text):
        _draw_socket_label(self, context, layout, node, text)

    def draw_color(self, context, node):
        return self.color


class REDengine_AnimGraphSocket_Int(bpy.types.NodeSocket):
    bl_idname = 'REDengine_AnimGraphSocket_Int'
    bl_label = 'Int Socket'
    color = (0.1, 0.9, 0.9, 1.0)
    __annotations__ = _metadata_annotations()

    def draw(self, context, layout, node, text):
        _draw_socket_label(self, context, layout, node, text)

    def draw_color(self, context, node):
        return self.color


class REDengine_AnimGraphSocket_Bool(bpy.types.NodeSocket):
    bl_idname = 'REDengine_AnimGraphSocket_Bool'
    bl_label = 'Bool Socket'
    color = (0.55, 0.0, 0.0, 1.0)
    __annotations__ = _metadata_annotations()

    def draw(self, context, layout, node, text):
        _draw_socket_label(self, context, layout, node, text)

    def draw_color(self, context, node):
        return self.color


class REDengine_AnimGraphSocket_Quaternion(bpy.types.NodeSocket):
    bl_idname = 'REDengine_AnimGraphSocket_Quaternion'
    bl_label = 'Quaternion Socket'
    color = (0.75, 0.65, 0.0, 1.0)
    __annotations__ = _metadata_annotations()

    def draw(self, context, layout, node, text):
        _draw_socket_label(self, context, layout, node, text)

    def draw_color(self, context, node):
        return self.color


class REDengine_AnimGraphSocket_Transform(bpy.types.NodeSocket):
    bl_idname = 'REDengine_AnimGraphSocket_Transform'
    bl_label = 'Transform Socket'
    color = (0.9, 0.1, 0.9, 1.0)
    __annotations__ = _metadata_annotations()

    def draw(self, context, layout, node, text):
        _draw_socket_label(self, context, layout, node, text)

    def draw_color(self, context, node):
        return self.color


class REDengine_AnimGraphSocket_Editor(bpy.types.NodeSocket):
    bl_idname = 'REDengine_AnimGraphSocket_Editor'
    bl_label = 'Editor Socket'
    color = (0.55, 0.55, 0.55, 1.0)
    __annotations__ = _metadata_annotations()

    def draw(self, context, layout, node, text):
        _draw_socket_label(self, context, layout, node, text)

    def draw_color(self, context, node):
        return self.color


class REDengine_AnimGraphSocket_Transition(bpy.types.NodeSocket):
    bl_idname = 'REDengine_AnimGraphSocket_Transition'
    bl_label = 'Transition Socket'
    color = (0.9, 0.5, 0.1, 1.0)
    __annotations__ = _metadata_annotations()

    def draw(self, context, layout, node, text):
        _draw_socket_label(self, context, layout, node, text)

    def draw_color(self, context, node):
        return self.color
