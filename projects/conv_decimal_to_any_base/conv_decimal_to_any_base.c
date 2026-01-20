/**
 * @file
 * @author [jucollet972](https://github.com/jucollet972)
 * @brief [Decimal to any-base](http://codeofthedamned.com/index.php/number-base-conversion) is a C function wich convert positive decimal
 * integer to any positive ascii base with the base's alphabet given in input and return it in a dynamically allocated string(recursive way)
 */

#include <string.h>  /// for strchr and strlen
#include <stdint.h>  /// for CPU arch's optimized int types
#include <stdbool.h> /// for boolean types
#include <stdlib.h>  /// for malloc and free

/**
 * @brief Checking if alphabet is valid
 * @param base alphabet inputed by user
 * @return int64_t as success or not
 */
bool isbad_alphabet(const char* alphabet) {
	if (alphabet == NULL) {
		return true;
	}
	uint64_t len = strlen(alphabet);

	/* Checking the length */
	if (len < 2) {
		return true;
	}
	/* Browse the alphabet */
	for (uint64_t i = 0; i < len ; i++) {
		/* Searching for duplicates */
		if (strchr(alphabet + i + 1, alphabet[i]))
			return true;
	}
	return false;
}

/**
 * @brief Calculate the final length of the converted number
 * @param nb to convert
 * @param base calculated from alphabet
 * @return Converted nb string length 
 */
uint64_t converted_len(uint64_t nb, uint64_t base) {
	/* Counting the number of characters translated to the base*/
	if (nb > base - 1) {
		return (converted_len(nb/base, base) + 1);
	}
	return 1;
}

/**
 * @brief Convert positive decimal integer into anybase recursively
 * @param nb to convert
 * @param alphabet inputed by user used for base convertion
 * @param base calculated from alphabet
 * @param converted string filled with the convertion's result
 * @return void
 */
void convertion(uint64_t nb, const char* alphabet, uint64_t base, char* converted) {
	/* Recursive convertion */
	*(converted) = *(alphabet + nb%base);
	if (nb > base - 1) {
		convertion(nb/base, alphabet, base, --converted);
	}
}

/**
 * @brief decimal_to_anybase ensure the validity of the parameters and convert any unsigned integers into any ascii positive base
 * @param nb to convert
 * @param base's alphabet
 * @returns nb converted on success
 * @returns NULL on error
 */
char* decimal_to_anybase(uint64_t nb, const char* alphabet) {
	char* converted;

	/* Verify that alphabet is valid */
	if (isbad_alphabet(alphabet)) {
		return NULL;
	}
	/* Convertion */
	uint64_t base = strlen(alphabet);
	uint64_t final_len = converted_len(nb, base);
	converted = malloc(sizeof(char) * (final_len + 1));
	converted[final_len] = 0;
	convertion(nb, alphabet, base, converted + final_len - 1);
	return converted;
}


/**
 * @brief Get the length of a converted number string
 * @param nb number to convert
 * @param alphabet base alphabet
 * @return length of converted string, 0 if alphabet is invalid
 */
uint64_t get_converted_length(uint64_t nb, const char* alphabet) {
	if (alphabet == NULL || isbad_alphabet(alphabet)) {
		return 0;
	}
	uint64_t base = strlen(alphabet);
	return converted_len(nb, base);
}

/**
 * @brief Check if two converted numbers are equal
 * @param nb1 first number
 * @param nb2 second number
 * @param alphabet base alphabet
 * @return true if conversions are equal, false otherwise
 */
bool conversions_equal(uint64_t nb1, uint64_t nb2, const char* alphabet) {
	char* conv1 = decimal_to_anybase(nb1, alphabet);
	char* conv2 = decimal_to_anybase(nb2, alphabet);

	if (conv1 == NULL || conv2 == NULL) {
		if (conv1) free(conv1);
		if (conv2) free(conv2);
		return (conv1 == NULL && conv2 == NULL);
	}

	bool result = (strcmp(conv1, conv2) == 0);
	free(conv1);
	free(conv2);
	return result;
}

/**
 * @brief Convert and compare with expected string
 * @param nb number to convert
 * @param alphabet base alphabet
 * @param expected expected result string
 * @return true if conversion matches expected, false otherwise
 */
bool conversion_matches(uint64_t nb, const char* alphabet, const char* expected) {
	if (expected == NULL) {
		return false;
	}

	char* result = decimal_to_anybase(nb, alphabet);
	if (result == NULL) {
		return false;
	}

	bool matches = (strcmp(result, expected) == 0);
	free(result);
	return matches;
}

/**
 * @brief Get the base size from an alphabet
 * @param alphabet base alphabet string
 * @return base size, 0 if invalid
 */
uint64_t get_base_size(const char* alphabet) {
	if (alphabet == NULL || isbad_alphabet(alphabet)) {
		return 0;
	}
	return strlen(alphabet);
}

/**
 * @brief Check if an alphabet is valid for conversion
 * @param alphabet base alphabet string
 * @return true if valid, false if invalid
 */
bool is_valid_alphabet(const char* alphabet) {
	if (alphabet == NULL) {
		return false;
	}
	return !isbad_alphabet(alphabet);
}
