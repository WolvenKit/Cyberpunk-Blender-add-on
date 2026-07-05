import sys
import bpy
import os
import math
import zipfile
from bpy.types import EnumProperty
from mathutils import Color
import pkg_resources
import bmesh
import inspect
from mathutils import Vector
import json
scale_factor=1.0
from typing import Literal, get_args

class GLTFExclusionCache:
    """Manages the caching and retrieval of objects designated for exclusion from glTF I/O."""
    
    def __init__(self):
        """Initializes the cache state and timestamp."""
        self._excluded_objects_cache = None
        self._excluded_cache_timestamp = 0

    def get_excluded_objects(self):
        """Retrieves a cached set of excluded objects, updating the cache if the scene frame has changed."""
        current_time = bpy.context.scene.frame_current

        if self._excluded_objects_cache is None or current_time != self._excluded_cache_timestamp: 
            self._excluded_objects_cache = set()
            
            if "glTF_not_exported" in bpy.data.collections:
                not_exported_coll = bpy.data.collections["glTF_not_exported"]
                self._excluded_objects_cache = self._get_all_objects_recursive(not_exported_coll)
                
            self._excluded_cache_timestamp = current_time #TODO: probably just remove this, the timestamp is useless

        return self._excluded_objects_cache

    def _get_all_objects_recursive(self, coll):
        """Recursively aggregates objects from a specified collection and its nested children."""
        objects = set(coll.objects)
        for child in coll.children:
            objects.update(self._get_all_objects_recursive(child))
        return objects

    def clear_cache(self):
        """Resets the cache data and its associated timestamp."""
        self._excluded_objects_cache = None
        self._excluded_cache_timestamp = 0

# IMPORT THIS FOR USE, NOT THE CLASS 
exclusion_cache = GLTFExclusionCache()


def found(self,tex):
    result = os.path.exists(os.path.join(self.BasePath, tex)[:-3]+ self.image_format)
    if not result:
        result = os.path.exists(os.path.join(self.ProjPath, tex)[:-3]+ self.image_format)
        if not result:
            print(f"Texture not found: {tex}")
    return result

def load_zip(path):
    with zipfile.ZipFile(path, "r") as z:
        filename=z.namelist()[0]
        print(filename)
        with z.open(filename) as f:
            data = f.read()
    return data

# Function to dynamically gather classes defined in the same file
def get_classes(module):
    operators = set()
    other_classes = set()

    # Collect classes in the specified module
    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj) and obj.__module__ == module.__name__:
            if issubclass(obj, bpy.types.Operator):
                operators.add(obj)
            else:
                other_classes.add(obj)

    # Convert the sets to lists and sort the collected classes by name
    sorted_operators = sorted(list(operators), key=lambda cls: cls.__name__)
    sorted_other_classes = sorted(list(other_classes), key=lambda cls: cls.__name__)

    return sorted_operators, sorted_other_classes

def _value(data, *names, default=0):
    if not isinstance(data, dict):
        return default
    for name in names:
        if name in data:
            return data[name]
    return default


def _xyz(data, default=0):
    props = data.get('Properties', data) if isinstance(data, dict) else {}
    return [
        _value(props, 'X', 'x', default=default) / scale_factor,
        _value(props, 'Y', 'y', default=default) / scale_factor,
        _value(props, 'Z', 'z', default=default) / scale_factor,
    ]


def _image_format_extension(image_format):
    if not image_format:
        return ''
    return image_format if image_format.startswith('.') else f'.{image_format}'


def _with_image_extension(path, image_format):
    ext = _image_format_extension(image_format)
    return f'{path[:-4]}{ext}' if path.lower().endswith('.xbm') else f'{path[:-3]}{image_format}'


def _filepath_key(path):
    if not path:
        return ''
    try:
        path = bpy.path.abspath(path)
    except Exception:
        pass
    return os.path.normcase(os.path.abspath(os.path.normpath(path)))


def _matches_colorspace(image, is_normal):
    non_color = image.colorspace_settings.name == 'Non-Color'
    return non_color if is_normal else not non_color


_image_lookup_cache = {}
_asset_index_cache = {}


def _find_loaded_image(filepath, is_normal=False):
    key = (_filepath_key(filepath), bool(is_normal))
    cached_name = _image_lookup_cache.get(key)
    if cached_name:
        image = bpy.data.images.get(cached_name)
        if image and _filepath_key(image.filepath) == key[0] and _matches_colorspace(image, is_normal):
            return image

    image = next((img for img in bpy.data.images if _filepath_key(img.filepath) == key[0] and _matches_colorspace(img, is_normal)), None)
    if image:
        _image_lookup_cache[key] = image.name
    return image


def _resolve_indexed_image(reference, root, image_format):
    if not reference or not root:
        return None
    try:
        from .datakrash import DepotAssetIndex
    except Exception:
        return None

    ext = _image_format_extension(image_format)
    if not ext:
        return None

    root = os.path.abspath(os.path.normpath(root.replace('\\', os.sep)))
    cache_key = (root, ext.lower())
    index = _asset_index_cache.get(cache_key)
    if index is None:
        try:
            index = DepotAssetIndex.cached(root, extensions=(ext,), warn_missing=False)
        except Exception:
            return None
        _asset_index_cache[cache_key] = index

    local_reference = reference.replace('\\', os.sep).replace('/', os.sep)
    indexed_reference = _with_image_extension(local_reference, image_format)
    try:
        return index.resolve_expected(indexed_reference, ext, warn=False)
    except Exception:
        return None


