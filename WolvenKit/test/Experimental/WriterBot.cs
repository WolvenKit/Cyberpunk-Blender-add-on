using System;
using System.IO;
using System.Collections.Generic;
using WolvenKit.Common.Services;
using CP77.CR2W;
using WolvenKit.RED4.CR2W;
using WolvenKit.Common.Tools.Oodle;
using WolvenKit.RED4.CR2W.Archive;
using Catel.IoC;
using WolvenKit.Modkit.RED4.RigFile;
using WolvenKit.Modkit.RED4;
using WolvenKit.Modkit.RED4.MeshFile;
using WolvenKit.RED4.CR2W.Types;
using WolvenKit.Modkit.RED4.Opus;
using System.Linq;
using Newtonsoft.Json;

namespace Writer
{
    class Writer
    {
        static void Bot(DirectoryInfo dir)
        {
            
            var serviceLocator = ServiceLocator.Default;
            serviceLocator.RegisterType<ILoggerService, CatelLoggerService>();
            serviceLocator.RegisterType < IProgress<double>, PercentProgressService > ();
            serviceLocator.RegisterType<IHashService, HashService>();
            serviceLocator.RegisterType<Red4ParserService>();
            serviceLocator.RegisterType<TargetTools>();
            serviceLocator.RegisterType<RIG>();
            serviceLocator.RegisterType<MeshTools>();
            serviceLocator.RegisterType<MESHIMPORTER>();
            serviceLocator.RegisterType<ModTools>();
            var oodlePath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "oo2ext_7_win64.dll");
            OodleLoadLib.Load(oodlePath);

            var _wolvenkitFileService = serviceLocator.ResolveType<Red4ParserService>();

            var mts = Directory.GetFiles(dir.FullName, "*.mt", SearchOption.AllDirectories);
            var remts = Directory.GetFiles(dir.FullName, "*.remt", SearchOption.AllDirectories);

            var all = new List<string>();
            all.AddRange(mts);
            all.AddRange(remts);


            var ck = new List<string>();
            var types = new List<string>();
            string file = @"MaterialTypes.cs";
            List<string> notyper = new List<string>();

            List<string> typer = new List<string>();
            List<string> typist = new List<string>();

