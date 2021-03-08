using System;
using System.IO;
using CP77.CR2W;
using CP77.CR2W.Types;
using GeneralStructs;
using SharpGLTF.Scenes;
using System.Collections.Generic;
using System.Linq;
namespace CP77Rigs
{
    using Vec3 = System.Numerics.Vector3;
    using Quat = System.Numerics.Quaternion;
    using Mat = System.Numerics.Matrix4x4;

    public class CP77Rig
    {
        public static RawArmature ProcessRig(FileStream fs, CR2WFile cr2w)
        {
            RawArmature Rig = new RawArmature();
            Rig.Names = GetboneNames(cr2w, "animRig");
            Rig.BoneCount = Rig.Names.Length;
            Rig.Rig = true;
            long offset = 0;
            offset = fs.Length - 48 * Rig.BoneCount - 2 * Rig.BoneCount;
            Rig.Parent = GetboneParents(fs, Rig.BoneCount, offset);

            offset = fs.Length - 48 * Rig.BoneCount;
            BinaryReader br = new BinaryReader(fs);

            Rig.LocalPosn = new Vec3[Rig.BoneCount];

            for (int i = 0; i < Rig.BoneCount; i++)
            {
                fs.Position = offset + i * 48;
                Rig.LocalPosn[i] = new Vec3(br.ReadSingle(), br.ReadSingle(), br.ReadSingle());
            }

            Rig.LocalRot = new Quat[Rig.BoneCount];

            for (int i = 0; i < Rig.BoneCount; i++)
            {
                fs.Position = offset + i * 48 + 16;
                Rig.LocalRot[i] = new Quat(br.ReadSingle(), br.ReadSingle(), br.ReadSingle(), br.ReadSingle());
            }

            Rig.LocalScale = new Vec3[Rig.BoneCount];
            for (int i = 0; i < Rig.BoneCount; i++)
            {
                fs.Position = offset + i * 48 + 32;
                Rig.LocalScale[i] = new Vec3(br.ReadSingle(), br.ReadSingle(), br.ReadSingle());
            }
            
            // T R S to 4x4 matrix
            Mat[] matrix4Xes = new Mat[Rig.BoneCount];
            for (int i = 0; i < Rig.BoneCount; i++)
            {
                Mat T = Mat.CreateTranslation(Rig.LocalPosn[i]);
                Mat R = Mat.CreateFromQuaternion(Rig.LocalRot[i]);
                Mat S = Mat.CreateScale(Rig.LocalScale[i]);
                matrix4Xes[i] = (R * T)*S ; //  bereal careful with this scaling multiplication, since scale is always one, can't be trusted, R*T is okay
            }

            // creating worldspace matrix by parent multiplication
            for (int i = 0; i < Rig.BoneCount; i++)
            {
                int j = 0;
                j = Rig.Parent[i];
                if (j != -1)
                matrix4Xes[i] = matrix4Xes[i] * matrix4Xes[j];
            }

            Rig.WorldMat = new Mat[Rig.BoneCount];
            for (int i = 0; i < Rig.BoneCount; i++)
            {
                Rig.WorldMat[i] = matrix4Xes[i];
            }

            // if AposeWorld/AposeMS Exists then..... this can be done better i guess...
            if ((cr2w.Chunks[0].data as animRig).APoseMS != null)
            {
                Rig.AposeMSExits = true;
                Rig.AposeMSTrans = new Vec3[Rig.BoneCount];
                Rig.AposeMSRot = new Quat[Rig.BoneCount];
                Rig.AposeMSScale = new Vec3[Rig.BoneCount];
                Rig.APoseMSMat = new Mat[Rig.BoneCount];

                for (int i = 0; i < Rig.BoneCount; i++)
                {
                    float x = (cr2w.Chunks[0].data as animRig).APoseMS[i].Translation.X.val;
                    float y = (cr2w.Chunks[0].data as animRig).APoseMS[i].Translation.Y.val;
                    float z = (cr2w.Chunks[0].data as animRig).APoseMS[i].Translation.Z.val;
                    Mat Tra = Mat.CreateTranslation(new Vec3(x, y, z));
                    float I = (cr2w.Chunks[0].data as animRig).APoseMS[i].Rotation.I.val;
                    float J = (cr2w.Chunks[0].data as animRig).APoseMS[i].Rotation.J.val;
                    float K = (cr2w.Chunks[0].data as animRig).APoseMS[i].Rotation.K.val;
                    float R = (cr2w.Chunks[0].data as animRig).APoseMS[i].Rotation.R.val;
                    Mat Rot = Mat.CreateFromQuaternion(new Quat(I, J, K, R));
                    float t = (cr2w.Chunks[0].data as animRig).APoseMS[i].Scale.X.val;
                    float u = (cr2w.Chunks[0].data as animRig).APoseMS[i].Scale.Y.val;
                    float v = (cr2w.Chunks[0].data as animRig).APoseMS[i].Scale.Z.val;
                    Mat Sca = Mat.CreateScale(new Vec3(t, u, v));

                    Rig.APoseMSMat[i] = (Rot * Tra) * Sca;
                }
            }

            // not sure how APose works or how the matrix multiplication will be, maybe its a recursive mul 
            if ((cr2w.Chunks[0].data as animRig).APoseLS != null)
            {
                Rig.AposeLSExits = true;
                Rig.AposeLSTrans = new Vec3[Rig.BoneCount];
                Rig.AposeLSRot = new Quat[Rig.BoneCount];
                Rig.AposeLSScale = new Vec3[Rig.BoneCount];
                Rig.APoseLSMat = new Mat[Rig.BoneCount];

                Mat[] matrix4X4s = new Mat[Rig.BoneCount];
                for (int i = 0; i < Rig.BoneCount; i++)
                {
                    float x = (cr2w.Chunks[0].data as animRig).APoseLS[i].Translation.X.val;
                    float y = (cr2w.Chunks[0].data as animRig).APoseLS[i].Translation.Y.val;
                    float z = (cr2w.Chunks[0].data as animRig).APoseLS[i].Translation.Z.val;
                    Mat Tra = Mat.CreateTranslation(new Vec3(x, y, z));
                    float I = (cr2w.Chunks[0].data as animRig).APoseLS[i].Rotation.I.val;
                    float J = (cr2w.Chunks[0].data as animRig).APoseLS[i].Rotation.J.val;
                    float K = (cr2w.Chunks[0].data as animRig).APoseLS[i].Rotation.K.val;
                    float R = (cr2w.Chunks[0].data as animRig).APoseLS[i].Rotation.R.val;
                    Mat Rot = Mat.CreateFromQuaternion(new Quat(I, J, K, R));
                    float t = (cr2w.Chunks[0].data as animRig).APoseLS[i].Scale.X.val;
                    float u = (cr2w.Chunks[0].data as animRig).APoseLS[i].Scale.Y.val;
                    float v = (cr2w.Chunks[0].data as animRig).APoseLS[i].Scale.Z.val;
                    Mat Sca = Mat.CreateScale(new Vec3(t, u, v));

                    matrix4X4s[i] = (Rot * Tra) * Sca;
                }
                // recursive mul of AposeLS gives correct worlspace
                for (int i = 0; i < Rig.BoneCount; i++)
                {
                    int j = 0;
                    j = Rig.Parent[i];
                    if (j != -1)
                        matrix4X4s[i] = matrix4X4s[i] * matrix4X4s[j];
                }
                for (int i = 0; i < Rig.BoneCount; i++)
                {
                    Rig.APoseLSMat[i] = matrix4X4s[i];
                }
            }

            ExportNodes(Rig);
            return Rig;
        }
        static Int16[] GetboneParents(FileStream fs, int bonesCount, long offset)
        {
            BinaryReader br = new BinaryReader(fs);
            fs.Position = offset;

            Int16[] boneParents = new Int16[bonesCount];
            for (int i = 0; i < bonesCount; i++)
            {
                boneParents[i] = br.ReadInt16();
            }
            return boneParents;
        }
        static string[] GetboneNames(CR2WFile cr2w, string Type)
        {
            int last = 0;
            for (int i = 0; i < cr2w.Chunks.Count; i++)
            {
                if (cr2w.Chunks[i].REDType == Type)
                {
                    last = i;
                }
            }
            int boneCount = 0;
            if (Type == "animRig")
                boneCount = (cr2w.Chunks[last].data as animRig).BoneNames.Count;
            else
                boneCount = (cr2w.Chunks[last].data as CMesh).BoneNames.Count;


            string[] bonenames = new string[boneCount];
            for (int i = 0; i < boneCount; i++)
            {
                if (Type == "animRig")
                    bonenames[i] = (cr2w.Chunks[last].data as animRig).BoneNames[i].Value;
                else
                    bonenames[i] = (cr2w.Chunks[last].data as CMesh).BoneNames[i].Value;
            }

            return bonenames;
        }
        static void ExportNodes(RawArmature rig)
        {
            var bonesMapping = new Dictionary<int, NodeBuilder>();

            // process bones
            for (int i = 0; i < rig.BoneCount; i++)
            {
                bonesMapping[i] = CreateBoneHierarchy(rig, i, bonesMapping);
            }

            // find root nodes by looking at the bones that don't have any parent.
            //var bonesRoots = bonesMapping.Values.Where(n => n.Parent == null);

            var scene = new SceneBuilder();
            scene.AddNode(bonesMapping[0]); // bonesMapping[0] is the root node, it has no parent

            var model = scene.ToGltf2();
            model.SaveGLTF("test.gltf");
        }
        
