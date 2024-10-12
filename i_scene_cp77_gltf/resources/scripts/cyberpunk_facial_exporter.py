# Initial support for extraction of facial animations from scenerid and anim files
# Code written by a combination of John CO and Loomy, some tidying/QOL changes from Sim
# Export the .rig, .facialsetup and either anim or scenerid to a project as json
# Fill in the path variable at the top of the code to point at your project, 
# Paste the relative paths straight from wkit for the original game files into the File variables
# Run it, and it should generate the face rig, and create an anim track for it.
#

import bpy
import os
from mathutils import *
from math import *
import json
from types import SimpleNamespace
from enum import Enum
import base64
import copy
#ArmatureName = "facialsetup_armature"
project=r"C:\CPMod\facial_anims\source\raw"
facialSetupFile = r"base\characters\main_npc\judy\h0_001_wa_c__judy\h0_001_wa_c__judy_rigsetup.facialsetup"
rigFile = r"base\characters\main_npc\judy\h0_001_wa_c__judy\h0_001_wa_c__judy_skeleton.rig"
animFile = r"base\localization\en-us\lipsync\base\quest\main_quests\prologue\q004\scenes\q004_04b_after_tutorial\judy.anims"
#signature value from the actor in the scenerid - ignored for anims
actor_signature = "female_average"
track_names=["f_15B781CF6B5AE004"]

##ArmatureName = "facialsetup_armature"
#project=r"C:\CPMod\facial_anims\source\raw"
#facialSetupFile = r"base\characters\main_npc\judy\h0_001_wa_c__judy\h0_001_wa_c__judy_rigsetup.facialsetup"
#rigFile = r"base\characters\main_npc\judy\h0_001_wa_c__judy\h0_001_wa_c__judy_skeleton.rig"
#animFile = r"base\animations\quest\side_quests\sq030\sq030_10_sex\sex_judy_layout.scenerid"
##signature value from the actor in the scenerid - ignored for anims
#actor_signature = "female_average"
#track_names = ["sex_judy_layout_anim_sn93","sex_judy_layout_anim_sn94","sex_judy_layout_anim_sn95","sex_judy_layout_anim_sn96",
#"sex_judy_layout_anim_sn97","sex_judy_layout_anim_sn98","sex_judy_layout_anim_sn99","sex_judy_layout_anim_sn100","sex_judy_layout_anim_sn101"]

#project=r"C:\CPMod\facial_anims\source\raw"
#facialSetupFile = r"base\characters\main_npc\kerry_eurodyne\h0_001_ma_c__kerry_eurodyne\h0_001_ma_c__kerry_eurodyne_old_rigsetup.facialsetup"
#rigFile = r"base\characters\main_npc\kerry_eurodyne\h0_001_ma_c__kerry_eurodyne\h0_001_ma_c__kerry_eurodyne_old_skeleton.rig"
#animFile = r"base\animations\quest\side_quests\sq011\sq011_10_concert\rid\sq011_10_concert__kerry_performance.scenerid"
#actor_signature = "app_kerry_eurodyne_old__kerry_eurodyne_controlRig"
#track_names = ["sq011_10_concert__kerry_performance_anim_sn5","sq011_10_concert__kerry_performance_anim_sn6",
#"sq011_10_concert__kerry_performance_anim_sn7","sq011_10_concert__kerry_performance_anim_sn8"]


facialSetupFile = os.path.join(project,facialSetupFile)+'.json'
rigFile = os.path.join(project,rigFile)+'.json'
animFile = os.path.join(project,animFile)+'.json'
#TODO: remove all or use as Property Enums
FACE_REGION = [
    "FACE_REGION_EYES",
    "FACE_REGION_NOSE",
    "FACE_REGION_MOUTH",
    "FACE_REGION_JAW",
    "FACE_REGION_EARS"
]
#FACE_REGION[-1/255] = "FACE_REGION_NONE"
FACE_PART = [
    "FACE_NONE",
    "FACE_UPPER",
    "FACE_LOWER",
]
FACE_POSE_SIDE = [
    "POSE_SIDE_LEFT",
    "POSE_SIDE_RIGHT",
    "POSE_SIDE_MID",
    "POSE_SIDE_NONE"
]
#muzzles = like dog muzzle / reduction of track weights
FACE_MUZZLES = [
    "MUZZLE_LIPS",
    "MUZZLE_JAW",
    "MUZZLE_EYES",
    "MUZZLE_BROWS",
    "MUZZLE_EYE_DIRECTIONS",
    "MUZZLE_NONE"
]
CORRECTIVE_INFLUENCE_TYPE = [
    "None",
    "influencedBySpeed",
    "linearCorrection"
]

