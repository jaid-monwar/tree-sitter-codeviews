#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
#include <string.h>

typedef struct min_heap
{
    int *p;
    int size;
    int count;
} Heap;
/* Creates a min_heap structure and returns a pointer to the struct */
Heap *create_heap(void)
{
    Heap *heap = (Heap *)malloc(sizeof(Heap));
    if (heap == NULL)
        return NULL;
    heap->size = 1;
    heap->p = (int *)malloc(heap->size * sizeof(int));
    if (heap->p == NULL)
    {
        free(heap);
        return NULL;
    }
    heap->count = 0;
    return heap;
}

/* Pushes an element downwards in the heap to find its correct position */
void down_heapify(Heap *heap, int index)
{
    if (heap == NULL || index >= heap->count)
        return;
    int left = index * 2 + 1;
    int right = index * 2 + 2;
    int leftflag = 0, rightflag = 0;

    int minimum = *((heap->p) + index);
    if (left < heap->count && minimum > *((heap->p) + left))
    {
        minimum = *((heap->p) + left);
        leftflag = 1;
    }
    if (right < heap->count && minimum > *((heap->p) + right))
    {
        minimum = *((heap->p) + right);
        leftflag = 0;
        rightflag = 1;
    }
    if (leftflag)
    {
        *((heap->p) + left) = *((heap->p) + index);
        *((heap->p) + index) = minimum;
        down_heapify(heap, left);
    }
    if (rightflag)
    {
        *((heap->p) + right) = *((heap->p) + index);
        *((heap->p) + index) = minimum;
        down_heapify(heap, right);
    }
}
/* Pushes an element upwards in the heap to find its correct position */
void up_heapify(Heap *heap, int index)
{
    if (heap == NULL || index <= 0)
        return;
    int parent = (index - 1) / 2;
    if (*((heap->p) + index) < *((heap->p) + parent))
    {
        int temp = *((heap->p) + index);
        *((heap->p) + index) = *((heap->p) + parent);
        *((heap->p) + parent) = temp;
        up_heapify(heap, parent);
    }
}

/* Inserts an element in the heap */
void push(Heap *heap, int x)
{
    if (heap == NULL)
        return;
    if (heap->count >= heap->size)
    {
        /* Need to resize before inserting */
        int new_size = heap->size * 2;
        int *new_p = (int *)realloc(heap->p, new_size * sizeof(int));
        if (new_p == NULL)
            return;
        heap->p = new_p;
        heap->size = new_size;
    }
    *((heap->p) + heap->count) = x;
    heap->count++;
    if (4 * heap->count >= 3 * heap->size)
    {
        int new_size = heap->size * 2;
        int *new_p = (int *)realloc(heap->p, new_size * sizeof(int));
        if (new_p != NULL)
        {
            heap->p = new_p;
            heap->size = new_size;
        }
    }
    up_heapify(heap, heap->count - 1);
}
/* Removes the top element from the heap */
void pop(Heap *heap)
{
    if (heap == NULL || heap->count == 0)
        return;
    heap->count--;
    int temp = *((heap->p) + heap->count);
    *((heap->p) + heap->count) = *(heap->p);
    *(heap->p) = temp;
    down_heapify(heap, 0);
    if (heap->size > 1 && 4 * heap->count <= heap->size)
    {
        int new_size = heap->size / 2;
        if (new_size < 1)
            new_size = 1;
        int *new_p = (int *)realloc(heap->p, new_size * sizeof(int));
        if (new_p != NULL)
        {
            heap->p = new_p;
            heap->size = new_size;
        }
    }
}
/* Returns the top element of the heap or returns INT_MIN if heap is empty */
int top(Heap *heap)
{
    if (heap == NULL || heap->count == 0)
        return INT_MIN;
    return *(heap->p);
}

/* Checks if heap is empty (returns 1 if empty, 0 otherwise) */
int empty(Heap *heap)
{
    if (heap == NULL || heap->count == 0)
        return 1;
    return 0;
}

/* Returns the number of elements in the heap */
int heap_size(Heap *heap)
{
    if (heap == NULL)
        return 0;
    return heap->count;
}

/* ==================== UTILITY FUNCTIONS FOR TESTING ==================== */

/* Frees all memory associated with the heap */
void destroy_heap(Heap *heap)
{
    if (heap == NULL)
        return;
    if (heap->p != NULL)
        free(heap->p);
    free(heap);
}

/* Checks if a value exists in the heap (returns 1 if found, 0 otherwise) */
int heap_contains(Heap *heap, int value)
{
    if (heap == NULL)
        return 0;
    for (int i = 0; i < heap->count; i++)
    {
        if (*((heap->p) + i) == value)
            return 1;
    }
    return 0;
}

/* Returns the element at the given index (-1 if invalid index) */
int heap_get_at(Heap *heap, int index)
{
    if (heap == NULL || index < 0 || index >= heap->count)
        return INT_MIN;
    return *((heap->p) + index);
}

/* Verifies the min-heap property (returns 1 if valid, 0 otherwise) */
int verify_min_heap_property(Heap *heap)
{
    if (heap == NULL || heap->count <= 1)
        return 1;
    for (int i = 0; i < heap->count; i++)
    {
        int left = 2 * i + 1;
        int right = 2 * i + 2;
        int current = *((heap->p) + i);
        if (left < heap->count && current > *((heap->p) + left))
            return 0;
        if (right < heap->count && current > *((heap->p) + right))
            return 0;
    }
    return 1;
}

/* Converts heap contents to a string for testing (caller must free) */
char *heap_to_string(Heap *heap)
{
    if (heap == NULL || heap->count == 0)
    {
        char *empty_str = (char *)malloc(3);
        if (empty_str != NULL)
            strcpy(empty_str, "[]");
        return empty_str;
    }
    /* Estimate buffer size: each int up to 11 chars + comma + space */
    int buffer_size = heap->count * 14 + 3;
    char *result = (char *)malloc(buffer_size);
    if (result == NULL)
        return NULL;

    char *ptr = result;
    ptr += sprintf(ptr, "[");
    for (int i = 0; i < heap->count; i++)
    {
        if (i > 0)
            ptr += sprintf(ptr, ", ");
        ptr += sprintf(ptr, "%d", *((heap->p) + i));
    }
    sprintf(ptr, "]");
    return result;
}

/* Creates a heap from an array of integers */
Heap *heap_from_array(int *arr, int n)
{
    if (arr == NULL || n < 0)
        return NULL;
    Heap *heap = create_heap();
    if (heap == NULL)
        return NULL;
    for (int i = 0; i < n; i++)
    {
        push(heap, arr[i]);
    }
    return heap;
}

/* Returns the allocated capacity of the heap */
int heap_capacity(Heap *heap)
{
    if (heap == NULL)
        return 0;
    return heap->size;
}

/* Clears all elements from the heap without destroying it */
void heap_clear(Heap *heap)
{
    if (heap == NULL)
        return;
    heap->count = 0;
    /* Optionally shrink allocation back to initial size */
    if (heap->size > 1)
    {
        int *new_p = (int *)realloc(heap->p, sizeof(int));
        if (new_p != NULL)
        {
            heap->p = new_p;
            heap->size = 1;
        }
    }
}

/* Returns the second minimum element (or INT_MIN if less than 2 elements) */
int heap_second_min(Heap *heap)
{
    if (heap == NULL || heap->count < 2)
        return INT_MIN;
    /* Second minimum is one of the children of the root */
    int left = *((heap->p) + 1);
    if (heap->count == 2)
        return left;
    int right = *((heap->p) + 2);
    return (left < right) ? left : right;
}