def _new_file_image(name, filepath, is_normal=False):
    image = bpy.data.images.new(name, 1, 1)
    image.source = 'FILE'
    image.alpha_mode = 'CHANNEL_PACKED'
    image.filepath = filepath
    if is_normal:
        image.colorspace_settings.name = 'Non-Color'
    _image_lookup_cache[(_filepath_key(filepath), bool(is_normal))] = image.name
    return image


def clear_image_lookup_cache():
    _image_lookup_cache.clear()
    _asset_index_cache.clear()


def get_pos(inst):
    pos_data = inst.get('Position') or inst.get('position') or inst.get('translation') or inst.get('Translation')
    if not isinstance(pos_data, dict):
        return [0, 0, 0]

    if pos_data.get('$type') == 'WorldPosition':
        return [
            _value(pos_data.get('x'), 'Bits') / 131072 * scale_factor,
            _value(pos_data.get('y'), 'Bits') / 131072 * scale_factor,
            _value(pos_data.get('z'), 'Bits') / 131072 * scale_factor,
        ]

    return _xyz(pos_data)


def get_rot(inst):
    rot_data = inst.get('Orientation') or inst.get('orientation') or inst.get('Rotation') or inst.get('rotation')
    if not isinstance(rot_data, dict):
        return [1, 0, 0, 0]

    props = rot_data.get('Properties', rot_data)
    if 'r' in props:
        return [
            _value(props, 'r', default=1),
            _value(props, 'i'),
            _value(props, 'j'),
            _value(props, 'k'),
        ]

    return [
        _value(props, 'W', 'w', default=1),
        _value(props, 'X', 'x'),
        _value(props, 'Y', 'y'),
        _value(props, 'Z', 'z'),
    ]


def get_scale(inst):
    scale_data = inst.get('Scale') or inst.get('scale')
    if not isinstance(scale_data, dict):
        return [0, 0, 0]
    return _xyz(scale_data)

def loc(nodename):
    return bpy.app.translations.pgettext(nodename)

def get_plugin_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_resources_dir():
    plugin_dir = get_plugin_dir()
    return os.path.join(plugin_dir, "resources")

def get_icon_dir():
    plugin_dir = get_plugin_dir()
    return os.path.join(plugin_dir, "icons")

def get_refit_dir():
    resources_dir = get_resources_dir()
    return os.path.join(resources_dir, "refitters")

def get_char_dir():
    resources_dir = get_resources_dir()
    return os.path.join(resources_dir, "characters")

def get_script_dir():
    resources_dir = get_resources_dir()
    return os.path.join(resources_dir, "scripts")

def get_rig_dir():
    resources_dir = get_resources_dir()
    return os.path.join(resources_dir, "rigs")

def get_inputs(tree):
    vers=bpy.app.version
    if vers[0]<4:
        return tree.inputs
    else:
        return ([x for x in tree.interface.items_tree if (x.item_type == 'SOCKET' and x.in_out == 'INPUT')])


def get_outputs(tree):
    vers=bpy.app.version
    if vers[0]<4:
        return tree.outputs
    else:
        return ([x for x in tree.interface.items_tree if (x.item_type == 'SOCKET' and x.in_out == 'OUTPUT')])

def bsdf_socket_names():
    socket_names={}
    vers=bpy.app.version
    if vers[0]<4:
        socket_names['Subsurface']= 'Subsurface'
        socket_names['Subsurface Color']= 'Subsurface Color'
        socket_names['Specular']= 'Specular'
        socket_names['Transmission']= 'Transmission'
        socket_names['Coat']= 'Coat'
        socket_names['Sheen']= 'Sheen'
        socket_names['Emission']= 'Emission'
    else:
        socket_names['Subsurface Color']= 'Base Color'
        socket_names['Subsurface']= 'Subsurface Weight'
        socket_names['Specular']= 'Specular IOR Level'
        socket_names['Transmission']= 'Transmission Weight'
        socket_names['Coat']= 'Coat Weight'
        socket_names['Sheen']= 'Sheen Weight'
        socket_names['Emission']= 'Emission Color'
    return socket_names


def imageFromPath(Img,image_format,isNormal = False):
    filepath = _with_image_extension(Img, image_format)
    image = _find_loaded_image(filepath, isNormal)
    if image:
        return image

    return _new_file_image(os.path.basename(Img)[:-4], filepath, isNormal)


def imageFromRelPath(ImgPath, image_format='png', isNormal = False, DepotPath='',ProjPath=''):
    DepotPath=DepotPath.replace('\\',os.sep)
    ProjPath=ProjPath.replace('\\',os.sep)
    if isinstance(ImgPath, float):
        print(f"refusing to process unresolved relative image path {ImgPath}")
        return
    if isinstance(ProjPath, float):
        print(f"refusing to process unresolved project path {ProjPath}")
        return

    inProj = _with_image_extension(os.path.join(ProjPath, ImgPath), image_format)
    inDepot = _with_image_extension(os.path.join(DepotPath, ImgPath), image_format)

    image = _find_loaded_image(inProj, isNormal) or _find_loaded_image(inDepot, isNormal)
    if image:
        return image

    resolved = _resolve_indexed_image(ImgPath, ProjPath, image_format) or _resolve_indexed_image(ImgPath, DepotPath, image_format)
    if not resolved:
        resolved = inProj if os.path.exists(inProj) else inDepot

    return _new_file_image(os.path.basename(ImgPath)[:-4], resolved, isNormal)

def CreateShaderNodeTexImage(curMat,path = None, x = 0, y = 0, name = None, image_format = 'png', nonCol = False):
    ImgNode = curMat.nodes.new("ShaderNodeTexImage")
    ImgNode.location = (x, y)
    ImgNode.hide = True
    if name:
        ImgNode.label = name
    if path:
        Img = imageFromPath(path,image_format,nonCol)
        ImgNode.image = Img

    return ImgNode