def Clamp(value,low,high):
    if value < low: value = low
    elif value > high: value = high
    return value

def Lerp(alpha,a,b):
    return float((a * (1.0 - alpha)) + (b * alpha))

class CP77_FacialSetup:
    def __init__(self):
        self.ftepsilon = 0.001
        self.boneState = {}
        self.boneUsage = []
        self.trackData = []
        self.fs = {}
        self.isLoaded = False 
        self.isFsLoaded = False
        self.isRigLoaded = False
        self.rigData = {}
        self.boneNames = []
        self.trackNames = []
        self.boneRegions = []
        self.boneTransformsRHS = []
        self.lipsyncOverrides = []
        self.trackIndices = []
        self.trackIndices.append([])
        self.trackIndices.append([])
        self.trackIndices.append([])
        self.trackReferences = []
        self.trackDefault = []
        self.inbetweens = []
        self.poseSides = [{},{},{}]
        self.faceParts = [{},{},{}]
        self.envelopes = []
        self.wrinkleInfo = [{},{},{}]
        self.wrinkleMapping = [{},{},{}]
        self.envelopeMapping = [{},{},{}]
        self.poseInfluences = [{},{},{}]
        self.poseTrackData = [{},{},{}]
        self.trackBuffer = [{},{},{}]
        self.poseTrackInfo = [[],[],[]]
        self.poseTransformIdx = [{},{},{}]
        self.poseTrackWeights = [{},{},{}]
        self.poseInbetweens = [{},{},{}]
        self.poseInbetweensMult = [{},{},{}]
        self.numEnvelopeTracks = 13

    def loadJson(self, facialsetup_json, rig_json):		
        with open(facialsetup_json, 'r') as fp:
            fsdata=json.load(fp, object_hook=lambda data: SimpleNamespace(**data))
            self.fs = fsdata.Data.RootChunk
        with open(rig_json,'r') as rf:
            self.rigData = json.load(rf)
            self.boneNames = []
            self.boneUsage = []
            for bb in self.rigData["Data"]["RootChunk"]["boneNames"]:
                self.boneNames.append(bb["$value"])
                self.boneRegions.append(255)
                self.boneUsage.append(False)
            self.trackNames = []
            self.trackReferences = self.rigData["Data"]["RootChunk"]["referenceTracks"]
            self.trackDefault = self.rigData["Data"]["RootChunk"]["referenceTracks"]
            for t in self.rigData["Data"]["RootChunk"]["trackNames"]:
                self.trackNames.append(t["$value"])
                #self.inbetweens.append(0)
            self.trackBuffer = [{},{},{}]
            for trk,tName in enumerate(self.trackNames):
                self.trackBuffer[0][trk] = self.trackReferences[trk]
        #self.getTransforms()
        print("successfully loaded FacialSetup")

    def initTracks(self,extraTracks=[]):
        #mostly override related (envelopes, jaw/lips multiplier, muzzle defaults)
        self.trackData = self.rigData["Data"]["RootChunk"]["referenceTracks"]
        #manually entered / fetched from action[trackKeys]
        if len(extraTracks) > 0:
            for et in extraTracks:
                self.trackData[et[0]] = et[1]
    # quick fetch of facialsetup data
    # TODO: Check mem consumption of passing byref multple times, vs direct ref
    def bakedData(self,partIndex=0):
        #if not self.isLoaded:
        #	return {}
        if partIndex == 1:
            return self.fs.bakedData.Data.Eyes
        elif partIndex == 2:
            return self.fs.bakedData.Data.Tongue
        else:
            return self.fs.bakedData.Data.Face
    def poseData(self,partIndex=0):
        #if not self.isLoaded:
        #	return {}
        if partIndex == 1:
            return self.fs.mainPosesData.Data.Eyes
        elif partIndex == 2:
            return self.fs.mainPosesData.Data.Tongue
        else:
            return self.fs.mainPosesData.Data.Face
    def correctiveData(self,partIndex=0):
        #if not self.isLoaded:
        #	return {}
        if partIndex == 1:
            return self.fs.correctivePosesData.Data.Eyes
        elif partIndex == 2:
            return self.fs.correctivePosesData.Data.Tongue
        else:
            return self.fs.correctivePosesData.Data.Face
    def poseInfo(self,partIndex=0):
        #if not self.isLoaded:
        #	return {}
        if partIndex == 1:
            return self.fs.posesInfo.eyes
        elif partIndex == 2:
            return self.fs.posesInfo.tongue
        else:
            return self.fs.posesInfo.face
    def Info(self,partIndex=0):
        #if not self.isLoaded:
        #	return {}
        if partIndex < 0:
            return self.fs.info
        elif partIndex == 1:
            return self.fs.info.eyes
        elif partIndex == 2:
            return self.fs.info.tongue
        else:
            return self.fs.info.face
    #
    def getOriginalBoneTransform(self,boneName):
        boneIndex = self.boneNames.index(boneName)
        rr = self.rigData["Data"]["RootChunk"]["boneTransforms"][boneIndex]["Rotation"]
        tt = self.rigData["Data"]["RootChunk"]["boneTransforms"][boneIndex]["Translation"]
        ss = self.rigData["Data"]["RootChunk"]["boneTransforms"][boneIndex]["Scale"]
        r = Quaternion((rr["r"],rr["i"],rr["j"],rr["k"]))
        t = Vector((tt["X"],tt["Y"],tt["Z"]))
        s = Vector((ss["X"],ss["Y"],ss["Z"]))
        posMtx = Matrix.Translation(t)
        rotMtx = r.to_matrix().to_4x4()
        matrix = posMtx @ rotMtx
        scaMtx = Matrix()  # 4x4 default
        scaMtx[0][0] = 1.0
        scaMtx[1][1] = 1.0
        scaMtx[2][2] = 1.0
        matrix = matrix @ scaMtx
        return matrix
    # undo wkit/glb handedness conversion, to original rig boneTransform matrices
    def convertHeadBonesRHStoLHS(self):
        if C.active_object is not None and C.active_object.type == 'ARMATURE':
            self.boneTransformsRHS = []
            bpy.ops.object.mode_set(mode='OBJECT')
            arm = C.active_object
            bpy.ops.object.mode_set(mode='EDIT')
            for b in self.boneNames:
                self.boneTransformsRHS.append([])
            #store original LHS bone matrices
            #for b in self.boneNames:
            #	boneIndex = self.boneNames.index(b)
            #	if boneIndex == 0:
            #		t,r,s = arm.data.edit_bones[0].matrix.decompose()
            #	else:
            #		t,r,s = (arm.data.edit_bones[boneIndex].parent.matrix.inverted() @ arm.data.edit_bones[boneIndex].matrix).decompose()
            #	self.boneTransformsRHS[boneIndex] = [t,r,s]
            for b in self.boneNames:
                boneIndex = self.boneNames.index(b)
                mtx =  self.getOriginalBoneTransform(b)
                if boneIndex < 1:
                    mtx = arm.matrix_world @ mtx
                    arm.data.edit_bones[b].matrix = mtx
                    skip=1
                elif boneIndex == 1:
                    pmtx =  self.getOriginalBoneTransform("Root")
                    pmtx = arm.matrix_world @ pmtx
                    mtx = pmtx @ mtx
                    arm.data.edit_bones[b].matrix = mtx
                    #mtx = arm.data.edit_bones[b].parent.matrix.inverted() @ mtx
                    #arm.data.edit_bones[b].matrix = mtx
                else:
                    mtx = arm.data.edit_bones[b].parent.matrix @ mtx
                    arm.data.edit_bones[b].matrix = mtx
            bpy.ops.object.mode_set(mode='OBJECT')
    ###
    def Clamp(self,value,low,high):
        if value < low: value = low
        elif value > high: value = high
        return value
    def Lerp(self,alpha,a,b):
        return float((a * (1.0 - alpha)) + (b * alpha))
    def quat_mul(self,q,weight=1.0):
        qt = (q.x + q.y + q.z)
        if qt == 0:
            return q
        euv4 = Vector(q.to_euler()) * weight
        return Euler(euv4).to_quaternion()
    def v3_mul(self,v,weight=1.0):
        vt = v[0]+v[1]+v[2]
        if vt == 0:
            return v
        return v * weight
    def ti(self,n):#trackIndex
        return self.trackNames.index(n)
    #TODO: remove
    ## FETCH BONE DRIVER VALUE (Cumulative Transforms for all Tracks/Poses)
    def bone_driver_evaluate(self,bone,channel,index):
        self.syncTrackBuffer(0)
        return self.boneState[bone][channel][index]
    #TODO: remove
    def calc_bone_transforms(self,trackKey,weight=0.0,facePart=0):
        numInbetweens = self.poseInbetweens[facePart][trackKey]
        # inbetween step
        stepFrom_w = 0.0
        stepTo_w = 0.0
        pose1_index = -1
        pose2_index = -1
        max_w = max(self.poseTrackWeights[facePart][trackKey])
        max_step = self.poseTrackWeights[facePart][trackKey].index(max_w)
        #overriden / multiplied poses with weight > 1.0
        if weight > max_w:
            pose2_index = max_step
            pose2_weight = weight        
        elif numInbetweens == 1:
            pose2_index = 0
            pose2_weight = weight  
        else:
            for ibw in self.poseTrackWeights[facePart][trackKey]:
                stepTo_w = ibw
                if weight <= stepTo_w:
                    pose2_index = self.poseTrackWeights[facePart][trackKey].index(stepTo_w)
                    break
                stepFrom_w = stepTo_w
                pose1_index = self.poseTrackWeights[facePart][trackKey].index(stepFrom_w)
            pose2_weight = (weight - stepFrom_w) / (stepTo_w - stepFrom_w)
            pose1_weight = 1.0 - pose2_weight
        if pose1_index >= 0 and pose1_weight > 0.0:
            poseData = self.poseTrackData[facePart][trackKey][pose1_index]
            for pose in poseData:
                bn = pose['bone']
                t1,r1,s1 = self.boneState[bn]
                t2 = pose['T']
                r2 = pose['R']
                s2 = pose['S']
                t3 = t1 + (t2 * pose1_weight)
                r3 = Euler(Vector(r1.to_euler()) + (Vector(r2.to_euler())*pose1_weight)).to_quaternion()
                s3 = s1 + (s2 * pose1_weight)
                self.boneState[bn][0] = t3
                self.boneState[bn][1] = r3
                self.boneState[bn][2] = s3
        if pose2_index >= 0 and pose2_weight > 0.0:
            poseData = self.poseTrackData[facePart][trackKey][pose2_index]
            for pose in poseData:
                bn = pose['bone']
                t1,r1,s1 = self.boneState[bn]
                t2 = pose['T']
                r2 = pose['R']
                s2 = pose['S']
                t3 = t1 + (t2 * pose2_weight)
                r3 = Euler(Vector(r1.to_euler()) + (Vector(r2.to_euler())*pose2_weight)).to_quaternion()
                s3 = s1 + (s2 * pose2_weight)
                self.boneState[bn][0] = t3
                self.boneState[bn][1] = r3
                self.boneState[bn][2] = s3
            #
        #
    #TODO: link to mesh based controls
    def syncTrackBuffer(self,facePart=0):
        #self.trackBuffer[facePart] = {}
        #for trk,tName in enumerate(self.trackNames):
        #    self.trackBuffer[facePart][trk] = self.trackReferences[trk]
        #bpy.data.objects["sldt1_knob.001"]["SLD_1_Val"]
        self.trackBuffer[0][45] = bpy.data.objects["sldt1_knob.001"]["SLD_1_Val"]
        #self.trackBuffer[0][46] = bpy.data.objects["sldt1_knob.002"]["SLD_2_Val"]
        self.boneState = {}
        for bn, bName in enumerate(self.boneNames):
            self.boneState[bn] = [Vector(),Quaternion(),Vector([0.0,0.0,0.0,0.0])]
        for trackKey in self.trackBuffer[facePart].keys():
            weight = self.trackBuffer[facePart][trackKey]
            if weight != 0.0 and trackKey in self.poseTrackData[facePart]:
                self.calc_bone_transforms(trackKey,weight,facePart)
            #
        #
    #
    # Track Weight calculation - per part (face H0,eyes HE,tongue HT)
    def update_tracks(self,partIndex,tracks):
        numAllInbetweens = self.Info(partIndex).numAllMainPosesInbetweens
        numAllCorrectives = self.Info(partIndex).numAllCorrectives
        numGlobalCorrectives = len(self.bakedData(partIndex).GlobalCorrectiveEntries)
        numAllCorrectiveInbetweens = len(self.correctiveData(partIndex).Poses)
        correctives = []
        correctivesData = []
        inbetweenWeights = []
        inbetweenData = []
        #
        for i in range(0,512):
            correctivesData.append(1.0)
            inbetweenData.append(0.0)
        for i in range(0,numAllCorrectives):
            correctives.append(1.0)
        for i in range(0,numAllInbetweens):
            inbetweenWeights.append(0.0)
        #
        muzzleLimits = [1.0,1.0,1.0,1.0,1.0,1.0]
        faceLimits = [1.0,2.0,2.0]
        multiplyLimits = [2.0, 2.0, 1.0, 1.0, 1.0, 1.0]
        muzzles = [
            1.0 - Clamp(0.0,0.0,muzzleLimits[0]), 
            1.0 - Clamp(0.0,0.0,muzzleLimits[1]), 
            1.0 - Clamp(tracks[self.ti("muzzleEyes")], 0.0, muzzleLimits[2]), 
            1.0 - Clamp(tracks[self.ti("muzzleBrows")], 0.0, muzzleLimits[3]), 
            1.0 - Clamp(tracks[self.ti("muzzleEyeDirections")], 0.0, muzzleLimits[4]),
            1.0 - Clamp(0.0,0.0,muzzleLimits[5])
        ]
        multipliers = [
            Clamp(tracks[self.ti("jaliJaw")],0.0,multiplyLimits[0]),
            Clamp(tracks[self.ti("jaliLips")],0.0,multiplyLimits[1]),
            1.0,
            1.0,
            1.0,
            1.0
        ]
        faceEnvelopes = [
            1.0,
            Clamp(tracks[self.ti("upperFace")],0.0,faceLimits[1]),
            Clamp(tracks[self.ti("lowerFace")],0.0,faceLimits[2])
        ]
        self.setMuzzles(partIndex,tracks,muzzles)
        self.setGlobalLimits(partIndex,tracks,multipliers)
        self.setPoseInfluences(partIndex, tracks)
        self.setFaceEnvelopes(partIndex, tracks,faceEnvelopes)
        self.setLipsyncOverrides(partIndex, tracks)
        self.addLipsyncPoses(partIndex, tracks)
        self.setPoseInfluences(partIndex, tracks)
        self.getInbetweenWeights(partIndex, tracks, inbetweenWeights)

        self.setGlobalCorrectives(partIndex, tracks, correctives)
        self.setInbetweenCorrectives(partIndex, tracks, correctives)
        self.setCorrectiveInfluences(partIndex, tracks, correctives)

        self.setPoseTransforms(partIndex, tracks, inbetweenWeights)
        #APPLY MAIN POSES (tracks,inbetweenWeights)
        #APPLY CORRECTIVES (tracks, correctiveWeights)
    #
    def setMuzzles(self,partIndex,tracks,muzzles):
        for e in self.bakedData(partIndex).EnvelopesPerTrackMapping:
            trk = e.Track
            lod = e.LevelOfDetail
            eidx = e.Envelope
            w = Clamp(tracks[trk], 0.0, 1.0)
            if w > self.ftepsilon:
                w *= muzzles[eidx]
            else:
                w = 0.0
            tracks[trk] = w
    #
    def clampWeight(self, inputWeight, minval, midval, maxval):
        outWeight = 0.0
        if inputWeight == 1.0:
            outWeight = midval
        elif inputWeight < 1.0:
            outWeight = minval + (inputWeight * (midval - minval))
            minWeight = min([minval, midval])
            maxWeight = max([minval, midval])
            outWeight = Clamp(outWeight, minWeight, maxWeight)
        else:
            outWeight = midval + ((inputWeight - 1.0) * (maxval - midval))
            minWeight = min([midval, maxval])
            maxWeight = max([midval, maxval])
            outWeight = Clamp(outWeight, minWeight, maxWeight)
        return outWeight
    #
    def setGlobalLimits(self,partIndex,tracks,multipliers):
        lipsyncEnvelope = Clamp(tracks[self.ti("lipSyncEnvelope")], 0.0, 1.0)
        muzzleLips = Clamp(tracks[self.ti("muzzleLips")], 0.0, 1.0)
        if lipsyncEnvelope == 0.0:
            return True 
        for gl in self.bakedData(partIndex).GlobalLimits:
            trk = gl.Track
            eidx = gl.Envelope
            maxWeight = self.clampWeight(multipliers[eidx],gl.Min, gl.Mid, gl.Max)
            if tracks[trk] > maxWeight:
                tracks[trk] = self.Lerp(muzzleLips, tracks[trk], maxWeight);
    #
    def setPoseInfluences(self, partIndex, tracks):
        idx = 0
        for infTrk in self.bakedData(partIndex).InfluencedPoses:
            trk = infTrk.Track
            num = infTrk.NumInfluences
            infType = infTrk.Type
            w = tracks[trk]
            if w <= 0.0:
                idx += num
                continue
            inf_w = 0.0 
            for i in range(0,num):
                inf_idx = self.bakedData(partIndex).InfluenceIndices[idx+i]
                inf_w += tracks[inf_idx]
            idx += num
            if inf_w >= 1.0:
                w = 0.0
            elif infType == 0:
                m = 1.0 - inf_w
                if m < w:
                    w = m
            elif infType == 1:
                w *= 1.0 - (inf_w * inf_w)
            elif infType == 2:
                m = 1.0 - inf_w
                w *= m * m
            tracks[trk] = w
    #
    def setFaceEnvelopes(self, partIndex, tracks,faceEnvelopes):
        # Envelope min/max limit
        limits = [[0.0,1.0],[0.0,2.0],[0.0,2.0]] 
        for e in self.bakedData(partIndex).UpperLowerFace:
            w = Clamp(tracks[e.Track] * faceEnvelopes[e.Part] , 0.0, limits[e.Part][1])
            tracks[e.Track] = w
    #
    def setLipsyncOverrides(self, partIndex, tracks):
        lipsyncEnvelope = Clamp(tracks[self.ti("lipSyncEnvelope")], 0.0, 1.0)
        trkOffset = self.Info(-1).tracksMapping.numEnvelopes + self.Info(-1).tracksMapping.numMainPoses
        for i in range(0,self.Info(-1).numLipsyncOverridesIndexMapping):
            trk = self.fs.bakedData.Data.LipsyncOverridesIndexMapping[i]
            tracks[trk] *= Lerp(lipsyncEnvelope, 1.0, tracks[trkOffset + i])
    #
    def addLipsyncPoses(self, partIndex, tracks):
        lipsyncEnvelope = Clamp(tracks[self.ti("lipSyncEnvelope")], 0.0, 1.0)
        lipSyncLeftEnvelope = Clamp(tracks[self.ti("lipSyncLeftEnvelope")], 0.0, 1.0)
        lipSyncRightEnvelope = Clamp(tracks[self.ti("lipSyncRightEnvelope")], 0.0, 1.0)
        tmap = self.Info(-1).tracksMapping
        lipsyncTrackOffset = tmap.numEnvelopes + tmap.numMainPoses + tmap.numLipsyncOverrides
        for s in self.bakedData(partIndex).LipsyncPosesSides:
            trk = s.Track
            side = s.Side
            lipsyncTrack = lipsyncTrackOffset + trk - 13
            w = Clamp(tracks[trk] + tracks[lipsyncTrack], 0.0, 1.0)
            tracks[trk] = w
    #
    def getInbetweenWeights(self, partIndex, tracks, inbetweenWeights):
        numAllMainPosesInbetweens = self.Info(partIndex).numAllMainPosesInbetweens
        inbetweens = self.bakedData(partIndex).AllMainPosesInbetweens
        inbetweenScope =  self.bakedData(partIndex).AllMainPosesInbetweenScopeMultipliers
        oi = 0 # output index
        wi = 0 # inbetween index
        si = 0 # scope index
        for i in range(0,len(self.bakedData(partIndex).AllMainPoses)):
            mp = self.bakedData(partIndex).AllMainPoses[i]
            numInbetweens = mp.NumInbetweens
            w = tracks[mp.Track]
            for ii in range(0,numInbetweens):
                inbetweenWeights[oi + ii] = 0.0
            end = numInbetweens - 1
            endWeight = inbetweens[wi + end]
            startWeight = inbetweens[wi]
            if w < 0.001:
                skip=1
            elif numInbetweens == 1:
                inbetweenWeights[oi] = w
            elif w <= startWeight:
                inbetweenWeights[oi] = w * inbetweenScope[si]
            elif endWeight <= w:
                inbetweenWeights[oi + end] = 1.0
            else:
                realEnd = 1
                while inbetweens[wi + realEnd] <= w and realEnd < numInbetweens:
                    realEnd += 1
                start = realEnd - 1
                realEndingWeight = (w - inbetweens[wi + start]) * inbetweenScope[si + (realEnd-1)]
                realStartWeight = 1.0 - realEndingWeight
                inbetweenWeights[oi + start] = realStartWeight
                inbetweenWeights[oi + realEnd] = realEndingWeight
            oi += numInbetweens
            wi += numInbetweens
            si += numInbetweens - 1
        # END FOR
    #
    def setGlobalCorrectives(self, partIndex, tracks, correctives):
        for gc in self.bakedData(partIndex).GlobalCorrectiveEntries:
            corrIndex = gc.Index
            tmp = (gc.Track << 4) | gc.Unknown
            trackIndex = (tmp & 0xFFF0) >> 4
            lod = tmp & 0x000F
            trackWeight = tracks[trackIndex]
            if trackWeight <= 0.0:
                correctives[corrIndex] = 0.0
            elif trackWeight > 1.0:
                trackWeight = 1.0
            correctives[corrIndex] *= trackWeight
    #
    def setInbetweenCorrectives(self, partIndex, tracks, correctives):
        for gc in self.bakedData(partIndex).InbetweenCorrectiveEntries:
            corrIndex = gc.Index
            tmp = (gc.Track << 4) | gc.Unknown
            trackIndex = (tmp & 0xFFF0) >> 4
            lod = tmp & 0x000F
            trackWeight = tracks[trackIndex]
            if trackWeight <= 0.0:
                correctives[corrIndex] = 0.0
            elif trackWeight > 1.0:
                trackWeight = 1.0
            correctives[corrIndex] *= trackWeight
    #
    def setCorrectiveInfluences(self, partIndex, tracks, correctives):
        idx = 0
        for infTrk in self.bakedData(partIndex).CorrectiveInfluencedPoses:
            trk = infTrk.Index
            num = infTrk.NumInfluences
            infType = infTrk.Type
            influenceBySpeed = infTrk.Type & 1
            linearCorrection = infTrk.Type & 2
            w = correctives[trk]
            if w <= self.ftepsilon: #0.001
                idx += num
                continue
            corr_w = 0.0 
            for i in range(0,num):
                inf_idx = self.bakedData(partIndex).CorrectiveInfluenceIndices[idx+i]
                corr_w += correctives[inf_idx]
            idx += num
            #
            if linearCorrection:
                c = 1.0 - corr_w
                w = w * c
                if influenceBySpeed:
                    w *= c
            else:
                if corr_w >= 1.0:
                    w = 0.0
                elif not influenceBySpeed:
                    c = 1.0 - corr_w
                    if c < w:
                        w = c
                elif influenceBySpeed:
                    w *= 1.0 - (corr_w * corr_w)
            correctives[trk] = w
    #
    def getBaseTransforms(self):
        #store cumulative additive transforms per bone
        self.boneState = {}
        for bn, bName in enumerate(self.boneNames):
            #flag to track which bones have transforms for current call/pose
            #no need for extra 100+ [v3/v4/v3]
            self.boneUsage[bn] = False
            self.boneState[bn] = []
        for bn in self.fs.usedTransformIndices:
            #TODO: factor in pose bones default scale of 1:1:1
            #location/rotation_quaternion/scale
            self.boneState[bn] = [Vector(),Quaternion(),Vector([0.0,0.0,0.0])]
    #apply facial poses based on calculated weights
    #TODO: same method used for corrective transforms (MainPoseData/CorrectiveData) with corrective weights
    def setPoseTransforms(self, partIndex, tracks, weights):
        poseInfo = self.poseData(partIndex)
        numPoses = len(poseInfo.Poses)
        if numPoses != len(weights):
            print("PoseTransforms vs Weights mismatch")
            #throw ex
        for i in range(0,numPoses):
            pinfo = poseInfo.Poses[i]
            weight = weights[i]
            if weight > 0.001: #epsilon / ignore lower
                num = pinfo.NumTransforms
                if num < 1:
                    continue
                if pinfo.IsScale:
                    if True: #scaling isnt supported in source 2 so just gonna ignore this
                        continue
                    #TODO: may require some experimentation
                    #only eyes(iris) & tongue have scale values, tongue may requre mul not add
                    for tidx in range(pinfo.ScaleIdx, pinfo.ScaleIdx + num):
                        t = poseInfo.Scales[tidx]
                        bn = t.Bone
                        self.boneUsage[bn] = True
                        region = t.JointRegion
                        sca = Vector((t.i,t.j,t.k))
                        self.boneState[bn][2] += sca
                else:
                    for tidx in range(pinfo.TransformIdx, pinfo.TransformIdx + num):
                        t = poseInfo.Transforms[tidx]
                        bn = t.Bone
                        self.boneUsage[bn] = True
                        region = t.JointRegion
                        pos = Vector((t.Translation.X,t.Translation.Y,t.Translation.Z))
                        rot = Quaternion((t.Rotation.r,t.Rotation.i,t.Rotation.j,t.Rotation.k))
                        pos *= weight
                        self.boneState[bn][0] += pos
                        rot_base = Vector(self.boneState[bn][1].to_euler())
                        rot_add = Vector(rot.to_euler()) * weight
                        self.boneState[bn][1] = Euler(rot_base + rot_add).to_quaternion()
                #
            #
        #
    #TODO: include in track calculations
    def applyWrinkles(self,partIndex,tracks):
        numWrinkles = self.wrinkleInfo[partIndex].numWrinkles
        wrinkleIndex = self.wrinkleInfo[partIndex].wrinkleIndex
        for wrInTrack in self.wrinkleMapping[partIndex].keys():
            wrOutTrack = self.wrinkleMapping[partIndex][wrInTrack]
            w = 1.0 - tracks[wrInTrack]
            tracks[wrOutTrack] = Clamp(1 - w * w, 0.0, 1.0)
        #
    #
