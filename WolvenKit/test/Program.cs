using System;
using System.IO;
using Catel.IoC;
using WolvenKit.Common.Services;
using WolvenKit.RED4.CR2W;
using CP77.CR2W;
using WolvenKit.Modkit.RED4.Materials;
using WolvenKit.Common.Tools.Oodle;
namespace GLTFNodesTest
{
    class Program
    {
        static void Main(string[] args)
        {
            var oodlePath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "oo2ext_7_win64.dll");
            OodleLoadLib.Load(oodlePath);

            ServiceLocator.Default.RegisterInstance(typeof(IProgress<double>), new MockProgressService());
            ServiceLocator.Default.RegisterType<ILoggerService, CatelLoggerService>();
            ServiceLocator.Default.RegisterType<IHashService, HashService>();
            ServiceLocator.Default.RegisterType<IWolvenkitFileService, Cp77FileService>();
            ServiceLocator.Default.RegisterType<ModTools>();

            string g = @"C:\Program Files (x86)\Steam\steamapps\common\Cyberpunk 2077\archive\pc\content";
            string f = @"C:\Users\Abhinav\Desktop\t1_001_wa_tank__judy.mesh";
            MATERIAL m = new MATERIAL(new DirectoryInfo(g));

            m.ExportMeshWithMaterialsUsingArchives(new FileStream(f, FileMode.Open, FileAccess.Read), Path.GetFileNameWithoutExtension(f), new FileInfo(f), false, WolvenKit.Common.DDS.EUncookExtension.tga);
            //m.ExportMeshWithMaterialsUsingAssetLib(new FileStream(f, FileMode.Open, FileAccess.Read),new DirectoryInfo(@"D:\Material Repo"), Path.GetFileNameWithoutExtension(f), new FileInfo(f));
        }
    }
}
