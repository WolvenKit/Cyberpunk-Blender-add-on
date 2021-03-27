using System;
using System.IO;
using CP77.CR2W;
using WolvenKit.RED4.GeneralStructs;
using WolvenKit.RED4.CR2W;
using WolvenKit.RED4.CR2W.Types;
using WolvenKit.Common.Oodle;
using System.Collections.Generic;
using Newtonsoft.Json;
using SharpGLTF.Schema2;
using SharpGLTF.Memory;
using SharpGLTF.Scenes;
using SharpGLTF.Materials;
using WolvenKit.RED4.MeshFile;
using SharpGLTF.Geometry.VertexTypes;
using SharpGLTF.Geometry;

namespace WolvenKit.RED4.MeshFile.Materials
{
    using Vec4 = System.Numerics.Vector4;
    using Vec2 = System.Numerics.Vector2;
    using Vec3 = System.Numerics.Vector3;

    using RIGIDVERTEX = VertexBuilder<VertexPositionNormalTangent, VertexColor1Texture2, VertexEmpty>;
    using RIGIDMESH = MeshBuilder<VertexPositionNormalTangent, VertexColor1Texture2, VertexEmpty>;

    using VPNT = VertexPositionNormalTangent;
    using VCT = VertexColor1Texture2;
    public class MATERIAL
    {
        public static void GetMateriaEntries(Stream meshStream)
        {
            var cr2w = ModTools.TryReadCr2WFile(meshStream);

            int index = 0;
            for (int i = 0; i < cr2w.Chunks.Count; i++)
            {
                if (cr2w.Chunks[i].REDType == "CMesh")
                {
                    index = i;
                }
            }

            int count = (cr2w.Chunks[index].data as CMesh).MaterialEntries.Count;
            MaterialEntry[] materialEntries = new MaterialEntry[count];

            for (int i = 0; i < count; i++)
            {
                materialEntries[i] = new MaterialEntry();
                materialEntries[i].Name = (cr2w.Chunks[index].data as CMesh).MaterialEntries[i].Name.Value;
            }

            bool isbuffered = true;
            if ((cr2w.Chunks[index].data as CMesh).LocalMaterialBuffer.RawDataHeaders.Count == 0)
                isbuffered = false;

            List<CMaterialInstance> cMaterialInstances = new List<CMaterialInstance>();
            if (isbuffered)
            {
                MemoryStream materialStream = GetMaterialStream(meshStream, cr2w);
                byte[] bytes = materialStream.ToArray();
                for (int i = 0; i < count; i++)
                {
                    UInt32 offset = (cr2w.Chunks[index].data as CMesh).LocalMaterialBuffer.RawDataHeaders[i].Offset.Value;
                    UInt32 size = (cr2w.Chunks[index].data as CMesh).LocalMaterialBuffer.RawDataHeaders[i].Size.Value;

                    MemoryStream ms = new MemoryStream(bytes, (int)offset, (int)size);
                    var mtcr2w = ModTools.TryReadCr2WFile(ms);
                    cMaterialInstances.Add((mtcr2w.Chunks[0].data as CMaterialInstance));
                }
            }
            else
            {
                for (int i = 0; i < cr2w.Chunks.Count; i++)
                {
                    if (cr2w.Chunks[i].REDType == "CMaterialInstance")
                    {
                        index = i;
                    }
                }
                cMaterialInstances.Add((cr2w.Chunks[index].data as CMaterialInstance));
            }
        }
        public static void ParseMaterialInstance(/*CMaterialInstance cMaterialInstance*/)
        {
            var scene = new SceneBuilder();
            var model = scene.ToGltf2();
            string AlbedoTEX = @"E:\stuff\New folder (4)\texs\h0_001_wa_c__judy_d01.png";
            string NormalTEX = @"E:\stuff\New folder (4)\texs\h0_001_wa_c__judy_n01.png";
            MemoryImage diffuseimage = new MemoryImage(AlbedoTEX);
            MemoryImage normalimage = new MemoryImage(NormalTEX);
            model.UseImage(diffuseimage).Name = "h0_001_wa_c__judy_d01";
            model.UseImage(normalimage).Name = "h0_001_wa_c__judy_n01";

            model.SaveGLB(@"E:\stuff\bb.gltf");
        }
        static MemoryStream GetMaterialStream(Stream ms,CR2WFile cr2w)
        {
            MemoryStream materialStream = new MemoryStream();

            var buffers = cr2w.Buffers;
            for (var i = 0; i < buffers.Count; i++)
            {
                var b = buffers[i];
                ms.Seek(b.Offset, SeekOrigin.Begin);

                MemoryStream outstream = new MemoryStream();
                // copy to some outstream
                ms.DecompressAndCopySegment(outstream, b.DiskSize, b.MemSize);

                BinaryReader outreader = new BinaryReader(outstream);
                outstream.Position = 161;
                if (new string(outreader.ReadChars(17)) == "CMaterialInstance")
                {
                    materialStream = outstream;
                    break;
                }
            }

            return materialStream;
        }
        
