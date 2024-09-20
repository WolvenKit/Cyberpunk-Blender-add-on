#all of these should be json
facialsetupFile = r"F:\rip\cyberpunk\wkproject\kerry_face\kerryface\source\raw\base\characters\main_npc\kerry_eurodyne\h0_001_ma_c__kerry_eurodyne\h0_001_ma_c__kerry_eurodyne_old_rigsetup.facialsetup.json"
rigFile = r"F:\rip\cyberpunk\wkproject\kerry_face\kerryface\source\raw\base\characters\main_npc\kerry_eurodyne\h0_001_ma_c__kerry_eurodyne\h0_001_ma_c__kerry_eurodyne_old_skeleton.rig.json"
#only scenerid is supported rn but it should be pretty straightforward to load from .anims, just need to change where ApplyFacialSequenceFromeSceneRid looks for the animation data
animFile = r"F:\rip\cyberpunk\wkproject\kerry_face\kerryface\source\raw\base\animations\quest\side_quests\sq011\sq011_10_concert\rid\sq011_10_concert__kerry_performance.scenerid.json"

import bpy
import mathutils
import math
import base64
import copy

facialsetup = None
rig = None
def Init():
    ReadFiles()
    CreateArmature() #creates an armature by the name of facialsetup_armature from the rig file unless one alread exists
    
    ApplyFacialSequenceFromeSceneRid("app_kerry_eurodyne_old__kerry_eurodyne_controlRig", "sq011_10_concert__kerry_performance_anim_sn5")
    #third argument tells it to stich this onto the end of the previous sequence, useful for scenerid where stuff tends to be cut up into chunks
    ApplyFacialSequenceFromeSceneRid("app_kerry_eurodyne_old__kerry_eurodyne_controlRig", "sq011_10_concert__kerry_performance_anim_sn6", bpy.context.scene.frame_end)
    ApplyFacialSequenceFromeSceneRid("app_kerry_eurodyne_old__kerry_eurodyne_controlRig", "sq011_10_concert__kerry_performance_anim_sn7", bpy.context.scene.frame_end)
    ApplyFacialSequenceFromeSceneRid("app_kerry_eurodyne_old__kerry_eurodyne_controlRig", "sq011_10_concert__kerry_performance_anim_sn8", bpy.context.scene.frame_end)
    bpy.context.scene.frame_start = 1
    #do this to apply a set of individual poses
    # trackSettings = {}
    # trackSettings["eye_r_blink"] = 1 #scale, can be greater than 1 or negative, i havent specifically tried it but negative probably doesnt apply rotations correctly
    # trackSettings["eye_l_blink"] = 1 #if you want to fix applying rotations for negative scales the place to do that is in ScaleCoordSet
    # coordset = InitCoordSet()
    # for trackName in trackSettings.keys():
    #   CombineCoordSet(coordset, ScaleCoordSet(GetBoneTransformsForTrack(trackName), trackSettings[trackName]))
    # ApplyCorrectiveShapes(coordset, trackSettings) #this doesnt actually do anything rn lol
    # ApplyCoordSet(coordset) #give this a second argument with a frame number to keyframe instead of just set
    
def ReadFiles():
    print("reading rig...")
    jsonfile = open(rigFile, "r")
    exec("rig = "+jsonfile.read().replace("null", "None").replace("true", "True").replace("false", "False"), globals())
    jsonfile.close()
    
    print("reading facialsetup...")
    jsonfile = open(facialsetupFile, "r")
    exec("facialsetup = "+jsonfile.read().replace("null", "None").replace("true", "True").replace("false", "False"), globals())
    jsonfile.close()
    
    print("reading anim...")
    jsonfile = open(animFile, "r")
    exec("anim = "+jsonfile.read().replace("null", "None").replace("true", "True").replace("false", "False"), globals())
    jsonfile.close()
    print("done")

