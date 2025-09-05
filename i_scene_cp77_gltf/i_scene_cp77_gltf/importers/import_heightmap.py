import base64
import json
import struct
import bpy
import numpy as np

def load_json(filename):
    with open(filename) as json_file:
        data = json.load(json_file)
    return data

class BinaryReader:
    __position = 0
    __length = 0

    def __init__(self, buffer):
        self.__buffer = buffer
        self.__length = len(buffer)

    @property
    def position(self):
        return self.__position

    @position.setter
    def position(self, value):
        self.__position = value

    @property
    def length(self):
        return self.__length

    def __read_internal(self, count):
        data = self.__buffer[self.position : self.position + count]
        self.position += count
        return data

    def read_byte(self):
        return struct.unpack('B', self.__read_internal(1))[0]

    def read_chars(self, count):
        return struct.unpack(f'{count}s', self.__read_internal(count))[0]

    def read_int16(self):
        return struct.unpack('h', self.__read_internal(2))[0]

    def read_uint16(self):
        return struct.unpack('H', self.__read_internal(2))[0]

    def read_uint32(self):
        return struct.unpack('I', self.__read_internal(4))[0]

    def read_single(self):
        return struct.unpack('f', self.__read_internal(4))[0]


class PhysX:
    @staticmethod
    def __read_header(br):
        return {
            "type1": br.read_chars(3),
            "mismatch": (br.read_byte() & 1) != 1,
            "type2": br.read_chars(4),
            "version": br.read_uint32()
        }

    @staticmethod
    def __load_heightfield(br, header):
        result = {
            "rows": br.read_uint32(),
            "columns": br.read_uint32(),
        }

        if header["version"] >= 2:
            result["row_limit"] = br.read_uint32()
            result["col_limit"] = br.read_uint32()
            result["nb_columns"] = br.read_uint32()
        else:
            result["row_limit"] = br.read_single()
            result["col_limit"] = br.read_single()
            result["nb_columns"] = br.read_single()

        result["thickness"] = br.read_single()
        result["convex_edge_threshold"] = br.read_single()
        result["flags"] = br.read_uint16()
        result["format"] = br.read_uint32()

        result["min_max_bounds"] = {
            "min": {
                "x": 0,
                "y": 0,
                "z": 0
            },
            "max": {
                "x": 0,
                "y": 0,
                "z": 0
            }
        }
        result["min_max_bounds"]["min"]["x"] = br.read_single()
        result["min_max_bounds"]["min"]["y"] = br.read_single()
        result["min_max_bounds"]["min"]["z"] = br.read_single()
        result["min_max_bounds"]["max"]["x"] = br.read_single()
        result["min_max_bounds"]["max"]["y"] = br.read_single()
        result["min_max_bounds"]["max"]["z"] = br.read_single()

        result["sample_stride"] = br.read_uint32()
        result["nb_samples"] = br.read_uint32()
        result["min_height"] = br.read_single()
        result["max_height"] = br.read_single()

        result["samples"] = []

        nb_verts = result["rows"] * result["columns"]
        if nb_verts > 0:
            for i in range(nb_verts):
                result["samples"].append({
                    "height": br.read_int16(),
                    "material_index_0": br.read_byte(),
                    "material_index_1": br.read_byte(),
                })

        return result

    @staticmethod
    def load(b64str):
        data = base64.b64decode(b64str)
        br = BinaryReader(data)

        result = []

        while br.position < br.length:
            header = PhysX.__read_header(br)

            if header["type1"] == b"NXS" and header["type2"] == b"HFHF":
                result.append(PhysX.__load_heightfield(br, header))
            else:
                raise Exception()

        return result

def create_geom_from_heightfield(heightfieldGeometry):
    tmp = PhysX.load(heightfieldGeometry['Bytes'])
    for key in tmp[0].keys():
        if key != 'samples':
            print(f"{key}: {tmp[0][key]}")
        else:
            print(f"{key}: {len(tmp[0][key])} samples")
    # === Your PhysX heightfield data ===
    hf = tmp[0]  # replace with your data dict

    rows = hf["rows"]
    cols = hf["columns"]

    # Heights as 2D grid
    heights = np.array([s["height"] for s in hf["samples"]], dtype=np.float32).reshape((rows, cols))

    bounds = hf["min_max_bounds"]

    min_x, max_x = bounds["min"]["x"], bounds["max"]["x"]
    min_z, max_z = bounds["min"]["z"], bounds["max"]["z"]

    size_x = max_x - min_x
    size_z = max_z - min_z

    verts = []
    for r in range(rows):
        for c in range(cols):
            # normalized [0..1] across grid
            u = c / (cols - 1)
            v = r / (rows - 1)

            # map to XZ footprint
            x = min_x + u * size_x
            z = min_z + v * size_z

            # height directly from samples
            y = heights[r, c] * 0.001  # <-- apply only a scale factor if needed

            verts.append((x, z, y))

    # === Build faces with material indices ===
    faces = []
    face_mats = []  # one entry per face, with material index

    samples = hf["samples"]

    for r in range(rows - 1):
        for c in range(cols - 1):
            base = r * cols + c
            v0 = base
            v1 = v0 + 1
            v2 = v0 + cols
            v3 = v2 + 1

            # Index in the samples array for this grid point
            s_idx = r * cols + c
            s = samples[s_idx]

            # Two triangles per quad
            faces.append((v0, v2, v1))
            face_mats.append(s["material_index_0"])

            faces.append((v1, v2, v3))
            face_mats.append(s["material_index_1"])

    # === Create mesh ===
    mesh = bpy.data.meshes.new("HeightfieldMesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    # === Create object ===
    obj = bpy.data.objects.new("Heightfield", mesh)
    bpy.context.collection.objects.link(obj)

    # === Setup materials ===
    unique_mats = sorted(set(face_mats))
    mat_index_map = {m: i for i, m in enumerate(unique_mats)}

    # Create dummy materials (just colored by index)
    for m_id in unique_mats:
        mat = bpy.data.materials.new(name=f"Mat_{m_id}")
        mat.diffuse_color = ((m_id % 10) / 10.0, (m_id % 7) / 7.0, (m_id % 5) / 5.0, 1.0)
        obj.data.materials.append(mat)

    # Assign materials per face
    for poly, mat_id in zip(mesh.polygons, face_mats):
        poly.material_index = mat_index_map[mat_id]

    # === Smooth shading ===
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()

    print(f"Heightfield mesh created with {len(unique_mats)} materials")
    return obj

def main():
    data = load_json(r"C:\CPMod\terrain_collision\source\raw\base\worlds\03_night_city\_compiled\default\exterior_-2_-8_0_3.streamingsector.json")
    wtcs=[node for node in data['Data']['RootChunk']['nodes'] if node['Data']['$type'] == 'worldTerrainCollisionNode']
    for node in wtcs:
        heightfieldGeometry = node['Data']['heightfieldGeometry']
                
        obj=create_geom_from_heightfield(heightfieldGeometry)
        obj['NodeIndex']=node['Data']['NodeIndex']



if __name__ == '__main__':
    main()