        public static void ParseMaterials(Stream meshStream, string _meshName, string outfile, bool LodFilter = true, bool isGLBinary = true)
        {
            DiffusedBSDF material = new DiffusedBSDF();
            material.AlbedoTEX = @"E:\stuff\New folder (4)\texs\h0_001_wa_c__judy_d01.png";
            material.NormalTEX = @"E:\stuff\New folder (4)\texs\h0_001_wa_c__judy_n01.png";
            MemoryImage diffuseimage = new MemoryImage(material.AlbedoTEX);
            MemoryImage normalimage = new MemoryImage(material.NormalTEX);


            MaterialBuilder mat = new MaterialBuilder("Default").WithMetallicRoughness(0,(float)0.5);
            mat.WithBaseColor(diffuseimage, new Vec4((float)0.792157, (float)0.694118, (float)0.6, 1));
            mat.UseChannel(KnownChannel.BaseColor).UseTexture().WithPrimaryImage(ImageBuilder.From(diffuseimage, "h0_001_wa_c__judy_d01")).WithTransform(new Vec2(0,0), new Vec2(1,1),0,0);
            mat.UseChannel(KnownChannel.Normal).UseTexture().WithPrimaryImage(ImageBuilder.From(normalimage, "h0_001_wa_c__judy_n01")).WithTransform(new Vec2(0, 0), new Vec2(1, 1), 0, 0);
            List<RawMeshContainer> expMeshes = new List<RawMeshContainer>();

            BinaryReader br = new BinaryReader(meshStream);
            var cr2w = CP77.CR2W.ModTools.TryReadCr2WFile(meshStream);

            MemoryStream ms = MESH.GetMeshBufferStream(meshStream, cr2w);
            MeshesInfo meshinfo = MESH.GetMeshesinfo(cr2w);
            for (int i = 0; i < meshinfo.meshC; i++)
            {
                if (meshinfo.LODLvl[i] != 1 && LodFilter)
                    continue;
                RawMeshContainer mesh = MESH.ContainRawMesh(ms, meshinfo.vertCounts[i], meshinfo.indCounts[i], meshinfo.vertOffsets[i], meshinfo.tx0Offsets[i], meshinfo.normalOffsets[i], meshinfo.colorOffsets[i], meshinfo.unknownOffsets[i], meshinfo.indicesOffsets[i], meshinfo.vpStrides[i], meshinfo.qScale, meshinfo.qTrans, meshinfo.weightcounts[i]);
                mesh.name = _meshName + "_" + i;
                expMeshes.Add(mesh);
            }
            ModelRoot model = RigidMeshesWithMaterialsToGLTF(expMeshes, mat);

            if (isGLBinary)
                model.SaveGLB(outfile);
            else
                model.SaveGLTF(outfile);
        }
        static ModelRoot RigidMeshesWithMaterialsToGLTF(List<RawMeshContainer> meshes, MaterialBuilder mat)
        {
            var scene = new SceneBuilder();

            foreach (var mesh in meshes)
            {
                long indCount = mesh.indices.Length;
                var expmesh = new RIGIDMESH(mesh.name);

                var prim = expmesh.UsePrimitive(mat);
                for (int i = 0; i < indCount; i += 3)
                {
                    uint idx0 = mesh.indices[i + 1];
                    uint idx1 = mesh.indices[i];
                    uint idx2 = mesh.indices[i + 2];

                    //VPNT
                    Vec3 p_0 = new Vec3(mesh.vertices[idx0].X, mesh.vertices[idx0].Y, mesh.vertices[idx0].Z);
                    Vec3 n_0 = new Vec3(mesh.normals[idx0].X, mesh.normals[idx0].Y, mesh.normals[idx0].Z);
                    Vec4 t_0 = new Vec4(mesh.tangents[idx0].X, mesh.tangents[idx0].Y, mesh.tangents[idx0].Z, mesh.tangents[idx0].W);

                    Vec3 p_1 = new Vec3(mesh.vertices[idx1].X, mesh.vertices[idx1].Y, mesh.vertices[idx1].Z);
                    Vec3 n_1 = new Vec3(mesh.normals[idx1].X, mesh.normals[idx1].Y, mesh.normals[idx1].Z);
                    Vec4 t_1 = new Vec4(mesh.tangents[idx1].X, mesh.tangents[idx1].Y, mesh.tangents[idx1].Z, mesh.tangents[idx1].W);

                    Vec3 p_2 = new Vec3(mesh.vertices[idx2].X, mesh.vertices[idx2].Y, mesh.vertices[idx2].Z);
                    Vec3 n_2 = new Vec3(mesh.normals[idx2].X, mesh.normals[idx2].Y, mesh.normals[idx2].Z);
                    Vec4 t_2 = new Vec4(mesh.tangents[idx2].X, mesh.tangents[idx2].Y, mesh.tangents[idx2].Z, mesh.tangents[idx2].W);

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
                scene.AddRigidMesh(expmesh, System.Numerics.Matrix4x4.CreateFromQuaternion(new System.Numerics.Quaternion((float)-0.707107, 0, 0, (float)0.707107))); // to rotate mesh +Z up in blender
            }
            var model = scene.ToGltf2();
            return model;
        }
    }
}
