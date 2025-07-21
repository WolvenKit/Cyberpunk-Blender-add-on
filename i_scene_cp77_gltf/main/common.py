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

def get_pos(inst):
    pos=[0,0,0]
    if 'Position' in inst.keys():
        if '$type' in inst['Position'].keys() and inst['Position']['$type']=='WorldPosition':
            pos[0]=inst['Position']['x']['Bits']/131072*scale_factor
            pos[1]=inst['Position']['y']['Bits']/131072*scale_factor
            pos[2]=inst['Position']['z']['Bits']/131072*scale_factor
        else:
            if 'Properties' in inst['Position'].keys():
                pos[0] = inst['Position']['Properties']['X'] /scale_factor
                pos[1] = inst['Position']['Properties']['Y'] /scale_factor
                pos[2] = inst['Position']['Properties']['Z'] /scale_factor
            else:
                if 'X' in inst['Position'].keys():
                    pos[0] = inst['Position']['X'] /scale_factor
                    pos[1] = inst['Position']['Y'] /scale_factor
                    pos[2] = inst['Position']['Z'] /scale_factor
                else:
                    pos[0] = inst['Position']['x'] /scale_factor
                    pos[1] = inst['Position']['y'] /scale_factor
                    pos[2] = inst['Position']['z'] /scale_factor
    elif 'position' in inst.keys():
        if 'X' in inst['position'].keys():
                pos[0] = inst['position']['X'] /scale_factor
                pos[1] = inst['position']['Y'] /scale_factor
                pos[2] = inst['position']['Z'] /scale_factor
    elif 'translation' in inst.keys():
        pos[0] = inst['translation']['X'] /scale_factor
        pos[1] = inst['translation']['Y'] /scale_factor
        pos[2] = inst['translation']['Z'] /scale_factor
    return pos

def get_rot(inst):
    rot=[0,0,0,1]
    if 'Orientation' in inst.keys():
        if 'Properties' in inst['Orientation'].keys():
            rot[0] = inst['Orientation']['Properties']['r']
            rot[1] = inst['Orientation']['Properties']['i']
            rot[2] = inst['Orientation']['Properties']['j']
            rot[3] = inst['Orientation']['Properties']['k']
        else:
            rot[0] = inst['Orientation']['r']
            rot[1] = inst['Orientation']['i']
            rot[2] = inst['Orientation']['j']
            rot[3] = inst['Orientation']['k']
    elif 'orientation' in inst.keys():
            rot[0] = inst['orientation']['r']
            rot[1] = inst['orientation']['i']
            rot[2] = inst['orientation']['j']
            rot[3] = inst['orientation']['k']
    elif 'Rotation' in inst.keys() and 'r' in inst['Rotation'].keys():
            rot[0] = inst['Rotation']['r']
            rot[1] = inst['Rotation']['i']
            rot[2] = inst['Rotation']['j']
            rot[3] = inst['Rotation']['k']
    elif 'Rotation' in inst.keys() and 'X' in inst['Rotation'].keys():
            rot[0] = inst['Rotation']['W']
            rot[1] = inst['Rotation']['X']
            rot[2] = inst['Rotation']['Y']
            rot[3] = inst['Rotation']['Z']
    elif 'rotation' in inst.keys():
            rot[0] = inst['rotation']['r']
            rot[1] = inst['rotation']['i']
            rot[2] = inst['rotation']['j']
            rot[3] = inst['rotation']['k']
    return rot

def get_scale(inst):
    scale=[0,0,0]
    if 'Scale' in inst.keys():
        if 'Properties' in inst['Scale'].keys():
            scale[0] = inst['Scale']['Properties']['X'] /scale_factor
            scale[1] = inst['Scale']['Properties']['Y'] /scale_factor
            scale[2] = inst['Scale']['Properties']['Z'] /scale_factor
        else:
            scale[0] = inst['Scale']['X'] /scale_factor
            scale[1] = inst['Scale']['Y'] /scale_factor
            scale[2] = inst['Scale']['Z'] /scale_factor
    elif 'scale' in inst.keys():
        scale[0] = inst['scale']['X'] /scale_factor
        scale[1] = inst['scale']['Y'] /scale_factor
        scale[2] = inst['scale']['Z'] /scale_factor
    return scale

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
        return tree.inputs
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
    # The speedtree materials use the same name textures for different plants this code was loading the same leaves on all of them
    Im = bpy.data.images.get(os.path.basename(Img)[:-4])
    if Im and Im.filepath==Img[:-3]+ image_format:
        if Im.colorspace_settings.name != 'Non-Color':
            if isNormal:
                Im = None
        else:
            if not isNormal:
                Im = None
    else:
        Im=None
    if not Im :
        Im = bpy.data.images.get(os.path.basename(Img)[:-4] + ".001")
        if Im and Im.filepath==Img[:-3]+ image_format:
            if Im.colorspace_settings.name != 'Non-Color':
                if isNormal:
                    Im = None
            else:
                if not isNormal:
                    Im = None
        else :
            Im = None

    if not Im:
        Im = bpy.data.images.new(os.path.basename(Img)[:-4],1,1)
        Im.source = "FILE"
        Im.filepath = Img[:-3]+ image_format
        if isNormal:
            Im.colorspace_settings.name = 'Non-Color'
    return Im

