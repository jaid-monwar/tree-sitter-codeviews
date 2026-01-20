/**
 * @file
 * @brief [Longest Common
 * Subsequence](https://en.wikipedia.org/wiki/Longest_common_subsequence_problem)
 * algorithm
 * @details
 * From Wikipedia: The longest common subsequence (LCS) problem is the problem
 * of finding the longest subsequence common to all sequences in a set of
 * sequences (often just two sequences).
 * @author [Kurtz](https://github.com/itskurtz)
 */

#include <stdio.h>		/* for io operations */
#include <stdlib.h>		/* for memory management & exit */
#include <string.h>		/* for string manipulation & ooperations */
#include <assert.h>		/* for asserts */

enum {LEFT, UP, DIAG};

/**
 * @brief Computes LCS between s1 and s2 using a dynamic-programming approach
 * @param s1 first null-terminated string
 * @param s2 second null-terminated string
 * @param l1 length of s1
 * @param l2 length of s2
 * @param L matrix of size l1 x l2
 * @param B matrix of size l1 x l2
 * @returns void
 */
void lcslen(const char *s1, const char *s2, int l1, int l2, int **L, int **B) {
	/* B is the directions matrix
	   L is the LCS matrix */
	int i, j;

	/* loop over the simbols in my sequences
	   save the directions according to the LCS */
	for (i = 1; i <= l1; ++i) {
		for (j = 1; j <= l2; ++j) {
			if (s1[i-1] == s2[j-1]) {
				L[i][j] = 1 + L[i-1][j-1];
				B[i][j] = DIAG;
			}
			else if (L[i-1][j] < L[i][j-1]) {
				L[i][j] = L[i][j-1];
				B[i][j] = LEFT;
			}
			else {
				L[i][j] = L[i-1][j];
				B[i][j] = UP;
            }
		}
	}
}

/**
 * @brief Builds the LCS according to B using a traceback approach
 * @param s1 first null-terminated string
 * @param l1 length of s1
 * @param l2 length of s2
 * @param L matrix of size l1 x l2
 * @param B matrix of size l1 x l2
 * @returns lcs longest common subsequence
 */
char *lcsbuild(const char *s1, int l1, int l2, int **L, int **B) {
	int	 i, j, lcsl;
	char	*lcs;
	lcsl = L[l1][l2];
	
	/* my lcs is at least the empty symbol */
	lcs = (char *)calloc(lcsl+1, sizeof(char)); /* null-terminated \0 */
	if (!lcs) {
		perror("calloc: ");
		return NULL;
	}

	i = l1, j = l2;
	while (i > 0 && j > 0) {
		/* walk the matrix backwards */
		if (B[i][j] == DIAG) {
			lcs[--lcsl] = s1[i-1];
			i = i - 1;
			j = j - 1;
		}
        else if (B[i][j] == LEFT)
        {
            j = j - 1;
		}
        else
        {
            i = i - 1;
        }
	}
	return lcs;
}

/**
 * @brief Allocates and initializes a 2D matrix of integers
 * @param rows number of rows
 * @param cols number of columns
 * @returns pointer to allocated matrix, or NULL on failure
 */
int **allocate_matrix(int rows, int cols) {
	int **matrix = (int **)calloc(rows, sizeof(int *));
	if (!matrix) {
		return NULL;
	}
	for (int i = 0; i < rows; i++) {
		matrix[i] = (int *)calloc(cols, sizeof(int));
		if (!matrix[i]) {
			for (int j = 0; j < i; j++) {
				free(matrix[j]);
			}
			free(matrix);
			return NULL;
		}
	}
	return matrix;
}

/**
 * @brief Frees a 2D matrix of integers
 * @param matrix pointer to the matrix
 * @param rows number of rows
 */
void free_matrix(int **matrix, int rows) {
	if (!matrix) {
		return;
	}
	for (int i = 0; i < rows; i++) {
		free(matrix[i]);
	}
	free(matrix);
}

