/*
 * Singly Linked List with Deletion Operations
 *
 * This module provides a singly linked list implementation with insertion
 * and deletion operations at arbitrary positions.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct node
{
    int info;
    struct node *link;
};

//////////////////////////////////////////////////////////////////
// Function to create a new node with given data
struct node *createnode(int data)
{
    struct node *t = (struct node *)malloc(sizeof(struct node));
    if (t != NULL)
    {
        t->info = data;
        t->link = NULL;
    }
    return t;
}

//////////////////////////////////////////////////////////////////
// Function to insert a node at a given position
// Returns: 0 on success, -1 on failure (invalid position or allocation failure)
int insert(struct node **head, int pos, int data)
{
    if (head == NULL || pos < 1)
    {
        return -1;
    }

    struct node *new_node = createnode(data);
    if (new_node == NULL)
    {
        return -1;  // Allocation failed
    }

    if (pos == 1)
    {
        new_node->link = *head;
        *head = new_node;
        return 0;
    }

    struct node *pre = *head;
    for (int i = 2; i < pos; i++)
    {
        if (pre == NULL)
        {
            free(new_node);
            return -1;  // Position not found
        }
        pre = pre->link;
    }

    if (pre == NULL)
    {
        free(new_node);
        return -1;  // Position not found
    }

    new_node->link = pre->link;
    pre->link = new_node;
    return 0;
}

//////////////////////////////////////////////////////////////////
// Function to delete a node at a given position
// Returns: 0 on success, -1 on failure (empty list or invalid position)
int deletion(struct node **head, int pos)
{
    if (head == NULL || *head == NULL || pos < 1)
    {
        return -1;  // Invalid input or empty list
    }

    if (pos == 1)
    {
        struct node *p = *head;
        *head = (*head)->link;
        free(p);
        return 0;
    }

    struct node *prev = *head;
    for (int i = 2; i < pos; i++)
    {
        if (prev == NULL)
        {
            return -1;  // Position not found
        }
        prev = prev->link;
    }

    if (prev == NULL || prev->link == NULL)
    {
        return -1;  // Position not found or no node to delete
    }

    struct node *n = prev->link;
    prev->link = n->link;
    free(n);
    return 0;
}

//////////////////////////////////////////////////////////////////
// Function to display list values to stdout
void viewlist(struct node *head)
{
    if (head == NULL)
    {
        printf("list is empty");
        return;
    }

    struct node *p = head;
    while (p != NULL)
    {
        printf("%d ", p->info);
        p = p->link;
    }
}

//////////////////////////////////////////////////////////////////
// String-based alternative: write list to a buffer
// Returns: number of characters written, or -1 on error
int viewlist_to_string(struct node *head, char *buffer, size_t buffer_size)
{
    if (buffer == NULL || buffer_size == 0)
    {
        return -1;
    }

    buffer[0] = '\0';

    if (head == NULL)
    {
        int ret = snprintf(buffer, buffer_size, "list is empty");
        return (ret >= 0 && (size_t)ret < buffer_size) ? ret : -1;
    }

    size_t offset = 0;
    struct node *p = head;
    while (p != NULL)
    {
        int written = snprintf(buffer + offset, buffer_size - offset, "%d ", p->info);
        if (written < 0 || (size_t)written >= buffer_size - offset)
        {
            return -1;  // Buffer overflow
        }
        offset += written;
        p = p->link;
    }

    // Remove trailing space
    if (offset > 0 && buffer[offset - 1] == ' ')
    {
        buffer[offset - 1] = '\0';
        offset--;
    }

    return (int)offset;
}

//////////////////////////////////////////////////////////////////
// Utility: Count the number of nodes in the list
int count_nodes(struct node *head)
{
    int count = 0;
    struct node *p = head;
    while (p != NULL)
    {
        count++;
        p = p->link;
    }
    return count;
}

//////////////////////////////////////////////////////////////////
// Utility: Search for a value in the list
// Returns: position (1-indexed) if found, 0 if not found
int search(struct node *head, int value)
{
    int pos = 1;
    struct node *p = head;
    while (p != NULL)
    {
        if (p->info == value)
        {
            return pos;
        }
        pos++;
        p = p->link;
    }
    return 0;  // Not found
}

//////////////////////////////////////////////////////////////////
// Utility: Get the value at a given position
// Returns: 0 on success (value stored in *value_out), -1 on failure
int get_at_position(struct node *head, int pos, int *value_out)
{
    if (head == NULL || pos < 1 || value_out == NULL)
    {
        return -1;
    }

    struct node *p = head;
    for (int i = 1; i < pos; i++)
    {
        if (p == NULL)
        {
            return -1;
        }
        p = p->link;
    }

    if (p == NULL)
    {
        return -1;
    }

    *value_out = p->info;
    return 0;
}

//////////////////////////////////////////////////////////////////
// Utility: Check if the list is empty
int is_empty(struct node *head)
{
    return (head == NULL) ? 1 : 0;
}

//////////////////////////////////////////////////////////////////
// Utility: Get the head value (first element)
// Returns: 0 on success, -1 on failure (empty list)
int get_head(struct node *head, int *value_out)
{
    if (head == NULL || value_out == NULL)
    {
        return -1;
    }
    *value_out = head->info;
    return 0;
}

//////////////////////////////////////////////////////////////////
// Utility: Get the tail value (last element)
// Returns: 0 on success, -1 on failure (empty list)
int get_tail(struct node *head, int *value_out)
{
    if (head == NULL || value_out == NULL)
    {
        return -1;
    }

    struct node *p = head;
    while (p->link != NULL)
    {
        p = p->link;
    }

    *value_out = p->info;
    return 0;
}

//////////////////////////////////////////////////////////////////
// Utility: Free all nodes in the list
void free_list(struct node **head)
{
    if (head == NULL)
    {
        return;
    }

    struct node *p = *head;
    while (p != NULL)
    {
        struct node *next = p->link;
        free(p);
        p = next;
    }
    *head = NULL;
}

//////////////////////////////////////////////////////////////////
// Utility: Insert at the end of the list (append)
// Returns: 0 on success, -1 on failure
int append(struct node **head, int data)
{
    if (head == NULL)
    {
        return -1;
    }

    struct node *new_node = createnode(data);
    if (new_node == NULL)
    {
        return -1;
    }

    if (*head == NULL)
    {
        *head = new_node;
        return 0;
    }

    struct node *p = *head;
    while (p->link != NULL)
    {
        p = p->link;
    }
    p->link = new_node;
    return 0;
}

//////////////////////////////////////////////////////////////////
// Utility: Insert at the beginning (prepend)
// Returns: 0 on success, -1 on failure
int prepend(struct node **head, int data)
{
    return insert(head, 1, data);
}

//////////////////////////////////////////////////////////////////
// Utility: Create a list from an array
// Returns: pointer to new list head, or NULL on failure
struct node *create_from_array(int *arr, int size)
{
    if (arr == NULL || size <= 0)
    {
        return NULL;
    }

    struct node *head = NULL;
    for (int i = 0; i < size; i++)
    {
        if (append(&head, arr[i]) != 0)
        {
            free_list(&head);
            return NULL;
        }
    }
    return head;
}

//////////////////////////////////////////////////////////////////
// Utility: Convert list to array
// Returns: number of elements copied, or -1 on error
int to_array(struct node *head, int *arr, int max_size)
{
    if (arr == NULL || max_size <= 0)
    {
        return -1;
    }

    int count = 0;
    struct node *p = head;
    while (p != NULL && count < max_size)
    {
        arr[count++] = p->info;
        p = p->link;
    }
    return count;
}
