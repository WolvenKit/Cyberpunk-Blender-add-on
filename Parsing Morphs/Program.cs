using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using WolvenKit.Common.Services;
using CP77.CR2W.Types;
using WolvenKit.Common.Oodle; // can be removed using it for buffers decomp
using Catel.IoC;
using SharpGLTF.Geometry;
using SharpGLTF.Geometry.VertexTypes;
using SharpGLTF.Materials;
using CP77.CR2W;
using System.Text;
using CommonDataStructs;

namespace Parsing_Morphs
{
    using Vec4 = System.Numerics.Vector4;
    using Vec3 = System.Numerics.Vector3;
    using Vec2 = System.Numerics.Vector2;
    using VERTEX = VertexBuilder<VertexPositionNormalTangent, VertexColor1Texture2, VertexEmpty>;
    using MESH = MeshBuilder<VertexPositionNormalTangent, VertexColor1Texture2, VertexEmpty>;
    using VPNT = VertexPositionNormalTangent;
    using VCT = VertexColor1Texture2;

    class Program
    {
        static void Main(string[] args)
        {
            ServiceLocator.Default.RegisterType<ILoggerService, LoggerService>();

            string filename = Console.ReadLine();
            if (filename.Contains("\""))
                filename = filename.Replace("\"", string.Empty);

            FileStream fs = new FileStream(filename, FileMode.Open, FileAccess.Read);

            BinaryReader br = new BinaryReader(fs);
            CR2WFile cr2w = new CR2WFile();
            br.BaseStream.Seek(0, SeekOrigin.Begin);
            cr2w.Read(br);
            List<byte[]> buffers = new List<byte[]>();

            foreach (var b in cr2w.Buffers.Select(_ => _.Buffer))
            {
                br.BaseStream.Seek(b.offset, SeekOrigin.Begin);

                var zbuffer = br.ReadBytes((int)b.diskSize);

                using var input = new MemoryStream(zbuffer);
                using var output = new MemoryStream();
                using var reader = new BinaryReader(input);
                using var writer = new BinaryWriter(output);
                reader.DecompressBuffer(writer, (uint)zbuffer.Length, b.memSize);

                buffers.Add(Catel.IO.StreamExtensions.ToByteArray(output));
            }
            FileInfo fi = new FileInfo(filename);
            ParseMesh(cr2w, buffers, fi);
        }
        public static void ParseMesh(CR2WFile cr2w, List<byte[]> buffers, FileInfo outfile)
        {
            int meshbufferindex = Getmeshbufferindex(buffers);
            MeshesInfo meshesInfo = GetMeshesinfo(cr2w);
            List<RawMeshContainer> expMeshes = new List<RawMeshContainer>();
            MemoryStream meshbuffer = new MemoryStream(buffers[meshbufferindex]);

            MemoryStream diffsbuffer = new MemoryStream(buffers[0]);
            MemoryStream mappingbuffer = new MemoryStream(buffers[1]);

            for (int i = 0; i < meshesInfo.meshC; i++)
            {
                if (meshesInfo.LODLvl[i] == 1)
                    expMeshes.Add(ContainRawMesh(meshbuffer, meshesInfo.vertCounts[i], meshesInfo.indCounts[i], meshesInfo.vertOffsets[i], meshesInfo.tx0Offsets[i], meshesInfo.normalOffsets[i], meshesInfo.colorOffsets[i], meshesInfo.unknownOffsets[i], meshesInfo.indicesOffsets[i], meshesInfo.vpStrides[i], meshesInfo.qScale, meshesInfo.qTrans, meshesInfo.weightcounts[i]));
            }

            TargetsInfo targetsInfo = GetTargetInfos(cr2w, meshesInfo.meshC);

            List<RawTargetContainer[]> expTargets = new List<RawTargetContainer[]>();

            for(int i = 0; i < targetsInfo.NumTargets; i++)
            {
                UInt32[] temp_NumVertexDiffsInEachChunk = new UInt32[meshesInfo.meshC];
                UInt32[] temp_NumVertexDiffsMappingInEachChunk = new UInt32[meshesInfo.meshC];
                for (int e = 0; e < meshesInfo.meshC; e++)
                {
                    temp_NumVertexDiffsInEachChunk[e] = targetsInfo.NumVertexDiffsInEachChunk[i, e];
                    temp_NumVertexDiffsMappingInEachChunk[e] = targetsInfo.NumVertexDiffsMappingInEachChunk[i, e];
                }
                expTargets.Add(ContainRawTargets(diffsbuffer, mappingbuffer, temp_NumVertexDiffsInEachChunk, temp_NumVertexDiffsMappingInEachChunk, targetsInfo.TargetStartsInVertexDiffs[i], targetsInfo.TargetStartsInVertexDiffsMapping[i], targetsInfo.TargetPositionDiffOffset[i], targetsInfo.TargetPositionDiffScale[i], meshesInfo.meshC));
            }

            for(int i = 0; i < targetsInfo.NumTargets ; i++)
            {
                //ExportASCII(expMeshes, outfile, expTargets[i], targetsInfo.Names[i]);
            }
            ContainedMeshToGLTF(expMeshes, outfile, expTargets, targetsInfo.Names);

        }

