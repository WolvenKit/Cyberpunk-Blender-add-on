using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using CP77.CR2W;
using CP77.CR2W.Types;
using WolvenKit.Common.Oodle;
using GeneralStructs;
using SharpGLTF.Geometry;
using SharpGLTF.Geometry.VertexTypes;
using SharpGLTF.Materials;
using SharpGLTF.Scenes;
using CP77.RigFile;
using SharpGLTF.Schema2;

namespace CP77.MeshFile
{
    using Vec4 = System.Numerics.Vector4;
    using Vec3 = System.Numerics.Vector3;
    using Vec2 = System.Numerics.Vector2;
    using Quat = System.Numerics.Quaternion;

    using SKINNEDVERTEX = VertexBuilder<VertexPositionNormalTangent, VertexColor1Texture2, VertexJoints8>;
    using SKINNEDMESH = MeshBuilder<VertexPositionNormalTangent, VertexColor1Texture2, VertexJoints8>;
    using RIGIDVERTEX = VertexBuilder<VertexPositionNormalTangent, VertexColor1Texture2, VertexEmpty>;
    using RIGIDMESH = MeshBuilder<VertexPositionNormalTangent, VertexColor1Texture2, VertexEmpty>;
    using VPNT = VertexPositionNormalTangent;
    using VCT = VertexColor1Texture2;
    using VJ = VertexJoints8;

