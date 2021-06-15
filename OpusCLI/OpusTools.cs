using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Diagnostics;

namespace WolvenKit.Modkit.RED4.Opus
{
    class OpusTools
    {
        public static void Parse(FileInfo opusinfofile,DirectoryInfo paksdir,DirectoryInfo outdir)
        {
            FileStream fs = new FileStream(opusinfofile.FullName, FileMode.Open, FileAccess.Read);
            OpusInfo info = new OpusInfo(fs);


            string[] files = Directory.GetFiles(paksdir.FullName, "*.opuspak").OrderBy(f => Convert.ToUInt32(f.Replace(".opuspak", string.Empty).Substring(f.LastIndexOf('_') + 1))).ToArray();
            Stream[] paks = new Stream[files.Length];
            for(int i = 0; i < files.Length; i++)
            {
                paks[i] = new FileStream(files[i], FileMode.Open, FileAccess.Read);
            }
            info.WriteAllOpusFromPaks(paks, outdir);
            
        }
    }
    class OpusInfo
    {
                                    //  S       N       D   ?....
        public byte[] Header { get; } = { 0x53, 0x4E, 0x44, 0x20, 0x02, 0x00, 0x00, 0xF0, 0x00, 0x00, 0x00, 0x00 };
        public  UInt32 OpusCount { get; set; }
        public UInt32 GroupingObjSize4x { get; set; }
        public UInt32[] OpusHashes { get; set; }
        public UInt16[] PackIndices { get; set; }
        public UInt32[] OpusOffsets { get; set; }
        public UInt16[] RiffOpusOffsets { get; set; }
        public UInt32[] OpusStreamLengths { get; set; }
        public UInt32[] WavStreamLengths { get; set; }
        public List<Group> GroupObjs { get; set; }
        public class Group
        {
            public UInt32 Hash { get; set; }
            public UInt32 MemberCount { get; set; }
            public UInt32[] MemberHashes { get; set; }
        }
        public OpusInfo(Stream ms)
        {
            ms.Position = 0xc;
            BinaryReader br = new BinaryReader(ms);
            OpusCount = br.ReadUInt32();
            GroupingObjSize4x = br.ReadUInt32();

            OpusHashes = new UInt32[OpusCount];
            for(int i = 0; i < OpusCount; i++)
            {
                OpusHashes[i] = br.ReadUInt32();
            }

            PackIndices = new UInt16[OpusCount];
            for (int i = 0; i < OpusCount; i++)
            {
                PackIndices[i] = br.ReadUInt16();
            }

            OpusOffsets = new UInt32[OpusCount];
            for (int i = 0; i < OpusCount; i++)
            {
                OpusOffsets[i] = br.ReadUInt32();
            }

            RiffOpusOffsets = new UInt16[OpusCount];
            for (int i = 0; i < OpusCount; i++)
            {
                RiffOpusOffsets[i] = br.ReadUInt16();
            }

            OpusStreamLengths = new UInt32[OpusCount];
            for (int i = 0; i < OpusCount; i++)
            {
                OpusStreamLengths[i] = br.ReadUInt32();
            }

            WavStreamLengths = new UInt32[OpusCount];
            for (int i = 0; i < OpusCount; i++)
            {
                WavStreamLengths[i] = br.ReadUInt32();
            }
            GroupObjs = new List<Group>();
            while (ms.Position < ms.Length)
            {
                Group group = new Group();
                group.Hash = br.ReadUInt32();
                group.MemberCount = br.ReadUInt32();
                group.MemberHashes = new UInt32[group.MemberCount];
                for(UInt32 i = 0; i < group.MemberCount; i++)
                {
                    group.MemberHashes[i] = br.ReadUInt32();
                }
                GroupObjs.Add(group);
            }
        }
        public void WriteAllOpusFromPaks(Stream[] opuspaks,DirectoryInfo outdir)
        {
            BinaryReader[] brs = new BinaryReader[opuspaks.Length];
            for(int i = 0; i < opuspaks.Length; i++)
            {
                brs[i] = new BinaryReader(opuspaks[i]);
            }
            for(UInt32 i =0; i < OpusCount; i++)
            {
                opuspaks[PackIndices[i]].Position = OpusOffsets[i] + RiffOpusOffsets[i];
                //Console.WriteLine(OpusHashes[i] + " " + PackIndices[i] + " " + (OpusOffsets[i] + RiffOpusOffsets[i]) + " " + (OpusStreamLengths[i] - RiffOpusOffsets[i]));
                byte[] bytes = brs[PackIndices[i]].ReadBytes(Convert.ToInt32(OpusStreamLengths[i] - RiffOpusOffsets[i]));
                string name = OpusHashes[i] + ".opus";
                File.WriteAllBytes(Path.Combine(outdir.FullName,name),bytes);
            }
        }
        public void WriteOpusFromPaks(Stream[] opuspaks, DirectoryInfo outdir, UInt32 hash)
        {
            BinaryReader[] brs = new BinaryReader[opuspaks.Length];
            for (int i = 0; i < opuspaks.Length; i++)
            {
                brs[i] = new BinaryReader(opuspaks[i]);
            }

            for (UInt32 i = 0; i < OpusCount; i++)
            {
                if(OpusHashes[i] == hash)
                {
                    opuspaks[PackIndices[i]].Position = OpusOffsets[i] + RiffOpusOffsets[i];
                    byte[] bytes = brs[PackIndices[i]].ReadBytes(Convert.ToInt32(OpusStreamLengths[i] - RiffOpusOffsets[i]));
                    string name = OpusHashes[i] + ".opus";
                    File.WriteAllBytes(Path.Combine(outdir.FullName, name), bytes);
                    break;
                }
            }
        }
        public void WriteOpusToPak(MemoryStream opus,ref Stream pak, UInt32 hash, MemoryStream wav)
        {
            BinaryReader br = new BinaryReader(pak);
            pak.Position = 0;
            int index = 0;
            for(int i = 0; i < OpusCount; i++)
            {
                if (hash == OpusHashes[i])
                    index = i;
            }
            int pakIdx = PackIndices[index];
            List<int> indices = new List<int>();
            for (int i = 0; i < OpusCount; i++)
            {
                if (pakIdx == PackIndices[i])
                    indices.Add(i);
            }

            MemoryStream ms = new MemoryStream();
            BinaryWriter bw = new BinaryWriter(ms);
            ms.Position = 0;
            for (int i = 0; i < indices.Count; i++)
            {
                UInt32 temp = Convert.ToUInt32(ms.Position);
                if(hash == OpusHashes[indices[i]])
                {
                    pak.Position = OpusOffsets[indices[i]] + 8;
                    var bytes = br.ReadBytes(RiffOpusOffsets[indices[i]] - 12);
                    bw.Write(new byte[] { 0x52, 0x49, 0x46, 0x46 }); //RIFF
                    bw.Write(Convert.ToUInt32(wav.Length - 44 + RiffOpusOffsets[indices[i]] - 8));
                    bw.Write(bytes);
                    bw.Write(Convert.ToUInt32(wav.Length - 44));
                    bw.Write(opus.ToArray());

                    WavStreamLengths[indices[i]] = Convert.ToUInt32(wav.Length - 44 + RiffOpusOffsets[indices[i]]);
                    OpusStreamLengths[indices[i]] = Convert.ToUInt32(opus.Length + RiffOpusOffsets[indices[i]]);
                    OpusOffsets[indices[i]] = Convert.ToUInt32(temp);
                }
                else
                {
                    pak.Position = OpusOffsets[indices[i]];
                    var bytes = br.ReadBytes(Convert.ToInt32(OpusStreamLengths[indices[i]]));
                    bw.Write(bytes);
                    OpusOffsets[indices[i]] = Convert.ToUInt32(temp);
                }
            }

            pak = ms;
            //File.WriteAllBytes(@"C:\Users\Abhinav\Desktop\mod\sfx_container_1280.opuspak",ms.ToArray());
        }
        public void WriteOpusInfo(DirectoryInfo dir)
        {
            MemoryStream ms = new MemoryStream();
            BinaryWriter bw = new BinaryWriter(ms);

            bw.Write(Header);
            bw.Write(OpusCount);
            bw.Write(GroupingObjSize4x);
            for(int i = 0; i < OpusCount; i++)
            {
                bw.Write(OpusHashes[i]);
            }
            for (int i = 0; i < OpusCount; i++)
            {
                bw.Write(PackIndices[i]);
            }
            for (int i = 0; i < OpusCount; i++)
            {
                bw.Write(OpusOffsets[i]);
            }
            for (int i = 0; i < OpusCount; i++)
            {
                bw.Write(RiffOpusOffsets[i]);
            }
            for (int i = 0; i < OpusCount; i++)
            {
                bw.Write(OpusStreamLengths[i]);
            }
            for (int i = 0; i < OpusCount; i++)
            {
                bw.Write(WavStreamLengths[i]);
            }

            for (int i = 0; i < GroupObjs.Count; i++)
            {
                bw.Write(GroupObjs[i].Hash);
                bw.Write(GroupObjs[i].MemberCount);
                for(int e = 0; e < GroupObjs[i].MemberCount; e++)
                {
                    bw.Write(GroupObjs[i].MemberHashes[e]);
                }
            }
            File.WriteAllBytes(Path.Combine(dir.FullName,"sfx_container.opusinfo"), ms.ToArray());
        }
    }
}
