using System;
using System.IO;
using Catel.IoC;
using WolvenKit.Common.Services;
using CP77.RigFile;
using System.Collections.Generic;
using GeneralStructs;
using SharpGLTF.Scenes;
using System.Linq;

namespace GLTFNodesTest
{
    class Program
    {
        static void Main(string[] args)
        {
            ServiceLocator.Default.RegisterType<ILoggerService, LoggerService>();

            /*
            string filename_rig = @"C:\Users\Abhinav\Desktop\New folder (2)\rigs\h0_001_wa_c__judy_skeleton.rig";
            string filename_mesh = @"C:\Users\Abhinav\Desktop\New folder (4)\l1_001_wa_pants__judy.mesh";
            
            byte[] mbytes = File.ReadAllBytes(filename_mesh);
            MemoryStream mms = new MemoryStream(mbytes);
            CP77.MeshFile.MeshFile.ExportMeshWithoutRig(mms, "l1_001_wa_pants__judy", true);
            
            
            byte[] rbytes = File.ReadAllBytes(filename_rig);
            MemoryStream rms = new MemoryStream(rbytes);
            CP77.MeshFile.MeshFile.ExportMeshWithRig(mms,rms, "h0_001_wa_c__judy", true);
            */
            /*
            string filename_rig2 = @"C:\Users\Abhinav\Desktop\New folder (2)\rigs\h0_001_wa_c__judy_skeleton.rig";

            byte[] bytes1 = File.ReadAllBytes(filename_rig2);
            MemoryStream r1ms = new MemoryStream(bytes1);
            RawArmature rig1 = RigFile.ProcessRig(r1ms);

            byte[] bytes2 = File.ReadAllBytes(filename_rig1);
            MemoryStream r2ms = new MemoryStream(bytes2);
            RawArmature rig2 = RigFile.ProcessRig(r2ms);

            List<RawArmature> rigs = new List<RawArmature>();

            rigs.Add(rig1);
            rigs.Add(rig2);

            RawArmature CombinedRig =  RigFile.CombineRigs(rigs);

            var bonesmapping = RigFile.ExportNodes(CombinedRig);

            var rootbone = bonesmapping.Values.Where(n => n.Parent == null).FirstOrDefault();

            var scene = new SceneBuilder();
            scene.AddNode(rootbone);
            var model = scene.ToGltf2();

            model.SaveGLTF("combined.gltf");
            */
            
            List<MemoryStream> meshStreams = new List<MemoryStream>();
            List<MemoryStream> rigStreams = new List<MemoryStream>();
            List<string> meshes = new List<string>(Directory.GetFiles(@"C:\Users\Abhinav\Desktop\New folder (6)", "*.mesh"));
            List<string> rigs = new List<string>(Directory.GetFiles(@"C:\Users\Abhinav\Desktop\New folder (6)", "*.rig"));
            List<string> names = new List<string>();

            for(int i = 0; i < meshes.Count; i++)
            {
                byte[] bytes = File.ReadAllBytes(meshes[i]);
                MemoryStream ms = new MemoryStream(bytes);
                meshStreams.Add(ms);
                names.Add(Path.GetFileNameWithoutExtension(meshes[i]));
            }
            for (int i = 0; i < rigs.Count; i++)
            {
                byte[] bytes = File.ReadAllBytes(rigs[i]);
                MemoryStream ms = new MemoryStream(bytes);
                rigStreams.Add(ms);
            }
            CP77.MeshFile.MeshFile.ExportMultiMeshWithRig(meshStreams, rigStreams, names, true, @"C:\Users\Abhinav\Desktop\3dskinned.gltf");

        }
    }
}