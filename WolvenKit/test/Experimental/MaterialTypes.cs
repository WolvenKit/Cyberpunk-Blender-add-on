using WolvenKit.RED4.CR2W.Types;

namespace WolvenKit.Modkit.RED4.Materials.Types
{
    public partial class _3d_map
    {
        public Color Color { get; set; }    //Color
        public float Opacity { get; set; }    //Float
        public float Lighting { get; set; }    //Float
        public float ParticleSize { get; set; }    //Float
        public float WorldScale { get; set; }    //Float
        public string WorldColorTex { get; set; }    //rRef:ITexture
        public string WorldPosTex { get; set; }    //rRef:ITexture
        public string WorldNormalTex { get; set; }    //rRef:ITexture
        public string WorldDepthTex { get; set; }    //rRef:ITexture
        public float AdditiveAlphaBlend { get; set; }    //Float
    }
    public partial class _3d_map_cubes
    {
        public float PointCloudTextureHeight { get; set; }    //Float
        public Vec4 TransMin { get; set; }    //Vector4
        public Vec4 TransMax { get; set; }    //Vector4
        public string WorldPosTex { get; set; }    //rRef:ITexture
        public float CubeSize { get; set; }    //Float
        public float ColorGradient { get; set; }    //Float
        public Vec4 DebugScaleOffset { get; set; }    //Vector4
        public float DissolveDistance { get; set; }    //Float
        public float DissolveBandWidth { get; set; }    //Float
        public float DissolveCellSize { get; set; }    //Float
        public Color DissolveBurnColor { get; set; }    //Color
        public float DissolveBurnStrength { get; set; }    //Float
        public float DissolveBurnMinCameraSpeed { get; set; }    //Float
        public Vec4 MapEdgeDissolveCenter { get; set; }    //Vector4
        public float MapEdgeDissolveRadiusStart { get; set; }    //Float
        public float MapEdgeDissolveRadiusBand { get; set; }    //Float
        public float MapEdgeDissolveCellSize { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public Color EdgeColor { get; set; }    //Color
        public float EdgeThickness { get; set; }    //Float
        public float EdgeSharpnessPower { get; set; }    //Float
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Translucency { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _3d_map_solid
    {
        public float RenderOnTop { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color Color { get; set; }    //Color
    }
    public partial class _beyondblackwall
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string DiffuseMap { get; set; }    //rRef:ITexture
        public string HeightMap { get; set; }    //rRef:ITexture
        public float Height { get; set; }    //Float
        public float Intensity { get; set; }    //Float
        public float AnimBlend { get; set; }    //Float
        public float SmallDistortionStrenght { get; set; }    //Float
        public float BigDistortionStrenght { get; set; }    //Float
        public float SmallDistortionTime { get; set; }    //Float
        public float BigDistortionTime { get; set; }    //Float
        public float VignetteIntensity { get; set; }    //Float
        public float LuminancePower { get; set; }    //Float
        public float CompareValue { get; set; }    //Float
        public float PixelStretchBlend { get; set; }    //Float
    }
    public partial class _beyondblackwall_chars
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color Color { get; set; }    //Color
        public float TextureColorBlend { get; set; }    //Float
        public float Metalness { get; set; }    //Float
        public float Roughness { get; set; }    //Float
        public float AtlasSize { get; set; }    //Float
        public float AtlasID { get; set; }    //Float
        public float SmallDistortionStrenght { get; set; }    //Float
        public float BigDistortionStrenght { get; set; }    //Float
        public float SmallDistortionTime { get; set; }    //Float
        public float BigDistortionTime { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _beyondblackwall_sky
    {
        public string SkyDiffuse { get; set; }    //rRef:ITexture
        public string SkySorted { get; set; }    //rRef:ITexture
        public string SkySortMask { get; set; }    //rRef:ITexture
        public string NoiseMap { get; set; }    //rRef:ITexture
        public string SilhouetteDiffuse { get; set; }    //rRef:ITexture
        public string SilhouetteMask { get; set; }    //rRef:ITexture
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float LightDirectionHorizontal { get; set; }    //Float
        public float LightDirectionVertical { get; set; }    //Float
        public float Wrap { get; set; }    //Float
        public float WrapIntensity { get; set; }    //Float
        public Vec4 FlashIntensity { get; set; }    //Vector4
        public Vec4 FlashTimeScale { get; set; }    //Vector4
        public Color LightColor { get; set; }    //Color
        public float SkyAmbient { get; set; }    //Float
        public Vec4 SkyParameter { get; set; }    //Vector4
        public Vec4 SilhouetteUV { get; set; }    //Vector4
        public float CompareValue { get; set; }    //Float
    }
    public partial class _beyondblackwall_sky_raymarch
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string NoiseTexture3D { get; set; }    //rRef:ITexture
        public string VolumeNoise { get; set; }    //rRef:ITexture
        public string ScreenNoise { get; set; }    //rRef:ITexture
        public Color LightColor { get; set; }    //Color
        public float LightIntensity { get; set; }    //Float
        public float LightVectorXY { get; set; }    //Float
        public float LightVectorZ { get; set; }    //Float
        public Color SkyColor { get; set; }    //Color
        public float VectorNoiseSize { get; set; }    //Float
        public float VectorNoiseIntensity { get; set; }    //Float
        public Color AmbientLightTop { get; set; }    //Color
        public Color AmbientLightBottom { get; set; }    //Color
        public float CoverageShift { get; set; }    //Float
        public float JitterIntensity { get; set; }    //Float
        public float EmisssivIntensity { get; set; }    //Float
        public float CloudScaleXY { get; set; }    //Float
        public float CloudScaleZ { get; set; }    //Float
        public float CloudPositionZ { get; set; }    //Float
        public Vec4 NoiseOffset { get; set; }    //Vector4
        public Vec4 FlashAreaOffset { get; set; }    //Vector4
        public float SphereOffsetZ { get; set; }    //Float
        public float SphereSize { get; set; }    //Float
        public Vec4 SphereOffsetVec { get; set; }    //Vector4
        public float NoiseSize { get; set; }    //Float
        public float CloudDensity { get; set; }    //Float
        public float DetailNoiseSize { get; set; }    //Float
        public Vec4 DetailNoiseOffset { get; set; }    //Vector4
        public Vec4 ScreenNoiseVec { get; set; }    //Vector4
        public Vec4 Samples { get; set; }    //Vector4
        public Vec4 SkyBlend { get; set; }    //Vector4
        public Vec4 Scatter { get; set; }    //Vector4
        public Vec4 SilverLightCone { get; set; }    //Vector4
    }
    public partial class _blood_puddle_decal
    {
        public string NoiseTexture { get; set; }    //rRef:ITexture
        public Color Color { get; set; }    //Color
        public float Roughness { get; set; }    //Float
        public float Squash { get; set; }    //Float
        public float Curls { get; set; }    //Float
        public float Details { get; set; }    //Float
        public float Thickness { get; set; }    //Float
        public float ProgressiveOpacity { get; set; }    //Float
    }
    public partial class _cable
    {
        public float VehicleDamageInfluence { get; set; }    //Float
        public float ThicknessStart { get; set; }    //Float
        public float ThicknessEnd { get; set; }    //Float
        public float RangeStart { get; set; }    //Float
        public float RangeEnd { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveLift { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _circuit_wires
    {
        public float PointCloudTextureRes { get; set; }    //Float
        public float TransMin { get; set; }    //Float
        public float TransMax { get; set; }    //Float
        public string WorldPosTex { get; set; }    //rRef:ITexture
        public float WireThickness { get; set; }    //Float
        public Vec4 InstanceOffset { get; set; }    //Vector4
        public Vec4 LocalNormal { get; set; }    //Vector4
        public float BevelStrenght { get; set; }    //Float
        public float DebugVC { get; set; }    //Float
        public float DebugID { get; set; }    //Float
        public Color BaseColor { get; set; }    //Color
        public float Metalness { get; set; }    //Float
        public float Roughness { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Translucency { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _cloth_mov
    {
        public string vertex_paint_tex { get; set; }    //rRef:ITexture
        public float trans_min { get; set; }    //Float
        public float trans_max { get; set; }    //Float
        public float n_frames { get; set; }    //Float
        public float n_pieces { get; set; }    //Float
        public float play_time { get; set; }    //Float
        public float frame_rate { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _cloth_mov_multilayered
    {
        public string vertex_paint_tex { get; set; }    //rRef:ITexture
        public float trans_min { get; set; }    //Float
        public float trans_max { get; set; }    //Float
        public float n_frames { get; set; }    //Float
        public float n_pieces { get; set; }    //Float
        public float play_time { get; set; }    //Float
        public float frame_rate { get; set; }    //Float
        public string GlobalNormal { get; set; }    //rRef:ITexture
        public string MultilayerMask { get; set; }     //rRef:Multilayer_Mask
        public string MultilayerSetup { get; set; }     //rRef:Multilayer_Setup
        public string MaskAtlas { get; set; }    //rRef:ITexture
        public DataBuffer MaskTiles { get; set; }
        public DataBuffer Layers { get; set; }
        public float LayersStartIndex { get; set; }    //Float
        public float SurfaceTexAspectRatio { get; set; }    //Float
        public Vec4 MaskToTileScale { get; set; }    //Vector4
        public float MaskTileSize { get; set; }    //Float
        public Vec4 MaskAtlasDims { get; set; }    //Vector4
        public Vec4 MaskBaseResolution { get; set; }    //Vector4
        public float SetupLayerMask { get; set; }    //Float
    }
    public partial class _cyberparticles_base
    {
        public Vec4 trans_extent { get; set; }    //Vector4
        public float Contrast { get; set; }    //Float
        public float AddSizeX { get; set; }    //Float
        public float AddSizeY { get; set; }    //Float
        public float Width { get; set; }    //Float
        public float Height { get; set; }    //Float
        public string WorldColorTex { get; set; }    //rRef:ITexture
        public string WorldPosTex { get; set; }    //rRef:ITexture
        public float WorldSize { get; set; }    //Float
        public float ParticleSize { get; set; }    //Float
        public float DissolveTime { get; set; }    //Float
        public float DissolveGlobalTime { get; set; }    //Float
        public float DissolveDeltaScale { get; set; }    //Float
        public float DissolveNoiseScale { get; set; }    //Float
        public float DissolveParticleSize { get; set; }    //Float
        public float WarpTime { get; set; }    //Float
        public Vec4 WarpLocation { get; set; }    //Vector4
        public float StretchMul { get; set; }    //Float
        public float StretchMax { get; set; }    //Float
        public float UnRevealTime { get; set; }    //Float
        public float Displace01 { get; set; }    //Float
        public float Displace02 { get; set; }    //Float
        public float GlobalNoiseScale { get; set; }    //Float
        public string VectorField { get; set; }    //rRef:ITexture
        public float VectorFieldSliceCount { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float Opacity { get; set; }    //Float
        public Color Tint { get; set; }    //Color
        public string Mask { get; set; }    //rRef:ITexture
    }
    public partial class _cyberparticles_blackwall
    {
        public string VideoRT { get; set; }    //rRef:ITexture
        public string GradientTex { get; set; }    //rRef:ITexture
        public string DisturbTex { get; set; }    //rRef:ITexture
        public float Opacity { get; set; }    //Float
        public float UsesInstancing { get; set; }    //Float
        public float DisturbRadius { get; set; }    //Float
        public float DisturbCurveFrequency { get; set; }    //Float
        public float DisturbMul { get; set; }    //Float
        public float DisturbTime { get; set; }    //Float
        public float DisturbNoiseScale { get; set; }    //Float
        public float DisturbScale { get; set; }    //Float
        public float DisturbBrighten { get; set; }    //Float
        public Vec4 DisturbLocation1 { get; set; }    //Vector4
        public Vec4 DisturbLocation2 { get; set; }    //Vector4
        public float TimeFactor { get; set; }    //Float
        public Vec4 Scale { get; set; }    //Vector4
        public Vec4 Dimensions { get; set; }    //Vector4
        public Vec4 TexTiling { get; set; }    //Vector4
        public float Contrast { get; set; }    //Float
        public float AddSizeX { get; set; }    //Float
        public float AddSizeY { get; set; }    //Float
        public float ParticleSize { get; set; }    //Float
        public float WarpTime { get; set; }    //Float
        public Vec4 WarpLocation { get; set; }    //Vector4
        public float StretchMul { get; set; }    //Float
        public float StretchMax { get; set; }    //Float
        public float CNoiseAdjust { get; set; }    //Float
        public float Align { get; set; }    //Float
        public Vec4 HighFreqFade { get; set; }    //Vector4
        public string VectorField { get; set; }    //rRef:ITexture
        public float VectorFieldSliceCount { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color Tint { get; set; }    //Color
    }
    public partial class _cyberparticles_blackwall_touch
    {
        public float Opacity { get; set; }    //Float
        public float RippleSize { get; set; }    //Float
        public float RippleSpeed { get; set; }    //Float
        public float RippleNumber { get; set; }    //Float
        public float RippleHeight { get; set; }    //Float
        public Vec4 RipplePosition { get; set; }    //Vector4
        public Vec4 RippleDirection { get; set; }    //Vector4
        public float TimeFactor { get; set; }    //Float
        public Vec4 Scale { get; set; }    //Vector4
        public Vec4 Dimensions { get; set; }    //Vector4
        public Vec4 TexTiling { get; set; }    //Vector4
        public float Contrast { get; set; }    //Float
        public float AddSizeX { get; set; }    //Float
        public float AddSizeY { get; set; }    //Float
        public float ParticleSize { get; set; }    //Float
        public float WarpTime { get; set; }    //Float
        public Vec4 WarpLocation { get; set; }    //Vector4
        public float StretchMul { get; set; }    //Float
        public float StretchMax { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color Tint { get; set; }    //Color
        public Color TintPulse { get; set; }    //Color
    }
    public partial class _cyberparticles_braindance
    {
        public float DebugAlwaysShow { get; set; }    //Float
        public float DebugDisplayUV { get; set; }    //Float
        public float NumQuadsX { get; set; }    //Float
        public float Opacity { get; set; }    //Float
        public float ParticleSize { get; set; }    //Float
        public string WorldPosTex { get; set; }    //rRef:ITexture
        public string RevealMask { get; set; }    //rRef:ITexture
        public float RevealMaskFramesY { get; set; }    //Float
        public Vec4 RevealMaskBoundsMin { get; set; }    //Vector4
        public Vec4 RevealMaskBoundsMax { get; set; }    //Vector4
        public string FlowMap0 { get; set; }    //rRef:ITexture
        public string CluesMap { get; set; }    //rRef:ITexture
        public float CharacterBlobRadius { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string MaskParticle { get; set; }    //rRef:ITexture
    }
    public partial class _cyberparticles_dynamic
    {
        public float Opacity { get; set; }    //Float
        public float ParticleSize { get; set; }    //Float
        public float JitterStrength { get; set; }    //Float
        public string WorldPosTex { get; set; }    //rRef:ITexture
        public string NormalTex { get; set; }    //rRef:ITexture
        public float NumQuadsX { get; set; }    //Float
        public string VectorField { get; set; }    //rRef:ITexture
        public float VectorFieldSliceCount { get; set; }    //Float
        public Vec4 VectorFieldTiling { get; set; }    //Vector4
        public Vec4 VectorFieldAnimSpeed { get; set; }    //Vector4
        public Vec4 VectorFieldDisplacementStrength { get; set; }    //Vector4
        public float Scale { get; set; }    //Float
        public float UsePivotAsOffset { get; set; }    //Float
        public Vec4 OriginalPivotWorldPosition { get; set; }    //Vector4
        public Color ColorMain { get; set; }    //Color
        public float Brightness { get; set; }    //Float
        public float BrightnessTop { get; set; }    //Float
        public float HACK_Q110_IsElder { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
    }
    public partial class _cyberparticles_platform
    {
        public string BlueNoise { get; set; }    //rRef:ITexture
        public string DataTex { get; set; }    //rRef:ITexture
        public string BlackTex { get; set; }    //rRef:ITexture
        public float UnRevealTime { get; set; }    //Float
        public float RevealDirection { get; set; }    //Float
        public float ColorMul { get; set; }    //Float
        public float MovementScale { get; set; }    //Float
        public float DistanceFade { get; set; }    //Float
        public float FloorScale { get; set; }    //Float
        public Vec4 BlockSize { get; set; }    //Vector4
        public float CityTilingX { get; set; }    //Float
        public float CityTilingY { get; set; }    //Float
        public float SideTilingX { get; set; }    //Float
        public float SideTilingY { get; set; }    //Float
        public float AddSizeX { get; set; }    //Float
        public float AddSizeY { get; set; }    //Float
        public float Width { get; set; }    //Float
        public float Height { get; set; }    //Float
        public float Depth { get; set; }    //Float
        public Vec4 NoiseScale { get; set; }    //Vector4
        public Vec4 NoiseSize { get; set; }    //Vector4
        public float TranslateTime { get; set; }    //Float
        public Vec4 TranslateDestination { get; set; }    //Vector4
        public float StretchMul { get; set; }    //Float
        public float StretchMax { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float Opacity { get; set; }    //Float
        public Color Tint { get; set; }    //Color
    }
    public partial class _decal_emissive_color
    {
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float AlphaMaskContrast { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveAlphaThreshold { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _decal_emissive_only
    {
        public string EmissiveMask { get; set; }    //rRef:ITexture
        public float EmissiveEV { get; set; }    //Float
        public float AlphaMaskContrast { get; set; }    //Float
        public float EmissiveAlphaThreshold { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _decal_forward
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public string Metalness { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float Alpha { get; set; }    //Float
    }
    public partial class _decal_gradientmap_recolor
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public string MaskTexture { get; set; }    //rRef:ITexture
        public float DiffuseTextureAsMaskTexture { get; set; }    //Float
        public string GradientMap { get; set; }    //rRef:ITexture
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _decal_gradientmap_recolor_emissive
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public string MaskTexture { get; set; }    //rRef:ITexture
        public float DiffuseTextureAsMaskTexture { get; set; }    //Float
        public string GradientMap { get; set; }    //rRef:ITexture
        public string EmissiveGradientMap { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float AlphaMaskContrast { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _decal_normal_roughness
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public float DiffuseTextureAsMaskTexture { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _decal_normal_roughness_metalness
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public float DiffuseTextureAsMaskTexture { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _decal_normal_roughness_metalness_2
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public float DiffuseTextureAsMaskTexture { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public Vec4 AtlasSize { get; set; }    //Vector4
        public Vec4 SubRegion { get; set; }    //Vector4
    }
    public partial class _decal_parallax
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public float DiffuseTextureAsMaskTexture { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public Vec4 AtlasSize { get; set; }    //Vector4
        public Vec4 SubRegion { get; set; }    //Vector4
        public string HeightTexture { get; set; }    //rRef:ITexture
        public float HeightStrength { get; set; }    //Float
    }
    public partial class _decal_puddle
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public string NormalTexture { get; set; }    //rRef:ITexture
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float AlphaMaskContrast { get; set; }    //Float
        public float DiffuseTextureAsMaskTexture { get; set; }    //Float
        public float DiffuseAlpha { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _decal_roughness
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public float DiffuseTextureAsMaskTexture { get; set; }    //Float
        public Color DiffuseColor { get; set; }    //Color
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _decal_roughness_only
    {
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _decal_terrain_projected
    {
        public string AlphaMask { get; set; }    //rRef:ITexture
        public float AlphaMaskBlackPoint { get; set; }    //Float
        public float AlphaMaskWhitePoint { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Roughness { get; set; }    //rRef:ITexture
        public string SpecularIntensity { get; set; }    //rRef:ITexture
        public Vec4 RoughnessLevels { get; set; }    //Vector4
        public Vec4 SpecularIntensityLevels { get; set; }    //Vector4
        public Vec4 ColorMaskLevels { get; set; }    //Vector4
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public string Microblend { get; set; }    //rRef:ITexture
        public float MicroblendContrast { get; set; }    //Float
        public float MaterialTiling { get; set; }    //Float
        public float LayerTiling { get; set; }    //Float
        public float MicroblendTiling { get; set; }    //Float
    }
    public partial class _decal_tintable
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public float DiffuseTextureAsMaskTexture { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public string TintMaskTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public Color MaskColorR { get; set; }    //Color
        public Color MaskColorG { get; set; }    //Color
        public Color MaskColorB { get; set; }    //Color
        public Vec4 AtlasSize { get; set; }    //Vector4
        public Vec4 SubRegion { get; set; }    //Vector4
    }
    public partial class _diode_sign
    {
        public Color ColorForeground { get; set; }    //Color
        public Color ColorMiddle { get; set; }    //Color
        public Color ColorBackground { get; set; }    //Color
        public float Metalness { get; set; }    //Float
        public float Roughness { get; set; }    //Float
        public float HeightIndex { get; set; }    //Float
        public float WidthPixels { get; set; }    //Float
        public Vec4 StretchFactor { get; set; }    //Vector4
        public float ScrollSpeed { get; set; }    //Float
        public float DotSize { get; set; }    //Float
        public float Multiplier { get; set; }    //Float
        public float AmountOfLayers { get; set; }    //Float
        public float DotsSpacing { get; set; }    //Float
        public float FarDotMultiplier { get; set; }    //Float
        public float WidthPixelsStart { get; set; }    //Float
        public float AllWidthPixels { get; set; }    //Float
        public float AmountOfLines { get; set; }    //Float
        public string Text { get; set; }    //rRef:ITexture
    }
    public partial class _earth_globe
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public string MultilayerMask { get; set; }     //rRef:Multilayer_Mask
        public string MultilayerSetup { get; set; }     //rRef:Multilayer_Setup
        public float MultilayerBlendStrength { get; set; }    //Float
        public string MaskAtlas { get; set; }    //rRef:ITexture
        public DataBuffer MaskTiles { get; set; }
        public DataBuffer Layers { get; set; }
        public float SurfaceTexAspectRatio { get; set; }    //Float
        public Vec4 MaskToTileScale { get; set; }    //Vector4
        public float MaskTileSize { get; set; }    //Float
        public string CloudsMicroblend { get; set; }    //rRef:ITexture
        public Vec4 MaskAtlasDims { get; set; }    //Vector4
        public Vec4 MaskBaseResolution { get; set; }    //Vector4
        public string CityLightsMicroblend { get; set; }    //rRef:ITexture
        public float SetupLayerMask { get; set; }    //Float
        public Color BaseColorScale { get; set; }    //Color
        public Vec4 SunDirection { get; set; }    //Vector4
        public string WaterMask { get; set; }    //rRef:ITexture
        public string Clouds { get; set; }    //rRef:ITexture
        public string CityLights { get; set; }    //rRef:ITexture
        public float LayersStartIndex { get; set; }    //Float
        public float CloudIntensity { get; set; }    //Float
        public Color CityLightsColor { get; set; }    //Color
        public string OceanDetailNormalMap { get; set; }    //rRef:ITexture
        public float OceanRoughness { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
    }
    public partial class _earth_globe_atmosphere
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color AtmosphereColor { get; set; }    //Color
        public Color AtmosphereOrangeColor { get; set; }    //Color
        public float Brigthness { get; set; }    //Float
        public float FresnelPower { get; set; }    //Float
        public float TransmissionBoost { get; set; }    //Float
        public float TransmissionBoostPower { get; set; }    //Float
        public float EarthRadius { get; set; }    //Float
        public Vec4 SunDirection { get; set; }    //Vector4
    }
    public partial class _earth_globe_lights
    {
        public float VertexOffsetFactor { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float AnimationSpeed { get; set; }    //Float
        public float AnimationFramesWidth { get; set; }    //Float
        public float AnimationFramesHeight { get; set; }    //Float
        public Vec4 ScrollSpeed { get; set; }    //Vector4
        public float HardOrSoftTransition { get; set; }    //Float
        public float FullVisibilityFactor { get; set; }    //Float
        public float EnableAlternateUVcoord { get; set; }    //Float
        public float Preview2ndState { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
        public string CityLightsMicroblend { get; set; }    //rRef:ITexture
        public Vec4 SunDirection { get; set; }    //Vector4
    }
    public partial class _emissive_control
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Translucency { get; set; }    //Float
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _eye
    {
        public string Albedo { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public string Blick { get; set; }     //rRef:ITexture
        public string NormalBubble { get; set; }    //rRef:ITexture
        public float RefractionIndex { get; set; }    //Float
        public float RefractionAmount { get; set; }    //Float
        public float EyeRadius { get; set; }    //Float
        public float EyeHorizAngleRight { get; set; }    //Float
        public float EyeHorizAngleLeft { get; set; }    //Float
        public float EyeParallaxPlane { get; set; }    //Float
        public float IrisSize { get; set; }    //Float
        public float IrisCoordMargin { get; set; }    //Float
        public float IrisCoordFactor { get; set; }    //Float
        public float BlickScale { get; set; }    //Float
        public float BubbleNormalTile { get; set; }    //Float
        public float EggMarginExponent { get; set; }    //Float
        public float EggMarginFactor { get; set; }    //Float
        public float EggSubFactor { get; set; }    //Float
        public float EggFullRadius { get; set; }    //Float
        public float Specularity { get; set; }    //Float
        public float RoughnessScale { get; set; }    //Float
        public float SubsurfaceFactor { get; set; }    //Float
        public float AntiLightbleedValue { get; set; }    //Float
        public float AntiLightbleedUpOff { get; set; }    //Float
    }
    public partial class _eye_blendable
    {
        public string VectorField { get; set; }    //rRef:ITexture
        public float FadeOutDistance { get; set; }    //Float
        public float FadeOutOffset { get; set; }    //Float
        public float GlitchChance { get; set; }    //Float
        public float GlitchOffset { get; set; }    //Float
        public Color FresnelColor { get; set; }    //Color
        public string Albedo { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public string Blick { get; set; }     //rRef:ITexture
        public string NormalBubble { get; set; }    //rRef:ITexture
        public float RefractionIndex { get; set; }    //Float
        public float RefractionAmount { get; set; }    //Float
        public float IrisSize { get; set; }    //Float
        public float EyeHorizAngleRight { get; set; }    //Float
        public float EyeHorizAngleLeft { get; set; }    //Float
        public float EyeRadius { get; set; }    //Float
        public float EyeParallaxPlane { get; set; }    //Float
        public float BubbleNormalTile { get; set; }    //Float
        public float EggFullRadius { get; set; }    //Float
        public float EggMarginExponent { get; set; }    //Float
        public float EggMarginFactor { get; set; }    //Float
        public float EggSubFactor { get; set; }    //Float
        public float IrisCoordFactor { get; set; }    //Float
        public float IrisCoordMargin { get; set; }    //Float
        public float BlickScale { get; set; }    //Float
        public float Specularity { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float SubsurfaceFactor { get; set; }    //Float
        public float AntiLightbleedValue { get; set; }    //Float
        public float AntiLightbleedUpOff { get; set; }    //Float
    }
    public partial class _eye_gradient
    {
        public string Albedo { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public string Blick { get; set; }     //rRef:ITexture
        public string NormalBubble { get; set; }    //rRef:ITexture
        public string IrisMask { get; set; }    //rRef:ITexture
        public string IrisColorGradient { get; set; }     //rRef:CGradient
        public float RefractionIndex { get; set; }    //Float
        public float RefractionAmount { get; set; }    //Float
        public float IrisSize { get; set; }    //Float
        public float EyeHorizAngleRight { get; set; }    //Float
        public float EyeHorizAngleLeft { get; set; }    //Float
        public float EyeRadius { get; set; }    //Float
        public float EyeParallaxPlane { get; set; }    //Float
        public float BubbleNormalTile { get; set; }    //Float
        public float EggFullRadius { get; set; }    //Float
        public float EggMarginExponent { get; set; }    //Float
        public float EggMarginFactor { get; set; }    //Float
        public float EggSubFactor { get; set; }    //Float
        public float IrisCoordFactor { get; set; }    //Float
        public float IrisCoordMargin { get; set; }    //Float
        public float BlickScale { get; set; }    //Float
        public float Specularity { get; set; }    //Float
        public float RoughnessScale { get; set; }    //Float
        public float SubsurfaceFactor { get; set; }    //Float
        public float AntiLightbleedValue { get; set; }    //Float
        public float AntiLightbleedUpOff { get; set; }    //Float
    }
    public partial class _eye_shadow
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color ShadowColor { get; set; }    //Color
        public float Exponent { get; set; }    //Float
        public float Intensity { get; set; }    //Float
        public string Mask { get; set; }    //rRef:ITexture
        public float WetnessRoughness { get; set; }    //Float
        public float WetnessStrength { get; set; }    //Float
        public float SubsurfaceBlur { get; set; }    //Float
    }
    public partial class _eye_shadow_blendable
    {
        public string VectorField { get; set; }    //rRef:ITexture
        public float FadeOutDistance { get; set; }    //Float
        public float FadeOutOffset { get; set; }    //Float
        public float GlitchChance { get; set; }    //Float
        public float GlitchOffset { get; set; }    //Float
        public Color FresnelColor { get; set; }    //Color
        public float FresnelColorIntensity { get; set; }    //Float
        public float FresnelExponent { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color ShadowColor { get; set; }    //Color
        public float Exponent { get; set; }    //Float
        public float Intensity { get; set; }    //Float
        public string Mask { get; set; }    //rRef:ITexture
        public float WetnessRoughness { get; set; }    //Float
        public float WetnessStrength { get; set; }    //Float
        public float SubsurfaceBlur { get; set; }    //Float
    }
    public partial class _fake_occluder
    {
        public float DissolveDistance { get; set; }    //Float
        public float DissolveBandWidth { get; set; }    //Float
    }
    public partial class _fillable_fluid
    {
        public Vec4 FluidBoundingBoxMin { get; set; }    //Vector4
        public Vec4 FluidBoundingBoxMax { get; set; }    //Vector4
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color TintColor { get; set; }    //Color
        public float RoughnessScale { get; set; }    //Float
        public float MetalnessScale { get; set; }    //Float
        public float ObjectSize { get; set; }    //Float
        public float ControlledByFx { get; set; }    //Float
        public float FillAmount { get; set; }    //Float
        public string Waves { get; set; }    //rRef:ITexture
        public float WaveAmplitude { get; set; }    //Float
        public float WaveSpeed { get; set; }    //Float
        public float WaveSize { get; set; }    //Float
    }
    public partial class _fillable_fluid_vertex
    {
        public Vec4 FluidBoundingBoxMin { get; set; }    //Vector4
        public Vec4 FluidBoundingBoxMax { get; set; }    //Vector4
        public float ControlledByFx { get; set; }    //Float
        public float ControlledByFxMode { get; set; }    //Float
        public float PinchDeformation { get; set; }    //Float
        public float FillAmount { get; set; }    //Float
        public string Waves { get; set; }    //rRef:ITexture
        public float WaveAmplitude { get; set; }    //Float
        public float WaveSpeed { get; set; }    //Float
        public float WaveSize { get; set; }    //Float
        public float Opacity { get; set; }    //Float
        public string GlassTint { get; set; }    //rRef:ITexture
        public Color TintColor { get; set; }    //Color
        public float FrontFacesReflectionPower { get; set; }    //Float
        public float IOR { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public Color GlassSpecularColor { get; set; }    //Color
        public float BlurRadius { get; set; }    //Float
    }
    public partial class _fluid_mov
    {
        public float Opacity { get; set; }    //Float
        public float OpacityBackFace { get; set; }    //Float
        public float UvTilingX { get; set; }    //Float
        public float UvTilingY { get; set; }    //Float
        public float UvOffsetX { get; set; }    //Float
        public float UvOffsetY { get; set; }    //Float
        public Vec4 RoughnessTileAndOffset { get; set; }    //Vector4
        public Vec4 NormalTileAndOffset { get; set; }    //Vector4
        public Vec4 GlassTintTileAndOffset { get; set; }    //Vector4
        public string vertex_paint_tex { get; set; }    //rRef:ITexture
        public float IsControlledByDestruction { get; set; }    //Float
        public float trans_min { get; set; }    //Float
        public float trans_max { get; set; }    //Float
        public float rot_min { get; set; }    //Float
        public float rot_max { get; set; }    //Float
        public float n_frames { get; set; }    //Float
        public float n_pieces { get; set; }    //Float
        public float play_time { get; set; }    //Float
        public float debug_familys { get; set; }    //Float
        public float frame_rate { get; set; }    //Float
        public float YAxisUp { get; set; }    //Float
        public float z_min { get; set; }    //Float
        public float ground_offset { get; set; }    //Float
        public string GlassTint { get; set; }    //rRef:ITexture
        public Color TintColor { get; set; }    //Color
        public float TintFromVertexPaint { get; set; }    //Float
        public float FrontFacesReflectionPower { get; set; }    //Float
        public float BackFacesReflectionPower { get; set; }    //Float
        public float IOR { get; set; }    //Float
        public float RefractionDepth { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public Color GlassSpecularColor { get; set; }    //Color
        public float NormalStrength { get; set; }    //Float
        public float NormalMapAffectsSpecular { get; set; }    //Float
        public string MaskTexture { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public float SurfaceMetalness { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float MaskOpacity { get; set; }    //Float
        public float GlassRoughnessBias { get; set; }    //Float
        public float MaskRoughnessBias { get; set; }    //Float
        public float BlurRadius { get; set; }    //Float
        public float BlurByRoughness { get; set; }    //Float
    }
    public partial class _frosted_glass
    {
        public float RenderBackFaces { get; set; }    //Float
        public float Opacity { get; set; }    //Float
        public float UvTilingX { get; set; }    //Float
        public float UvTilingY { get; set; }    //Float
        public float UvOffsetX { get; set; }    //Float
        public float UvOffsetY { get; set; }    //Float
        public Vec4 RoughnessTileAndOffset { get; set; }    //Vector4
        public Vec4 NormalTileAndOffset { get; set; }    //Vector4
        public Vec4 GlassTintTileAndOffset { get; set; }    //Vector4
        public float RoughnessBase { get; set; }    //Float
        public float RoughnessAttenuation { get; set; }    //Float
        public float SurfaceOpacity { get; set; }    //Float
        public Color ColorMultiplier { get; set; }    //Color
        public string GlassTint { get; set; }    //rRef:ITexture
        public Color TintSurface { get; set; }    //Color
        public Color GlassSpecularColor { get; set; }    //Color
        public float FrontFacesReflectionPower { get; set; }    //Float
        public float BackFacesReflectionPower { get; set; }    //Float
        public float IOR { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public float RefractionDepth { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public float SurfaceMetalness { get; set; }    //Float
        public float SpecularPower { get; set; }    //Float
        public float NormalStrength { get; set; }    //Float
        public float NormalMapAffectsSpecular { get; set; }    //Float
        public float BlurRadius { get; set; }    //Float
        public float BlurRoughness { get; set; }    //Float
        public float MaskOpacity { get; set; }    //Float
        public float MaskUseAlpha { get; set; }    //Float
        public float MaskAddSurface { get; set; }    //Float
        public float MaskAddOpacity { get; set; }    //Float
        public float MaskAddRoughness { get; set; }    //Float
    }
    public partial class _frosted_glass_curtain
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float MaskOpacity { get; set; }    //Float
        public float RoughnessDirty { get; set; }    //Float
        public float Opacity { get; set; }    //Float
        public Color ColorMultiplier { get; set; }    //Color
        public float TintColorAttenuation { get; set; }    //Float
        public float RoughnessAttenuation { get; set; }    //Float
        public float FrontFacesReflectionPower { get; set; }    //Float
        public float BackFacesReflectionPower { get; set; }    //Float
        public float IOR { get; set; }    //Float
        public float blurRadius { get; set; }    //Float
        public float diffuseStrength { get; set; }    //Float
        public float SpecularPower { get; set; }    //Float
        public float NormalStrength { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
    }
    public partial class _glass
    {
        public float Opacity { get; set; }    //Float
        public float OpacityBackFace { get; set; }    //Float
        public float UvTilingX { get; set; }    //Float
        public float UvTilingY { get; set; }    //Float
        public float UvOffsetX { get; set; }    //Float
        public float UvOffsetY { get; set; }    //Float
        public Vec4 RoughnessTileAndOffset { get; set; }    //Vector4
        public Vec4 NormalTileAndOffset { get; set; }    //Vector4
        public Vec4 GlassTintTileAndOffset { get; set; }    //Vector4
        public Color TintColor { get; set; }    //Color
        public string GlassTint { get; set; }    //rRef:ITexture
        public float TintFromVertexPaint { get; set; }    //Float
        public float FrontFacesReflectionPower { get; set; }    //Float
        public float BackFacesReflectionPower { get; set; }    //Float
        public float IOR { get; set; }    //Float
        public float RefractionDepth { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public Color GlassSpecularColor { get; set; }    //Color
        public float NormalStrength { get; set; }    //Float
        public float NormalMapAffectsSpecular { get; set; }    //Float
        public float SurfaceMetalness { get; set; }    //Float
        public float MaskOpacity { get; set; }    //Float
        public string MaskTexture { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public float GlassRoughnessBias { get; set; }    //Float
        public float MaskRoughnessBias { get; set; }    //Float
        public float BlurRadius { get; set; }    //Float
        public float BlurByRoughness { get; set; }    //Float
    }
    public partial class _glass_blendable
    {
        public string VectorField { get; set; }    //rRef:ITexture
        public float FadeOutDistance { get; set; }    //Float
        public float FadeOutOffset { get; set; }    //Float
        public float GlitchChance { get; set; }    //Float
        public float GlitchOffset { get; set; }    //Float
        public float Opacity { get; set; }    //Float
        public float OpacityBackFace { get; set; }    //Float
        public Color FresnelColor { get; set; }    //Color
        public float FresnelColorIntensity { get; set; }    //Float
        public float FresnelExponent { get; set; }    //Float
        public string GlassTint { get; set; }    //rRef:ITexture
        public Color TintColor { get; set; }    //Color
        public float TintFromVertexPaint { get; set; }    //Float
        public float FrontFacesReflectionPower { get; set; }    //Float
        public float BackFacesReflectionPower { get; set; }    //Float
        public float IOR { get; set; }    //Float
        public float RefractionDepth { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public Color GlassSpecularColor { get; set; }    //Color
        public float NormalStrength { get; set; }    //Float
        public float NormalMapAffectsSpecular { get; set; }    //Float
        public string MaskTexture { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public float SurfaceMetalness { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float MaskOpacity { get; set; }    //Float
        public float GlassRoughnessBias { get; set; }    //Float
        public float MaskRoughnessBias { get; set; }    //Float
        public float BlurRadius { get; set; }    //Float
        public float BlurByRoughness { get; set; }    //Float
    }
    public partial class _glass_cracked_edge
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public float AlphaScale { get; set; }    //Float
        public float UseAlphaFromSkinning { get; set; }    //Float
        public float MetalnessScale { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float AlphaThreshold { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _glass_deferred
    {
        public float UvTilingX { get; set; }    //Float
        public float UvTilingY { get; set; }    //Float
        public float UvOffsetX { get; set; }    //Float
        public float UvOffsetY { get; set; }    //Float
        public Vec4 NormalTileAndOffset { get; set; }    //Vector4
        public string GlassTint { get; set; }    //rRef:ITexture
        public Color TintColor { get; set; }    //Color
        public float TintFromVertexPaint { get; set; }    //Float
        public float TintColorAttenuation { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public float NormalStrength { get; set; }    //Float
        public string MaskTexture { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public float SurfaceMetalness { get; set; }    //Float
        public float GlassMetalness { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float MaskOpacity { get; set; }    //Float
        public float MaskRoughnessBias { get; set; }    //Float
        public string Reflection { get; set; }     //rRef:ITexture
        public float EmissiveEV { get; set; }    //Float
    }
    public partial class _glass_scope
    {
        public Vec4 UvTilingOffset { get; set; }    //Vector4
        public float LensRoughness { get; set; }    //Float
        public float SurfaceMetalness { get; set; }    //Float
        public float LensMetalness { get; set; }    //Float
        public string GlassTint { get; set; }    //rRef:ITexture
        public Color GlassTintMultiplier { get; set; }    //Color
        public float EmissiveTint { get; set; }    //Float
        public Color LensSpecularColor { get; set; }    //Color
        public float LensReflectionPower { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public float SpecularPower { get; set; }    //Float
        public float MaskOpacity { get; set; }    //Float
        public Vec4 UseMask { get; set; }    //Vector4
        public float ScopeMaskFarDistance { get; set; }    //Float
        public string ScopeMaskClose { get; set; }    //rRef:ITexture
        public string ScopeMaskFar { get; set; }    //rRef:ITexture
        public string LensBulge { get; set; }    //rRef:ITexture
        public Color ScopeInside { get; set; }    //Color
        public float DistortionStrenght { get; set; }    //Float
        public float LensBulgeStrength { get; set; }    //Float
        public float AberrationStrenght { get; set; }    //Float
        public float SphereMaskCloseRadius { get; set; }    //Float
        public float SphereMaskCloseHardness { get; set; }    //Float
        public float LensBulgeRadius { get; set; }    //Float
        public float LensBulgeHardness { get; set; }    //Float
        public float SphereMaskFarRadius { get; set; }    //Float
        public float SphereMaskFarHardness { get; set; }    //Float
        public float SphereMaskDistortionRadius { get; set; }    //Float
        public float SphereMaskDistortionHardness { get; set; }    //Float
        public Vec4 EyeRelief { get; set; }    //Vector4
    }
    public partial class _glass_window_rain
    {
        public float UvTilingX { get; set; }    //Float
        public float UvTilingY { get; set; }    //Float
        public float UvOffsetX { get; set; }    //Float
        public float UvOffsetY { get; set; }    //Float
        public Vec4 RoughnessTileAndOffset { get; set; }    //Vector4
        public Vec4 GlassTintTileAndOffset { get; set; }    //Vector4
        public float Opacity { get; set; }    //Float
        public float OpacityBackFace { get; set; }    //Float
        public string GlassTint { get; set; }    //rRef:ITexture
        public Color TintColor { get; set; }    //Color
        public Color TintSurface { get; set; }    //Color
        public float FrontFacesReflectionPower { get; set; }    //Float
        public float BackFacesReflectionPower { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public Color GlassSpecularColor { get; set; }    //Color
        public string MaskTexture { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public float SurfaceMetalness { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public float MaskOpacity { get; set; }    //Float
        public float GlassRoughnessBias { get; set; }    //Float
        public float MaskRoughnessBias { get; set; }    //Float
        public float RainTiling { get; set; }    //Float
        public float FlowTiling { get; set; }    //Float
        public string DotsNormalTxt { get; set; }    //rRef:ITexture
        public string DotsTxt { get; set; }    //rRef:ITexture
        public string FlowTxt { get; set; }    //rRef:ITexture
    }
    public partial class _hair
    {
        public string Strand_Gradient { get; set; }    //rRef:ITexture
        public float Animation_AmplitudeScale { get; set; }    //Float
        public float Animation_PeriodScale { get; set; }    //Float
        public string Strand_ID { get; set; }    //rRef:ITexture
        public string Strand_Alpha { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float AlphaCutoff { get; set; }    //Float
        public string Flow { get; set; }    //rRef:ITexture
        public float FlowStrength { get; set; }    //Float
        public float VertexColorStrength { get; set; }    //Float
        public float Scattering { get; set; }    //Float
        public float ShadowStrength { get; set; }    //Float
        public float ShadowMin { get; set; }    //Float
        public float ShadowMax { get; set; }    //Float
        public float ShadowRoughness { get; set; }    //Float
        public float DebugHairColor { get; set; }    //Float
        public string HairProfile { get; set; }     //rRef:CHairProfile
    }
    public partial class _hair_blendable
    {
        public string VectorField { get; set; }    //rRef:ITexture
        public float FadeOutDistance { get; set; }    //Float
        public float FadeOutOffset { get; set; }    //Float
        public float GlitchChance { get; set; }    //Float
        public float GlitchOffset { get; set; }    //Float
        public string Strand_Gradient { get; set; }    //rRef:ITexture
        public float Animation_AmplitudeScale { get; set; }    //Float
        public float Animation_PeriodScale { get; set; }    //Float
        public Color FresnelColor { get; set; }    //Color
        public float FresnelColorIntensity { get; set; }    //Float
        public float FresnelExponent { get; set; }    //Float
        public string Strand_ID { get; set; }    //rRef:ITexture
        public string Strand_Alpha { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float AlphaCutoff { get; set; }    //Float
        public string Flow { get; set; }    //rRef:ITexture
        public float FlowStrength { get; set; }    //Float
        public float VertexColorStrength { get; set; }    //Float
        public float Scattering { get; set; }    //Float
        public float ShadowStrength { get; set; }    //Float
        public float ShadowMin { get; set; }    //Float
        public float ShadowMax { get; set; }    //Float
        public float ShadowRoughness { get; set; }    //Float
        public float DebugHairColor { get; set; }    //Float
        public string HairProfile { get; set; }     //rRef:CHairProfile
    }
    public partial class _hair_proxy
    {
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Albedo { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Scattering { get; set; }    //Float
    }
    public partial class _ice_fluid_mov
    {
        public float WaveIdleNormalStrength { get; set; }    //Float
        public Vec4 WaveIdleTilingAndSpeed { get; set; }    //Vector4
        public float DebugTimeOverride { get; set; }    //Float
        public float n_frames { get; set; }    //Float
        public float frame_rate { get; set; }    //Float
        public float SimulationAtlasFrameCountX { get; set; }    //Float
        public float SimulationAtlasFrameCountY { get; set; }    //Float
        public string SimulationAtlas { get; set; }    //rRef:ITexture
        public string WaveIdleMap { get; set; }    //rRef:ITexture
        public float WaveIdleHeight { get; set; }    //Float
        public float HeightMin { get; set; }    //Float
        public float HeightMax { get; set; }    //Float
        public float WaterRoughness { get; set; }    //Float
        public float WaterSpecF0 { get; set; }    //Float
        public float WaterSpecF90 { get; set; }    //Float
        public Color WaterColorShallow { get; set; }    //Color
        public Color WaterColorDeep { get; set; }    //Color
        public Color WaveColor0 { get; set; }    //Color
        public Color WaveColor1 { get; set; }    //Color
        public float WaveNoiseTiling { get; set; }    //Float
        public float WaveNoiseContrast { get; set; }    //Float
        public float WaveNoiseContrastOut { get; set; }    //Float
        public float RefractionStrength { get; set; }    //Float
        public Color IceColor1 { get; set; }    //Color
        public Color IceColor2 { get; set; }    //Color
        public float IceTiling { get; set; }    //Float
        public float UVRatio { get; set; }    //Float
        public float IceDepth { get; set; }    //Float
        public float IceNormalStrength { get; set; }    //Float
        public Color BloodColor { get; set; }    //Color
        public float BloodFadeStart { get; set; }    //Float
        public float BloodFadeEnd { get; set; }    //Float
        public string WaveNoiseMap { get; set; }    //rRef:ITexture
        public string IceMasksMap { get; set; }    //rRef:ITexture
        public string IceNormalMap { get; set; }    //rRef:ITexture
    }
    public partial class _ice_ver_mov_translucent
    {
        public string vertex_paint_tex { get; set; }    //rRef:ITexture
        public float trans_min { get; set; }    //Float
        public float trans_max { get; set; }    //Float
        public float rot_min { get; set; }    //Float
        public float rot_max { get; set; }    //Float
        public float n_frames { get; set; }    //Float
        public float n_pieces { get; set; }    //Float
        public float play_time { get; set; }    //Float
        public float debug_familys { get; set; }    //Float
        public float frame_rate { get; set; }    //Float
        public string WaveIdleMap { get; set; }    //rRef:ITexture
        public float WaveIdleHeight { get; set; }    //Float
        public Vec4 WaveIdleTilingAndSpeed { get; set; }    //Vector4
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public Color RefractionTint { get; set; }    //Color
        public float IOR { get; set; }    //Float
    }
    public partial class _lights_interactive
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string Emissive { get; set; }    //rRef:ITexture
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
        public float Zone0EmissiveEV { get; set; }    //Float
        public float Zone1EmissiveEV { get; set; }    //Float
        public float Zone2EmissiveEV { get; set; }    //Float
        public float Zone3EmissiveEV { get; set; }    //Float
        public Vec4 DebugLightsIntensity { get; set; }    //Vector4
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _loot_drop_highlight
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float Mode { get; set; }    //Float
        public Color HighlightColor { get; set; }    //Color
        public float HighlightIntensity { get; set; }    //Float
        public float SolidBlendingDistanceStart { get; set; }    //Float
        public float SolidBlendingDistanceEnd { get; set; }    //Float
    }
    public partial class _mesh_decal
    {
        public float VertexOffsetFactor { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float DiffuseAlpha { get; set; }    //Float
        public float UVOffsetX { get; set; }    //Float
        public float UVOffsetY { get; set; }    //Float
        public float UVRotation { get; set; }    //Float
        public float UVScaleX { get; set; }    //Float
        public float UVScaleY { get; set; }    //Float
        public string SecondaryMask { get; set; }    //rRef:ITexture
        public float SecondaryMaskUVScale { get; set; }    //Float
        public float SecondaryMaskInfluence { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalAlpha { get; set; }    //Float
        public string NormalAlphaTex { get; set; }    //rRef:ITexture
        public float UseNormalAlphaTex { get; set; }    //Float
        public float NormalsBlendingMode { get; set; }    //Float
        public string NormalsBlendingModeAlpha { get; set; }    //rRef:ITexture
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float AnimationSpeed { get; set; }    //Float
        public float AnimationFramesWidth { get; set; }    //Float
        public float AnimationFramesHeight { get; set; }    //Float
        public float DepthThreshold { get; set; }    //Float
    }
    public partial class _mesh_decal_blendable
    {
        public string VectorField { get; set; }    //rRef:ITexture
        public float FadeOutDistance { get; set; }    //Float
        public float FadeOutOffset { get; set; }    //Float
        public float GlitchChance { get; set; }    //Float
        public float GlitchOffset { get; set; }    //Float
        public float VertexOffsetFactor { get; set; }    //Float
        public Color FresnelColor { get; set; }    //Color
        public float FresnelColorIntensity { get; set; }    //Float
        public float FresnelExponent { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float DiffuseAlpha { get; set; }    //Float
        public float UVOffsetX { get; set; }    //Float
        public float UVOffsetY { get; set; }    //Float
        public float UVRotation { get; set; }    //Float
        public float UVScaleX { get; set; }    //Float
        public float UVScaleY { get; set; }    //Float
        public string SecondaryMask { get; set; }    //rRef:ITexture
        public float SecondaryMaskUVScale { get; set; }    //Float
        public float SecondaryMaskInfluence { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalAlpha { get; set; }    //Float
        public string NormalAlphaTex { get; set; }    //rRef:ITexture
        public float UseNormalAlphaTex { get; set; }    //Float
        public float NormalsBlendingMode { get; set; }    //Float
        public string NormalsBlendingModeAlpha { get; set; }    //rRef:ITexture
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float AnimationSpeed { get; set; }    //Float
        public float AnimationFramesWidth { get; set; }    //Float
        public float AnimationFramesHeight { get; set; }    //Float
        public float DepthThreshold { get; set; }    //Float
    }
    public partial class _mesh_decal_double_diffuse
    {
        public float VertexOffsetFactor { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float DiffuseAlpha { get; set; }    //Float
        public string SecondaryDiffuseAlpha { get; set; }    //rRef:ITexture
        public Color SecondaryDiffuseColor { get; set; }    //Color
        public float SecondaryDiffuseAlphaIntensity { get; set; }    //Float
        public float UVOffsetX { get; set; }    //Float
        public float UVOffsetY { get; set; }    //Float
        public float UVRotation { get; set; }    //Float
        public float UVScaleX { get; set; }    //Float
        public float UVScaleY { get; set; }    //Float
        public string SecondaryMask { get; set; }    //rRef:ITexture
        public float SecondaryMaskUVScale { get; set; }    //Float
        public float SecondaryMaskInfluence { get; set; }    //Float
        public string NormalsBlendingModeAlpha { get; set; }    //rRef:ITexture
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalAlpha { get; set; }    //Float
        public string NormalAlphaTex { get; set; }    //rRef:ITexture
        public float UseNormalAlphaTex { get; set; }    //Float
        public float NormalsBlendingMode { get; set; }    //Float
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float AnimationSpeed { get; set; }    //Float
        public float AnimationFramesWidth { get; set; }    //Float
        public float AnimationFramesHeight { get; set; }    //Float
        public float DepthThreshold { get; set; }    //Float
    }
    public partial class _mesh_decal_emissive
    {
        public float DamageInfluence { get; set; }    //Float
        public float DamageInfluenceDebug { get; set; }    //Float
        public float VertexOffsetFactor { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public Color DiffuseColor2 { get; set; }    //Color
        public float DiffuseAlpha { get; set; }    //Float
        public float UVOffsetX { get; set; }    //Float
        public float UVOffsetY { get; set; }    //Float
        public float UVRotation { get; set; }    //Float
        public float UVScaleX { get; set; }    //Float
        public float UVScaleY { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float AnimationSpeed { get; set; }    //Float
        public float AnimationFramesWidth { get; set; }    //Float
        public float AnimationFramesHeight { get; set; }    //Float
        public Vec4 ScrollSpeed { get; set; }    //Vector4
        public float HardOrSoftTransition { get; set; }    //Float
        public float FullVisibilityFactor { get; set; }    //Float
        public float EnableAlternateColor { get; set; }    //Float
        public float EnableAlternateUVcoord { get; set; }    //Float
        public float Preview2ndState { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _mesh_decal_emissive_subsurface
    {
        public float VertexOffsetFactor { get; set; }    //Float
        public string EmissiveMask { get; set; }    //rRef:ITexture
        public string SecondaryMask { get; set; }    //rRef:ITexture
        public Vec4 EmissiveMaskChannel { get; set; }    //Vector4
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _mesh_decal_gradientmap_recolor
    {
        public float VertexOffsetFactor { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public string MaskTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float DiffuseAlpha { get; set; }    //Float
        public string GradientMap { get; set; }    //rRef:ITexture
        public string SecondaryMask { get; set; }    //rRef:ITexture
        public float SecondaryMaskUVScale { get; set; }    //Float
        public float SecondaryMaskInfluence { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalAlpha { get; set; }    //Float
        public float NormalsBlendingMode { get; set; }    //Float
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float AnimationSpeed { get; set; }    //Float
        public float AnimationFramesWidth { get; set; }    //Float
        public float AnimationFramesHeight { get; set; }    //Float
        public float DepthThreshold { get; set; }    //Float
    }
    public partial class _mesh_decal_gradientmap_recolor_2
    {
        public float VertexOffsetFactor { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public string MaskTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float DiffuseAlpha { get; set; }    //Float
        public string Gradient { get; set; }     //rRef:CGradient
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalAlpha { get; set; }    //Float
        public float NormalsBlendingMode { get; set; }    //Float
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float AnimationSpeed { get; set; }    //Float
        public float AnimationFramesWidth { get; set; }    //Float
        public float AnimationFramesHeight { get; set; }    //Float
        public float DepthThreshold { get; set; }    //Float
    }
    public partial class _mesh_decal_gradientmap_recolor_emissive
    {
        public float VertexOffsetFactor { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public string MaskTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float DiffuseAlpha { get; set; }    //Float
        public string GradientMap { get; set; }    //rRef:ITexture
        public string EmissiveGradientMap { get; set; }    //rRef:ITexture
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalAlpha { get; set; }    //Float
        public float NormalsBlendingMode { get; set; }    //Float
        public float AlphaMaskContrast { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float AnimationSpeed { get; set; }    //Float
        public float AnimationFramesWidth { get; set; }    //Float
        public float AnimationFramesHeight { get; set; }    //Float
        public float DepthThreshold { get; set; }    //Float
    }
    public partial class _mesh_decal_multitinted
    {
        public float VertexOffsetFactor { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float DiffuseAlpha { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalAlpha { get; set; }    //Float
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float AnimationSpeed { get; set; }    //Float
        public float AnimationFramesWidth { get; set; }    //Float
        public float AnimationFramesHeight { get; set; }    //Float
        public float DepthThreshold { get; set; }    //Float
        public string TintMaskTexture { get; set; }    //rRef:ITexture
        public Color TintColor0 { get; set; }    //Color
        public Color TintColor1 { get; set; }    //Color
        public Color TintColor2 { get; set; }    //Color
        public Color TintColor3 { get; set; }    //Color
        public Color TintColor4 { get; set; }    //Color
        public Color TintColor5 { get; set; }    //Color
        public Color TintColor6 { get; set; }    //Color
        public Color TintColor7 { get; set; }    //Color
    }
    public partial class _mesh_decal_parallax
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float DiffuseAlpha { get; set; }    //Float
        public float UVOffsetX { get; set; }    //Float
        public float UVOffsetY { get; set; }    //Float
        public float UVRotation { get; set; }    //Float
        public float UVScaleX { get; set; }    //Float
        public float UVScaleY { get; set; }    //Float
        public string SecondaryMask { get; set; }    //rRef:ITexture
        public float SecondaryMaskUVScale { get; set; }    //Float
        public float SecondaryMaskInfluence { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalAlpha { get; set; }    //Float
        public string NormalAlphaTex { get; set; }    //rRef:ITexture
        public float UseNormalAlphaTex { get; set; }    //Float
        public float NormalsBlendingMode { get; set; }    //Float
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float AnimationSpeed { get; set; }    //Float
        public float AnimationFramesWidth { get; set; }    //Float
        public float AnimationFramesHeight { get; set; }    //Float
        public float DepthThreshold { get; set; }    //Float
        public string HeightTexture { get; set; }    //rRef:ITexture
        public float HeightStrength { get; set; }    //Float
    }
    public partial class _mesh_decal_revealed
    {
        public float VertexOffsetFactor { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float DiffuseAlpha { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalAlpha { get; set; }    //Float
        public float NormalsBlendingMode { get; set; }    //Float
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float AnimationSpeed { get; set; }    //Float
        public float AnimationFramesWidth { get; set; }    //Float
        public float AnimationFramesHeight { get; set; }    //Float
        public float TileNumber { get; set; }    //Float
        public float DepthThreshold { get; set; }    //Float
        public string FlowTexture { get; set; }    //rRef:ITexture
    }
    public partial class _mesh_decal_wet_character
    {
        public float VertexOffsetFactor { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float DiffuseAlpha { get; set; }    //Float
        public float UVOffsetX { get; set; }    //Float
        public float UVOffsetY { get; set; }    //Float
        public float UVRotation { get; set; }    //Float
        public float UVScaleX { get; set; }    //Float
        public float UVScaleY { get; set; }    //Float
        public string SecondaryMask { get; set; }    //rRef:ITexture
        public float SecondaryMaskUVScale { get; set; }    //Float
        public float SecondaryMaskInfluence { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalAlpha { get; set; }    //Float
        public string NormalAlphaTex { get; set; }    //rRef:ITexture
        public float UseNormalAlphaTex { get; set; }    //Float
        public float NormalsBlendingMode { get; set; }    //Float
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float AnimationSpeed { get; set; }    //Float
        public float AnimationFramesWidth { get; set; }    //Float
        public float AnimationFramesHeight { get; set; }    //Float
        public float DepthThreshold { get; set; }    //Float
    }
    public partial class _metal_base_bink
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public string VideoCanvasName { get; set; }     //CName
        public string BinkY { get; set; }    //rRef:ITexture
        public string BinkCR { get; set; }    //rRef:ITexture
        public string BinkCB { get; set; }    //rRef:ITexture
        public string BinkA { get; set; }    //rRef:ITexture
        public DataBuffer BinkParams { get; set; }
    }
    public partial class _metal_base_det
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float AlphaThreshold { get; set; }    //Float
        public string DetailColor { get; set; }    //rRef:ITexture
        public string DetailNormal { get; set; }    //rRef:ITexture
        public float DetailU { get; set; }    //Float
        public float DetailV { get; set; }    //Float
    }
    public partial class _metal_base_det_dithered
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float AlphaThreshold { get; set; }    //Float
        public string DetailColor { get; set; }    //rRef:ITexture
        public string DetailNormal { get; set; }    //rRef:ITexture
        public float DetailU { get; set; }    //Float
        public float DetailV { get; set; }    //Float
    }
    public partial class _metal_base_dithered
    {
        public float VehicleDamageInfluence { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveLift { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _metal_base_gradientmap_recolor
    {
        public float VehicleDamageInfluence { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Mask { get; set; }    //rRef:ITexture
        public string GradientMap { get; set; }    //rRef:ITexture
        public string EmissiveGradientMap { get; set; }    //rRef:ITexture
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _metal_base_parallax
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveLift { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public string HeightTexture { get; set; }    //rRef:ITexture
        public float HeightStrength { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _metal_base_trafficlight_proxy
    {
        public float TrafficCellSize { get; set; }    //Float
        public float TrafficSpeed { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveLift { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _metal_base_ui
    {
        public string ScanlineTexture { get; set; }    //rRef:ITexture
        public float Metalness { get; set; }    //Float
        public float RoughnessScale { get; set; }    //Float
        public float FixToPbr { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float LayersSeparation { get; set; }    //Float
        public Vec4 IntensityPerLayer { get; set; }    //Vector4
        public Vec4 ScanlinesDensity { get; set; }    //Vector4
        public float ScanlinesIntensity { get; set; }    //Float
        public float IsBroken { get; set; }    //Float
        public float ImageScale { get; set; }    //Float
        public string UIRenderTexture { get; set; }    //rRef:ITexture
        public Vec4 RenderTextureScale { get; set; }    //Vector4
        public float VerticalFlipEnabled { get; set; }    //Float
        public Vec4 TexturePartUV { get; set; }    //Vector4
        public string DirtTexture { get; set; }    //rRef:ITexture
        public Color DirtColor { get; set; }    //Color
        public float DirtRoughness { get; set; }    //Float
        public float DirtEmissiveAttenuation { get; set; }    //Float
        public float DirtContrast { get; set; }    //Float
        public Color Tint { get; set; }    //Color
        public float FixForBlack { get; set; }    //Float
        public float FixForVerticalSlide { get; set; }    //Float
        public Color ForcedTint { get; set; }    //Color
    }
    public partial class _metal_base_vertexcolored
    {
    }
    public partial class _mikoshi_blocks_big
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public Color EmissiveColor { get; set; }    //Color
        public string DataTex { get; set; }    //rRef:ITexture
        public string NoiseTex { get; set; }    //rRef:ITexture
        public string PcbTex { get; set; }    //rRef:ITexture
    }
    public partial class _mikoshi_blocks_medium
    {
        public float RandomSeed { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public Color EmissiveColor { get; set; }    //Color
        public string DataTex { get; set; }    //rRef:ITexture
        public string NoiseTex { get; set; }    //rRef:ITexture
    }
    public partial class _mikoshi_blocks_small
    {
        public float RandomSeed { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public Color EmissiveColor { get; set; }    //Color
        public string DataTex { get; set; }    //rRef:ITexture
        public string NoiseTex { get; set; }    //rRef:ITexture
    }
    public partial class _mikoshi_parallax
    {
        public string RoomAtlas { get; set; }    //rRef:ITexture
        public string LayerAtlas { get; set; }    //rRef:ITexture
        public Vec4 AtlasGridUvRatio { get; set; }    //Vector4
        public float AtlasDepth { get; set; }    //Float
        public float roomWidth { get; set; }    //Float
        public float roomHeight { get; set; }    //Float
        public float roomDepth { get; set; }    //Float
        public float positionXoffset { get; set; }    //Float
        public float positionYoffset { get; set; }    //Float
        public float LayerDepth { get; set; }    //Float
        public float Frostiness { get; set; }    //Float
        public string WindowTexture { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
    }
    public partial class _mikoshi_prison_cell
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float EdgeFalloff { get; set; }    //Float
        public float DepthAttenuation { get; set; }    //Float
        public float DepthAttenuationPower { get; set; }    //Float
        public float LightIntensity { get; set; }    //Float
        public Color LightColor { get; set; }    //Color
        public string SilhouetteTex { get; set; }    //rRef:ITexture
    }
    public partial class _multilayered_clear_coat
    {
        public float Opacity { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color CoatTintFwd { get; set; }    //Color
        public Color CoatTintSide { get; set; }    //Color
        public float CoatTintFresnelBias { get; set; }    //Float
        public Color CoatSpecularColor { get; set; }    //Color
        public float CoatNormalStrength { get; set; }    //Float
        public float CoatRoughnessBase { get; set; }    //Float
        public float CoatReflectionPower { get; set; }    //Float
        public float CoatFresnelBias { get; set; }    //Float
        public float CoatLayerMin { get; set; }    //Float
        public float CoatLayerMax { get; set; }    //Float
        public string GlobalNormal { get; set; }    //rRef:ITexture
        public string MultilayerMask { get; set; }     //rRef:Multilayer_Mask
        public string MultilayerSetup { get; set; }     //rRef:Multilayer_Setup
        public string MaskAtlas { get; set; }    //rRef:ITexture
        public DataBuffer MaskTiles { get; set; }
        public DataBuffer Layers { get; set; }
        public float LayersStartIndex { get; set; }    //Float
        public float SurfaceTexAspectRatio { get; set; }    //Float
        public Vec4 MaskToTileScale { get; set; }    //Vector4
        public float MaskTileSize { get; set; }    //Float
        public Vec4 MaskAtlasDims { get; set; }    //Vector4
        public Vec4 MaskBaseResolution { get; set; }    //Vector4
        public float SetupLayerMask { get; set; }    //Float
    }
    public partial class _multilayered_terrain
    {
        public float UseOldVertexFormat { get; set; }    //Float
        public Vec4 UVGenScaleOffset { get; set; }    //Vector4
        public float DebugPreviewMasks { get; set; }    //Float
        public float UseGlobalNormal { get; set; }    //Float
        public string MultilayerMask { get; set; }     //rRef:Multilayer_Mask
        public string GlobalNormal { get; set; }    //rRef:ITexture
        public string MultilayerSetup { get; set; }     //rRef:Multilayer_Setup
        public string BaseColor { get; set; }    //rRef:ITexture
        public string TilingMap { get; set; }    //rRef:ITexture
        public string MaskAtlas { get; set; }    //rRef:ITexture
        public DataBuffer MaskTiles { get; set; }
        public DataBuffer Layers { get; set; }
        public float LayersStartIndex { get; set; }    //Float
        public float SurfaceTexAspectRatio { get; set; }    //Float
        public Vec4 MaskToTileScale { get; set; }    //Vector4
        public float MaskTileSize { get; set; }    //Float
        public Vec4 MaskAtlasDims { get; set; }    //Vector4
        public Vec4 MaskBaseResolution { get; set; }    //Vector4
        public float SetupLayerMask { get; set; }    //Float
        public string TerrainSetup { get; set; }     //rRef:CTerrainSetup
        public DataBuffer TilingDataBuffer { get; set; }
        public string MaskFoliage { get; set; }    //rRef:ITexture
    }
    public partial class _neon_parallax
    {
        public float UvTilingX { get; set; }    //Float
        public float UvTilingY { get; set; }    //Float
        public float UvOffsetX { get; set; }    //Float
        public float UvOffsetY { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public float UseGradientMapMode { get; set; }    //Float
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string GradientMap { get; set; }    //rRef:ITexture
        public Color BaseColorScaleEdgeStart { get; set; }    //Color
        public Color BaseColorScaleEdgeEnd { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Emissive { get; set; }    //rRef:ITexture
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float ParallaxDepth { get; set; }    //Float
        public float ParallaxFlip { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _presimulated_particles
    {
        public string vertex_paint_tex { get; set; }    //rRef:ITexture
        public float trans_min { get; set; }    //Float
        public float trans_max { get; set; }    //Float
        public float n_frames { get; set; }    //Float
        public float n_pieces { get; set; }    //Float
        public float play_time { get; set; }    //Float
        public float frame_rate { get; set; }    //Float
        public float ParticleScale { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Translucency { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _proxy_ad
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Translucency { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _proxy_crowd
    {
        public string Atlas { get; set; }    //rRef:ITexture
        public string BaseColor { get; set; }    //rRef:ITexture
        public string Metalness { get; set; }    //rRef:ITexture
        public Color Color1 { get; set; }    //Color
        public Color Color2 { get; set; }    //Color
        public Color Color3 { get; set; }    //Color
        public Color Color4 { get; set; }    //Color
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Translucency { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public Vec4 AtlasSize { get; set; }    //Vector4
    }
    public partial class _q116_mikoshi_cubes
    {
        public float PointCloudTextureHeight { get; set; }    //Float
        public Vec4 TransMin { get; set; }    //Vector4
        public Vec4 TransMax { get; set; }    //Vector4
        public string WorldPosTex { get; set; }    //rRef:ITexture
        public float CubeSize { get; set; }    //Float
        public float Tiling { get; set; }    //Float
        public float DiffuseVariationUvScale { get; set; }    //Float
        public float ParallaxHeightScale { get; set; }    //Float
        public float ParallaxFlip { get; set; }    //Float
        public string Emissive { get; set; }    //rRef:ITexture
        public string ExtraMasks { get; set; }    //rRef:ITexture
        public string EdgeMask { get; set; }    //rRef:ITexture
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _q116_mikoshi_floor
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public Color EmissiveColor { get; set; }    //Color
        public string Emissive { get; set; }    //rRef:ITexture
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float FalloffDistanceStart { get; set; }    //Float
        public float FalloffDistanceEnd { get; set; }    //Float
        public float GlowBrightnessStart { get; set; }    //Float
        public float GlowBrightnessEnd { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public string VectorField1 { get; set; }    //rRef:ITexture
        public string VectorField2 { get; set; }    //rRef:ITexture
        public float VectorFieldSliceCount { get; set; }    //Float
        public string Grain { get; set; }    //rRef:ITexture
    }
    public partial class _q202_lake_surface
    {
        public string Starmap { get; set; }     //rRef:ITexture
        public string Galaxy { get; set; }    //rRef:ITexture
        public float GalaxyIntensity { get; set; }    //Float
        public float StarmapIntensity { get; set; }    //Float
        public float DimScale { get; set; }    //Float
        public float BrightScale { get; set; }    //Float
        public float ConstelationScale { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _rain
    {
        public float RainType { get; set; }    //Float
        public string WindNoise { get; set; }    //rRef:ITexture
        public float Speed { get; set; }    //Float
        public float Scale { get; set; }    //Float
        public float WindSkew { get; set; }    //Float
        public float WindStrength { get; set; }    //Float
        public float WindDirectionMovement { get; set; }    //Float
        public float WindFrequency { get; set; }    //Float
        public float Height { get; set; }    //Float
        public float Distance { get; set; }    //Float
        public float Radius { get; set; }    //Float
        public float BrightnessCards { get; set; }    //Float
        public float BrightnessDrops { get; set; }    //Float
        public float MovementStrength { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float UvSpeed { get; set; }    //Float
        public string Mask { get; set; }    //rRef:ITexture
    }
    public partial class _road_debug_grid
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public float TransitionSize { get; set; }    //Float
        public float GridScale { get; set; }    //Float
        public float EnableWorldSpace { get; set; }    //Float
    }
    public partial class _set_stencil_3
    {
        public float ExtraThickness { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
    }
    public partial class _silverhand_overlay
    {
        public float DepthOffset { get; set; }    //Float
        public string VectorField { get; set; }    //rRef:ITexture
        public float GlitchChance { get; set; }    //Float
        public float GlitchOffset { get; set; }    //Float
        public float GlitchTimeSeed { get; set; }    //Float
        public string FresnelMask { get; set; }    //rRef:ITexture
        public float FresnelMaskIntensity { get; set; }    //Float
        public string GlobalNormal { get; set; }    //rRef:ITexture
        public string MultilayerMask { get; set; }     //rRef:Multilayer_Mask
        public string MultilayerSetup { get; set; }     //rRef:Multilayer_Setup
        public float Emissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float BayerScale { get; set; }    //Float
        public float BayerIntensity { get; set; }    //Float
        public Vec4 VertexColorSelection { get; set; }    //Vector4
        public float VectorFieldTiling { get; set; }    //Float
        public float VectorFieldIntensity { get; set; }    //Float
        public Vec4 VectorFieldAnim { get; set; }    //Vector4
        public Color FresnelColor { get; set; }    //Color
        public float FresnelColorIntensity { get; set; }    //Float
        public float FresnelExponent { get; set; }    //Float
        public string MaskAtlas { get; set; }    //rRef:ITexture
        public DataBuffer MaskTiles { get; set; }
        public DataBuffer Layers { get; set; }
        public float LayersStartIndex { get; set; }    //Float
        public float SurfaceTexAspectRatio { get; set; }    //Float
        public Vec4 MaskToTileScale { get; set; }    //Vector4
        public float MaskTileSize { get; set; }    //Float
        public Vec4 MaskAtlasDims { get; set; }    //Vector4
        public Vec4 MaskBaseResolution { get; set; }    //Vector4
        public float SetupLayerMask { get; set; }    //Float
    }
    public partial class _silverhand_overlay_blendable
    {
        public float FadeOutDistance { get; set; }    //Float
        public float FadeOutOffset { get; set; }    //Float
        public string VectorField { get; set; }    //rRef:ITexture
        public float GlitchChance { get; set; }    //Float
        public float GlitchOffset { get; set; }    //Float
        public float GlitchTimeSeed { get; set; }    //Float
        public string FresnelMask { get; set; }    //rRef:ITexture
        public float FresnelMaskIntensity { get; set; }    //Float
        public Color FresnelColor { get; set; }    //Color
        public float FresnelColorIntensity { get; set; }    //Float
        public float FresnelExponent { get; set; }    //Float
        public float Emissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float BayerScale { get; set; }    //Float
        public float BayerIntensity { get; set; }    //Float
        public Vec4 VertexColorSelection { get; set; }    //Vector4
        public float VectorFieldTiling { get; set; }    //Float
        public float VectorFieldIntensity { get; set; }    //Float
        public Vec4 VectorFieldAnim { get; set; }    //Vector4
        public string GlobalNormal { get; set; }    //rRef:ITexture
        public string MultilayerMask { get; set; }     //rRef:Multilayer_Mask
        public string MultilayerSetup { get; set; }     //rRef:Multilayer_Setup
        public string MaskAtlas { get; set; }    //rRef:ITexture
        public DataBuffer MaskTiles { get; set; }
        public DataBuffer Layers { get; set; }
        public float LayersStartIndex { get; set; }    //Float
        public float SurfaceTexAspectRatio { get; set; }    //Float
        public Vec4 MaskToTileScale { get; set; }    //Vector4
        public float MaskTileSize { get; set; }    //Float
        public Vec4 MaskAtlasDims { get; set; }    //Vector4
        public Vec4 MaskBaseResolution { get; set; }    //Vector4
        public float SetupLayerMask { get; set; }    //Float
    }
    public partial class _skin
    {
        public string Albedo { get; set; }    //rRef:ITexture
        public string SecondaryAlbedo { get; set; }    //rRef:ITexture
        public float SecondaryAlbedoInfluence { get; set; }    //Float
        public float SecondaryAlbedoTintColorInfluence { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string DetailNormal { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public float DetailRoughnessBiasMin { get; set; }    //Float
        public float DetailRoughnessBiasMax { get; set; }    //Float
        public float MicroDetailUVScale01 { get; set; }    //Float
        public float MicroDetailUVScale02 { get; set; }    //Float
        public string MicroDetail { get; set; }    //rRef:ITexture
        public float MicroDetailInfluence { get; set; }    //Float
        public string TintColorMask { get; set; }    //rRef:ITexture
        public Color TintColor { get; set; }    //Color
        public float TintScale { get; set; }    //Float
        public string SkinProfile { get; set; }     //rRef:CSkinProfile
        public string Detailmap_Stretch { get; set; }    //rRef:ITexture
        public string EmissiveMask { get; set; }    //rRef:ITexture
        public float EmissiveEV { get; set; }    //Float
        public string Detailmap_Squash { get; set; }    //rRef:ITexture
        public float CavityIntensity { get; set; }    //Float
        public string Bloodflow { get; set; }    //rRef:ITexture
        public Color BloodColor { get; set; }    //Color
        public float DetailNormalInfluence { get; set; }    //Float
    }
    public partial class _skin_blendable
    {
        public string VectorField { get; set; }    //rRef:ITexture
        public float FadeOutDistance { get; set; }    //Float
        public float FadeOutOffset { get; set; }    //Float
        public float GlitchChance { get; set; }    //Float
        public float GlitchOffset { get; set; }    //Float
        public Color FresnelColor { get; set; }    //Color
        public float FresnelColorIntensity { get; set; }    //Float
        public float FresnelExponent { get; set; }    //Float
        public string Albedo { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public string DetailNormal { get; set; }    //rRef:ITexture
        public float DetailNormalInfluence { get; set; }    //Float
        public float CavityIntensity { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float DetailRoughnessBiasMin { get; set; }    //Float
        public float DetailRoughnessBiasMax { get; set; }    //Float
        public string MicroDetail { get; set; }    //rRef:ITexture
        public float MicroDetailUVScale01 { get; set; }    //Float
        public float MicroDetailUVScale02 { get; set; }    //Float
        public float MicroDetailInfluence { get; set; }    //Float
        public string TintColorMask { get; set; }    //rRef:ITexture
        public Color TintColor { get; set; }    //Color
        public float TintScale { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public string Detailmap_Stretch { get; set; }    //rRef:ITexture
        public string Detailmap_Squash { get; set; }    //rRef:ITexture
        public string Bloodflow { get; set; }    //rRef:ITexture
        public Color BloodColor { get; set; }    //Color
        public string SkinProfile { get; set; }     //rRef:CSkinProfile
    }
    public partial class _skybox
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string DiffuseDayTime { get; set; }    //rRef:ITexture
        public string DiffuseNightTime { get; set; }    //rRef:ITexture
    }
    public partial class _speedtree_3d_v8_billboard
    {
        public string WindNoise { get; set; }    //rRef:ITexture
        public float WindLodFlags { get; set; }    //Float
        public float WindDataAvailable { get; set; }    //Float
        public float HorizontalBillboardsCount { get; set; }    //Float
        public float ContainsTopBillboard { get; set; }    //Float
        public float TreeCrownRadius { get; set; }    //Float
        public string DiffuseMap { get; set; }    //rRef:ITexture
        public string NormalMap { get; set; }    //rRef:ITexture
        public string TransGlossMap { get; set; }    //rRef:ITexture
        public string FoliageProfileMap { get; set; }    //rRef:ITexture
        public string FoliageProfile { get; set; }     //rRef:CFoliageProfile
        public float MeshTotalHeight { get; set; }    //Float
        public float ForceTerrainBlend { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
    }
    public partial class _speedtree_3d_v8_onesided
    {
        public string WindNoise { get; set; }    //rRef:ITexture
        public string BonesPositionsMap { get; set; }    //rRef:ITexture
        public string BonesAdditionalDataMap { get; set; }    //rRef:ITexture
        public Vec4 BoneMapData { get; set; }    //Vector4
        public float WindLodFlags { get; set; }    //Float
        public float WindDataAvailable { get; set; }    //Float
        public string DiffuseMap { get; set; }    //rRef:ITexture
        public string NormalMap { get; set; }    //rRef:ITexture
        public string TransGlossMap { get; set; }    //rRef:ITexture
        public string FoliageProfileMap { get; set; }    //rRef:ITexture
        public string FoliageProfile { get; set; }     //rRef:CFoliageProfile
        public float MeshTotalHeight { get; set; }    //Float
        public float ForceTerrainBlend { get; set; }    //Float
    }
    public partial class _speedtree_3d_v8_onesided_gradient_recolor
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Mask { get; set; }    //rRef:ITexture
        public string GradientMap { get; set; }    //rRef:ITexture
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _speedtree_3d_v8_seams
    {
        public string WindNoise { get; set; }    //rRef:ITexture
        public string BoneMap { get; set; }    //rRef:ITexture
        public string BonesPositionsMap { get; set; }    //rRef:ITexture
        public string BonesAdditionalDataMap { get; set; }    //rRef:ITexture
        public Vec4 BoneMapData { get; set; }    //Vector4
        public float WindLodFlags { get; set; }    //Float
        public float WindDataAvailable { get; set; }    //Float
        public string DiffuseMap { get; set; }    //rRef:ITexture
        public string NormalMap { get; set; }    //rRef:ITexture
        public string TransGlossMap { get; set; }    //rRef:ITexture
        public string FoliageProfileMap { get; set; }    //rRef:ITexture
        public string FoliageProfile { get; set; }     //rRef:CFoliageProfile
        public float MeshTotalHeight { get; set; }    //Float
        public float ForceTerrainBlend { get; set; }    //Float
    }
    public partial class _speedtree_3d_v8_twosided
    {
        public string WindNoise { get; set; }    //rRef:ITexture
        public string BoneMap { get; set; }    //rRef:ITexture
        public string BonesPositionsMap { get; set; }    //rRef:ITexture
        public string BonesAdditionalDataMap { get; set; }    //rRef:ITexture
        public Vec4 BoneMapData { get; set; }    //Vector4
        public float WindLodFlags { get; set; }    //Float
        public float WindDataAvailable { get; set; }    //Float
        public float TwosidedFlipN { get; set; }    //Float
        public string DiffuseMap { get; set; }    //rRef:ITexture
        public string NormalMap { get; set; }    //rRef:ITexture
        public string TransGlossMap { get; set; }    //rRef:ITexture
        public string FoliageProfileMap { get; set; }    //rRef:ITexture
        public string FoliageProfile { get; set; }     //rRef:CFoliageProfile
        public float MeshTotalHeight { get; set; }    //Float
        public float ForceTerrainBlend { get; set; }    //Float
    }
    public partial class _spline_deformed_metal_base
    {
        public float SplineLength { get; set; }    //Float
        public float SpanCount { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Translucency { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _terrain_simple
    {
        public Vec4 UVGenScaleOffset { get; set; }    //Vector4
        public string BaseColor { get; set; }    //rRef:ITexture
        public string GlobalNormal { get; set; }    //rRef:ITexture
        public string MaskFoliage { get; set; }    //rRef:ITexture
    }
    public partial class _top_down_car_proxy_depth
    {
    }
    public partial class _trail_decal
    {
        public float DepthOffset { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float Roughness { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _trail_decal_normal
    {
        public float DepthOffset { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _trail_decal_normal_color
    {
        public float DepthOffset { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float Roughness { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _transparent_liquid
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float SurfaceMetalness { get; set; }    //Float
        public Color ScatteringColorThin { get; set; }    //Color
        public Color ScatteringColorThick { get; set; }    //Color
        public Color Albedo { get; set; }    //Color
        public float IOR { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Roughness { get; set; }    //Float
        public float SpecularStrengthMultiplier { get; set; }    //Float
        public float NormalStrength { get; set; }    //Float
        public float MaskOpacity { get; set; }    //Float
        public float ThicknessMultiplier { get; set; }    //Float
        public float SubUVWidth { get; set; }    //Float
        public float SubUVHeight { get; set; }    //Float
        public float InterpolateFrames { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public Vec4 NormalTilingAndScrolling { get; set; }    //Vector4
        public string Distort { get; set; }    //rRef:ITexture
        public float DistortAmount { get; set; }    //Float
        public Vec4 DistortTilingAndScrolling { get; set; }    //Vector4
        public string Mask { get; set; }    //rRef:ITexture
        public float EnableRowAnimation { get; set; }    //Float
        public float UseOnStaticMeshes { get; set; }    //Float
    }
    public partial class _underwater_blood
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float DebugTimeOverride { get; set; }    //Float
        public float n_frames { get; set; }    //Float
        public float frame_rate { get; set; }    //Float
        public float StartDelayFrames { get; set; }    //Float
        public float SimulationAtlasFrameCountX { get; set; }    //Float
        public float SimulationAtlasFrameCountY { get; set; }    //Float
        public string SimulationAtlas { get; set; }    //rRef:ITexture
        public float SpeedExponent { get; set; }    //Float
        public Color ColorScale { get; set; }    //Color
        public Color ColorScale1 { get; set; }    //Color
        public Color ColorScale2 { get; set; }    //Color
        public Vec4 ColorGradientPositions { get; set; }    //Vector4
        public float ColorMode { get; set; }    //Float
    }
    public partial class _vehicle_destr_blendshape
    {
        public float DamageInfluence { get; set; }    //Float
        public float DamageInfluenceDebug { get; set; }    //Float
        public float Opacity { get; set; }    //Float
        public float TextureTiling { get; set; }    //Float
        public string BakedNormal { get; set; }    //rRef:ITexture
        public string ScratchMask { get; set; }    //rRef:ITexture
        public string DirtMap { get; set; }    //rRef:ITexture
        public string MultilayerMask { get; set; }     //rRef:Multilayer_Mask
        public string MultilayerSetup { get; set; }     //rRef:Multilayer_Setup
        public string GlobalNormal { get; set; }    //rRef:ITexture
        public float ScratchResistance { get; set; }    //Float
        public float DirtOpacity { get; set; }    //Float
        public Color DirtColor { get; set; }    //Color
        public Vec4 DirtMaskOffsets { get; set; }    //Vector4
        public Color CoatTintFwd { get; set; }    //Color
        public Color CoatTintSide { get; set; }    //Color
        public float CoatTintFresnelBias { get; set; }    //Float
        public Color CoatSpecularColor { get; set; }    //Color
        public float CoatFresnelBias { get; set; }    //Float
        public float CoatLayerMin { get; set; }    //Float
        public float CoatLayerMax { get; set; }    //Float
        public string MaskAtlas { get; set; }    //rRef:ITexture
        public DataBuffer MaskTiles { get; set; }
        public DataBuffer Layers { get; set; }
        public float LayersStartIndex { get; set; }    //Float
        public float SurfaceTexAspectRatio { get; set; }    //Float
        public Vec4 MaskToTileScale { get; set; }    //Vector4
        public float MaskTileSize { get; set; }    //Float
        public Vec4 MaskAtlasDims { get; set; }    //Vector4
        public Vec4 MaskBaseResolution { get; set; }    //Vector4
        public float SetupLayerMask { get; set; }    //Float
    }
    public partial class _vehicle_glass
    {
        public float UvTilingX { get; set; }    //Float
        public float UvTilingY { get; set; }    //Float
        public float UvOffsetX { get; set; }    //Float
        public float UvOffsetY { get; set; }    //Float
        public float DamageInfluence { get; set; }    //Float
        public float DamageInfluenceDebug { get; set; }    //Float
        public float Opacity { get; set; }    //Float
        public float OpacityBackFace { get; set; }    //Float
        public string GlassTint { get; set; }    //rRef:ITexture
        public Color TintColor { get; set; }    //Color
        public Color TintSurface { get; set; }    //Color
        public float FrontFacesReflectionPower { get; set; }    //Float
        public float BackFacesReflectionPower { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public Color GlassSpecularColor { get; set; }    //Color
        public float NormalStrength { get; set; }    //Float
        public string MaskTexture { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public float SurfaceMetalness { get; set; }    //Float
        public float MaskOpacity { get; set; }    //Float
        public float MaskRoughnessBias { get; set; }    //Float
        public float UseDamageGrid { get; set; }    //Float
        public float UseShatterPoints { get; set; }    //Float
        public Color ShatterColor { get; set; }    //Color
        public string ShatterTexture { get; set; }    //rRef:ITexture
        public string ShatterNormal { get; set; }    //rRef:ITexture
        public float ShatterNormalStrength { get; set; }    //Float
        public float ShatterRadiusScale { get; set; }    //Float
        public float ShatterAspectRatio { get; set; }    //Float
        public float ShatterCutout { get; set; }    //Float
        public float DamageGridCutout { get; set; }    //Float
        public Vec4 DebugShatterPoint0 { get; set; }    //Vector4
        public string Cracks { get; set; }    //rRef:ITexture
        public float CracksTiling { get; set; }    //Float
        public string DotsNormalTxt { get; set; }    //rRef:ITexture
        public string DotsTxt { get; set; }    //rRef:ITexture
        public string FlowTxt { get; set; }    //rRef:ITexture
        public string WiperMask { get; set; }    //rRef:ITexture
    }
    public partial class _vehicle_glass_proxy
    {
        public float UvTilingX { get; set; }    //Float
        public float UvTilingY { get; set; }    //Float
        public float UvOffsetX { get; set; }    //Float
        public float UvOffsetY { get; set; }    //Float
        public string GlassTint { get; set; }    //rRef:ITexture
        public Color TintColor { get; set; }    //Color
        public float FrontFacesReflectionPower { get; set; }    //Float
        public Color GlassSpecularColor { get; set; }    //Color
    }
    public partial class _vehicle_lights
    {
        public float UvTilingX { get; set; }    //Float
        public float UvTilingY { get; set; }    //Float
        public float UvOffsetX { get; set; }    //Float
        public float UvOffsetY { get; set; }    //Float
        public float DamageInfluence { get; set; }    //Float
        public float DamageInfluenceDebug { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public float AlphaThreshold { get; set; }    //Float
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public string Emissive { get; set; }    //rRef:ITexture
        public float EmissionTiling { get; set; }    //Float
        public float EmissionParallax { get; set; }    //Float
        public float Zone0EmissiveEV { get; set; }    //Float
        public float Zone1EmissiveEV { get; set; }    //Float
        public float Zone2EmissiveEV { get; set; }    //Float
        public float Zone3EmissiveEV { get; set; }    //Float
        public Vec4 DebugLightsIntensity { get; set; }    //Vector4
        public Color DebugLightsColor0 { get; set; }    //Color
        public Color DebugLightsColor1 { get; set; }    //Color
        public Color DebugLightsColor2 { get; set; }    //Color
        public Color DebugLightsColor3 { get; set; }    //Color
    }
    public partial class _vehicle_mesh_decal
    {
        public float DamageInfluence { get; set; }    //Float
        public float DamageInfluenceDebug { get; set; }    //Float
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float DiffuseAlpha { get; set; }    //Float
        public string MaskTexture { get; set; }    //rRef:ITexture
        public string GradientMap { get; set; }    //rRef:ITexture
        public float UseGradientMap { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalAlpha { get; set; }    //Float
        public float NormalsBlendingMode { get; set; }    //Float
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float DepthThreshold { get; set; }    //Float
        public string DirtMap { get; set; }    //rRef:ITexture
        public float DirtOpacity { get; set; }    //Float
        public Vec4 DirtMaskOffsets { get; set; }    //Vector4
    }
    public partial class _ver_mov
    {
        public float IsControlledByDestruction { get; set; }    //Float
        public string vertex_paint_tex { get; set; }    //rRef:ITexture
        public float trans_min { get; set; }    //Float
        public float trans_max { get; set; }    //Float
        public float rot_min { get; set; }    //Float
        public float rot_max { get; set; }    //Float
        public float n_frames { get; set; }    //Float
        public float n_pieces { get; set; }    //Float
        public float play_time { get; set; }    //Float
        public float debug_familys { get; set; }    //Float
        public float frame_rate { get; set; }    //Float
        public float YAxisUp { get; set; }    //Float
        public float z_min { get; set; }    //Float
        public float ground_offset { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Roughness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Metalness { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _ver_mov_glass
    {
        public float Opacity { get; set; }    //Float
        public float OpacityBackFace { get; set; }    //Float
        public float UvTilingX { get; set; }    //Float
        public float UvTilingY { get; set; }    //Float
        public float UvOffsetX { get; set; }    //Float
        public float UvOffsetY { get; set; }    //Float
        public Vec4 RoughnessTileAndOffset { get; set; }    //Vector4
        public Vec4 NormalTileAndOffset { get; set; }    //Vector4
        public Vec4 GlassTintTileAndOffset { get; set; }    //Vector4
        public string vertex_paint_tex { get; set; }    //rRef:ITexture
        public float IsControlledByDestruction { get; set; }    //Float
        public float trans_min { get; set; }    //Float
        public float trans_max { get; set; }    //Float
        public float rot_min { get; set; }    //Float
        public float rot_max { get; set; }    //Float
        public float n_frames { get; set; }    //Float
        public float n_pieces { get; set; }    //Float
        public float play_time { get; set; }    //Float
        public float debug_familys { get; set; }    //Float
        public float frame_rate { get; set; }    //Float
        public float YAxisUp { get; set; }    //Float
        public float z_min { get; set; }    //Float
        public float ground_offset { get; set; }    //Float
        public string GlassTint { get; set; }    //rRef:ITexture
        public Color TintColor { get; set; }    //Color
        public float TintFromVertexPaint { get; set; }    //Float
        public float FrontFacesReflectionPower { get; set; }    //Float
        public float BackFacesReflectionPower { get; set; }    //Float
        public float IOR { get; set; }    //Float
        public float RefractionDepth { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public Color GlassSpecularColor { get; set; }    //Color
        public float NormalStrength { get; set; }    //Float
        public float NormalMapAffectsSpecular { get; set; }    //Float
        public string MaskTexture { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public float SurfaceMetalness { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float MaskOpacity { get; set; }    //Float
        public float GlassRoughnessBias { get; set; }    //Float
        public float MaskRoughnessBias { get; set; }    //Float
        public float BlurRadius { get; set; }    //Float
        public float BlurByRoughness { get; set; }    //Float
    }
    public partial class _ver_mov_multilayered
    {
        public string vertex_paint_tex { get; set; }    //rRef:ITexture
        public float IsControlledByDestruction { get; set; }    //Float
        public float trans_min { get; set; }    //Float
        public float trans_max { get; set; }    //Float
        public float rot_min { get; set; }    //Float
        public float rot_max { get; set; }    //Float
        public float n_frames { get; set; }    //Float
        public float n_pieces { get; set; }    //Float
        public float play_time { get; set; }    //Float
        public float frame_rate { get; set; }    //Float
        public float z_min { get; set; }    //Float
        public float ground_offset { get; set; }    //Float
        public string GlobalNormal { get; set; }    //rRef:ITexture
        public string MultilayerMask { get; set; }     //rRef:Multilayer_Mask
        public string MultilayerSetup { get; set; }     //rRef:Multilayer_Setup
        public string MaskAtlas { get; set; }    //rRef:ITexture
        public DataBuffer MaskTiles { get; set; }
        public DataBuffer Layers { get; set; }
        public float LayersStartIndex { get; set; }    //Float
        public float SurfaceTexAspectRatio { get; set; }    //Float
        public Vec4 MaskToTileScale { get; set; }    //Vector4
        public float MaskTileSize { get; set; }    //Float
        public Vec4 MaskAtlasDims { get; set; }    //Vector4
        public Vec4 MaskBaseResolution { get; set; }    //Vector4
        public float SetupLayerMask { get; set; }    //Float
    }
    public partial class _ver_skinned_mov
    {
        public string vertex_paint_tex { get; set; }    //rRef:ITexture
        public string vertex_paint_tex_z { get; set; }    //rRef:ITexture
        public float trans_min { get; set; }    //Float
        public float trans_max { get; set; }    //Float
        public float rot_min { get; set; }    //Float
        public float rot_max { get; set; }    //Float
        public float buffer_offset { get; set; }    //Float
        public float n_frames { get; set; }    //Float
        public float n_pieces { get; set; }    //Float
        public float play_time { get; set; }    //Float
        public float debug_familys { get; set; }    //Float
        public float frame_rate { get; set; }    //Float
        public float YAxisUp { get; set; }    //Float
        public float z_multiply { get; set; }    //Float
        public float ground_offset { get; set; }    //Float
        public Vec4 bounds_and_pivot { get; set; }    //Vector4
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public string FoliageProfileMap { get; set; }    //rRef:ITexture
        public string FoliageProfile { get; set; }     //rRef:CFoliageProfile
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _ver_skinned_mov_parade
    {
        public string vertex_paint_tex { get; set; }    //rRef:ITexture
        public float trans_min { get; set; }    //Float
        public float trans_max { get; set; }    //Float
        public float rot_min { get; set; }    //Float
        public float rot_max { get; set; }    //Float
        public float n_frames { get; set; }    //Float
        public float n_pieces { get; set; }    //Float
        public float frame_rate { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _window_interior_uv
    {
        public string Glass { get; set; }    //rRef:ITexture
        public float LightIntensity { get; set; }    //Float
        public Color LightColor { get; set; }    //Color
        public Color GlassColor { get; set; }    //Color
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalScale { get; set; }    //Float
        public float RoomHeight { get; set; }    //Float
        public float RoomWidth { get; set; }    //Float
        public Vec4 TextureTiling { get; set; }    //Vector4
        public Color CeilFloorColor { get; set; }    //Color
        public Color WallColor { get; set; }    //Color
        public string Ceiling { get; set; }    //rRef:ITexture
        public string WallsXY { get; set; }    //rRef:ITexture
        public string WallsZY { get; set; }    //rRef:ITexture
        public string Floor { get; set; }    //rRef:ITexture
    }
    public partial class _window_parallax_interior
    {
        public string RoomAtlas { get; set; }    //rRef:ITexture
        public string LayerAtlas { get; set; }    //rRef:ITexture
        public string Curtain { get; set; }    //rRef:ITexture
        public string ColorOverlayTexture { get; set; }    //rRef:ITexture
        public Vec4 AtlasGridUvRatio { get; set; }    //Vector4
        public float AtlasDepth { get; set; }    //Float
        public float roomWidth { get; set; }    //Float
        public float roomHeight { get; set; }    //Float
        public float roomDepth { get; set; }    //Float
        public float positionXoffset { get; set; }    //Float
        public float positionYoffset { get; set; }    //Float
        public float scaleXrandomization { get; set; }    //Float
        public float positionXrandomization { get; set; }    //Float
        public float LayerDepth { get; set; }    //Float
        public float CurtainDepth { get; set; }    //Float
        public float CurtainMaxCover { get; set; }    //Float
        public float CurtainCoverRandomize { get; set; }    //Float
        public float CurtainAlpha { get; set; }    //Float
        public float LightsTempVariationAtNight { get; set; }    //Float
        public float AmountTurnOffAtNight { get; set; }    //Float
        public string WindowTexture { get; set; }    //rRef:ITexture
        public Color TintColorAtNight { get; set; }    //Color
        public string Roughness { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _window_parallax_interior_proxy
    {
        public string RoomAtlas { get; set; }    //rRef:ITexture
        public string Curtain { get; set; }    //rRef:ITexture
        public string ColorOverlayTexture { get; set; }    //rRef:ITexture
        public Vec4 AtlasGridUvRatio { get; set; }    //Vector4
        public float AtlasDepth { get; set; }    //Float
        public float roomWidth { get; set; }    //Float
        public float roomHeight { get; set; }    //Float
        public float roomDepth { get; set; }    //Float
        public float positionXoffset { get; set; }    //Float
        public float positionYoffset { get; set; }    //Float
        public float scaleXrandomization { get; set; }    //Float
        public float positionXrandomization { get; set; }    //Float
        public float LightsTempVariationAtNight { get; set; }    //Float
        public float CurtainDepth { get; set; }    //Float
        public float CurtainMaxCover { get; set; }    //Float
        public float CurtainCoverRandomize { get; set; }    //Float
        public float CurtainAlpha { get; set; }    //Float
        public float AmountTurnOffAtNight { get; set; }    //Float
        public Color TintColorAtNight { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
    }
    public partial class _window_parallax_interior_proxy_buffer
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Translucency { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _window_very_long_distance
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public string Mask { get; set; }    //rRef:ITexture
        public string ColorOverlayTexture { get; set; }    //rRef:ITexture
        public string WorldHeightMap { get; set; }    //rRef:ITexture
        public string WorldColorMap { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float WindowsSize { get; set; }    //Float
        public float Saturation { get; set; }    //Float
        public float TurnedOff { get; set; }    //Float
        public float FadeStart { get; set; }    //Float
        public float FadeEnd { get; set; }    //Float
        public float LightsFadeStart { get; set; }    //Float
        public float LightsFadeEnd { get; set; }    //Float
        public float LightsIntensityMultiplier { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
    }
    public partial class _worldspace_grid
    {
        public float GridScale { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public float EnableWorldSpace { get; set; }    //Float
        public float AbsoluteWorldSpace { get; set; }    //Float
    }
    public partial class _bink_simple
    {
        public Color ColorScale { get; set; }    //Color
        public string VideoCanvasName { get; set; }     //CName
        public string BinkY { get; set; }    //rRef:ITexture
        public string BinkCR { get; set; }    //rRef:ITexture
        public string BinkCB { get; set; }    //rRef:ITexture
        public string BinkA { get; set; }    //rRef:ITexture
        public DataBuffer BinkParams { get; set; }
    }
    public partial class _cable_strip
    {
        public float CableWidth { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Translucency { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _debugdraw_bias
    {
    }
    public partial class _debugdraw_wireframe
    {
    }
    public partial class _debugdraw_wireframe_bias
    {
    }
    public partial class _debug_coloring
    {
    }
    public partial class _font
    {
    }
    public partial class _global_water_patch
    {
        public string WaterFFT { get; set; }    //rRef:ITexture
        public string WaterMap { get; set; }    //rRef:ITexture
        public float WaterMapWeight { get; set; }    //Float
        public float WaterSize { get; set; }    //Float
        public float ShoreThreshold { get; set; }    //Float
        public float ShoreOffset { get; set; }    //Float
        public Vec4 Choppiness { get; set; }    //Vector4
        public float ScatteringDepth { get; set; }    //Float
        public float NormalDetailScale { get; set; }    //Float
        public float NormalDetailIntensity { get; set; }    //Float
        public float ScatteringSunRadius { get; set; }    //Float
        public float ScatteringSunIntensity { get; set; }    //Float
        public Color ScatteringColor { get; set; }    //Color
        public float BlurRadius { get; set; }    //Float
        public float ScatteringSlopeThreshold { get; set; }    //Float
        public float ScatteringSlopeIntensity { get; set; }    //Float
        public float WaterOpacity { get; set; }    //Float
        public float IndexOfRefraction { get; set; }    //Float
        public float RefractionNormalIntensity { get; set; }    //Float
        public float BlurStrength { get; set; }    //Float
        public string FoamTexture { get; set; }    //rRef:ITexture
        public Color FoamColor { get; set; }    //Color
        public float FoamSize { get; set; }    //Float
        public float FoamThreshold { get; set; }    //Float
        public float FoamIntensity { get; set; }    //Float
        public float EdgeBlend { get; set; }    //Float
    }
    public partial class _metal_base_animated_uv
    {
        public float UvPanningSpeedX { get; set; }    //Float
        public float UvPanningSpeedY { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveLift { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _metal_base_blendable
    {
        public string VectorField { get; set; }    //rRef:ITexture
        public float FadeOutDistance { get; set; }    //Float
        public float FadeOutOffset { get; set; }    //Float
        public float GlitchChance { get; set; }    //Float
        public float GlitchOffset { get; set; }    //Float
        public Color FresnelColor { get; set; }    //Color
        public float FresnelColorIntensity { get; set; }    //Float
        public float FresnelExponent { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveLift { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _metal_base_fence
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _metal_base_garment
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _metal_base_packed
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string RoughMetal { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _metal_base_proxy
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public string WorldColorMap { get; set; }    //rRef:ITexture
        public string WorldHeightMap { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
        public float FadeStart { get; set; }    //Float
        public float FadeEnd { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveLift { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float LayerTile { get; set; }    //Float
    }
    public partial class _multilayered
    {
        public string GlobalNormal { get; set; }    //rRef:ITexture
        public string MultilayerMask { get; set; }     //rRef:Multilayer_Mask
        public string MultilayerSetup { get; set; }     //rRef:Multilayer_Setup
        public float GlobalNormalIntensity { get; set; }    //Float
        public Vec4 GlobalNormalUVScale { get; set; }    //Vector4
        public Vec4 GlobalNormalUVBias { get; set; }    //Vector4
        public string MaskAtlas { get; set; }    //rRef:ITexture
        public DataBuffer MaskTiles { get; set; }
        public DataBuffer Layers { get; set; }
        public float LayersStartIndex { get; set; }    //Float
        public float SurfaceTexAspectRatio { get; set; }    //Float
        public Vec4 MaskToTileScale { get; set; }    //Vector4
        public float MaskTileSize { get; set; }    //Float
        public Vec4 MaskAtlasDims { get; set; }    //Vector4
        public Vec4 MaskBaseResolution { get; set; }    //Vector4
        public float SetupLayerMask { get; set; }    //Float
    }
    public partial class _multilayered_debug
    {
    }
    public partial class _pbr_simple
    {
        public Color Color { get; set; }    //Color
        public float Roughness { get; set; }    //Float
        public float Metalness { get; set; }    //Float
    }
    public partial class _shadows_debug
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Translucency { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _transparent_notxaa_2
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
    }
    public partial class _ui_default_element
    {
    }
    public partial class _ui_default_nine_slice_element
    {
    }
    public partial class _ui_default_tile_element
    {
    }
    public partial class _ui_effect_box_blur
    {
    }
    public partial class _ui_effect_color_correction
    {
    }
    public partial class _ui_effect_color_fill
    {
    }
    public partial class _ui_effect_glitch
    {
    }
    public partial class _ui_effect_inner_glow
    {
    }
    public partial class _ui_effect_light_sweep
    {
    }
    public partial class _ui_effect_linear_wipe
    {
    }
    public partial class _ui_effect_mask
    {
    }
    public partial class _ui_effect_point_cloud
    {
    }
    public partial class _ui_effect_radial_wipe
    {
    }
    public partial class _ui_effect_swipe
    {
    }
    public partial class _ui_element_depth_texture
    {
    }
    public partial class _ui_panel
    {
        public string CameraName { get; set; }     //CName
    }
    public partial class _ui_text_element
    {
        public float hackParameterForUiBatcher { get; set; }    //Float
    }
    public partial class _alphablend_glass
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public Color Color { get; set; }    //Color
        public Vec4 TextureScaling { get; set; }    //Vector4
        public float InterlaceScale { get; set; }    //Float
        public float InterlaceIntensityLow { get; set; }    //Float
        public float InterlaceIntensityHigh { get; set; }    //Float
        public float UVdivisions { get; set; }    //Float
        public float UVoffset { get; set; }    //Float
        public float Emissive { get; set; }    //Float
    }
    public partial class _alpha_control_refraction
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string RefractionMap { get; set; }    //rRef:ITexture
        public string RecolorMap { get; set; }    //rRef:ITexture
        public float RefractionAmount { get; set; }    //Float
        public float RefractionSpeed { get; set; }    //Float
        public float JerkingSpeed { get; set; }    //Float
        public float JerkingAmount { get; set; }    //Float
        public float MaxAlpha { get; set; }    //Float
        public float RecolorAmount { get; set; }    //Float
        public float RecolorMultiplier { get; set; }    //Float
        public Color SpecularColor { get; set; }    //Color
    }
    public partial class _animated_decal
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public float DiffuseAlpha { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public float NormalAlpha { get; set; }    //Float
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public string RevealMasks { get; set; }    //rRef:ITexture
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float AnimationFramesWidth { get; set; }    //Float
        public float AnimationFramesHeight { get; set; }    //Float
        public float FloatParam { get; set; }    //Float
    }
    public partial class _beam_particles
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string MainTexture { get; set; }    //rRef:ITexture
        public string AdditionalMask { get; set; }    //rRef:ITexture
        public float UseMaskROrA { get; set; }    //Float
        public string AdditionalMaskFlowmap { get; set; }    //rRef:ITexture
        public Color MainColor { get; set; }    //Color
        public float ColorMultiplier { get; set; }    //Float
        public float TextureScale { get; set; }    //Float
        public float TextureStretch { get; set; }    //Float
        public float TextureHasNoAlpha { get; set; }    //Float
        public float BlackbodyOrColor { get; set; }    //Float
        public Vec4 FlowmapControl { get; set; }    //Vector4
        public Vec4 AdditionalMaskControl { get; set; }    //Vector4
        public float FlowmapMultiplier { get; set; }    //Float
        public float TextureHasAlpha { get; set; }    //Float
    }
    public partial class _blackbodyradiation
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float Temperature { get; set; }    //Float
        public float subUVWidth { get; set; }    //Float
        public float AlphaExponent { get; set; }    //Float
        public float subUVHeight { get; set; }    //Float
        public float ScatterAmount { get; set; }    //Float
        public float ScatterPower { get; set; }    //Float
        public string FireScatterAlpha { get; set; }    //rRef:ITexture
        public float HueShift { get; set; }    //Float
        public float HueSpread { get; set; }    //Float
        public float maxAlpha { get; set; }    //Float
        public Color LightSmoke { get; set; }    //Color
        public Color DarkSmoke { get; set; }    //Color
        public float ExpensiveBlending { get; set; }    //Float
        public float Saturation { get; set; }    //Float
        public float SoftAlpha { get; set; }    //Float
        public float MultiplierExponent { get; set; }    //Float
        public Vec4 TexCoordDtortScale { get; set; }    //Vector4
        public Vec4 TexCoordDtortSpeed { get; set; }    //Vector4
        public string Distort { get; set; }    //rRef:ITexture
        public float NoAlphaOnTexture { get; set; }    //Float
        public float EatUpOrStraightAlpha { get; set; }    //Float
        public float DistortAmount { get; set; }    //Float
        public float EnableRowAnimation { get; set; }    //Float
        public float DoNotApplyLighting { get; set; }    //Float
        public string MaskTexture { get; set; }    //rRef:ITexture
        public float InvertMask { get; set; }    //Float
        public Vec4 MaskTilingAndSpeed { get; set; }    //Vector4
        public float MaskIntensity { get; set; }    //Float
        public float UseVertexAlpha { get; set; }    //Float
        public float DotWithLookAt { get; set; }    //Float
    }
    public partial class _blackbody_simple
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string TemperatureTexture { get; set; }    //rRef:ITexture
        public float Temperature { get; set; }    //Float
        public float SubUVWidth { get; set; }    //Float
        public float SubUVHeight { get; set; }    //Float
        public float SoftAlpha { get; set; }    //Float
    }
    public partial class _blood_transparent
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color ColorThin { get; set; }    //Color
        public Color ColorThick { get; set; }    //Color
        public float BloodThickness { get; set; }    //Float
        public float LightingBleeding { get; set; }    //Float
        public float SpecularPower { get; set; }    //Float
        public float SpecularMultiplier { get; set; }    //Float
        public float SubUVWidth { get; set; }    //Float
        public float SubUVHeight { get; set; }    //Float
        public float CurrentFrame { get; set; }    //Float
        public string NormalAndDensity { get; set; }    //rRef:ITexture
        public string VelocityMap { get; set; }    //rRef:ITexture
        public string SpecularMap { get; set; }    //rRef:ITexture
        public float FlowmapStrength { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float NormalPow { get; set; }    //Float
        public float EVCompensation { get; set; }    //Float
    }
    public partial class _braindance_fog
    {
        public float BrightnessNear { get; set; }    //Float
        public float BrightnessFar { get; set; }    //Float
        public string RevealMask { get; set; }    //rRef:ITexture
        public float RevealMaskFramesY { get; set; }    //Float
        public Vec4 RevealMaskBoundsMin { get; set; }    //Vector4
        public Vec4 RevealMaskBoundsMax { get; set; }    //Vector4
        public float TonemapExposure { get; set; }    //Float
        public float FarFogBrightness { get; set; }    //Float
        public float FarFogDistance { get; set; }    //Float
        public float UseHack_SQ021 { get; set; }    //Float
        public string CluesMap { get; set; }    //rRef:ITexture
        public float CluesBrightness { get; set; }    //Float
        public float UseClueDepthClipping { get; set; }    //Float
        public string VectorField { get; set; }    //rRef:ITexture
        public float VectorFieldSliceCount { get; set; }    //Float
        public float VectorFieldTiling { get; set; }    //Float
        public float VectorFieldAnimSpeed { get; set; }    //Float
        public float VectorFieldStrength { get; set; }    //Float
    }
    public partial class _braindance_particle_thermal
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color Color { get; set; }    //Color
        public float Brightness { get; set; }    //Float
        public string FireScatterAlpha { get; set; }    //rRef:ITexture
        public float subUVWidth { get; set; }    //Float
        public float subUVHeight { get; set; }    //Float
        public float AlphaExponent { get; set; }    //Float
        public float maxAlpha { get; set; }    //Float
        public float EatUpOrStraightAlpha { get; set; }    //Float
        public float SoftAlpha { get; set; }    //Float
        public float UseVertexAlpha { get; set; }    //Float
    }
    public partial class _cloak
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Distortion { get; set; }    //rRef:ITexture
        public Vec4 DistortionUVScale { get; set; }    //Vector4
        public float DistortionVisibility { get; set; }    //Float
        public string IridescenceMask { get; set; }    //rRef:ITexture
        public float IridescenceSpeed { get; set; }    //Float
        public float IridescenceDim { get; set; }    //Float
        public Color Tinge { get; set; }    //Color
        public string DirtMask { get; set; }    //rRef:ITexture
        public Vec4 DirtMaskScaleAndOffset { get; set; }    //Vector4
        public float DirtMaskPower { get; set; }    //Float
        public float DirtMaskMultiplier { get; set; }    //Float
        public Color DirtColor { get; set; }    //Color
        public float UseOutline { get; set; }    //Float
        public float OutlineOpacity { get; set; }    //Float
        public float OutlineSize { get; set; }    //Float
    }
    public partial class _cyberspace_pixelsort_stencil
    {
        public float CameraOffsetZ { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
    }
    public partial class _cyberspace_pixelsort_stencil_0
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
    }
    public partial class _cyberware_animation
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string EmissiveMask { get; set; }    //rRef:ITexture
        public float UseTimeOrFloatParam { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
    }
    public partial class _damage_indicator
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Mask { get; set; }    //rRef:ITexture
        public string Noise { get; set; }    //rRef:ITexture
        public float DoubleDistortWithNoise { get; set; }    //Float
        public string Scanline { get; set; }    //rRef:ITexture
        public Vec4 NoiseScailingAndSpeed { get; set; }    //Vector4
        public float MinMaskExponent { get; set; }    //Float
        public float MaxMaskExponent { get; set; }    //Float
        public float MaskMultiplier { get; set; }    //Float
        public Color ThickScanlinesColor { get; set; }    //Color
        public Color ThinScanlinesColor { get; set; }    //Color
        public float ScanlineDensity { get; set; }    //Float
        public float ScanlineMinimumValue { get; set; }    //Float
        public float ThickScanlineMultiplier { get; set; }    //Float
        public float ThinScanlineExponent { get; set; }    //Float
        public float ThinScanlineMultiplier { get; set; }    //Float
        public float RefractionOffsetStrength { get; set; }    //Float
    }
    public partial class _device_diode
    {
        public float NormalOffset { get; set; }    //Float
        public float VehicleDamageInfluence { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string Emissive { get; set; }    //rRef:ITexture
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float Blinking { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float BlinkingSpeed { get; set; }    //Float
        public float UseMaterialParameter { get; set; }    //Float
        public Color EmissiveColor1 { get; set; }    //Color
        public Color EmissiveColor2 { get; set; }    //Color
        public float EmissiveInitialState { get; set; }    //Float
        public float UseTwoEmissiveColors { get; set; }    //Float
        public float SwitchingTwoEmissiveColorsSpeed { get; set; }    //Float
        public float UseFresnel { get; set; }    //Float
    }
    public partial class _device_diode_multi_state
    {
        public float NormalOffset { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string Emissive { get; set; }    //rRef:ITexture
        public Color EmissiveColor1 { get; set; }    //Color
        public Color EmissiveColor2 { get; set; }    //Color
        public Color EmissiveColor3 { get; set; }    //Color
        public Color EmissiveColor4 { get; set; }    //Color
        public float EmissiveColorSelector { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float Blinking { get; set; }    //Float
        public float BlinkingSpeed { get; set; }    //Float
        public float UseMaterialParameter { get; set; }    //Float
        public float EmissiveInitialState { get; set; }    //Float
    }
    public partial class _diode_pavements
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public float Metalness { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public string DiodesMask { get; set; }    //rRef:ITexture
        public string SignTexture { get; set; }    //rRef:ITexture
        public Vec4 DiodesTilingAndScrollSpeed { get; set; }    //Vector4
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float UseMaskAsAlphaThreshold { get; set; }    //Float
        public float AmountOfGlitch { get; set; }    //Float
        public float GlitchSpeed { get; set; }    //Float
        public float NumberOfRows { get; set; }    //Float
        public float DisplayRow { get; set; }    //Float
        public Vec4 BaseColorRoughnessTiling { get; set; }    //Vector4
    }
    public partial class _drugged_sobel
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color DarkColor { get; set; }    //Color
        public Color BrightColor { get; set; }    //Color
        public float DarkColorPower { get; set; }    //Float
        public float KernelOffset { get; set; }    //Float
        public float UseInEngineSobel { get; set; }    //Float
    }
    public partial class _emissive_basic_transparent
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public string Mask { get; set; }    //rRef:ITexture
        public string AnimMask { get; set; }    //rRef:ITexture
        public Color EmissiveColor { get; set; }    //Color
    }
    public partial class _fog_laser
    {
        public float AdditionalThicnkess { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float TimeScale { get; set; }    //Float
        public string NoiseTexture { get; set; }    //rRef:ITexture
        public float DetailNoiseScale { get; set; }    //Float
        public float DetailNoiseBrighten { get; set; }    //Float
        public float GeneralNoiseScale { get; set; }    //Float
        public Color LaserColor { get; set; }    //Color
        public float SmokeExponent { get; set; }    //Float
        public float SmokeMultiplier { get; set; }    //Float
        public float LineThreshold { get; set; }    //Float
        public float LineMultiplier { get; set; }    //Float
        public float LineAddOrSubtract { get; set; }    //Float
        public float UseSoftAlpha { get; set; }    //Float
        public float SoftAlpha { get; set; }    //Float
        public float SoftAlphaMultiplier { get; set; }    //Float
        public float HorizontalGradientMultiplier { get; set; }    //Float
        public float FlipEdgeFade { get; set; }    //Float
        public float UseVertexColor { get; set; }    //Float
        public float TextureRatioU { get; set; }    //Float
        public float TextureRatioV { get; set; }    //Float
        public float IntensiveCore { get; set; }    //Float
        public float RotateUV { get; set; }    //Float
        public string VectorField { get; set; }    //rRef:ITexture
        public float VectorFieldSliceCount { get; set; }    //Float
        public float UseWorldSpace { get; set; }    //Float
    }
    public partial class _hologram
    {
        public Vec4 ScaleReferencePosAndScale { get; set; }    //Vector4
        public float GlitchChance { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float OpaqueScanlineDensity { get; set; }    //Float
        public string Scanline { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public string DotsTexture { get; set; }    //rRef:ITexture
        public float DotsSize { get; set; }    //Float
        public Color DotsColor { get; set; }    //Color
        public Vec4 Projector1Position { get; set; }    //Vector4
        public Color SurfaceColor { get; set; }    //Color
        public Color SurfaceShadows { get; set; }    //Color
        public Color FallofColor { get; set; }    //Color
        public string Diffuse { get; set; }    //rRef:ITexture
        public float GradientOffset { get; set; }    //Float
        public float GradientLength { get; set; }    //Float
        public float FresnelStrength { get; set; }    //Float
        public float DotsFresnelStrength { get; set; }    //Float
        public float GlowStrength { get; set; }    //Float
        public float DesaturationStrength { get; set; }    //Float
        public float FlickerThreshold { get; set; }    //Float
        public float FlickerChance { get; set; }    //Float
        public float ArtifactsChance { get; set; }    //Float
        public float LightBleed { get; set; }    //Float
        public float NormalStrength { get; set; }    //Float
        public float ScreenSpaceFlicker { get; set; }    //Float
        public float UseIsobars { get; set; }    //Float
        public float EntropyThreshold { get; set; }    //Float
        public float UseMovingDots { get; set; }    //Float
        public float IsHair { get; set; }    //Float
        public float ScanlineThickness { get; set; }    //Float
        public float Opacity { get; set; }    //Float
        public float GlobalTint { get; set; }    //Float
        public float SampledOrProceduralDots { get; set; }    //Float
        public float FullColorOrGrayscale { get; set; }    //Float
    }
    public partial class _hologram_two_sided
    {
        public Vec4 ScaleReferencePosAndScale { get; set; }    //Vector4
        public float GlitchChance { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string Diffuse { get; set; }    //rRef:ITexture
        public string Scanline { get; set; }    //rRef:ITexture
        public string DotsTexture { get; set; }    //rRef:ITexture
        public Vec4 Projector1Position { get; set; }    //Vector4
        public float OpaqueScanlineDensity { get; set; }    //Float
        public float DotsSize { get; set; }    //Float
        public Color DotsColor { get; set; }    //Color
        public Color SurfaceColor { get; set; }    //Color
        public Color SurfaceShadows { get; set; }    //Color
        public Color FallofColor { get; set; }    //Color
        public float GradientOffset { get; set; }    //Float
        public float GradientLength { get; set; }    //Float
        public float FresnelStrength { get; set; }    //Float
        public float DotsFresnelStrength { get; set; }    //Float
        public float GlowStrength { get; set; }    //Float
        public float DesaturationStrength { get; set; }    //Float
        public float FlickerThreshold { get; set; }    //Float
        public float FlickerChance { get; set; }    //Float
        public float ArtifactsChance { get; set; }    //Float
        public float LightBleed { get; set; }    //Float
        public float NormalStrength { get; set; }    //Float
        public float ScreenSpaceFlicker { get; set; }    //Float
        public float UseIsobars { get; set; }    //Float
        public float EntropyThreshold { get; set; }    //Float
        public float UseMovingDots { get; set; }    //Float
        public float IsHair { get; set; }    //Float
        public float ScanlineThickness { get; set; }    //Float
        public float Opacity { get; set; }    //Float
        public float GlobalTint { get; set; }    //Float
        public float SampledOrProceduralDots { get; set; }    //Float
        public float FullColorOrGrayscale { get; set; }    //Float
    }
    public partial class _holo_projections
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float ColorMultiply { get; set; }    //Float
        public Color EmissiveColor { get; set; }    //Color
        public float BrightnessNoiseStreght { get; set; }    //Float
        public float SubUVWidth { get; set; }    //Float
        public float SubUVHeight { get; set; }    //Float
        public float FrameNum { get; set; }    //Float
        public float PlaySpeed { get; set; }    //Float
        public float InvertSoftAlpha { get; set; }    //Float
        public Vec4 UVScrollSpeed { get; set; }    //Vector4
        public float ScrollStepFactor { get; set; }    //Float
        public float ScrollMaskOrTexture { get; set; }    //Float
        public float RandomAnimation { get; set; }    //Float
        public float RandomFrameFrequency { get; set; }    //Float
        public float RandomFrameChangeSpeed { get; set; }    //Float
        public float FrameNumDisplayChance { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public string ScrollingMaskTexture { get; set; }    //rRef:ITexture
    }
    public partial class _hud_focus_mode_scanline
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float Progress { get; set; }    //Float
        public float vProgress { get; set; }    //Float
        public float ScanlineDensity { get; set; }    //Float
        public float ScanlineOffset { get; set; }    //Float
        public float ScanlineWidth { get; set; }    //Float
        public float EffectIntensity { get; set; }    //Float
        public float ScanlineDensityVertical { get; set; }    //Float
        public float ScanlineOffsetVertical { get; set; }    //Float
        public float ScanlineWidthVertical { get; set; }    //Float
        public float VerticalIntensity { get; set; }    //Float
        public float BarsWidth { get; set; }    //Float
        public float SideFadeWidth { get; set; }    //Float
        public float SideFadeFeather { get; set; }    //Float
    }
    public partial class _hud_markers_notxaa
    {
        public string Diffuse { get; set; }    //rRef:ITexture
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color Color { get; set; }    //Color
        public Color Second_Color { get; set; }    //Color
        public float ColorMultiplier { get; set; }    //Float
        public float ClampOrWrap { get; set; }    //Float
        public float TillingX { get; set; }    //Float
        public float TillingY { get; set; }    //Float
        public float OffsetX { get; set; }    //Float
        public float OffsetY { get; set; }    //Float
        public float WipeValue { get; set; }    //Float
        public float RotateUV90Deg { get; set; }    //Float
        public float SoftAlpha { get; set; }    //Float
        public float InverseSoftAlphaValue { get; set; }    //Float
        public float UseOnMeshes { get; set; }    //Float
        public float UseWorldSpaceNoise { get; set; }    //Float
        public string WorldSpaceNoise { get; set; }    //rRef:ITexture
        public float WorldSpaceNoiseTilling { get; set; }    //Float
        public float NoiseSpeed { get; set; }    //Float
        public float FresnelPower { get; set; }    //Float
        public float FresnelContrast { get; set; }    //Float
        public float SecondSoftAlpha { get; set; }    //Float
    }
    public partial class _hud_markers_transparent
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public Color Color { get; set; }    //Color
        public Color Second_Color { get; set; }    //Color
        public float ColorMultiplier { get; set; }    //Float
        public float ClampOrWrap { get; set; }    //Float
        public float TillingX { get; set; }    //Float
        public float TillingY { get; set; }    //Float
        public float OffsetX { get; set; }    //Float
        public float OffsetY { get; set; }    //Float
        public float RotateUV90Deg { get; set; }    //Float
        public float WipeValue { get; set; }    //Float
        public float SoftAlpha { get; set; }    //Float
        public float InverseSoftAlphaValue { get; set; }    //Float
        public float UseOnMeshes { get; set; }    //Float
        public float UseWorldSpaceNoise { get; set; }    //Float
        public string WorldSpaceNoise { get; set; }    //rRef:ITexture
        public float WorldSpaceNoiseTilling { get; set; }    //Float
        public float NoiseSpeed { get; set; }    //Float
        public float FresnelPower { get; set; }    //Float
        public float FresnelContrast { get; set; }    //Float
        public float SecondSoftAlpha { get; set; }    //Float
    }
    public partial class _hud_markers_vision
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public Color Color { get; set; }    //Color
        public Color Second_Color { get; set; }    //Color
        public float ColorMultiplier { get; set; }    //Float
        public float ClampOrWrap { get; set; }    //Float
        public float TillingX { get; set; }    //Float
        public float TillingY { get; set; }    //Float
        public float OffsetX { get; set; }    //Float
        public float OffsetY { get; set; }    //Float
        public float RotateUV90Deg { get; set; }    //Float
        public float WipeValue { get; set; }    //Float
        public float SoftAlpha { get; set; }    //Float
        public float InverseSoftAlphaValue { get; set; }    //Float
        public float UseOnMeshes { get; set; }    //Float
        public float UseWorldSpaceNoise { get; set; }    //Float
        public string WorldSpaceNoise { get; set; }    //rRef:ITexture
        public float WorldSpaceNoiseTilling { get; set; }    //Float
        public float NoiseSpeed { get; set; }    //Float
        public float FresnelPower { get; set; }    //Float
        public float FresnelContrast { get; set; }    //Float
        public float SecondSoftAlpha { get; set; }    //Float
    }
    public partial class _hud_ui_dot
    {
        public string Diffuse { get; set; }    //rRef:ITexture
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float TillingX { get; set; }    //Float
        public float TillingY { get; set; }    //Float
        public float OffsetX { get; set; }    //Float
        public float OffsetY { get; set; }    //Float
        public Color Color { get; set; }    //Color
        public float ColorMultiplier { get; set; }    //Float
    }
    public partial class _hud_vision_pass
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public Vec4 TextureTilingAndSpeed { get; set; }    //Vector4
        public Color Color { get; set; }    //Color
        public float ColorMultiplier { get; set; }    //Float
        public float AlphaMultiplier { get; set; }    //Float
        public float SoftTransparencyAmount { get; set; }    //Float
        public float SoftContrast { get; set; }    //Float
        public float UseVertexColor { get; set; }    //Float
        public float Wipe { get; set; }    //Float
        public float TestForDepth { get; set; }    //Float
    }
    public partial class _johnny_effect
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public Color Color { get; set; }    //Color
        public float Tilling { get; set; }    //Float
        public float Contrast { get; set; }    //Float
    }
    public partial class _johnny_glitch
    {
        public float Offset { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public Color Color { get; set; }    //Color
        public Color BodyColor { get; set; }    //Color
        public float Tilling { get; set; }    //Float
        public float Contrast { get; set; }    //Float
        public float LineLength { get; set; }    //Float
        public float MinDistance { get; set; }    //Float
        public float MaxDistance { get; set; }    //Float
        public float MaxSteps { get; set; }    //Float
        public float NoiseSpeed { get; set; }    //Float
        public float BackgroundOffset { get; set; }    //Float
        public float BlurredIntensity { get; set; }    //Float
        public float NoiseSize { get; set; }    //Float
        public float TileSizeX1 { get; set; }    //Float
        public float TileSizeY1 { get; set; }    //Float
        public float TileSizeX2 { get; set; }    //Float
        public float TileSizeY2 { get; set; }    //Float
        public float GlitchSpeed { get; set; }    //Float
        public float UseHorizontal { get; set; }    //Float
        public string VectorField { get; set; }    //rRef:ITexture
    }
    public partial class _metal_base_atlas_animation
    {
        public float SubUVWidth { get; set; }    //Float
        public float SubUVHeight { get; set; }    //Float
        public float LoopedAnimationSpeed { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Translucency { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _metal_base_blackbody
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public string Metalness { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public string EmissiveMask { get; set; }    //rRef:ITexture
        public string HeatDistribution { get; set; }    //rRef:ITexture
        public float MaskMinimum { get; set; }    //Float
        public float HeatTilingX { get; set; }    //Float
        public float HeatTilingY { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float MaxTemperature { get; set; }    //Float
        public Vec4 HSV_Mod { get; set; }    //Vector4
        public float DebugTemperature { get; set; }    //Float
        public float DebugOrExternalCurve { get; set; }    //Float
        public float HeatMoveSpeed { get; set; }    //Float
    }
    public partial class _metal_base_glitter
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float AlphaFromEmissive { get; set; }    //Float
        public string EmissiveMask { get; set; }    //rRef:ITexture
        public float EmissiveEV { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public Color EmissiveColor { get; set; }    //Color
        public float HistogramRange { get; set; }    //Float
        public float ScrollSpeed { get; set; }    //Float
        public float EmissiveTile { get; set; }    //Float
        public float Looped { get; set; }    //Float
    }
    public partial class _neon_tubes
    {
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EmissiveEdgeMult { get; set; }    //Float
        public Color color { get; set; }    //Color
        public string tex1 { get; set; }    //rRef:ITexture
        public float fresnelpower { get; set; }    //Float
        public float UseBlinkingNoise { get; set; }    //Float
        public float BlinkSpeed { get; set; }    //Float
        public float MinNoiseValue { get; set; }    //Float
        public float TimeSeed { get; set; }    //Float
        public float UseMatParamToCtrlNoise { get; set; }    //Float
        public float TextureU { get; set; }    //Float
        public float TextureV { get; set; }    //Float
        public float TextureIntensity { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
    }
    public partial class _noctovision_mode
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Vec4 NPC_HDRColor1 { get; set; }    //Vector4
        public Vec4 NPC_HDRColor2 { get; set; }    //Vector4
        public Vec4 Enemy_HDRColor1 { get; set; }    //Vector4
        public Vec4 Enemy_HDRColor2 { get; set; }    //Vector4
        public float Multiplier { get; set; }    //Float
        public string Distortion { get; set; }    //rRef:ITexture
        public float DistortionSpeed { get; set; }    //Float
        public float DistortionOffset { get; set; }    //Float
        public float EnemyAlphaMultiplier { get; set; }    //Float
        public Vec4 ScanlineValues { get; set; }    //Vector4
        public float ScanlineContrast { get; set; }    //Float
    }
    public partial class _parallaxscreen
    {
        public string ParalaxTexture { get; set; }    //rRef:ITexture
        public string ScanlineTexture { get; set; }    //rRef:ITexture
        public float Metalness { get; set; }    //Float
        public float Roughness { get; set; }    //Float
        public float Emissive { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float ImageScale { get; set; }    //Float
        public float LayersSeparation { get; set; }    //Float
        public Vec4 IntensityPerLayer { get; set; }    //Vector4
        public float ScanlinesDensity { get; set; }    //Float
        public float ScanlinesIntensity { get; set; }    //Float
        public float BlinkingSpeed { get; set; }    //Float
        public string BlinkingMaskTexture { get; set; }    //rRef:ITexture
        public string ScrollMaskTexture { get; set; }    //rRef:ITexture
        public float ScrollVerticalOrHorizontal { get; set; }    //Float
        public float ScrollMaskStartPoint1 { get; set; }    //Float
        public float ScrollMaskHeight1 { get; set; }    //Float
        public float ScrollSpeed1 { get; set; }    //Float
        public float ScrollStepFactor1 { get; set; }    //Float
        public float ScrollMaskStartPoint2 { get; set; }    //Float
        public float ScrollMaskHeight2 { get; set; }    //Float
        public float ScrollSpeed2 { get; set; }    //Float
        public float ScrollStepFactor2 { get; set; }    //Float
        public Color EmissiveColor { get; set; }    //Color
        public Vec4 HSV_Mod { get; set; }    //Vector4
        public float IsBroken { get; set; }    //Float
        public float FixForBlack { get; set; }    //Float
    }
    public partial class _parallaxscreen_transparent
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string ParalaxTexture { get; set; }    //rRef:ITexture
        public Vec4 TexHSVControl { get; set; }    //Vector4
        public Color Color { get; set; }    //Color
        public float Emissive { get; set; }    //Float
        public float AdditiveOrAlphaBlened { get; set; }    //Float
        public Vec4 ImageScale { get; set; }    //Vector4
        public float TextureOffsetX { get; set; }    //Float
        public float TextureOffsetY { get; set; }    //Float
        public float TilesWidth { get; set; }    //Float
        public float TilesHeight { get; set; }    //Float
        public float PlaySpeed { get; set; }    //Float
        public float InterlaceLines { get; set; }    //Float
        public float SeparateLayersFromTexture { get; set; }    //Float
        public float LayersSeparation { get; set; }    //Float
        public Vec4 IntensityPerLayer { get; set; }    //Vector4
        public float ScanlinesDensity { get; set; }    //Float
        public float ScanlinesIntensity { get; set; }    //Float
        public float ScanlinesSpeed { get; set; }    //Float
        public float NoPostORPost { get; set; }    //Float
        public float EdgesMask { get; set; }    //Float
        public float ClampUV { get; set; }    //Float
        public string ScrollMaskTexture { get; set; }    //rRef:ITexture
        public float ScrollVerticalOrHorizontal { get; set; }    //Float
        public float ScrollMaskStartPoint1 { get; set; }    //Float
        public float ScrollMaskHeight1 { get; set; }    //Float
        public float ScrollSpeed1 { get; set; }    //Float
        public float ScrollStepFactor1 { get; set; }    //Float
        public float ScrollMaskStartPoint2 { get; set; }    //Float
        public float ScrollMaskHeight2 { get; set; }    //Float
        public float ScrollSpeed2 { get; set; }    //Float
        public float ScrollStepFactor2 { get; set; }    //Float
        public Vec4 LayersScrollSpeed { get; set; }    //Vector4
    }
    public partial class _parallaxscreen_transparent_ui
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string ScanlineTexture { get; set; }    //rRef:ITexture
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float ImageScale { get; set; }    //Float
        public float LayersSeparation { get; set; }    //Float
        public Vec4 IntensityPerLayer { get; set; }    //Vector4
        public Vec4 ScanlinesDensity { get; set; }    //Vector4
        public float IsBroken { get; set; }    //Float
        public float ScanlinesIntensity { get; set; }    //Float
        public string UIRenderTexture { get; set; }    //rRef:ITexture
        public Vec4 TexturePartUV { get; set; }    //Vector4
        public float FixToPbr { get; set; }    //Float
        public Vec4 RenderTextureScale { get; set; }    //Vector4
        public float VerticalFlipEnabled { get; set; }    //Float
        public float EdgeMask { get; set; }    //Float
        public Color Tint { get; set; }    //Color
        public float FixForVerticalSlide { get; set; }    //Float
        public float AlphaAsOne { get; set; }    //Float
        public float SaturationLift { get; set; }    //Float
    }
    public partial class _parallax_bink
    {
        public Color ColorScale { get; set; }    //Color
        public string VideoCanvasName { get; set; }     //CName
        public string BinkY { get; set; }    //rRef:ITexture
        public string BinkCR { get; set; }    //rRef:ITexture
        public string BinkCB { get; set; }    //rRef:ITexture
        public string BinkA { get; set; }    //rRef:ITexture
        public DataBuffer BinkParams { get; set; }
    }
    public partial class _particles_generic_expanded
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public Color Color { get; set; }    //Color
        public float ColorMultiplier { get; set; }    //Float
        public float SubUVWidth { get; set; }    //Float
        public float SubUVHeight { get; set; }    //Float
        public float SoftUVInterpolate { get; set; }    //Float
        public float Desaturate { get; set; }    //Float
        public float ColorPower { get; set; }    //Float
        public float DistortAmount { get; set; }    //Float
        public Vec4 TexCoordScale { get; set; }    //Vector4
        public Vec4 TexCoordSpeed { get; set; }    //Vector4
        public Vec4 TexCoordDtortScale { get; set; }    //Vector4
        public Vec4 TexCoordDistortSpeed { get; set; }    //Vector4
        public float AlphaGlobal { get; set; }    //Float
        public float AlphaSoft { get; set; }    //Float
        public float AlphaFresnelPower { get; set; }    //Float
        public float UseAlphaFresnel { get; set; }    //Float
        public float UseAlphaMask { get; set; }    //Float
        public float UseOneChannel { get; set; }    //Float
        public float UseContrastAlpha { get; set; }    //Float
        public string AlphaMask { get; set; }    //rRef:ITexture
        public string Distortion { get; set; }    //rRef:ITexture
        public float UseAlphaFresnelInverted { get; set; }    //Float
        public float AlphaFresnelInvertedPower { get; set; }    //Float
        public float AlphaDistortAmount { get; set; }    //Float
        public Vec4 AlphaMaskDistortScale { get; set; }    //Vector4
        public Vec4 AlphaMaskDistortSpeed { get; set; }    //Vector4
        public float UseTimeOfDay { get; set; }    //Float
    }
    public partial class _particles_hologram
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float UseMaterialParam { get; set; }    //Float
        public Color ColorParam { get; set; }    //Color
        public float DotsCoords { get; set; }    //Float
        public float View_or_World { get; set; }    //Float
        public float ColorMultiplier { get; set; }    //Float
        public float AlphaSoft { get; set; }    //Float
        public Vec4 GlitchTexCoordSpeed { get; set; }    //Vector4
        public string Dots { get; set; }    //rRef:ITexture
        public string AlphaMask { get; set; }    //rRef:ITexture
        public string GlitchTex { get; set; }    //rRef:ITexture
        public Vec4 AlphaTexCoordSpeed { get; set; }    //Vector4
        public float AlphaSubUVWidth { get; set; }    //Float
        public float AlphaSubUVHeight { get; set; }    //Float
        public float SoftUVInterpolate { get; set; }    //Float
        public float AlphaGlobal { get; set; }    //Float
        public float UseOnMesh { get; set; }    //Float
    }
    public partial class _pointcloud_source_mesh
    {
        public Vec4 WorldPositionOffset { get; set; }    //Vector4
    }
    public partial class _postprocess
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float Gain { get; set; }    //Float
        public Color ReColor { get; set; }    //Color
        public float BlurredIntensity { get; set; }    //Float
        public float MaskContrast { get; set; }    //Float
        public float ReColorStrength { get; set; }    //Float
    }
    public partial class _postprocess_notxaa
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float Gain { get; set; }    //Float
        public Color ReColor { get; set; }    //Color
        public float BlurredIntensity { get; set; }    //Float
        public float MaskContrast { get; set; }    //Float
        public float NumberOfIterations { get; set; }    //Float
        public float UseMovingBlur { get; set; }    //Float
        public float ReColorStrength { get; set; }    //Float
    }
    public partial class _radial_blur
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string RedLinesMask { get; set; }    //rRef:ITexture
        public string BlurMask { get; set; }    //rRef:ITexture
        public float RedLinesDensity { get; set; }    //Float
        public Color RedLine1 { get; set; }    //Color
        public Color RedLine2 { get; set; }    //Color
        public Color BluringBackgroundRecolor { get; set; }    //Color
        public float AberationAmount { get; set; }    //Float
        public float BlurAmount { get; set; }    //Float
        public float LightupAmount { get; set; }    //Float
        public float MixAmount { get; set; }    //Float
        public float BlurOrAberration { get; set; }    //Float
        public float ChromaticOffsetSpeed { get; set; }    //Float
    }
    public partial class _reflex_buster
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float MaxDistortMulitiplier { get; set; }    //Float
        public float MinDistortMulitiplier { get; set; }    //Float
        public float ZoomMultiplier { get; set; }    //Float
        public float RelativeFStop { get; set; }    //Float
        public float GlobalTint { get; set; }    //Float
        public float Desaturate { get; set; }    //Float
        public Color Color { get; set; }    //Color
        public float UseAlphaOverEffect { get; set; }    //Float
    }
    public partial class _refraction
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Vec4 TexCoordDtortScaleSpeed { get; set; }    //Vector4
        public float DistortAmount { get; set; }    //Float
        public string Alpha { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public float UseVertexAlpha { get; set; }    //Float
    }
    public partial class _sandevistan_trails
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string MainTexture { get; set; }    //rRef:ITexture
        public string MainAdditiveTexture { get; set; }    //rRef:ITexture
        public float MainColorMultiplier { get; set; }    //Float
        public Color MainAdditiveColor { get; set; }    //Color
        public float MainAdditiveColorMultiplier { get; set; }    //Float
        public float SlowFactor { get; set; }    //Float
        public float MainAdditiveAlphaTimingExponent { get; set; }    //Float
        public Color MainColorStart { get; set; }    //Color
        public Color MainColorEnd { get; set; }    //Color
        public float HueSpread { get; set; }    //Float
        public float MainBlackBodyMultiplier { get; set; }    //Float
    }
    public partial class _screens
    {
        public Vec4 Tex1CoordMove { get; set; }    //Vector4
        public Vec4 Tex1Color { get; set; }    //Vector4
        public Vec4 Tex2CoordMove { get; set; }    //Vector4
        public Vec4 Tex2Color { get; set; }    //Vector4
        public Vec4 BackCoordMove { get; set; }    //Vector4
        public Vec4 BackColor { get; set; }    //Vector4
        public float Tex2AnimSpeed { get; set; }    //Float
        public string background { get; set; }    //rRef:ITexture
        public string Tex1 { get; set; }    //rRef:ITexture
        public string Tex2 { get; set; }    //rRef:ITexture
        public Vec4 Tex1UVSpeed { get; set; }    //Vector4
        public float DotsCoords { get; set; }    //Float
        public float BackFlatOrCube { get; set; }    //Float
        public string BackgroundCube { get; set; }     //rRef:ITexture
    }
    public partial class _screen_artifacts
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color Color { get; set; }    //Color
        public float Complexity { get; set; }    //Float
        public float Visiblity { get; set; }    //Float
        public float Disturbance { get; set; }    //Float
        public float Speed { get; set; }    //Float
        public float RandomNumber { get; set; }    //Float
        public float UseBlackBackground { get; set; }    //Float
        public float BraindanceArtifacts { get; set; }    //Float
        public float TillingVertical { get; set; }    //Float
        public float TillingHorizontal { get; set; }    //Float
        public float BendScreen { get; set; }    //Float
        public float AlphaClip { get; set; }    //Float
    }
    public partial class _screen_artifacts_vision
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color Color { get; set; }    //Color
        public float Complexity { get; set; }    //Float
        public float Visiblity { get; set; }    //Float
        public float Disturbance { get; set; }    //Float
        public float Speed { get; set; }    //Float
        public float RandomNumber { get; set; }    //Float
        public float UseBlackBackground { get; set; }    //Float
        public float BraindanceArtifacts { get; set; }    //Float
        public float TillingVertical { get; set; }    //Float
        public float TillingHorizontal { get; set; }    //Float
        public float BendScreen { get; set; }    //Float
        public float AlphaClip { get; set; }    //Float
    }
    public partial class _screen_black
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color Color { get; set; }    //Color
    }
    public partial class _screen_fast_travel_glitch
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color Color { get; set; }    //Color
        public float SingelColor { get; set; }    //Float
        public float ColorMultiplier { get; set; }    //Float
        public float Complexity { get; set; }    //Float
        public float Density { get; set; }    //Float
        public float Disturbance { get; set; }    //Float
        public float Speed { get; set; }    //Float
        public float TillingVertical { get; set; }    //Float
        public float TillingHorizontal { get; set; }    //Float
        public float BendScreen { get; set; }    //Float
        public float Vertical { get; set; }    //Float
    }
    public partial class _screen_glitch
    {
        public float Offset { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color GridColor { get; set; }    //Color
        public float BlurredIntensity { get; set; }    //Float
        public float NoiseSize { get; set; }    //Float
        public float TileSizeX1 { get; set; }    //Float
        public float TileSizeY1 { get; set; }    //Float
        public float TileSizeX2 { get; set; }    //Float
        public float TileSizeY2 { get; set; }    //Float
        public float GlitchSpeed { get; set; }    //Float
        public float GlitchSpeedOffset { get; set; }    //Float
        public float GlitchModTime { get; set; }    //Float
        public float GlitchDepth { get; set; }    //Float
        public float UseSquareMask { get; set; }    //Float
        public float UseScreenSpaceMask { get; set; }    //Float
        public float AlphaMaskContrast { get; set; }    //Float
        public Color ArtifactColor { get; set; }    //Color
        public float ArtifactIntensity { get; set; }    //Float
        public float ArtifactNarrowness { get; set; }    //Float
        public float ArtifactMinimizer { get; set; }    //Float
        public float ArtifactSpeed { get; set; }    //Float
        public float ArtifactTimeOffset { get; set; }    //Float
        public float SmallArtifactsTileX { get; set; }    //Float
        public float SmallArtifactsTileY { get; set; }    //Float
        public float UseStencilMask { get; set; }    //Float
        public float UseSmallArtifacts { get; set; }    //Float
        public float UseBothSideBlur { get; set; }    //Float
        public float UseHorizontal { get; set; }    //Float
        public float UseAlphaOverEntireEffect { get; set; }    //Float
        public float ErrorIntensity { get; set; }    //Float
        public float InvertBrightnessMask { get; set; }    //Float
        public string DotTex { get; set; }    //rRef:ITexture
    }
    public partial class _screen_glitch_notxaa
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color GridColor { get; set; }    //Color
        public float BlurredIntensity { get; set; }    //Float
        public float NoiseSize { get; set; }    //Float
        public float TileSizeX1 { get; set; }    //Float
        public float TileSizeY1 { get; set; }    //Float
        public float TileSizeX2 { get; set; }    //Float
        public float TileSizeY2 { get; set; }    //Float
        public float GlitchSpeed { get; set; }    //Float
        public float GlitchSpeedOffset { get; set; }    //Float
        public float GlitchModTime { get; set; }    //Float
        public float GlitchDepth { get; set; }    //Float
        public float UseSquareMask { get; set; }    //Float
        public float UseScreenSpaceMask { get; set; }    //Float
        public float AlphaMaskContrast { get; set; }    //Float
        public Color ArtifactColor { get; set; }    //Color
        public float ArtifactIntensity { get; set; }    //Float
        public float ArtifactNarrowness { get; set; }    //Float
        public float ArtifactMinimizer { get; set; }    //Float
        public float ArtifactSpeed { get; set; }    //Float
        public float ArtifactTimeOffset { get; set; }    //Float
        public float SmallArtifactsTileX { get; set; }    //Float
        public float SmallArtifactsTileY { get; set; }    //Float
        public float UseStencilMask { get; set; }    //Float
        public float UseSmallArtifacts { get; set; }    //Float
        public float UseBothSideBlur { get; set; }    //Float
        public float UseHorizontal { get; set; }    //Float
        public float UseAlphaOverEntireEffect { get; set; }    //Float
        public float ErrorIntensity { get; set; }    //Float
        public float InvertBrightnessMask { get; set; }    //Float
        public string ErrorTex { get; set; }    //rRef:ITexture
        public string DotTex { get; set; }    //rRef:ITexture
    }
    public partial class _screen_glitch_vision
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color GridColor { get; set; }    //Color
        public float BlurredIntensity { get; set; }    //Float
        public float NoiseSize { get; set; }    //Float
        public float TileSizeX1 { get; set; }    //Float
        public float TileSizeY1 { get; set; }    //Float
        public float TileSizeX2 { get; set; }    //Float
        public float TileSizeY2 { get; set; }    //Float
        public float GlitchSpeed { get; set; }    //Float
        public float GlitchSpeedOffset { get; set; }    //Float
        public float GlitchModTime { get; set; }    //Float
        public float GlitchDepth { get; set; }    //Float
        public float UseSquareMask { get; set; }    //Float
        public float UseScreenSpaceMask { get; set; }    //Float
        public float AlphaMaskContrast { get; set; }    //Float
        public Color ArtifactColor { get; set; }    //Color
        public float ArtifactIntensity { get; set; }    //Float
        public float ArtifactNarrowness { get; set; }    //Float
        public float ArtifactMinimizer { get; set; }    //Float
        public float ArtifactSpeed { get; set; }    //Float
        public float ArtifactTimeOffset { get; set; }    //Float
        public float SmallArtifactsTileX { get; set; }    //Float
        public float SmallArtifactsTileY { get; set; }    //Float
        public float UseStencilMask { get; set; }    //Float
        public float UseSmallArtifacts { get; set; }    //Float
        public float UseBothSideBlur { get; set; }    //Float
        public float UseHorizontal { get; set; }    //Float
        public float UseAlphaOverEntireEffect { get; set; }    //Float
        public float ErrorIntensity { get; set; }    //Float
        public float InvertBrightnessMask { get; set; }    //Float
        public string ErrorTex { get; set; }    //rRef:ITexture
        public string DotTex { get; set; }    //rRef:ITexture
    }
    public partial class _signages
    {
        public string MainTexture { get; set; }    //rRef:ITexture
        public float UseRoughnessTexture { get; set; }    //Float
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float Metalness { get; set; }    //Float
        public float Roughness { get; set; }    //Float
        public Vec4 RoughnessTilingAndOffset { get; set; }    //Vector4
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float UniformColor { get; set; }    //Float
        public float UseVertexColorOrMap { get; set; }    //Float
        public Color ColorOneStart { get; set; }    //Color
        public Color ColorOneEnd { get; set; }    //Color
        public float ColorGradientScale { get; set; }    //Float
        public float HorizontalOrVerticalGradient { get; set; }    //Float
        public float GradientStartPosition { get; set; }    //Float
        public Color ColorTwo { get; set; }    //Color
        public Color ColorThree { get; set; }    //Color
        public Color ColorFour { get; set; }    //Color
        public Color ColorFive { get; set; }    //Color
        public Color ColorSix { get; set; }    //Color
        public string NoiseTexture { get; set; }    //rRef:ITexture
        public float LightupDensity { get; set; }    //Float
        public float LightupMinimumValue { get; set; }    //Float
        public float LightupHorizontalOrVertical { get; set; }    //Float
        public float BlinkingSpeed { get; set; }    //Float
        public float BlinkingMinimumValue { get; set; }    //Float
        public float BlinkingPhase { get; set; }    //Float
        public float BlinkSmoothness { get; set; }    //Float
        public float FresnelAmount { get; set; }    //Float
    }
    public partial class _signages_transparent_no_txaa
    {
        public string MainTexture { get; set; }    //rRef:ITexture
        public float UseRoughnessTexture { get; set; }    //Float
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float Metalness { get; set; }    //Float
        public float Roughness { get; set; }    //Float
        public Vec4 RoughnessTilingAndOffset { get; set; }    //Vector4
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float UniformColor { get; set; }    //Float
        public float UseVertexColorOrMap { get; set; }    //Float
        public Color ColorOneStart { get; set; }    //Color
        public Color ColorOneEnd { get; set; }    //Color
        public float ColorGradientScale { get; set; }    //Float
        public float HorizontalOrVerticalGradient { get; set; }    //Float
        public float GradientStartPosition { get; set; }    //Float
        public Color ColorTwo { get; set; }    //Color
        public Color ColorThree { get; set; }    //Color
        public Color ColorFour { get; set; }    //Color
        public Color ColorFive { get; set; }    //Color
        public Color ColorSix { get; set; }    //Color
        public string NoiseTexture { get; set; }    //rRef:ITexture
        public float LightupDensity { get; set; }    //Float
        public float LightupMinimumValue { get; set; }    //Float
        public float LightupHorizontalOrVertical { get; set; }    //Float
        public float BlinkingSpeed { get; set; }    //Float
        public float BlinkingMinimumValue { get; set; }    //Float
        public float BlinkingPhase { get; set; }    //Float
        public float BlinkSmoothness { get; set; }    //Float
        public float FresnelAmount { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
    }
    public partial class _silverhand_proxy
    {
        public string Color { get; set; }    //rRef:ITexture
        public float EmissiveEV { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public float BayerScale { get; set; }    //Float
        public float BayerIntensity { get; set; }    //Float
        public float FresnelExponent { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
    }
    public partial class _simple_additive_ui
    {
        public string UIRenderTexture { get; set; }    //rRef:ITexture
        public Vec4 UvTilingAndOffset { get; set; }    //Vector4
        public Vec4 DirtTilingAndOffset { get; set; }    //Vector4
        public Vec4 TexturePartUV { get; set; }    //Vector4
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float PremultiplyByAlpha { get; set; }    //Float
        public Color EmissiveColor { get; set; }    //Color
        public float Saturation { get; set; }    //Float
        public string DirtTexture { get; set; }    //rRef:ITexture
        public float DirtOpacity { get; set; }    //Float
        public Color DirtColorScale { get; set; }    //Color
    }
    public partial class _simple_emissive_decals
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float ColorMultiply { get; set; }    //Float
        public Color EmissiveColor { get; set; }    //Color
        public float SubUVWidth { get; set; }    //Float
        public float SubUVHeight { get; set; }    //Float
        public float FrameNum { get; set; }    //Float
        public float InvertSoftAlpha { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
    }
    public partial class _simple_fresnel
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public Color FresnelColor { get; set; }    //Color
        public float FresnelPower { get; set; }    //Float
    }
    public partial class _simple_refraction
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float RefractionStrength { get; set; }    //Float
        public string Refraction { get; set; }    //rRef:ITexture
        public float UseDepth { get; set; }    //Float
        public Vec4 RefractionTextureOffset { get; set; }    //Vector4
        public Vec4 RefractionTextureSpeed { get; set; }    //Vector4
        public float SlowFactor { get; set; }    //Float
        public float RefractionStrengthSlowTime { get; set; }    //Float
    }
    public partial class _sound_clue
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public Color Color { get; set; }    //Color
        public float ColorMultiplier { get; set; }    //Float
    }
    public partial class _television_ad
    {
        public float TilesWidth { get; set; }    //Float
        public float TilesHeight { get; set; }    //Float
        public float PlaySpeed { get; set; }    //Float
        public float InterlaceLines { get; set; }    //Float
        public float PixelsHeight { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float BlackLinesRatio { get; set; }    //Float
        public float BlackLinesIntensity { get; set; }    //Float
        public string AdTexture { get; set; }    //rRef:ITexture
        public float BlackLinesSize { get; set; }    //Float
        public float LinesOrDots { get; set; }    //Float
        public float DistanceDivision { get; set; }    //Float
        public float Metalness { get; set; }    //Float
        public float Roughness { get; set; }    //Float
        public float IsBroken { get; set; }    //Float
        public float UseFloatParameter { get; set; }    //Float
        public float UseFloatParameter1 { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public string DirtTexture { get; set; }    //rRef:ITexture
        public float DirtOpacityScale { get; set; }    //Float
        public float DirtRoughness { get; set; }    //Float
        public float DirtUvScaleU { get; set; }    //Float
        public float DirtUvScaleV { get; set; }    //Float
        public float HUEChangeSpeed { get; set; }    //Float
    }
    public partial class _triplanar_projection
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public float FirstValue { get; set; }    //Float
        public float SecondValue { get; set; }    //Float
        public float ThirdValue { get; set; }    //Float
        public Color Color { get; set; }    //Color
        public float Stretch { get; set; }    //Float
        public float ColorMultiplier { get; set; }    //Float
    }
    public partial class _water_test
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color TintColor { get; set; }    //Color
        public Color TintColorDeep { get; set; }    //Color
        public Vec4 TexCoordDtortScaleSpeed { get; set; }    //Vector4
        public float DistortAmount { get; set; }    //Float
        public float IOR { get; set; }    //Float
        public float ReflectionPower { get; set; }    //Float
        public Vec4 ReflectNormalMultiplier { get; set; }    //Vector4
        public string Normal { get; set; }    //rRef:ITexture
        public string Alpha { get; set; }    //rRef:ITexture
    }
    public partial class _zoom
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float Progress { get; set; }    //Float
        public Color OutlineColor { get; set; }    //Color
        public float OutlineThickness { get; set; }    //Float
        public float MinRange { get; set; }    //Float
        public float MaxRange { get; set; }    //Float
        public float MotionIntensity { get; set; }    //Float
        public float TransitionOrLoop { get; set; }    //Float
        public float IsBackwardEffect { get; set; }    //Float
        public float UseBrokenSobelPixels { get; set; }    //Float
    }
    public partial class _alt_halo
    {
        public float Offset { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Noise { get; set; }    //rRef:ITexture
        public string DistanceNoise { get; set; }    //rRef:ITexture
        public float DistanceNoiseScale { get; set; }    //Float
        public string Dot { get; set; }    //rRef:ITexture
        public float DotsLift { get; set; }    //Float
        public float DistPower { get; set; }    //Float
        public float NoiseScale { get; set; }    //Float
        public float NoiseSpeed { get; set; }    //Float
        public float DistanceNoiseAmount { get; set; }    //Float
        public float DotsMax { get; set; }    //Float
        public Color Color { get; set; }    //Color
        public float WorldOrLocalSpace { get; set; }    //Float
        public float DotsScale { get; set; }    //Float
        public float LocalSpaceRatio { get; set; }    //Float
        public float FadeOutDistance { get; set; }    //Float
        public float FadeOutDistanceMinimum { get; set; }    //Float
        public float UVOrScreenSpace { get; set; }    //Float
    }
    public partial class _blackbodyradiation_distant
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float Temperature { get; set; }    //Float
        public string FireScatterAlpha { get; set; }    //rRef:ITexture
        public float subUVWidth { get; set; }    //Float
        public float subUVHeight { get; set; }    //Float
        public float MultiplierExponent { get; set; }    //Float
        public float NoAlphaOnTexture { get; set; }    //Float
        public float AlphaExponent { get; set; }    //Float
        public float maxAlpha { get; set; }    //Float
        public float EatUpOrStraightAlpha { get; set; }    //Float
        public float ScatterAmount { get; set; }    //Float
        public float ScatterPower { get; set; }    //Float
        public float HueShift { get; set; }    //Float
        public float HueSpread { get; set; }    //Float
        public float Saturation { get; set; }    //Float
        public float ExpensiveBlending { get; set; }    //Float
        public Color LightSmoke { get; set; }    //Color
        public Color DarkSmoke { get; set; }    //Color
        public float SoftAlpha { get; set; }    //Float
        public string Distort { get; set; }    //rRef:ITexture
        public Vec4 TexCoordDtortScale { get; set; }    //Vector4
        public Vec4 TexCoordDtortSpeed { get; set; }    //Vector4
        public float DistortAmount { get; set; }    //Float
        public float EnableRowAnimation { get; set; }    //Float
        public float DoNotApplyLighting { get; set; }    //Float
        public string MaskTexture { get; set; }    //rRef:ITexture
        public float InvertMask { get; set; }    //Float
        public Vec4 MaskTilingAndSpeed { get; set; }    //Vector4
        public float MaskIntensity { get; set; }    //Float
        public float UseVertexAlpha { get; set; }    //Float
        public float DotWithLookAt { get; set; }    //Float
    }
    public partial class _blackbodyradiation_notxaa
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float Temperature { get; set; }    //Float
        public string FireScatterAlpha { get; set; }    //rRef:ITexture
        public float subUVWidth { get; set; }    //Float
        public float subUVHeight { get; set; }    //Float
        public float MultiplierExponent { get; set; }    //Float
        public float NoAlphaOnTexture { get; set; }    //Float
        public float AlphaExponent { get; set; }    //Float
        public float maxAlpha { get; set; }    //Float
        public float EatUpOrStraightAlpha { get; set; }    //Float
        public float ScatterAmount { get; set; }    //Float
        public float ScatterPower { get; set; }    //Float
        public float HueShift { get; set; }    //Float
        public float HueSpread { get; set; }    //Float
        public float Saturation { get; set; }    //Float
        public float ExpensiveBlending { get; set; }    //Float
        public Color LightSmoke { get; set; }    //Color
        public Color DarkSmoke { get; set; }    //Color
        public float SoftAlpha { get; set; }    //Float
        public string Distort { get; set; }    //rRef:ITexture
        public Vec4 TexCoordDtortScale { get; set; }    //Vector4
        public Vec4 TexCoordDtortSpeed { get; set; }    //Vector4
        public float DistortAmount { get; set; }    //Float
        public float EnableRowAnimation { get; set; }    //Float
        public float DoNotApplyLighting { get; set; }    //Float
        public string MaskTexture { get; set; }    //rRef:ITexture
        public float InvertMask { get; set; }    //Float
        public Vec4 MaskTilingAndSpeed { get; set; }    //Vector4
        public float MaskIntensity { get; set; }    //Float
        public float UseVertexAlpha { get; set; }    //Float
        public float DotWithLookAt { get; set; }    //Float
    }
    public partial class _blood_metal_base
    {
        public Color ColorThin { get; set; }    //Color
        public Color ColorThick { get; set; }    //Color
        public string NormalAndDensity { get; set; }    //rRef:ITexture
        public float Metalness { get; set; }    //Float
        public float Roughness { get; set; }    //Float
        public float SubUVWidth { get; set; }    //Float
        public float SubUVHeight { get; set; }    //Float
        public float UseTimeFlowmap { get; set; }    //Float
        public float FlowMapSpeed { get; set; }    //Float
        public string VelocityMap { get; set; }    //rRef:ITexture
        public float FlowmapStrength { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float UseOnStaticMeshes { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
    }
    public partial class _caustics
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Distortion { get; set; }    //rRef:ITexture
        public Color Color { get; set; }    //Color
        public float Contrast { get; set; }    //Float
        public float Speed { get; set; }    //Float
        public float SmallMovementSpeed { get; set; }    //Float
        public float Multiplier { get; set; }    //Float
        public float Spread { get; set; }    //Float
        public float DistortionAmount { get; set; }    //Float
        public float DistortionUVScaling { get; set; }    //Float
        public float UVScaling { get; set; }    //Float
        public float EdgeWidth { get; set; }    //Float
        public float EdgeMultiplier { get; set; }    //Float
        public float MaxValue { get; set; }    //Float
    }
    public partial class _character_kerenzikov
    {
        public float VertexOffset { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public Vec4 CenterPoint { get; set; }    //Vector4
        public float PixelOffset { get; set; }    //Float
        public float ComebackPixelOffset { get; set; }    //Float
        public float NoiseAmount { get; set; }    //Float
        public float Debug { get; set; }    //Float
    }
    public partial class _character_sandevistan
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float Iterations { get; set; }    //Float
        public float OffsetStrength { get; set; }    //Float
        public float InsideSoftAlpha { get; set; }    //Float
        public float TopDisplacePower { get; set; }    //Float
        public float TopDisplaceIntensity { get; set; }    //Float
    }
    public partial class _crystal_dome
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float ScanlineDensity { get; set; }    //Float
        public float GainMin { get; set; }    //Float
        public float GainMax { get; set; }    //Float
        public float NoiseMax { get; set; }    //Float
        public float NoiseBrightness { get; set; }    //Float
        public float IntialGradientTime { get; set; }    //Float
    }
    public partial class _crystal_dome_opaque
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public Color PrimaryGlowColor { get; set; }    //Color
        public Color SecondaryGlowColor { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public string Roughness { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public Vec4 Tiling { get; set; }    //Vector4
        public float InitialTime { get; set; }    //Float
        public float MaxTimeOffset { get; set; }    //Float
        public float SwipeAngle { get; set; }    //Float
        public string FluffMask { get; set; }    //rRef:ITexture
        public string PatternMask { get; set; }    //rRef:ITexture
        public float UVDivision { get; set; }    //Float
        public float NoiseMax { get; set; }    //Float
        public float DebugValue { get; set; }    //Float
        public float Debug { get; set; }    //Float
        public float UVDivision_FluffMask { get; set; }    //Float
        public float MinUV { get; set; }    //Float
        public float MaxUV { get; set; }    //Float
        public string DistortionMap { get; set; }    //rRef:ITexture
        public float DistortionScale { get; set; }    //Float
    }
    public partial class _cyberspace_gradient
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float InitialGradientTiling { get; set; }    //Float
        public float InitialGradientDivisions { get; set; }    //Float
        public float RectangleRatio { get; set; }    //Float
        public string GradientPalette { get; set; }    //rRef:ITexture
        public string SecondaryGradientPalette { get; set; }    //rRef:ITexture
        public float Reveal { get; set; }    //Float
        public float ReveakMaskContrast { get; set; }    //Float
        public float RevealBiasMin { get; set; }    //Float
        public float RevealBiasMax { get; set; }    //Float
        public float ColorBias { get; set; }    //Float
        public float FloatOrParam { get; set; }    //Float
        public float FloatOrAlpha { get; set; }    //Float
        public Vec4 HSB { get; set; }    //Vector4
        public float BottomLinesAmount { get; set; }    //Float
        public float BottomLinesCuttoff { get; set; }    //Float
        public float BottomLinesWidth { get; set; }    //Float
        public float TowardsCameraSpeed { get; set; }    //Float
    }
    public partial class _cyberspace_teleport_glitch
    {
        public float DepthOffset { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string DistortionMap { get; set; }    //rRef:ITexture
        public float DistortionSize { get; set; }    //Float
        public float DistortionMultiplier { get; set; }    //Float
        public float ChangeChance { get; set; }    //Float
        public float LinesSize { get; set; }    //Float
        public float LinesSpeed { get; set; }    //Float
        public float LinesAmount { get; set; }    //Float
        public float LinesDistortion { get; set; }    //Float
        public float SampledDistortOFfset { get; set; }    //Float
        public Vec4 SampledDistortSize { get; set; }    //Vector4
        public float ColorMultiplier { get; set; }    //Float
    }
    public partial class _decal_caustics
    {
        public Color Color { get; set; }    //Color
        public float AlphaMaskContrast { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public string Distortion { get; set; }    //rRef:ITexture
        public float Contrast { get; set; }    //Float
        public float Speed { get; set; }    //Float
        public float SmallMovementSpeed { get; set; }    //Float
        public float Spread { get; set; }    //Float
        public float DistortionAmount { get; set; }    //Float
        public float DistortionUVScaling { get; set; }    //Float
        public float UVScaling { get; set; }    //Float
        public float EdgeWidth { get; set; }    //Float
        public float EdgeMultiplier { get; set; }    //Float
        public float MaxValue { get; set; }    //Float
        public float GradientStartPosition { get; set; }    //Float
        public float GradientLength { get; set; }    //Float
    }
    public partial class _decal_glitch
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public string MaskTexture { get; set; }    //rRef:ITexture
        public string GradientMap { get; set; }    //rRef:ITexture
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
        public float GlitchScale { get; set; }    //Float
        public float GlitchStrength { get; set; }    //Float
        public float GlitchChance { get; set; }    //Float
        public float GlitchOffOn { get; set; }    //Float
        public float DissapearingChance { get; set; }    //Float
        public float ColorChangeAmount { get; set; }    //Float
        public Color DiffuseColor { get; set; }    //Color
        public float EmissiveEV { get; set; }    //Float
    }
    public partial class _decal_glitch_emissive
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public string MaskTexture { get; set; }    //rRef:ITexture
        public string GradientMap { get; set; }    //rRef:ITexture
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
        public float GlitchScale { get; set; }    //Float
        public float GlitchStrength { get; set; }    //Float
        public float GlitchChance { get; set; }    //Float
        public float GlitchOffOn { get; set; }    //Float
        public float DissapearingChance { get; set; }    //Float
        public float ColorChangeAmount { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public Color DiffuseColor { get; set; }    //Color
    }
    public partial class _depth_based_sobel
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float ThinLinesThickness { get; set; }    //Float
        public float ThinLinesDistance { get; set; }    //Float
        public float ThickLinesThickness { get; set; }    //Float
        public float ThickLinesDistance { get; set; }    //Float
        public float OutlineThickness { get; set; }    //Float
        public Color LinesColor { get; set; }    //Color
        public float Brightness { get; set; }    //Float
        public float MinDistance { get; set; }    //Float
        public float MaxDistance { get; set; }    //Float
        public float MaskSizeX { get; set; }    //Float
        public float MaskSizeY { get; set; }    //Float
        public float SobelThreshold { get; set; }    //Float
        public float SobelStep { get; set; }    //Float
        public float SobelMinimumChange { get; set; }    //Float
    }
    public partial class _diode_pavements_ui
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public float Metalness { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public string DiodesMask { get; set; }    //rRef:ITexture
        public string SignTexture { get; set; }    //rRef:ITexture
        public Vec4 DiodesTilingAndScrollSpeed { get; set; }    //Vector4
        public float Emissive { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public float UseMaskAsAlphaThreshold { get; set; }    //Float
        public string UIRenderTexture { get; set; }    //rRef:ITexture
        public Vec4 TexturePartUV { get; set; }    //Vector4
        public Vec4 RenderTextureScale { get; set; }    //Vector4
        public float VerticalFlipEnabled { get; set; }    //Float
        public float AmountOfGlitch { get; set; }    //Float
        public float GlitchSpeed { get; set; }    //Float
        public Vec4 BaseColorRoughnessTiling { get; set; }    //Vector4
    }
    public partial class _dirt_animated_masked
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Mask { get; set; }    //rRef:ITexture
        public string Dirt { get; set; }    //rRef:ITexture
        public string DirtSecond { get; set; }    //rRef:ITexture
        public Color DirtColor { get; set; }    //Color
        public float Multiplier { get; set; }    //Float
        public float WidthScaling { get; set; }    //Float
        public float HeightScaling { get; set; }    //Float
        public float RedChannelOrAlpha { get; set; }    //Float
    }
    public partial class _e3_prototype_mask
    {
        public string MaskTexture { get; set; }    //rRef:ITexture
        public string HeatDistribution { get; set; }    //rRef:ITexture
        public float Temperature { get; set; }    //Float
        public float TemperatureMinimum { get; set; }    //Float
        public float HueShift { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveExponent { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public float GradientWidth { get; set; }    //Float
        public float DebugValue { get; set; }    //Float
        public float UseFloatValue { get; set; }    //Float
    }
    public partial class _fake_flare
    {
        public float WidthScale { get; set; }    //Float
        public float HeightScale { get; set; }    //Float
        public float Promixity { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public Color Color { get; set; }    //Color
        public float Multiplier { get; set; }    //Float
        public float MultiplierPower { get; set; }    //Float
    }
    public partial class _fake_flare_simple
    {
        public float DistanceSizeFactor { get; set; }    //Float
        public float SizeScale { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string MaskTexture { get; set; }    //rRef:ITexture
        public float RadialOrTexture { get; set; }    //Float
        public Color Color { get; set; }    //Color
        public float Multiplier { get; set; }    //Float
        public float FalloffPower { get; set; }    //Float
        public float MinimumDistanceVisibility { get; set; }    //Float
        public float DistanceVisibilityFadeIn { get; set; }    //Float
        public float MaximumRangeMin { get; set; }    //Float
        public float MaximumRangeMax { get; set; }    //Float
        public float BlinkSpeed { get; set; }    //Float
    }
    public partial class _flat_fog_masked
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string RefractionMask { get; set; }    //rRef:ITexture
        public float DebugValue { get; set; }    //Float
        public float Fogginess { get; set; }    //Float
        public float Crackness { get; set; }    //Float
        public float FogOrRefraction { get; set; }    //Float
        public Color CrackColor { get; set; }    //Color
    }
    public partial class _flat_fog_masked_notxaa
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string RefractionMask { get; set; }    //rRef:ITexture
        public float DebugValue { get; set; }    //Float
        public float Fogginess { get; set; }    //Float
        public float Crackness { get; set; }    //Float
        public float FogOrRefraction { get; set; }    //Float
        public Color CrackColor { get; set; }    //Color
    }
    public partial class _highlight_blocker
    {
        public float MeshGrow { get; set; }    //Float
    }
    public partial class _hologram_proxy
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Color { get; set; }    //rRef:ITexture
        public float EmissiveEV { get; set; }    //Float
        public float FresnelIntensity { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public float FresnelGamma { get; set; }    //Float
        public float Alpha { get; set; }    //Float
        public float DecayStart { get; set; }    //Float
        public float Decay { get; set; }    //Float
    }
    public partial class _holo_mask
    {
        public float VerticalDivisions { get; set; }    //Float
        public float GlitchChance { get; set; }    //Float
        public float GlitchOffset { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public float ChangeSpeed { get; set; }    //Float
        public float HorizontalDivisions { get; set; }    //Float
        public float ScanlineDensity { get; set; }    //Float
        public float ScanlineMinimum { get; set; }    //Float
        public Color MinColor { get; set; }    //Color
        public Color MaxColor { get; set; }    //Color
        public Color EyesColor { get; set; }    //Color
        public float BrightnessBoost { get; set; }    //Float
        public float EyesBoost { get; set; }    //Float
        public float AmountOfHorizontalTear { get; set; }    //Float
        public float ULimit { get; set; }    //Float
        public float VLimit { get; set; }    //Float
    }
    public partial class _invisible
    {
    }
    public partial class _lightning_plasma
    {
        public float UseTimeOrAnimationFrame { get; set; }    //Float
        public string DisplaceAlongUV { get; set; }    //rRef:ITexture
        public float DisplaceAlongUVSpeed { get; set; }    //Float
        public float DisplaceAlongUVScale { get; set; }    //Float
        public float DisplaceAlongUVStrength { get; set; }    //Float
        public float DisplaceAlongUVStrengthPower { get; set; }    //Float
        public float DisplaceAlongUVAdjustWidth { get; set; }    //Float
        public float DisplaceSeed { get; set; }    //Float
        public float DisplaceSeedSPEED { get; set; }    //Float
        public float DisplaceSeedSPEEDProbability { get; set; }    //Float
        public float DisplaceAlongUVOffScale { get; set; }    //Float
        public float DisplaceAlongUVOffSpeed { get; set; }    //Float
        public float DisplaceAlongUVOffSTR { get; set; }    //Float
        public float WorldNoiseSTR { get; set; }    //Float
        public float WorldNoiseSize { get; set; }    //Float
        public float WorldNoiseSpeed { get; set; }    //Float
        public float WorldNoise_Up_extra { get; set; }    //Float
        public float SetWorldNoiseToLocal { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float FlipUVby90deg { get; set; }    //Float
        public string TemperatureTexture { get; set; }    //rRef:ITexture
        public float MeshAnimationOnOff { get; set; }    //Float
        public float MeshPlaySpeed { get; set; }    //Float
        public float SubUVWidth { get; set; }    //Float
        public float SubUVHeight { get; set; }    //Float
        public float TemperatureTextureScale { get; set; }    //Float
        public float TemperatureTextureSpeed { get; set; }    //Float
        public float Temperature { get; set; }    //Float
        public float TemperaturePow { get; set; }    //Float
        public float TemperatureFlickerSpeed { get; set; }    //Float
        public float TemperatureFlickerSTR { get; set; }    //Float
        public float HueShift { get; set; }    //Float
        public float HueSaturation { get; set; }    //Float
        public float ContactPointRange { get; set; }    //Float
        public float ContactPointSTR { get; set; }    //Float
        public Color Tint { get; set; }    //Color
        public float SoftAlpha { get; set; }    //Float
        public float maxAlpha { get; set; }    //Float
        public string DistortTexture { get; set; }    //rRef:ITexture
        public float DistortAmount { get; set; }    //Float
        public Vec4 TexCoordDtortScale { get; set; }    //Vector4
        public Vec4 TexCoordDistortSpeed { get; set; }    //Vector4
    }
    public partial class _light_gradients
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color BottomColor { get; set; }    //Color
        public Color TopColor { get; set; }    //Color
        public float LerpGradient { get; set; }    //Float
        public float Multiplier { get; set; }    //Float
        public float MinProximityAlpha { get; set; }    //Float
        public float MaxProximityAlpha { get; set; }    //Float
        public float GroundPosition { get; set; }    //Float
        public float TopPosition { get; set; }    //Float
        public float GradientDirection { get; set; }    //Float
        public float RoundGradientPosition { get; set; }    //Float
        public float RoundGradientScale { get; set; }    //Float
        public float DistanceToSurfaceModifier { get; set; }    //Float
    }
    public partial class _low_health
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string MainPattern { get; set; }    //rRef:ITexture
        public string FluffText { get; set; }    //rRef:ITexture
        public string FluffPattern { get; set; }    //rRef:ITexture
        public float Rows { get; set; }    //Float
        public float MaximumSliding { get; set; }    //Float
        public float MaximumDistortion { get; set; }    //Float
        public float OffsetChangeSpeed { get; set; }    //Float
        public float OffsetAmount { get; set; }    //Float
        public float PatternTiling { get; set; }    //Float
        public float PatternVisibility { get; set; }    //Float
        public float FluffVisibility { get; set; }    //Float
        public float FluffTiling { get; set; }    //Float
        public Color VignetteColor { get; set; }    //Color
        public Color FluffTextColor { get; set; }    //Color
        public float VignetteMin { get; set; }    //Float
        public float Multiplier { get; set; }    //Float
        public float VignetteMax { get; set; }    //Float
        public float VignetteLength { get; set; }    //Float
        public float VignetteSteps { get; set; }    //Float
        public float VignetteContrast { get; set; }    //Float
        public float FinalContrast { get; set; }    //Float
        public float LinesMultiplier { get; set; }    //Float
    }
    public partial class _mesh_decal__blackbody
    {
        public float VertexOffsetFactor { get; set; }    //Float
        public string MaskTexture { get; set; }    //rRef:ITexture
        public string HeatDistribution { get; set; }    //rRef:ITexture
        public Vec4 HeatTiling { get; set; }    //Vector4
        public float Temperature { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float MaskMinimum { get; set; }    //Float
        public Vec4 HSV_Mod { get; set; }    //Vector4
        public float UseFloatParam { get; set; }    //Float
        public float EmissiveAlphaContrast { get; set; }    //Float
    }
    public partial class _metal_base_scrolling
    {
        public float Metalness { get; set; }    //Float
        public float Roughness { get; set; }    //Float
        public Color Bright { get; set; }    //Color
        public Color Dark { get; set; }    //Color
        public string Normal { get; set; }    //rRef:ITexture
        public string Mask { get; set; }    //rRef:ITexture
        public Vec4 MaskTilingAndScrolling { get; set; }    //Vector4
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
    }
    public partial class _multilayer_blackbody_inject
    {
        public float Emissive { get; set; }    //Float
        public float Temperature { get; set; }    //Float
        public float MaximumTemperature { get; set; }    //Float
        public float ColorExponent { get; set; }    //Float
        public float Debug { get; set; }    //Float
        public Vec4 FireHSV { get; set; }    //Vector4
        public Vec4 PoisonHSV { get; set; }    //Vector4
        public Vec4 ElectricHSV { get; set; }    //Vector4
        public string GlobalNormal { get; set; }    //rRef:ITexture
        public string DamageTypeRGBMask { get; set; }    //rRef:ITexture
        public string DamageTypeNoise { get; set; }    //rRef:ITexture
        public float DamageTypeNoiseIntesityAdd { get; set; }    //Float
        public Vec4 DamageTypeNoiseUV { get; set; }    //Vector4
        public string MultilayerMask { get; set; }     //rRef:Multilayer_Mask
        public string MultilayerSetup { get; set; }     //rRef:Multilayer_Setup
        public string MaskAtlas { get; set; }    //rRef:ITexture
        public DataBuffer MaskTiles { get; set; }
        public DataBuffer Layers { get; set; }
        public float LayersStartIndex { get; set; }    //Float
        public float SurfaceTexAspectRatio { get; set; }    //Float
        public Vec4 MaskToTileScale { get; set; }    //Vector4
        public float MaskTileSize { get; set; }    //Float
        public Vec4 MaskAtlasDims { get; set; }    //Vector4
        public Vec4 MaskBaseResolution { get; set; }    //Vector4
        public float SetupLayerMask { get; set; }    //Float
    }
    public partial class _nanowire_string
    {
        public float Thickness { get; set; }    //Float
        public float NoiseAmount { get; set; }    //Float
        public float NoiseScale { get; set; }    //Float
        public float MaxVelocity { get; set; }    //Float
        public float MaxVelocityExponent { get; set; }    //Float
        public float StartGradient { get; set; }    //Float
        public float GradientWidth { get; set; }    //Float
        public float MaxDistance { get; set; }    //Float
        public Color MainColor { get; set; }    //Color
        public string NormalMap { get; set; }    //rRef:ITexture
        public string MaskTexture { get; set; }    //rRef:ITexture
        public Vec4 NormalTiling { get; set; }    //Vector4
        public float Metalness { get; set; }    //Float
        public float Roughness { get; set; }    //Float
        public float Temperature { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float MinimumEmissive { get; set; }    //Float
        public float EmissiveMaskPower { get; set; }    //Float
        public float TurnOffBrightness { get; set; }    //Float
        public float BlinkSpeed { get; set; }    //Float
        public float BlinkWidth { get; set; }    //Float
        public float BlinkMultiplier { get; set; }    //Float
        public float BlinkOffMultiplier { get; set; }    //Float
        public Vec4 HSVMod { get; set; }    //Vector4
    }
    public partial class _oda_helm
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public string Hologram { get; set; }    //rRef:ITexture
        public string NormalRoughnessMetalness { get; set; }    //rRef:ITexture
        public string ScanlineTexture { get; set; }    //rRef:ITexture
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVGlitched { get; set; }    //Float
        public float DotPower { get; set; }    //Float
        public float SecondaryDotPower { get; set; }    //Float
        public float LayersSeparation { get; set; }    //Float
        public Vec4 LayersIntensity { get; set; }    //Vector4
        public Vec4 ScanlineTilingAndSpeed { get; set; }    //Vector4
        public float ScanlinesIntensity { get; set; }    //Float
        public Vec4 NoiseScale { get; set; }    //Vector4
        public Color PrimaryColor { get; set; }    //Color
        public Color SecondaryColor { get; set; }    //Color
        public Color BackgroundColor { get; set; }    //Color
        public Color NoiseColor { get; set; }    //Color
        public float NormalOrBroken { get; set; }    //Float
    }
    public partial class _rift_noise
    {
        public float EmissiveEVMin { get; set; }    //Float
        public float EmissiveEVMax { get; set; }    //Float
        public Color EmissiveColor { get; set; }    //Color
        public string EmissiveMask { get; set; }    //rRef:ITexture
        public string Dot { get; set; }    //rRef:ITexture
        public string Noise { get; set; }    //rRef:ITexture
        public float NoiseSpeed { get; set; }    //Float
        public float NoiseScale { get; set; }    //Float
        public Vec4 NoiseScaleXY { get; set; }    //Vector4
        public string DistanceNoise { get; set; }    //rRef:ITexture
        public float DistanceNoiseScale { get; set; }    //Float
        public Vec4 DistanceNoiseScaleXY { get; set; }    //Vector4
        public float DistanceNoiseAmount { get; set; }    //Float
        public float DistPower { get; set; }    //Float
        public float DotsLift { get; set; }    //Float
        public float DotsMax { get; set; }    //Float
        public float DistanceNoiseSpeed { get; set; }    //Float
        public float MaxDistance { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
    }
    public partial class _screen_wave
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float DistortAmount { get; set; }    //Float
    }
    public partial class _simple_fog
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Mask { get; set; }    //rRef:ITexture
        public Color Color { get; set; }    //Color
        public float Brightness { get; set; }    //Float
        public float MinimumVisibilityDistance { get; set; }    //Float
        public float VisibilityFadeIn { get; set; }    //Float
        public float TextureFalloff { get; set; }    //Float
        public float MinimumBottonDistance { get; set; }    //Float
        public float BottomVisibilityFadeIn { get; set; }    //Float
        public float DepthDivision { get; set; }    //Float
        public float DepthContrast { get; set; }    //Float
        public float SoftAlpha { get; set; }    //Float
        public float SteepAngleBlend { get; set; }    //Float
        public float SteepAngleBlendLength { get; set; }    //Float
    }
    public partial class _simple_refraction_mask
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float RefractionStrength { get; set; }    //Float
        public Vec4 RefractionTextureOffset { get; set; }    //Vector4
        public Vec4 RefractionTextureSpeed { get; set; }    //Vector4
        public Vec4 RefractionTextureScale { get; set; }    //Vector4
        public string Refraction { get; set; }    //rRef:ITexture
        public float UseAlphaMask { get; set; }    //Float
        public string AlphaMask { get; set; }    //rRef:ITexture
        public float UseDepth { get; set; }    //Float
        public float SlowFactor { get; set; }    //Float
        public float RefractionStrengthSlowTime { get; set; }    //Float
        public float MaskGradientPower { get; set; }    //Float
        public Color Color { get; set; }    //Color
        public float SoftAlpha { get; set; }    //Float
    }
    public partial class _transparent_flowmap
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public string Flowmap { get; set; }    //rRef:ITexture
        public float FlowMapStrength { get; set; }    //Float
        public float FlowSpeed { get; set; }    //Float
        public Color Color { get; set; }    //Color
        public float Multiplier { get; set; }    //Float
        public float Power { get; set; }    //Float
    }
    public partial class _transparent_liquid_notxaa
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float SurfaceMetalness { get; set; }    //Float
        public Color ScatteringColorThin { get; set; }    //Color
        public Color ScatteringColorThick { get; set; }    //Color
        public Color Albedo { get; set; }    //Color
        public float IOR { get; set; }    //Float
        public float FresnelBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Roughness { get; set; }    //Float
        public float SpecularStrengthMultiplier { get; set; }    //Float
        public float NormalStrength { get; set; }    //Float
        public float MaskOpacity { get; set; }    //Float
        public float ThicknessMultiplier { get; set; }    //Float
        public float SubUVWidth { get; set; }    //Float
        public float SubUVHeight { get; set; }    //Float
        public float InterpolateFrames { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public Vec4 NormalTilingAndScrolling { get; set; }    //Vector4
        public string Distort { get; set; }    //rRef:ITexture
        public float DistortAmount { get; set; }    //Float
        public Vec4 DistortTilingAndScrolling { get; set; }    //Vector4
        public string Mask { get; set; }    //rRef:ITexture
        public float EnableRowAnimation { get; set; }    //Float
        public float UseOnStaticMeshes { get; set; }    //Float
    }
    public partial class _world_to_screen_glitch
    {
        public float OffsetAmount { get; set; }    //Float
        public float Spread { get; set; }    //Float
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float DistortionAmount { get; set; }    //Float
        public float Divisions { get; set; }    //Float
        public float GlitchChance { get; set; }    //Float
        public float GlitchSpeed { get; set; }    //Float
        public float GlowMultipier { get; set; }    //Float
        public float DistortGlitchDivisions { get; set; }    //Float
        public float DistortGlitchSpeed { get; set; }    //Float
        public float MidMaskWidth { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
    }
    public partial class _hit_proxy
    {
    }
    public partial class _lod_coloring
    {
    }
    public partial class _overdraw
    {
    }
    public partial class _overdraw_seethrough
    {
    }
    public partial class _selection
    {
    }
    public partial class _uv_density
    {
    }
    public partial class _wireframe
    {
    }
    public partial class _editor_mlmask_preview
    {
        public string MultilayerMask { get; set; }     //rRef:Multilayer_Mask
        public string MaskAtlas { get; set; }    //rRef:ITexture
        public DataBuffer MaskTiles { get; set; }
        public DataBuffer Layers { get; set; }
        public float LayersStartIndex { get; set; }    //Float
        public float SurfaceTexAspectRatio { get; set; }    //Float
        public Vec4 MaskToTileScale { get; set; }    //Vector4
        public float MaskTileSize { get; set; }    //Float
        public Vec4 MaskAtlasDims { get; set; }    //Vector4
        public Vec4 MaskBaseResolution { get; set; }    //Vector4
        public float EditorMaskLayerIndex { get; set; }    //Float
        public float EditorVisualizationModeIndex { get; set; }    //Float
        public float EditorShowValue { get; set; }    //Float
        public Vec4 EditorCursorPosition { get; set; }    //Vector4
    }
    public partial class _editor_mltemplate_preview
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public string NormalTexture { get; set; }    //rRef:ITexture
        public Vec4 ColorScale { get; set; }    //Vector4
        public float NormalScale { get; set; }    //Float
        public string RoughnessTexture { get; set; }    //rRef:ITexture
        public float MetalnessScaleIn { get; set; }    //Float
        public float MetalnessBiasIn { get; set; }    //Float
        public float RoughnessScaleIn { get; set; }    //Float
        public float RoughnessBiasIn { get; set; }    //Float
        public float MetalnessScaleOut { get; set; }    //Float
        public float MetalnessBiasOut { get; set; }    //Float
        public float RoughnessScaleOut { get; set; }    //Float
        public float RoughnessBiasOut { get; set; }    //Float
        public float ColorMaskScaleIn { get; set; }    //Float
        public float ColorMaskBiasIn { get; set; }    //Float
        public float ColorMaskScaleOut { get; set; }    //Float
        public float ColorMaskBiasOut { get; set; }    //Float
        public string MetalnessTexture { get; set; }    //rRef:ITexture
        public float Tiling { get; set; }    //Float
    }
    public partial class _gi_backface_debug
    {
    }
    public partial class _multilayered_baked
    {
        public float SurfaceID { get; set; }    //Float
        public string Indirection { get; set; }    //rRef:ITexture
        public string BaseColorRough { get; set; }    //rRef:ITexture
        public string NormalMetal { get; set; }    //rRef:ITexture
    }

    public partial class _mikoshi_fullscr_transition
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public string Mask { get; set; }    //rRef:ITexture
    }
    public partial class _decal
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public float DiffuseTextureAsMaskTexture { get; set; }    //Float
        public Color DiffuseColor { get; set; }    //Color
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _decal_normal
    {
        public string DiffuseTexture { get; set; }    //rRef:ITexture
        public float DiffuseTextureAsMaskTexture { get; set; }    //Float
        public string NormalTexture { get; set; }    //rRef:ITexture
        public Color DiffuseColor { get; set; }    //Color
        public float AlphaMaskContrast { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public float RoughnessMetalnessAlpha { get; set; }    //Float
        public float SubUVx { get; set; }    //Float
        public float SubUVy { get; set; }    //Float
        public float Frame { get; set; }    //Float
    }
    public partial class _pbr_layer
    {
        public string Diffuse { get; set; }    //rRef:ITexture
        public string Mask { get; set; }    //rRef:ITexture
        public string GlobalNormal { get; set; }    //rRef:ITexture
        public string MicroBlends { get; set; }    //rRef:ITexture
        public string Normal { get; set; }    //rRef:ITexture
        public string RoughMetalBlend { get; set; }    //rRef:ITexture
        public Color TintColor { get; set; }    //Color
        public float LayerTile { get; set; }    //Float
        public float MicroblendTile { get; set; }    //Float
        public float MicroblendContrast { get; set; }    //Float
        public float MicroblendNormalStrength { get; set; }    //Float
        public float LayerOpacity { get; set; }    //Float
        public float LayerOffsetU { get; set; }    //Float
        public float LayerOffsetV { get; set; }    //Float
        public float is_df { get; set; }    //Float
    }
    public partial class _debugdraw
    {
    }
    public partial class _fallback
    {
    }
    public partial class _metal_base
    {
        public float VehicleDamageInfluence { get; set; }    //Float
        public string BaseColor { get; set; }    //rRef:ITexture
        public Vec4 BaseColorScale { get; set; }    //Vector4
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float NormalStrength { get; set; }    //Float
        public float AlphaThreshold { get; set; }    //Float
        public string Emissive { get; set; }    //rRef:ITexture
        public float EmissiveLift { get; set; }    //Float
        public float EmissiveEV { get; set; }    //Float
        public float EmissiveEVRaytracingBias { get; set; }    //Float
        public float EmissiveDirectionality { get; set; }    //Float
        public float EnableRaytracedEmissive { get; set; }    //Float
        public Color EmissiveColor { get; set; }    //Color
        public float LayerTile { get; set; }    //Float
    }
    public partial class _mirror
    {
        public string BaseColor { get; set; }    //rRef:ITexture
        public string BorderMask { get; set; }    //rRef:ITexture
        public Color BaseColorScale { get; set; }    //Color
        public string Metalness { get; set; }    //rRef:ITexture
        public float MetalnessScale { get; set; }    //Float
        public float MetalnessBias { get; set; }    //Float
        public string Roughness { get; set; }    //rRef:ITexture
        public float RoughnessScale { get; set; }    //Float
        public float RoughnessBias { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public float Translucency { get; set; }    //Float
        public float BorderThickness { get; set; }    //Float
        public Color BorderColor { get; set; }    //Color
    }
    public partial class _particles_generic
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public Color Color { get; set; }    //Color
        public float ColorMultiplier { get; set; }    //Float
        public float SubUVWidth { get; set; }    //Float
        public float SubUVHeight { get; set; }    //Float
        public float Desaturate { get; set; }    //Float
        public float ColorPower { get; set; }    //Float
        public float DistortAmount { get; set; }    //Float
        public Vec4 TexCoordScale { get; set; }    //Vector4
        public Vec4 TexCoordSpeed { get; set; }    //Vector4
        public Vec4 TexCoordDtortScale { get; set; }    //Vector4
        public Vec4 TexCoordDistortSpeed { get; set; }    //Vector4
        public float AlphaGlobal { get; set; }    //Float
        public float AlphaSoft { get; set; }    //Float
        public float AlphaFresnelPower { get; set; }    //Float
        public float UseAlphaFresnel { get; set; }    //Float
        public float UseAlphaMask { get; set; }    //Float
        public float UseOneChannel { get; set; }    //Float
        public string Diffuse { get; set; }    //rRef:ITexture
        public string AlphaMask { get; set; }    //rRef:ITexture
        public float FlipUVby90deg { get; set; }    //Float
        public float EVCompensation { get; set; }    //Float
        public string Distortion { get; set; }    //rRef:ITexture
        public float UseContrastAlpha { get; set; }    //Float
        public float SoftUVInterpolate { get; set; }    //Float
    }
    public partial class _particles_liquid
    {
        public float AdditiveAlphaBlend { get; set; }    //Float
        public float SubUVWidth { get; set; }    //Float
        public float SubUVHeight { get; set; }    //Float
        public float Desaturate { get; set; }    //Float
        public float DistortAmount { get; set; }    //Float
        public Vec4 TexCoordScale { get; set; }    //Vector4
        public Vec4 TexCoordSpeed { get; set; }    //Vector4
        public Vec4 TexCoordDtortScale { get; set; }    //Vector4
        public Vec4 TexCoordDistortSpeed { get; set; }    //Vector4
        public float AlphaGlobal { get; set; }    //Float
        public float AlphaSoft { get; set; }    //Float
        public float AlphaFresnelPower { get; set; }    //Float
        public float UseAlphaFresnel { get; set; }    //Float
        public float UseAlphaMask { get; set; }    //Float
        public Vec4 NormalMultiplier { get; set; }    //Vector4
        public float ReflectionMultiplier { get; set; }    //Float
        public float ReflectionPower { get; set; }    //Float
        public Color ReflectionColor { get; set; }    //Color
        public float RefractionMultiplier { get; set; }    //Float
        public string Normal { get; set; }    //rRef:ITexture
        public string AlphaMask { get; set; }    //rRef:ITexture
        public string Distortion { get; set; }    //rRef:ITexture
        public string Reflection { get; set; }     //rRef:ITexture
        public float SoftUVInterpolate { get; set; }    //Float
        public float ReflectionEdge { get; set; }    //Float
        public Color MainColor { get; set; }    //Color
    }
    public class Color
    {
        public float Red { get; set; } = 255;
        public float Green { get; set; } = 255;
        public float Blue { get; set; } = 255;
        public float Alpha { get; set; } = 255;

        public Color(CColor c)
        {
            Red = c.Red.Value;
            Green = c.Green.Value;
            Blue = c.Blue.Value;
            Alpha = c.Alpha.Value;
        }
    }
    public class Vec4
    {
        public float X { get; set; } = 0;
        public float Y { get; set; } = 0;
        public float Z { get; set; } = 0;
        public float W { get; set; } = 0;

        public Vec4(Vector4 v)
        {
            X = v.X.Value;
            Y = v.Y.Value;
            Z = v.Z.Value;
            W = v.W.Value;
        }
    }
}

