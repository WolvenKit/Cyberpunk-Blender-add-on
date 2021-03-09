using System;
using System.IO;
using Catel.IoC;
using WolvenKit.Common.Services;

namespace GLTFNodesTest
{
    class Program
    {
        static void Main(string[] args)
        {
            ServiceLocator.Default.RegisterType<ILoggerService, LoggerService>();


            string filename_rig = "woman_base_deformations.rig";
            string filename_mesh = "t0_001_wa_body__judy.mesh";

            byte[] mbytes = File.ReadAllBytes(filename_mesh);
            MemoryStream mms = new MemoryStream(mbytes);
            CP77.MeshFile.MeshFile.ExportMeshWithoutRig(mms, true);

            byte[] rbytes = File.ReadAllBytes(filename_rig);
            MemoryStream rms = new MemoryStream(rbytes);
            CP77.MeshFile.MeshFile.ExportMeshWithRig(mms,rms, true);
        }
    }
}