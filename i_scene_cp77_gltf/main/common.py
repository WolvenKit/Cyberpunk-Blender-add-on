import bpy
import os

def imageFromPath(Img,image_format,isNormal = False):
    Im = bpy.data.images.get(os.path.basename(Img)[:-4])
    if Im:
        if Im.colorspace_settings.name != 'Non-Color':
            if isNormal:
                Im = None
        else:
            if not isNormal:
                Im = None
    if not Im:
        Im = bpy.data.images.get(os.path.basename(Img)[:-4] + ".001")
        if Im:
            if Im.colorspace_settings.name != 'Non-Color':
                if isNormal:
                    Im = None
            else:
                if not isNormal:
                    Im = None
        
    if not Im:
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

def CreateShaderNodeNormalMap(curMat,path = None, x = 0, y = 0, name = None,image_format = 'png', nonCol = True):
    nMap = curMat.nodes.new("ShaderNodeNormalMap")
    nMap.location = (x,y)
    nMap.hide = True

    if path is not None:
        ImgNode = curMat.nodes.new("ShaderNodeTexImage")
        ImgNode.location = (x - 600, y)
        ImgNode.hide = True
        if name is not None:
            ImgNode.label = name
        Img = imageFromPath(path,image_format,nonCol)
        ImgNode.image = Img

        RgbCurve = curMat.nodes.new("ShaderNodeRGBCurve")
        RgbCurve.location = (x - 300, y)
        RgbCurve.hide = True
        RgbCurve.mapping.curves[2].points[0].location = (0,1)
        RgbCurve.mapping.curves[2].points[1].location = (1,1)

        curMat.links.new(ImgNode.outputs[0],RgbCurve.inputs[1])
        curMat.links.new(RgbCurve.outputs[0],nMap.inputs[1])

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