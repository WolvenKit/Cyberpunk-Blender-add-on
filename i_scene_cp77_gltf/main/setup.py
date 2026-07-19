import hashlib
import json
import os
import sys

import bpy

from .material_registry import DECAL_REGISTRY, REGISTRY
from ..material_types.unknown import unknownMaterial

_MATERIAL_CACHE = {}


def _set_hashed_render_method(material):
    if hasattr(material, "surface_render_method"):
        try:
            material.surface_render_method = "DITHERED"
            return
        except (TypeError, ValueError):
            pass
    if hasattr(material, "blend_method"):
        try:
            material.blend_method = "HASHED"
        except (TypeError, ValueError):
            pass


def _context_path_key(path):
    if not path:
        return ''
    return os.path.normcase(os.path.abspath(os.path.normpath(str(path))))


def _cached_material(signature):
    material = _MATERIAL_CACHE.get(signature)
    if material is None:
        return None
    try:
        if bpy.data.materials.get(material.name) is material:
            return material
    except ReferenceError:
        pass
    _MATERIAL_CACHE.pop(signature, None)
    return None


def clear_material_cache():
    _MATERIAL_CACHE.clear()


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class MaterialBuilder:
    def __init__(self, obj, BasePath, image_format, MeshPath):
        self.BasePath = BasePath
        self.image_format = image_format
        self.obj = obj
        self.MeshPath = MeshPath
        before, mid, after = MeshPath.partition('source\\raw\\'.replace('\\', os.sep))
        self.ProjPath = before + mid
        self.addon_module = sys.modules["i_scene_cp77_gltf"]
        self.addon_ver = self.addon_module.bl_info['version']
        self._signature_cache = {}

    def material_signature(self, raw_material):
        cache_key = id(raw_material)
        signature = self._signature_cache.get(cache_key)
        if signature is not None:
            return signature

        try:
            experimental = bool(
                    bpy.context.preferences.addons[__name__.split('.')[0]].preferences.experimental_features
                    )
        except Exception:
            experimental = False

        payload = {
            'material': raw_material,
            'base_path': _context_path_key(self.BasePath),
            'project_path': _context_path_key(self.ProjPath),
            'mesh_path': _context_path_key(self.MeshPath),
            'image_format': str(self.image_format).lower(),
            'blender_version': tuple(bpy.app.version),
            'addon_version': tuple(self.addon_ver),
            'experimental_features': experimental,
            }
        encoded = json.dumps(
                payload,
                sort_keys=True,
                separators=(',', ':'),
                ensure_ascii=False,
                ).encode('utf-8')
        signature = hashlib.blake2b(encoded, digest_size=20).hexdigest()
        self._signature_cache[cache_key] = signature
        return signature

    def _ensure_nodes(self, bpyMat):
        bpyMat.use_nodes = True
        nodes = bpyMat.node_tree.nodes
        if len(nodes) != 0:
            return
        output = nodes.new('ShaderNodeOutputMaterial')
        output.location = (400, 0)
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bpyMat.node_tree.links.new(output.inputs['Surface'], bsdf.outputs['BSDF'])

    def _new_material(self, name):
        bpyMat = bpy.data.materials.new(name)
        self._ensure_nodes(bpyMat)
        return bpyMat

    def _archive_material_name(self):
        archive_name = self.obj.get("Header", {}).get("ArchiveFileName")
        return os.path.basename(archive_name) if archive_name else 'decal_material'

    def _base_material_path(self, data_chunk):
        base_material = data_chunk.get("baseMaterial") if isinstance(data_chunk, dict) else None
        depot_path = base_material.get("DepotPath") if isinstance(base_material, dict) else None
        return depot_path.get('$value') if isinstance(depot_path, dict) else None

    def _route_material(self, template_path, factory_data, create_data, bpyMat, registry, *, is_decal=False):
        rule = registry.resolve(template_path)
        if not rule:
            label = 'decal' if is_decal else 'mt'
            print(f'{bcolors.WARNING}Unhandled {label} - {template_path}{bcolors.ENDC}')
            _set_hashed_render_method(bpyMat)
            if not is_decal:
                bpyMat['no_shadows'] = False
            return False

        instance = rule.factory(self, factory_data)
        instance.create(create_data, bpyMat)
        if not rule.preserve_render_method:
            _set_hashed_render_method(bpyMat)
        if not is_decal:
            bpyMat['no_shadows'] = rule.no_shadows
        return True

    def create(self, mats, materialIndex):
        if not mats:
            return self.createdecal(materialIndex)

        rawMat = mats[materialIndex]
        signature = self.material_signature(rawMat)
        cached = _cached_material(signature)
        if cached is not None:
            return cached

        bpyMat = self._new_material(rawMat["Name"])
        bpyMat['MeshPath'] = self.MeshPath
        bpyMat['DepotPath'] = self.BasePath
        bpyMat['ProjPath'] = self.ProjPath
        bpyMat['MaterialTemplate'] = rawMat["MaterialTemplate"]
        bpyMat['AddonVersion'] = self.addon_ver

        material_template = rawMat["MaterialTemplate"]
        if self._route_material(material_template, rawMat, rawMat["Data"], bpyMat, REGISTRY):
            _MATERIAL_CACHE[signature] = bpyMat
            return bpyMat

        context = bpy.context
        if context.preferences.addons[__name__.split('.')[0]].preferences.experimental_features:
            unknown = unknownMaterial(self.BasePath, self.image_format, self.ProjPath)
            unknown.create(rawMat["Data"], bpyMat)

        _set_hashed_render_method(bpyMat)
        bpyMat['no_shadows'] = False
        _MATERIAL_CACHE[signature] = bpyMat
        return bpyMat

    def createdecal(self, materialIndex):
        root = self.obj.get("Data", {}).get("RootChunk", {})
        if not root.get("baseMaterial"):
            return None

        bpyMat = self._new_material(self._archive_material_name())
        base_path = self._base_material_path(root)
        if base_path:
            self._route_material(base_path, root, root, bpyMat, DECAL_REGISTRY, is_decal=True)
        else:
            print(f'{bcolors.WARNING}Unhandled decal - missing baseMaterial DepotPath{bcolors.ENDC}')
            _set_hashed_render_method(bpyMat)
        return bpyMat