def CreateCullBackfaceGroup(curMat, x = 0, y = 0,name = 'Cull Backface'):
    group = bpy.data.node_groups.get("Cull Backface")

    if group is None:
        group = bpy.data.node_groups.new("Cull Backface","ShaderNodeTree")

        GroupInN = group.nodes.new("NodeGroupInput")
        GroupInN.location = (-1000,0)

        GroupOutN = group.nodes.new("NodeGroupOutput")
        GroupOutN.location = (0,0)
        vers=bpy.app.version
        if vers[0]<4:
            input_socket = group.inputs.new('NodeSocketFloat','Input')
            output_socket = group.outputs.new('NodeSocketFloat','Output')
        else:
            input_socket = group.interface.new_socket(name="Input",socket_type='NodeSocketFloat', in_out='INPUT')
            output_socket = group.interface.new_socket(name="Output",socket_type='NodeSocketFloat', in_out='OUTPUT')

        input_socket.default_value = 1.0

        GeometryNode = group.nodes.new("ShaderNodeNewGeometry")
        GeometryNode.location = (-750,-300)

        OneMinusNode = group.nodes.new("ShaderNodeMath")
        OneMinusNode.location = (-500,-300)
        OneMinusNode.operation = 'SUBTRACT'
        OneMinusNode.inputs[0].default_value = 1.0

        MultiplyNode = group.nodes.new("ShaderNodeMath")
        MultiplyNode.operation = 'MULTIPLY'
        MultiplyNode.location = (-250,0)

        group.links.new(GroupInN.outputs[0],MultiplyNode.inputs[0])
        group.links.new(GeometryNode.outputs[6],OneMinusNode.inputs[1])
        group.links.new(OneMinusNode.outputs[0],MultiplyNode.inputs[1])
        group.links.new(MultiplyNode.outputs[0],GroupOutN.inputs[0])

    ShaderGroup = curMat.nodes.new("ShaderNodeGroup")
    ShaderGroup.location = (x,y)
    ShaderGroup.hide = True
    ShaderGroup.node_tree = group
    ShaderGroup.name = name

    return ShaderGroup


def CreateRebildNormalGroup(curMat, x = 0, y = 0,name = 'Rebuild Normal Z'):
    group = bpy.data.node_groups.get("Rebuild Normal Z")

    if group is None:
        group = bpy.data.node_groups.new("Rebuild Normal Z","ShaderNodeTree")

        GroupInN = group.nodes.new("NodeGroupInput")
        GroupInN.location = (-1400,0)

        GroupOutN = group.nodes.new("NodeGroupOutput")
        GroupOutN.location = (200,0)
        vers=bpy.app.version
        if vers[0]<4:
            group.inputs.new('NodeSocketColor','Image')
            group.outputs.new('NodeSocketColor','Image')
        else:
            group.interface.new_socket(name="Image", socket_type='NodeSocketColor', in_out='OUTPUT')
            group.interface.new_socket(name="Image",socket_type='NodeSocketColor', in_out='INPUT')

        VMup = group.nodes.new("ShaderNodeVectorMath")
        VMup.location = (-1200,-200)
        VMup.operation = 'MULTIPLY'
        VMup.inputs[1].default_value[0] = 2.0
        VMup.inputs[1].default_value[1] = 2.0

        VSub = group.nodes.new("ShaderNodeVectorMath")
        VSub.location = (-1000,-200)
        VSub.operation = 'SUBTRACT'
        VSub.name = 'NormalSubtract'
        VSub.inputs[1].default_value[0] = 1.0
        VSub.inputs[1].default_value[1] = 1.0

        VDot = group.nodes.new("ShaderNodeVectorMath")
        VDot.location = (-800,-200)
        VDot.operation = 'DOT_PRODUCT'

        Sub = group.nodes.new("ShaderNodeMath")
        Sub.location = (-600,-200)
        Sub.operation = 'SUBTRACT'
        group.links.new(VDot.outputs[0],Sub.inputs[1])
        Sub.inputs[0].default_value = 1.020

        SQR = group.nodes.new("ShaderNodeMath")
        SQR.location = (-400,-200)
        SQR.operation = 'SQRT'

        Range = group.nodes.new("ShaderNodeMapRange")
        Range.location = (-200,-200)
        Range.clamp = True
        Range.inputs[1].default_value = -1.0

        Sep = group.nodes.new("ShaderNodeSeparateColor")
        Sep.mode = 'RGB'
        Sep.location = (-600,0)
        Comb = group.nodes.new("ShaderNodeCombineColor")
        Comb.mode= 'RGB'
        Comb.location = (-300,0)

        RGBCurvesConvert = group.nodes.new("ShaderNodeRGBCurve")
        RGBCurvesConvert.label = "Convert DX to OpenGL Normal"
        RGBCurvesConvert.hide = True
        RGBCurvesConvert.location = (-100,0)
        RGBCurvesConvert.mapping.curves[1].points[0].location = (0,1)
        RGBCurvesConvert.mapping.curves[1].points[1].location = (1,0)

        group.links.new(GroupInN.outputs[0],VMup.inputs[0])
        group.links.new(VMup.outputs[0],VSub.inputs[0])
        group.links.new(VSub.outputs[0],VDot.inputs[0])
        group.links.new(VSub.outputs[0],VDot.inputs[1])
        group.links.new(VDot.outputs["Value"],Sub.inputs[1])
        group.links.new(Sub.outputs[0],SQR.inputs[0])
        group.links.new(SQR.outputs[0],Range.inputs[0])
        group.links.new(GroupInN.outputs[0],Sep.inputs[0])
        group.links.new(Sep.outputs[0],Comb.inputs[0])
        group.links.new(Sep.outputs[1],Comb.inputs[1])
        group.links.new(Range.outputs[0],Comb.inputs[2])
        group.links.new(Comb.outputs[0],RGBCurvesConvert.inputs[1])
        group.links.new(RGBCurvesConvert.outputs[0],GroupOutN.inputs[0])

    ShaderGroup = curMat.nodes.new("ShaderNodeGroup")
    ShaderGroup.location = (x,y)
    ShaderGroup.hide = True
    ShaderGroup.node_tree = group
    ShaderGroup.name = name

    return ShaderGroup

