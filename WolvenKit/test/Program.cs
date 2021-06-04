using System;
using System.Linq;
using System.IO;
using Catel.IoC;
using WolvenKit.Common.Services;
using WolvenKit.RED4.CR2W;
using CP77.CR2W;
using WolvenKit.Modkit.RED4.Materials;
using WolvenKit.Common.Tools.Oodle;
using WolvenKit.Modkit.RED4.Opus;
using System.Collections.Generic;
using WolvenKit.Common.FNV1A;

namespace CyberpunkToolz
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
            DirectoryInfo paksdir = new DirectoryInfo(@"D:\unbundle\base\sound\soundbanks");
            DirectoryInfo outdir = new DirectoryInfo(@"D:\New folder");
            FileInfo file = new FileInfo(@"D:\unbundle\base\sound\soundbanks\sfx_container.opusinfo");
            OpusTools.Parse(file, paksdir, outdir);
        }
        static void hash()
        {
            /*
string g = @"C:\Users\Abhinav\Desktop\missinghashes.txt";
string[] miss = File.ReadAllLines(g);
UInt64[] missed = new UInt64[miss.Length];
for(int i = 0; i < miss.Length; i++)
{
    missed[i] = Convert.ToUInt64(miss[i]);
}
*/
            string f = @"C:\Users\Abhinav\Desktop\cp_list.txt";
            string[] lines = File.ReadAllLines(f);
            List<string> files = new List<string>();
            for (int i = 20; i < lines.Length; i++)
            {
                lines[i] = lines[i].Substring(53, lines[i].Length - 53);
                files.Add(lines[i].Replace('/', '\\'));
                /*
                if(lines[i].Contains("/base/"))
                {
                    lines[i] = lines[i].Substring(lines[i].IndexOf("/base/") + 1, lines[i].Length - lines[i].IndexOf("/base/") - 1);
                    files.Add(lines[i].Replace('/','\\'));
                }
                */
                //Console.WriteLine(lines[i]);
            }
            /*
            var dirs = Directory.GetDirectories(@"D:\unbundle", "", SearchOption.AllDirectories);
            for (int i = 0; i < dirs.Length; i++)
            {
                dirs[i] = dirs[i].Replace("D:\\unbundle\\",string.Empty);
                bool found = false;
                foreach (string file in files)
                {
                    if(file.Contains(dirs[i]))
                    {
                        found = true;
                        break;
                    }
                }
                if(!found)
                {
                    Console.WriteLine(dirs[i]);
                }
            }
            */
            /*
            string z = @"C:\Users\Abhinav\Desktop\archivehashes.txt";
            var ss = File.ReadAllLines(z).ToList();
            List<string> found = new List<string>();
            foreach (string file in files)
            {
                for (int i = 0; i < missed.Length; i++)
                {
                    if (FNV1A64HashAlgorithm.HashString(file) == missed[i])
                    {
                        found.Add(file);
                    }
                }

            }
            File.WriteAllLines(@"C:\Users\Abhinav\Desktop\ahsha.txt", found);
            */
        }
    }
}
