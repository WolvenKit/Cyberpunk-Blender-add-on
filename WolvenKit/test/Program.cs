using System;
using System.IO;
using Catel.IoC;
using WolvenKit.Common.Services;
using WolvenKit.RED4.CR2W;
using System.Collections.Generic;
using WolvenKit.RED4.MeshFile.Materials;
using WolvenKit.RED4.MeshFile;
using WolvenKit.Common.FNV1A;
using WolvenKit.RED4.CR2W.Archive;
using WolvenKit.Common.DDS;
using CP77.CR2W.Uncooker;
using CP77.CR2W;
using WolvenKit.RED4.CR2W.Types;
using WolvenKit.RED4.MaterialSetupFile;
using WolvenKit.RED4.CR2W.Archive;

namespace GLTFNodesTest
{
    class Program
    {
        static void Main(string[] args)
        {
            ServiceLocator.Default.RegisterType<ILoggerService, LoggerService>();
            ServiceLocator.Default.RegisterType<IHashService, HashService>();
            ServiceLocator.Default.RegisterType<IWolvenkitFileService, Cp77FileService>();

            char c = 'c';
            bool exit = false;
            do
            {
                Console.WriteLine("Hit y/Y To Export Mesh With Materials");
                Console.WriteLine("Hit n/N To Export Mesh Only");
                Console.WriteLine("Hit e/E To Exit\n");

                c = Console.ReadKey().KeyChar;
                switch (c)
                {
                    case 'n':
                    case 'N':
                        Console.WriteLine("\nEnter Directory: ");
                        string dir = Console.ReadLine().Replace("\"", string.Empty);
                        Console.WriteLine("\nEnter Output Directory: ");
                        DirectoryInfo outdir = new DirectoryInfo(Console.ReadLine().Replace("\"", string.Empty));
                        string[] files = Directory.GetFiles(dir, "*.mesh", SearchOption.AllDirectories);
                        for (int i = 0; i < files.Length; i++)
                        {
                            Console.WriteLine("Working With: " + files[i]);
                            FileStream fs = new FileStream(files[i], FileMode.Open, FileAccess.Read);
                            string name = Path.GetFileNameWithoutExtension(files[i]);
                            MESH.ExportMeshWithoutRig(fs, name, new FileInfo(outdir.FullName + "\\" + name + ".glb"));
                            Console.WriteLine("Exported: " + outdir.FullName + "\\" + name + ".glb");
                        }
                        break;

                    case 'y':
                    case 'Y':
                        Console.WriteLine("\nEnter Directory Where Meshes Are (any existing sub dirs will be searched for .mesh also): ");
                        string Dir = Console.ReadLine().Replace("\"", string.Empty);
                        bool useAssetLib = false;
                        Console.WriteLine("\nHit y/Y to use unbundled(dir in which base folder is located) to Parse Materials");
                        char s = Console.ReadKey().KeyChar;
                        if (s == 'Y' || s == 'y')
                            useAssetLib = true;

                        bool copytex = false;
                        if (useAssetLib)
                        {
                            Console.WriteLine("\nHit y/Y To Copy Textures to OutPut Dir");
                            char w = Console.ReadKey().KeyChar;
                            if (w == 'Y' || w == 'y')
                                copytex = true;
                            Console.WriteLine("\nEnter unbundled(dir in which base folder is located)");
                        }
                        else
                        {
                            Console.WriteLine("\nEnter Dir Where Cyberpunk2077.exe is located i.e. bin\\x64\\, Archives files are supposed to be there in ..Dir\\archive\\pc\\content\\");
                        }
                        DirectoryInfo depotDir = new DirectoryInfo(Console.ReadLine().Replace("\"", string.Empty));

                        Console.WriteLine("\nEnter Output Directory:");
                        DirectoryInfo Outdir = new DirectoryInfo(Console.ReadLine().Replace("\"", string.Empty));

                        string[] Files = Directory.GetFiles(Dir, "*.mesh", SearchOption.AllDirectories);
                        if(useAssetLib)
                        {
                            MATERIAL mat = new MATERIAL();

                            for (int i = 0; i < Files.Length; i++)
                            {
                                Console.WriteLine("Working With: " + Files[i]);
                                FileStream fs = new FileStream(Files[i], FileMode.Open, FileAccess.Read);
                                string Name = Path.GetFileNameWithoutExtension(Files[i]);

                                mat.ExporMeshWithMaterialsUsingAssetLib(fs, depotDir, Name, new FileInfo(Outdir.FullName + "\\" + Name + ".glb"), true,copytex, EUncookExtension.png);
                                Console.WriteLine("Exported: " + Outdir.FullName + "\\" + Name + ".glb");
                            }
                        }
                        else
                        {
                            string[] archiveList = Directory.GetFiles(depotDir.FullName.Replace("bin\\x64", "archive\\pc\\content"), "*.archive", SearchOption.AllDirectories);
                            var Archives = new List<Archive>();
                            for (int i = 0; i < archiveList.Length; i++)
                                Archives.Add(new Archive(archiveList[i]));
                            MATERIAL mat = new MATERIAL(Archives);

                            for (int i = 0; i < Files.Length; i++)
                            {
                                Console.WriteLine("Working With: " + Files[i]);
                                FileStream fs = new FileStream(Files[i], FileMode.Open, FileAccess.Read);
                                string Name = Path.GetFileNameWithoutExtension(Files[i]);

                                mat.ExportMeshWithMaterialsUsingArchives(fs, Name, new FileInfo(Outdir.FullName + "\\" + Name + ".glb"), true, EUncookExtension.png);
                                Console.WriteLine("Exported: " + Outdir.FullName + "\\" + Name + ".glb");
                            }

                        }
                        break;
                    case 'e':
                    case 'E':
                        exit = true;
                        break;
                    default:
                        Console.WriteLine("Wrong Option");
                        break;
                }

            }
            while (!exit);
            /*
            FileStream fs = new FileStream(@"C:\Users\Asus\Desktop\ml_t1_001_wa_tank__judy_masksset.mlmask", FileMode.Open, FileAccess.Read);

            //MESH.ExportMeshWithoutRig(fs, "h1_007_pma_specs__aviators", @"C:\Users\Asus\Desktop\h1_007_pwa_specs__aviators.glb");

            var cr2w = CP77.CR2W.ModTools.TryReadCr2WFile(fs);
            cr2w.FileName = @"C:\Users\Asus\Desktop\ml_t1_001_wa_tank__judy_masksset.mlmask";
            Mlmask.Uncook(fs, cr2w, EUncookExtension.dds);
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
            MESH.ExportMultiMeshWithRig(meshStreams, rigStreams, names, @"C:\Users\Asus\Desktop\skinned.gltf",true,false);
            */

            //FileStream fs = new FileStream(@"E:\stuff\New folder (4)\h0_001_wa_c__judy.mesh", FileMode.Open, FileAccess.Read);
            //FileStream rs = new FileStream(@"E:\stuff\New folder (4)\h0_001_wa_c__judy_skeleton.rig", FileMode.Open, FileAccess.Read);
            //MESH.ExportMeshWithRig(fs,rs, "h0_001_wa_c__judy", @"C:\Users\Asus\Desktop\skinned.glb",true,true);

            //  MATERIAL.ParseMaterials(fs, "h0_001_wa_c__judy", @"E:\stuff\rigid.glb",true,false);
            //MATERIAL.ExporMeshWithMaterials(fs,@"Y:\", "h0_001_wa_c__judy", @"C:\Users\Asus\Desktop\New folder\HeadMatTest.gltf", true,false);

            /*
            List<string> meshes = new List<string>(Directory.GetFiles(@"C:\Users\Asus\Desktop\New folder (2)", "*.mesh"));
            for(int i = 0; i < meshes.Count; i++)
            {
                FileStream fs = new FileStream(meshes[i], FileMode.Open, FileAccess.Read);
                MATERIAL.testing(fs);
            }
            */
            //MESHIMPORTER.Import(@"C:\Users\Asus\Desktop\skinned.gltf", fs);

            /*
            string gameDir = @"Z:\bin\x64\";
            FileStream fs = new FileStream(@"C:\Users\Asus\Desktop\h0_001_wa_c__judy.mesh", FileMode.Open, FileAccess.Read);
            MATERIAL.ExporMeshWithMaterials(fs, new DirectoryInfo(gameDir), "mesh", new FileInfo(@"C:\Users\Asus\Desktop\New folder (2)\rigid.glb"),true,false,true,EUncookExtension.png);
            */
            //Console.WriteLine(new FileInfo(@"C:\Users\Asus\Desktop\New folder (2)\h0_001_wa_c__judy.mesh").Name);
            /*
            gameDir = gameDir.Replace("bin\\x64", "archive\\pc\\content");
            string[] archiveNames = Directory.GetFiles(gameDir, "*.archive");

            foreach (string archiveName in archiveNames)
                Console.WriteLine(archiveName);

            List<Archive> archives = new List<Archive>();
            for (int i = 0; i < archiveNames.Length; i++)
                archives.Add(new Archive(archiveNames[i]));

            for (int i = 0; i < archives.Count; i++)
                CP77.CR2W.ModTools.ExtractSingle(archives[i], FNV1A64HashAlgorithm.HashString("base\\characters\\main_npc\\judy\\h0_001_wa_c__judy\\textures\\h0_001_wa_c__judy_n01.xbm"), new DirectoryInfo(gameDir));

            */
            /*
            FileStream fs = new FileStream(@"C:\Users\Asus\Desktop\plastic_tech_hq_01_30.mltemplate", FileMode.Open, FileAccess.Read);

            var cr2w = ModTools.TryReadCr2WFile(fs);
            var temp = (cr2w.Chunks[0].data as Multilayer_LayerTemplate);
            Template temp1 = new Template(temp, "plastic_tech_hq_01_30.mltemplate");
            */
            //File.WriteAllText(@"C:\Users\Asus\Desktop\blabla.json", Newtonsoft.Json.JsonConvert.SerializeObject(temp1, Newtonsoft.Json.Formatting.Indented));
            //File.WriteAllText(@"C:\Users\Asus\Desktop\blabla.json", SharpGLTF.IO.JsonContent.Serialize(temp1, new System.Text.Json.JsonSerializerOptions(System.Text.Json.JsonSerializerDefaults.General)).ToJson());
            /*
            List<string> xbms = new List<string>(Directory.GetFiles(@"Y:\base\characters\main_npc\", "*.mesh",SearchOption.AllDirectories));
            for (int i = 0; i < xbms.Count; i++)
            {
                if (File.Exists(xbms[i]))
                {
                    var fs = new FileStream(xbms[i], FileMode.Open, FileAccess.Read);
                    MATERIAL.ExporMeshWithMaterials(fs, new DirectoryInfo(@"Y:\"), Path.GetFileNameWithoutExtension(xbms[i]), new FileInfo(@"C:\Users\Asus\Desktop\New folder (2)\" + Path.GetFileNameWithoutExtension(xbms[i] + ".glb")), true, true);
                    fs.Dispose();
                    fs.Close();
                }
            }
            */
        }
    }
}