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
using CP77.RigFile;
using CP77.MeshFile;

namespace GLTFNodesTest
{
    class Program
    {
        public static bool LOD_filter = true;
        public static List<RawMeshContainer> expMeshes = new List<RawMeshContainer>();
        [STAThread]
        static void Main(string[] args)
        {
            ServiceLocator.Default.RegisterType<ILoggerService, LoggerService>();


            string filename_rig = @"C:\Users\Abhinav\Desktop\New folder (2)\rigs\woman_base_deformations.rig";
            string filename_mesh = @"C:\Users\Abhinav\Desktop\New folder (2)\t0_001_wa_body__judy.mesh";

            byte[] mbytes = File.ReadAllBytes(filename_mesh);
            MemoryStream mms = new MemoryStream(mbytes);
            CP77.MeshFile.MeshFile.ExportMeshWithoutRig(mms, true);

            byte[] rbytes = File.ReadAllBytes(filename_rig);
            MemoryStream rms = new MemoryStream(rbytes);
            CP77.MeshFile.MeshFile.ExportMeshWithRig(mms,rms, true);
        }
    }
}