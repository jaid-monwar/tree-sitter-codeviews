/**
 * @file
 * @brief This is a vector implemenation in C. A vector is an expandable array.
 * @details This vector implementation in C comes with some wrapper functions that lets the user work with data without having to worrying about memory.
 */

#include <stdio.h>     /// for IO operations
#include <stdlib.h>    /// for malloc() and free()
#include <assert.h>    /// for testing using assert()

/** This is the struct that defines the vector. */
typedef struct {
    int len;           ///< contains the length of the vector
    int current;       ///< holds the current item
    int* contents;     ///< the internal array itself
} Vector;

/**
 * This function initilaizes the vector and gives it a size of 1
 * and initializes the first index to 0.
 * @params Vector* (a pointer to the Vector struct)
 * @params int     (the actual data to be passed to the vector)
 * @returns 0 on success, -1 on failure
 */
int init(Vector* vec, int val) {
    if (vec == NULL) {
        return -1;
    }
    vec->contents = (int*)malloc(sizeof(int));
    if (vec->contents == NULL) {
        return -1;
    }
    vec->contents[0] = val;
    vec->current = 0;
    vec->len = 1;
    return 0;
}

/**
 * This function clears the heap memory allocated by the Vector.
 * @params Vector* (a pointer to the Vector struct)
 * @returns: none
 */
void delete(Vector* vec) {
    free(vec->contents);    
}

/**
 * This function clears the contents of the Vector.
 * @params Vector* (a pointer to the Vector struct)
 * @returns 0 on success, -1 on failure
 */
int clear(Vector* vec) {
    if (vec == NULL) {
        return -1;
    }
    delete(vec);
    return init(vec, 0);
}

/**
 * This function returns the length the Vector.
 * @params Vector* (a pointer to the Vector struct)
 * @returns: int
 */
int len(Vector* vec) {
    return vec->len;    
}

/**
 * This function pushes a value to the end of the Vector.
 * @params Vector* (a pointer to the Vector struct)
 * @params int     (the value to be pushed)
 * @returns 0 on success, -1 on failure
 */
int push(Vector* vec, int val) {
    if (vec == NULL || vec->contents == NULL) {
        return -1;
    }
    int* new_contents = realloc(vec->contents, (sizeof(int) * (vec->len + 1)));
    if (new_contents == NULL) {
        return -1;
    }
    vec->contents = new_contents;
    vec->contents[vec->len] = val;
    vec->len++;
    return 0;
}

/**
 * This function get the item at the specified index of the Vector.
 * @params Vector* (a pointer to the Vector struct)
 * @params int     (the index to get value from)
 * @returns: int
 */
int get(Vector* vec, int index) {
    if(index < vec->len) {
        return vec->contents[index];
    }
    return -1;
}

/**
 * This function sets an item at the specified index of the Vector.
 * @params Vector* (a pointer to the Vector struct)
 * @params int     (the index to set value at)
 * @returns: none
 */
void set(Vector* vec, int index, int val) {
    if(index < vec->len) {
        vec->contents[index] = val;
    }
}

/**
 * This function gets the next item from the Vector each time it's called.
 * @params Vector* (a pointer to the Vector struct)
 * @returns: int
 */
int next(Vector* vec) {
    if(vec->current == vec->len) {
        vec->current = 0;
    }
    int current_val = vec->contents[vec->current];
    vec->current++;
    return current_val;
}

/**
 * This function returns the pointer to the begining of the Vector.
 * @params Vector* (a pointer to the Vector struct)
 * @returns: void*
 */
void* begin(Vector* vec) {
    return (void*)vec->contents;
}

/**
 * This function prints the entire Vector as a list.
 * @params Vector* (a pointer to the Vector struct)
 * @returns: none
 */
void print(Vector* vec) {
    int size = vec->len;
    printf("[ ");
    for(int count = 0; count < size; count++) {
        printf("%d ", vec->contents[count]);
    }
    printf("]\n");
}

/**
 * This function converts the Vector to a string representation.
 * String-based alternative to print() for testing without stdout.
 * @params Vector* (a pointer to the Vector struct)
 * @params char* buffer (output buffer to write string to)
 * @params int buffer_size (size of the output buffer)
 * @returns number of characters written, or -1 on error
 */
int vector_to_string(Vector* vec, char* buffer, int buffer_size) {
    if (vec == NULL || buffer == NULL || buffer_size <= 0) {
        return -1;
    }
    int written = 0;
    int ret = snprintf(buffer + written, buffer_size - written, "[ ");
    if (ret < 0 || ret >= buffer_size - written) {
        return -1;
    }
    written += ret;

    for (int i = 0; i < vec->len; i++) {
        ret = snprintf(buffer + written, buffer_size - written, "%d ", vec->contents[i]);
        if (ret < 0 || ret >= buffer_size - written) {
            return -1;
        }
        written += ret;
    }

    ret = snprintf(buffer + written, buffer_size - written, "]");
    if (ret < 0 || ret >= buffer_size - written) {
        return -1;
    }
    written += ret;

    return written;
}

/**
 * Utility function to check if a value exists in the Vector.
 * @params Vector* (a pointer to the Vector struct)
 * @params int val (the value to search for)
 * @returns index of the value if found, -1 if not found
 */
int vector_find(Vector* vec, int val) {
    if (vec == NULL || vec->contents == NULL) {
        return -1;
    }
    for (int i = 0; i < vec->len; i++) {
        if (vec->contents[i] == val) {
            return i;
        }
    }
    return -1;
}

/**
 * Utility function to check if the Vector contains a specific value.
 * @params Vector* (a pointer to the Vector struct)
 * @params int val (the value to search for)
 * @returns 1 if found, 0 if not found
 */
int vector_contains(Vector* vec, int val) {
    return vector_find(vec, val) >= 0 ? 1 : 0;
}

/**
 * Utility function to check if the Vector is empty.
 * @params Vector* (a pointer to the Vector struct)
 * @returns 1 if empty (len == 0), 0 otherwise
 */
int vector_is_empty(Vector* vec) {
    if (vec == NULL) {
        return 1;
    }
    return vec->len == 0 ? 1 : 0;
}

/**
 * Utility function to compare two Vectors for equality.
 * @params Vector* vec1 (first vector)
 * @params Vector* vec2 (second vector)
 * @returns 1 if equal, 0 if not equal
 */
int vector_equals(Vector* vec1, Vector* vec2) {
    if (vec1 == NULL || vec2 == NULL) {
        return (vec1 == vec2) ? 1 : 0;
    }
    if (vec1->len != vec2->len) {
        return 0;
    }
    for (int i = 0; i < vec1->len; i++) {
        if (vec1->contents[i] != vec2->contents[i]) {
            return 0;
        }
    }
    return 1;
}

/**
 * Utility function to get the sum of all elements in the Vector.
 * @params Vector* (a pointer to the Vector struct)
 * @returns sum of all elements, or 0 if vector is NULL/empty
 */
int vector_sum(Vector* vec) {
    if (vec == NULL || vec->contents == NULL || vec->len == 0) {
        return 0;
    }
    int sum = 0;
    for (int i = 0; i < vec->len; i++) {
        sum += vec->contents[i];
    }
    return sum;
}

/**
 * Utility function to reset the iterator to the beginning.
 * @params Vector* (a pointer to the Vector struct)
 */
void vector_reset_iterator(Vector* vec) {
    if (vec != NULL) {
        vec->current = 0;
    }
}
