/**
 * @file
 *
 * @brief
 * Dynamic [Stack](https://en.wikipedia.org/wiki/Stack_(abstract_data_type)),
 * just like Dynamic Array, is a stack data structure whose the length or
 * capacity (maximum number of elements that can be stored) increases or
 * decreases in real time based on the operations (like insertion or deletion)
 * performed on it.
 *
 * In this implementation, functions such as PUSH, POP, PEEK, show_capacity,
 * isempty, and stack_size are coded to implement dynamic stack.
 *
 * @author [SahilK-027](https://github.com/SahilK-027)
 *
 */
#include <stdio.h>     /// for IO operations
#include <stdlib.h>  /// for including functions involving memory allocation such as `malloc`
#include <string.h>  /// for string operations
/**
 * @brief DArrayStack Structure of stack.
 */
typedef struct DArrayStack
{
    int capacity, top;  ///< to store capacity and top of the stack
    int *arrPtr;        ///< array pointer
} DArrayStack;

/**
 * @brief Create a Stack object
 *
 * @param cap Capacity of stack (must be > 0)
 * @return DArrayStack* Newly created stack object pointer, or NULL on failure
 */
DArrayStack *create_stack(int cap)
{
    if (cap <= 0)
    {
        return NULL;
    }
    DArrayStack *ptr;
    ptr = (DArrayStack *)malloc(sizeof(DArrayStack));
    if (ptr == NULL)
    {
        return NULL;
    }
    ptr->arrPtr = (int *)malloc(sizeof(int) * cap);
    if (ptr->arrPtr == NULL)
    {
        free(ptr);
        return NULL;
    }
    ptr->capacity = cap;
    ptr->top = -1;
    return (ptr);
}

/**
 * @brief As this is stack implementation using dynamic array this function will
 * expand the size of the stack by twice as soon as the stack is full.
 *
 * @param ptr Stack pointer
 * @param cap Capacity of stack
 * @return DArrayStack*: Modified stack, or NULL on failure
 */
DArrayStack *double_array(DArrayStack *ptr, int cap)
{
    if (ptr == NULL || cap <= 0)
    {
        return NULL;
    }
    int newCap = 2 * cap;
    int *temp;
    temp = (int *)malloc(sizeof(int) * newCap);
    if (temp == NULL)
    {
        return NULL;
    }
    for (int i = 0; i < (ptr->top) + 1; i++)
    {
        temp[i] = ptr->arrPtr[i];
    }
    free(ptr->arrPtr);
    ptr->arrPtr = temp;
    ptr->capacity = newCap;
    return ptr;
}

/**
 * @brief As this is stack implementation using dynamic array this function will
 * shrink the size of stack by twice as soon as the stack's capacity and size
 * has significant difference.
 *
 * @param ptr Stack pointer
 * @param cap Capacity of stack
 * @return DArrayStack*: Modified stack, or NULL on failure
 */
DArrayStack *shrink_array(DArrayStack *ptr, int cap)
{
    if (ptr == NULL || cap < 2)
    {
        return NULL;
    }
    int newCap = cap / 2;
    if (newCap <= 0)
    {
        newCap = 1;
    }
    int *temp;
    temp = (int *)malloc(sizeof(int) * newCap);
    if (temp == NULL)
    {
        return NULL;
    }
    for (int i = 0; i < (ptr->top) + 1; i++)
    {
        temp[i] = ptr->arrPtr[i];
    }
    free(ptr->arrPtr);
    ptr->arrPtr = temp;
    ptr->capacity = newCap;
    return ptr;
}

/**
 * @brief The push function pushes the element onto the stack.
 *
 * @param ptr Stack pointer
 * @param data Value to be pushed onto stack
 * @return int Position of top pointer, or -1 on failure
 */
int push(DArrayStack *ptr, int data)
{
    if (ptr == NULL)
    {
        return -1;
    }
    if (ptr->top == (ptr->capacity) - 1)
    {
        DArrayStack *result = double_array(ptr, ptr->capacity);
        if (result == NULL)
        {
            return -1;
        }
        ptr->top++;
        ptr->arrPtr[ptr->top] = data;
    }
    else
    {
        ptr->top++;
        ptr->arrPtr[ptr->top] = data;
    }
    return ptr->top;
}

/**
 * @brief The pop function to pop an element from the stack.
 *
 * @param ptr Stack pointer
 * @param success Pointer to store success status (1 = success, 0 = failure), can be NULL
 * @return int Popped value, or 0 on failure (check success flag)
 */
int pop(DArrayStack *ptr, int *success)
{
    if (ptr == NULL)
    {
        if (success) *success = 0;
        return 0;
    }
    if (ptr->top == -1)
    {
        if (success) *success = 0;
        return 0;
    }
    if (success) *success = 1;
    int ele = ptr->arrPtr[ptr->top];
    ptr->arrPtr[ptr->top] = 0;
    ptr->top = (ptr->top - 1);
    if ((ptr->capacity) % 2 == 0 && ptr->capacity >= 2)
    {
        if (ptr->top <= (ptr->capacity / 2) - 1)
        {
            shrink_array(ptr, ptr->capacity);
        }
    }
    return ele;
}

/**
 * @brief To retrieve or fetch the first element of the Stack or the element
 * present at the top of the Stack.
 *
 * @param ptr Stack pointer
 * @param success Pointer to store success status (1 = success, 0 = failure), can be NULL
 * @return int Top of the stack, or 0 on failure (check success flag)
 */
int peek(DArrayStack *ptr, int *success)
{
    if (ptr == NULL || ptr->top == -1)
    {
        if (success) *success = 0;
        return 0;
    }
    if (success) *success = 1;
    return ptr->arrPtr[ptr->top];
}

