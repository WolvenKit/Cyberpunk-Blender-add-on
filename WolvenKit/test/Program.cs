using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Globalization;
using System.Threading;
using Catel.IoC;
using CP77.CR2W;
using WolvenKit.Common.Services;
using CP77.CR2W.Types;
using WolvenKit.Common.Oodle;
using SharpGLTF.Geometry;
using SharpGLTF.Geometry.VertexTypes;
using SharpGLTF.Materials;
using SharpGLTF.Scenes;
using System.Text;
using GeneralStructs;
using CP77Rigs;

namespace GLTFNodesTest
{
    class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            ServiceLocator.Default.RegisterType<ILoggerService, LoggerService>();
            string filename = @"C:\Users\Abhinav\Desktop\New folder (2)\rigs\woman_base_deformations.rig";
            FileStream fs = new FileStream(filename, FileMode.Open, FileAccess.Read);

            BinaryReader br = new BinaryReader(fs);
            CR2WFile cr2w = new CR2WFile();
            br.BaseStream.Seek(0, SeekOrigin.Begin);
            cr2w.Read(br);

            RawArmature rig = CP77Rig.ProcessRig(fs, cr2w);

            StringBuilder sbr = new StringBuilder();

            for (int i = 0; i < rig.BoneCount; i++)
                sbr.AppendLine(string.Format("v {0} {1} {2}", rig.APoseMSMat[i].M41, rig.APoseMSMat[i].M42, rig.APoseMSMat[i].M43));
           File.WriteAllText(@"test.obj", sbr.ToString());
        }
    }
}