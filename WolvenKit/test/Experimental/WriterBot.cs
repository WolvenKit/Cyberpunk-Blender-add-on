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
        public static void Bot(DirectoryInfo dir)
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

            List<string> typer = new List<string>();
            foreach (string a in all)
            {
                typer.Add($"case \"{Path.GetFileName(a)}\":");
                typer.Add($"rawMaterial._{Path.GetFileNameWithoutExtension(a)} = new _{Path.GetFileNameWithoutExtension(a)}(cMaterialInstance);");
                typer.Add($"rawMaterial.MaterialType = MaterialTypes._{Path.GetFileNameWithoutExtension(a)}.ToString();");
                typer.Add("break;");
            }
            foreach (string a in all)
            {
                typer.Add($"case MaterialTypes._{Path.GetFileNameWithoutExtension(a)}:");
                typer.Add($"mat._{Path.GetFileNameWithoutExtension(a)}.write(ref mi);");
                typer.Add("if (mat.BaseMaterial == null)");
                typer.Add($"mat.BaseMaterial = @\"{a.Replace(@"D:\unbundle\",string.Empty)}\";");
                typer.Add("break;");
            }

            foreach (string a in all)
            {
                typer.Add("[JsonProperty(NullValueHandling = NullValueHandling.Ignore)]");
                typer.Add($"public _{Path.GetFileNameWithoutExtension(a)} _{Path.GetFileNameWithoutExtension(a)}    {{ get; set; }}");
            }
            File.WriteAllLines(@"swit", typer);
            //
            /*
            var ck = new List<string>();
            var types = new List<string>();
            string file = @"MaterialTypes.cs";



            List<string> enumtyper = new List<string>();
            List<string> typer = new List<string>();
            List<string> inittyper = new List<string>();
            List<string> deinittyper = new List<string>();



            enumtyper.Add("public enum MaterialTypes\n{");
            foreach (string a in all)
            {
                var ms = new MemoryStream(File.ReadAllBytes(a));
                var cr2w = _wolvenkitFileService.TryReadCr2WFile(ms);

                var b = cr2w.Chunks.Select(_ => _.Data).OfType<CMaterialTemplate>().First();
                enumtyper.Add("   " + "_" + b.Name.Value + ",");
                //Console.WriteLine(b.Name.Value);
                typer.Add($"public partial class _{b.Name.Value}\n{{");
                inittyper.Add($"public partial class _{b.Name.Value}\n{{");
                inittyper.Add($"   public _{b.Name.Value}()   {{}}");
                inittyper.Add($"   public _{b.Name.Value}(CMaterialInstance cMaterialInstance)\n   {{");
                inittyper.Add($"       for (int i = 0; i < cMaterialInstance.CMaterialInstanceData.Count; i++)\n       {{");
                inittyper.Add($"           var data = cMaterialInstance.CMaterialInstanceData[i];");

                deinittyper.Add($"public partial class _{b.Name.Value}\n{{");
                deinittyper.Add($"  public void write(ref CR2WFile cr2w)\n    {{");
                deinittyper.Add($"      var m = (cr2w.Chunks[0].Data as CMaterialInstance).CMaterialInstanceData;");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = new Color(data.Variant as CColor);");

                        deinittyper.Add($"      if({val} != null){{");
                        deinittyper.Add($"          var v = new CVariantSizeNameType(cr2w, m, \"{val}\") {{ IsSerialized = true }}; m.Add(v);");
                        deinittyper.Add($"          var p = new CColor(cr2w, v, \"{val}\") {{ IsSerialized = true, Red = new CUInt8() {{ Value = (Byte){val}.Red }}, Green = new CUInt8() {{ Value = (Byte){val}.Green }}, Blue = new CUInt8() {{ Value = (Byte){val}.Blue }}, Alpha = new CUInt8() {{ Value = (Byte){val}.Alpha }} }}; v.Variant = p;}}");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = (data.Variant as CFloat).Value;");

                        deinittyper.Add($"      if({val} != null){{");
                        deinittyper.Add($"          var v = new CVariantSizeNameType(cr2w, m, \"{val}\") {{ IsSerialized = true }}; m.Add(v);");
                        deinittyper.Add($"          var p = new CFloat(cr2w, v, \"{val}\") {{ IsSerialized = true ,Value = (float){val}}}; v.Variant = p;}}");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = (data.Variant as rRef<ITexture>).DepotPath;");

                        deinittyper.Add($"      if({val} != null){{");
                        deinittyper.Add($"          var v = new CVariantSizeNameType(cr2w, m, \"{val}\") {{ IsSerialized = true }}; m.Add(v);");          
                        deinittyper.Add($"          var p = new rRef<ITexture>(cr2w, v, \"{val}\") {{ IsSerialized = true, DepotPath = {val} }}; v.Variant = p; }}");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = new Vec4(data.Variant as Vector4);");


                        deinittyper.Add($"      if({val} != null){{");
                        deinittyper.Add($"          var v = new CVariantSizeNameType(cr2w, m, \"{val}\") {{ IsSerialized = true }}; m.Add(v);");
                        deinittyper.Add($"          var p = new Vector4(cr2w, v, \"{val}\") {{ IsSerialized = true }}; v.Variant = p;");
                        deinittyper.Add($"          p.X = new CFloat(cr2w, p, \"X\") {{ IsSerialized = true, Value = (float){val}.X}}; p.Y = new CFloat(cr2w, p, \"Y\") {{ IsSerialized = true, Value = (float){val}.Y}}; p.Z = new CFloat(cr2w, p, \"Z\") {{ IsSerialized = true, Value = (float){val}.Z}}; p.W = new CFloat(cr2w, p, \"W\") {{ IsSerialized = true, Value = (float){val}.W}};}}");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = (data.Variant as rRef<ITexture>).DepotPath;");

                        deinittyper.Add($"      if({val} != null){{");
                        deinittyper.Add($"          var v = new CVariantSizeNameType(cr2w, m, \"{val}\") {{ IsSerialized = true }}; m.Add(v);");
                        deinittyper.Add($"          var p = new rRef<ITexture>(cr2w, v, \"{val}\") {{ IsSerialized = true, DepotPath = {val} }}; v.Variant = p; }}");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = (data.Variant as rRef<Multilayer_Mask>).DepotPath;");


                        deinittyper.Add($"      if({val} != null){{");
                        deinittyper.Add($"          var v = new CVariantSizeNameType(cr2w, m, \"{val}\") {{ IsSerialized = true }}; m.Add(v);");
                        deinittyper.Add($"          var p = new rRef<Multilayer_Mask>(cr2w, v, \"{val}\") {{ IsSerialized = true, DepotPath = {val} }}; v.Variant = p; }}");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = (data.Variant as rRef<Multilayer_Setup>).DepotPath;");


                        deinittyper.Add($"      if({val} != null){{");
                        deinittyper.Add($"          var v = new CVariantSizeNameType(cr2w, m, \"{val}\") {{ IsSerialized = true }}; m.Add(v);");
                        deinittyper.Add($"          var p = new rRef<Multilayer_Setup>(cr2w, v, \"{val}\") {{ IsSerialized = true, DepotPath = {val} }}; v.Variant = p; }}");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = (data.Variant as rRef<ITexture>).DepotPath;");


                        deinittyper.Add($"      if({val} != null){{");
                        deinittyper.Add($"          var v = new CVariantSizeNameType(cr2w, m, \"{val}\") {{ IsSerialized = true }}; m.Add(v);");
                        deinittyper.Add($"          var p = new rRef<ITexture>(cr2w, v, \"{val}\") {{ IsSerialized = true, DepotPath = {val} }}; v.Variant = p; }}");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = (data.Variant as rRef<CGradient>).DepotPath;");


                        deinittyper.Add($"      if({val} != null){{");
                        deinittyper.Add($"          var v = new CVariantSizeNameType(cr2w, m, \"{val}\") {{ IsSerialized = true }}; m.Add(v);");
                        deinittyper.Add($"          var p = new rRef<CGradient>(cr2w, v, \"{val}\") {{ IsSerialized = true, DepotPath = {val} }}; v.Variant = p; }}");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = (data.Variant as rRef<CHairProfile>).DepotPath;");


                        deinittyper.Add($"      if({val} != null){{");
                        deinittyper.Add($"          var v = new CVariantSizeNameType(cr2w, m, \"{val}\") {{ IsSerialized = true }}; m.Add(v);");
                        deinittyper.Add($"          var p = new rRef<CHairProfile>(cr2w, v, \"{val}\") {{ IsSerialized = true, DepotPath = {val} }}; v.Variant = p; }}");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = (data.Variant as CName).Value;");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = (data.Variant as rRef<CTerrainSetup>).DepotPath;");


                        deinittyper.Add($"      if({val} != null){{");
                        deinittyper.Add($"          var v = new CVariantSizeNameType(cr2w, m, \"{val}\") {{ IsSerialized = true }}; m.Add(v);");
                        deinittyper.Add($"          var p = new rRef<CTerrainSetup>(cr2w, v, \"{val}\") {{ IsSerialized = true, DepotPath = {val} }}; v.Variant = p; }}");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = (data.Variant as rRef<CSkinProfile>).DepotPath;");


                        deinittyper.Add($"      if({val} != null){{");
                        deinittyper.Add($"          var v = new CVariantSizeNameType(cr2w, m, \"{val}\") {{ IsSerialized = true }}; m.Add(v);");
                        deinittyper.Add($"          var p = new rRef<CSkinProfile>(cr2w, v, \"{val}\") {{ IsSerialized = true, DepotPath = {val} }}; v.Variant = p; }}");
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
                        inittyper.Add($"           if (data.REDName == \"{val}\")");
                        inittyper.Add($"               {val} = (data.Variant as rRef<CFoliageProfile>).DepotPath;");


                        deinittyper.Add($"      if({val} != null){{");
                        deinittyper.Add($"          var v = new CVariantSizeNameType(cr2w, m, \"{val}\") {{ IsSerialized = true }}; m.Add(v);");
                        deinittyper.Add($"          var p = new rRef<CFoliageProfile>(cr2w, v, \"{val}\") {{ IsSerialized = true, DepotPath = {val} }}; v.Variant = p; }}");
                    }
                }
                typer.Add($"}}");

                inittyper.Add($"       }}");
                inittyper.Add($"   }}");
                inittyper.Add($"}}");

                //deinittyper.Add($"       }}");
                deinittyper.Add($"   }}");
                deinittyper.Add($"}}");
            }
            enumtyper.Add("}");

            File.WriteAllLines(file, typer);
            File.WriteAllLines(@"MaterialInit.cs", inittyper);
            File.WriteAllLines(@"MaterialEnum.cs", enumtyper);
            File.WriteAllLines(@"MaterialDeinit.cs", deinittyper);
            */
        }
    }
}
