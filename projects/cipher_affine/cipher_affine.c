/**
 * @file
 * @brief An [affine cipher](https://en.wikipedia.org/wiki/Affine_cipher) is a
 * letter substitution cipher that uses a linear transformation to substitute
 * letters in a message.
 * @details Given an alphabet of length M with characters with numeric values
 * 0-(M-1), an arbitrary character x can be transformed with the expression (ax
 * + b) % M into our ciphertext character. The only caveat is that a must be
 * relatively prime with M in order for this transformation to be invertible,
 * i.e., gcd(a, M) = 1.
 * @author [Daniel Murrow](https://github.com/dsmurrow)
 */

#include <assert.h>  /// for assertions
#include <stdio.h>   /// for IO
#include <stdlib.h>  /// for div function and div_t struct as well as malloc and free
#include <string.h>  /// for strlen, strcpy, and strcmp

/**
 * @brief number of characters in our alphabet (printable ASCII characters)
 */
#define ALPHABET_SIZE 95

/**
 * @brief used to convert a printable byte (32 to 126) to an element of the
 * group Z_95 (0 to 94)
 */
#define Z95_CONVERSION_CONSTANT 32

/**
 * @brief a structure representing an affine cipher key
 */
typedef struct
{
    int a;  ///< what the character is being multiplied by
    int b;  ///< what is being added after the multiplication with `a`
} affine_key_t;

/**
 * @brief finds the value x such that (a * x) % m = 1
 *
 * @param a number we are finding the inverse for
 * @param m the modulus the inversion is based on
 *
 * @returns the modular multiplicative inverse of `a` mod `m`
 */
int modular_multiplicative_inverse(unsigned int a, unsigned int m)
{
    int x[2] = {1, 0};
    div_t div_result;

    if (m == 0) {
        return 0;
    }
    a %= m;
    if (a == 0) {
        return 0;
    }

    div_result.rem = a;

    while (div_result.rem > 0)
    {
        div_result = div(m, a);

        m = a;
        a = div_result.rem;

        // Calculate value of x for this iteration
        int next = x[1] - (x[0] * div_result.quot);

        x[1] = x[0];
        x[0] = next;
    }

    return x[1];
}

/**
 * @brief Given a valid affine cipher key, this function will produce the
 * inverse key.
 *
 * @param key They key to be inverted
 *
 * @returns inverse of key
 */
affine_key_t inverse_key(affine_key_t key)
{
    affine_key_t inverse;

    inverse.a = modular_multiplicative_inverse(key.a, ALPHABET_SIZE);

    // Turn negative results positive
    inverse.a += ALPHABET_SIZE;
    inverse.a %= ALPHABET_SIZE;

    inverse.b = -(key.b % ALPHABET_SIZE) + ALPHABET_SIZE;

    return inverse;
}

/**
 * @brief Encrypts character string `s` with key
 *
 * @param s string to be encrypted
 * @param key affine key used for encryption
 *
 * @returns void
 */
void affine_encrypt(char *s, affine_key_t key)
{
    for (int i = 0; s[i] != '\0'; i++)
    {
        int c = (int)s[i] - Z95_CONVERSION_CONSTANT;

        c *= key.a;
        c += key.b;
        c %= ALPHABET_SIZE;

        s[i] = (char)(c + Z95_CONVERSION_CONSTANT);
    }
}

/**
 * @brief Decrypts an affine ciphertext
 *
 * @param s string to be decrypted
 * @param key Key used when s was encrypted
 *
 * @returns void
 */
void affine_decrypt(char *s, affine_key_t key)
{
    affine_key_t inverse = inverse_key(key);

    for (int i = 0; s[i] != '\0'; i++)
    {
        int c = (int)s[i] - Z95_CONVERSION_CONSTANT;

        c += inverse.b;
        c *= inverse.a;
        c %= ALPHABET_SIZE;

        s[i] = (char)(c + Z95_CONVERSION_CONSTANT);
    }
}