def CreateCalculateVecNormalZ(curMat, x = 0, y = 0,name = 'Calculate Vectorized Normal Z'):
    group = bpy.data.node_groups.get("Calculate Vectorized Normal Z")

    if group is None:
        group = bpy.data.node_groups.new("Calculate Vectorized Normal Z","ShaderNodeTree")

        GroupInN = group.nodes.new("NodeGroupInput")
        GroupInN.location = (-1400,0)

        GroupOutN = group.nodes.new("NodeGroupOutput")
        GroupOutN.location = (300,0)
        vers=bpy.app.version
        if vers[0]<4:
            group.inputs.new('NodeSocketVector','Image')
            group.outputs.new('NodeSocketColor','Image')
        else:
            group.interface.new_socket(name="Image",socket_type='NodeSocketVector', in_out='INPUT')
            group.interface.new_socket(name="Image",socket_type='NodeSocketColor', in_out='OUTPUT')

        VDot = group.nodes.new("ShaderNodeVectorMath")
        VDot.location = (-900,-200)
        VDot.operation = 'DOT_PRODUCT'

        Sub = group.nodes.new("ShaderNodeMath")
        Sub.location = (-700,-200)
        Sub.operation = 'SUBTRACT'
        group.links.new(VDot.outputs[0],Sub.inputs[1])
        Sub.inputs[0].default_value = 1.0

        SQR = group.nodes.new("ShaderNodeMath")
        SQR.location = (-500,-200)
        SQR.operation = 'SQRT'

        Sep = group.nodes.new("ShaderNodeSeparateColor")
        Sep.location = (-700,100)

        Mult = group.nodes.new("ShaderNodeMath")
        Mult.operation = 'MULTIPLY'
        Mult.location = (-500,0)
        Mult.label = "OpenGL to DX"
        Mult.inputs[1].default_value = -1.0

        Comb = group.nodes.new("ShaderNodeCombineColor")
        Comb.location = (-300,100)

        MultAdd = group.nodes.new("ShaderNodeVectorMath")
        MultAdd.location = (-50, 0)
        MultAdd.operation = "MULTIPLY_ADD"
        MultAdd.inputs[1].default_value = 0.5, 0.5, 0.5
        MultAdd.inputs[2].default_value = 0.5, 0.5, 0.5

        group.links.new(GroupInN.outputs[0],Sep.inputs[0])
        group.links.new(GroupInN.outputs[0],VDot.inputs[0])
        group.links.new(GroupInN.outputs[0],VDot.inputs[1])
        group.links.new(VDot.outputs["Value"],Sub.inputs[1])
        group.links.new(Sub.outputs[0],SQR.inputs[0])
        group.links.new(SQR.outputs[0],Comb.inputs[2])
        group.links.new(Sep.outputs[0],Comb.inputs[0])
        group.links.new(Sep.outputs[1],Mult.inputs[0])
        group.links.new(Mult.outputs[0],Comb.inputs[1])
        group.links.new(Comb.outputs[0],MultAdd.inputs[0])
        group.links.new(MultAdd.outputs[0],GroupOutN.inputs[0])

    ShaderGroup = curMat.nodes.new("ShaderNodeGroup")
    ShaderGroup.location = (x,y)
    ShaderGroup.hide = True
    ShaderGroup.node_tree = group
    ShaderGroup.name = name

    return ShaderGroup

def CreateShaderNodeNormalMap(curMat,path = None, x = 0, y = 0, name = None,image_format = 'png', nonCol = True):
    nMap = curMat.nodes.new("ShaderNodeNormalMap")
    nMap.location = (x,y)
    nMap.hide = True

    if path is not None:
        ImgNode = curMat.nodes.new("ShaderNodeTexImage")
        ImgNode.location = (x - 400, y)
        ImgNode.hide = True
        if name is not None:
            ImgNode.label = name
        Img = imageFromPath(path,image_format,nonCol)
        ImgNode.image = Img

        NormalRebuildGroup = CreateRebildNormalGroup(curMat, x - 150, y, name + ' Rebuilt')

        curMat.links.new(ImgNode.outputs[0],NormalRebuildGroup.inputs[0])
        curMat.links.new(NormalRebuildGroup.outputs[0],nMap.inputs[1])

    return nMap

def CreateShaderNodeGlobalNormalMap(curMat,path = None, x = 0, y = 0, name = None,image_format = 'png', nonCol = True):
    if path is not None:
        ImgNode = curMat.nodes.new("ShaderNodeTexImage")
        ImgNode.location = (x - 450, y)
        ImgNode.width = 350
        ImgNode.hide = False
        Img = imageFromPath(path,image_format,nonCol)
        ImgNode.image = Img
    return ImgNode