        // recursive helper class
        static NodeBuilder CreateBoneHierarchy(RawArmature srcBones, int srcIndex, IReadOnlyDictionary<int, NodeBuilder> bonesMap)
        {
            var dstNode = new NodeBuilder(srcBones.Names[srcIndex]);

            var srcParentIdx = srcBones.Parent[srcIndex]; // I guess a negative parent index means it's a root bone.

            if (srcParentIdx >= 0) // if this bone has a parent, get the parent NodeBuilder from the bonesMap. 
            {
                var dstParent = bonesMap[srcParentIdx];
                dstParent.AddNode(dstNode);
            }

            // fill transform or any other property...

            var s = new Vec3(srcBones.LocalScale[srcIndex].X, srcBones.LocalScale[srcIndex].Y, srcBones.LocalScale[srcIndex].Z);
            var r = new Quat(srcBones.LocalRot[srcIndex].X, srcBones.LocalRot[srcIndex].Y, srcBones.LocalRot[srcIndex].Z, srcBones.LocalRot[srcIndex].W);
            var t = new Vec3(srcBones.LocalPosn[srcIndex].X, srcBones.LocalPosn[srcIndex].Y, srcBones.LocalPosn[srcIndex].Z);

            dstNode.WithLocalTranslation(t).WithLocalRotation(r).WithLocalScale(s);
            return dstNode;
        }
    }
}
