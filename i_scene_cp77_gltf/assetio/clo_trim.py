import io
import struct
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

from .clo_pac import decode_pac, entry, flag, integer, number, text, unsigned
from .files import png_dimensions

_MILLIMETRE = 0.001
_SUPPORTED = {
    ".btn": "BUTTON",
    ".bth": "BUTTONHOLE",
    ".zpu": "ZIPPER_PULLER",
    ".zsl": "ZIPPER_SLIDER",
    ".zst": "ZIPPER_STOPPER",
    ".zth": "ZIPPER_TEETH",
    ".zss": "ZIPPER_STYLE",
    ".trm": "TRIM",
    ".sst": "TOPSTITCH",
}
_PAYLOAD_EXTENSIONS = {".bnd", ".zom", ".ztm", ".brn", ".tmp"}


@dataclass(frozen=True, slots=True)
class CloTrimMaterial:
    name: str
    base_color: tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0)
    texture_name: str = ""
    normal_name: str = ""
    metallic: float = 0.0
    roughness: float = 0.5


@dataclass(frozen=True, slots=True)
class CloTrimMesh:
    name: str
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]
    face_materials: tuple[int, ...]
    uvs: tuple[tuple[float, float], ...]
    materials: tuple[CloTrimMaterial, ...]


@dataclass(frozen=True, slots=True)
class CloTrimAsset:
    name: str
    data: bytes


@dataclass(frozen=True, slots=True)
class CloTrimStyle:
    kind: str
    name: str
    source_name: str
    meshes: tuple[CloTrimMesh, ...]
    assets: tuple[CloTrimAsset, ...]
    parameters: tuple[tuple[str, float | int | str | bool], ...]
    default_mode: str

    def parameter(self, name, default=None):
        return next((value for key, value in self.parameters if key == name), default)

    def asset(self, name):
        folded = name.casefold()
        return next(
            (asset.data for asset in self.assets if asset.name.casefold() == folded),
            None,
        )

    @property
    def is_path_style(self):
        return self.kind in {"ZIPPER_TEETH", "TOPSTITCH"}


def supported_trim_extensions():
    return tuple(_SUPPORTED)


def _package_files(data):
    offset = data.find(b"PK\x03\x04")
    if offset < 0:
        raise ValueError("CLO trim style contains no embedded package")
    with zipfile.ZipFile(io.BytesIO(data[offset:])) as archive:
        return tuple(
            CloTrimAsset(name, archive.read(name))
            for name in archive.namelist()
            if not name.endswith("/")
        )


def _walk_maps(node, path="root"):
    yield path, node
    for item in node:
        if len(item) != 3:
            continue
        key, kind, value = item
        if kind == 22:
            yield from _walk_maps(value, f"{path}.{key}")
        elif kind == 20:
            for index, (element_kind, element) in enumerate(value):
                if element_kind == 22:
                    yield from _walk_maps(element, f"{path}.{key}[{index}]")


def _payload_roots(assets):
    roots = []
    for asset in assets:
        if PurePosixPath(asset.name).suffix.lower() not in _PAYLOAD_EXTENSIONS:
            continue
        try:
            roots.append((asset.name, decode_pac(asset.data)))
        except (IndexError, struct.error, UnicodeDecodeError, ValueError):
            continue
    if not roots:
        raise ValueError("CLO trim style contains no supported style payload")
    return tuple(roots)


def _string(node, key, default=""):
    value = entry(node, key)
    return text(value) if value is not None else default


def _float(node, key, default=0.0):
    value = entry(node, key)
    return number(value) if value is not None else default


def _int(node, key, default=0):
    value = entry(node, key)
    return integer(value) if value is not None else default


def _uint(node, key, default=0):
    value = entry(node, key)
    return unsigned(value) if value is not None else default


def _bool(node, key, default=False):
    value = entry(node, key)
    return flag(value) if value is not None else default


def _vec3(node, key, default=(0.8, 0.8, 0.8)):
    value = entry(node, key)
    return (
        struct.unpack("<3f", value)
        if value is not None and len(value) == 12
        else default
    )


def _recursive_texture_names(node):
    names = []
    for _path, mapping in _walk_maps(node):
        for key, kind, value in mapping:
            if kind == 15 and key in {"qsFileName", "qsFileNameUTF8"}:
                name = text(value)
                if name and name not in names:
                    names.append(name)
    return tuple(names)


