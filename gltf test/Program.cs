using System;
using System.Collections.Generic;
using SharpGLTF.Scenes;
using System.Linq;
using SharpGLTF.Geometry;
using SharpGLTF.Geometry.VertexTypes;
using SharpGLTF.Schema2;

namespace ConsoleApp1
{
    using Vec3 = System.Numerics.Vector3;
    using Vec4 = System.Numerics.Vector4;

    using SKINNEDVERTEX = VertexBuilder<VertexPosition, VertexColor1, VertexJoints8>;
    using SKINNEDMESH = MeshBuilder<VertexPosition, VertexColor1, VertexJoints8>;
    class Program
    {
        static void Main(string[] args)
        {
            Armature rig = createArmature();
            Mesh mesh = createPlane();

            ModelRoot model = ExportGLTF(mesh, rig);
            model.SaveGLTF("test.gltf");
        }
        static ModelRoot ExportGLTF(Mesh mesh, Armature rig)
        {
            var scene = new SceneBuilder();
            var bones = ExportNodes(rig);
            var rootbone = bones.Values.Where(n => n.Parent == null).FirstOrDefault();

            var expMesh = new SKINNEDMESH();
            int indicesCount = mesh.indices.Length;
            var prim = expMesh.UsePrimitive(new SharpGLTF.Materials.MaterialBuilder("Default"));

            for (int i = 0; i < indicesCount; i += 3)
            {
                uint idx0 = mesh.indices[i + 1];
                uint idx1 = mesh.indices[i];
                uint idx2 = mesh.indices[i + 2];

                Vec3 p0 = new Vec3(mesh.vertices[idx0].X, mesh.vertices[idx0].Y, mesh.vertices[idx0].Z);
                Vec3 p1 = new Vec3(mesh.vertices[idx1].X, mesh.vertices[idx1].Y, mesh.vertices[idx1].Z);
                Vec3 p2 = new Vec3(mesh.vertices[idx2].X, mesh.vertices[idx2].Y, mesh.vertices[idx2].Z);

                (int, float)[] bind0 = new (int, float)[8];
                (int, float)[] bind1 = new (int, float)[8];
                (int, float)[] bind2 = new (int, float)[8];

                for (int w = 0; w < mesh.weightcount; w++)
                {
                    bind0[w].Item1 = mesh.jointindex[idx0, w];
                    bind0[w].Item2 = mesh.weights[idx0, w];
                    bind1[w].Item1 = mesh.jointindex[idx1, w];
                    bind1[w].Item2 = mesh.weights[idx1, w];
                    bind2[w].Item1 = mesh.jointindex[idx2, w];
                    bind2[w].Item2 = mesh.weights[idx2, w];
                }

                Vec4 color = new Vec4(1, 1, 1, 1);
                var v0 = new SKINNEDVERTEX(new VertexPosition(p0), new VertexColor1(color), new VertexJoints8(bind0));
                var v1 = new SKINNEDVERTEX(new VertexPosition(p1), new VertexColor1(color), new VertexJoints8(bind1));
                var v2 = new SKINNEDVERTEX(new VertexPosition(p2), new VertexColor1(color), new VertexJoints8(bind2));
                // triangle build

                prim.AddTriangle(v0, v1, v2);
            }
            scene.AddSkinnedMesh(expMesh, rootbone.WorldMatrix, bones.Values.ToArray());
            var model = scene.ToGltf2();

            return model;
        }
        static Mesh createPlane()
        {
            Mesh mesh = new Mesh();
            mesh.vertices = new Vec3[4];
            mesh.vertices[0] = new Vec3(1, 1, 1);
            mesh.vertices[1] = new Vec3(-1,1,-1);
            mesh.vertices[2] = new Vec3(1,1,-1);
            mesh.vertices[3] = new Vec3(-1, 1, 1);

            mesh.indices = new UInt16[3*2];
            mesh.indices[0] = 3; mesh.indices[1] = 1; mesh.indices[2] = 0;
            mesh.indices[3] = 2; mesh.indices[4] = 0; mesh.indices[5] = 1;

            mesh.weightcount = 8;
            mesh.jointindex = new UInt16[4, mesh.weightcount];
            mesh.weights = new float[4, mesh.weightcount];
            for(int i = 0; i < 4; i++)
            {
                for(UInt16 e = 0; e < mesh.weightcount; e++)
                {
                    mesh.jointindex[i, e] = e;
                    mesh.weights[i, e] = 0.125f;
                }
            }
            return mesh;
        }
        static Armature createArmature()
        {
            Armature arma = new Armature();
            arma.boneCount = 10;
            arma.Names = new string[arma.boneCount];
            arma.parent = new Int16[arma.boneCount];
            arma.Translation = new System.Numerics.Vector3[arma.boneCount];

            arma.Names[0] = "Root";
            arma.parent[0] = -1;
            arma.Translation[0] = new Vec3(0, 0, 0);

            for(int i = 1; i < arma.boneCount; i++)
            {
                arma.Names[i] = "bone_" + i;
                arma.parent[i] = (Int16)(i - 1);
                arma.Translation[i] = new Vec3(0.25f, 0.25f, 0.25f);
            }
            return arma;
        }
        static Dictionary<int, NodeBuilder> ExportNodes(Armature rig)
        {
            var bonesMapping = new Dictionary<int, NodeBuilder>();

            // process bones
            for (int i = 0; i < rig.boneCount; i++)
            {
                bonesMapping[i] = CreateBoneHierarchy(rig, i, bonesMapping);
            }

            // find root nodes by looking at the bones that don't have any parent.
            var bonesRoots = bonesMapping.Values.Where(n => n.Parent == null).FirstOrDefault();

            return bonesMapping;
        }
        static NodeBuilder CreateBoneHierarchy(Armature srcBones, int srcIndex, IReadOnlyDictionary<int, NodeBuilder> bonesMap)
        {
            var dstNode = new NodeBuilder(srcBones.Names[srcIndex]);

            var srcParentIdx = srcBones.parent[srcIndex]; // I guess a negative parent index means it's a root bone.

            if (srcParentIdx >= 0) // if this bone has a parent, get the parent NodeBuilder from the bonesMap. 
            {
                var dstParent = bonesMap[srcParentIdx];
                dstParent.AddNode(dstNode);
            }
            
            var t = new Vec3(srcBones.Translation[srcIndex].X, srcBones.Translation[srcIndex].Y, srcBones.Translation[srcIndex].Z);
            dstNode.WithLocalTranslation(t);
            
            return dstNode;
        }
        class Mesh
        {
            public Vec3[] vertices;
            public UInt16[] indices;
            public UInt16[,] jointindex;
            public float[,] weights;
            public int weightcount;
        }
        class Armature
        {
            public int boneCount;
            public string[] Names;
            public Int16[] parent;
            public Vec3[] Translation;
        }
    }
}
