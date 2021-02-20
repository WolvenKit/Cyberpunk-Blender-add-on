using System;
using System.Numerics;

namespace HalfFloat
{
    class Converters
    {
        public float hfconvert(UInt16 read)// for converting ushort representation of a Half float to a float32
        {
            String bin = Convert.ToString(read, 2).PadLeft(16, '0');
            UInt16 sp = Convert.ToUInt16(bin.Substring(6, 10), 2);
            UInt16 pow = Convert.ToUInt16(bin.Substring(1, 5), 2);
            UInt16 sign = Convert.ToUInt16(bin.Substring(0, 1));

            float value = 0f;
            if (pow == 0)
            {
                value = Convert.ToSingle(Math.Pow(2, -14)) * (sp / 1024f);
            }
            else if (pow == 31)
            {
                if (sp == 0)
                    value = float.PositiveInfinity;
                else
                    value = float.NaN;
            }
            else
            {
                value = Convert.ToSingle(Math.Pow(2, pow - 15)) * (1 + sp / 1024f);
            }

            if (sign == 1)
            {
                value = (-1) * value;
            }

            return value;
        }
        public UInt16 converthf(float value) // a floating point to halffloat uint16 equivalent representation -65504 <= value <= 65504
        {
            UInt16 sign = 0;
            UInt16 sp = 0;
            UInt16 pow = 0;
            if (float.IsNegative(value) && !float.IsNaN(value))
            {
                sign = 32768;
                value = -1 * value;
            }
            if (value > 65504)
            {
                value = 65504;      // if number provided is > Half.Max or < Half.Min then normalized
            }
            if (value >= 0 && value <= (float)0.000060975552)
            {
                pow = 0;
                sp = Convert.ToUInt16(value * 1024 * Math.Pow(2, 14));
            }
            else if (float.IsNaN(value) || float.IsPositiveInfinity(value))
            {
                sp = 0;
                pow = 31744;
                if (float.IsNaN(value))
                    sp = 55; // sp can be anything in this case i randomly put 55
            }
            else if (value >= (float)0.00006103515625 && value <= (float)65504)
            {
                Int16 temp1 = 14;
                UInt64 temp2 = Convert.ToUInt64((value * Math.Pow(2, temp1) - 1) * 1024);
                for (; temp2 > 1023; temp1--)
                {
                    temp2 = Convert.ToUInt64((value * Math.Pow(2, temp1 - 1) - 1) * 1024);
                }
                sp = Convert.ToUInt16(temp2);
                UInt16 temp3 = Convert.ToUInt16((-1 * temp1) + 15);
                pow = Convert.ToUInt16(temp3 << 10);
            }
            UInt16 U16 = Convert.ToUInt16(sign | sp | pow);
            return U16;
        }
    }
}
