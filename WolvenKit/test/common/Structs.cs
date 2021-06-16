using System;
using System.Numerics;
using System.Collections.Generic;
using WolvenKit.Modkit.RED4.Materials.Type;
using Newtonsoft.Json;
using WolvenKit.Modkit.RED4.MaterialSetupFiles;

namespace WolvenKit.Modkit.RED4.GeneralStruct
{
    public class RawArmature
    {
        public string[] Names;

        public Int16[] Parent;
        public int BoneCount;
        public bool Rig;
        public Vector3[] LocalPosn;
        public Quaternion[] LocalRot;
        public Vector3[] LocalScale;
        public Matrix4x4[] WorldMat;
        public Matrix4x4[] IBWorldMat;

        // temp, to be depreciated after fixing IBM mumbo jumbo
        public bool AposeMSExits;
        public Vector3[] AposeMSTrans;
        public Quaternion[] AposeMSRot;
        public Vector3[] AposeMSScale;
        public Matrix4x4[] AposeMSMat;
        public Matrix4x4[] IBAposeMat;
        // temp, to be depreciated after fixing IBM mumbo jumbo
        public bool AposeLSExits;
        public Vector3[] AposeLSTrans;
        public Quaternion[] AposeLSRot;
        public Vector3[] AposeLSScale;
        public Matrix4x4[] AposeLSMat;
    }
    public class MeshesInfo
    {
        public UInt32[] vertCounts { get; set; }
        public UInt32[] indCounts { get; set; }
        public UInt32[] vertOffsets { get; set; }
        public UInt32[] tx0Offsets { get; set; }
        public UInt32[] normalOffsets { get; set; }
        public UInt32[] tangentOffsets { get; set; }
        public UInt32[] colorOffsets { get; set; }
        public UInt32[] tx1Offsets { get; set; }
        public UInt32[] unknownOffsets { get; set; }
        public UInt32[] indicesOffsets { get; set; }
        public UInt32[] vpStrides { get; set; }
        public UInt32[] weightcounts { get; set; }
        public bool[] extraExists { get; set; }
        public Vector4 qTrans { get; set; }
        public Vector4 qScale { get; set; }
        public int meshC { get; set; }
        public UInt32[] LODLvl { get; set; }
        public List<Appearance> appearances { get; set; }
        public UInt32 vertBufferSize { get; set; }
        public UInt32 indexBufferSize { get; set; }
        public UInt32 indexBufferOffset { get; set; }
    }
    public class RawMeshContainer
    {
        public Vector3[] vertices { get; set; }
        public uint[] indices { get; set; }
        public Vector2[] tx0coords { get; set; }
        public Vector2[] tx1coords { get; set; }
        public Vector3[] normals { get; set; }
        public Vector4[] tangents { get; set; }
        public Vector4[] colors { get; set; }
        public float[,] weights { get; set; }
        public bool extraExist { get; set; }
        public UInt16[,] boneindices { get; set; }
        public Vector3[] extradata { get; set; }
        public string name { get; set; }
        public UInt32 weightcount { get; set; }
        public string[] appNames { get; set; }
        public string[] materialNames { get; set; }
    }
    public class Re4MeshContainer
    {
        public Int16[,] ExpVerts { get; set; }
        public UInt32[] Nor32s { get; set; }
        public UInt32[] Tan32s { get; set; }
        public UInt16[] indices { get; set; }
        public UInt16[,] uv0s { get; set; }
        public UInt16[,] uv1s { get; set; }
        public Byte[,] colors { get; set; }
        public Byte[,] weights { get; set; }
        public Byte[,] boneindices { get; set; }
        public string name { get; set; }
        public UInt32 weightcount { get; set; }
        public UInt16[,] extraData { get; set; }
        public bool extraExist;
    }

