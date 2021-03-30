using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.IO;
using WolvenKit.RED4.GeneralStructs;
using SharpGLTF.Schema2;
using SharpGLTF.IO;
using WolvenKit.RED4.RigFile;
using WolvenKit.RED4.CR2W;

namespace WolvenKit.RED4.MeshFile
{
    using Vec4 = System.Numerics.Vector4;
    using Vec2 = System.Numerics.Vector2;
    using Vec3 = System.Numerics.Vector3;
    public class MESHIMPORTER
    {
        public static void Import(string glTFFileName, Stream meshStream)
        {
            var model = ModelRoot.Load(glTFFileName);

            List<RawMeshContainer> Meshes = new List<RawMeshContainer>();
            for (int i = 0; i < model.LogicalMeshes.Count; i++)
            {
                Meshes.Add(GltfMeshToRawContainer(model.LogicalMeshes[i]));
            }

            Vec3 max = new Vec3(Meshes[0].vertices[0].X, Meshes[0].vertices[0].Y, Meshes[0].vertices[0].Z);
            Vec3 min = new Vec3(Meshes[0].vertices[0].X, Meshes[0].vertices[0].Y, Meshes[0].vertices[0].Z);
            for(int e = 0; e < Meshes.Count; e++)
                for (int i = 0; i < Meshes[e].vertices.Length; i++)
                {
                    if (Meshes[e].vertices[i].X >= max.X)
                        max.X = Meshes[e].vertices[i].X;
                    if (Meshes[e].vertices[i].Y >= max.Y)
                        max.Y = Meshes[e].vertices[i].Y;
                    if (Meshes[e].vertices[i].Z >= max.Z)
                        max.Z = Meshes[e].vertices[i].Z;
                    if (Meshes[e].vertices[i].X <= min.X)
                        min.X = Meshes[e].vertices[i].X;
                    if (Meshes[e].vertices[i].Y <= min.Y)
                        min.Y = Meshes[e].vertices[i].Y;
                    if (Meshes[e].vertices[i].Z <= min.Z)
                        min.Z = Meshes[e].vertices[i].Z;
                }
            Vec4 QuantScale = new Vec4((max.X - min.X) / 2, (max.Y - min.Y) / 2, (max.Z - min.Z) / 2, 0);
            Vec4 QuantTrans = new Vec4((max.X + min.X) / 2, (max.Y + min.Y) / 2, (max.Z + min.Z) / 2, 1);

            string[] bones = new string[model.LogicalSkins[0].JointsCount];
            for (int i = 0; i < model.LogicalSkins[0].JointsCount; i++)
                bones[i] = model.LogicalSkins[0].GetJoint(i).Joint.Name;


            var cr2w = CP77.CR2W.ModTools.TryReadCr2WFile(meshStream);
            string[] meshbones = RIG.GetboneNames(cr2w, "CMesh");

            for (int i = 0; i < Meshes.Count; i++)
                for(int e = 0; e < Meshes[i].vertices.Length; e++)
                    for(int eye = 0; eye < Meshes[i].weightcount; eye++)
                    {
                        string name = bones[Meshes[i].boneindices[e, eye]];
                        for(UInt16 t = 0; t < meshbones.Length; t++)
                        {
                            if (name == meshbones[t])
                                Meshes[i].boneindices[e, eye] = t;
                        }
                    }

            List<Re4MeshContainer> expMeshes = new List<Re4MeshContainer>();

            for (int i = 0; i < Meshes.Count; i++)
                expMeshes.Add(RawMeshToRE4Mesh(Meshes[i],QuantScale,QuantTrans));

            MemoryStream meshBuffer = new MemoryStream();
            MeshesInfo meshesInfo = BufferWriter(expMeshes, ref meshBuffer);

        }
        static RawMeshContainer GltfMeshToRawContainer(Mesh mesh)
        {

            List<string> accessors = mesh.Primitives[0].VertexAccessors.Keys.ToList();

            List<uint> indices = mesh.Primitives[0].GetIndices().ToList();

            List<Vec3> vertices = new List<Vec3>();
            if (accessors.Contains("POSITION"))
                vertices = mesh.Primitives[0].GetVertices("POSITION").AsVector3Array().ToList();

            List<Vec3> normals = new List<Vec3>();
            if (accessors.Contains("NORMAL"))
                normals = mesh.Primitives[0].GetVertices("NORMAL").AsVector3Array().ToList();

            List<Vec4> tangents = new List<Vec4>();
            if (accessors.Contains("TANGENT"))
                tangents = mesh.Primitives[0].GetVertices("TANGENT").AsVector4Array().ToList();

            List<Vec4> colors = new List<Vec4>();
            if (accessors.Contains("COLOR_0"))
                colors = mesh.Primitives[0].GetVertices("COLOR_0").AsVector4Array().ToList();

            List<Vec2> tx0coords = new List<Vec2>();
            if (accessors.Contains("TEXCOORD_0"))
                tx0coords = mesh.Primitives[0].GetVertices("TEXCOORD_0").AsVector2Array().ToList();

            List<Vec2> tx1coords = new List<Vec2>();
            if (accessors.Contains("TEXCOORD_1"))
                tx1coords = mesh.Primitives[0].GetVertices("TEXCOORD_1").AsVector2Array().ToList();

            List<Vec4> joints0 = new List<Vec4>();
            if (accessors.Contains("JOINTS_0"))
                joints0 = mesh.Primitives[0].GetVertices("JOINTS_0").AsVector4Array().ToList();

            List<Vec4> joints1 = new List<Vec4>();
            if (accessors.Contains("JOINTS_1"))
                joints1 = mesh.Primitives[0].GetVertices("JOINTS_1").AsVector4Array().ToList();

            List<Vec4> weights0 = new List<Vec4>();
            if (accessors.Contains("WEIGHTS_0"))
                weights0 = mesh.Primitives[0].GetVertices("WEIGHTS_0").AsVector4Array().ToList();

            List<Vec4> weights1 = new List<Vec4>();
            if (accessors.Contains("WEIGHTS_1"))
                weights1 = mesh.Primitives[0].GetVertices("WEIGHTS_1").AsVector4Array().ToList();

            UInt32 weightcount = 0;

            if (joints0.Count != 0)
                weightcount += 4;
            if (joints1.Count != 0)
                weightcount += 4;

            int vertCount = vertices.Count;
            UInt16[,] boneindices = new UInt16[vertCount, weightcount];
            float[,] weights = new float[vertCount, weightcount];

            for (int i = 0; i < vertCount; i++)
            {
                if (joints0.Count != 0)
                {
                    boneindices[i, 0] = (UInt16)joints0[i].X;
                    boneindices[i, 1] = (UInt16)joints0[i].Y;
                    boneindices[i, 2] = (UInt16)joints0[i].Z;
                    boneindices[i, 3] = (UInt16)joints0[i].W;

                    weights[i, 0] = weights0[i].X;
                    weights[i, 1] = weights0[i].Y;
                    weights[i, 2] = weights0[i].Z;
                    weights[i, 3] = weights0[i].W;
                }
                if (joints1.Count != 0)
                {
                    boneindices[i, 4] = (UInt16)joints1[i].X;
                    boneindices[i, 5] = (UInt16)joints1[i].Y;
                    boneindices[i, 6] = (UInt16)joints1[i].Z;
                    boneindices[i, 7] = (UInt16)joints1[i].W;

                    weights[i, 4] = weights1[i].X;
                    weights[i, 5] = weights1[i].Y;
                    weights[i, 6] = weights1[i].Z;
                    weights[i, 7] = weights1[i].W;
                }
            }

            RawMeshContainer rawMeshContainer = new RawMeshContainer()
            {
                vertices = vertices.ToArray(),
                indices = indices.ToArray(),
                tx0coords = tx0coords.ToArray(),
                tx1coords = tx1coords.ToArray(),
                normals = normals.ToArray(),
                tangents = tangents.ToArray(),
                colors = colors.ToArray(),
                boneindices = boneindices,
                weights = weights,
                weightcount = weightcount
            };

            return rawMeshContainer;
        }
        