def CreateShaderNodeVectorizedNormalMap(curMat,path = None, x = 0, y = 0, name = None,image_format = 'png', nonCol = True):
    normalVectorize = curMat.nodes.new("ShaderNodeVectorMath")
    normalVectorize.operation='MULTIPLY_ADD'
    normalVectorize.location = (x,y)
    normalVectorize.hide = True
    normalVectorize.inputs[1].default_value = 2, 2, 0
    normalVectorize.inputs[2].default_value = -1, -1, 0

    if path is not None:
        ImgNode = curMat.nodes.new("ShaderNodeTexImage")
        ImgNode.location = (x - 450, y)
        ImgNode.width = 350
        ImgNode.hide = False
        Img = imageFromPath(path,image_format,nonCol)
        ImgNode.image = Img

        curMat.links.new(ImgNode.outputs[0],normalVectorize.inputs[0])

    return normalVectorize


def image_has_alpha(img):
    b = 32 if img.is_float else 8
    return (
        img.depth == 2*b or   # Grayscale+Alpha
        img.depth == 4*b      # RGB+Alpha
    )

def CreateShaderNodeRGB(curMat, color,x = 0, y = 0,name = None, isVector = False):
    rgbNode = curMat.nodes.new("ShaderNodeRGB")
    rgbNode.location = (x, y)
    rgbNode.hide = True
    if name is not None:
        rgbNode.label = name

    if isVector:
        rgbNode.outputs[0].default_value = (float(color["X"]),float(color["Y"]),float(color["Z"]),float(color["W"]))
    else:
        rgbNode.outputs[0].default_value = (float(color["Red"])/255,float(color["Green"])/255,float(color["Blue"])/255,float(color["Alpha"])/255)

    return rgbNode

def CreateShaderNodeValue(curMat, value = 0,x = 0, y = 0,name = None):
    valNode = curMat.nodes.new("ShaderNodeValue")
    valNode.location = (x,y)
    valNode.outputs[0].default_value = float(value)
    valNode.hide = True
    if name :
        valNode.label = name

    return valNode

def crop_image(orig_img,outname, cropped_min_x, cropped_max_x, cropped_min_y, cropped_max_y):
    '''Crops an image object of type <class 'bpy.types.Image'>.  For example, for a 10x10 image,
    if you put cropped_min_x = 2 and cropped_max_x = 6,
    you would get back a cropped image with width 4, and
    pixels ranging from the 2 to 5 in the x-coordinate
    Note: here y increasing as you down the image.  So,
    if cropped_min_x and cropped_min_y are both zero,
    you'll get the top-left of the image (as in GIMP).
    Returns: An image of type  <class 'bpy.types.Image'>
    '''

    num_channels=orig_img.channels
    #calculate cropped image size
    cropped_size_x = cropped_max_x - cropped_min_x
    cropped_size_y = cropped_max_y - cropped_min_y
    #original image size
    orig_size_x = orig_img.size[0]
    orig_size_y = orig_img.size[1]

    cropped_img = bpy.data.images.new(name=outname, width=cropped_size_x, height=cropped_size_y)

    print("Exctracting image fragment, this could take a while...")

    #loop through each row of the cropped image grabbing the appropriate pixels from original
    #the reason for the strange limits is because of the
    #order that Blender puts pixels into a 1-D array.
    current_cropped_row = 0
    for yy in range(orig_size_y - cropped_max_y, orig_size_y - cropped_min_y):
        #the index we start at for copying this row of pixels from the original image
        orig_start_index = (cropped_min_x + yy*orig_size_x) * num_channels
        #and to know where to stop we add the amount of pixels we must copy
        orig_end_index = orig_start_index + (cropped_size_x * num_channels)
        #the index we start at for the cropped image
        cropped_start_index = (current_cropped_row * cropped_size_x) * num_channels
        cropped_end_index = cropped_start_index + (cropped_size_x * num_channels)

        #copy over pixels
        cropped_img.pixels[cropped_start_index : cropped_end_index] = orig_img.pixels[orig_start_index : orig_end_index]

        #move to the next row before restarting loop
        current_cropped_row += 1

    return cropped_img

def create_node(NG, type, loc, hide=True, operation=None, image=None, label=None, blend_type=None):
    Node=NG.new(type)
    Node.hide = hide
    Node.location = loc
    if operation:
        Node.operation=operation
    if image:
        Node.image=image
    if label:
        Node.label=label
    if blend_type:
        Node.blend_type=blend_type
    return Node

def createOverrideTable(matTemplateObj):
        OverList = matTemplateObj["overrides"]
        if OverList is None:
            OverList = matTemplateObj.get("Overrides")
        Output = {}
        Output["ColorScale"] = {}
        Output["NormalStrength"] = {}
        Output["RoughLevelsIn"] = {}
        Output["RoughLevelsOut"] = {}
        Output["MetalLevelsIn"] = {}
        Output["MetalLevelsOut"] = {}
        for x in OverList["colorScale"]:
            tmpName = x["n"]["$value"]
            tmpR = float(x["v"]["Elements"][0])
            tmpG = float(x["v"]["Elements"][1])
            tmpB = float(x["v"]["Elements"][2])
            Output["ColorScale"][tmpName] = (tmpR,tmpG,tmpB,1)
        for x in OverList["normalStrength"]:
            tmpName = x["n"]["$value"]
            tmpStrength = 0
            if x.get("v") is not None:
                tmpStrength = float(x["v"])
            Output["NormalStrength"][tmpName] = tmpStrength
        for x in OverList["roughLevelsIn"]:
            tmpName = x["n"]["$value"]
            tmpStrength0 = float(x["v"]["Elements"][0])
            tmpStrength1 = float(x["v"]["Elements"][1])
            Output["RoughLevelsIn"][tmpName] = [(tmpStrength0),(tmpStrength1)]
        for x in OverList["roughLevelsOut"]:
            tmpName = x["n"]["$value"]
            tmpStrength0 = float(x["v"]["Elements"][0])
            tmpStrength1 = float(x["v"]["Elements"][1])
            Output["RoughLevelsOut"][tmpName] = [(tmpStrength0),(tmpStrength1)]
        for x in OverList["metalLevelsIn"]:
            tmpName = x["n"]["$value"]
            if x.get("v") is not None:
                tmpStrength0 = float(x["v"]["Elements"][0])
                tmpStrength1 = float(x["v"]["Elements"][1])
            else:
                tmpStrength0 = 0
                tmpStrength1 = 1
            Output["MetalLevelsIn"][tmpName] = [(tmpStrength0),(tmpStrength1)]
        for x in OverList["metalLevelsOut"]:
            tmpName = x["n"]["$value"]
            if x.get("v") is not None:
                tmpStrength0 = float(x["v"]["Elements"][0])
                tmpStrength1 = float(x["v"]["Elements"][1])
            else:
                tmpStrength0 = 0
                tmpStrength1 = 1
            Output["MetalLevelsOut"][tmpName] = [(tmpStrength0),(tmpStrength1)]
        return Output