    public class RawTargetContainer
    {
        public Vector3[] vertexDelta { get; set; }
        public Vector3[] normalDelta { get; set; }
        public Vector3[] tangentDelta { get; set; }
        public UInt16[] vertexMapping { get; set; }
        public UInt32 diffsCount { get; set; }
    }
    public class TargetsInfo
    {
        public UInt32[,] NumVertexDiffsInEachChunk { get; set; }
        public UInt32 NumDiffs { get; set; }
        public UInt32 NumDiffsMapping { get; set; }
        public UInt32[,] NumVertexDiffsMappingInEachChunk { get; set; }
        public UInt32[] TargetStartsInVertexDiffs { get; set; }
        public UInt32[] TargetStartsInVertexDiffsMapping { get; set; }
        public Vector4[] TargetPositionDiffOffset { get; set; }
        public Vector4[] TargetPositionDiffScale { get; set; }
        public string[] Names { get; set; }
        public string[] RegionNames { get; set; }
        public UInt32 NumTargets { get; set; }
        public string BaseMesh { get; set; }
        public string BaseTexture { get; set; }
    }

    public class Appearance
    {
        public string Name;
        public string[] MaterialNames;
    }
    public class RawMaterial
    {
        public string Name { get; set; }
        public string BaseMaterial { get; set; }
        public string MaterialType { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _skin _skin { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _multilayered _multilayered { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _3d_map _3d_map { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _3d_map_cubes _3d_map_cubes { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _3d_map_solid _3d_map_solid { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _beyondblackwall _beyondblackwall { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _beyondblackwall_chars _beyondblackwall_chars { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _beyondblackwall_sky _beyondblackwall_sky { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _beyondblackwall_sky_raymarch _beyondblackwall_sky_raymarch { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _blood_puddle_decal _blood_puddle_decal { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cable _cable { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _circuit_wires _circuit_wires { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cloth_mov _cloth_mov { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cloth_mov_multilayered _cloth_mov_multilayered { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cyberparticles_base _cyberparticles_base { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cyberparticles_blackwall _cyberparticles_blackwall { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cyberparticles_blackwall_touch _cyberparticles_blackwall_touch { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cyberparticles_braindance _cyberparticles_braindance { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cyberparticles_dynamic _cyberparticles_dynamic { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cyberparticles_platform _cyberparticles_platform { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_emissive_color _decal_emissive_color { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_emissive_only _decal_emissive_only { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_forward _decal_forward { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_gradientmap_recolor _decal_gradientmap_recolor { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_gradientmap_recolor_emissive _decal_gradientmap_recolor_emissive { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_normal_roughness _decal_normal_roughness { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_normal_roughness_metalness _decal_normal_roughness_metalness { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_normal_roughness_metalness_2 _decal_normal_roughness_metalness_2 { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_parallax _decal_parallax { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_puddle _decal_puddle { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_roughness _decal_roughness { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_roughness_only _decal_roughness_only { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_terrain_projected _decal_terrain_projected { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_tintable _decal_tintable { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _diode_sign _diode_sign { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _earth_globe _earth_globe { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _earth_globe_atmosphere _earth_globe_atmosphere { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _earth_globe_lights _earth_globe_lights { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _emissive_control _emissive_control { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _eye _eye { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _eye_blendable _eye_blendable { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _eye_gradient _eye_gradient { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _eye_shadow _eye_shadow { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _eye_shadow_blendable _eye_shadow_blendable { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _fake_occluder _fake_occluder { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _fillable_fluid _fillable_fluid { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _fillable_fluid_vertex _fillable_fluid_vertex { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _fluid_mov _fluid_mov { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _frosted_glass _frosted_glass { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _frosted_glass_curtain _frosted_glass_curtain { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _glass _glass { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _glass_blendable _glass_blendable { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _glass_cracked_edge _glass_cracked_edge { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _glass_deferred _glass_deferred { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _glass_scope _glass_scope { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _glass_window_rain _glass_window_rain { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _hair _hair { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _hair_blendable _hair_blendable { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _hair_proxy _hair_proxy { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ice_fluid_mov _ice_fluid_mov { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ice_ver_mov_translucent _ice_ver_mov_translucent { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _lights_interactive _lights_interactive { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _loot_drop_highlight _loot_drop_highlight { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mesh_decal _mesh_decal { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mesh_decal_blendable _mesh_decal_blendable { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mesh_decal_double_diffuse _mesh_decal_double_diffuse { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mesh_decal_emissive _mesh_decal_emissive { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mesh_decal_emissive_subsurface _mesh_decal_emissive_subsurface { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mesh_decal_gradientmap_recolor _mesh_decal_gradientmap_recolor { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mesh_decal_gradientmap_recolor_2 _mesh_decal_gradientmap_recolor_2 { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mesh_decal_gradientmap_recolor_emissive _mesh_decal_gradientmap_recolor_emissive { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mesh_decal_multitinted _mesh_decal_multitinted { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mesh_decal_parallax _mesh_decal_parallax { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mesh_decal_revealed _mesh_decal_revealed { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mesh_decal_wet_character _mesh_decal_wet_character { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_bink _metal_base_bink { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_det _metal_base_det { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_det_dithered _metal_base_det_dithered { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_dithered _metal_base_dithered { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_gradientmap_recolor _metal_base_gradientmap_recolor { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_parallax _metal_base_parallax { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_trafficlight_proxy _metal_base_trafficlight_proxy { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_ui _metal_base_ui { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_vertexcolored _metal_base_vertexcolored { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mikoshi_blocks_big _mikoshi_blocks_big { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mikoshi_blocks_medium _mikoshi_blocks_medium { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mikoshi_blocks_small _mikoshi_blocks_small { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mikoshi_parallax _mikoshi_parallax { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mikoshi_prison_cell _mikoshi_prison_cell { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _multilayered_clear_coat _multilayered_clear_coat { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _multilayered_terrain _multilayered_terrain { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _neon_parallax _neon_parallax { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _presimulated_particles _presimulated_particles { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _proxy_ad _proxy_ad { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _proxy_crowd _proxy_crowd { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _q116_mikoshi_cubes _q116_mikoshi_cubes { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _q116_mikoshi_floor _q116_mikoshi_floor { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _q202_lake_surface _q202_lake_surface { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _rain _rain { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _road_debug_grid _road_debug_grid { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _set_stencil_3 _set_stencil_3 { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _silverhand_overlay _silverhand_overlay { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _silverhand_overlay_blendable _silverhand_overlay_blendable { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _skin_blendable _skin_blendable { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _skybox _skybox { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _speedtree_3d_v8_billboard _speedtree_3d_v8_billboard { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _speedtree_3d_v8_onesided _speedtree_3d_v8_onesided { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _speedtree_3d_v8_onesided_gradient_recolor _speedtree_3d_v8_onesided_gradient_recolor { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _speedtree_3d_v8_seams _speedtree_3d_v8_seams { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _speedtree_3d_v8_twosided _speedtree_3d_v8_twosided { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _spline_deformed_metal_base _spline_deformed_metal_base { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _terrain_simple _terrain_simple { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _top_down_car_proxy_depth _top_down_car_proxy_depth { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _trail_decal _trail_decal { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _trail_decal_normal _trail_decal_normal { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _trail_decal_normal_color _trail_decal_normal_color { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _transparent_liquid _transparent_liquid { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _underwater_blood _underwater_blood { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _vehicle_destr_blendshape _vehicle_destr_blendshape { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _vehicle_glass _vehicle_glass { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _vehicle_glass_proxy _vehicle_glass_proxy { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _vehicle_lights _vehicle_lights { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _vehicle_mesh_decal _vehicle_mesh_decal { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ver_mov _ver_mov { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ver_mov_glass _ver_mov_glass { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ver_mov_multilayered _ver_mov_multilayered { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ver_skinned_mov _ver_skinned_mov { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ver_skinned_mov_parade _ver_skinned_mov_parade { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _window_interior_uv _window_interior_uv { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _window_parallax_interior _window_parallax_interior { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _window_parallax_interior_proxy _window_parallax_interior_proxy { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _window_parallax_interior_proxy_buffer _window_parallax_interior_proxy_buffer { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _window_very_long_distance _window_very_long_distance { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _worldspace_grid _worldspace_grid { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _bink_simple _bink_simple { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cable_strip _cable_strip { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _debugdraw_bias _debugdraw_bias { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _debugdraw_wireframe _debugdraw_wireframe { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _debugdraw_wireframe_bias _debugdraw_wireframe_bias { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _debug_coloring _debug_coloring { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _font _font { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _global_water_patch _global_water_patch { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_animated_uv _metal_base_animated_uv { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_blendable _metal_base_blendable { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_fence _metal_base_fence { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_garment _metal_base_garment { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_packed _metal_base_packed { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_proxy _metal_base_proxy { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _multilayered_debug _multilayered_debug { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _pbr_simple _pbr_simple { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _shadows_debug _shadows_debug { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _transparent_notxaa_2 _transparent_notxaa_2 { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_default_element _ui_default_element { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_default_nine_slice_element _ui_default_nine_slice_element { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_default_tile_element _ui_default_tile_element { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_effect_box_blur _ui_effect_box_blur { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_effect_color_correction _ui_effect_color_correction { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_effect_color_fill _ui_effect_color_fill { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_effect_glitch _ui_effect_glitch { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_effect_inner_glow _ui_effect_inner_glow { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_effect_light_sweep _ui_effect_light_sweep { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_effect_linear_wipe _ui_effect_linear_wipe { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_effect_mask _ui_effect_mask { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_effect_point_cloud _ui_effect_point_cloud { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_effect_radial_wipe _ui_effect_radial_wipe { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_effect_swipe _ui_effect_swipe { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_element_depth_texture _ui_element_depth_texture { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_panel _ui_panel { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _ui_text_element _ui_text_element { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _alphablend_glass _alphablend_glass { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _alpha_control_refraction _alpha_control_refraction { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _animated_decal _animated_decal { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _beam_particles _beam_particles { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _blackbodyradiation _blackbodyradiation { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _blackbody_simple _blackbody_simple { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _blood_transparent _blood_transparent { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _braindance_fog _braindance_fog { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _braindance_particle_thermal _braindance_particle_thermal { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cloak _cloak { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cyberspace_pixelsort_stencil _cyberspace_pixelsort_stencil { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cyberspace_pixelsort_stencil_0 _cyberspace_pixelsort_stencil_0 { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cyberware_animation _cyberware_animation { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _damage_indicator _damage_indicator { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _device_diode _device_diode { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _device_diode_multi_state _device_diode_multi_state { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _diode_pavements _diode_pavements { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _drugged_sobel _drugged_sobel { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _emissive_basic_transparent _emissive_basic_transparent { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _fog_laser _fog_laser { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _hologram _hologram { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _hologram_two_sided _hologram_two_sided { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _holo_projections _holo_projections { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _hud_focus_mode_scanline _hud_focus_mode_scanline { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _hud_markers_notxaa _hud_markers_notxaa { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _hud_markers_transparent _hud_markers_transparent { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _hud_markers_vision _hud_markers_vision { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _hud_ui_dot _hud_ui_dot { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _hud_vision_pass _hud_vision_pass { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _johnny_effect _johnny_effect { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _johnny_glitch _johnny_glitch { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_atlas_animation _metal_base_atlas_animation { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_blackbody _metal_base_blackbody { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_glitter _metal_base_glitter { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _neon_tubes _neon_tubes { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _noctovision_mode _noctovision_mode { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _parallaxscreen _parallaxscreen { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _parallaxscreen_transparent _parallaxscreen_transparent { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _parallaxscreen_transparent_ui _parallaxscreen_transparent_ui { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _parallax_bink _parallax_bink { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _particles_generic_expanded _particles_generic_expanded { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _particles_hologram _particles_hologram { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _pointcloud_source_mesh _pointcloud_source_mesh { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _postprocess _postprocess { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _postprocess_notxaa _postprocess_notxaa { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _radial_blur _radial_blur { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _reflex_buster _reflex_buster { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _refraction _refraction { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _sandevistan_trails _sandevistan_trails { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _screens _screens { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _screen_artifacts _screen_artifacts { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _screen_artifacts_vision _screen_artifacts_vision { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _screen_black _screen_black { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _screen_fast_travel_glitch _screen_fast_travel_glitch { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _screen_glitch _screen_glitch { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _screen_glitch_notxaa _screen_glitch_notxaa { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _screen_glitch_vision _screen_glitch_vision { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _signages _signages { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _signages_transparent_no_txaa _signages_transparent_no_txaa { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _silverhand_proxy _silverhand_proxy { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _simple_additive_ui _simple_additive_ui { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _simple_emissive_decals _simple_emissive_decals { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _simple_fresnel _simple_fresnel { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _simple_refraction _simple_refraction { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _sound_clue _sound_clue { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _television_ad _television_ad { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _triplanar_projection _triplanar_projection { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _zoom _zoom { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _alt_halo _alt_halo { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _blackbodyradiation_distant _blackbodyradiation_distant { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _blackbodyradiation_notxaa _blackbodyradiation_notxaa { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _blood_metal_base _blood_metal_base { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _caustics _caustics { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _character_kerenzikov _character_kerenzikov { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _character_sandevistan _character_sandevistan { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _crystal_dome _crystal_dome { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _crystal_dome_opaque _crystal_dome_opaque { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cyberspace_gradient _cyberspace_gradient { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _cyberspace_teleport_glitch _cyberspace_teleport_glitch { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_caustics _decal_caustics { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_glitch _decal_glitch { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_glitch_emissive _decal_glitch_emissive { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _depth_based_sobel _depth_based_sobel { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _diode_pavements_ui _diode_pavements_ui { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _dirt_animated_masked _dirt_animated_masked { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _e3_prototype_mask _e3_prototype_mask { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _fake_flare _fake_flare { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _fake_flare_simple _fake_flare_simple { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _flat_fog_masked _flat_fog_masked { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _flat_fog_masked_notxaa _flat_fog_masked_notxaa { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _highlight_blocker _highlight_blocker { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _hologram_proxy _hologram_proxy { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _holo_mask _holo_mask { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _invisible _invisible { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _lightning_plasma _lightning_plasma { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _light_gradients _light_gradients { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _low_health _low_health { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mesh_decal__blackbody _mesh_decal__blackbody { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base_scrolling _metal_base_scrolling { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _multilayer_blackbody_inject _multilayer_blackbody_inject { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _nanowire_string _nanowire_string { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _oda_helm _oda_helm { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _rift_noise _rift_noise { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _screen_wave _screen_wave { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _simple_fog _simple_fog { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _simple_refraction_mask _simple_refraction_mask { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _transparent_flowmap _transparent_flowmap { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _transparent_liquid_notxaa _transparent_liquid_notxaa { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _world_to_screen_glitch _world_to_screen_glitch { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _hit_proxy _hit_proxy { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _lod_coloring _lod_coloring { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _overdraw _overdraw { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _overdraw_seethrough _overdraw_seethrough { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _selection _selection { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _uv_density _uv_density { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _wireframe _wireframe { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _editor_mlmask_preview _editor_mlmask_preview { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _editor_mltemplate_preview _editor_mltemplate_preview { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _gi_backface_debug _gi_backface_debug { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _multilayered_baked _multilayered_baked { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mikoshi_fullscr_transition _mikoshi_fullscr_transition { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal _decal { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _decal_normal _decal_normal { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _pbr_layer _pbr_layer { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _debugdraw _debugdraw { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _fallback _fallback { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _metal_base _metal_base { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _mirror _mirror { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _particles_generic _particles_generic { get; set; }
        [JsonProperty(NullValueHandling = NullValueHandling.Ignore)]
        public _particles_liquid _particles_liquid { get; set; }

    }
    public class MatData
    {
        public List<RawMaterial> Materials  { get; set; }
    }

}
