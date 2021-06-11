using System;
using System.IO;
using System.Linq;
using WolvenKit.Modkit.RED4.Opus;
using Newtonsoft.Json;
using System.Collections.Generic;
using System.Diagnostics;

namespace OpusToolZ
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("Enter the path of sfx_container.opusinfo, (all the .opuspak files sould be present in the same directory as sfx_container.opusinfo)\n");
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
            while(BitConverter.ToString(br.ReadBytes(3)) != "53-4E-44")
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

            List<UInt16> tempolisto = new List<UInt16>();
            for (int i = 0; i < info.OpusCount; i++)
            {
                if(!tempolisto.Contains(info.PackIndices[i]))
                {
                    tempolisto.Add(info.PackIndices[i]);
                }
            }

            UInt32 numOfPaks = Convert.ToUInt32(tempolisto.Count);

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
                Console.WriteLine("2. Hit (s/S) to extract a single .opus and .wav using 32bit Hash input\n");
                Console.WriteLine("3. Hit (a/A) to extract all the .opus files to a directory\n");
                Console.WriteLine("4. Hit (i/I) to get .opus hash info\n");
                Console.WriteLine("5. Hit (p/P) to select a folder containing .wav file(s) and packthem to .opuspaks and rebuild .opusinfo\n");
                Console.WriteLine("6. Hit (e/E) to exit\n");
                Console.ResetColor();

                y = Console.ReadKey().KeyChar;
                switch(y)
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
                        if(files.Length != numOfPaks)
                        {
                            Console.ForegroundColor = ConsoleColor.Red;
                            Console.WriteLine("All " + Convert.ToString(numOfPaks) + " .opuspak files are not present in the directory of sfx_container.opusinfo\n");
                            Console.WriteLine("Make sure all of them are there and restart the tool\n");
                            Console.ResetColor();
                        }
                        else
                        {
                            Console.WriteLine("Enter 32Bit uint Hash of the .opus file:\n");
                            UInt32 hash = 0;
                            bool thrown = false;
                            try
                            {
                                hash = Convert.ToUInt32(Console.ReadLine());
                                if (!info.OpusHashes.Contains(hash))
                                {
                                    Console.ForegroundColor = ConsoleColor.Red;
                                    Console.WriteLine("Opus file hash not present in opusinfo , try again\n");
                                    Console.ResetColor();
                                }
                            }
                            catch { Console.ForegroundColor = ConsoleColor.Red; Console.WriteLine("Invalid Hash, try again\n"); thrown = true; Console.ResetColor(); }
                            if(!thrown)
                            {
                                Console.ForegroundColor = ConsoleColor.Green;
                                string aaa = AppDomain.CurrentDomain.BaseDirectory + Convert.ToString(hash) + ".opus";
                                info.WriteOpusFromPaks(streams, new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory), hash);
                                string tempdiro = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "opusdec.exe");

                                var proc = new ProcessStartInfo(tempdiro)
                                {
                                    WorkingDirectory = AppDomain.CurrentDomain.BaseDirectory,
                                    Arguments = $" \"{aaa}\" \"{aaa.Replace("opus", "wav")}\"",
                                    UseShellExecute = false,
                                    RedirectStandardOutput = true,
                                    CreateNoWindow = true,
                                };
                                using (var p = Process.Start(proc))
                                {
                                    p.WaitForExit();
                                }

                                Console.WriteLine("output: " + aaa);
                                Console.ResetColor();
                            }
                        }
                        break;
                    case 'a':
                    case 'A':
                        if (files.Length != numOfPaks)
                        {
                            Console.ForegroundColor = ConsoleColor.Red;
                            Console.WriteLine("All " + Convert.ToString(numOfPaks) + " .opuspak files are not present in the directory of sfx_container.opusinfo\n");
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
                                    if(hash == info.OpusHashes[i])
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
                    case 'p':
                    case 'P':
                        bool writeinfo = false;
                        if (files.Length != numOfPaks)
                        {
                            Console.ForegroundColor = ConsoleColor.Red;
                            Console.WriteLine("All " + Convert.ToString(numOfPaks) + ".opuspak files are not present in the directory of sfx_container.opusinfo\n");
                            Console.WriteLine("Make sure all of them are there and restart the tool\n");
                            Console.ResetColor();
                        }
                        else
                        {
                            Console.WriteLine("Enter Directory Containing .wav file(s)\n");
                            string directory = Console.ReadLine().Replace("\"", string.Empty);
                            if (!Directory.Exists(directory))
                            {
                                Console.ForegroundColor = ConsoleColor.Red;
                                Console.WriteLine("Invalid Directory! try again it\n");
                                Console.ResetColor();
                            }
                            else
                            {
                                var ffiiles = Directory.GetFiles(directory, "*.wav");
                                if (ffiiles.Length == 0)
                                {
                                    Console.ForegroundColor = ConsoleColor.Red;
                                    Console.WriteLine("Directory contains no .wav files\n");
                                    Console.ResetColor();
                                }
                                List<UInt32> foundids = new List<UInt32>();
                                foreach (string wav in ffiiles)
                                {
                                    try
                                    {
                                        UInt32 idddd = Convert.ToUInt32(Path.GetFileNameWithoutExtension(wav));
                                        foundids.Add(idddd);
                                    }
                                    catch
                                    {
                                        Console.ForegroundColor = ConsoleColor.Red;
                                        Console.WriteLine("Invalid .wav filename: " + Path.GetFileName(wav) + " Name should be a Unsigned integer number \n");
                                        Console.ResetColor();
                                    }
                                }
                                List<UInt32> validids = new List<UInt32>();
                                for (int i = 0; i < foundids.Count; i++)
                                {
                                    bool found = false;
                                    for (int e = 0; e < info.OpusCount; e++)
                                    {
                                        if (info.OpusHashes[e] == foundids[i])
                                        {
                                            found = true;
                                            validids.Add(foundids[i]);
                                            break;
                                        }
                                    }
                                    if (!found)
                                    {
                                        Console.ForegroundColor = ConsoleColor.Red;
                                        Console.WriteLine(foundids[i] + ".wav is not originally present in .opusinfo\n");
                                        Console.ResetColor();
                                    }
                                }
                                Stream[] modStreams = new Stream[files.Length];
                                for (int i = 0; i < files.Length; i++)
                                {
                                    modStreams[i] = new FileStream(files[i], FileMode.Open, FileAccess.Read);
                                }
                                List<int> pakstowrite = new List<int>();
                                Console.ForegroundColor = ConsoleColor.Yellow;
                                for (int i = 0; i < validids.Count; i++)
                                {
                                    string name = Path.Combine(directory, Convert.ToString(validids[i]) + ".opus");
                                    var proc = new ProcessStartInfo(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "opusenc.exe"))
                                    {
                                        WorkingDirectory = AppDomain.CurrentDomain.BaseDirectory,
                                        Arguments = $" \"{name.Replace("opus", "wav")}\" \"{name}\" --serial 42 --quiet --padding 0 --vbr --comp 10 --framesize 20 ",
                                        UseShellExecute = false,
                                        RedirectStandardOutput = true,
                                        CreateNoWindow = true,
                                    };
                                    using (var p = Process.Start(proc))
                                    {
                                        p.WaitForExit();
                                    }
                                    if (File.Exists(name))
                                    {
                                        Console.WriteLine("Processing:" + Path.GetFileName(name) + "\n");
                                        for (int e = 0; e < info.OpusCount; e++)
                                        {
                                            if (validids[i] == info.OpusHashes[e])
                                            {
                                                int pakIdx = info.PackIndices[e];

                                                info.WriteOpusToPak(new MemoryStream(File.ReadAllBytes(name)), ref modStreams[pakIdx], validids[i], Convert.ToUInt32(new FileInfo(name.Replace("opus", "wav")).Length));

                                                if (!pakstowrite.Contains(pakIdx))
                                                {
                                                    pakstowrite.Add(pakIdx);
                                                }
                                            }
                                        }
                                    }
                                }
                                Console.ForegroundColor = ConsoleColor.Green;
                                for (int i = 0; i < pakstowrite.Count; i++)
                                {
                                    var temp = modStreams[pakstowrite[i]];
                                    byte[] bytes = new byte[temp.Length];
                                    temp.Position = 0;
                                    temp.Read(bytes, 0, Convert.ToInt32(temp.Length));
                                    string outTemp = Path.Combine(directory, "sfx_container_" + Convert.ToString(pakstowrite[i] + ".opuspak"));
                                    File.WriteAllBytes(outTemp, bytes);
                                    Console.WriteLine("Output: " + outTemp);
                                    writeinfo = true;
                                }
                                if (writeinfo)
                                {
                                    info.WriteOpusInfo(new DirectoryInfo(directory));
                                    Console.WriteLine("Output: " + Path.Combine(new DirectoryInfo(directory).FullName, "sfx_container.opusinfo"));
                                }
                                Console.ResetColor();

                                for (int i = 0; i < modStreams.Length; i++)
                                {
                                    modStreams[i].Dispose();
                                    modStreams[i].Close();
                                }
                            }
                        }
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
