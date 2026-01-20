/**
 * @file
 * @brief [Infix to
 * Postfix](https://condor.depaul.edu/ichu/csc415/notes/notes9/Infix.htm)
 * Expression Conversion
 * @details Convert Infixed expressions to Postfix expression.
 * @author [Harsh Karande](https://github.com/harshcut)
 */

// include header files
#include <stdio.h>   /// for printf() and scanf()
#include <string.h>  /// for strlen() and strcmp()

/// Maximum stack capacity
#define STACK_CAPACITY 100

/**
 * @brief a globally declared structure with an array and an variable that
 * points to the topmost index of the array
 */
struct Stack
{
    char arr[STACK_CAPACITY];  ///> static array of characters
    int tos;                   ///> stores index on topmost element in stack
};

// function headers
void push(struct Stack *p, char ch);   // push element in stack
char pop(struct Stack *p);             // pop topmost element from the stack
int isOprnd(char ch);                  // check if element is operand or not
int isEmpty(struct Stack s);           // check if stack is empty
int isFull(struct Stack s);            // check if stack is full
int stackSize(struct Stack s);         // get number of elements in stack
char peek(struct Stack s);             // look at top element without removing
void initStack(struct Stack *p);       // initialize stack
int getPrecedence(char op1, char op2); // check operator precedence
int getPrecedenceValue(char op);       // get numeric precedence of operator
void convert(char infix[], char postfix[]);  // convert infix to postfix expression
int isValidInfix(const char *expr);    // validate infix expression
int isOperator(char ch);               // check if character is an operator
int compareStrings(const char *s1, const char *s2);  // compare two strings


/**
 * @brief push function
 * @param *p : used as a pointer variable of stack
 * @param x : char to be pushed in stack
 * @returns void
 */
void push(struct Stack *p, char x)
{
    if (p->tos == STACK_CAPACITY - 1)  // check if stack has reached its max limit
    {
        return;
    }

    p->tos += 1;         // increment tos
    p->arr[p->tos] = x;  // assign char x to index of stack pointed by tos
}

/**
 * @brief pop function
 * @param *p : used as a pointer variable of stack
 * @returns x or \0 on exit
 */
char pop(struct Stack *p)
{
    char x;

    if (p->tos == -1)
    {
        return '\0';
    }

    x = p->arr[p->tos];  // assign the value of stack at index tos to x
    p->tos -= 1;         // decrement tos

    return x;
}

/**
 * @brief isOprnd function
 * @param ch : this is the element from the infix array
 * @returns 1 or 0 on exit
 */
int isOprnd(char ch)
{
    if ((ch >= 65 && ch <= 90) ||
        (ch >= 97 && ch <= 122) ||  // check if ch is an operator or
        (ch >= 48 && ch <= 57))     // operand using ASCII values
    {
        return 1;  // return for true result
    }
    else
    {
        return 0;  // return for false result
    }
}

/**
 * @brief isEmpty function
 * @param s : it is the object reference of stack
 * @returns 1 or 0 on exit
 */
int isEmpty(struct Stack s)
{
    if (s.tos == -1)  // check if stack is empty
    {
        return 1;  // return for true result
    }
    else
    {
        return 0;  // return for false result
    }
}

/**
 * @brief convert function
 * @param infix[] : infix array provided by user
 * @param postfix[] : empty array to be given to convert()
 * @returns postfixed expresion or \0 on exit
 */
void convert(char infix[], char postfix[])
{
    struct Stack s;  // initialze object reference of stack
    s.tos = -1;      // initalize the tos

    int i, j = 0, pr;
    char ch, temp;

    for (i = 0; infix[i] != '\0'; i++)
    {
        ch = infix[i];

        if (isOprnd(ch) == 1)  // check if char is operand or operator
        {
            postfix[j] = ch;  // assign ch to postfix array with index j
            j++;              // incement j
        }
        else
        {
            if (ch == '(')
            {
                push(&s, ch);
            }
            else
            {
                if (ch == ')')
                {
                    while ((temp = pop(&s)) != '(')
                    {
                        postfix[j] = temp;
                        j++;
                    }
                }
                else
                {
                    while (isEmpty(s) == 0)  // check if stack is empty
                    {
                        pr = getPrecedence(ch,
                                   s.arr[s.tos]);  // check operator precedence

                        if (pr == 1)
                        {
                            break;  // if ch has a greater precedence than
                                    // s.arr[s.top]
                        }

                        postfix[j] = pop(&s);
                        j++;
                    }

                    push(&s, ch);  // push ch to stack
                }
            }
        }
    }

    while (isEmpty(s) == 0)  // check if stack is empty
    {
        postfix[j] = pop(&s);
        j++;
    }

    postfix[j] = '\0';
}