def _material_from_mat_mesh(mat_mesh, index):
    name = (
        _string(mat_mesh, "qsNameUTF8")
        or _string(mat_mesh, "qsName")
        or f"Material {index + 1}"
    )
    material = entry(mat_mesh, "mapMaterial") or []
    rgb = _vec3(material, "v3BaseColor")
    alpha = _float(mat_mesh, "fTransparentAlpha", 1.0)
    metallic = max(0.0, min(1.0, _float(material, "fMetalness", 0.0)))
    gloss = max(0.0, min(1.0, _float(material, "fGlossiness", 0.5)))
    texture_names = _recursive_texture_names(material)
    normal = next(
        (
            item
            for item in texture_names
            if "nrm" in item.casefold() or "normal" in item.casefold()
        ),
        "",
    )
    texture = next((item for item in texture_names if item != normal), "")
    return CloTrimMaterial(name, (*rgb, alpha), texture, normal, metallic, 1.0 - gloss)


def _decode_sources(shape):
    result = []
    for _kind, source in entry(shape, "listSource") or []:
        count = _uint(source, "uiCount")
        raw = entry(source, "baArray") or b""
        if not count or len(raw) % (count * 4):
            result.append((source, ()))
            continue
        components = len(raw) // (count * 4)
        values = struct.unpack(f"<{count * components}f", raw)
        result.append(
            (
                source,
                tuple(
                    tuple(values[i : i + components])
                    for i in range(0, len(values), components)
                ),
            )
        )
    return result


def _basis(kind, point):
    x, y, z = point[:3]
    if kind == "BUTTON":
        return (x * _MILLIMETRE, z * _MILLIMETRE, y * _MILLIMETRE)
    return (x * _MILLIMETRE, y * _MILLIMETRE, z * _MILLIMETRE)


def _center_general_trim(vertices):
    if not vertices:
        return vertices
    low_x = min(point[0] for point in vertices)
    high_x = max(point[0] for point in vertices)
    low_y = min(point[1] for point in vertices)
    high_y = max(point[1] for point in vertices)
    low_z = min(point[2] for point in vertices)
    cx, cy = (low_x + high_x) * 0.5, (low_y + high_y) * 0.5
    return tuple((x - cx, y - cy, z - low_z) for x, y, z in vertices)


def _decode_mat_shape(kind, label, mat_shape):
    shape = entry(mat_shape, "mapShape") or mat_shape
    sources = _decode_sources(shape)
    position_index = _int(shape, "iPositionSourceIndex", 0)
    if position_index < 0 or position_index >= len(sources):
        raise ValueError(f"{label}: missing position source")
    positions = sources[position_index][1]
    if not positions or any(len(point) < 3 for point in positions):
        raise ValueError(f"{label}: malformed position source")
    vertices = tuple(_basis(kind, point) for point in positions)
    if kind == "TRIM":
        vertices = _center_general_trim(vertices)
    uvs = ()
    for source, values in sources:
        source_type = _int(source, "enType", -1)
        if (
            source_type in {-1, 2}
            and len(values) == len(vertices)
            and values
            and len(values[0]) == 2
        ):
            uvs = tuple((float(point[0]), 1.0 - float(point[1])) for point in values)
            break
    material_maps = tuple(item[1] for item in entry(mat_shape, "listMatMesh") or [])
    materials = tuple(
        _material_from_mat_mesh(material, index)
        for index, material in enumerate(material_maps)
    )
    if not materials:
        materials = (CloTrimMaterial(label),)
    invert = _bool(shape, "bInvertWinding")
    faces, face_materials = [], []
    for group_index, (_kind, indexed) in enumerate(
        entry(shape, "listIndexedMesh") or []
    ):
        if _bool(indexed, "bReferedTexCoordIndex") and not _bool(
            indexed, "bUnifiedIndex"
        ):
            raise ValueError(
                f"{label}: independently indexed texture coordinates are not supported"
            )
        raw = entry(indexed, "baPositionIndex") or b""
        if len(raw) % 12:
            raise ValueError(f"{label}: indexed mesh is not triangular")
        indices = struct.unpack(f"<{len(raw) // 4}I", raw)
        for offset in range(0, len(indices), 3):
            face = (indices[offset], indices[offset + 1], indices[offset + 2])
            if any(index >= len(vertices) for index in face):
                raise ValueError(f"{label}: mesh index is outside the position source")
            faces.append((face[0], face[2], face[1]) if invert else face)
            face_materials.append(min(group_index, len(materials) - 1))
    if not faces:
        raise ValueError(f"{label}: trim mesh has no triangles")
    return CloTrimMesh(
        label, vertices, tuple(faces), tuple(face_materials), uvs, materials
    )


