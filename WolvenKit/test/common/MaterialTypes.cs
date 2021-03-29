namespace WolvenKit.RED4.MeshFile.Materials.MaterialTypes
{
    public enum MaterialType
    {
        MultiLayered, MeshDecal, HoomanSkin
    }
    public class MultiLayered
    {
        public string multilayerSetup { get; set; } = null;
        public string multilayerMask { get; set; } = null;
        public string globalNormal { get; set; } = null;
    }
    public class MeshDecal
    {
        public string diffuseTexture { get; set; } = null;
        public MVector4 diffuseColor { get; set; } = new MVector4(1, 1, 1, 1);
        public float diffuseAlpha { get; set; } = 1;
        public MVector2 uVOffset { get; set; } = new MVector2(0, 0);
        public float uVRotation { get; set; } = 0;
        public MVector2 uVScale { get; set; } = new MVector2(1, 1);
        public string secondaryMask { get; set; } = null;
        public float secondaryMaskUVScale { get; set; } = 1;
        public float secondaryMaskInfluence { get; set; } = 0;
        public string normalTexture { get; set; } = null;
        public float normalAlpha { get; set; } = 0;
        public string normalAlphaTex { get; set; } = null;
        public float normalsBlendingMode { get; set; } = 1;
        public string roughnessTexture { get; set; } = null;
        public string metalnessTexture { get; set; } = null;
        public float alphaMaskContrast { get; set; } = 0;
        public float roughnessMetalnessAlpha { get; set; } = 0;
        public float animationSpeed { get; set; } = 1;
        public float animationFramesWidth { get; set; } = 1;
        public float animationFramesHeight { get; set; } = 1;
        public float depthThreshold { get; set; } = 0;
    }
    
    public class HoomanSkin
    {
        public string roughness { get; set; } = null;
        public string detailNormal { get; set; } = null;
        public float detailNormalInfluence { get; set; } = 1;
        public string normal { get; set; } = null;
        public string albedo { get; set; } = null;
        public string detailmap_Squash { get; set; } = null;
        public string detailmap_Stretch { get; set; } = null;
        public float detailRoughnessBiasMin { get; set; } = 1;
        public float detailRoughnessBiasMax { get; set; } = 0;
        public MVector4 tintColor { get; set; } = new MVector4(1, 1, 1, 1);
        public float tintScale { get; set; } = 0;
        public string skinProfile { get; set; } = null;
        public string bloodflow { get; set; } = null;
        public MVector4 bloodColor { get; set; } = new MVector4(0,0,0,0);
    }
    // defining some custom vecs for materials system.text.json parsing it only serialized properties {get; set;} and not fields system.numerics.vec4 has fields
    public class MVector4
    {
        public float X { get; set; }
        public float Y { get; set; }
        public float Z { get; set; }
        public float W { get; set; }

        public MVector4(float x, float y, float z, float w)
        {
            this.X = x;
            this.Y = y;
            this.Z = z;
            this.W = w;
        }
    }
    public class MVector2
    {
        public float X { get; set; }
        public float Y { get; set; }
        public MVector2(float x, float y)
        {
            this.X = x;
            this.Y = y;
        }
    }
}
