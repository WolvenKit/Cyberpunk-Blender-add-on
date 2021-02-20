using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Globalization;
using System.Threading;
using Catel.IoC;
using CP77.CR2W;
using WolvenKit.Common.Services;
using CP77.CR2W.Types;
using WolvenKit.Common.Oodle;
using HalfFloat;

namespace MeshExportASCII
{
    using Vec4 = System.Numerics.Vector4;
    using Vec3 = System.Numerics.Vector3;
    using Vec2 = System.Numerics.Vector2;

    class Program
    {
        static List<Mesh> expMeshes = new List<Mesh>();
        static bool LOD_filter = true;
        static bool MeshInfoVerbosity = true;
        [STAThread]
        static void Main(string[] args)
        {
            CultureInfo customCulture = (CultureInfo)Thread.CurrentThread.CurrentCulture.Clone();
            customCulture.NumberFormat.NumberDecimalSeparator = ".";
            Thread.CurrentThread.CurrentCulture = customCulture;

            ServiceLocator.Default.RegisterType<ILoggerService, LoggerService>();

            char option = ' ';
            bool con = true;

            if (!File.Exists(@"oo2ext_7_win64.dll"))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("oo2ext_7_win64.dll is Missing");
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("Copy oo2ext_7_win64.dll from bin\\x64\\ and paste into MeshExportASCII Folder\n\n");
            }

            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine("Mesh Files Must Have Been Uncooked/Unpacked From CP77Tools v0.2.0.0 Or Above");
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine("LOD Filtering(Only LOD Lvl 1 Meshes are Exported): " + LOD_filter);
            Console.WriteLine("Meshes Info Verbosity: " + MeshInfoVerbosity);
            Console.ResetColor();
            Console.WriteLine("-----------------------------------------------------------------------------");
            do
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("\nOptions");
                Console.ResetColor();
                Console.WriteLine("(m/M) Takes a single .mesh file and exports into XNAascii file.");
                Console.WriteLine("(d/D) Takes a directory and exports all the .mesh files to XNAascii files(sub dirs included)");
                Console.WriteLine("(r/R) Takes a directory with .mesh and .rig files and combines them to a single Model with parented rig");
                Console.WriteLine("(e/E) To Exit\n");

