/**
 * @file
 * @author [sunzhenliang](https://github.com/HiSunzhenliang)
 * @brief A-law algorithm for encoding and decoding (16bit pcm <=> a-law).
 * This is the implementation of [G.711](https://en.wikipedia.org/wiki/G.711)
 * in C.
 **/

/**
 * Linear input code | Compressed code | Linear output code
 * ------------------+-----------------+-------------------
 * s0000000abcdx     | s000abcd        | s0000000abcd1
 * s0000001abcdx     | s001abcd        | s0000001abcd1
 * s000001abcdxx     | s010abcd        | s000001abcd10
 * s00001abcdxxx     | s011abcd        | s00001abcd100
 * s0001abcdxxxx     | s100abcd        | s0001abcd1000
 * s001abcdxxxxx     | s101abcd        | s001abcd10000
 * s01abcdxxxxxx     | s110abcd        | s01abcd100000
 * s1abcdxxxxxxx     | s111abcd        | s1abcd1000000
 *
 * Compressed code: (s | eee | abcd)
 **/
#include <assert.h>    /// for assert
#include <inttypes.h>  /// for appropriate size int types
#include <stdio.h>     /// for IO operations

/**
 * @brief 16bit pcm to 8bit alaw
 * @param out unsigned 8bit alaw array
 * @param in  signed 16bit pcm array
 * @param len length of pcm array
 * @returns void
 */
void encode(uint8_t *out, int16_t *in, size_t len)
{
    uint8_t alaw = 0;
    int16_t pcm = 0;
    int32_t sign = 0;
    int32_t abcd = 0;
    int32_t eee = 0;
    int32_t mask = 0;
    for (size_t i = 0; i < len; i++)
    {
        pcm = *in++;
        /* 0-7 kinds of quantization level from the table above */
        eee = 7;
        mask = 0x4000; /* 0x4000: '0b0100 0000 0000 0000' */

        /* Get sign bit */
        sign = (pcm & 0x8000) >> 8;

        /* Turn negative pcm to positive */
        /* The absolute value of a negative number may be larger than the size
         * of the corresponding positive number, so here needs `-pcm -1` after
         * taking the opposite number. */
        pcm = sign ? (-pcm - 1) : pcm;

        /* Get eee and abcd bit */
        /* Use mask to locate the first `1` bit and quantization level at the
         * same time */
        while ((pcm & mask) == 0 && eee > 0)
        {
            eee--;
            mask >>= 1;
        }

        /* The location of abcd bits is related with quantization level. Check
         * the table above to determine how many bits to `>>` to get abcd */
        abcd = (pcm >> (eee ? (eee + 3) : 4)) & 0x0f;

        /* Put the quantization level number at right bit location to get eee
         * bits */
        eee <<= 4;

        /* Splice results */
        alaw = (sign | eee | abcd);

        /* The standard specifies that all resulting even bits (LSB
         * is even) are inverted before the octet is transmitted. This is to
         * provide plenty of 0/1 transitions to facilitate the clock recovery
         * process in the PCM receivers. Thus, a silent A-law encoded PCM
         * channel has the 8 bit samples coded 0xD5 instead of 0x80 in the
         * octets. (Reference from wiki above) */
        *out++ = alaw ^ 0xD5;
    }
}

/**
 * @brief 8bit alaw to 16bit pcm
 * @param out signed 16bit pcm array
 * @param in  unsigned 8bit alaw array
 * @param len length of alaw array
 * @returns void
 */
void decode(int16_t *out, uint8_t *in, size_t len)
{
    uint8_t alaw = 0;
    int32_t pcm = 0;
    int32_t sign = 0;
    int32_t eee = 0;
    for (size_t i = 0; i < len; i++)
    {
        alaw = *in++;

        /* Re-toggle toggled bits */
        alaw ^= 0xD5;

        /* Get sign bit */
        sign = alaw & 0x80;

        /* Get eee bits */
        eee = (alaw & 0x70) >> 4;

        /* Get abcd bits and add 1/2 quantization step */
        pcm = (alaw & 0x0f) << 4 | 8;

        /* If quantization level > 0, there need `1` bit before abcd bits */
        pcm += eee ? 0x100 : 0x0;

        /* Left shift according quantization level */
        pcm <<= eee > 1 ? (eee - 1) : 0;

        /* Use the right sign */
        *out++ = sign ? -pcm : pcm;
    }
}