        static Re4MeshContainer RawMeshToRE4Mesh(RawMeshContainer mesh, Vec4 qScale, Vec4 qTrans)
        {
            int vertCount = mesh.vertices.Length;
            Int16[,] ExpVerts = new Int16[vertCount, 3];
            UInt32[] Nor32s = new UInt32[vertCount];
            UInt32[] Tan32s = new UInt32[vertCount];

            for (int i = 0; i < vertCount; i++)
            {
                float x = (mesh.vertices[i].X - qTrans.X) / qScale.X;
                float y = (mesh.vertices[i].Y - qTrans.Y) / qScale.Y;
                float z = (mesh.vertices[i].Z - qTrans.Z) / qScale.Z;
                ExpVerts[i, 0] = Convert.ToInt16(x * 32767);
                ExpVerts[i, 1] = Convert.ToInt16(y * 32767);
                ExpVerts[i, 2] = Convert.ToInt16(z * 32767);
            }

            // managing normals
            for (int i = 0; i < vertCount; i++)
            {
                Vec4 v = new Vec4(mesh.normals[i], 0); // for normal w == 0
                Nor32s[i] = Converters.Vec4ToU32(v);
            }
            // managing tangents

            for (int i = 0; i < vertCount; i++)
            {
                Vec4 v = mesh.tangents[i]; // for tangents w == 1 or -1
                Tan32s[i] = Converters.Vec4ToU32(v);
            }


            UInt16[,] uv0s = new UInt16[vertCount, 2];

            for(int i = 0; i < mesh.tx0coords.Length; i++)
            {
                uv0s[i, 0] = Converters.converthf(mesh.tx0coords[i].X);
                uv0s[i, 1] = Converters.converthf(mesh.tx0coords[i].Y);
            }

            UInt16[,] uv1s = new UInt16[vertCount, 2];

            for (int i = 0; i < mesh.tx0coords.Length; i++)
            {
                uv1s[i, 0] = Converters.converthf(mesh.tx1coords[i].X);
                uv1s[i, 1] = Converters.converthf(mesh.tx1coords[i].Y);
            }

            Byte[,] colors = new byte[vertCount, 4];

            for(int i = 0; i < mesh.colors.Length; i++)
            {
                colors[i, 0] = Convert.ToByte(mesh.colors[i].X * 255);
                colors[i, 1] = Convert.ToByte(mesh.colors[i].Y * 255);
                colors[i, 2] = Convert.ToByte(mesh.colors[i].Z * 255);
                colors[i, 3] = Convert.ToByte(mesh.colors[i].W * 255);
            }
            UInt32 weightcount = mesh.weightcount;

            Byte[,] boneindices = new byte[vertCount, weightcount];
            for (int i = 0; i < vertCount; i++)
                for (int e = 0; e < weightcount; e++)
                    boneindices[i, e] = Convert.ToByte(mesh.boneindices[i, e]); // mesh.boneindices are supposed to be processed
                                                                                // (updated according to the mesh bones rather than rig bones) before putting here

            Byte[,] weights = new byte[vertCount, weightcount];
            for (int i = 0; i < vertCount; i++)
            {
                for (int e = 0; e < weightcount; e++)
                {
                    weights[i, e] = Convert.ToByte(mesh.weights[i, e] * 255);
                }
                // weight summing can cause problems here, sometimes sum >= 256, idk how to fix them yet
            }

            UInt16[] indices = new UInt16[mesh.indices.Length];
            for (int i = 0; i < mesh.indices.Length; i++)
                indices[i] = Convert.ToUInt16(mesh.indices[i]);

            Re4MeshContainer Re4Mesh = new Re4MeshContainer()
            {
                ExpVerts = ExpVerts,
                Nor32s = Nor32s,
                Tan32s = Tan32s,
                uv0s = uv0s,
                uv1s = uv1s,
                colors = colors,
                boneindices = boneindices,
                weights = weights,
                weightcount = weightcount,
                indices = indices
            };
            return Re4Mesh;
        }
        static MeshesInfo BufferWriter(List<Re4MeshContainer> expMeshes, ref MemoryStream ms)
        {
            int meshC = expMeshes.Count;

            UInt32[] vertCounts = new UInt32[meshC];
            UInt32[] indCounts = new UInt32[meshC];
            UInt32[] vertOffsets = new UInt32[meshC];
            UInt32[] tx0Offsets = new UInt32[meshC];
            UInt32[] normalOffsets = new UInt32[meshC];
            UInt32[] colorOffsets = new UInt32[meshC];
            UInt32[] unknownOffsets = new UInt32[meshC];
            UInt32[] indicesOffsets = new UInt32[meshC];
            UInt32[] vpStrides = new UInt32[meshC];
            UInt32[] weightcounts = new UInt32[meshC];
            UInt32[] LODLvl = new UInt32[meshC];        // can be determined based on a mesh name which is remained to be parsed an managed


            BinaryWriter bw = new BinaryWriter(ms);
            

            for(int i = 0; i < expMeshes.Count; i++)
            {
                int vertCount = expMeshes[i].ExpVerts.Length / 3;

                vertCounts[i] = (UInt32)vertCount;
                vertOffsets[i] = (UInt32)ms.Position;

                // haven't taken extra data into consideration
                vpStrides[i] = expMeshes[i].weightcount * 2 + 8;
                weightcounts[i] = expMeshes[i].weightcount;

                for (int e = 0; e < vertCount; e++)
                {
                    bw.Write(expMeshes[i].ExpVerts[e, 0]);
                    bw.Write(expMeshes[i].ExpVerts[e, 1]);
                    bw.Write(expMeshes[i].ExpVerts[e, 2]);
                    bw.Write((Int16)32767);
                    for (int eye = 0; eye < expMeshes[i].weightcount; eye++)
                        bw.Write(expMeshes[i].boneindices[e, eye]);

                    for (int eye = 0; eye < expMeshes[i].weightcount; eye++)
                        bw.Write(expMeshes[i].weights[e, eye]);
                }

                tx0Offsets[i] = (UInt32)ms.Position;
                for (int e = 0; e < vertCount; e++)
                {
                    bw.Write(expMeshes[i].uv0s[e, 0]);
                    bw.Write(expMeshes[i].uv0s[e, 1]);
                }

                // padding writer betwwen uv0 and normals, if required
                /*
                if(((UInt64)ms.Length % 16) != 0)
                {
                    int tempCount = (int)((((UInt64)ms.Length / 16) + 1) * 16 - ((UInt64)ms.Length % 16));
                    Byte[] bytes = new Byte[tempCount];
                    bw.Write(bytes);
                }
                */
                normalOffsets[i] = (UInt32)ms.Position;
                for (int e = 0; e < vertCount; e++)
                {
                    bw.Write(expMeshes[i].Nor32s[e]);
                    bw.Write(expMeshes[i].Tan32s[e]);
                }

                // padding writer betwwen nors/tans and colors/uv1s, if required
                /*
                if(((UInt64)ms.Length % 16) != 0)
                {
                    int tempCount = (int)((((UInt64)ms.Length / 16) + 1) * 16 - ((UInt64)ms.Length % 16));
                    Byte[] bytes = new Byte[tempCount];
                    bw.Write(bytes);
                }
                */

                colorOffsets[i] = (UInt32)ms.Position;
                for (int e = 0; e < vertCount; e++)
                {
                    bw.Write(expMeshes[i].colors[e, 0]);
                    bw.Write(expMeshes[i].colors[e, 1]);
                    bw.Write(expMeshes[i].colors[e, 2]);
                    bw.Write(expMeshes[i].colors[e, 3]);
                    bw.Write(expMeshes[i].uv1s[e, 0]);
                    bw.Write(expMeshes[i].uv1s[e, 1]);
                }

                // after colors and uv1s some crap data is there, dunno what, (looking at judy head buffer)
                // padding writer if necessary
                /*
                if(((UInt64)ms.Length % 16) != 0)
                {
                    int tempCount = (int)((((UInt64)ms.Length / 16) + 1) * 16 - ((UInt64)ms.Length % 16));
                    Byte[] bytes = new Byte[tempCount];
                    bw.Write(bytes);
                }
                */
                unknownOffsets[i] = (UInt32)ms.Position;
            }

            for(int i = 0; i < expMeshes.Count; i++)
            {
                int indCount = expMeshes[i].indices.Length;
                indCounts[i] = (UInt32)indCount;

                indicesOffsets[i] = (UInt32)ms.Position;
                for (int e = 0; e < indCount; e++)
                    bw.Write(expMeshes[i].indices[e]);
            }

            MeshesInfo meshesInfo = new MeshesInfo()
            {
                vertCounts = vertCounts,
                indCounts = indCounts,
                vertOffsets = vertOffsets,
                tx0Offsets = tx0Offsets,
                normalOffsets = normalOffsets,
                colorOffsets = colorOffsets,
                unknownOffsets = unknownOffsets,
                indicesOffsets = indicesOffsets,
                vpStrides = vpStrides,
                weightcounts = weightcounts,
                LODLvl = LODLvl
            };

            return meshesInfo;
        }
    }
}
