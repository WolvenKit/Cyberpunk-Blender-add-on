from asyncio.windows_events import NULL
import bpy
import os

def imageFromPath(Img,image_format,isNormal = False):
    # The speedtree materials use the same name textures for different plants this code was loading the same leaves on all of them
    Im = bpy.data.images.get(os.path.basename(Img)[:-4])
    print('0', Img)
    if Im and Im.filepath==Img[:-3]+ image_format:
        print('1', Img,Im.filepath)
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
            print('2', Img,Im.filepath)
            if Im.colorspace_settings.name != 'Non-Color':
                if isNormal:
                    Im = None
            else:
                if not isNormal:
                    Im = None
        else :
            Im = None
    
    if not Im:
        print('not Im')
        Im = bpy.data.images.new(os.path.basename(Img)[:-4],1,1)
        Im.source = "FILE"
        Im.filepath = Img[:-3]+ image_format
        if isNormal:
            Im.colorspace_settings.name = 'Non-Color'
    return Im


def CreateShaderNodeTexImage(curMat,path = None, x = 0, y = 0, name = None,image_format = 'png', nonCol = False):
    ImgNode = curMat.nodes.new("ShaderNodeTexImage")
    ImgNode.location = (x, y)
    ImgNode.hide = True
    if name is not None:
        ImgNode.label = name
    if path is not None:
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
    
        group.inputs.new('NodeSocketColor','Image')
        group.outputs.new('NodeSocketColor','Image')
    
        VMup = group.nodes.new("ShaderNodeVectorMath")
        VMup.location = (-1200,-200)
        VMup.operation = 'MULTIPLY'
        VMup.inputs[1].default_value[0] = 2.0
        VMup.inputs[1].default_value[1] = 2.0
    
        VSub = group.nodes.new("ShaderNodeVectorMath")
        VSub.location = (-1000,-200)
        VSub.operation = 'SUBTRACT'
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
    if name is not None:
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