def createParallaxGroup():
    CurMat = bpy.data.node_groups.get('CP77_Parallax')
    if CurMat:
        return CurMat
    else:
        CurMat = bpy.data.node_groups.new('CP77_Parallax', 'ShaderNodeTree')
        vers=bpy.app.version
        if vers[0]<4:
            CurMat.outputs.new('NodeSocketVector','Vector' )
            CurMat.inputs.new('NodeSocketFloat','Distance' )
        else:
            CurMat.interface.new_socket(name="Vector", socket_type='NodeSocketVector', in_out='OUTPUT')
            CurMat.interface.new_socket(name="Distance",socket_type='NodeSocketFloat', in_out='INPUT')
        GroupOutput = create_node(CurMat.nodes,"NodeGroupOutput",(771.574462890625, 0.0), label="Group Output")
        Tangent = create_node(CurMat.nodes,"ShaderNodeTangent",(-565., -136.), label="Tangent")
        Tangent.direction_type='UV_MAP'
        VectorMath = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-566., -342.), operation='CROSS_PRODUCT', label="Vector Math")
        VectorMath002 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-227., -208.), operation='DOT_PRODUCT', label="Vector Math.002")
        VectorMath004 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(361., 34.), operation='SCALE', label="Vector Math.004")
        VectorMath005 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(581., 123.), operation='SUBTRACT', label="Vector Math.005")
        UVMap = create_node(CurMat.nodes,"ShaderNodeUVMap",(299., 342.), label="UV Map")
        VectorMath001 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-248., 37.), operation='DOT_PRODUCT', label="Vector Math.001")
        VectorMath006 = create_node(CurMat.nodes,"ShaderNodeVectorMath",(-95., 332.), operation='DOT_PRODUCT', label="Vector Math.006")
        Geometry = create_node(CurMat.nodes,"ShaderNodeNewGeometry",(-581., 222.), label="Geometry")
        Math = create_node(CurMat.nodes,"ShaderNodeMath",(159., -230.), operation='DIVIDE', label="Math")
        CombineXYZ = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",(-13., 31.), label="Combine XYZ")
        GroupInput = create_node(CurMat.nodes,"NodeGroupInput",(-781., 0.0), label="Group Input")
        CurMat.links.new(VectorMath005.outputs['Vector'], GroupOutput.inputs[0])
        CurMat.links.new(Geometry.outputs['Normal'], VectorMath.inputs[0])
        CurMat.links.new(Tangent.outputs['Tangent'], VectorMath.inputs[1])
        CurMat.links.new(Geometry.outputs['Incoming'], VectorMath002.inputs[0])
        CurMat.links.new(VectorMath.outputs['Vector'], VectorMath002.inputs[1])
        CurMat.links.new(CombineXYZ.outputs['Vector'], VectorMath004.inputs[0])
        CurMat.links.new(Math.outputs['Value'], VectorMath004.inputs[3])
        CurMat.links.new(UVMap.outputs['UV'], VectorMath005.inputs[0])
        CurMat.links.new(VectorMath004.outputs['Vector'], VectorMath005.inputs[1])
        CurMat.links.new(Geometry.outputs['Incoming'], VectorMath001.inputs[0])
        CurMat.links.new(Tangent.outputs['Tangent'], VectorMath001.inputs[1])
        CurMat.links.new(Geometry.outputs['Incoming'], VectorMath006.inputs[0])
        CurMat.links.new(Geometry.outputs['Normal'], VectorMath006.inputs[1])
        CurMat.links.new(GroupInput.outputs['Distance'], Math.inputs[0])
        CurMat.links.new(VectorMath006.outputs['Value'], Math.inputs[1])
        CurMat.links.new(VectorMath001.outputs['Value'], CombineXYZ.inputs[0])
        CurMat.links.new(VectorMath002.outputs['Value'], CombineXYZ.inputs[1])
        return CurMat


def CreateGradMapRamp(CurMat, grad_image_node, location=(-400, 250)):
    image = grad_image_node.image
    image_width = image.size[0]
    row_index = 0
    all_pixels = tuple(image.pixels)

    color_ramp_node = CurMat.nodes.new('ShaderNodeValToRGB')
    color_ramp_node.location = location

    step = math.ceil(image_width / 32) if image_width > 32 else 1
    color_ramp_node.color_ramp.elements.remove(color_ramp_node.color_ramp.elements[1])

    first = True
    for i in range(0, image_width, step):
        idx = (row_index * image_width + i) * 4
        r, g, b, a = all_pixels[idx:idx + 4]
        element = color_ramp_node.color_ramp.elements[0] if first else color_ramp_node.color_ramp.elements.new(i / image_width)
        element.color = (r, g, b, a)
        element.position = i / image_width
        first = False

    color_ramp_node.color_ramp.interpolation = 'CONSTANT'
    return color_ramp_node