/**
 * @brief Gets the LCS length from the L matrix
 * @param L the LCS length matrix
 * @param l1 length of first string
 * @param l2 length of second string
 * @returns LCS length
 */
int get_lcs_length(int **L, int l1, int l2) {
	if (!L) {
		return -1;
	}
	return L[l1][l2];
}

/**
 * @brief Computes and returns the LCS of two strings
 * @param s1 first null-terminated string
 * @param s2 second null-terminated string
 * @param out_length pointer to store the LCS length (can be NULL)
 * @returns newly allocated LCS string, or NULL on failure
 */
char *compute_lcs(const char *s1, const char *s2, int *out_length) {
	if (!s1 || !s2) {
		return NULL;
	}

	int l1 = strlen(s1);
	int l2 = strlen(s2);

	int **L = allocate_matrix(l1 + 1, l2 + 1);
	int **B = allocate_matrix(l1 + 1, l2 + 1);

	if (!L || !B) {
		free_matrix(L, l1 + 1);
		free_matrix(B, l1 + 1);
		return NULL;
	}

	lcslen(s1, s2, l1, l2, L, B);

	if (out_length) {
		*out_length = L[l1][l2];
	}

	char *lcs = lcsbuild(s1, l1, l2, L, B);

	free_matrix(L, l1 + 1);
	free_matrix(B, l1 + 1);

	return lcs;
}

/**
 * @brief Checks if a string is a valid subsequence of another
 * @param subsequence the potential subsequence
 * @param original the original string
 * @returns 1 if valid subsequence, 0 otherwise
 */
int is_valid_subsequence(const char *subsequence, const char *original) {
	if (!subsequence || !original) {
		return 0;
	}

	int sub_len = strlen(subsequence);
	int orig_len = strlen(original);

	if (sub_len == 0) {
		return 1;
	}
	if (sub_len > orig_len) {
		return 0;
	}

	int sub_idx = 0;
	for (int i = 0; i < orig_len && sub_idx < sub_len; i++) {
		if (original[i] == subsequence[sub_idx]) {
			sub_idx++;
		}
	}

	return sub_idx == sub_len;
}

/**
 * @brief Checks if a string is a common subsequence of two strings
 * @param subsequence the potential common subsequence
 * @param s1 first string
 * @param s2 second string
 * @returns 1 if valid common subsequence, 0 otherwise
 */
int is_common_subsequence(const char *subsequence, const char *s1, const char *s2) {
	return is_valid_subsequence(subsequence, s1) &&
	       is_valid_subsequence(subsequence, s2);
}

/**
 * @brief Verifies that a computed LCS is correct
 * @param s1 first string
 * @param s2 second string
 * @param lcs the computed LCS
 * @param expected_length expected length of LCS
 * @returns 1 if LCS is valid, 0 otherwise
 */
int verify_lcs(const char *s1, const char *s2, const char *lcs, int expected_length) {
	if (!lcs) {
		return 0;
	}

	int lcs_len = strlen(lcs);

	if (lcs_len != expected_length) {
		return 0;
	}

	return is_common_subsequence(lcs, s1, s2);
}

/**
 * @brief Gets the direction value at a specific position in the B matrix
 * @param B the directions matrix
 * @param i row index
 * @param j column index
 * @returns direction value (LEFT, UP, or DIAG), or -1 on error
 */
int get_direction(int **B, int i, int j) {
	if (!B || i < 0 || j < 0) {
		return -1;
	}
	return B[i][j];
}

/**
 * @brief Gets the LCS value at a specific position in the L matrix
 * @param L the LCS length matrix
 * @param i row index
 * @param j column index
 * @returns LCS length value at position, or -1 on error
 */
int get_lcs_value(int **L, int i, int j) {
	if (!L || i < 0 || j < 0) {
		return -1;
	}
	return L[i][j];
}