def CreateArmature():
    if "facialsetup_armature" in bpy.data.objects:
        return
    armature = bpy.data.objects.new("facialsetup_armature", bpy.data.armatures.new("facialsetup_armature"))
    bpy.context.scene.collection.objects.link(armature)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT')
    for i in range(0, len(rig["Data"]["RootChunk"]["boneNames"])):
        bone = armature.data.edit_bones.new(rig["Data"]["RootChunk"]["boneNames"][i]["$value"])
        bone.head = (0,0,0)
        bone.tail = (0,0,0.01)
    for i in range(0, len(rig["Data"]["RootChunk"]["boneNames"])):
        child = rig["Data"]["RootChunk"]["boneNames"][i]["$value"]
        parentindex = rig["Data"]["RootChunk"]["boneParentIndexes"][i]
        if parentindex == -1:
            continue
        parent = rig["Data"]["RootChunk"]["boneNames"][parentindex]["$value"]
        armature.data.edit_bones[child].parent = armature.data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for i in range(0, len(rig["Data"]["RootChunk"]["boneNames"])):
        bone = armature.pose.bones[rig["Data"]["RootChunk"]["boneNames"][i]["$value"]]
        transform = rig["Data"]["RootChunk"]["boneTransforms"][i]
        bone.location = mathutils.Vector((transform["Translation"]["X"], transform["Translation"]["Y"], transform["Translation"]["Z"]))
        bone.rotation_quaternion = (transform["Rotation"]["r"], transform["Rotation"]["i"], transform["Rotation"]["j"], transform["Rotation"]["k"])
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode='OBJECT')
    armature.rotation_euler = mathutils.Euler((math.radians(-90),0,0))
    
def ApplyFacialSequenceFromeSceneRid(actorSignature, sequence, offset=0):
    #find actor
    actor = None
    for i in range(0, len(anim["Data"]["RootChunk"]["actors"])):
        if anim["Data"]["RootChunk"]["actors"][i]["tag"]["signature"]["$value"] == actorSignature:
            actor = anim["Data"]["RootChunk"]["actors"][i]
            break
    if not actor:
        print("couldnt find actor "+actorSignature)
        return
    #find anim data
    animdata = None
    for i in range(0, len(actor["facialAnimations"])):
        if actor["facialAnimations"][i]["animation"]["Data"]["name"]["$value"] == sequence:
            animdata = actor["facialAnimations"][i]["animation"]["Data"]
            break
    if not animdata:
        print("couldnt find sequence "+sequence)
        return
    #read buffer
    trackAnimation = {}
    br = BinaryReader(base64.b64decode(animdata["animBuffer"]["Data"]["defferedBuffer"]["Bytes"]), Endian.LITTLE)
    #dont give a shit about these
    for i in range(0,animdata["animBuffer"]["Data"]["numAnimKeys"]):
        br.read_uint16()
        br.read_uint16()
        br.read_uint16()
        br.read_uint16()
        br.read_uint16()
    for i in range(0,animdata["animBuffer"]["Data"]["numAnimKeysRaw"]):
        br.read_uint16()
        br.read_uint16()
        br.read_uint32()
        br.read_uint32()
        br.read_uint32()
    for i in range(0,animdata["animBuffer"]["Data"]["numConstAnimKeys"]):
        br.read_uint16()
        br.read_uint16()
        br.read_uint32()
        br.read_uint32()
        br.read_uint32()
    #track info
    for i in range(0,animdata["animBuffer"]["Data"]["numTrackKeys"]):
        time = (br.read_uint16() / 65535) * animdata["animBuffer"]["Data"]["duration"]
        idx = br.read_uint16();
        value = br.read_float()
        if not idx in trackAnimation:
            trackAnimation[idx] = {}
        trackAnimation[idx][time] = value
    for i in range(0,animdata["animBuffer"]["Data"]["numConstTrackKeys"]):
        idx = br.read_uint16();
        time = (br.read_uint16() / 65535) * animdata["animBuffer"]["Data"]["duration"]
        value = br.read_uint32() / 4294967295
        if not idx in trackAnimation:
            trackAnimation[idx] = {}
        trackAnimation[idx][time] = value
    bpy.context.scene.render.fps = 30
    bpy.context.scene.frame_start = 1 + offset
    bpy.context.scene.frame_end = offset + round(animdata["animBuffer"]["Data"]["duration"] / (1 / 30) + 0.5)
    for frame in range(bpy.context.scene.frame_start, bpy.context.scene.frame_end + 1):
        frameTime = (frame - offset) * (1/30)
        frameSettings = {}
        for trackIndex in trackAnimation.keys():
            #calc blend
            startTime = None
            endTime = None
            for time in trackAnimation[trackIndex].keys():
                if time < frameTime:
                    startTime = time
                else:
                    endTime = time
                    break
            if not startTime and not endTime:
                continue
            if not startTime:
                startTime = endTime
            if not endTime:
                endTime = startTime
            blend = 0
            timeDiff = endTime - startTime
            if timeDiff > 0:
                blend = (frameTime - startTime) / timeDiff
            trackValue = trackAnimation[trackIndex][startTime] * (1 - blend) + trackAnimation[trackIndex][endTime] * blend
            if trackValue == 0:
                continue
            frameSettings[rig["Data"]["RootChunk"]["trackNames"][trackIndex]["$value"]] = trackValue
        frameCoordSet = InitCoordSet()
        for trackName in frameSettings.keys():
            CombineCoordSet(frameCoordSet, ScaleCoordSet(GetBoneTransformsForTrack(trackName), frameSettings[trackName]))
        ApplyCorrectiveShapes(frameCoordSet, frameSettings)
        print(frame)
        ApplyCoordSet(frameCoordSet, frame)
        