#
#Context.active_object (head armature)

def RunShit():
    ReadFiles()
    CreateArmature()

    cpo = CP77_FacialSetup()
    cpo.loadJson(facialSetupFile,rigFile)
    cpo.getBaseTransforms()
    tracks = cpo.trackData
    for idx,track in enumerate(track_names):
        if idx==0:
            offset=0
        else:
            offset=bpy.context.scene.frame_end
        ApplyFacialSequenceFromeSceneRid(cpo, actor_signature, track, offset)
    bpy.context.scene.frame_start = 1
        
def ReadFiles():
    print("reading rig...")
    jsonfile = open(rigFile, "r")
    exec("rig = "+jsonfile.read().replace("null", "None").replace("true", "True").replace("false", "False"), globals())
    jsonfile.close()
    
    print("reading facialsetup...")
    jsonfile = open(facialSetupFile, "r")
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
        bone.location = Vector((transform["Translation"]["X"], transform["Translation"]["Y"], transform["Translation"]["Z"]))
        bone.rotation_quaternion = (transform["Rotation"]["r"], transform["Rotation"]["i"], transform["Rotation"]["j"], transform["Rotation"]["k"])
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.armature_apply()
    bpy.ops.object.mode_set(mode='OBJECT')
    armature.rotation_euler = Euler((radians(-90),0,0))
    