/**
 * @brief getPrecedence function returns the precedence after comparing two operators passed as parameter.
 * @param op1 : first operator
 * @param op2 : second operator
 * @returns 1 if op1 has higher precedence than op2, 0 otherwise
 */
int getPrecedence(char op1, char op2)
{
    if (op2 == '$')
    {
        return 0;
    }
    else if (op1 == '$')
    {
        return 1;
    }
    else if (op2 == '*' || op2 == '/' || op2 == '%')
    {
        return 0;
    }
    else if (op1 == '*' || op1 == '/' || op1 == '%')
    {
        return 1;
    }
    else if (op2 == '+' || op2 == '-')
    {
        return 0;
    }
    else
    {
        return 1;
    }
}

/**
 * @brief isFull function checks if stack is full
 * @param s : stack structure
 * @returns 1 if full, 0 otherwise
 */
int isFull(struct Stack s)
{
    if (s.tos == STACK_CAPACITY - 1)
    {
        return 1;
    }
    else
    {
        return 0;
    }
}

/**
 * @brief stackSize function returns the number of elements in the stack
 * @param s : stack structure
 * @returns number of elements in stack
 */
int stackSize(struct Stack s)
{
    return s.tos + 1;
}

/**
 * @brief peek function returns the top element without removing it
 * @param s : stack structure
 * @returns top element or '\0' if empty
 */
char peek(struct Stack s)
{
    if (s.tos == -1)
    {
        return '\0';
    }
    return s.arr[s.tos];
}

/**
 * @brief initStack function initializes a stack
 * @param *p : pointer to stack structure
 * @returns void
 */
void initStack(struct Stack *p)
{
    p->tos = -1;
}

/**
 * @brief getPrecedenceValue returns a numeric precedence value for an operator
 * @param op : operator character
 * @returns precedence value (higher = more precedence), -1 for non-operators
 */
int getPrecedenceValue(char op)
{
    if (op == '$')
    {
        return 3;  // highest precedence (exponentiation)
    }
    else if (op == '*' || op == '/' || op == '%')
    {
        return 2;  // multiplication, division, modulo
    }
    else if (op == '+' || op == '-')
    {
        return 1;  // addition, subtraction
    }
    else
    {
        return -1;  // not an operator
    }
}

/**
 * @brief isOperator function checks if a character is an operator
 * @param ch : character to check
 * @returns 1 if operator, 0 otherwise
 */
int isOperator(char ch)
{
    if (ch == '+' || ch == '-' || ch == '*' || ch == '/' || ch == '%' || ch == '$')
    {
        return 1;
    }
    return 0;
}

/**
 * @brief isValidInfix function validates an infix expression
 * @param expr : infix expression string
 * @returns 1 if valid, 0 otherwise
 */
int isValidInfix(const char *expr)
{
    int i;
    int operandCount = 0;
    int operatorCount = 0;
    int parenBalance = 0;

    if (expr == NULL || expr[0] == '\0')
    {
        return 0;  // empty or null expression is invalid
    }

    for (i = 0; expr[i] != '\0'; i++)
    {
        char ch = expr[i];

        if (isOprnd(ch))
        {
            operandCount++;
        }
        else if (isOperator(ch))
        {
            operatorCount++;
        }
        else if (ch == '(')
        {
            parenBalance++;
        }
        else if (ch == ')')
        {
            parenBalance--;
            if (parenBalance < 0)
            {
                return 0;  // unmatched closing parenthesis
            }
        }
        else
        {
            return 0;  // invalid character
        }
    }

    // Check parenthesis balance and operator/operand relationship
    if (parenBalance != 0)
    {
        return 0;  // unmatched parentheses
    }

    // For a valid expression: operands = operators + 1
    if (operandCount != operatorCount + 1)
    {
        return 0;
    }

    return 1;
}

/**
 * @brief compareStrings function compares two strings
 * @param s1 : first string
 * @param s2 : second string
 * @returns 0 if equal, negative if s1 < s2, positive if s1 > s2
 */
int compareStrings(const char *s1, const char *s2)
{
    if (s1 == NULL && s2 == NULL)
    {
        return 0;
    }
    if (s1 == NULL)
    {
        return -1;
    }
    if (s2 == NULL)
    {
        return 1;
    }
    return strcmp(s1, s2);
}