        private static int Getmeshbufferindex(List<byte[]> buffers)
        {
            int meshbufferindex = int.MaxValue;
            for (int i = 0; i < buffers.Count; i++)
            {
                MemoryStream bms = new MemoryStream(buffers[i]);
                BinaryReader bbr = new BinaryReader(bms);
                bms.Position = 6;

                if (bbr.ReadInt16() == Int16.MaxValue)
                {
                    meshbufferindex = i;
                    break;
                }
            }
            return meshbufferindex;
        }
        private static MeshesInfo GetMeshesinfo(CR2WFile cr2w)
        {
            int Index = int.MaxValue;
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
            Vector4 qScale = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.QuantizationScale;
            Vector4 qTrans = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.QuantizationOffset;


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
        private static TargetsInfo GetTargetInfos(CR2WFile cr2w, int SubMeshC)
        {
            int Index = int.MaxValue;
            for (int i = 0; i < cr2w.Chunks.Count; i++)
            {
                if (cr2w.Chunks[i].REDType == "rendRenderMorphTargetMeshBlob")
                {
                    Index = i;
                }
            }

            UInt32 NumTargets = (cr2w.Chunks[Index].data as rendRenderMorphTargetMeshBlob).Header.NumTargets.val;

            UInt32[,] NumVertexDiffsInEachChunk = new UInt32[NumTargets, SubMeshC];
            UInt32 NumDiffs = (cr2w.Chunks[Index].data as rendRenderMorphTargetMeshBlob).Header.NumDiffs.val;
            UInt32 NumDiffsMapping = (cr2w.Chunks[Index].data as rendRenderMorphTargetMeshBlob).Header.NumDiffsMapping.val;
            UInt32[,] NumVertexDiffsMappingInEachChunk = new UInt32[NumTargets, SubMeshC];
            UInt32[] TargetStartsInVertexDiffs = new UInt32[NumTargets];
            UInt32[] TargetStartsInVertexDiffsMapping = new UInt32[NumTargets];
            Vector4[] TargetPositionDiffOffset = new Vector4[NumTargets];
            Vector4[] TargetPositionDiffScale = new Vector4[NumTargets];
            for (int i = 0; i < NumTargets; i++)
            {
                for(int e = 0; e < SubMeshC; e++)
                {
                    NumVertexDiffsInEachChunk[i, e] = (cr2w.Chunks[Index].data as rendRenderMorphTargetMeshBlob).Header.NumVertexDiffsInEachChunk[i][e].val;
                    NumVertexDiffsMappingInEachChunk[i, e] = (cr2w.Chunks[Index].data as rendRenderMorphTargetMeshBlob).Header.NumVertexDiffsMappingInEachChunk[i][e].val;
                }

                TargetStartsInVertexDiffs[i] = (cr2w.Chunks[Index].data as rendRenderMorphTargetMeshBlob).Header.TargetStartsInVertexDiffs[i].val;
                TargetStartsInVertexDiffsMapping[i] = (cr2w.Chunks[Index].data as rendRenderMorphTargetMeshBlob).Header.TargetStartsInVertexDiffsMapping[i].val;

                TargetPositionDiffOffset[i] = (cr2w.Chunks[Index].data as rendRenderMorphTargetMeshBlob).Header.TargetPositionDiffOffset[i];
                TargetPositionDiffScale[i] = (cr2w.Chunks[Index].data as rendRenderMorphTargetMeshBlob).Header.TargetPositionDiffScale[i];
            }


            Index = int.MaxValue;
            for (int i = 0; i < cr2w.Chunks.Count; i++)
            {
                if (cr2w.Chunks[i].REDType == "MorphTargetMesh")
                {
                    Index = i;
                }
            }

            string[] Names = new string[NumTargets];
            string[] RegionNames = new string[NumTargets];
            string BaseMesh = (cr2w.Chunks[Index].data as MorphTargetMesh).BaseMesh.DepotPath;
            string BaseTexture = (cr2w.Chunks[Index].data as MorphTargetMesh).BaseTexture.DepotPath;

            for (int i = 0; i < NumTargets; i++)
            {
                Names[i] = (cr2w.Chunks[Index].data as MorphTargetMesh).Targets[i].Name.Value;
                RegionNames[i] = (cr2w.Chunks[Index].data as MorphTargetMesh).Targets[i].RegionName.Value;
            }

            TargetsInfo targetsInfo = new TargetsInfo()
            {
                NumVertexDiffsInEachChunk = NumVertexDiffsInEachChunk,
                NumDiffs = NumDiffs,
                NumDiffsMapping = NumDiffsMapping,
                NumVertexDiffsMappingInEachChunk = NumVertexDiffsMappingInEachChunk,
                TargetStartsInVertexDiffs = TargetStartsInVertexDiffs,
                TargetStartsInVertexDiffsMapping = TargetStartsInVertexDiffsMapping,
                TargetPositionDiffOffset = TargetPositionDiffOffset,
                TargetPositionDiffScale = TargetPositionDiffScale,
                Names = Names,
                RegionNames = RegionNames,
                NumTargets = NumTargets,
                BaseTexture = BaseTexture,
            };
            return targetsInfo;
        }
        /*
        private static RawMeshContainer ContainRawMesh(MemoryStream gfs, UInt32 vertCount, UInt32 indCount, UInt32 vertOffset, UInt32 tx0Offset, UInt32 normalOffset, UInt32 colorOffset, UInt32 tx1Offset, UInt32 indOffset, UInt32 vpStride, Vector4 qScale, Vector4 qTrans, MemoryStream mms, MemoryStream ims)
        {
            Converters converter = new Converters(); // contains methods for halffloats
            int numdiffs = 2791;
            UInt16[] morphIndices = new UInt16[numdiffs];
            BinaryReader ibr = new BinaryReader(ims);
            ims.Position = 0;
            BinaryReader mbr = new BinaryReader(mms);
            mms.Position = 0;
            for (int i = 0; i < numdiffs; i++)
            {
                morphIndices[i] = ibr.ReadUInt16();
            }
            Vec3[] vertexDelta = new Vec3[numdiffs];
            Vec3[] normalDelta = new Vec3[numdiffs];
            Vec3[] tangentDelta = new Vec3[numdiffs];
            for (int i = 0; i < numdiffs; i++)
            {
                Vec4 v = converter.TenBitUnsigned(mbr.ReadUInt32());
                vertexDelta[i] = new Vec3(v.X, v.Y, v.Z);
                Vec4 n = converter.TenBitShifted(mbr.ReadUInt32());
                normalDelta[i] = new Vec3(n.X, n.Y, n.Z);
                Vec4 t = converter.TenBitShifted(mbr.ReadUInt32());
                tangentDelta[i] = new Vec3(t.X, t.Y, t.Z);
            }

            for (int i = 0; i < numdiffs; i++)
            {
                index = morphIndices[i];
                vertices[index].X += (float)(vertexDelta[i].X * 0.006889195 + -0.00353031);
                vertices[index].Y += (float)(vertexDelta[i].Y * 0.0047274334 + -0.0005970103);
                vertices[index].Z += (float)(vertexDelta[i].Z * 0.0049985982 + -0.004314909);
                normals[index].X += normalDelta[i].X;
                normals[index].Y += normalDelta[i].Y;
                normals[index].Z += normalDelta[i].Z;
                tangents[index].X += tangentDelta[i].X;
                tangents[index].Y += tangentDelta[i].Y;
                tangents[index].Z += tangentDelta[i].Z;
            }
        }*/
        private static RawMeshContainer ContainRawMesh(MemoryStream gfs, UInt32 vertCount, UInt32 indCount, UInt32 vertOffset, UInt32 tx0Offset, UInt32 normalOffset, UInt32 colorOffset, UInt32 unknownOffset, UInt32 indOffset, UInt32 vpStride, Vector4 qScale, Vector4 qTrans, UInt32 weightcount)
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

                float x = (gbr.ReadInt16() / 32767f) * qScale.X.val + qTrans.X.val;
                float y = (gbr.ReadInt16() / 32767f) * qScale.Y.val + qTrans.Y.val;
                float z = (gbr.ReadInt16() / 32767f) * qScale.Z.val + qTrans.Z.val;
                vertices[i] = new Vec3(x, y, z);
            }
            // got vertices