def createLerpGroup():
    CurMat = bpy.data.node_groups.get('lerp')
    if CurMat:
        return CurMat
    else:
        CurMat = bpy.data.node_groups.new('lerp', 'ShaderNodeTree')
        vers=bpy.app.version
        if vers[0]<4:
            CurMat.inputs.new('NodeSocketFloat','A' )
            CurMat.inputs.new('NodeSocketFloat','B' )
            CurMat.inputs.new('NodeSocketFloat','t' )
            CurMat.outputs.new('NodeSocketFloat','result' )
        else:
            CurMat.interface.new_socket(name="A",socket_type='NodeSocketFloat', in_out='INPUT')
            CurMat.interface.new_socket(name="B",socket_type='NodeSocketFloat', in_out='INPUT')
            CurMat.interface.new_socket(name="t",socket_type='NodeSocketFloat', in_out='INPUT')
            CurMat.interface.new_socket(name="result", socket_type='NodeSocketFloat', in_out='OUTPUT')
        GroupInput = create_node(CurMat.nodes,"NodeGroupInput",(0, 0), label="Group Input")
        GroupOutput = create_node(CurMat.nodes,"NodeGroupOutput",(700, 0), label="Group Output")
        sub = create_node(CurMat.nodes,"ShaderNodeMath", (200,100) , operation = 'SUBTRACT')
        mul = create_node(CurMat.nodes,"ShaderNodeMath", (350,50) , operation = 'MULTIPLY')
        mul2 =create_node(CurMat.nodes,"ShaderNodeMath", (350,-50) , operation = 'MULTIPLY')
        add = create_node(CurMat.nodes,"ShaderNodeMath", (500,0) , operation = 'ADD')
        sub.inputs[0].default_value = 1.0
        CurMat.links.new(GroupInput.outputs[2],sub.inputs[1])
        CurMat.links.new(sub.outputs[0],mul.inputs[0])
        CurMat.links.new(GroupInput.outputs[0],mul.inputs[1])
        CurMat.links.new(GroupInput.outputs[2],mul2.inputs[0])
        CurMat.links.new(GroupInput.outputs[1],mul2.inputs[1])
        CurMat.links.new(GroupInput.outputs[1],mul2.inputs[1])
        CurMat.links.new(mul.outputs[0],add.inputs[0])
        CurMat.links.new(mul2.outputs[0],add.inputs[1])
        CurMat.links.new(add.outputs[0],GroupOutput.inputs[0])
        return CurMat

# (1-t)a+tb for vectors
def createVecLerpGroup():
    CurMat = bpy.data.node_groups.get('vecLerp')
    if CurMat:
        return CurMat
    else:
        CurMat = bpy.data.node_groups.new('vecLerp', 'ShaderNodeTree')
        vers=bpy.app.version
        if vers[0]<4:
            CurMat.inputs.new('NodeSocketVector','A' )
            CurMat.inputs.new('NodeSocketVector','B' )
            CurMat.inputs.new('NodeSocketVector','t' )
            CurMat.outputs.new('NodeSocketVector','result' )
        else:
            CurMat.interface.new_socket(name="A",socket_type='NodeSocketVector', in_out='INPUT')
            CurMat.interface.new_socket(name="B",socket_type='NodeSocketVector', in_out='INPUT')
            CurMat.interface.new_socket(name="t",socket_type='NodeSocketVector', in_out='INPUT')
            CurMat.interface.new_socket(name="result", socket_type='NodeSocketVector', in_out='OUTPUT')
        GroupInput = create_node(CurMat.nodes,"NodeGroupInput",(0, 0), label="Group Input")
        GroupOutput = create_node(CurMat.nodes,"NodeGroupOutput",(700, 0), label="Group Output")
        sub = create_node(CurMat.nodes,"ShaderNodeVectorMath", (200,100) , operation = 'SUBTRACT')
        mul = create_node(CurMat.nodes,"ShaderNodeVectorMath", (350,50) , operation = 'MULTIPLY')
        mul2 =create_node(CurMat.nodes,"ShaderNodeVectorMath", (350,-50) , operation = 'MULTIPLY')
        add = create_node(CurMat.nodes,"ShaderNodeVectorMath", (500,0) , operation = 'ADD')
        sub.inputs[0].default_value = (1,1,1)
        CurMat.links.new(GroupInput.outputs[2],sub.inputs[1])
        CurMat.links.new(sub.outputs[0],mul.inputs[0])
        CurMat.links.new(GroupInput.outputs[0],mul.inputs[1])
        CurMat.links.new(GroupInput.outputs[2],mul2.inputs[0])
        CurMat.links.new(GroupInput.outputs[1],mul2.inputs[1])
        CurMat.links.new(GroupInput.outputs[1],mul2.inputs[1])
        CurMat.links.new(mul.outputs[0],add.inputs[0])
        CurMat.links.new(mul2.outputs[0],add.inputs[1])
        CurMat.links.new(add.outputs[0],GroupOutput.inputs[0])
        return CurMat

def show_message(message):
    bpy.ops.cp77.message_box('INVOKE_DEFAULT', message=message)