def imageFromRelPath(ImgPath, image_format='png', isNormal = False, DepotPath='',ProjPath=''):
    # The speedtree materials use the same name textures for different plants this code was loading the same leaves on all of them
    # Also copes with the fact that theres black.xbm in base and engine for instance
    DepotPath=DepotPath.replace('\\',os.sep)
    ProjPath=ProjPath.replace('\\',os.sep)
    if ImgPath is float:
        print(f"refusing to process unresolved relative image path {ImgPath}")
        return
    if ProjPath is float:
        print(f"refusing to process unresolved project path {ProjPath}")
        return

    inProj=os.path.join(ProjPath,ImgPath)[:-3]+ image_format
    inDepot=os.path.join(DepotPath,ImgPath)[:-3]+ image_format
    img_names=[k for k in bpy.data.images.keys() if bpy.data.images[k].filepath==inProj]
    img_name=None
    if len(img_names)>0:
        img_name=img_names[0]
    if not img_name:
        img_names=[k for k in bpy.data.images.keys() if bpy.data.images[k].filepath==inDepot]
        if len(img_names)>0:
            img_name=img_names[0]
    if img_name:
        Im = bpy.data.images.get(img_name)
    else:
        Im = None

    if Im:
        if Im.colorspace_settings.name != 'Non-Color':
            if isNormal:
                Im = None
        else:
            if not isNormal:
                Im = None
    else:
        Im=None

    if not Im:
        Im = bpy.data.images.new(os.path.basename(ImgPath)[:-4],1,1)
        Im.source = "FILE"
        if os.path.exists(inProj):
            Im.filepath = inProj
        else:
            Im.filepath = inDepot
        if isNormal:
            Im.colorspace_settings.name = 'Non-Color'
    return Im

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

        Sep = group.nodes.new("ShaderNodeSeparateRGB")
        Sep.location = (-600,0)
        Comb = group.nodes.new("ShaderNodeCombineRGB")
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
    if 'CP77_Parallax' in bpy.data.node_groups.keys():
        return bpy.data.node_groups['CP77_Parallax']
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
    # Get image dimensions
    image_width = grad_image_node.image.size[0]

    # Calculate stop positions
    stop_positions = [i / (image_width) for i in range(image_width)]
    #print(len(stop_positions))
    row_index = 0
    # Get colors from the row
    colors = []
    alphas = []
    for x in range(image_width):
        pixel_data = grad_image_node.image.pixels[(row_index * image_width + x) * 4: (row_index * image_width + x) * 4 + 4]
        color = Color()
        color.r, color.g, color.b = pixel_data[0:3]
        colors.append(color)
        alphas.append(pixel_data[3])
        # Create ColorRamp node
    color_ramp_node = CurMat.nodes.new('ShaderNodeValToRGB')
    color_ramp_node.location = location
    #print(len(colors))
    step=1
    if len(colors)>32:
        step=math.ceil(len(colors)/32)
    # Set the stops
    color_ramp_node.color_ramp.elements.remove(color_ramp_node.color_ramp.elements[1])
    for i, color in enumerate(colors):
        if i%step==0:
            if i>0:
                element = color_ramp_node.color_ramp.elements.new(i / (len(colors) ))
            else:
                element = color_ramp_node.color_ramp.elements[0]
            element.color = (color.r, color.g, color.b, alphas[i])
            element.position = stop_positions[i]

    color_ramp_node.color_ramp.interpolation = 'CONSTANT'
    return color_ramp_node

 # (1-t)a+tb

def createLerpGroup():
    if 'lerp' in bpy.data.node_groups.keys():
        return bpy.data.node_groups['lerp']
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
    if 'vecLerp' in bpy.data.node_groups.keys():
        return bpy.data.node_groups['vecLerp']
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
    if 'hash12' in bpy.data.node_groups.keys():
        return bpy.data.node_groups['hash12']
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
    items = [(name, name, "") for name in presets.keys()]
    return items