def _root_entry(roots, key):
    for _name, root in roots:
        value = entry(root, key)
        if value is not None:
            return value
    return None


def _translated_mesh(mesh, offset):
    if not any(abs(value) > 1.0e-12 for value in offset):
        return mesh
    dx, dy, dz = offset
    return CloTrimMesh(
        mesh.name,
        tuple((x + dx, y + dy, z + dz) for x, y, z in mesh.vertices),
        mesh.faces,
        mesh.face_materials,
        mesh.uvs,
        mesh.materials,
    )


def _shape_meshes(kind, roots):
    meshes = []
    if kind == "BUTTON":
        base = _root_entry(roots, "mapButtonStyleBase") or []
        target = entry(base, "mapRenderingMatShape") or entry(base, "mapMatShape")
        if target:
            meshes.append(
                _decode_mat_shape(
                    kind,
                    _string(base, "qsNameUTF8") or _string(base, "qsName") or "Button",
                    target,
                )
            )
    elif kind == "ZIPPER_PULLER":
        target = _root_entry(roots, "mapZipperPullerMatShape")
        if target:
            meshes.append(_decode_mat_shape(kind, "Zipper Puller", target))
    elif kind == "ZIPPER_SLIDER":
        target = _root_entry(roots, "mapZipperSliderMatShape")
        if target:
            meshes.append(_decode_mat_shape(kind, "Zipper Slider", target))
    elif kind == "ZIPPER_STOPPER":
        targets = _root_entry(roots, "listZipperStopperMatShape") or []
        for index, (_element_kind, target) in enumerate(targets):
            meshes.append(
                _decode_mat_shape(kind, f"Zipper Stopper {index + 1}", target)
            )
    elif kind == "ZIPPER_TEETH":
        style = _root_entry(roots, "mapObjTeethStyle") or []
        data = entry(style, "mapTeethData") or []
        target = entry(data, "mapMatShape") or entry(data, "mapShape")
        if target:
            meshes.append(
                _decode_mat_shape(
                    kind,
                    _string(style, "qsNameUTF8")
                    or _string(style, "qsName")
                    or "Zipper Teeth",
                    target,
                )
            )
    elif kind == "ZIPPER_STYLE":
        slider = _root_entry(roots, "mapZipperSliderMatShape")
        puller = _root_entry(roots, "mapZipperPullerMatShape")
        if slider:
            meshes.append(_decode_mat_shape(kind, "Zipper Slider", slider))
        if puller:
            mesh = _decode_mat_shape(kind, "Zipper Puller", puller)
            position = _root_entry(roots, "v3PullerPosition")
            if position is not None and len(position) == 12:
                px, py, pz = struct.unpack("<3f", position)
                mesh = _translated_mesh(mesh, _basis(kind, (px, py, pz)))
            meshes.append(mesh)
    elif kind == "TRIM":
        tf = _root_entry(roots, "mapTF3D") or []
        for index, (_element_kind, target) in enumerate(
            entry(tf, "listMatShape") or []
        ):
            meshes.append(_decode_mat_shape(kind, f"Trim {index + 1}", target))
    elif kind == "TOPSTITCH":
        multi = _root_entry(roots, "mapMultiStitch") or []
        for stitch_index, (_element_kind, stitch) in enumerate(
            entry(multi, "listStitch") or []
        ):
            target = (
                entry(stitch, "mapStitchObj")
                or entry(stitch, "mapThickStitchObj")
                or entry(stitch, "mapThinStitchObj")
            )
            if target:
                meshes.append(
                    _decode_mat_shape(kind, f"Stitch {stitch_index + 1}", target)
                )
    return tuple(meshes)