/**
 * @brief To display the current capacity of the stack.
 *
 * @param ptr Stack pointer
 * @return int Current capacity of the stack, or -1 if ptr is NULL
 */
int show_capacity(DArrayStack *ptr)
{
    if (ptr == NULL)
    {
        return -1;
    }
    return ptr->capacity;
}

/**
 * @brief The function is used to check whether the stack is empty or not and
 * return true or false accordingly.
 *
 * @param ptr Stack pointer
 * @return int returns 1 -> true (empty or NULL), returns 0 -> false (not empty)
 */
int isempty(DArrayStack *ptr)
{
    if (ptr == NULL || ptr->top == -1)
    {
        return 1;
    }
    return 0;
}

/**
 * @brief Used to get the size of the Stack or the number of elements present in
 * the Stack.
 *
 * @param ptr Stack pointer
 * @return int size of stack, or 0 if ptr is NULL
 */
int stack_size(DArrayStack *ptr)
{
    if (ptr == NULL)
    {
        return 0;
    }
    return ptr->top + 1;
}

/**
 * @brief Free the entire stack and its internal array.
 *
 * @param ptr Stack pointer
 */
void free_stack(DArrayStack *ptr)
{
    if (ptr == NULL)
    {
        return;
    }
    if (ptr->arrPtr != NULL)
    {
        free(ptr->arrPtr);
    }
    free(ptr);
}

/**
 * @brief Get the element at a specific index in the stack (0 = bottom).
 *
 * @param ptr Stack pointer
 * @param index Index from bottom of stack
 * @param success Pointer to store success status (1 = success, 0 = failure), can be NULL
 * @return int Element at index, or 0 on failure
 */
int get_element_at(DArrayStack *ptr, int index, int *success)
{
    if (ptr == NULL || index < 0 || index > ptr->top)
    {
        if (success) *success = 0;
        return 0;
    }
    if (success) *success = 1;
    return ptr->arrPtr[index];
}

/**
 * @brief Check if a value exists in the stack.
 *
 * @param ptr Stack pointer
 * @param value Value to search for
 * @return int 1 if found, 0 if not found or stack is NULL/empty
 */
int stack_contains(DArrayStack *ptr, int value)
{
    if (ptr == NULL)
    {
        return 0;
    }
    for (int i = 0; i <= ptr->top; i++)
    {
        if (ptr->arrPtr[i] == value)
        {
            return 1;
        }
    }
    return 0;
}

/**
 * @brief Clear all elements from the stack without freeing it.
 *
 * @param ptr Stack pointer
 */
void clear_stack(DArrayStack *ptr)
{
    if (ptr == NULL)
    {
        return;
    }
    for (int i = 0; i <= ptr->top; i++)
    {
        ptr->arrPtr[i] = 0;
    }
    ptr->top = -1;
}

/**
 * @brief Convert stack contents to a string representation.
 *
 * @param ptr Stack pointer
 * @param buffer Output buffer for the string
 * @param buffer_size Size of the output buffer
 * @return int Number of characters written (excluding null terminator), or -1 on error
 */
int stack_to_string(DArrayStack *ptr, char *buffer, int buffer_size)
{
    if (buffer == NULL || buffer_size <= 0)
    {
        return -1;
    }
    if (ptr == NULL || ptr->top == -1)
    {
        if (buffer_size >= 3)
        {
            strcpy(buffer, "[]");
            return 2;
        }
        return -1;
    }

    int written = 0;
    int remaining = buffer_size - 1;

    buffer[written++] = '[';
    remaining--;

    for (int i = 0; i <= ptr->top && remaining > 0; i++)
    {
        char num_buf[32];
        int num_len = snprintf(num_buf, sizeof(num_buf), "%d", ptr->arrPtr[i]);

        if (i > 0)
        {
            if (remaining < 2)
            {
                break;
            }
            buffer[written++] = ',';
            buffer[written++] = ' ';
            remaining -= 2;
        }

        if (num_len > remaining)
        {
            break;
        }

        memcpy(buffer + written, num_buf, num_len);
        written += num_len;
        remaining -= num_len;
    }

    if (remaining >= 1)
    {
        buffer[written++] = ']';
    }
    buffer[written] = '\0';

    return written;
}

/**
 * @brief Check if two stacks have equal contents.
 *
 * @param stack1 First stack pointer
 * @param stack2 Second stack pointer
 * @return int 1 if equal, 0 if not equal
 */
int stacks_equal(DArrayStack *stack1, DArrayStack *stack2)
{
    if (stack1 == NULL && stack2 == NULL)
    {
        return 1;
    }
    if (stack1 == NULL || stack2 == NULL)
    {
        return 0;
    }
    if (stack1->top != stack2->top)
    {
        return 0;
    }
    for (int i = 0; i <= stack1->top; i++)
    {
        if (stack1->arrPtr[i] != stack2->arrPtr[i])
        {
            return 0;
        }
    }
    return 1;
}

/**
 * @brief Copy a stack to a new stack.
 *
 * @param src Source stack pointer
 * @return DArrayStack* New stack with copied contents, or NULL on failure
 */
DArrayStack *copy_stack(DArrayStack *src)
{
    if (src == NULL)
    {
        return NULL;
    }
    DArrayStack *dest = create_stack(src->capacity);
    if (dest == NULL)
    {
        return NULL;
    }
    for (int i = 0; i <= src->top; i++)
    {
        dest->arrPtr[i] = src->arrPtr[i];
    }
    dest->top = src->top;
    return dest;
}
