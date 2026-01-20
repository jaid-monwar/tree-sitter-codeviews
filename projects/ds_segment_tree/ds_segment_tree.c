/**
 * @file segment_tree.c
 * @brief segment trees with only point updates
 * @details
 * This code implements segment trees. Segment trees are general structures
 * which allow range based queries in a given array in logN time.
 * Segment tree with point updates allow update of single element in the array
 * in logN time.
 * [Learn more about segment trees
 * here](https://codeforces.com/blog/entry/18051)
 * @author [Lakhan Nad](https://github.com/Lakhan-Nad)
 */

#include <assert.h>   /* for assert */
#include <inttypes.h> /* for int32 */
#include <stdio.h>    /* for scanf printf */
#include <stdlib.h>   /* for malloc, free */
#include <string.h>   /* for memcpy, memset */

/**
 * Function that combines two data to generate a new one
 * The name of function might be misleading actually combine here signifies the
 * fact that in segment trees we take partial result from two ranges and using
 * partial results we derive the result for joint range of those two ranges
 * For Example: array(1,2,3,4,5,6) sum of range [0,2] = 6
 * and sum of range [3,5] = 15 the combined sum of two range is 6+15=21
 * @note The function is same to binary function in Discrete Mathematics
 * @param a pointer to first data
 * @param b pointer to second data
 * @param result pointer to memory location where result of combining a and b is
 * to be stored
 */
typedef void (*combine_function)(const void *a, const void *b, void *result);

/**
 * This structures holds all the data that is required by a segment tree
 */
typedef struct segment_tree
{
    void *root;       /**< the root of formed segment tree */
    void *identity;   /**< identity element for combine function */
    size_t elem_size; /**< size in bytes of each data element */
    size_t length;    /**< total size of array which segment tree represents*/
    /** the function to be used to combine two node's
     * data to form parent's data
     */
    combine_function combine;
} segment_tree;

/**
 * Builds a Segment tree
 * It is assumed that leaves of tree already contains data.
 * @param tree pointer to segment tree to be build
 */
void segment_tree_build(segment_tree *tree)
{
    size_t elem_size = tree->elem_size;
    int index = (tree->length - 2);
    size_t b, l, r;
    char *ptr = (char *)tree->root;
    for (; index >= 0; index--)
    {
        b = index * elem_size;
        l = (2 * index + 1) * elem_size;
        r = (2 * index + 2) * elem_size;
        tree->combine(ptr + l, ptr + r, ptr + b);
    }
}

/**
 * For point updates
 * This function updates the element at given index and also updates segment
 * tree accordingly
 *
 * @param tree pointer to segment tree
 * @param index the index whose element is to be updated (0 based indexing used)
 * @param val pointer to value that is to be replaced at given index
 */
void segment_tree_update(segment_tree *tree, size_t index, void *val)
{
    size_t elem_size = tree->elem_size;
    index = index + tree->length - 1;
    char *base = (char *)tree->root;
    char *t = base + index * elem_size;
    memcpy(t, val, elem_size);
    while (index > 0)
    {
        index = ((index - 1) >> 1);
        tree->combine(base + (2 * index + 1) * elem_size,
                      base + (2 * index + 2) * elem_size,
                      base + index * elem_size);
    }
}

/**
 * Query the segment tree
 * This function helps in range query of segment tree
 * This function assumes that the given range is valid
 * Performs the query in range [l,r]
 * @param tree pointer to segment tree
 * @param l the start of range
 * @param r the end of range
 * @param res the pointer to memory where result of query is stored
 */
void segment_tree_query(segment_tree *tree, long long l, long long r, void *res)
{
    size_t elem_size = tree->elem_size;
    memcpy(res, tree->identity, elem_size);
    elem_size = tree->elem_size;
    char *root = (char *)tree->root;
    l += tree->length - 1;
    r += tree->length - 1;
    while (l <= r)
    {
        if (!(l & 1))
        {
            tree->combine(res, root + l * elem_size, res);
        }
        if (r & 1)
        {
            tree->combine(res, root + r * elem_size, res);
        }
        r = (r >> 1) - 1;
        l = (l >> 1);
    }
}

/**
 * Initializes Segment Tree
 * Accquires memory for segment tree
 * and fill the leaves of segment tree with data from array
 * @param arr the array data upon which segment tree is build
 * @param elem_size size of each element in segment tree
 * @param len total no of elements in array
 * @param identity the identity element for combine_function
 * @param func the combine_function used to build segment tree
 *
 * @returns pointer to sgement tree build
 */
segment_tree *segment_tree_init(void *arr, size_t elem_size, size_t len,
                                void *identity, combine_function func)
{
    segment_tree *tree = malloc(sizeof(segment_tree));
    tree->elem_size = elem_size;
    tree->length = len;
    tree->combine = func;
    tree->root = malloc(sizeof(char) * elem_size * (2 * len - 1));
    tree->identity = malloc(sizeof(char) * elem_size);
    char *ptr = (char *)tree->root;
    memset(ptr, 0, (len - 1) * elem_size);  // Initializing memory
    ptr = ptr + (len - 1) * elem_size;
    memcpy(ptr, arr, elem_size * len);  // copy the leaf nodes i.e. array data
    memcpy(tree->identity, identity, elem_size);  // copy identity element
    return tree;
}

/**
 * Dispose Segment Tree
 * Frees all heap memory accquired by segment tree
 * @param tree pointer to segment tree
 */
void segment_tree_dispose(segment_tree *tree)
{
    free(tree->root);
    free(tree->identity);
}

/**
 * Prints the data in segment tree
 * The data should be of int type
 * A utility to print segment tree
 * with data type of int
 * @param tree pointer to segment tree
 */
