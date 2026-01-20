#include <limits.h>  /// for INT_MIN
#include <stdio.h>   /// for IO operations
#include <stdlib.h>  /// for dynamic memory allocation

typedef struct max_heap
{
    int *p;
    int size;
    int count;
} Heap;

Heap *create_heap(Heap *heap); /*Creates a max_heap structure and returns a
                                  pointer to the struct*/
void down_heapify(Heap *heap, int index); /*Pushes an element downwards in the
                                             heap to find its correct position*/
void up_heapify(Heap *heap, int index); /*Pushes an element upwards in the heap
                                           to find its correct position*/
void push(Heap *heap, int x);           /*Inserts an element in the heap*/
void pop(Heap *heap); /*Removes the top element from the heap*/
int top(Heap *heap); /*Returns the top element of the heap or returns INT_MIN if
                        heap is empty*/
int empty(Heap *heap); /*Checks if heap is empty*/
int size(Heap *heap);  /*Returns the size of heap*/

/* Utility functions for test assertions */
void destroy_heap(Heap *heap); /*Frees heap memory and cleans up*/
int get_element_at(Heap *heap, int index); /*Returns element at given index*/
int is_valid_max_heap(Heap *heap); /*Checks if heap satisfies max-heap property*/
int get_capacity(Heap *heap); /*Returns the current capacity of the heap*/
int contains(Heap *heap, int value); /*Checks if a value exists in the heap*/
int heap_to_array(Heap *heap, int *arr, int arr_size); /*Copies heap to array*/
Heap *create_heap_from_array(int *arr, int arr_size); /*Creates heap from array*/
int heap_to_string(Heap *heap, char *buffer, int buffer_size); /*Heap to string*/