            Converters converter = new Converters(); // contains methods for halffloats
            float[] values = new float[vertCount * 2];

            if (tx0Offset != 0)
            {
                // getting texturecoord0 as half floats
                gfs.Position = tx0Offset;
                for (int i = 0; i < vertCount * 2; i++)
                {
                    UInt16 read = gbr.ReadUInt16();
                    values[i] = converter.hfconvert(read);
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
                Vec4 tempv = converter.TenBitShifted(NorRead32);
                normals[i] = new Vec3(tempv.X, tempv.Y, tempv.Z);
            }
            // got 10bit normals

            // getting 10bit tangents
            for (int i = 0; i < vertCount; i++)
            {
                gfs.Position = normalOffset + 4 + 8 * i;
                NorRead32 = gbr.ReadUInt32();
                Vec4 tempv = converter.TenBitShifted(NorRead32);
                tangents[i] = new Vec4(tempv.X, tempv.Y, tempv.Z, 1f);
            }


            if (colorOffset != 0)
            {
                gfs.Position = colorOffset + 4;
                // getting texturecoord1 as half floats
                for (int i = 0; i < vertCount * 2; i++)
                {
                    UInt16 read = gbr.ReadUInt16();
                    values[i] = converter.hfconvert(read);
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
        private static RawTargetContainer[] ContainRawTargets(MemoryStream diffsbuffer, MemoryStream mappingbuffer, UInt32[] NumVertexDiffsInEachChunk, UInt32[] NumVertexDiffsMappingInEachChunk, UInt32 TargetStartsInVertexDiffs, UInt32 TargetStartsInVertexDiffsMapping, Vector4 TargetPositionDiffOffset, Vector4 TargetPositionDiffScale, int SubMeshC)
        {
            RawTargetContainer[] rawtarget = new RawTargetContainer[SubMeshC];

            BinaryReader diffsbr = new BinaryReader(diffsbuffer);
            BinaryReader mappingbr = new BinaryReader(mappingbuffer);

            Converters converter = new Converters();

            for (int i = 0; i < SubMeshC; i++)
            {
                UInt32 diffsCount = NumVertexDiffsInEachChunk[i];
                Vec3[] vertexDelta = new Vec3[diffsCount];
                Vec3[] normalDelta = new Vec3[diffsCount];
                Vec3[] tangentDelta = new Vec3[diffsCount];

                if (i == 0)
                    diffsbuffer.Position = TargetStartsInVertexDiffs * 12;
                else
                {
                    diffsbuffer.Position = TargetStartsInVertexDiffs * 12;

                    for(int eye = 0; eye < i; eye++)
                    {
                        diffsbuffer.Position += NumVertexDiffsInEachChunk[eye] * 12;
                    }
                }


                for (int e = 0; e < diffsCount; e++)
                {
                    Vec4 v = converter.TenBitUnsigned(diffsbr.ReadUInt32());
                    vertexDelta[e] = new Vec3(v.X * TargetPositionDiffScale.X.val + TargetPositionDiffOffset.X.val, v.Y * TargetPositionDiffScale.Y.val + TargetPositionDiffOffset.Y.val, v.Z * TargetPositionDiffScale.Z.val + TargetPositionDiffOffset.Z.val);
                    Vec4 n = converter.TenBitShifted(diffsbr.ReadUInt32());
                    normalDelta[e] = new Vec3(n.X, n.Y, n.Z);
                    Vec4 t = converter.TenBitShifted(diffsbr.ReadUInt32());
                    tangentDelta[e] = new Vec3(t.X, t.Y, t.Z);
                }

                UInt16[] vertexMapping = new UInt16[diffsCount];

                if (i == 0)
                    mappingbuffer.Position = TargetStartsInVertexDiffsMapping * 4;
                else
                {
                    mappingbuffer.Position = TargetStartsInVertexDiffsMapping * 4;

                    for (int eye = 0; eye < i; eye++)
                    {
                        mappingbuffer.Position += NumVertexDiffsMappingInEachChunk[eye] * 4;
                    }
                }

                for(int e = 0; e < diffsCount; e++)
                {
                    vertexMapping[e] = mappingbr.ReadUInt16();
                }

                rawtarget[i] = new RawTargetContainer()
                {
                    vertexDelta = vertexDelta,
                    normalDelta = normalDelta,
                    tangentDelta = tangentDelta,
                    vertexMapping = vertexMapping,
                    diffsCount = diffsCount
                };
            }

            return rawtarget;
        }
        private static void ContainedMeshToGLTF(List<RawMeshContainer> meshes, FileInfo outfile,List<RawTargetContainer[]> expTargets,string[] names)
        {
            var scene = new SharpGLTF.Scenes.SceneBuilder();

            int mIndex = -1;
            foreach (var mesh in meshes)
            {
                ++mIndex;
                long indCount = mesh.indices.Length;
                var expmesh = new MESH(string.Format("mesh_{0}", mIndex));

                var prim = expmesh.UsePrimitive(new MaterialBuilder("Default"));
                for (long i = 0; i < indCount; i += 3)
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
                    var v0 = new VERTEX(new VPNT(p_0, n_0, t_0), new VCT(col_0, tx0_0, tx1_0));
                    var v1 = new VERTEX(new VPNT(p_1, n_1, t_1), new VCT(col_1, tx0_1, tx1_1));
                    var v2 = new VERTEX(new VPNT(p_2, n_2, t_2), new VCT(col_2, tx0_2, tx1_2));

                    // triangle build
                    prim.AddTriangle(v0, v1, v2);
                }
                for(int i = 0; i < expTargets.Count; i++)
                {
                    var morphBuilder = expmesh.UseMorphTarget(i);

                    for(int e = 0; e < expTargets[i][mIndex].diffsCount; e++)
                    {
                        morphBuilder.SetVertexDelta(mesh.vertices[expTargets[i][mIndex].vertexMapping[e]], new VertexGeometryDelta(expTargets[i][mIndex].vertexDelta[e], expTargets[i][mIndex].normalDelta[e], expTargets[i][mIndex].tangentDelta[e]));
                    }
                }
                scene.AddRigidMesh(expmesh, System.Numerics.Matrix4x4.Identity);
            }

            var model = scene.ToGltf2();
            model.SaveGLB(Path.GetFullPath(outfile.FullName).Replace(".morphtarget", ".glb"));
        }

        static void ExportASCII(List<RawMeshContainer> meshes, FileInfo outfile, RawTargetContainer[] Targets,string name)
        {
            if (meshes == null || meshes.Count == 0)
                return;

            int mIndex = -1;
            int meshCount = meshes.Count;
            StringBuilder objS = new StringBuilder();
            // printing bones
            StringBuilder asciiS = new StringBuilder();

            asciiS.AppendLine(string.Format("0 # Bones"));
            objS.Append(asciiS.ToString());
            objS.AppendLine(string.Format("{0} # meshes", meshCount));

            foreach (var mesh in meshes)
            {
                int vertCount = mesh.vertices.Length;
                int indCount = mesh.indices.Length;
                int uvCount = mesh.tx0coords.Length;
                int norCount = mesh.normals.Length;
                ++mIndex;

                objS.AppendLine(string.Format("test_{0}", mIndex));
                objS.AppendLine(string.Format("1 # UV Layers"));
                objS.AppendLine("1 # Textures");
                objS.AppendLine("Texture.png");
                objS.AppendLine("0 # UV Index");
                objS.AppendLine(string.Format("{0} # Vertices", vertCount));

                StringBuilder appS = new StringBuilder();

                Vec3[] vertices = new Vec3[vertCount];
                Vec3[] normals = new Vec3[vertCount];
                Vec4[] tangents = new Vec4[vertCount];

                for(int i = 0; i < vertCount; i++)
                {
                    Vec3 vert = mesh.vertices[i];
                    Vec3 norm = mesh.normals[i];
                    Vec4 tang = mesh.tangents[i];

                    vertices[i] = new Vec3(vert.X, vert.Y, vert.Z);
                    normals[i] = new Vec3(norm.X, norm.Y, norm.Z);
                    tangents[i] = new Vec4(tang.X, tang.Y, tang.Z,tang.W);

                }
                UInt16 index = 0;
                for (int i = 0; i < Targets[mIndex].diffsCount; i++)
                {
                    index = Targets[mIndex].vertexMapping[i];
                    vertices[index].X += Targets[mIndex].vertexDelta[i].X;
                    vertices[index].Y += Targets[mIndex].vertexDelta[i].Y;
                    vertices[index].Z += Targets[mIndex].vertexDelta[i].Z;
                    normals[index].X += Targets[mIndex].normalDelta[i].X;
                    normals[index].Y += Targets[mIndex].normalDelta[i].Y;
                    normals[index].Z += Targets[mIndex].normalDelta[i].Z;
                    tangents[index].X += Targets[mIndex].tangentDelta[i].X;
                    tangents[index].Y += Targets[mIndex].tangentDelta[i].Y;
                    tangents[index].Z += Targets[mIndex].tangentDelta[i].Z;
                }
                for (int i = 0; i < vertCount; i++)
                {
                    Vec3 vert = vertices[i];
                    appS.AppendLine(string.Format("{0} {1} {2} # Coords", vert.X, vert.Y, vert.Z));
                    Vec3 norm = normals[i];
                    appS.AppendLine(String.Format("{0} {1} {2} # Norms", norm.X, norm.Y, norm.Z));
                    appS.AppendLine(string.Format("255 255 255 255"));
                    Vec2 uv = mesh.tx0coords[i];
                    appS.AppendLine(string.Format("{0} {1} # Uv's", uv.X, uv.Y));
                }

                objS.Append(appS.ToString());
                objS.AppendLine(string.Format("{0} # faces", indCount / 3));

                // faces
                for (int i = 0; i < indCount; i += 3)
                {
                    objS.AppendLine(string.Format("{0} {1} {2}", mesh.indices[i], mesh.indices[i + 1], mesh.indices[i + 2]));
                }
            }
            // done printing mesh
            File.WriteAllText(Path.GetDirectoryName(outfile.FullName) + "\\" + name + ".ascii", objS.ToString());
        }
        class RawMeshContainer
        {
            public Vec3[] vertices { get; set; }
            public uint[] indices { get; set; }
            public Vec2[] tx0coords { get; set; }
            public Vec2[] tx1coords { get; set; }
            public Vec3[] normals { get; set; }
            public Vec4[] tangents { get; set; }
            public Vec4[] colors { get; set; }
            public float[,] weights { get; set; }
            public UInt16[,] boneindices { get; set; }
            public string name;
            public UInt32 weightcount { get; set; }
        }
        class MeshesInfo
        {
            public UInt32[] vertCounts { get; set; }
            public UInt32[] indCounts { get; set; }
            public UInt32[] vertOffsets { get; set; }
            public UInt32[] tx0Offsets { get; set; }
            public UInt32[] normalOffsets { get; set; }
            public UInt32[] colorOffsets { get; set; }
            public UInt32[] unknownOffsets { get; set; }
            public UInt32[] indicesOffsets { get; set; }
            public UInt32[] vpStrides { get; set; }

            public UInt32[] weightcounts { get; set; }
            public Vector4 qTrans { get; set; }
            public Vector4 qScale { get; set; }
            public int meshC { get; set; }
            public UInt32[] LODLvl { get; set; }
        }
        class RawTargetContainer
        {
            public Vec3[] vertexDelta { get; set; }
            public Vec3[] normalDelta { get; set; }
            public Vec3[] tangentDelta { get; set; }
            public UInt16[] vertexMapping { get; set; }
            public UInt32 diffsCount { get; set; }
        }
        class TargetsInfo
        {
            public UInt32[,] NumVertexDiffsInEachChunk { get; set; }
            public UInt32 NumDiffs { get; set; }
            public UInt32 NumDiffsMapping { get; set; }
            public UInt32[,] NumVertexDiffsMappingInEachChunk { get; set; }
            public UInt32[] TargetStartsInVertexDiffs { get; set; }
            public UInt32[] TargetStartsInVertexDiffsMapping { get; set; }
            public Vector4[] TargetPositionDiffOffset { get; set; }
            public Vector4[] TargetPositionDiffScale { get; set; }
            public string[] Names { get; set; }
            public string[] RegionNames { get; set; }
            public UInt32 NumTargets { get; set; }
            public string BaseMesh { get; set; }
            public string BaseTexture { get; set; }
        }
    }
}
