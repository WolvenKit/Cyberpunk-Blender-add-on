using System;
using System.IO;
using CP77.CR2W;
using GeneralStructs;
using CP77.CR2W.Types;
using WolvenKit.Common.Oodle;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace CP77.MeshFile.Materials
{
    class MATERIAL
    {
        public static void GetMateriaEntries(MemoryStream meshStream)
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
        static void ParseMaterialInstance(CMaterialInstance cMaterialInstance)
        {

        }
        static MemoryStream GetMaterialStream(MemoryStream ms,CR2WFile cr2w)
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
        /*
        public static void ParseMaterials(MemoryStream meshStream, string _meshName, bool Filter, string outfile)
        {
            DiffusedBSDF material = new DiffusedBSDF();
            material.AlbedoTEX = @"C:\Users\Abhinav\Desktop\New folder (4)\texs\h0_001_wa_c__judy_d01.png";
            material.NormalTEX = @"C:\Users\Abhinav\Desktop\New folder (4)\texs\h0_001_wa_c__judy_n01.png";
            MemoryImage diffuseimage = new MemoryImage(material.AlbedoTEX);
            MemoryImage normalimage = new MemoryImage(material.NormalTEX);


            MaterialBuilder mat = new MaterialBuilder("Default").WithMetallicRoughness(0,(float)0.5);
            mat.WithBaseColor(diffuseimage, new Vec4((float)0.792157, (float)0.694118, (float)0.6, 1));
            //mat.UseChannel(KnownChannel.BaseColor).UseTexture().WithPrimaryImage(ImageBuilder.From(diffuseimage, "h0_001_wa_c__judy_d01")).WithTransform(new Vec2(0,0), new Vec2(1,1),0,0);
            mat.UseChannel(KnownChannel.Normal).UseTexture().WithPrimaryImage(ImageBuilder.From(normalimage, "h0_001_wa_c__judy_n01")).WithTransform(new Vec2(0, 0), new Vec2(1, 1), 0, 0);
            List<RawMeshContainer> expMeshes = new List<RawMeshContainer>();

            BinaryReader br = new BinaryReader(meshStream);
            CR2WFile cr2w = new CR2WFile();
            br.BaseStream.Seek(0, SeekOrigin.Begin);
            cr2w.Read(br);

            CP77.MeshFile.MeshFile.BuffersInfo buffinfo = CP77.MeshFile.MeshFile.Getbuffersinfo(meshStream, cr2w);
            MemoryStream ms = new MemoryStream(buffinfo.buffers[buffinfo.meshbufferindex]);
            MeshesInfo meshinfo = CP77.MeshFile.MeshFile.GetMeshesinfo(cr2w);
            for (int i = 0; i < meshinfo.meshC; i++)
            {
                if (meshinfo.LODLvl[i] != 1 && Filter)
                    continue;
                RawMeshContainer mesh = CP77.MeshFile.MeshFile.ContainRawMesh(ms, meshinfo.vertCounts[i], meshinfo.indCounts[i], meshinfo.vertOffsets[i], meshinfo.tx0Offsets[i], meshinfo.normalOffsets[i], meshinfo.colorOffsets[i], meshinfo.unknownOffsets[i], meshinfo.indicesOffsets[i], meshinfo.vpStrides[i], meshinfo.qScale, meshinfo.qTrans, meshinfo.weightcounts[i]);
                mesh.name = _meshName + "_" + i;
                expMeshes.Add(mesh);
            }
            ModelRoot model = RigidMeshesWithMaterialsToGLTF(expMeshes, mat);
            model.SaveGLB(outfile);
        }
        */
    }
}