def ApplyCorrectiveShapes(coordset, trackSettings):
    #corrective shapes arent implemented yet
    return coordset
    
def GetBoneTransformsForTrack(track):
    #print("getting bone transforms for track "+track)
    #find track index
    trackIndex = -1
    for i in range(0,len(rig["Data"]["RootChunk"]["trackNames"])):
        if rig["Data"]["RootChunk"]["trackNames"][i]["$value"] == track:
            trackIndex = i
            break
    if trackIndex == -1:
        print("couldnt find track in rig file")
        return
    #print("trackIndex = "+str(trackIndex))
    coordset = {}
    #find face part
    #print("finding face parts")
    for part in ["Face", "Tongue", "Eyes"]:
        found = False
        for v in facialsetup["Data"]["RootChunk"]["bakedData"]["Data"][part]["UpperLowerFace"]:
            if v["Track"] == trackIndex:
                found = True
        if not found:
            continue
        #print("track found in face part " + part)
        #convert track index to face part specific pose index
        poseIndex = -1
        for i in range(0,len(facialsetup["Data"]["RootChunk"]["bakedData"]["Data"][part]["AllMainPoses"])):
            if facialsetup["Data"]["RootChunk"]["bakedData"]["Data"][part]["AllMainPoses"][i]["Track"] == trackIndex:
                poseIndex = i
                break
        if poseIndex == -1:
            print("couldnt find pose index for track")
            return
        #print("poseIndex = "+str(poseIndex))
        #find transform set
        poseDef = facialsetup["Data"]["RootChunk"]["mainPosesData"]["Data"][part]["Poses"][poseIndex]
        startTransform = poseDef["TransformIdx"]
        stopTransform = startTransform + poseDef["NumTransforms"]
        #print("startTransform = "+str(startTransform))
        #print("endTransform = "+str(stopTransform))
        #collect transform info
        for transformIndex in range(startTransform, stopTransform):
            transform = facialsetup["Data"]["RootChunk"]["mainPosesData"]["Data"][part]["Transforms"][transformIndex]
            bone = rig["Data"]["RootChunk"]["boneNames"][transform["Bone"]]["$value"]
            #print(str(transformIndex)+": "+bone)
            pos = mathutils.Vector((transform["Translation"]["X"], transform["Translation"]["Y"], transform["Translation"]["Z"]))
            #print("  pos:"+FormatVectorForString(pos))
            rot = mathutils.Quaternion((transform["Rotation"]["r"], transform["Rotation"]["i"], transform["Rotation"]["j"], transform["Rotation"]["k"]))
            CombineCoordSet(coordset,{bone.lower(): {"pos" : pos, "rot" : rot}})
    return coordset

def InitCoordSet():
    coordSet = {}
    for bone in rig["Data"]["RootChunk"]["boneNames"]:
        coordSet[bone["$value"].lower()] = {"pos" :  mathutils.Vector((0, 0, 0)), "rot" : mathutils.Quaternion()}
    return coordSet
            
def CombineCoordSet(a,b):
    for bone in b.keys():
        if bone in a:
            a[bone]["pos"] += b[bone]["pos"]
            a[bone]["rot"].rotate(b[bone]["rot"])
        else:
            a[bone] = b[bone]
    return a