def _buttonhole_mesh(roots, assets, style_name):
    base = _root_entry(roots, "mapButtonStyleBase") or []
    image_name = _string(base, "qsButtonHoleImageNameUTF8") or _string(
        base, "qsButtonHoleImageName"
    )
    size = max(_float(base, "fPlanarSize", 10.0), 0.1) * _MILLIMETRE
    image = next(
        (
            asset.data
            for asset in assets
            if asset.name.casefold() == image_name.casefold()
        ),
        None,
    )
    width, height = size, size * 0.35
    pixels = png_dimensions(image) if image else None
    if pixels is not None and pixels[0] and pixels[1]:
        height = width * pixels[1] / pixels[0]
    vertices = (
        (-width * 0.5, -height * 0.5, 0.0002),
        (width * 0.5, -height * 0.5, 0.0002),
        (width * 0.5, height * 0.5, 0.0002),
        (-width * 0.5, height * 0.5, 0.0002),
    )
    material = CloTrimMaterial(style_name, texture_name=image_name)
    return CloTrimMesh(
        style_name,
        vertices,
        ((0, 1, 2), (0, 2, 3)),
        (0, 0),
        ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        (material,),
    )


def _style_name(kind, roots, source_name):
    if kind in {"BUTTON", "BUTTONHOLE"}:
        base = _root_entry(roots, "mapButtonStyleBase") or []
        return (
            _string(base, "qsNameUTF8")
            or _string(base, "qsName")
            or PurePosixPath(source_name).stem
        )
    if kind == "TRIM":
        for _payload_name, root in roots:
            return (
                _string(root, "qsTrimNameUTF8")
                or _string(root, "qsTrimName")
                or PurePosixPath(source_name).stem
            )
    if kind == "TOPSTITCH":
        multi = _root_entry(roots, "mapMultiStitch") or []
        return (
            _string(multi, "qsMultiStitchPresetName") or PurePosixPath(source_name).stem
        )
    return PurePosixPath(source_name).stem


def _parameters(kind, roots):
    result = []
    if kind in {"BUTTON", "BUTTONHOLE"}:
        base = _root_entry(roots, "mapButtonStyleBase") or []
        result.extend(
            (
                ("button_type", _int(base, "enButtonType")),
                ("height_offset_mm", _float(base, "fHeightOffset")),
                ("object_width_mm", _float(base, "fObjWidth")),
                ("planar_size_mm", _float(base, "fPlanarSize")),
            )
        )
    elif kind == "ZIPPER_TEETH":
        style = _root_entry(roots, "mapObjTeethStyle") or []
        data = entry(style, "mapTeethData") or []
        result.append(("teeth_spacing_mm", _float(data, "fTeethSpace")))
    elif kind == "TOPSTITCH":
        multi = _root_entry(roots, "mapMultiStitch") or []
        result.append(("additional_offset_mm", _float(multi, "fAddtionalOffset")))
        stitches = entry(multi, "listStitch") or []
        if stitches:
            stitch = stitches[0][1]
            for source, target in (
                ("fStitchDistance", "stitch_distance_mm"),
                ("fStitchLength", "stitch_length_mm"),
                ("fStitchSpace", "stitch_space_mm"),
                ("fThreadThickness", "thread_thickness_mm"),
                ("fOffset", "offset_mm"),
            ):
                result.append((target, _float(stitch, source)))
            result.append(("render_type", _int(stitch, "enRenderType")))
    return tuple(result)


def decode_clo_trim_style(data, source_name):
    suffix = PurePosixPath(source_name).suffix.lower()
    kind = _SUPPORTED.get(suffix)
    if kind is None:
        raise ValueError(f"Unsupported CLO trim style: {suffix or source_name}")
    assets = _package_files(data)
    roots = _payload_roots(assets)
    name = _style_name(kind, roots, source_name)
    meshes = _shape_meshes(kind, roots)
    if kind == "BUTTONHOLE" and not meshes:
        meshes = (_buttonhole_mesh(roots, assets, name),)
    if kind != "BUTTONHOLE" and not meshes:
        raise ValueError(f"{source_name}: style contains no usable mesh geometry")
    mode = "SURFACE" if kind in {"BUTTONHOLE", "ZIPPER_TEETH", "TOPSTITCH"} else "RIGID"
    return CloTrimStyle(
        kind, name, source_name, meshes, assets, _parameters(kind, roots), mode
    )


def decode_zpac_trim_styles(data):
    """Decode CLO trim-style files embedded in a .zpac project archive"""
    styles = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for archive_name in archive.namelist():
            suffix = PurePosixPath(archive_name).suffix.lower()
            if suffix not in _SUPPORTED:
                continue
            style = decode_clo_trim_style(
                archive.read(archive_name), PurePosixPath(archive_name).name
            )
            styles.append(style)
    return tuple(styles)
