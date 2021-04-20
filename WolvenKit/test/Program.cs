using System;
using System.IO;
using Catel.IoC;
using WolvenKit.Common.Services;
using WolvenKit.RED4.CR2W;
using System.Collections.Generic;
using WolvenKit.RED4.MeshFile;
using WolvenKit.RED4.GeneralStructs;
using SharpGLTF.Schema2;
using WolvenKit.RED4.CR2W.Types;

namespace GLTFNodesTest
{
    using Vec3 = System.Numerics.Vector3;
    using Vec4 = System.Numerics.Vector4;
    class Program
    {
        static void Main(string[] args)
        {
            ServiceLocator.Default.RegisterType<ILoggerService, LoggerService>();
            ServiceLocator.Default.RegisterType<IHashService, HashService>();
            ServiceLocator.Default.RegisterType<IWolvenkitFileService, Cp77FileService>();


            string file = @"C:\Users\Abhinav\Desktop\h0_001_wa_c__judy.mesh";
            string rig = @"C:\Users\Abhinav\Desktop\h0_001_wa_c__judy_skeleton.rig";

            /*
            string file = @"C:\Users\Abhinav\Desktop\t0_001_wa_body__judy.mesh";
            string rig = @"C:\Users\Abhinav\Desktop\woman_base_deformations.rig";
            */

            //string file = @"C:\Users\Abhinav\Desktop\untitled.mesh";
            //string rig = @"C:\Users\Abhinav\Desktop\h0_001_wa_c__judy_skeleton.rig";
            FileStream fs = new FileStream(file, FileMode.Open, FileAccess.Read);
            FileStream rs = new FileStream(rig, FileMode.Open, FileAccess.Read);

            MESHIMPORTER.Import(new FileInfo(@"C:\Users\Abhinav\Desktop\catto.glb"), fs, new FileInfo(@"C:\Users\Abhinav\Desktop\untitled.mesh"));

            //MESH.ExportMeshWithRig(fs,rs, "mesh", new FileInfo(@"C:\Users\Abhinav\Desktop\blop.glb"), false);

        }
    }
}