                Console.ResetColor();
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.Write("Choose Option: ");
                Console.ResetColor();
                option = Console.ReadKey().KeyChar;
                switch (option)
                {
                    case 'm':
                    case 'M':
                        OpM();
                        break;
                    case 'd':
                    case 'D':
                        OpD();
                        break;
                    case 'r':
                    case 'R':
                        OpR();
                        break;
                    case 'e':
                    case 'E':
                        break;
                    default:
                        Console.ForegroundColor = ConsoleColor.Red;
                        Console.WriteLine("\nInvalid Option");
                        Console.ResetColor();
                        break;
                }
                if (option == 'e' || option == 'E')
                    con = false;
            }
            while(con);
        }
        static meshesinfo GetMeshesinfo(CR2WFile cr2w)
        {
            meshesinfo MeshesInfo = new meshesinfo();
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
            UInt32[] uvOffsets = new UInt32[meshC];
            UInt32[] normalOffsets = new UInt32[meshC];
            UInt32[] unknown1Offsets = new UInt32[meshC];
            UInt32[] unknown2Offsets = new UInt32[meshC];
            UInt32[] indicesOffsets = new UInt32[meshC];
            UInt32[] vpStrides = new UInt32[meshC];
            UInt32[] LODLvl = new UInt32[meshC];
            for (int i = 0; i < meshC; i++)
            {
                vertCounts[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].NumVertices.val;
                indCounts[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].NumIndices.val;
                vertOffsets[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkVertices.ByteOffsets[0].val;
                uvOffsets[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkVertices.ByteOffsets[1].val;
                normalOffsets[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkVertices.ByteOffsets[2].val;
                unknown1Offsets[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkVertices.ByteOffsets[3].val;
                unknown2Offsets[i] = (cr2w.Chunks[Index].data as rendRenderMeshBlob).Header.RenderChunkInfos[i].ChunkVertices.ByteOffsets[4].val;

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
                //    Console.WriteLine(weightcounts[i]);
            }
            MeshesInfo.vertCounts = vertCounts;
            MeshesInfo.indCounts = indCounts;
            MeshesInfo.vertOffsets = vertOffsets;
            MeshesInfo.uvOffsets = uvOffsets;
            MeshesInfo.normalOffsets = normalOffsets;
            MeshesInfo.unknown1Offsets = unknown1Offsets;
            MeshesInfo.unknown2Offsets = unknown2Offsets;
            MeshesInfo.indicesOffsets = indicesOffsets;
            MeshesInfo.vpStrides = vpStrides;
            MeshesInfo.weightcounts = weightcounts;
            MeshesInfo.LODLvl = LODLvl;
            MeshesInfo.qScale = qScale;
            MeshesInfo.qTrans = qTrans;
            MeshesInfo.meshC = meshC;
            return MeshesInfo;
        }
        static string[] getboneNames(CR2WFile cr2w, string Type)
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
        static Vec3[] getboneposn(CR2WFile cr2w)
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
        static Mesh getMesh(MemoryStream gfs, UInt32 vertCount, UInt32 indCount, UInt32 vertOffset, UInt32 uvOffset, UInt32 normalOffset, UInt32 indOffset, UInt32 vpStride, Vector4 qScale, Vector4 qTrans, UInt32 weightcount)
        {
            BinaryReader gbr = new BinaryReader(gfs);

            Vec3[] vertices = new Vec3[vertCount];
            uint[] indices = new uint[indCount];
            Vec2[] uvs = new Vec2[vertCount];
            Vec3[] normals = new Vec3[vertCount];
            Vec4[] tangents = new Vec4[vertCount];
            float[,] weights = new float[vertCount, weightcount];
            UInt16[,] boneindexes = new UInt16[vertCount, weightcount];
            // geting vertices
            for (int i = 0; i < vertCount; i++)
            {
                gfs.Position = vertOffset + i * vpStride;

                float x = (gbr.ReadInt16() / 32767f)*qScale.X.val + qTrans.X.val;
                float y = (gbr.ReadInt16() / 32767f)*qScale.Y.val + qTrans.Y.val;
                float z = (gbr.ReadInt16() / 32767f)*qScale.Z.val + qTrans.Z.val;
                vertices[i] = new Vec3(x,y,z);
            }
            // got vertices
            // getting uv's as half floats
            float[] values = new float[vertCount * 2];
            gfs.Position = uvOffset;

            Converters converter = new Converters(); // contains methods for halffloats
            for (int i = 0; i < vertCount * 2; i++)
            {
                UInt16 read = gbr.ReadUInt16();
                values[i] = converter.hfconvert(read);
            }

            for (int i = 0; i < vertCount; i++)
            {
                uvs[i] = new Vec2(values[2 * i], values[2 * i + 1]);
            }
            // got uv's as half floats
            // getting 10bit normals
            UInt32 NorRead32;
            Int16 nX, nY, nZ;
            for (int i = 0; i < vertCount; i++)
            {
                gfs.Position = normalOffset + 8 * i;
                NorRead32 = gbr.ReadUInt32();
                nX = Convert.ToInt16(NorRead32 & 0x3ff);
                nY = Convert.ToInt16((NorRead32 >> 10) & 0x3ff);
                nZ = Convert.ToInt16((NorRead32 >> 20) & 0x3ff);
                normals[i] = new Vec3((nX - 512) / 512f, (nY - 512) / 512f, (nZ - 512) / 512f);
            }
            // got 10bit normals
            // getting 10bit tangents
            for (int i = 0; i < vertCount; i++)
            {
                gfs.Position = normalOffset + 4 + 8 * i;
                NorRead32 = gbr.ReadUInt32();
                nX = Convert.ToInt16(NorRead32 & 0x3ff);
                nY = Convert.ToInt16((NorRead32 >> 10) & 0x3ff);
                nZ = Convert.ToInt16((NorRead32 >> 20) & 0x3ff);
                tangents[i] = new Vec4((nX - 512) / 512f, (nY - 512) / 512f, (nZ - 512) / 512f, 1f);
            }
            // getting bone indexes
            for (int i = 0; i < vertCount; i++)
            {
                gfs.Position = vertOffset + i * vpStride + 8;
                for (int e = 0; e < weightcount; e++)
                {
                    boneindexes[i, e] = gbr.ReadByte();
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
            Mesh mesh = new Mesh()
            {
                vertices = vertices,
                indices = indices,
                uvs = uvs,
                normals = normals,
                tangents = tangents,
                boneindexes = boneindexes,
                weights = weights,
                weightcount = weightcount
            };
            return mesh;
        }
        static void ExportASCII(List<Mesh> meshes, bones Bones,string filename)
        {
            if (meshes == null || meshes.Count == 0)
                return;

            int mIndex = -1;
            int meshCount = meshes.Count;
            StringBuilder objS = new StringBuilder();
            // printing bones
            StringBuilder asciiS = new StringBuilder();

            asciiS.AppendLine(string.Format("{0} # Bones", Bones.boneCount));
            for (int i = 0; i < Bones.boneCount; i++)
            {
                asciiS.AppendLine(string.Format("{0}", Bones.bonenames[i]));
                asciiS.AppendLine(string.Format("{0}", Bones.parent[i]));
                asciiS.AppendLine(string.Format("{0} {1} {2}", Bones.posn[i].X, Bones.posn[i].Y, Bones.posn[i].Z));
            }
            objS.Append(asciiS.ToString());
            // done printing bones
            // printing mesh
            objS.AppendLine(string.Format("{0} # meshes", meshCount));

            foreach (var mesh in meshes)
            {
                int vertCount = mesh.vertices.Length;
                int indCount = mesh.indices.Length;
                int uvCount = mesh.uvs.Length;
                int norCount = mesh.normals.Length;
                ++mIndex;

                objS.AppendLine(string.Format(mesh.name));
                objS.AppendLine(string.Format("1 # UV Layers"));
                objS.AppendLine("1 # Textures");
                objS.AppendLine("Texture.png");
                objS.AppendLine("0 # UV Index");
                objS.AppendLine(string.Format("{0} # Vertices", vertCount));

                StringBuilder appS = new StringBuilder();

                for (int i = 0; i < vertCount; i++)
                {
                    Vec3 vert = mesh.vertices[i];
                    appS.AppendLine(string.Format("{0} {1} {2} # Coords", vert.X, vert.Y, vert.Z));
                    Vec3 norm = mesh.normals[i];
                    appS.AppendLine(String.Format("{0} {1} {2} # Norms", norm.X, norm.Y, norm.Z));
                    appS.AppendLine(string.Format("255 255 255 255"));
                    Vec2 uv = mesh.uvs[i];
                    appS.AppendLine(string.Format("{0} {1} # Uv's", uv.X, uv.Y));
                    //        Vector3 tan = mesh.tangents[i];
                    //        appS.AppendLine(String.Format("{0} {1} {2} 1.000000000",tan.x,tan.y,tan.z));
                    for (int e = 0; e < mesh.weightcount; e++)
                    {
                        if (e == (mesh.weightcount - 1))
                            appS.Append(string.Format("{0}", mesh.boneindexes[i, e]));
                        else
                            appS.Append(string.Format("{0} ", mesh.boneindexes[i, e]));
                    }
                    appS.AppendLine();
                    float weightsum = 0;
                    for (int e = 0; e < mesh.weightcount; e++)
                    {
                        weightsum += mesh.weights[i, e];
                        if (e == (mesh.weightcount - 1))
                        {
                            appS.Append(string.Format("{0}", mesh.weights[i, e]));
                            // uncomment only for test  if sum = 1 fine with blender but sucks for noe
                            //    appS.Append(string.Format(" # sum == {0}",weightsum));
                        }
                        else
                            appS.Append(string.Format("{0} ", mesh.weights[i, e]));
                    }
                    appS.AppendLine();
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
            File.WriteAllText(string.Format(filename), objS.ToString());
        }
        static Int16[] getboneParents(FileStream fs, int bonesCount, long offset)
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

        static void RigTOMesh(bones RigCombined, bones bonesCombined,string filename)
        {
            int index = 0;
            bool found = false;
            // updating bone positions from mesh combined bones, can be depreciated maybe
            for (int i = 0; i < RigCombined.boneCount; i++)
            {
                found = false;
                index = 0;
                for (int e = 0; e < bonesCombined.boneCount; e++)
                {
                    if (RigCombined.bonenames[i] == bonesCombined.bonenames[e])
                    {
                        found = true;
                        index = e;
                    }
                }
                if (found)
                    RigCombined.posn[i] = new Vec3(bonesCombined.posn[index].X, bonesCombined.posn[index].Y, bonesCombined.posn[index].Z);
            }

            // updating mesh bone indexes
            for (int i = 0; i < expMeshes.Count; i++)
            {
                for (int e = 0; e < expMeshes[i].vertices.Length; e++)
                {
                    for (int eye = 0; eye < expMeshes[i].weightcount; eye++)
                    {
                        for (UInt16 r = 0; r < RigCombined.boneCount; r++)
                        {
                            if (RigCombined.bonenames[r] == bonesCombined.bonenames[expMeshes[i].boneindexes[e, eye]])
                            {
                                expMeshes[i].boneindexes[e, eye] = r;
                                break;
                            }
                        }
                    }
                }
            }
            ExportASCII(expMeshes, RigCombined,filename);
        }

        static bones ProcessRig(FileStream rig_fs, CR2WFile cr2w)
        {
            bones bones_Rig = new bones();
            bones_Rig.bonenames = getboneNames(cr2w, "animRig");
            bones_Rig.boneCount = bones_Rig.bonenames.Length;

            long offset = 0;
            offset = rig_fs.Length - 48 * bones_Rig.boneCount - 2 * bones_Rig.boneCount;
            bones_Rig.parent = getboneParents(rig_fs, bones_Rig.boneCount, offset);

            offset = rig_fs.Length - 48 * bones_Rig.boneCount;
            BinaryReader br = new BinaryReader(rig_fs);

            double[,,] Mat44 = new double[bones_Rig.boneCount, 4, 4];
            for (int i = 0; i < bones_Rig.boneCount; i++)
            {
                rig_fs.Position = offset + i * 48;
                for (int c = 0; c < 4; c++)
                {
                    if (c == 3)
                        Mat44[i, 3, c] = 1f;
                    else
                        Mat44[i, 3, c] = br.ReadSingle();
                }
            }
            float[] x = new float[bones_Rig.boneCount];
            float[] y = new float[bones_Rig.boneCount];
            float[] z = new float[bones_Rig.boneCount];
            float[] w = new float[bones_Rig.boneCount];

            for (int i = 0; i < bones_Rig.boneCount; i++)
            {
                rig_fs.Position = offset + i * 48 + 16;
                x[i] = br.ReadSingle();
                y[i] = br.ReadSingle();
                z[i] = br.ReadSingle();
                w[i] = br.ReadSingle();
            }
            // quaternion to 3x4 rotation matrix
            for (int i = 0; i < bones_Rig.boneCount; i++)
            {
                Mat44[i, 0, 0] = (1 - 2 * y[i] * y[i] - 2 * z[i] * z[i]);
                Mat44[i, 0, 1] = (2 * x[i] * y[i] - 2 * z[i] * w[i]);
                Mat44[i, 0, 2] = (2 * x[i] * z[i] + 2 * y[i] * w[i]);
                Mat44[i, 0, 3] = 0f;
                Mat44[i, 1, 0] = (2 * x[i] * y[i] + 2 * z[i] * w[i]);
                Mat44[i, 1, 1] = 1 - 2 * x[i] * x[i] - 2 * z[i] * z[i];
                Mat44[i, 1, 2] = 2 * y[i] * z[i] - 2 * x[i] * w[i];
                Mat44[i, 1, 3] = 0f;
                Mat44[i, 2, 0] = (2 * x[i] * z[i] - 2 * y[i] * w[i]);
                Mat44[i, 2, 1] = 2 * y[i] * z[i] + 2 * x[i] * w[i];
                Mat44[i, 2, 2] = 1 - 2 * x[i] * x[i] - 2 * y[i] * y[i];
                Mat44[i, 2, 3] = 0f;
            }

            // transposing rot matrix
            double[,,] Mat33 = new double[bones_Rig.boneCount, 3, 3];
            for (int i = 0; i < bones_Rig.boneCount; i++)
            {
                for (int r = 0; r < 3; r++)
                {
                    for (int c = 0; c < 3; c++)
                    {
                        Mat33[i, r, c] = Mat44[i, r, c];
                    }
                }
            }

            for (int i = 0; i < bones_Rig.boneCount; i++)
            {
                for (int r = 0; r < 3; r++)
                {
                    for (int c = 0; c < 3; c++)
                    {
                        Mat44[i, r, c] = Mat33[i, c, r];
                    }
                }
            }
            // converting local space bones to world space bones
            double[,] MM44 = new double[4, 4];
            int j = 0;
            for (int i = 0; i < bones_Rig.boneCount; i++)
            {
                j = bones_Rig.parent[i];
                if (j != -1)
                {
                    for (int m = 0; m < 4; m++)
                    {
                        for (int e = 0; e < 4; e++)
                        {
                            MM44[m, e] = 0;
                            for (int eye = 0; eye < 4; eye++)
                            {
                                MM44[m, e] += Mat44[i, m, eye] * Mat44[j, eye, e];
                            }
                        }
                    }
                    for (int m = 0; m < 4; m++)
                    {
                        for (int e = 0; e < 4; e++)
                        {
                            Mat44[i, m, e] = MM44[m, e];
                        }
                    }
                }
            }
            bones_Rig.posn = new Vec3[bones_Rig.boneCount];

            // if AposeWorld/AposeMS Exists then..... this can be done better i guess... hehehehe
            if ((cr2w.Chunks[0].data as animRig).APoseMS != null)
            {
                for (int i = 0; i < bones_Rig.boneCount; i++)
                {
                    Mat44[i, 3, 0] = (cr2w.Chunks[0].data as animRig).APoseMS[i].Translation.X.val;
                    Mat44[i, 3, 1] = (cr2w.Chunks[0].data as animRig).APoseMS[i].Translation.Y.val;
                    Mat44[i, 3, 2] = (cr2w.Chunks[0].data as animRig).APoseMS[i].Translation.Z.val;
                    Mat44[i, 3, 3] = (cr2w.Chunks[0].data as animRig).APoseMS[i].Translation.W.val;
                }
            }
            for (int i = 0; i < bones_Rig.boneCount; i++)
            {
                bones_Rig.posn[i] = new Vec3(Convert.ToSingle(Mat44[i, 3, 0]), Convert.ToSingle(Mat44[i, 3, 1]), Convert.ToSingle(Mat44[i, 3, 2]));
            }

            return bones_Rig;
        }
        static bones combineRig(List<string> filename_rig)
        {
            List<bones> bones_temp = new List<bones>();

            for (int i = 0; i < filename_rig.Count; i++)
            {
                FileStream fs = new FileStream(filename_rig[i], FileMode.Open, FileAccess.Read);
                BinaryReader br = new BinaryReader(fs);
                CR2WFile cr2w = new CR2WFile();
                br.BaseStream.Seek(0, SeekOrigin.Begin);
                cr2w.Read(br);
                bones_temp.Add(ProcessRig(fs, cr2w));
            }

            bones bones_combine = new bones();
            bones_combine.boneCount = bones_temp[0].boneCount;

            List<string> names = new List<string>();
            List<Vec3> posn = new List<Vec3>();
            List<Int16> parent = new List<Int16>();
            for (int i = 0; i < bones_temp[0].boneCount; i++)
            {
                names.Add(bones_temp[0].bonenames[i]);
                Vec3 pos = new Vec3(bones_temp[0].posn[i].X, bones_temp[0].posn[i].Y, bones_temp[0].posn[i].Z);
                posn.Add(pos);
                parent.Add(bones_temp[0].parent[i]);
            }
            bool condition = true;
            int index = 0;

            for (int r = 1; r < bones_temp.Count; r++)
            {
                for (int i = 0; i < bones_temp[r].boneCount; i++)
                {
                    condition = true;
                    index = i;
                    for (int e = 0; e < bones_combine.boneCount; e++)
                    {
                        if (bones_temp[r].bonenames[i] == names[e])
                        {
                            condition = false;
                            break;
                        }
                    }
                    if (condition)
                    {
                        bones_combine.boneCount++;
                        names.Add(bones_temp[r].bonenames[index]);
                        Vec3 pos = new Vec3(bones_temp[r].posn[index].X, bones_temp[r].posn[index].Y, bones_temp[r].posn[index].Z);
                        posn.Add(pos);
                        parent.Add(bones_temp[r].parent[index]);
                    }
                }
            }
            for (int r = 1; r < bones_combine.boneCount; r++)
            {
                for (int i = 0; i < bones_temp.Count; i++)
                {
                    for (int e = 0; e < bones_temp[i].boneCount; e++)
                    {
                        if (bones_temp[i].bonenames[e] == names[r])
                        {
                            index = bones_temp[i].parent[e];
                            if (index == -1)
                                continue;
                            if (bones_temp[i].bonenames[index] == "Root")
                                continue;
                            for (Int16 c = 0; c < bones_combine.boneCount; c++)
                            {
                                if (bones_temp[i].bonenames[index] == names[c])
                                {
                                    parent[r] = c;
                                    break;
                                }
                            }
                        }
                    }
                }
            }

            bones_combine.bonenames = new string[bones_combine.boneCount];
            bones_combine.posn = new Vec3[bones_combine.boneCount];
            bones_combine.parent = new Int16[bones_combine.boneCount];

            for (int i = 0; i < bones_combine.boneCount; i++)
            {
                bones_combine.bonenames[i] = names[i];
                Vec3 pos = new Vec3(posn[i].X, posn[i].Y, posn[i].Z);
                bones_combine.posn[i] = pos;
                bones_combine.parent[i] = parent[i];
            }
            return bones_combine;

        }
        static BuffersInfo Getbuffersinfo(FileStream fs, CR2WFile cr2w)
        {
            BinaryReader br = new BinaryReader(fs);
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
        static void Files(string filename_mesh, bones Combined)
        {
            FileStream mesh_fs = new FileStream(filename_mesh, FileMode.Open, FileAccess.Read);
            BinaryReader mesh_br = new BinaryReader(mesh_fs);
            CR2WFile cr2w = new CR2WFile();
            mesh_br.BaseStream.Seek(0, SeekOrigin.Begin);
            cr2w.Read(mesh_br);

            BuffersInfo buffinfo = Getbuffersinfo(mesh_fs, cr2w);
            MemoryStream buffer_fs = new MemoryStream(buffinfo.buffers[buffinfo.meshbufferindex]);

            meshesinfo MeshesInfo = GetMeshesinfo(cr2w);

            if (MeshInfoVerbosity)
                Console.WriteLine("Meshes Info");
            for (int i = 0; i < MeshesInfo.meshC; i++)
            {
                if(MeshInfoVerbosity)
                Console.WriteLine("Counts: " + MeshesInfo.vertCounts[i] + " " + MeshesInfo.indCounts[i] + " Offsets: " + MeshesInfo.vertOffsets[i] + " " + MeshesInfo.uvOffsets[i] + " " + MeshesInfo.normalOffsets[i] + " " + MeshesInfo.unknown1Offsets[i] + " " + MeshesInfo.unknown2Offsets[i] + " " + MeshesInfo.indicesOffsets[i] + " Stride: " + MeshesInfo.vpStrides[i] + " Weight Count: " + MeshesInfo.weightcounts[i] + " LODLevel: " + MeshesInfo.LODLvl[i]);
            }

            if(MeshInfoVerbosity)
            {
                Console.WriteLine("Quantizations");
                Console.WriteLine(MeshesInfo.qScale.X.val + " " + MeshesInfo.qScale.Y.val + " " + MeshesInfo.qScale.Z.val + " " + MeshesInfo.qScale.W.val);
                Console.WriteLine(MeshesInfo.qTrans.X.val + " " + MeshesInfo.qTrans.Y.val + " " + MeshesInfo.qTrans.Z.val + " " + MeshesInfo.qTrans.W.val);
            }

            bones Bones = new bones();

            Bones.bonenames = getboneNames(cr2w, "CMesh");
            Bones.posn = getboneposn(cr2w);
            Bones.boneCount = Bones.bonenames.Length;
            Bones.parent = new Int16[Bones.boneCount];
            for (int i = 0; i < Bones.boneCount; i++)
            {
                Bones.parent[i] = -1;
            }

            for (int i = 0; i < MeshesInfo.meshC; i++)
            {
                if (MeshesInfo.LODLvl[i] != 1 && LOD_filter)
                    continue;
                Mesh mesh = getMesh(buffer_fs, MeshesInfo.vertCounts[i], MeshesInfo.indCounts[i], MeshesInfo.vertOffsets[i], MeshesInfo.uvOffsets[i], MeshesInfo.normalOffsets[i], MeshesInfo.indicesOffsets[i], MeshesInfo.vpStrides[i], MeshesInfo.qScale, MeshesInfo.qTrans, MeshesInfo.weightcounts[i]);
                mesh.name = Path.GetFileName(filename_mesh).Replace(".mesh", string.Format("_mesh_{0}", i));

                // updating mesh bone indexes
                for (int e = 0; e < mesh.vertices.Length; e++)
                {
                    for (int eye = 0; eye < mesh.weightcount; eye++)
                    {
                        for (UInt16 r = 0; r < Combined.boneCount; r++)
                        {
                            if (Combined.bonenames[r] == Bones.bonenames[mesh.boneindexes[e, eye]])
                            {
                                mesh.boneindexes[e, eye] = r;
                                break;
                            }
                        }
                    }
                }
                expMeshes.Add(mesh);
            }
        }
        static bones combineMeshBones(List<string> filename_mesh)
        {
            List<bones> Bones_Mesh = new List<bones>();
            bones bones_combine = new bones();
            List<string> names = new List<string>();
            List<Vec3> posn = new List<Vec3>();
            List<Int16> parent = new List<Int16>();
            bones_combine.boneCount = 0;
            for (int i = 0; i < filename_mesh.Count; i++)
            {
                FileStream mesh_fs = new FileStream(filename_mesh[i], FileMode.Open, FileAccess.Read);
                BinaryReader mesh_br = new BinaryReader(mesh_fs);

                CR2WFile mesh_cr2w = new CR2WFile();
                mesh_br.BaseStream.Seek(0, SeekOrigin.Begin);
                mesh_cr2w.Read(mesh_br);                

                bones Bones = new bones();
                Bones.bonenames = getboneNames(mesh_cr2w, "CMesh");
                Bones.posn = getboneposn(mesh_cr2w);
                Bones.boneCount = Bones.bonenames.Length;
                Bones.parent = new Int16[Bones.boneCount];
                for (int e = 0; e < Bones.boneCount; e++)
                {
                    Bones.parent[e] = -1;
                }
                Bones_Mesh.Add(Bones);
                
            }
            for (int i = 0; i < Bones_Mesh[0].boneCount; i++)
            {
                names.Add(Bones_Mesh[0].bonenames[i]);
                Vec3 pos = new Vec3(Bones_Mesh[0].posn[i].X, Bones_Mesh[0].posn[i].Y, Bones_Mesh[0].posn[i].Z);
                posn.Add(pos);
                parent.Add(Bones_Mesh[0].parent[i]);
                bones_combine.boneCount++;
            }
            bool found = false;
            for (int i = 0; i < Bones_Mesh.Count; i++)
            {
                for (int e = 0; e < Bones_Mesh[i].boneCount; e++)
                {
                    found = false;
                    for (int eye = 0; eye < bones_combine.boneCount; eye++)
                    {
                        if (Bones_Mesh[i].bonenames[e] == names[eye])
                        {
                            found = true;
                            break;
                        }
                    }
                    if (found == false)
                    {
                        names.Add(Bones_Mesh[i].bonenames[e]);
                        Vec3 pos = new Vec3(Bones_Mesh[i].posn[e].X, Bones_Mesh[i].posn[e].Y, Bones_Mesh[i].posn[e].Z);
                        posn.Add(pos);
                        parent.Add(Bones_Mesh[i].parent[e]);
                        bones_combine.boneCount++;
                    }
                }
            }
            bones_combine.posn = new Vec3[bones_combine.boneCount];
            bones_combine.bonenames = new string[bones_combine.boneCount];
            bones_combine.parent = new Int16[bones_combine.boneCount];
            for (int i = 0; i < bones_combine.boneCount; i++)
            {
                Vec3 pos = new Vec3(posn[i].X, posn[i].Y, posn[i].Z);
                bones_combine.posn[i] = pos;
                bones_combine.bonenames[i] = names[i];
                bones_combine.parent[i] = parent[i];
            }
            return bones_combine;
        }
        static void Drugdealer(List<string> filename_mesh, List<string> filename_rig)
        {
            bones bonesCombined = combineMeshBones(filename_mesh);

            for (int i = 0; i < filename_mesh.Count; i++)
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("\nDealing with: " + filename_mesh[i]);
                Console.ResetColor();
                Files(filename_mesh[i], bonesCombined);
            }

            if (filename_rig.Count >= 1)
            {
                bones RigCombined = combineRig(filename_rig);

                bool tester = true;
                for (int i = 0; i < bonesCombined.boneCount; i++)
                {
                    tester = true;
                    for (int e = 0; e < RigCombined.boneCount; e++)
                    {
                        if (bonesCombined.bonenames[i] == RigCombined.bonenames[e])
                        {
                            tester = false;
                            break;
                        }
                    }
                    if (tester)
                    {
                        Console.ForegroundColor = ConsoleColor.Red;
                        Console.WriteLine("\nThis Particular Bone is Missing From Any Of The Provided Rigs: " + bonesCombined.bonenames[i]);
                        Console.ResetColor();
                        break;
                    }
                }

                if(tester)
                {
                    Console.ForegroundColor = ConsoleColor.Red;
                    Console.WriteLine("\nProvided Rigs Are Incomplete/Missing/Incompatible");
                    Console.ResetColor();
                }
                else
                {
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("\nProvided Rigs Are Compatible, Rig Export Should Work fine");
                    Console.ResetColor();
                }
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.Write("\nExport hierarchical Model(y/n): ");
                Console.ResetColor();

                char y = 'n';
                y = Console.ReadKey().KeyChar;
                if (y == 'y' || y == 'Y')
                {
                    string exportname = Path.GetDirectoryName(filename_mesh[0]) + "\\rigscombined.mesh.ascii";
                    RigTOMesh(RigCombined, bonesCombined,exportname);
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("\nExport Filename: " + exportname);
                }
                else
                {
                    string exportname = Path.GetDirectoryName(filename_mesh[0]) + "\\combined.mesh.ascii";
                    ExportASCII(expMeshes, bonesCombined, exportname);
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("\nExport Filename: " + exportname);
                }
            }
            else
            {
                if(filename_mesh.Count == 1)
                {
                    string exportname = filename_mesh[0] + ".ascii";
                    ExportASCII(expMeshes, bonesCombined, exportname);
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("\nExport Filename: " + exportname);
                }
                else
                {
                    string exportname = Path.GetDirectoryName(filename_mesh[0]) + "\\combined.mesh.ascii";
                    ExportASCII(expMeshes, bonesCombined, exportname);
                    Console.ForegroundColor = ConsoleColor.Red;
                    Console.WriteLine("No Rigs Found!");
                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine("\nExport Filename: " + exportname);
                }
            }
            Console.ResetColor();
            expMeshes.Clear();
        }
        static void OpM()
        {
            List<string> filename_mesh = new List<string>();
            List<string> filename_rig = new List<string>();
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.Write("\nEnter Filepath: ");
            Console.ResetColor();
            string  name = Console.ReadLine();
            if (name.Contains("\""))
                name = name.Replace("\"", string.Empty);

            if (File.Exists(name))
            {
                filename_mesh.Add(name);
                Drugdealer(filename_mesh, filename_rig);
                filename_mesh.Clear();
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("Invalid File Path");
                Console.ResetColor();
            }
        }
        static void OpD()
        {
            List<string> filename_mesh = new List<string>();
            List<string> filename_rig = new List<string>();
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.Write("\nEnter Directory: ");
            Console.ResetColor();
            string dir = Console.ReadLine();
            if (dir.Contains("\""))
                dir = dir.Replace("\"", string.Empty);

            if (Directory.Exists(dir))
            {
                List<string> names = new List<string>(Directory.GetFiles(dir, "*.mesh", SearchOption.AllDirectories));
                if (names.Count >= 1)
                {
                    for (int i = 0; i < names.Count; i++)
                    {
                        filename_mesh.Add(names[i]);
                        Drugdealer(filename_mesh, filename_rig);
                        filename_mesh.Clear();
                    }
                }
                else
                {
                    Console.ForegroundColor = ConsoleColor.Red;
                    Console.WriteLine("Specified Directory Contains no mesh files");
                    Console.ResetColor();
                }
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("Invalid Directory");
                Console.ResetColor();
            }
        }
        static void OpR()
        {
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.Write("\nEnter Directory: ");
            Console.ResetColor();
            string dir = Console.ReadLine();
            if (dir.Contains("\""))
                dir = dir.Replace("\"", string.Empty);

            if (Directory.Exists(dir))
            {
                List<string> filename_mesh = new List<string>(Directory.GetFiles(dir, "*.mesh"));
                List<string> filename_rig = new List<string>(Directory.GetFiles(dir, "*.rig"));
                if (filename_mesh.Count >= 1)
                    Drugdealer(filename_mesh, filename_rig);
                else
                {
                    Console.ForegroundColor = ConsoleColor.Red;
                    Console.WriteLine("Specified Directory Contains no mesh files");
                    Console.ResetColor();
                }
            }
            else
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("Invalid Directory");
                Console.ResetColor();
            }
        }
    }
    public struct meshesinfo
    {
        public UInt32[] vertCounts;
        public UInt32[] indCounts;
        public UInt32[] vertOffsets;
        public UInt32[] uvOffsets;
        public UInt32[] normalOffsets;
        public UInt32[] unknown1Offsets;
        public UInt32[] unknown2Offsets;
        public UInt32[] indicesOffsets;
        public UInt32[] vpStrides;
        public UInt32[] weightcounts;
        public Vector4 qTrans;
        public Vector4 qScale;
        public int meshC;

        public UInt32[] LODLvl;
    }

    public class bones
    {
        public string[] bonenames;
        public Vec3[] posn;
        public Int16[] parent;
        public int boneCount;
    }
    public class Mesh
    {
        public Vec3[] vertices { get; set; }
        public uint[] indices { get; set; }
        public Vec2[] uvs { get; set; }
        public Vec3[] normals { get; set; }
        public Vec4[] tangents { get; set; }
        public float[,] weights { get; set; }
        public UInt16[,] boneindexes { get; set; }
        public UInt32 weightcount { get; set; }
        public string name;
    }
    public class BuffersInfo
    {
        public List<byte[]> buffers;
        public int meshbufferindex;
    }
}