/**
 * @brief Encode a single 16bit PCM sample to 8bit A-law
 * @param pcm_sample signed 16bit pcm value
 * @returns encoded 8bit A-law value
 */
uint8_t encode_single(int16_t pcm_sample)
{
    uint8_t result;
    encode(&result, &pcm_sample, 1);
    return result;
}

/**
 * @brief Decode a single 8bit A-law sample to 16bit PCM
 * @param alaw_sample unsigned 8bit A-law value
 * @returns decoded 16bit PCM value
 */
int16_t decode_single(uint8_t alaw_sample)
{
    int16_t result;
    decode(&result, &alaw_sample, 1);
    return result;
}

/**
 * @brief Compare two PCM arrays for equality
 * @param arr1 first PCM array
 * @param arr2 second PCM array
 * @param len length of arrays
 * @returns 1 if arrays are equal, 0 otherwise
 */
int pcm_arrays_equal(int16_t *arr1, int16_t *arr2, size_t len)
{
    for (size_t i = 0; i < len; i++)
    {
        if (arr1[i] != arr2[i])
        {
            return 0;
        }
    }
    return 1;
}

/**
 * @brief Compare two A-law arrays for equality
 * @param arr1 first A-law array
 * @param arr2 second A-law array
 * @param len length of arrays
 * @returns 1 if arrays are equal, 0 otherwise
 */
int alaw_arrays_equal(uint8_t *arr1, uint8_t *arr2, size_t len)
{
    for (size_t i = 0; i < len; i++)
    {
        if (arr1[i] != arr2[i])
        {
            return 0;
        }
    }
    return 1;
}

/**
 * @brief Check if decoded PCM is within acceptable tolerance of original
 * @param original original PCM array
 * @param decoded decoded PCM array
 * @param len length of arrays
 * @param tolerance maximum allowed difference per sample
 * @returns 1 if within tolerance, 0 otherwise
 */
int pcm_within_tolerance(int16_t *original, int16_t *decoded, size_t len, int16_t tolerance)
{
    for (size_t i = 0; i < len; i++)
    {
        int32_t diff = original[i] - decoded[i];
        if (diff < 0) diff = -diff;
        if (diff > tolerance)
        {
            return 0;
        }
    }
    return 1;
}

/**
 * @brief Verify encode-decode roundtrip is within acceptable loss
 * @param pcm_input original PCM array
 * @param len length of array
 * @param tolerance maximum allowed difference per sample after roundtrip
 * @returns 1 if roundtrip is within tolerance, 0 otherwise
 */
int verify_roundtrip(int16_t *pcm_input, size_t len, int16_t tolerance)
{
    if (len == 0) return 1;

    /* Allocate temporary buffers on stack for small arrays */
    uint8_t encoded[256];
    int16_t decoded[256];

    /* For larger arrays, we'd need dynamic allocation, but 256 is reasonable for tests */
    if (len > 256) return 0;

    encode(encoded, pcm_input, len);
    decode(decoded, encoded, len);

    return pcm_within_tolerance(pcm_input, decoded, len, tolerance);
}

/**
 * @brief Get the quantization level (eee bits) from an A-law sample
 * @param alaw_sample the A-law encoded sample
 * @returns quantization level (0-7)
 */
int get_quantization_level(uint8_t alaw_sample)
{
    /* Re-toggle the bits first */
    uint8_t alaw = alaw_sample ^ 0xD5;
    return (alaw & 0x70) >> 4;
}

/**
 * @brief Get the sign bit from an A-law sample
 * @param alaw_sample the A-law encoded sample
 * @returns 1 if negative, 0 if positive
 */
int get_alaw_sign(uint8_t alaw_sample)
{
    uint8_t alaw = alaw_sample ^ 0xD5;
    return (alaw & 0x80) ? 1 : 0;
}

/**
 * @brief Get the mantissa (abcd bits) from an A-law sample
 * @param alaw_sample the A-law encoded sample
 * @returns mantissa value (0-15)
 */
int get_alaw_mantissa(uint8_t alaw_sample)
{
    uint8_t alaw = alaw_sample ^ 0xD5;
    return alaw & 0x0f;
}