def ScaleCoordSet(set, scale):
    for bone in set.keys():
        set[bone]["pos"] *= scale
        rotscale = scale
        newrot = mathutils.Quaternion()
        while rotscale > 0: #slerp only allows a range 0-1 so gotta do this shit, doesnt support negative scale tho
            newrot.rotate(set[bone]["rot"].slerp(mathutils.Quaternion(), max(0, min(1 - scale, 1))))
            rotscale -= 1
        set[bone]["rot"] = newrot
    return set

def ApplyCoordSet(set, frame=None):
    if frame:
        bpy.context.scene.frame_set(frame)
    if not set:
        return
    for posebone in bpy.data.objects["facialsetup_armature"].pose.bones:
        if posebone.name.lower() in set:
            posebone.location = set[posebone.name.lower()]["pos"]
            posebone.rotation_mode = "QUATERNION"
            posebone.rotation_quaternion = set[posebone.name.lower()]["rot"]
            if frame:
                posebone.keyframe_insert("location", frame=frame)
                posebone.keyframe_insert("rotation_quaternion", frame=frame)


def FormatVectorForString(vec):
    str = ""
    if not format(vec.x, '.4f').startswith("-"):
        str += " "
    str += format(vec.x, '.4f')+","
    if not format(vec.y, '.4f').startswith("-"):
        str += " "
    str += format(vec.y, '.4f')+","
    if not format(vec.z, '.4f').startswith("-"):
        str += " "
    str += format(vec.z, '.4f')
    return str

#gutted binary reader stuff that im sticking in here just for the sake of only portability 
#https://github.com/K0lb3/binaryreader
#__author__ = "SutandoTsukai181"
#__copyright__ = "Copyright 2021, SutandoTsukai181"
#__license__ = "MIT"
#__version__ = "1.4.3"
import struct
from contextlib import contextmanager
from enum import Flag, IntEnum
from typing import Tuple, Union
FMT = dict()
for c in ["b", "B", "s"]:
    FMT[c] = 1
for c in ["h", "H", "e"]:
    FMT[c] = 2
for c in ["i", "I", "f"]:
    FMT[c] = 4
for c in ["q", "Q"]:
    FMT[c] = 8
class Endian(Flag):
    LITTLE = False
    BIG = True
class Whence(IntEnum):
    BEGIN = 0
    CUR = 1
    END = 2
class BrStruct:
    def __init__(self) -> None:
        pass
    def __br_read__(self, br: 'BinaryReader', *args) -> None:
        pass
    def __br_write__(self, br: 'BinaryReader', *args) -> None:
        pass
class BinaryReader:
    __buf: bytearray
    __idx: int
    __endianness: Endian
    __encoding: str
    def __init__(self, buffer: bytearray = bytearray(), endianness: Endian = Endian.LITTLE, encoding='utf-8'):
        self.__buf = bytearray(buffer)
        self.__endianness = endianness
        self.__idx = 0
        self.set_encoding(encoding)
    def __past_eof(self, index: int) -> bool:
        return index > self.size()
    def past_eof(self) -> bool:
        return self.__past_eof(self.pos())
    def size(self) -> int:
        return len(self.__buf)
    def set_endian(self, endianness: Endian) -> None:
        self.__endianness = endianness
    def set_encoding(self, encoding: str) -> None:
        str.encode('', encoding)
        self.__encoding = encoding
    def __read_type(self, format: str, count=1):
        i = self.__idx
        new_offset = self.__idx + (FMT[format] * count)
        end = ">" if self.__endianness else "<"
        if self.__past_eof(new_offset):
            raise Exception(
                'BinaryReader Error: cannot read farther than buffer length.')
        self.__idx = new_offset
        return struct.unpack_from(end + str(count) + format, self.__buf, i)
    def read_uint32(self, count=None) -> Union[int, Tuple[int]]:
        if count is not None:
            return self.__read_type("I", count)
        return self.__read_type("I")[0]
    def read_uint16(self, count=None) -> Union[int, Tuple[int]]:
        if count is not None:
            return self.__read_type("H", count)
        return self.__read_type("H")[0]
    def read_float(self, count=None) -> Union[float, Tuple[float]]:
        if count is not None:
            return self.__read_type("f", count)
        return self.__read_type("f")[0]

Init()