            notyper.Add("public enum MaterialTypes\n{");
            foreach (string a in all)
            {
                var ms = new MemoryStream(File.ReadAllBytes(a));
                var cr2w = _wolvenkitFileService.TryReadCr2WFile(ms);

                var b = cr2w.Chunks.Select(_ => _.Data).OfType<CMaterialTemplate>().First();
                notyper.Add("   " + b.Name.Value + ",");
                //Console.WriteLine(b.Name.Value);
                typer.Add($"public partial class {b.Name.Value}\n{{");
                typist.Add($"public partial class {b.Name.Value}\n{{");
                typist.Add($"   public {b.Name.Value}(CMaterialInstance cMaterialInstance)\n   {{");
                typist.Add($"       for (int i = 0; i < cMaterialInstance.CMaterialInstanceData.Count; i++)\n       {{");
                typist.Add($"           var data = cMaterialInstance.CMaterialInstanceData[i];");
                //                if (data.REDName == "MultilayerSetup")
                List<string> rem = new List<string>();
                for (int i = 1; i < cr2w.Chunks.Count; i++)
                {
                    var d = cr2w.Chunks[i].Data;
                    
                    if(d.REDType == "CMaterialParameterColor")
                    {   
                        var val = (d as CMaterialParameterColor).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                            var type = (d as CMaterialParameterColor).Color.REDType;
                        //Console.WriteLine(type); CColor
                        typer.Add($"    public Color {val} {{ get; set;}}    //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = new Color(data.Variant as CColor);");
                    }
                    //if (!types.Contains(cr2w.Chunks[i].Data.REDType))
                    //types.Add(cr2w.Chunks[i].Data.REDType);

                    if (d.REDType == "CMaterialParameterScalar")
                    {
                        var val = (d as CMaterialParameterScalar).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        var type = (d as CMaterialParameterScalar).Scalar.REDType;
                        //Console.WriteLine(type); //CFloat
                        typer.Add($"    public float {val} {{ get; set; }}    //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = (data.Variant as CFloat).Value;");
                    }

                    if (d.REDType == "CMaterialParameterTexture")
                    {
                        var val = (d as CMaterialParameterTexture).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        var type = (d as CMaterialParameterTexture).Texture.REDType;
                        //Console.WriteLine(type); rRef<ITexture>
                        typer.Add($"    public string {val} {{ get; set; }}    //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = (data.Variant as rRef<ITexture>).DepotPath;");
                    }

                    if (d.REDType == "CMaterialParameterVector")
                    {
                        var val = (d as CMaterialParameterVector).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        var type = (d as CMaterialParameterVector).Vector.REDType;
                        //Console.WriteLine(type); //Vector4
                        typer.Add($"    public Vec4 {val} {{ get; set; }}    //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = new Vec4(data.Variant as Vector4);");
                    }

                    if (d.REDType == "CMaterialParameterTextureArray")
                    {
                        var val = (d as CMaterialParameterTextureArray).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        var type = (d as CMaterialParameterTextureArray).Texture.REDType;
                        //Console.WriteLine(type); rRef<ITexture>
                        typer.Add($"    public string {val} {{ get; set; }}    //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = (data.Variant as rRef<ITexture>).DepotPath;");
                    }

                    if (d.REDType == "CMaterialParameterMultilayerMask")
                    {
                        var val = (d as CMaterialParameterMultilayerMask).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        var type = (d as CMaterialParameterMultilayerMask).Mask.REDType;
                        //Console.WriteLine(type); rRef<Multilayer_Mask>
                        typer.Add($"    public string {val} {{ get; set; }}     //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = (data.Variant as rRef<Multilayer_Mask>).DepotPath;");
                    }

                    if (d.REDType == "CMaterialParameterMultilayerSetup")
                    {
                        var val = (d as CMaterialParameterMultilayerSetup).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        var type = (d as CMaterialParameterMultilayerSetup).Setup.REDType;
                        //Console.WriteLine(type); //rRef<Multilayer_Setup>
                        typer.Add($"    public string {val} {{ get; set; }}     //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = (data.Variant as rRef<Multilayer_Setup>).DepotPath;");
                    }

                    if (d.REDType == "CMaterialParameterStructBuffer")
                    {
                        var val = (d as CMaterialParameterStructBuffer).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        //var type = (d as CMaterialParameterStructBuffer).REDType;
                        //Console.WriteLine(val);
                        typer.Add($"    public DataBuffer {val} {{ get; set; }}");
                    }

                    if (d.REDType == "CMaterialParameterCube")
                    {
                        var val = (d as CMaterialParameterCube).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        var type = (d as CMaterialParameterCube).Texture.REDType;
                        //Console.WriteLine(type);  rRef<ITexture>
                        typer.Add($"    public string {val} {{ get; set; }}     //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = (data.Variant as rRef<ITexture>).DepotPath;");
                    }

                    if (d.REDType == "CMaterialParameterGradient")
                    {
                        var val = (d as CMaterialParameterGradient).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        var type = (d as CMaterialParameterGradient).Gradient.REDType;
                        //Console.WriteLine(type); rRef<CGradient>
                        typer.Add($"    public string {val} {{ get; set; }}     //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = (data.Variant as rRef<CGradient>).DepotPath;");
                    }

                    if (d.REDType == "CMaterialParameterHairParameters")
                    {
                        var val = (d as CMaterialParameterHairParameters).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        var type = (d as CMaterialParameterHairParameters).HairProfile.REDType;
                        //Console.WriteLine(type); rRef<CHairProfile>
                        typer.Add($"    public string {val} {{ get; set;}}     //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = (data.Variant as rRef<CHairProfile>).DepotPath;");
                    }

                    if (d.REDType == "CMaterialParameterCpuNameU64")
                    {
                        var val = (d as CMaterialParameterCpuNameU64).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        var type = (d as CMaterialParameterCpuNameU64).Name.REDType;
                        //Console.WriteLine(a);  CName
                        //Console.WriteLine(type); 
                        typer.Add($"    public string {val} {{ get; set; }}     //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = (data.Variant as CName).Value;");
                    }

                    if (d.REDType == "CMaterialParameterTerrainSetup")
                    {
                        var val = (d as CMaterialParameterTerrainSetup).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        var type = (d as CMaterialParameterTerrainSetup).Setup.REDType;
                        //Console.WriteLine(type); rRef<CTerrainSetup>
                        typer.Add($"    public string {val} {{ get; set; }}     //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = (data.Variant as rRef<CTerrainSetup>).DepotPath;");
                    }

                    if (d.REDType == "CMaterialParameterSkinParameters")
                    {
                        var val = (d as CMaterialParameterSkinParameters).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        var type = (d as CMaterialParameterSkinParameters).SkinProfile.REDType;
                        //Console.WriteLine(type); rRef<CSkinProfile>
                        typer.Add($"    public string {val} {{ get; set; }}     //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = (data.Variant as rRef<CSkinProfile>).DepotPath;");
                    }

                    if (d.REDType == "CMaterialParameterFoliageParameters")
                    {
                        var val = (d as CMaterialParameterFoliageParameters).ParameterName.Value;
                        if (!rem.Contains(val))
                            rem.Add(val);
                        else
                            continue;
                        var type = (d as CMaterialParameterFoliageParameters).FoliageProfile.REDType;
                        //Console.WriteLine(type); rRef<CFoliageProfile>
                        typer.Add($"    public string {val} {{ get; set; }}     //{type}");
                        typist.Add($"           if (data.REDName == \"{val}\")");
                        typist.Add($"               {val} = (data.Variant as rRef<CFoliageProfile>).DepotPath;");
                    }
                }
                typer.Add($"}}");
                typist.Add($"       }}");
                typist.Add($"   }}");
                typist.Add($"}}");
            }
            notyper.Add("}");

            File.WriteAllLines(file, typer);
            File.WriteAllLines(@"MaterialInit.cs", typist);
            File.WriteAllLines(@"MaterialEnum.cs", notyper);
        }
    }
}
