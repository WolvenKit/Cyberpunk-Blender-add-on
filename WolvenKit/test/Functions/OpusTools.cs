using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace WolvenKit.Modkit.RED4.Opus
{
    class OpusTools
    {
        public static void Parse()
        {

        }
    }
    class OpusInfo
    {
                                    //  S       N       D   ?....
        public byte[] Header { get; } = { 0x53, 0x4E, 0x44, 0x20, 0x02, 0x00, 0x00, 0xF0, 0x00, 0x00, 0x00, 0x00 };
        public UInt32 OpusCount { get; set; }
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
        public OpusInfo(MemoryStream ms)
        {
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
    }
}