Heap *create_heap(Heap *heap)
{
    heap = (Heap *)malloc(sizeof(Heap));
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

void down_heapify(Heap *heap, int index)
{
    if (heap == NULL || heap->p == NULL)
        return;
    if (index >= heap->count)
        return;
    int left = index * 2 + 1;
    int right = index * 2 + 2;
    int leftflag = 0, rightflag = 0;

    int maximum = *((heap->p) + index);
    if (left < heap->count && maximum < *((heap->p) + left))
    {
        maximum = *((heap->p) + left);
        leftflag = 1;
    }
    if (right < heap->count && maximum < *((heap->p) + right))
    {
        maximum = *((heap->p) + right);
        leftflag = 0;
        rightflag = 1;
    }
    if (leftflag)
    {
        *((heap->p) + left) = *((heap->p) + index);
        *((heap->p) + index) = maximum;
        down_heapify(heap, left);
    }
    if (rightflag)
    {
        *((heap->p) + right) = *((heap->p) + index);
        *((heap->p) + index) = maximum;
        down_heapify(heap, right);
    }
}
void up_heapify(Heap *heap, int index)
{
    if (heap == NULL || heap->p == NULL)
        return;
    if (index <= 0)
        return;
    int parent = (index - 1) / 2;
    if (*((heap->p) + index) > *((heap->p) + parent))
    {
        int temp = *((heap->p) + index);
        *((heap->p) + index) = *((heap->p) + parent);
        *((heap->p) + parent) = temp;
        up_heapify(heap, parent);
    }
}

void push(Heap *heap, int x)
{
    if (heap == NULL || heap->p == NULL)
        return;
    if (heap->count >= heap->size)
        return;
    *((heap->p) + heap->count) = x;
    heap->count++;
    if (4 * heap->count >= 3 * heap->size)
    {
        heap->size *= 2;
        int *new_p = (int *)realloc((heap->p), (heap->size) * sizeof(int));
        if (new_p == NULL)
        {
            heap->size /= 2;
            return;
        }
        heap->p = new_p;
    }
    up_heapify(heap, heap->count - 1);
}
void pop(Heap *heap)
{
    if (heap == NULL || heap->p == NULL)
        return;
    if (heap->count == 0)
        return;
    heap->count--;
    int temp = *((heap->p) + heap->count);
    *((heap->p) + heap->count) = *(heap->p);
    *(heap->p) = temp;
    down_heapify(heap, 0);
    if (4 * heap->count <= heap->size && heap->size > 1)
    {
        heap->size /= 2;
        int *new_p = (int *)realloc((heap->p), (heap->size) * sizeof(int));
        if (new_p != NULL)
        {
            heap->p = new_p;
        }
    }
}
int top(Heap *heap)
{
    if (heap == NULL || heap->p == NULL)
        return INT_MIN;
    if (heap->count != 0)
        return *(heap->p);
    else
        return INT_MIN;
}
int empty(Heap *heap)
{
    if (heap == NULL || heap->p == NULL)
        return 1;
    if (heap->count != 0)
        return 0;
    else
        return 1;
}
int size(Heap *heap)
{
    if (heap == NULL)
        return 0;
    return heap->count;
}

/* Utility functions for test assertions */

/*Frees heap memory and cleans up*/
void destroy_heap(Heap *heap)
{
    if (heap == NULL)
        return;
    if (heap->p != NULL)
        free(heap->p);
    free(heap);
}

/*Returns element at given index, or INT_MIN if invalid*/
int get_element_at(Heap *heap, int index)
{
    if (heap == NULL || heap->p == NULL)
        return INT_MIN;
    if (index < 0 || index >= heap->count)
        return INT_MIN;
    return *((heap->p) + index);
}

/*Checks if heap satisfies max-heap property (parent >= children)*/
int is_valid_max_heap(Heap *heap)
{
    if (heap == NULL || heap->p == NULL)
        return 1;
    if (heap->count <= 1)
        return 1;
    int i;
    for (i = 0; i < heap->count; i++)
    {
        int left = 2 * i + 1;
        int right = 2 * i + 2;
        if (left < heap->count && *((heap->p) + i) < *((heap->p) + left))
            return 0;
        if (right < heap->count && *((heap->p) + i) < *((heap->p) + right))
            return 0;
    }
    return 1;
}

/*Returns the current capacity of the heap*/
int get_capacity(Heap *heap)
{
    if (heap == NULL)
        return 0;
    return heap->size;
}

/*Checks if a value exists in the heap*/
int contains(Heap *heap, int value)
{
    if (heap == NULL || heap->p == NULL)
        return 0;
    int i;
    for (i = 0; i < heap->count; i++)
    {
        if (*((heap->p) + i) == value)
            return 1;
    }
    return 0;
}

/*Copies heap contents to an array, returns number of elements copied*/
int heap_to_array(Heap *heap, int *arr, int arr_size)
{
    if (heap == NULL || heap->p == NULL || arr == NULL)
        return 0;
    int count = heap->count < arr_size ? heap->count : arr_size;
    int i;
    for (i = 0; i < count; i++)
    {
        arr[i] = *((heap->p) + i);
    }
    return count;
}

/*Creates a heap and populates it with values from an array*/
Heap *create_heap_from_array(int *arr, int arr_size)
{
    if (arr == NULL || arr_size <= 0)
        return NULL;
    Heap *heap = create_heap(NULL);
    if (heap == NULL)
        return NULL;
    int i;
    for (i = 0; i < arr_size; i++)
    {
        push(heap, arr[i]);
    }
    return heap;
}

/*Returns heap contents as a string for debugging (format: "[a, b, c]")*/
int heap_to_string(Heap *heap, char *buffer, int buffer_size)
{
    if (buffer == NULL || buffer_size <= 0)
        return -1;
    if (heap == NULL || heap->p == NULL || heap->count == 0)
    {
        if (buffer_size >= 3)
        {
            buffer[0] = '[';
            buffer[1] = ']';
            buffer[2] = '\0';
            return 2;
        }
        return -1;
    }
    int pos = 0;
    if (pos < buffer_size - 1)
        buffer[pos++] = '[';
    int i;
    for (i = 0; i < heap->count && pos < buffer_size - 10; i++)
    {
        if (i > 0 && pos < buffer_size - 2)
        {
            buffer[pos++] = ',';
            buffer[pos++] = ' ';
        }
        pos += snprintf(buffer + pos, buffer_size - pos, "%d", *((heap->p) + i));
    }
    if (pos < buffer_size - 1)
        buffer[pos++] = ']';
    buffer[pos] = '\0';
    return pos;
}
