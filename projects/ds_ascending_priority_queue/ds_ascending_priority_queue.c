/* Ascending priority queue using Linked List - Program to implement Ascending
 * priority queue using Linked List */

/*A priority queue is a special type of queue in which each element is
associated with a priority and is served according to its priority. If elements
with the same priority occur, they are served according to their order in the
queue.

Generally, the value of the element itself is considered for assigning the
priority.

For example: The element with the highest value is considered as the highest
priority element. However, in other cases, we can assume the element with the
lowest value as the highest priority element. In other cases, we can set
priorities according to our needs.

In a queue, the first-in-first-out rule is implemented whereas, in a priority
queue, the values are removed on the basis of priority. The element with the
highest priority is removed first.

insert() - Would insert an element in a queue
delete() -  Would delete the smallest element in the queue
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct node
{
    int data;
    struct node *next;
};

struct node *front, *rear;

/* This function initializes the queue to empty by making both front and rear as
 * NULL */
void createqueue() { front = rear = NULL; }

int empty()
{
    if (front == NULL)
        return 1;
    else
        return 0;
}

int insert(int x)
{
    struct node *pnode;

    pnode = (struct node *)malloc(sizeof(struct node));
    if (pnode == NULL)
    {
        return -1; /* Memory allocation failed */
    }

    pnode->data = x;
    pnode->next = NULL; /* New node is always last node */

    if (empty())
        front = rear = pnode;
    else
    {
        rear->next = pnode;
        rear = pnode;
    }
    return 0; /* Success */
}

int removes(int *result)
{
    int min;
    struct node *follow, *follow1, *p, *p1;

    if (empty())
    {
        return -1; /* Queue underflow */
    }

    /* finding the node with minimum value in the APQ.*/
    p = p1 = front;
    follow = follow1 = NULL;
    min = front->data;
    while (p != NULL)
    {
        if (p->data < min)
        {
            min = p->data;
            follow1 = follow;
            p1 = p;
        }
        follow = p;
        p = p->next;
    }

    /* Deleting the node with min value */

    if (p1 == front) /* deleting first node.*/
    {
        front = front->next;
        if (front == NULL) /* Deleting the only one node */
            rear = NULL;
    }
    else if (p1 == rear) /* Deleting last node */
    {
        rear = follow1;
        rear->next = NULL;
    }
    else /* deleting any other node.*/
        follow1->next = p1->next;

    free(p1);
    if (result != NULL)
    {
        *result = min;
    }
    return 0; /* Success */
}

void show()
{
    struct node *p;

    if (empty())
        printf("Queue empty. No data to display \n");
    else
    {
        printf("Queue from front to rear is as shown: \n");

        p = front;
        while (p != NULL)
        {
            printf("%d ", p->data);
            p = p->next;
        }

        printf("\n");
    }
}

void destroyqueue()
{
    struct node *p = front;
    struct node *temp;
    while (p != NULL)
    {
        temp = p;
        p = p->next;
        free(temp);
    }
    front = rear = NULL;
}

/* ============================================
 * String-based alternatives for testing
 * ============================================ */

/* String-based show function - returns queue contents as string */
int show_to_string(char *buffer, int buffer_size)
{
    struct node *p;
    int written = 0;
    int ret;

    if (buffer == NULL || buffer_size <= 0)
    {
        return -1;
    }

    buffer[0] = '\0';

    if (empty())
    {
        ret = snprintf(buffer, buffer_size, "empty");
        return (ret >= 0 && ret < buffer_size) ? 0 : -1;
    }

    p = front;
    while (p != NULL)
    {
        if (written > 0)
        {
            ret = snprintf(buffer + written, buffer_size - written, " %d", p->data);
        }
        else
        {
            ret = snprintf(buffer + written, buffer_size - written, "%d", p->data);
        }

        if (ret < 0 || ret >= buffer_size - written)
        {
            return -1; /* Buffer overflow */
        }
        written += ret;
        p = p->next;
    }

    return 0; /* Success */
}

/* ============================================
 * Utility functions for test assertions
 * ============================================ */

/* Get the number of nodes in the queue */
int queue_size()
{
    int count = 0;
    struct node *p = front;
    while (p != NULL)
    {
        count++;
        p = p->next;
    }
    return count;
}

/* Check if a value exists in the queue */
int queue_contains(int value)
{
    struct node *p = front;
    while (p != NULL)
    {
        if (p->data == value)
        {
            return 1; /* Found */
        }
        p = p->next;
    }
    return 0; /* Not found */
}

/* Get the minimum value in the queue without removing it */
int queue_peek_min(int *result)
{
    struct node *p;
    int min;

    if (empty() || result == NULL)
    {
        return -1;
    }

    p = front;
    min = front->data;
    while (p != NULL)
    {
        if (p->data < min)
        {
            min = p->data;
        }
        p = p->next;
    }

    *result = min;
    return 0;
}

/* Get the value at a specific index (0-based) */
int queue_get_at(int index, int *result)
{
    struct node *p = front;
    int i = 0;

    if (index < 0 || result == NULL)
    {
        return -1;
    }

    while (p != NULL && i < index)
    {
        p = p->next;
        i++;
    }

    if (p == NULL)
    {
        return -1; /* Index out of bounds */
    }

    *result = p->data;
    return 0;
}

/* Get the front value without removing */
int queue_front_value(int *result)
{
    if (empty() || result == NULL)
    {
        return -1;
    }
    *result = front->data;
    return 0;
}

/* Get the rear value without removing */
int queue_rear_value(int *result)
{
    if (empty() || result == NULL)
    {
        return -1;
    }
    *result = rear->data;
    return 0;
}

/* Copy queue contents to an array, returns number of elements copied */
int queue_to_array(int *arr, int arr_size)
{
    struct node *p = front;
    int count = 0;

    if (arr == NULL || arr_size <= 0)
    {
        return -1;
    }

    while (p != NULL && count < arr_size)
    {
        arr[count] = p->data;
        count++;
        p = p->next;
    }

    return count;
}

/* Check if the queue is in a valid state (front/rear consistency) */
int queue_is_valid()
{
    if (front == NULL && rear == NULL)
    {
        return 1; /* Empty queue is valid */
    }

    if ((front == NULL) != (rear == NULL))
    {
        return 0; /* Inconsistent state */
    }

    /* Check that rear is actually the last node */
    struct node *p = front;
    while (p->next != NULL)
    {
        p = p->next;
    }

    return (p == rear) ? 1 : 0;
}