def ApplyFacialSequenceFromeSceneRid(cpo, actorSignature, sequence, offset=0):
    ext=animFile.split('.')[-2]
    if ext=='scenerid':
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
    elif ext=='anims':
        actor=anim["Data"]["RootChunk"]
        #find anim data
        animdata = None 
        for i in range(0, len(actor["animations"])):
            name=actor["animations"][i]['Data']["animation"]["Data"]['name']['$value']
            if name==sequence:
                animdata = actor["animations"][i]['Data']["animation"]['Data']
        if not animdata:
            print("couldnt find sequence "+sequence)
            return
    #read buffer
    trackAnimation = {}
    if animdata["animBuffer"]["Data"]["defferedBuffer"]:
        buffer=animdata["animBuffer"]["Data"]["defferedBuffer"]["Bytes"]
    elif animdata["animBuffer"]["Data"]["tempBuffer"]:
        buffer=animdata["animBuffer"]["Data"]["tempBuffer"]["Bytes"]
    br = BinaryReader(base64.b64decode(buffer), Endian.LITTLE)
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
        frameSettings = []
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
            frameSettings.append([trackIndex, trackValue])
        print(frame)
        cpo.getBaseTransforms()
        bpy.context.scene.frame_set(frame)
        cpo.initTracks(frameSettings)
        tracks = cpo.trackData
        cpo.update_tracks(0,tracks)
        cpo.update_tracks(1,tracks)
        cpo.update_tracks(2,tracks)
        for bidx, bn in enumerate(cpo.boneNames):
            if cpo.boneUsage[bidx] == True:
                bpy.data.objects["facialsetup_armature"].pose.bones[bn].location = cpo.boneState[bidx][0]
                bpy.data.objects["facialsetup_armature"].pose.bones[bn].rotation_quaternion = cpo.boneState[bidx][1]
                bpy.data.objects["facialsetup_armature"].pose.bones[bn].keyframe_insert("location", frame=frame)
                bpy.data.objects["facialsetup_armature"].pose.bones[bn].keyframe_insert("rotation_quaternion", frame=frame)  
    print('Completed reading frames')
        
        
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
    
RunShit()