void segment_tree_print_int(segment_tree *tree)
{
    char *base = (char *)tree->root;
    size_t i = 0;
    for (; i < 2 * tree->length - 1; i++)
    {
        printf("%d ", *(int *)(base + i * tree->elem_size));
    }
    printf("\n");
}

/**
 * Common combine functions for segment trees
 */

/**
 * Combine function for minimum (RMQ - Range Minimum Query)
 * @param a pointer to integer a
 * @param b pointer to integer b
 * @param c pointer where minimum of a and b is stored as result
 */
void combine_minimum(const void *a, const void *b, void *c)
{
    *(int *)c = *(int *)a < *(int *)b ? *(int *)a : *(int *)b;
}

/**
 * Combine function for maximum (RMaxQ - Range Maximum Query)
 * @param a pointer to integer a
 * @param b pointer to integer b
 * @param c pointer where maximum of a and b is stored as result
 */
void combine_maximum(const void *a, const void *b, void *c)
{
    *(int *)c = *(int *)a > *(int *)b ? *(int *)a : *(int *)b;
}

/**
 * Combine function for sum (Range Sum Query)
 * @param a pointer to integer a
 * @param b pointer to integer b
 * @param c pointer where sum of a and b is stored as result
 */
void combine_sum(const void *a, const void *b, void *c)
{
    *(int *)c = *(int *)a + *(int *)b;
}

/**
 * Utility functions for testing
 */

/**
 * Get the length of the array represented by the segment tree
 * @param tree pointer to segment tree
 * @returns length of the array, or 0 if tree is NULL
 */
size_t segment_tree_get_length(segment_tree *tree)
{
    if (tree == NULL)
    {
        return 0;
    }
    return tree->length;
}

/**
 * Get the element size of the segment tree
 * @param tree pointer to segment tree
 * @returns element size in bytes, or 0 if tree is NULL
 */
size_t segment_tree_get_elem_size(segment_tree *tree)
{
    if (tree == NULL)
    {
        return 0;
    }
    return tree->elem_size;
}

/**
 * Get the total number of nodes in the segment tree
 * @param tree pointer to segment tree
 * @returns total number of nodes (2*length - 1), or 0 if tree is NULL
 */
size_t segment_tree_get_node_count(segment_tree *tree)
{
    if (tree == NULL)
    {
        return 0;
    }
    return 2 * tree->length - 1;
}

/**
 * Get the value at a specific index in the original array
 * @param tree pointer to segment tree
 * @param index the index in the original array (0-based)
 * @param result pointer to memory where result is stored
 * @returns 0 on success, -1 on failure (NULL tree or out of bounds)
 */
int segment_tree_get_element(segment_tree *tree, size_t index, void *result)
{
    if (tree == NULL || result == NULL || index >= tree->length)
    {
        return -1;
    }
    size_t elem_size = tree->elem_size;
    size_t tree_index = index + tree->length - 1;
    char *base = (char *)tree->root;
    memcpy(result, base + tree_index * elem_size, elem_size);
    return 0;
}

/**
 * Get the root value of the segment tree (result of combining all elements)
 * @param tree pointer to segment tree
 * @param result pointer to memory where result is stored
 * @returns 0 on success, -1 on failure (NULL tree)
 */
int segment_tree_get_root_value(segment_tree *tree, void *result)
{
    if (tree == NULL || result == NULL || tree->root == NULL)
    {
        return -1;
    }
    memcpy(result, tree->root, tree->elem_size);
    return 0;
}

/**
 * Check if segment tree is valid (properly initialized)
 * @param tree pointer to segment tree
 * @returns 1 if valid, 0 if invalid or NULL
 */
int segment_tree_is_valid(segment_tree *tree)
{
    if (tree == NULL)
    {
        return 0;
    }
    if (tree->root == NULL || tree->identity == NULL)
    {
        return 0;
    }
    if (tree->elem_size == 0 || tree->length == 0)
    {
        return 0;
    }
    if (tree->combine == NULL)
    {
        return 0;
    }
    return 1;
}

/**
 * Get the identity element value
 * @param tree pointer to segment tree
 * @param result pointer to memory where identity is stored
 * @returns 0 on success, -1 on failure
 */
int segment_tree_get_identity(segment_tree *tree, void *result)
{
    if (tree == NULL || result == NULL || tree->identity == NULL)
    {
        return -1;
    }
    memcpy(result, tree->identity, tree->elem_size);
    return 0;
}

/**
 * Perform a safe query with bounds checking
 * @param tree pointer to segment tree
 * @param l the start of range (0-based, inclusive)
 * @param r the end of range (0-based, inclusive)
 * @param res pointer to memory where result of query is stored
 * @returns 0 on success, -1 on failure (invalid range or NULL)
 */
int segment_tree_query_safe(segment_tree *tree, size_t l, size_t r, void *res)
{
    if (tree == NULL || res == NULL)
    {
        return -1;
    }
    if (l > r || r >= tree->length)
    {
        return -1;
    }
    segment_tree_query(tree, (long long)l, (long long)r, res);
    return 0;
}

/**
 * Perform a safe update with bounds checking
 * @param tree pointer to segment tree
 * @param index the index to update (0-based)
 * @param val pointer to value to set at index
 * @returns 0 on success, -1 on failure (out of bounds or NULL)
 */
int segment_tree_update_safe(segment_tree *tree, size_t index, void *val)
{
    if (tree == NULL || val == NULL)
    {
        return -1;
    }
    if (index >= tree->length)
    {
        return -1;
    }
    segment_tree_update(tree, index, val);
    return 0;
}
