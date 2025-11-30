import base64
import struct

class BinaryWriter:
    def __init__(self):
        self._buffer = bytearray()

    @property
    def buffer(self):
        return bytes(self._buffer)

    def _write_internal(self, data: bytes):
        self._buffer.extend(data)

    def write_byte(self, value):
        self._write_internal(struct.pack("B", int(value)))

    def write_chars(self, data: bytes):
        self._write_internal(struct.pack(f"{len(data)}s", data))

    def write_int16(self, value):
        self._write_internal(struct.pack("h", int(value)))

    def write_uint16(self, value):
        self._write_internal(struct.pack("H", int(value)))

    def write_uint32(self, value):
        self._write_internal(struct.pack("I", int(value)))

    def write_single(self, value):
        self._write_internal(struct.pack("f", float(value)))

class PhysXWriter:
    @staticmethod
    def __write_header(bw: BinaryWriter, version: int = 2):
        bw.write_chars(b"NXS")

        # mismatch flag byte: reader interprets mismatch = (byte & 1) != 1
        # Use 1 so that mismatch becomes False when reading.
        bw.write_byte(1)

        bw.write_chars(b"HFHF")

        bw.write_uint32(version)

    @staticmethod
    def __write_heightfield(bw: BinaryWriter, hf: dict, version: int = 1):
        rows = int(hf["rows"])
        cols = int(hf["columns"])

        bw.write_uint32(rows)
        bw.write_uint32(cols)

        if version >= 2:
            bw.write_uint32(int(hf["row_limit"]))
            bw.write_uint32(int(hf["col_limit"]))
            bw.write_uint32(int(hf["nb_columns"]))
        else:
            bw.write_single(float(hf["row_limit"]))
            bw.write_single(float(hf["col_limit"]))
            bw.write_single(float(hf["nb_columns"]))

        bw.write_single(float(hf["thickness"]))
        bw.write_single(float(hf["convex_edge_threshold"]))
        bw.write_uint16(int(hf["flags"]))
        bw.write_uint32(int(hf["format"]))

        bounds = hf["min_max_bounds"]
        mn = bounds["min"]
        mx = bounds["max"]

        bw.write_single(float(mn["x"]))
        bw.write_single(float(mn["y"]))
        bw.write_single(float(mn["z"]))
        bw.write_single(float(mx["x"]))
        bw.write_single(float(mx["y"]))
        bw.write_single(float(mx["z"]))

        # Sample metadata / statistics
        samples = hf["samples"]
        nb_samples = len(samples)
        bw.write_uint32(int(hf.get("sample_stride", 4)))
        bw.write_uint32(nb_samples)
        bw.write_single(float(hf["min_height"]))
        bw.write_single(float(hf["max_height"]))

        # Heightfield samples
        for s in samples:
            bw.write_int16(int(s["height"]))
            bw.write_byte(int(s["material_index_0"]))
            bw.write_byte(int(s["material_index_1"]))

    @staticmethod
    def write(heightfields):
        if not isinstance(heightfields, (list, tuple)):
            heightfields = [heightfields]

        bw = BinaryWriter()

        for hf in heightfields:
            PhysXWriter.__write_header(bw, version=int(hf.get("version", 1)))
            PhysXWriter.__write_heightfield(bw, hf, version=int(hf.get("version", 1)))

        raw_bytes = bw.buffer
        return base64.b64encode(raw_bytes).decode("ascii")

