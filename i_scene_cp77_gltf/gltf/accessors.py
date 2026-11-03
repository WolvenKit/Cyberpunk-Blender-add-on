from __future__ import annotations

import numpy as np


class AccessorError(ValueError):
    pass


COMPONENT_DTYPES = {
    5120: np.dtype("i1"),
    5121: np.dtype("u1"),
    5122: np.dtype("<i2"),
    5123: np.dtype("<u2"),
    5125: np.dtype("<u4"),
    5126: np.dtype("<f4"),
}
TYPE_SHAPES = {
    "SCALAR": (1, 1),
    "VEC2": (1, 2),
    "VEC3": (1, 3),
    "VEC4": (1, 4),
    "MAT2": (2, 2),
    "MAT3": (3, 3),
    "MAT4": (4, 4),
}


class GLTFAccessorReader:
    """Decode validated glTF arrays, retaining buffer views until a copy is needed"""

    def __init__(self, gltf, *, error_type=AccessorError):
        self.error_type = error_type
        self.document = gltf.document
        self.binary = gltf.binary
        self.accessors = self.document.get("accessors") or ()
        self.buffer_views = self.document.get("bufferViews") or ()
        buffers = self.document.get("buffers") or ()
        self.binary_length = (
            self._integer(buffers[0].get("byteLength"), "buffer byteLength")
            if buffers
            else 0
        )
        if len(buffers) > 1 or (buffers and "uri" in buffers[0]):
            self._fail("glTF buffers must be resolved before decoding accessors.")
        if self.binary_length > len(self.binary):
            self._fail("The declared glTF buffer exceeds the available binary data.")

    def _fail(self, message):
        raise self.error_type(message)

    def _integer(self, value, label, *, minimum=0):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            self._fail(f"{label} must be an integer >= {minimum}.")
        return value

    def _layout(self, accessor):
        component = self._integer(
            accessor.get("componentType"), "accessor componentType"
        )
        dtype = COMPONENT_DTYPES.get(component)
        shape = TYPE_SHAPES.get(accessor.get("type"))
        if dtype is None or shape is None:
            self._fail("Unsupported glTF accessor component type or shape.")
        normalized = accessor.get("normalized", False)
        if not isinstance(normalized, bool) or (
            normalized and component not in (5120, 5121, 5122, 5123)
        ):
            self._fail(
                "Only signed/unsigned byte and short accessors may be normalized."
            )
        columns, rows = shape
        column_bytes = rows * dtype.itemsize
        column_stride = (column_bytes + 3) & ~3 if columns > 1 else column_bytes
        return dtype, columns, rows, column_stride

    def _view(self, view_index, offset, count, layout, *, sparse=False):
        view_index = self._integer(view_index, "bufferView index")
        if view_index >= len(self.buffer_views):
            self._fail(f"Invalid glTF bufferView index {view_index}.")
        view = self.buffer_views[view_index]
        if self._integer(view.get("buffer", 0), "buffer index") != 0:
            self._fail("Accessor references an unresolved glTF buffer.")
        start = self._integer(view.get("byteOffset", 0), "bufferView byteOffset")
        length = self._integer(
            view.get("byteLength"), "bufferView byteLength", minimum=1
        )
        if start + length > self.binary_length:
            self._fail(f"bufferView {view_index} exceeds its declared buffer.")
        offset = self._integer(offset, "accessor byteOffset")
        dtype, columns, rows, column_stride = layout
        element_bytes = columns * column_stride
        stride = self._integer(
            view.get("byteStride", element_bytes), "accessor stride", minimum=1
        )
        if stride < element_bytes or stride % dtype.itemsize:
            self._fail(f"Accessor has invalid byte stride {stride}.")
        if "byteStride" in view and (
            sparse or stride < 4 or stride > 252 or stride % 4
        ):
            self._fail("Invalid byteStride on a glTF bufferView.")
        if offset % dtype.itemsize or (start + offset) % dtype.itemsize:
            self._fail("Accessor data is not aligned to its component size.")
        if columns > 1 and (start + offset) % 4:
            self._fail("Matrix accessor columns must begin on four-byte boundaries.")
        end = (
            offset
            + (count - 1) * stride
            + (columns - 1) * column_stride
            + rows * dtype.itemsize
        )
        if offset > length or end > length:
            self._fail("Accessor exceeds its glTF bufferView.")
        raw = np.ndarray(
            (count, columns, rows),
            dtype=dtype,
            buffer=self.binary,
            offset=start + offset,
            strides=(stride, column_stride, dtype.itemsize),
        )
        return raw.reshape(count, columns * rows)

    def read(self, accessor_index, *, dtype=None, copy=False):
        accessor_index = self._integer(accessor_index, "accessor index")
        if accessor_index >= len(self.accessors):
            self._fail(f"Invalid glTF accessor index {accessor_index}.")
        accessor = self.accessors[accessor_index]
        count = self._integer(accessor.get("count"), "accessor count", minimum=1)
        layout = self._layout(accessor)
        component_dtype, columns, rows, _ = layout
        width = columns * rows
        view_index = accessor.get("bufferView")
        sparse = accessor.get("sparse")
        if view_index is None:
            if accessor.get("byteOffset", 0) != 0:
                self._fail("An accessor without a bufferView cannot have a byteOffset.")
            if count * width * component_dtype.itemsize > max(
                self.binary_length * 1024, 1024 * 1024
            ):
                self._fail(
                    "Sparse accessor expansion exceeds the supported allocation limit."
                )
            raw = np.zeros((count, width), dtype=component_dtype)
        else:
            raw = self._view(view_index, accessor.get("byteOffset", 0), count, layout)
        if sparse:
            sparse_count = self._integer(sparse.get("count"), "sparse count", minimum=1)
            if sparse_count > count:
                self._fail("Sparse accessor count exceeds its base count.")
            indices = sparse.get("indices") or {}
            index_type = indices.get("componentType")
            if index_type not in (5121, 5123, 5125):
                self._fail("Sparse indices require an unsigned byte, short or integer.")
            index_dtype = COMPONENT_DTYPES[index_type]
            index_values = self._view(
                indices.get("bufferView"),
                indices.get("byteOffset", 0),
                sparse_count,
                (index_dtype, 1, 1, index_dtype.itemsize),
                sparse=True,
            ).reshape(-1)
            if index_values[-1] >= count or np.any(
                index_values[1:] <= index_values[:-1]
            ):
                self._fail("Sparse accessor indices must be increasing and in range.")
            values = sparse.get("values") or {}
            replacements = self._view(
                values.get("bufferView"),
                values.get("byteOffset", 0),
                sparse_count,
                layout,
                sparse=True,
            )
            if view_index is not None:
                raw = raw.copy()
            raw[index_values] = replacements
        if accessor.get("normalized", False):
            result = raw.astype(np.float32)
            result /= float(np.iinfo(component_dtype).max)
            if component_dtype.kind == "i":
                np.maximum(result, -1.0, out=result)
            if dtype is not None:
                result = result.astype(dtype, copy=False)
        else:
            result = np.asarray(raw, dtype=dtype or component_dtype)
            if copy:
                result = result.copy()
        return result[:, 0] if width == 1 else result
