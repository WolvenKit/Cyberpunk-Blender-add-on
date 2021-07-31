using System;
using System.IO;
using Catel.IoC;
using WolvenKit.Common.Services;
using WolvenKit.RED4.CR2W;
using CP77.CR2W;
using WolvenKit.Common.Tools.Oodle;
using WolvenKit.Modkit.RED4;
using WolvenKit.Modkit.RED4.RigFile;

namespace TEST
{
    class Program
    {
        static void Main(string[] args)
        {
            var serviceLocator = ServiceLocator.Default;
            serviceLocator.RegisterType<IProgress<double>, PercentProgressService>();
            serviceLocator.RegisterType<IHashService, HashService>();
            serviceLocator.RegisterType<Red4ParserService>();
            serviceLocator.RegisterType<RIG>();
            serviceLocator.RegisterType<MeshTools>();
            serviceLocator.RegisterType<ModTools>();
            var oodlePath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "oo2ext_7_win64.dll");
            OodleLoadLib.Load(oodlePath);
        }
    }
}
