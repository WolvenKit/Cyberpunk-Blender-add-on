import bpy

try:
    from ...core.log import get_logger
except ImportError:
    import logging

    def get_logger(name):
        return logging.getLogger(f"i_scene_cp77_gltf.user_scripts.{name}")


_LOG = get_logger(__name__)


def get_coll():

    return bpy.context.collection


def format_i(index):

    return f"{index:02d}"


def rename_meshes(collection):
    if collection:
        mesh = [obj for obj in collection.objects if obj.type == "MESH"]

        for index, mesh in enumerate(mesh):
            formatted_index = format_i(index)
            new_name = f"submesh_{formatted_index}_LOD_1"
            mesh.name = new_name
            _LOG.info("Renamed %s", mesh.name)


coll = get_coll()


rename_meshes(coll)