    class MeshFile
    {
        public static void ExportMeshWithoutRig(MemoryStream meshMstream,bool Filter)
        {
            List<RawMeshContainer> expMeshes = new List<RawMeshContainer>();

            BinaryReader br = new BinaryReader(meshMstream);
            CR2WFile cr2w = new CR2WFile();
            br.BaseStream.Seek(0, SeekOrigin.Begin);
            cr2w.Read(br);

            BuffersInfo buffinfo = Getbuffersinfo(meshMstream, cr2w);
            MemoryStream ms = new MemoryStream(buffinfo.buffers[buffinfo.meshbufferindex]);
            MeshesInfo meshinfo = GetMeshesinfo(cr2w);
            for(int i = 0; i < meshinfo.meshC; i ++)
            {
                if (meshinfo.LODLvl[i] != 1 && Filter)
                    continue;
                RawMeshContainer mesh = ContainRawMesh(ms, meshinfo.vertCounts[i], meshinfo.indCounts[i], meshinfo.vertOffsets[i], meshinfo.tx0Offsets[i], meshinfo.normalOffsets[i], meshinfo.colorOffsets[i], meshinfo.unknownOffsets[i], meshinfo.indicesOffsets[i], meshinfo.vpStrides[i], meshinfo.qScale, meshinfo.qTrans, meshinfo.weightcounts[i]);
                expMeshes.Add(mesh);
            }
            ModelRoot model = RawRigidMeshesToGLTF(expMeshes);
            model.SaveGLTF("3drigid.gltf");
        }
        public static void ExportMeshWithRig(MemoryStream meshMstream, MemoryStream rigMStream, bool Filter)
        {
            List<RawMeshContainer> expMeshes = new List<RawMeshContainer>();

            BinaryReader br = new BinaryReader(meshMstream);
            CR2WFile cr2w = new CR2WFile();
            br.BaseStream.Seek(0, SeekOrigin.Begin);
            cr2w.Read(br);

            BuffersInfo buffinfo = Getbuffersinfo(meshMstream, cr2w);
            MemoryStream ms = new MemoryStream(buffinfo.buffers[buffinfo.meshbufferindex]);
            MeshesInfo meshinfo = GetMeshesinfo(cr2w);
            for (int i = 0; i < meshinfo.meshC; i++)
            {
                if (meshinfo.LODLvl[i] != 1 && Filter)
                    continue;
                RawMeshContainer mesh = ContainRawMesh(ms, meshinfo.vertCounts[i], meshinfo.indCounts[i], meshinfo.vertOffsets[i], meshinfo.tx0Offsets[i], meshinfo.normalOffsets[i], meshinfo.colorOffsets[i], meshinfo.unknownOffsets[i], meshinfo.indicesOffsets[i], meshinfo.vpStrides[i], meshinfo.qScale, meshinfo.qTrans, meshinfo.weightcounts[i]);
                expMeshes.Add(mesh);
            }

            MeshBones bones = new MeshBones();
            bones.Names = RigFile.RigFile.GetboneNames(cr2w, "CMesh");
            bones.WorldPosn = GetMeshBonesPosn(cr2w);

            RawArmature Rig = RigFile.RigFile.ProcessRig(rigMStream);
            UpdateMeshJoints(ref expMeshes, Rig, bones);

            ModelRoot model = RawSkinnedMeshesToGLTF(expMeshes,Rig);

            model.SaveGLTF("3dskinned.gltf");
        }
        static Vec3[] GetMeshBonesPosn(CR2WFile cr2w)
        {
            int Index = 0;
            for (int i = 0; i < cr2w.Chunks.Count; i++)
            {
                if (cr2w.Chunks[i].REDType == "rendRenderMeshBlob")
                {
                    Index = i;
                }
            }
            int boneCount = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.BonePositions.Count;
            Vec3[] posn = new Vec3[boneCount];
            float x, y, z = 0;
            for (int i = 0; i < boneCount; i++)
            {
                x = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.BonePositions[i].X.val;
                y = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.BonePositions[i].Y.val;
                z = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.BonePositions[i].Z.val;
                posn[i] = new Vec3(x, y, z);
            }
            return posn;
        }
        static MeshesInfo GetMeshesinfo(CR2WFile cr2w)
        {
            int Index = 0;
            for (int i = 0; i < cr2w.Chunks.Count; i++)
            {
                if (cr2w.Chunks[i].REDType == "rendRenderMeshBlob")
                {
                    Index = i;
                }
            }
            int meshC = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos.Count;

            UInt32[] vertCounts = new UInt32[meshC];
            UInt32[] indCounts = new UInt32[meshC];
            UInt32[] vertOffsets = new UInt32[meshC];
            UInt32[] tx0Offsets = new UInt32[meshC];
            UInt32[] normalOffsets = new UInt32[meshC];
            UInt32[] colorOffsets = new UInt32[meshC];
            UInt32[] unknownOffsets = new UInt32[meshC];
            UInt32[] indicesOffsets = new UInt32[meshC];
            UInt32[] vpStrides = new UInt32[meshC];
            UInt32[] LODLvl = new UInt32[meshC];
            for (int i = 0; i < meshC; i++)
            {
                vertCounts[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].NumVertices.val;
                indCounts[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].NumIndices.val;
                vertOffsets[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkVertices.ByteOffsets[0].val;
                tx0Offsets[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkVertices.ByteOffsets[1].val;
                normalOffsets[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkVertices.ByteOffsets[2].val;
                colorOffsets[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkVertices.ByteOffsets[3].val;
                unknownOffsets[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkVertices.ByteOffsets[4].val;

                if ((cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkIndices.TeOffset == null)
                {
                    indicesOffsets[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.IndexBufferOffset.val;
                }
                else
                {
                    indicesOffsets[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.IndexBufferOffset.val + (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkIndices.TeOffset.val;
                }
                vpStrides[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkVertices.VertexLayout.SlotStrides[0].val;
                LODLvl[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].LodMask.val;
            }
            Vector4 qSc = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.QuantizationScale;
            Vector4 qTr = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.QuantizationOffset;

            Vec4 qScale = new Vec4(qSc.X.val, qSc.Y.val, qSc.Z.val, qSc.W.val);
            Vec4 qTrans = new Vec4(qTr.X.val, qTr.Y.val, qTr.Z.val, qTr.W.val);

            // getting number of weights for the meshes
            UInt32[] weightcounts = new UInt32[meshC];
            int count = 0;
            UInt32 counter = 0;
            string checker = string.Empty;
            for (int i = 0; i < meshC; i++)
            {
                count = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkVertices.VertexLayout.Elements.Count;
                counter = 0;
                for (int e = 0; e < count; e++)
                {
                    checker = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkVertices.VertexLayout.Elements[e].Usage.Value[0];
                    if (checker == "PS_SkinIndices")
                        counter++;
                }
                weightcounts[i] = counter * 4;
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
                LODLvl = LODLvl,
                qScale = qScale,
                qTrans = qTrans,
                meshC = meshC
            };
            return meshesInfo;
        }
        static RawMeshContainer ContainRawMesh(MemoryStream gfs, UInt32 vertCount, UInt32 indCount, UInt32 vertOffset, UInt32 tx0Offset, UInt32 normalOffset, UInt32 colorOffset, UInt32 unknownOffset, UInt32 indOffset, UInt32 vpStride, Vec4 qScale, Vec4 qTrans, UInt32 weightcount)
        {
            BinaryReader gbr = new BinaryReader(gfs);

            Vec3[] vertices = new Vec3[vertCount];
            uint[] indices = new uint[indCount];
            Vec2[] tx0coords = new Vec2[vertCount];
            Vec3[] normals = new Vec3[vertCount];
            Vec4[] tangents = new Vec4[vertCount];
            Vec4[] colors = new Vec4[vertCount];
            Vec2[] tx1coords = new Vec2[vertCount];
            float[,] weights = new float[vertCount, weightcount];
            UInt16[,] boneindices = new UInt16[vertCount, weightcount];

            // geting vertices
            for (int i = 0; i < vertCount; i++)
            {
                gfs.Position = vertOffset + i * vpStride;

                float x = (gbr.ReadInt16() / 32767f) * qScale.X + qTrans.X;
                float y = (gbr.ReadInt16() / 32767f) * qScale.Y + qTrans.Y;
                float z = (gbr.ReadInt16() / 32767f) * qScale.Z + qTrans.Z;
                vertices[i] = new Vec3(x, y, z);
            }
            // got vertices

            float[] values = new float[vertCount * 2];

            if (tx0Offset != 0)
            {
                // getting texturecoord0 as half floats
                gfs.Position = tx0Offset;
                for (int i = 0; i < vertCount * 2; i++)
                {
                    UInt16 read = gbr.ReadUInt16();
                    values[i] = Converters.hfconvert(read);
                }
                for (int i = 0; i < vertCount; i++)
                {
                    tx0coords[i] = new Vec2(values[2 * i], values[2 * i + 1]);
                }
                // got texturecoord0 as half floats
            }

            UInt32 NorRead32;
            // getting 10bit normals
            for (int i = 0; i < vertCount; i++)
            {
                gfs.Position = normalOffset + 8 * i;
                NorRead32 = gbr.ReadUInt32();
                Vec4 tempv = Converters.TenBitShifted(NorRead32);
                normals[i] = new Vec3(tempv.X, tempv.Y, tempv.Z);
            }
            // got 10bit normals

            // getting 10bit tangents
            for (int i = 0; i < vertCount; i++)
            {
                gfs.Position = normalOffset + 4 + 8 * i;
                NorRead32 = gbr.ReadUInt32();
                Vec4 tempv = Converters.TenBitShifted(NorRead32);
                tangents[i] = new Vec4(tempv.X, tempv.Y, tempv.Z, 1f);
            }


            if (colorOffset != 0)
            {
                gfs.Position = colorOffset + 4;
                // getting texturecoord1 as half floats
                for (int i = 0; i < vertCount * 2; i++)
                {
                    UInt16 read = gbr.ReadUInt16();
                    values[i] = Converters.hfconvert(read);
                    if (i % 2 != 0)
                        gfs.Position += 4;
                }
                for (int i = 0; i < vertCount; i++)
                {
                    tx1coords[i] = new Vec2(values[2 * i], values[2 * i + 1]);
                }
                // got texturecoord1 as half floats
            }

            if (colorOffset != 0)
            {
                // getting vert colors, not sure of the format TBH RN,just a hush, may not work, lulz
                for (int i = 0; i < vertCount; i++)
                {
                    gfs.Position = colorOffset + i * 8;
                    Vec4 tempv = new Vec4(gbr.ReadByte() / 255f, gbr.ReadByte() / 255f, gbr.ReadByte() / 255f, gbr.ReadByte() / 255f);
                    colors[i] = new Vec4(tempv.X, tempv.Y, tempv.Z, tempv.W);
                }
                // got vert colors
            }

            // getting bone indices
            for (int i = 0; i < vertCount; i++)
            {
                gfs.Position = vertOffset + i * vpStride + 8;
                for (int e = 0; e < weightcount; e++)
                {
                    boneindices[i, e] = gbr.ReadByte();
                }
            }
            // got bone indexes

            // getting weights
            for (int i = 0; i < vertCount; i++)
            {
                gfs.Position = vertOffset + i * vpStride + 8 + weightcount;
                for (int e = 0; e < weightcount; e++)
                {
                    weights[i, e] = gbr.ReadByte() / 255f;
                }
            }
            // got weights

            // getting uint16 faces/indices
            gfs.Position = indOffset;
            for (int i = 0; i < indCount; i++)
            {
                indices[i] = gbr.ReadUInt16();
            }
            // got uint16 faces/indices

            RawMeshContainer mesh = new RawMeshContainer()
            {
                vertices = vertices,
                indices = indices,
                tx0coords = tx0coords,
                normals = normals,
                tangents = tangents,
                colors = colors,
                tx1coords = tx1coords,
                boneindices = boneindices,
                weights = weights,
                weightcount = weightcount
            };
            return mesh;
        }

        static void UpdateMeshJoints(ref List<RawMeshContainer> expMeshes, RawArmature Rig, MeshBones Bones)
        {
            // updating mesh bone indexes
            for (int i = 0; i < expMeshes.Count; i++)
            {
                for (int e = 0; e < expMeshes[i].vertices.Length; e++)
                {
                    for (int eye = 0; eye < expMeshes[i].weightcount; eye++)
                    {
                        for (UInt16 r = 0; r < Rig.BoneCount; r++)
                        {
                            if (Rig.Names[r] == Bones.Names[expMeshes[i].boneindices[e, eye]])
                            {
                                expMeshes[i].boneindices[e, eye] = r;
                                break;
                            }
                        }
                    }
                }
            }
        }
        static BuffersInfo Getbuffersinfo(MemoryStream ms, CR2WFile cr2w)
        {
            BinaryReader br = new BinaryReader(ms);
            BuffersInfo buffInfo = new BuffersInfo
            {
                buffers = new List<byte[]>()
            };
            foreach (var b in cr2w.Buffers.Select(_ => _.Buffer))
            {
                br.BaseStream.Seek(b.offset, SeekOrigin.Begin);

                var zbuffer = br.ReadBytes((int)b.diskSize);

                using var input = new MemoryStream(zbuffer);
                using var output = new MemoryStream();
                using var reader = new BinaryReader(input);
                using var writer = new BinaryWriter(output);
                reader.DecompressBuffer(writer, (uint)zbuffer.Length, b.memSize);

                buffInfo.buffers.Add(Catel.IO.StreamExtensions.ToByteArray(output));
            }
            // getting meshbufferindex 
            for (int i = 0; i < buffInfo.buffers.Count; i++)
            {
                MemoryStream bms = new MemoryStream(buffInfo.buffers[i]);
                BinaryReader bbr = new BinaryReader(bms);
                bms.Position = 6;

                if (bbr.ReadInt16() == Int16.MaxValue)
                {
                    buffInfo.meshbufferindex = i;
                    break;
                }
            }
            return buffInfo;
        }
        static ModelRoot RawSkinnedMeshesToGLTF(List<RawMeshContainer> meshes,RawArmature Rig)
        {
            var scene = new SceneBuilder();

            var bones = CP77.RigFile.RigFile.ExportNodes(Rig);
            var rootbone = bones.Values.Where(n => n.Parent == null).FirstOrDefault();

            int mIndex = -1;
            foreach (var mesh in meshes)
            {
                ++mIndex;
                long indCount = mesh.indices.Length;
                var expmesh = new SKINNEDMESH(mesh.name);

                var prim = expmesh.UsePrimitive(new MaterialBuilder("Default"));
                for (int i = 0; i < indCount; i += 3)
                {
                    uint idx0 = mesh.indices[i + 1];
                    uint idx1 = mesh.indices[i];
                    uint idx2 = mesh.indices[i + 2];

                    //VPNT
                    Vec3 p_0 = new Vec3(mesh.vertices[idx0].X, mesh.vertices[idx0].Y, mesh.vertices[idx0].Z);
                    Vec3 n_0 = new Vec3(mesh.normals[idx0].X, mesh.normals[idx0].Y, mesh.normals[idx0].Z);
                    Vec4 t_0 = new Vec4(new Vec3(mesh.tangents[idx0].X, mesh.tangents[idx0].Y, mesh.tangents[idx0].Z), 1);

                    Vec3 p_1 = new Vec3(mesh.vertices[idx1].X, mesh.vertices[idx1].Y, mesh.vertices[idx1].Z);
                    Vec3 n_1 = new Vec3(mesh.normals[idx1].X, mesh.normals[idx1].Y, mesh.normals[idx1].Z);
                    Vec4 t_1 = new Vec4(new Vec3(mesh.tangents[idx1].X, mesh.tangents[idx1].Y, mesh.tangents[idx1].Z), 1);

                    Vec3 p_2 = new Vec3(mesh.vertices[idx2].X, mesh.vertices[idx2].Y, mesh.vertices[idx2].Z);
                    Vec3 n_2 = new Vec3(mesh.normals[idx2].X, mesh.normals[idx2].Y, mesh.normals[idx2].Z);
                    Vec4 t_2 = new Vec4(new Vec3(mesh.tangents[idx2].X, mesh.tangents[idx2].Y, mesh.tangents[idx2].Z), 1);

                    //VCT
                    Vec2 tx0_0 = new Vec2(mesh.tx0coords[idx0].X, mesh.tx0coords[idx0].Y);
                    Vec2 tx1_0 = new Vec2(mesh.tx1coords[idx0].X, mesh.tx1coords[idx0].Y);

                    Vec2 tx0_1 = new Vec2(mesh.tx0coords[idx1].X, mesh.tx0coords[idx1].Y);
                    Vec2 tx1_1 = new Vec2(mesh.tx1coords[idx1].X, mesh.tx1coords[idx1].Y);

                    Vec2 tx0_2 = new Vec2(mesh.tx0coords[idx2].X, mesh.tx0coords[idx2].Y);
                    Vec2 tx1_2 = new Vec2(mesh.tx1coords[idx2].X, mesh.tx1coords[idx2].Y);

                    Vec4 col_0 = new Vec4(mesh.colors[idx0].X, mesh.colors[idx0].Y, mesh.colors[idx0].Z, mesh.colors[idx0].W);
                    Vec4 col_1 = new Vec4(mesh.colors[idx1].X, mesh.colors[idx1].Y, mesh.colors[idx1].Z, mesh.colors[idx1].W);
                    Vec4 col_2 = new Vec4(mesh.colors[idx2].X, mesh.colors[idx2].Y, mesh.colors[idx2].Z, mesh.colors[idx2].W);

                    if(mesh.weightcount == 8)
                    {
                        //VJ
                        Vec4 b0_0 = new Vec4(mesh.boneindices[idx0, 0], mesh.boneindices[idx0, 1], mesh.boneindices[idx0, 2], mesh.boneindices[idx0, 3]);
                        Vec4 b0_1 = new Vec4(mesh.boneindices[idx1, 0], mesh.boneindices[idx1, 1], mesh.boneindices[idx1, 2], mesh.boneindices[idx1, 3]);
                        Vec4 b0_2 = new Vec4(mesh.boneindices[idx2, 0], mesh.boneindices[idx2, 1], mesh.boneindices[idx2, 2], mesh.boneindices[idx2, 3]);

                        Vec4 b1_0 = new Vec4(mesh.boneindices[idx0, 4], mesh.boneindices[idx0, 5], mesh.boneindices[idx0, 6], mesh.boneindices[idx0, 7]);
                        Vec4 b1_1 = new Vec4(mesh.boneindices[idx1, 4], mesh.boneindices[idx1, 5], mesh.boneindices[idx1, 6], mesh.boneindices[idx1, 7]);
                        Vec4 b1_2 = new Vec4(mesh.boneindices[idx2, 4], mesh.boneindices[idx2, 5], mesh.boneindices[idx2, 6], mesh.boneindices[idx2, 7]);

                        Vec4 w0_0 = new Vec4(mesh.weights[idx0, 0], mesh.weights[idx0, 1], mesh.weights[idx0, 2], mesh.weights[idx0, 3]);
                        Vec4 w0_1 = new Vec4(mesh.weights[idx1, 0], mesh.weights[idx1, 1], mesh.weights[idx1, 2], mesh.weights[idx1, 3]);
                        Vec4 w0_2 = new Vec4(mesh.weights[idx2, 0], mesh.weights[idx2, 1], mesh.weights[idx2, 2], mesh.weights[idx2, 3]);

                        Vec4 w1_0 = new Vec4(mesh.weights[idx0, 4], mesh.weights[idx0, 5], mesh.weights[idx0, 6], mesh.weights[idx0, 7]);
                        Vec4 w1_1 = new Vec4(mesh.weights[idx1, 4], mesh.weights[idx1, 5], mesh.weights[idx1, 6], mesh.weights[idx1, 7]);
                        Vec4 w1_2 = new Vec4(mesh.weights[idx2, 4], mesh.weights[idx2, 5], mesh.weights[idx2, 6], mesh.weights[idx2, 7]);

                        VJ bone0 = new VJ(new SharpGLTF.Transforms.SparseWeight8(b0_0, b1_0, w0_0, w1_0));
                        VJ bone1 = new VJ(new SharpGLTF.Transforms.SparseWeight8(b0_1, b1_1, w0_1, w1_1));
                        VJ bone2 = new VJ(new SharpGLTF.Transforms.SparseWeight8(b0_2, b1_2, w0_2, w1_2));
                        // vertex build
                        var v0 = new SKINNEDVERTEX(new VPNT(p_0, n_0, t_0), new VCT(col_0, tx0_0, tx1_0), bone0);
                        var v1 = new SKINNEDVERTEX(new VPNT(p_1, n_1, t_1), new VCT(col_1, tx0_1, tx1_1), bone1);
                        var v2 = new SKINNEDVERTEX(new VPNT(p_2, n_2, t_2), new VCT(col_2, tx0_2, tx1_2), bone2);
                        // triangle build
                        prim.AddTriangle(v0, v1, v2);
                    }

                    // for weightcount = 4
                    else
                    {
                        //VJ
                        Vec4 b0_0 = new Vec4(mesh.boneindices[idx0, 0], mesh.boneindices[idx0, 1], mesh.boneindices[idx0, 2], mesh.boneindices[idx0, 3]);
                        Vec4 b0_1 = new Vec4(mesh.boneindices[idx1, 0], mesh.boneindices[idx1, 1], mesh.boneindices[idx1, 2], mesh.boneindices[idx1, 3]);
                        Vec4 b0_2 = new Vec4(mesh.boneindices[idx2, 0], mesh.boneindices[idx2, 1], mesh.boneindices[idx2, 2], mesh.boneindices[idx2, 3]);

                        Vec4 w0_0 = new Vec4(mesh.weights[idx0, 0], mesh.weights[idx0, 1], mesh.weights[idx0, 2], mesh.weights[idx0, 3]);
                        Vec4 w0_1 = new Vec4(mesh.weights[idx1, 0], mesh.weights[idx1, 1], mesh.weights[idx1, 2], mesh.weights[idx1, 3]);
                        Vec4 w0_2 = new Vec4(mesh.weights[idx2, 0], mesh.weights[idx2, 1], mesh.weights[idx2, 2], mesh.weights[idx2, 3]);

                        VJ bone0 = new VJ(new SharpGLTF.Transforms.SparseWeight8(b0_0, Vec4.Zero, w0_0, Vec4.Zero));
                        VJ bone1 = new VJ(new SharpGLTF.Transforms.SparseWeight8(b0_1, Vec4.Zero, w0_1, Vec4.Zero));
                        VJ bone2 = new VJ(new SharpGLTF.Transforms.SparseWeight8(b0_2, Vec4.Zero, w0_2, Vec4.Zero));
                        // vertex build
                        var v0 = new SKINNEDVERTEX(new VPNT(p_0, n_0, t_0), new VCT(col_0, tx0_0, tx1_0), bone0);
                        var v1 = new SKINNEDVERTEX(new VPNT(p_1, n_1, t_1), new VCT(col_1, tx0_1, tx1_1), bone1);
                        var v2 = new SKINNEDVERTEX(new VPNT(p_2, n_2, t_2), new VCT(col_2, tx0_2, tx1_2), bone2);

                        // triangle build
                        prim.AddTriangle(v0, v1, v2);
                    }
                }
                scene.AddSkinnedMesh(expmesh,rootbone.WorldMatrix, bones.Values.ToArray());
            }
            var model = scene.ToGltf2();

            return model;
        }
        static ModelRoot RawRigidMeshesToGLTF(List<RawMeshContainer> meshes)
        {
            var scene = new SceneBuilder();

            foreach (var mesh in meshes)
            {
                long indCount = mesh.indices.Length;
                var expmesh = new RIGIDMESH(mesh.name);

                var prim = expmesh.UsePrimitive(new MaterialBuilder("Default"));
                for (int i = 0; i < indCount; i += 3)
                {
                    uint idx0 = mesh.indices[i + 1];
                    uint idx1 = mesh.indices[i];
                    uint idx2 = mesh.indices[i + 2];

                    //VPNT
                    Vec3 p_0 = new Vec3(mesh.vertices[idx0].X, mesh.vertices[idx0].Y, mesh.vertices[idx0].Z);
                    Vec3 n_0 = new Vec3(mesh.normals[idx0].X, mesh.normals[idx0].Y, mesh.normals[idx0].Z);
                    Vec4 t_0 = new Vec4(new Vec3(mesh.tangents[idx0].X, mesh.tangents[idx0].Y, mesh.tangents[idx0].Z), 1);

                    Vec3 p_1 = new Vec3(mesh.vertices[idx1].X, mesh.vertices[idx1].Y, mesh.vertices[idx1].Z);
                    Vec3 n_1 = new Vec3(mesh.normals[idx1].X, mesh.normals[idx1].Y, mesh.normals[idx1].Z);
                    Vec4 t_1 = new Vec4(new Vec3(mesh.tangents[idx1].X, mesh.tangents[idx1].Y, mesh.tangents[idx1].Z), 1);

                    Vec3 p_2 = new Vec3(mesh.vertices[idx2].X, mesh.vertices[idx2].Y, mesh.vertices[idx2].Z);
                    Vec3 n_2 = new Vec3(mesh.normals[idx2].X, mesh.normals[idx2].Y, mesh.normals[idx2].Z);
                    Vec4 t_2 = new Vec4(new Vec3(mesh.tangents[idx2].X, mesh.tangents[idx2].Y, mesh.tangents[idx2].Z), 1);

                    //VCT
                    Vec2 tx0_0 = new Vec2(mesh.tx0coords[idx0].X, mesh.tx0coords[idx0].Y);
                    Vec2 tx1_0 = new Vec2(mesh.tx1coords[idx0].X, mesh.tx1coords[idx0].Y);

                    Vec2 tx0_1 = new Vec2(mesh.tx0coords[idx1].X, mesh.tx0coords[idx1].Y);
                    Vec2 tx1_1 = new Vec2(mesh.tx1coords[idx1].X, mesh.tx1coords[idx1].Y);

                    Vec2 tx0_2 = new Vec2(mesh.tx0coords[idx2].X, mesh.tx0coords[idx2].Y);
                    Vec2 tx1_2 = new Vec2(mesh.tx1coords[idx2].X, mesh.tx1coords[idx2].Y);

                    Vec4 col_0 = new Vec4(mesh.colors[idx0].X, mesh.colors[idx0].Y, mesh.colors[idx0].Z, mesh.colors[idx0].W);
                    Vec4 col_1 = new Vec4(mesh.colors[idx1].X, mesh.colors[idx1].Y, mesh.colors[idx1].Z, mesh.colors[idx1].W);
                    Vec4 col_2 = new Vec4(mesh.colors[idx2].X, mesh.colors[idx2].Y, mesh.colors[idx2].Z, mesh.colors[idx2].W);

                    // vertex build
                    var v0 = new RIGIDVERTEX(new VPNT(p_0, n_0, t_0), new VCT(col_0, tx0_0, tx1_0));
                    var v1 = new RIGIDVERTEX(new VPNT(p_1, n_1, t_1), new VCT(col_1, tx0_1, tx1_1));
                    var v2 = new RIGIDVERTEX(new VPNT(p_2, n_2, t_2), new VCT(col_2, tx0_2, tx1_2));
                    // triangle build
                    prim.AddTriangle(v0, v1, v2);
                }
                scene.AddRigidMesh(expmesh, System.Numerics.Matrix4x4.Identity);
            }
            var model = scene.ToGltf2();
            return model;
        }

        class BuffersInfo
        {
            public List<byte[]> buffers;
            public int meshbufferindex;
        }
        class MeshBones
        {
            public string[] Names;
            public Vec3[] WorldPosn;
        }
    }
}