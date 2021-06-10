using System;
using System.IO;
using System.Linq;
using WolvenKit.Modkit.RED4.Opus;
using Newtonsoft.Json;

namespace OpusToolZ
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("Enter the path of sfx_container.opusinfo, (all the 1444 .opuspak files sould be present in the same directory as sfx_container.opusinfo)\n");
            string f = Console.ReadLine();
            f = f.Replace("\"", string.Empty);
            while (!File.Exists(f))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("Invalid FilePath, Enter Again\n");
                Console.ResetColor();
                f = Console.ReadLine();
                f = f.Replace("\"", string.Empty);
            }
            FileStream fs = new FileStream(f, FileMode.Open, FileAccess.Read);
            BinaryReader br = new BinaryReader(fs);
            fs.Position = 0;
            while (BitConverter.ToString(br.ReadBytes(3)) != "53-4E-44")
            {
                fs.Dispose();
                fs.Close();
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("Not a opusinfo file, Enter Again\n");
                Console.ResetColor();
                f = Console.ReadLine();
                f = f.Replace("\"", string.Empty);
                while (!File.Exists(f))
                {
                    Console.ForegroundColor = ConsoleColor.Red;
                    Console.WriteLine("Invalid FilePath, Enter Again\n");
                    Console.ResetColor();
                    f = Console.ReadLine();
                    f = f.Replace("\"", string.Empty);
                }
                fs = new FileStream(f, FileMode.Open, FileAccess.Read);
                br = new BinaryReader(fs);
                fs.Position = 0;
            }
            var info = new OpusInfo(fs);
            string[] files = Directory.GetFiles(Path.GetDirectoryName(f), "*.opuspak").OrderBy(_ => Convert.ToUInt32(_.Replace(".opuspak", string.Empty).Substring(_.LastIndexOf('_') + 1))).ToArray();
            Stream[] streams = new Stream[files.Length];
            for (int i = 0; i < files.Length; i++)
            {
                streams[i] = new FileStream(files[i], FileMode.Open, FileAccess.Read);
            }
            string s = JsonConvert.SerializeObject(info,Formatting.Indented);

            char y;
            do
            {
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("\n#########OPTIONS########\n");
                Console.WriteLine("1. Hit (d/D) to dump all the opusinfo information to a .json file\n");
                Console.WriteLine("2. Hit (s/S) to extract a single .opus using 32bit Hash input\n");
                Console.WriteLine("3. Hit (a/A) to extract all the .opus files to a directory\n");
                Console.WriteLine("4. Hit (i/I) to get .opus hash info\n");
                Console.WriteLine("5. Hit (e/E) to exit\n");
                Console.ResetColor();

                y = Console.ReadKey().KeyChar;
                switch (y)
                {
                    case 'd':
                    case 'D':
                        string oo = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "sfx_container.opusinfo.json");
                        File.WriteAllText(oo, s);
                        Console.ForegroundColor = ConsoleColor.Green;
                        Console.WriteLine("ouput: " + oo);
                        Console.ResetColor();
                        break;
                    case 's':
                    case 'S':
                        if (files.Length != 1444)
                        {
                            Console.ForegroundColor = ConsoleColor.Red;
                            Console.WriteLine("All 1444 .opuspak files are not present in the directory of sfx_container.opusinfo\n");
                            Console.WriteLine("Make sure all of them are there and restart the tool\n");
                            Console.ResetColor();
                        }
                        else
                        {
                            Console.WriteLine("Enter 32Bit uint Hash of the .opus file:\n");
                            try
                            {
                                UInt32 hash = Convert.ToUInt32(Console.ReadLine());
                                if (!info.OpusHashes.Contains(hash))
                                {
                                    Console.ForegroundColor = ConsoleColor.Red;
                                    Console.WriteLine("Opus file hash not present in opusinfo , try again\n");
                                    Console.ResetColor();
                                }
                                else
                                {
                                    Console.ForegroundColor = ConsoleColor.Green;
                                    string aaa = AppDomain.CurrentDomain.BaseDirectory + Convert.ToString(hash) + ".opus";
                                    info.WriteOpusFromPaks(streams, new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory), hash);
                                    Console.WriteLine("output: " + aaa);
                                    Console.ResetColor();
                                }
                            }
                            catch { Console.WriteLine("Invalid Hash, try again\n"); }
                        }
                        break;
                    case 'a':
                    case 'A':
                        if (files.Length != 1444)
                        {
                            Console.ForegroundColor = ConsoleColor.Red;
                            Console.WriteLine("All 1444 .opuspak files are not present in the directory of sfx_container.opusinfo\n");
                            Console.WriteLine("Make sure all of them are there and restart the tool\n");
                            Console.ResetColor();
                        }
                        else
                        {
                            Console.WriteLine("Enter OutPut Directory:\n ");
                            string dir = Console.ReadLine();
                            dir = dir.Replace("\"", string.Empty);
                            if (!Directory.Exists(dir))
                            {
                                Console.ForegroundColor = ConsoleColor.Red;
                                Console.WriteLine("Invalid Directory! create it");
                                Console.ResetColor();
                            }
                            else
                            {
                                Console.ForegroundColor = ConsoleColor.Green;
                                info.WriteAllOpusFromPaks(streams, new DirectoryInfo(dir));
                                Console.WriteLine("output: " + dir);
                                Console.ResetColor();
                            }
                        }
                        break;
                    case 'e':
                    case 'E':
                        break;
                    case 'i':
                    case 'I':
                        Console.WriteLine("Enter 32Bit uint Hash of the .opus file:\n");
                        try
                        {
                            UInt32 hash = Convert.ToUInt32(Console.ReadLine());
                            if (!info.OpusHashes.Contains(hash))
                            {
                                Console.ForegroundColor = ConsoleColor.Red;
                                Console.WriteLine("Opus file hash not present in opusinfo , try again\n");
                                Console.ResetColor();
                            }
                            else
                            {
                                Console.ForegroundColor = ConsoleColor.Green;
                                for (int i = 0; i < info.OpusCount; i++)
                                {
                                    if (hash == info.OpusHashes[i])
                                    {
                                        Console.WriteLine("hash: " + info.OpusHashes[i]);
                                        Console.WriteLine("present in sfx_container_" + info.PackIndices[i] + ".opuspak");
                                        Console.WriteLine("offset: " + info.OpusOffsets[i]);
                                        Console.WriteLine("riffoffset: " + info.RiffOpusOffsets[i]);
                                        Console.WriteLine("opus file size: " + info.OpusStreamLengths[i]);
                                        Console.WriteLine("wav file size: " + info.WavStreamLengths[i]);
                                    }
                                }
                                Console.ResetColor();
                            }
                        }
                        catch { Console.WriteLine("Invalid Hash, try again\n"); }
                        break;
                    default:
                        Console.ForegroundColor = ConsoleColor.Red;
                        Console.WriteLine("Invalid Selection!\n");
                        Console.ResetColor();
                        break;
                }
            }
            while (y != 'e' && y != 'E');
        }
    }
}