def createHash12Group():
    CurMat = bpy.data.node_groups.get('hash12')
    if CurMat:
        return CurMat
    else:
        CurMat = bpy.data.node_groups.new('hash12', 'ShaderNodeTree')
        vers=bpy.app.version
        if vers[0]<4:
            CurMat.inputs.new('NodeSocketVector','vector' )
            CurMat.outputs.new('NodeSocketFloat','result' )
        else:
            CurMat.interface.new_socket(name="vector",socket_type='NodeSocketVector', in_out='INPUT')
            CurMat.interface.new_socket(name="result", socket_type='NodeSocketFloat', in_out='OUTPUT')
        GroupInput = create_node(CurMat.nodes,"NodeGroupInput",(-500, 0), label="Group Input")
        GroupOutput = create_node(CurMat.nodes,"NodeGroupOutput",(1350, 0), label="Group Output")
        separate = create_node(CurMat.nodes,"ShaderNodeSeparateXYZ",  (-350,0))
        combine = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",  (-200,0))
        combine2 = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",  (-200,-50))
        vecMul = create_node(CurMat.nodes,"ShaderNodeVectorMath",  (0,0), operation = "MULTIPLY")
        frac = create_node(CurMat.nodes,"ShaderNodeVectorMath",  (150,0), operation = "FRACTION")
        vecMul.inputs[1].default_value = (.1031,.1031,.1031)
        dot = create_node(CurMat.nodes,"ShaderNodeVectorMath",  (300,-50), operation = "DOT_PRODUCT")
        vecAdd = create_node(CurMat.nodes,"ShaderNodeVectorMath",  (0,-50), operation = "ADD")
        vecAdd2 = create_node(CurMat.nodes,"ShaderNodeVectorMath",  (600,0), operation = "ADD")
        combine3 = create_node(CurMat.nodes,"ShaderNodeCombineXYZ",  (450,-50))
        separate2 = create_node(CurMat.nodes,"ShaderNodeSeparateXYZ",  (750,0))
        add = create_node(CurMat.nodes,"ShaderNodeMath",  (900,0), operation = "ADD")
        mul = create_node(CurMat.nodes,"ShaderNodeMath",  (1050,0), operation = "MULTIPLY")
        frac2 = create_node(CurMat.nodes,"ShaderNodeMath",  (1200,0), operation = "FRACT")
        CurMat.links.new(GroupInput.outputs[0],separate.inputs[0])
        CurMat.links.new(separate.outputs[0],combine.inputs[0])
        CurMat.links.new(separate.outputs[1],combine.inputs[1])
        CurMat.links.new(separate.outputs[0],combine.inputs[2])
        CurMat.links.new(combine.outputs[0],vecMul.inputs[0])
        CurMat.links.new(vecMul.outputs[0],frac.inputs[0])
        CurMat.links.new(separate.outputs[1],combine2.inputs[0])
        CurMat.links.new(separate.outputs[2],combine2.inputs[1])
        CurMat.links.new(separate.outputs[0],combine2.inputs[2])
        CurMat.links.new(combine2.outputs[0],vecAdd.inputs[0])
        vecAdd.inputs[1].default_value = (33.33,33.33,33.33)
        CurMat.links.new(frac.outputs[0],dot.inputs[0])
        CurMat.links.new(vecAdd.outputs[0],dot.inputs[1])
        CurMat.links.new(dot.outputs["Value"],combine3.inputs[0])
        CurMat.links.new(dot.outputs["Value"],combine3.inputs[1])
        CurMat.links.new(dot.outputs["Value"],combine3.inputs[2])
        CurMat.links.new(frac.outputs[0],vecAdd2.inputs[0])
        CurMat.links.new(combine3.outputs[0],vecAdd2.inputs[1])
        CurMat.links.new(vecAdd2.outputs[0],separate2.inputs[0])
        CurMat.links.new(separate2.outputs[0],add.inputs[0])
        CurMat.links.new(separate2.outputs[1],add.inputs[1])
        CurMat.links.new(add.outputs[0],mul.inputs[0])
        CurMat.links.new(separate2.outputs[2],mul.inputs[1])
        CurMat.links.new(mul.outputs[0],frac2.inputs[0])
        CurMat.links.new(frac2.outputs[0],GroupOutput.inputs[0])
        return CurMat

res_dir= get_resources_dir()

# Path to the JSON file
VCOL_PRESETS_JSON = os.path.join(res_dir, "vertex_color_presets.json")

def get_color_presets():
    if os.path.exists(VCOL_PRESETS_JSON):
        with open(VCOL_PRESETS_JSON, 'r') as file:
            return json.load(file)
    return {}

def save_presets(presets):
    with open(VCOL_PRESETS_JSON, 'w') as file:
        json.dump(presets, file, indent=4)
    update_presets_items()

def update_presets_items():
    presets = get_color_presets()
    items = [(name, name, "") for name in presets]
    return items



def get_selected_collection():
    active = bpy.context.active_object
    selected_objects = [obj for obj in bpy.context.selected_objects if obj != active]
    if not selected_objects and active is not None:
        selected_objects.append(active)

    selected_names = {obj.name for obj in selected_objects}
    matches = []
    for coll in bpy.data.collections:
        if any(name in coll.objects for name in selected_names):
            matches.append(coll)
            if len(matches) > 1:
                return None

    return matches[0] if matches else None


def get_active_collection():
    active = bpy.context.active_object
    if active is None:
        return None

    matches = []
    for coll in bpy.data.collections:
        if active.name in coll.objects:
            matches.append(coll)
            if len(matches) > 1:
                return None

    return matches[0] if matches else None

_TARGET_TYPES = Literal["MESH", "ARMATURE", "ALL"]


def get_collection_children(target_collection_name, target_type:_TARGET_TYPES = "MESH"):
    options = get_args(_TARGET_TYPES)
    assert target_type in options, f"'{target_type}' is not in {options}"

    collection = bpy.data.collections.get(target_collection_name)
    if collection is None:
        return None

    selected_children = [obj for obj in collection.objects if target_type == "ALL" or obj.type == target_type]
    return selected_children