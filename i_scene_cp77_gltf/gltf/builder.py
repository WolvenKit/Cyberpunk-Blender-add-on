from __future__ import annotations

import numpy as np


class GLBBuilder:
    """Shared binary-buffer and accessor builder for direct GLB exporters"""

    def __init__(self, *, error_type=ValueError):
        self.error_type = error_type
        self.binary = bytearray()
        self.buffer_views: list[dict] = []
        self.accessors: list[dict] = []
        self._shared_float_accessors: dict[tuple, int] = {}

    def add_shared_float_accessor(
        self, values, accessor_type: str, *, include_bounds: bool = True
    ) -> int:
        """Reuse identical animation arrays without merging their channel identities"""
        array = np.asarray(values, dtype="<f4")
        key = (accessor_type, include_bounds, array.tobytes(order="C"))
        existing = self._shared_float_accessors.get(key)
        if existing is not None:
            return existing
        index = self.add_float_accessor(
            array, accessor_type, include_bounds=include_bounds
        )
        self._shared_float_accessors[key] = index
        return index

    def _align(self, alignment: int = 4) -> None:
        padding = (-len(self.binary)) % alignment
        if padding:
            self.binary.extend(b"\x00" * padding)

    def add_float_accessor(
        self,
        values,
        accessor_type: str,
        *,
        name: str | None = None,
        matrix_column_major: bool = False,
        include_bounds: bool = True,
        target: int | None = None,
    ) -> int:
        array = np.asarray(values, dtype="<f4")
        if not np.all(np.isfinite(array)):
            raise self.error_type(
                f"Accessor {name or accessor_type!r} contains non-finite values."
            )
        if accessor_type == "SCALAR":
            array = array.reshape(-1)
            count, width = len(array), 1
            payload_array = array
            bounds_array = array.reshape(-1, 1)
        else:
            width = {"VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}.get(accessor_type)
            if width is None:
                raise self.error_type(f"Unsupported accessor type {accessor_type!r}.")
            if accessor_type == "MAT4":
                array = array.reshape(-1, 4, 4)
                count = len(array)
                payload_array = (
                    np.swapaxes(array, 1, 2).reshape(count, 16)
                    if matrix_column_major
                    else array.reshape(count, 16)
                )
                bounds_array = payload_array
            else:
                array = array.reshape(-1, width)
                count = len(array)
                payload_array = bounds_array = array

        view_index = self._write_block(payload_array, target)
        accessor = {
            "bufferView": view_index,
            "componentType": 5126,
            "count": count,
            "type": accessor_type,
        }
        if name:
            accessor["name"] = name
        if include_bounds and count:
            accessor["min"] = [float(value) for value in np.min(bounds_array, axis=0)]
            accessor["max"] = [float(value) for value in np.max(bounds_array, axis=0)]
            if width == 1:
                accessor["min"] = accessor["min"][:1]
                accessor["max"] = accessor["max"][:1]
        accessor_index = len(self.accessors)
        self.accessors.append(accessor)
        return accessor_index

    def _write_block(self, array: np.ndarray, target: int | None):
        self._align(4)
        byte_offset = len(self.binary)
        payload = np.ascontiguousarray(array).tobytes(order="C")
        self.binary.extend(payload)
        view_index = len(self.buffer_views)
        view = {"buffer": 0, "byteOffset": byte_offset, "byteLength": len(payload)}
        if target is not None:
            view["target"] = target
        self.buffer_views.append(view)
        return view_index

    def add_integer_accessor(
        self,
        values,
        accessor_type: str,
        component_type: int,
        *,
        name: str | None = None,
        target: int | None = None,
        include_bounds: bool = False,
    ) -> int:
        dtypes = {5121: np.dtype("<u1"), 5123: np.dtype("<u2"), 5125: np.dtype("<u4")}
        dtype = dtypes.get(component_type)
        if dtype is None:
            raise self.error_type(
                f"Unsupported integer component type {component_type}."
            )
        widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
        width = widths.get(accessor_type)
        if width is None:
            raise self.error_type(f"Unsupported accessor type {accessor_type!r}.")

        array = np.asarray(values)
        if not np.all(np.isfinite(array)) or np.any(array != np.floor(array)):
            raise self.error_type(
                f"Accessor {name or accessor_type!r} requires finite integer values."
            )
        if np.any(array < 0):
            raise self.error_type(
                f"Accessor {name or accessor_type} holds negative values."
            )
        if int(array.max(initial=0)) > int(np.iinfo(dtype).max):
            raise self.error_type(
                f"Accessor {name or accessor_type} exceeds component type {component_type}."
            )
        array = array.reshape(-1) if width == 1 else array.reshape(-1, width)
        array = np.ascontiguousarray(array, dtype=dtype)
        count = int(array.shape[0])

        view_index = self._write_block(array, target)
        accessor = {
            "bufferView": view_index,
            "componentType": component_type,
            "count": count,
            "type": accessor_type,
        }
        if name:
            accessor["name"] = name
        if include_bounds and count:
            bounds = array.reshape(count, width)
            accessor["min"] = [int(value) for value in bounds.min(axis=0)]
            accessor["max"] = [int(value) for value in bounds.max(axis=0)]
        accessor_index = len(self.accessors)
        self.accessors.append(accessor)
        return accessor_index

    def add_normalized_accessor(
        self,
        values,
        accessor_type: str,
        component_type: int,
        *,
        name: str | None = None,
        target: int | None = None,
    ) -> int:
        dtypes = {5121: np.dtype("<u1"), 5123: np.dtype("<u2")}
        dtype = dtypes.get(component_type)
        if dtype is None:
            raise self.error_type(
                f"Unsupported normalized component type {component_type}."
            )
        widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
        width = widths.get(accessor_type)
        if width is None:
            raise self.error_type(f"Unsupported accessor type {accessor_type!r}.")

        maximum = float(np.iinfo(dtype).max)
        values = np.asarray(values, dtype=np.float64)
        if not np.all(np.isfinite(values)) or np.any((values < 0.0) | (values > 1.0)):
            raise self.error_type(
                f"Accessor {name or accessor_type!r} requires finite values between 0 and 1."
            )
        scaled = values * maximum
        array = np.ascontiguousarray(np.rint(scaled).astype(dtype).reshape(-1, width))
        count = int(array.shape[0])

        view_index = self._write_block(array, target)
        accessor = {
            "bufferView": view_index,
            "componentType": component_type,
            "count": count,
            "type": accessor_type,
            "normalized": True,
        }
        if name:
            accessor["name"] = name
        accessor_index = len(self.accessors)
        self.accessors.append(accessor)
        return accessor_index
