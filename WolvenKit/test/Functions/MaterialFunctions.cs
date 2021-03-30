using System;
using System.IO;
using CP77.CR2W;
using WolvenKit.RED4.GeneralStructs;
using WolvenKit.RED4.CR2W;
using WolvenKit.RED4.CR2W.Types;
using WolvenKit.Common.Oodle;
using System.Collections.Generic;
using SharpGLTF.Schema2;
using SharpGLTF.Memory;
using SharpGLTF.Scenes;
using SharpGLTF.Materials;
using WolvenKit.RED4.MeshFile;
using SharpGLTF.Geometry.VertexTypes;
using SharpGLTF.Geometry;
using WolvenKit.RED4.MeshFile.Materials.MaterialTypes;

namespace WolvenKit.RED4.MeshFile.Materials
{
    using Vec4 = System.Numerics.Vector4;
    using Vec2 = System.Numerics.Vector2;
    using Vec3 = System.Numerics.Vector3;

    using RIGIDVERTEX = VertexBuilder<VertexPositionNormalTangent, VertexColor1Texture2, VertexEmpty>;
    using RIGIDMESH = MeshBuilder<VertexPositionNormalTangent, VertexColor1Texture2, VertexEmpty>;

    using VPNT = VertexPositionNormalTangent;
    using VCT = VertexColor1Texture2;
    public class MATERIAL
    {
        public static void ExporMeshWithMaterials(Stream meshStream, string dependencyMasterPath, string _meshName, string outfile, bool LodFilter = true, bool isGLBinary = true)
        {
            List<RawMeshContainer> expMeshes = new List<RawMeshContainer>();
            var mesh_cr2w = CP77.CR2W.ModTools.TryReadCr2WFile(meshStream);

            MemoryStream ms = MESH.GetMeshBufferStream(meshStream, mesh_cr2w);
            MeshesInfo meshinfo = MESH.GetMeshesinfo(mesh_cr2w);
            for (int i = 0; i < meshinfo.meshC; i++)
            {
                if (meshinfo.LODLvl[i] != 1 && LodFilter)
                    continue;
                RawMeshContainer mesh = MESH.ContainRawMesh(ms, meshinfo.vertCounts[i], meshinfo.indCounts[i], meshinfo.vertOffsets[i], meshinfo.tx0Offsets[i], meshinfo.normalOffsets[i], meshinfo.colorOffsets[i], meshinfo.unknownOffsets[i], meshinfo.indicesOffsets[i], meshinfo.vpStrides[i], meshinfo.qScale, meshinfo.qTrans, meshinfo.weightcounts[i]);
                mesh.name = _meshName + "_" + i;

                mesh.appNames = new string[meshinfo.appearances.Count];
                mesh.materialNames = new string[meshinfo.appearances.Count];
                for (int e = 0; e < meshinfo.appearances.Count; e++)
                {
                    mesh.appNames[e] = meshinfo.appearances[e].Name;
                    mesh.materialNames[e] = meshinfo.appearances[e].MaterialNames[i];
                }
                expMeshes.Add(mesh);
            }
            ModelRoot model = MESH.RawRigidMeshesToGLTF(expMeshes);

            PackMaterialsAndTexturesToGLTF(meshStream, dependencyMasterPath, ref model);

            if (isGLBinary)
                model.SaveGLB(outfile);
            else
                model.SaveGLTF(outfile);
        }
        static void GetMateriaEntries(Stream meshStream, ref List<string> primaryDependencies,ref List<string> materialEntryNames, ref List<CMaterialInstance> materialEntries)
        {
            var cr2w = ModTools.TryReadCr2WFile(meshStream);

            int index = 0;
            for (int i = 0; i < cr2w.Chunks.Count; i++)
            {
                if (cr2w.Chunks[i].REDType == "CMesh")
                {
                    index = i;
                }
            }

            int count = (cr2w.Chunks[index].data as CMesh).MaterialEntries.Count;
            
            for (int i = 0; i < count; i++)
            {
                materialEntryNames.Add((cr2w.Chunks[index].data as CMesh).MaterialEntries[i].Name.Value);
            }

            bool isbuffered = true;
            if ((cr2w.Chunks[index].data as CMesh).LocalMaterialBuffer.RawDataHeaders.Count == 0)
                isbuffered = false;

            if (isbuffered)
            {
                MemoryStream materialStream = GetMaterialStream(meshStream, cr2w);
                byte[] bytes = materialStream.ToArray();
                for (int i = 0; i < count; i++)
                {
                    UInt32 offset = (cr2w.Chunks[index].data as CMesh).LocalMaterialBuffer.RawDataHeaders[i].Offset.Value;
                    UInt32 size = (cr2w.Chunks[index].data as CMesh).LocalMaterialBuffer.RawDataHeaders[i].Size.Value;

                    MemoryStream ms = new MemoryStream(bytes, (int)offset, (int)size);
                    var mtcr2w = ModTools.TryReadCr2WFile(ms);

                    for (int e = 0; e < mtcr2w.Imports.Count; e++)
                    {
                        bool notFound = true;
                        for (int eye = 0; eye < primaryDependencies.Count; eye++)
                        {
                            if (primaryDependencies[eye] == mtcr2w.Imports[e].DepotPathStr)
                                notFound = false;
                        }
                        if (notFound)
                            primaryDependencies.Add(mtcr2w.Imports[e].DepotPathStr);
                    }

                    materialEntries.Add(mtcr2w.Chunks[0].data as CMaterialInstance);

                }
            }
            else
            {
                for (int i = 0; i < cr2w.Chunks.Count; i++)
                {
                    if (cr2w.Chunks[i].REDType == "CMaterialInstance")
                    {
                        materialEntries.Add(cr2w.Chunks[i].data as CMaterialInstance);
                    }
                }
                for(int i = 0; i < cr2w.Imports.Count; i++)
                {
                    bool notFound = true;
                    for(int e = 0; e < primaryDependencies.Count; e++)
                    {
                        if (primaryDependencies[e] == cr2w.Imports[i].DepotPathStr)
                            notFound = false;
                    }
                    if (notFound)
                        primaryDependencies.Add(cr2w.Imports[i].DepotPathStr);
                }
            }
        }
        static void PackMaterialsAndTexturesToGLTF(Stream meshStream, string dependencyMasterPath,ref ModelRoot model)
        {
            string cacheDir = Path.GetTempPath() + "WolvenKit\\Material\\TempImages\\";

            List<string> primaryDependencies = new List<string>();

            List<string> materialEntryNames = new List<string>();
            List<CMaterialInstance> materialEntries = new List<CMaterialInstance>();

            GetMateriaEntries(meshStream, ref primaryDependencies, ref materialEntryNames, ref materialEntries);

            List<string> mlSetupNames = new List<string>();
            List<Multilayer_Setup> mlSetups = new List<Multilayer_Setup>();

            List<string> mlTemplateNames = new List<string>();
            List<Multilayer_LayerTemplate> mlTemplates = new List<Multilayer_LayerTemplate>();

            Directory.CreateDirectory(cacheDir);
            for (int i = 0; i < primaryDependencies.Count; i++)
            {

                if (Path.GetExtension(primaryDependencies[i]) == ".xbm")
                    if (File.Exists(dependencyMasterPath + primaryDependencies[i]))
                    {
                        File.Copy(dependencyMasterPath + primaryDependencies[i], cacheDir + Path.GetFileName(primaryDependencies[i]),true);
                        CP77.CR2W.ModTools.Export(new FileInfo(cacheDir + Path.GetFileName(primaryDependencies[i])), WolvenKit.Common.DDS.EUncookExtension.png);
                    }
                if (Path.GetExtension(primaryDependencies[i]) == ".mlmask")
                    if (File.Exists(dependencyMasterPath + primaryDependencies[i]))
                    {
                        File.Copy(dependencyMasterPath + primaryDependencies[i], cacheDir + Path.GetFileName(primaryDependencies[i]),true);
                        //CP77.CR2W.ModTools.Export(new FileInfo(cacheDir + Path.GetFileName(primaryDependencies[i])), WolvenKit.Common.DDS.EUncookExtension.png);
                    }

                if (Path.GetExtension(primaryDependencies[i]) == ".mlsetup")
                    if (File.Exists(dependencyMasterPath + primaryDependencies[i]))
                    {
                        var cr2w = CP77.CR2W.ModTools.TryReadCr2WFile(new FileStream((dependencyMasterPath + primaryDependencies[i]), FileMode.Open, FileAccess.Read));
                        mlSetupNames.Add(Path.GetFileNameWithoutExtension(primaryDependencies[i]));
                        mlSetups.Add(cr2w.Chunks[0].data as Multilayer_Setup);

                        for (int e = 0; e < cr2w.Imports.Count; e++)
                        {
                            if (Path.GetExtension(cr2w.Imports[e].DepotPathStr) == ".xbm")
                                if (File.Exists(dependencyMasterPath + cr2w.Imports[e].DepotPathStr))
                                {
                                    File.Copy(dependencyMasterPath + cr2w.Imports[e].DepotPathStr, cacheDir + Path.GetFileName(cr2w.Imports[e].DepotPathStr),true);
                                    CP77.CR2W.ModTools.Export(new FileInfo(cacheDir + Path.GetFileName(cr2w.Imports[e].DepotPathStr)), WolvenKit.Common.DDS.EUncookExtension.png);
                                }
                            if (Path.GetExtension(cr2w.Imports[e].DepotPathStr) == ".mltemplate")
                                if (File.Exists(dependencyMasterPath + cr2w.Imports[e].DepotPathStr))
                                {
                                    var mlTempcr2w = CP77.CR2W.ModTools.TryReadCr2WFile(new FileStream((dependencyMasterPath + cr2w.Imports[e].DepotPathStr), FileMode.Open, FileAccess.Read));


                                    mlTemplateNames.Add(Path.GetFileNameWithoutExtension(cr2w.Imports[e].DepotPathStr));

                                    mlTemplates.Add(mlTempcr2w.Chunks[0].data as Multilayer_LayerTemplate);

                                    for (int eye = 0; eye < mlTempcr2w.Imports.Count; eye++)
                                    {
                                        if (File.Exists(dependencyMasterPath + mlTempcr2w.Imports[eye].DepotPathStr))
                                        {
                                            File.Copy(dependencyMasterPath + mlTempcr2w.Imports[eye].DepotPathStr, cacheDir + Path.GetFileName(mlTempcr2w.Imports[eye].DepotPathStr), true);
                                            CP77.CR2W.ModTools.Export(new FileInfo(cacheDir + Path.GetFileName(mlTempcr2w.Imports[eye].DepotPathStr)), WolvenKit.Common.DDS.EUncookExtension.png);
                                        }
                                    }
                                }
                        }

                    }
            }

            List<RawMaterial> rawMaterials = new List<RawMaterial>();
            for (int i = 0; i < materialEntries.Count; i++)
            {
                rawMaterials.Add(ContainRawMaterial(materialEntries[i], materialEntryNames[i]));
            }

            var obj = new { rawMaterials };
            model.Extras = SharpGLTF.IO.JsonContent.Serialize(obj);

            string[] images = Directory.GetFiles(cacheDir, "*.png");
            for (int i = 0; i < images.Length; i++)
            {
                model.UseImage(new MemoryImage(images[i])).Name = Path.GetFileNameWithoutExtension(images[i]);
            }

            Directory.Delete(cacheDir, true);
        }
        static RawMaterial ContainRawMaterial(CMaterialInstance cMaterialInstance, string name)
        {
            RawMaterial rawMaterial = new RawMaterial();

            rawMaterial.Name = name;
            if (Path.GetExtension(cMaterialInstance.BaseMaterial.DepotPath) == ".mi")
                rawMaterial.extInstanced = true;


            if (Path.GetFileNameWithoutExtension(cMaterialInstance.BaseMaterial.DepotPath) == "mesh_decal")
            {
                rawMaterial.materialType = MaterialType.MeshDecal;

                MeshDecal meshDecal = new MeshDecal();
                for (int i = 0; i < cMaterialInstance.CMaterialInstanceData.Count; i++)
                {
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "DiffuseTexture")
                        meshDecal.diffuseTexture = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);
                    if(cMaterialInstance.CMaterialInstanceData[i].REDName == "DiffuseColor")
                    {
                        float x = (cMaterialInstance.CMaterialInstanceData[i].Variant as CColor).Red.Value / 255f;
                        float y = (cMaterialInstance.CMaterialInstanceData[i].Variant as CColor).Green.Value / 255f;
                        float z = (cMaterialInstance.CMaterialInstanceData[i].Variant as CColor).Blue.Value / 255f;
                        float w = (cMaterialInstance.CMaterialInstanceData[i].Variant as CColor).Alpha.Value / 255f;

                        meshDecal.diffuseColor = new MVector4(x, y, z, w);
                    }
                    Vec2 uvOff = new Vec2();
                    Vec2 uvSca = new Vec2();
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "DiffuseAlpha")
                        meshDecal.diffuseAlpha = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "UVOffsetX")
                        uvOff.X = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "UVOffsetY")
                        uvOff.Y = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "UVRotation")
                        meshDecal.uVRotation = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "UVScaleX")
                        uvSca.X = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "UVScaleY")
                        uvSca.Y = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "SecondaryMask")
                        meshDecal.secondaryMask = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "SecondaryMaskUVScale")
                        meshDecal.secondaryMaskUVScale = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "SecondaryMaskInfluence")
                        meshDecal.secondaryMaskInfluence = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "NormalTexture")
                        meshDecal.normalTexture = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "NormalAlpha")
                        meshDecal.normalAlpha = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "NormalAlphaTex")
                        meshDecal.normalAlphaTex = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "NormalsBlendingMode")
                        meshDecal.normalsBlendingMode = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "RoughnessTexture")
                        meshDecal.roughnessTexture = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "MetalnessTexture")
                        meshDecal.metalnessTexture = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "AlphaMaskContrast")
                        meshDecal.alphaMaskContrast = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "RoughnessMetalnessAlpha")
                        meshDecal.roughnessMetalnessAlpha = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "AnimationSpeed")
                        meshDecal.animationSpeed = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "AnimationFramesWidth")
                        meshDecal.animationFramesWidth = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "AnimationFramesHeight")
                        meshDecal.animationFramesHeight = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "DepthThreshold")
                        meshDecal.depthThreshold = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;

                    meshDecal.uVScale = new MVector2(uvSca.X, uvSca.Y);
                    meshDecal.uVOffset = new MVector2(uvSca.X, uvSca.Y);
                }
                rawMaterial.meshDecal = meshDecal;
            }
            if (Path.GetFileNameWithoutExtension(cMaterialInstance.BaseMaterial.DepotPath) == "multilayered")
            {
                rawMaterial.materialType = MaterialType.MultiLayered;

                MultiLayered multiLayered = new MultiLayered();
                for(int i = 0; i < cMaterialInstance.CMaterialInstanceData.Count; i++)
                {
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "MultilayerSetup")
                        multiLayered.multilayerSetup =  Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<Multilayer_Setup>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "MultilayerMask")
                        multiLayered.multilayerMask = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<Multilayer_Mask>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "GlobalNormal")
                        multiLayered.globalNormal = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);
                }
                rawMaterial.multiLayered = multiLayered;
            }
            if (cMaterialInstance.BaseMaterial.DepotPath.Contains("skin"))
            {
                rawMaterial.materialType = MaterialType.HoomanSkin;

                HoomanSkin hoomanSkin = new HoomanSkin();

                for (int i = 0; i < cMaterialInstance.CMaterialInstanceData.Count; i++)
                {
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "Roughness")
                        hoomanSkin.roughness = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "DetailNormal")
                        hoomanSkin.detailNormal = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "DetailNormalInfluence")
                        hoomanSkin.detailNormalInfluence = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "Normal")
                        hoomanSkin.normal = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "Albedo")
                        hoomanSkin.albedo = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "Detailmap_Squash")
                        hoomanSkin.detailmap_Squash = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "Detailmap_Stretch")
                        hoomanSkin.detailmap_Stretch = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "DetailRoughnessBiasMin")
                        hoomanSkin.detailRoughnessBiasMin = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "DetailRoughnessBiasMax")
                        hoomanSkin.detailRoughnessBiasMax = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "TintColor")
                    {
                        float x = (cMaterialInstance.CMaterialInstanceData[i].Variant as CColor).Red.Value / 255f;
                        float y = (cMaterialInstance.CMaterialInstanceData[i].Variant as CColor).Green.Value / 255f;
                        float z = (cMaterialInstance.CMaterialInstanceData[i].Variant as CColor).Blue.Value / 255f;
                        float w = (cMaterialInstance.CMaterialInstanceData[i].Variant as CColor).Alpha.Value / 255f;

                        hoomanSkin.tintColor =  new MVector4(x, y, z, w);
                    }
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "TintScale")
                        hoomanSkin.tintScale = (cMaterialInstance.CMaterialInstanceData[i].Variant as CFloat).Value;

                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "SkinProfile")
                        hoomanSkin.skinProfile = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<CSkinProfile>).DepotPath);
                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "Bloodflow")
                        hoomanSkin.bloodflow = Path.GetFileNameWithoutExtension((cMaterialInstance.CMaterialInstanceData[i].Variant as rRef<ITexture>).DepotPath);

                    if (cMaterialInstance.CMaterialInstanceData[i].REDName == "BloodColor")
                    {
                        float x = (cMaterialInstance.CMaterialInstanceData[i].Variant as CColor).Red.Value / 255f;
                        float y = (cMaterialInstance.CMaterialInstanceData[i].Variant as CColor).Green.Value / 255f;
                        float z = (cMaterialInstance.CMaterialInstanceData[i].Variant as CColor).Blue.Value / 255f;
                        float w = (cMaterialInstance.CMaterialInstanceData[i].Variant as CColor).Alpha.Value / 255f;

                        hoomanSkin.bloodColor = new MVector4(x, y, z, w);
                    }
                }
                rawMaterial.hoomanSkin = hoomanSkin;
            }

            return rawMaterial;
        }
        static MemoryStream GetMaterialStream(Stream ms,CR2WFile cr2w)
        {
            MemoryStream materialStream = new MemoryStream();

            var buffers = cr2w.Buffers;
            for (var i = 0; i < buffers.Count; i++)
            {
                var b = buffers[i];
                ms.Seek(b.Offset, SeekOrigin.Begin);

                MemoryStream outstream = new MemoryStream();
                // copy to some outstream
                ms.DecompressAndCopySegment(outstream, b.DiskSize, b.MemSize);

                BinaryReader outreader = new BinaryReader(outstream);
                outstream.Position = 161;
                if (new string(outreader.ReadChars(17)) == "CMaterialInstance")
                {
                    materialStream = outstream;
                    break;
                }
            }

            return materialStream;
        }
        public static void testing(Stream meshStream)
        {
            List<string> primaryDependencies = new List<string>();

            List<string> materialEntryNames = new List<string>();
            List<CMaterialInstance> materialEntries = new List<CMaterialInstance>();

            GetMateriaEntries(meshStream, ref primaryDependencies, ref materialEntryNames, ref materialEntries);

            for(int i = 0; i < materialEntries.Count; i++)
            {
                Console.WriteLine(materialEntries[i].BaseMaterial.DepotPath);
            }    
        }
        
        public static void Parse(Stream meshStream, string _meshName, string outfile, bool LodFilter = true, bool isGLBinary = true)
        {
            /*
            var scene = new SceneBuilder();
            var model = scene.ToGltf2();
            string AlbedoTEX = @"E:\stuff\New folder (4)\texs\h0_001_wa_c__judy_d01.png";
            string NormalTEX = @"E:\stuff\New folder (4)\texs\h0_001_wa_c__judy_n01.png";
            MemoryImage diffuseimage = new MemoryImage(AlbedoTEX);
            MemoryImage normalimage = new MemoryImage(NormalTEX);
            model.UseImage(diffuseimage).Name = "h0_001_wa_c__judy_d01";
            model.UseImage(normalimage).Name = "h0_001_wa_c__judy_n01";

            model.SaveGLB(@"E:\stuff\bb.gltf");
            */
            string AlbedoTEX = @"E:\stuff\New folder (4)\texs\h0_001_wa_c__judy_d01.png";
            string NormalTEX = @"E:\stuff\New folder (4)\texs\h0_001_wa_c__judy_n01.png";
            MemoryImage diffuseimage = new MemoryImage(AlbedoTEX);
            MemoryImage normalimage = new MemoryImage(NormalTEX);


            MaterialBuilder mat = new MaterialBuilder("Default").WithMetallicRoughness(0,(float)0.5);
            mat.WithBaseColor(diffuseimage, new Vec4((float)0.792157, (float)0.694118, (float)0.6, 1));
            mat.UseChannel(KnownChannel.BaseColor).UseTexture().WithPrimaryImage(ImageBuilder.From(diffuseimage, "h0_001_wa_c__judy_d01")).WithTransform(new Vec2(0,0), new Vec2(1,1),0,0);
            mat.UseChannel(KnownChannel.Normal).UseTexture().WithPrimaryImage(ImageBuilder.From(normalimage, "h0_001_wa_c__judy_n01")).WithTransform(new Vec2(0, 0), new Vec2(1, 1), 0, 0);
            List<RawMeshContainer> expMeshes = new List<RawMeshContainer>();

            BinaryReader br = new BinaryReader(meshStream);
            var cr2w = CP77.CR2W.ModTools.TryReadCr2WFile(meshStream);

            MemoryStream ms = MESH.GetMeshBufferStream(meshStream, cr2w);
            MeshesInfo meshinfo = MESH.GetMeshesinfo(cr2w);
            for (int i = 0; i < meshinfo.meshC; i++)
            {
                if (meshinfo.LODLvl[i] != 1 && LodFilter)
                    continue;
                RawMeshContainer mesh = MESH.ContainRawMesh(ms, meshinfo.vertCounts[i], meshinfo.indCounts[i], meshinfo.vertOffsets[i], meshinfo.tx0Offsets[i], meshinfo.normalOffsets[i], meshinfo.colorOffsets[i], meshinfo.unknownOffsets[i], meshinfo.indicesOffsets[i], meshinfo.vpStrides[i], meshinfo.qScale, meshinfo.qTrans, meshinfo.weightcounts[i]);
                mesh.name = _meshName + "_" + i;
                expMeshes.Add(mesh);
            }
            ModelRoot model = RigidMeshesWithMaterialsToGLTF(expMeshes, mat);

            if (isGLBinary)
                model.SaveGLB(outfile);
            else
                model.SaveGLTF(outfile);
        }
        static ModelRoot RigidMeshesWithMaterialsToGLTF(List<RawMeshContainer> meshes, MaterialBuilder mat)
        {
            var scene = new SceneBuilder();

            foreach (var mesh in meshes)
            {
                long indCount = mesh.indices.Length;
                var expmesh = new RIGIDMESH(mesh.name);

                var prim = expmesh.UsePrimitive(mat);
                for (int i = 0; i < indCount; i += 3)
                {
                    uint idx0 = mesh.indices[i + 1];
                    uint idx1 = mesh.indices[i];
                    uint idx2 = mesh.indices[i + 2];

                    //VPNT
                    Vec3 p_0 = new Vec3(mesh.vertices[idx0].X, mesh.vertices[idx0].Y, mesh.vertices[idx0].Z);
                    Vec3 n_0 = new Vec3(mesh.normals[idx0].X, mesh.normals[idx0].Y, mesh.normals[idx0].Z);
                    Vec4 t_0 = new Vec4(mesh.tangents[idx0].X, mesh.tangents[idx0].Y, mesh.tangents[idx0].Z, mesh.tangents[idx0].W);

                    Vec3 p_1 = new Vec3(mesh.vertices[idx1].X, mesh.vertices[idx1].Y, mesh.vertices[idx1].Z);
                    Vec3 n_1 = new Vec3(mesh.normals[idx1].X, mesh.normals[idx1].Y, mesh.normals[idx1].Z);
                    Vec4 t_1 = new Vec4(mesh.tangents[idx1].X, mesh.tangents[idx1].Y, mesh.tangents[idx1].Z, mesh.tangents[idx1].W);

                    Vec3 p_2 = new Vec3(mesh.vertices[idx2].X, mesh.vertices[idx2].Y, mesh.vertices[idx2].Z);
                    Vec3 n_2 = new Vec3(mesh.normals[idx2].X, mesh.normals[idx2].Y, mesh.normals[idx2].Z);
                    Vec4 t_2 = new Vec4(mesh.tangents[idx2].X, mesh.tangents[idx2].Y, mesh.tangents[idx2].Z, mesh.tangents[idx2].W);

                    //VCT
                    Vec2 tx0_0 = new Vec2(mesh.tx0coords[idx0].X, mesh.tx0coords[idx0].Y);
                    Vec2 tx1_0 = new Vec2(mesh.tx1coords[idx0].X, mesh.tx1coords[idx0].Y);

                    Vec2 tx0_1 = new Vec2(mesh.tx0coords[idx1].X, mesh.tx0coords[idx1].Y);
                    Vec2 tx1_1 = new Vec2(mesh.tx1coords[idx1].X, mesh.tx1coords[idx1].Y);

                    Vec2 tx0_2 = new Vec2(mesh.tx0coords[idx2].X, mesh.tx0coords[idx2].Y);
                    Vec2 tx1_2 = new Vec2(mesh.tx1coords[idx2].X, mesh.tx1coords[idx2].Y);

                    Vec4 col_0 = new Vec4(mesh.colors[idx0].X, mesh.colors[idx0].Y, mesh.colors[idx0].Z, mesh.colors[idx0].W);
                    Vec4 col_1 = new Vec4(mesh.colors[idx1].X, mesh.colors[idx1].Y, mesh.colors[idx1].Z, mesh.colors[idx1].W);
                    Vec4 col_2 = new Vec4(mesh.colors[idx2].X, mesh.colors[idx2].Y, mesh.colors[idx2].Z, mesh.colors[idx2].W);

                    // vertex build
                    var v0 = new RIGIDVERTEX(new VPNT(p_0, n_0, t_0), new VCT(col_0, tx0_0, tx1_0));
                    var v1 = new RIGIDVERTEX(new VPNT(p_1, n_1, t_1), new VCT(col_1, tx0_1, tx1_1));
                    var v2 = new RIGIDVERTEX(new VPNT(p_2, n_2, t_2), new VCT(col_2, tx0_2, tx1_2));
                    // triangle build
                    prim.AddTriangle(v0, v1, v2);
                }
                scene.AddRigidMesh(expmesh, System.Numerics.Matrix4x4.CreateFromQuaternion(new System.Numerics.Quaternion((float)-0.707107, 0, 0, (float)0.707107))); // to rotate mesh +Z up in blender
            }
            var model = scene.ToGltf2();
            return model;
        }
    }
}
