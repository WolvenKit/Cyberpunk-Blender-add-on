using System;
using System.IO;
using Catel.IoC;
using WolvenKit.Common.Services;
using WolvenKit.RED4.CR2W;
using System.Collections.Generic;
using WolvenKit.RED4.MeshFile.Materials;

namespace GLTFNodesTest
{
    class Program
    {
        static void Main(string[] args)
        {
            ServiceLocator.Default.RegisterType<ILoggerService, LoggerService>();
            ServiceLocator.Default.RegisterType<IHashService, HashService>();
            ServiceLocator.Default.RegisterType<IWolvenkitFileService, Cp77FileService>();

            /*
            string filename_rig = @"C:\Users\Abhinav\Desktop\New folder (5)\man_base_deformations.rig";
            string filename_mesh = @"C:\Users\Abhinav\Desktop\New folder (5)\t2_050_ma_jacket__scavenger_dangle.mesh";
            
            byte[] bytes = File.ReadAllBytes(filename_mesh);
            MemoryStream ms = new MemoryStream(bytes);

            byte[] bytes1 = File.ReadAllBytes(filename_rig);
            MemoryStream ms1 = new MemoryStream(bytes1);
            CP77.MeshFile.MESH.ExportMeshWithRig(ms,ms1, "h0_001_wa_c__judy", true, @"C:\Users\Abhinav\Desktop\h0_001_mb_c__jackie_welles.glb");
            */
            /*
            CP77.MeshFile.Materials.Material.GetMateriaEntries(ms);
            
            
            byte[] bytes = File.ReadAllBytes(@"C:\Users\Abhinav\Desktop\morphing\h0_000_pwa__morphs.morphtarget");
            MemoryStream ms = new MemoryStream(bytes);
            TARGET.ExportTargets(ms,"morphing.glb");
            */
            /*
            byte[] rbytes = File.ReadAllBytes(filename_rig);
            MemoryStream rms = new MemoryStream(rbytes);
            CP77.MeshFile.MeshFile.ExportMeshWithRig(ms, rms, "h0_001_wa_c__judy", true, @"C:\Users\Abhinav\Desktop\3dskinned.glb");
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

            /*
            List<Stream> meshStreams = new List<Stream>();
            List<Stream> rigStreams = new List<Stream>();
            List<string> meshes = new List<string>(Directory.GetFiles(@"E:\stuff\New folder (4)", "*.mesh"));
            List<string> rigs = new List<string>(Directory.GetFiles(@"E:\stuff\New folder (4)", "*.rig"));
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
            WolvenKit.RED4.MeshFile.MESH.ExportMultiMeshWithRig(meshStreams, rigStreams, names, E:\stuff\3dskinned.glb);
            */
            FileStream fs = new FileStream(@"E:\stuff\New folder (4)\h0_001_wa_c__judy.mesh", FileMode.Open, FileAccess.Read);
            MATERIAL.ParseMaterials(fs, "h0_001_wa_c__judy", @"E:\stuff\rigid.glb",true,false);
            MATERIAL.ParseMaterialInstance();
        }
    }
}