/**
 * @brief Computes the greatest common divisor of two numbers
 *
 * @param a first number
 * @param b second number
 *
 * @returns the GCD of a and b
 */
int gcd(int a, int b)
{
    if (a < 0) a = -a;
    if (b < 0) b = -b;
    while (b != 0)
    {
        int temp = b;
        b = a % b;
        a = temp;
    }
    return a;
}

/**
 * @brief Checks if a key is valid for the affine cipher
 * A valid key requires gcd(key.a, ALPHABET_SIZE) == 1
 *
 * @param key the affine key to validate
 *
 * @returns 1 if key is valid, 0 otherwise
 */
int is_valid_key(affine_key_t key)
{
    return gcd(key.a, ALPHABET_SIZE) == 1;
}

/**
 * @brief Creates an affine key with the given a and b values
 *
 * @param a the multiplier (must be coprime with ALPHABET_SIZE)
 * @param b the additive constant
 *
 * @returns the created affine_key_t structure
 */
affine_key_t create_key(int a, int b)
{
    affine_key_t key;
    key.a = a;
    key.b = b;
    return key;
}

/**
 * @brief Encrypts a string and returns a newly allocated copy
 * The caller is responsible for freeing the returned string
 *
 * @param s the string to encrypt (not modified)
 * @param key the affine key for encryption
 *
 * @returns newly allocated encrypted string, or NULL on failure
 */
char *affine_encrypt_copy(const char *s, affine_key_t key)
{
    if (s == NULL)
    {
        return NULL;
    }

    size_t len = strlen(s);
    char *copy = malloc((len + 1) * sizeof(char));
    if (copy == NULL)
    {
        return NULL;
    }

    strcpy(copy, s);
    affine_encrypt(copy, key);
    return copy;
}

/**
 * @brief Decrypts a string and returns a newly allocated copy
 * The caller is responsible for freeing the returned string
 *
 * @param s the string to decrypt (not modified)
 * @param key the affine key used for original encryption
 *
 * @returns newly allocated decrypted string, or NULL on failure
 */
char *affine_decrypt_copy(const char *s, affine_key_t key)
{
    if (s == NULL)
    {
        return NULL;
    }

    size_t len = strlen(s);
    char *copy = malloc((len + 1) * sizeof(char));
    if (copy == NULL)
    {
        return NULL;
    }

    strcpy(copy, s);
    affine_decrypt(copy, key);
    return copy;
}

/**
 * @brief Checks if encryption followed by decryption returns original string
 *
 * @param s the original string
 * @param key the affine key to test
 *
 * @returns 1 if round-trip successful, 0 otherwise
 */
int verify_round_trip(const char *s, affine_key_t key)
{
    if (s == NULL)
    {
        return 0;
    }

    char *encrypted = affine_encrypt_copy(s, key);
    if (encrypted == NULL)
    {
        return 0;
    }

    char *decrypted = affine_decrypt_copy(encrypted, key);
    free(encrypted);

    if (decrypted == NULL)
    {
        return 0;
    }

    int result = (strcmp(s, decrypted) == 0);
    free(decrypted);
    return result;
}

/**
 * @brief Checks if a character is within the valid printable ASCII range
 *
 * @param c the character to check
 *
 * @returns 1 if valid (32-126), 0 otherwise
 */
int is_valid_char(char c)
{
    return (c >= 32 && c <= 126);
}

/**
 * @brief Checks if all characters in a string are valid for affine cipher
 *
 * @param s the string to check
 *
 * @returns 1 if all characters valid, 0 otherwise
 */
int is_valid_string(const char *s)
{
    if (s == NULL)
    {
        return 0;
    }

    for (int i = 0; s[i] != '\0'; i++)
    {
        if (!is_valid_char(s[i]))
        {
            return 0;
        }
    }
    return 1;
}
