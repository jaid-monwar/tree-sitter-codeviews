/**
 * @file
 * @brief [Infix to Postfix converter](https://www.includehelp.com/c/infix-to-postfix-conversion-using-stack-with-c-program.aspx) implementation
 * @details
 * The input infix expression is of type string upto 24 characters.
 * Supported operations- '+', '-', '/', '*', '%'
 * @author [Kumar Yash](https://github.com/kumaryash18)
 * @see infix_to_postfix.c
 */
 
#include <stdio.h>	/// for IO operations
#include <string.h>	/// for strlen(), strcmp()
#include <ctype.h>	/// for isalnum()
#include <stdlib.h>	/// for exit()
#include <stdint.h>	/// for uint16_t, int16_t
#include <assert.h>	/// for assert

/**
 * @brief array implementation of stack using structure
 */
struct Stack {
	char stack[10];		///< array stack
	int top;		///< stores index of the top element
};
struct Stack st;		///< global declaration of stack st

/**
 * @brief Function to initialize/reset the stack
 * @returns void
 */
void initStack() {
	st.top = -1;
}

/**
 * @brief Function to push on the stack
 * @param opd character to be pushed in the stack
 * @returns void
 */
void push(char opd) {
	if(st.top == 9)	{		// overflow condition
		printf("Stack overflow...");
		exit(1);
	}
	st.top++;
	st.stack[st.top] = opd;
}

/**
 * @brief Function to pop from the stack
 * @returns popped character
 */
char pop() {
	char item;				///< to store the popped value to be returned
	if(st.top == -1) {		// underflow condition
		printf("Stack underflow...");
		exit(1);
	}
	item = st.stack[st.top];
	st.top--;
	return item;
}

/**
 * @brief Function to check whether the stack is empty or not
 * @returns 1 if the stack IS empty
 * @returns 0 if the stack is NOT empty
 */
uint16_t isEmpty() {
	if(st.top == -1) {
		return 1;
	}
	return 0;
}

/**
 * @brief Function to get top of the stack
 * @returns top of stack
 */
char Top() {
	return st.stack[st.top];
}

/**
 * @brief Function to check priority of operators
 * @param opr operator whose priority is to be checked
 * @returns 0 if operator is '+' or '-'
 * @returns 1 if operator is '/' or '*' or '%'
 * @returns -1 otherwise
 */
int16_t priority(char opr) {
	if(opr == '+' || opr == '-') {
		return 0;
	}
	else if(opr == '/' || opr == '*' || opr == '%') {
		return 1;
	}
	else {
		return -1;
	}
}

/**
 * @brief Function to convert infix expression to postfix expression
 * @param inf the input infix expression
 * @returns output postfix expression
 */
char *convert(char inf[]) {
	static char post[25];				///< to store the postfix expression
	size_t i;							///< loop iterator
	int j = 0;							///< keeps track of end of postfix string
	for(i = 0; i < strlen(inf); i++) {
		if(isalnum(inf[i]))	{			// if scanned element is an alphabet or number
			post[j] = inf[i];			// append in postfix expression
			j++;
		}
		else if(inf[i] == '(') {		// if scanned element is opening parentheses
			push(inf[i]);				// push on stack.
		}
		else if(inf[i] == ')') {		// if scanned element is closing parentheses,
			while(Top() != '(') {		// pop elements from stack and append in postfix expression
				post[j] = pop();		// until opening parentheses becomes top.
				j++;
			}
			pop();						// pop opening parentheses
		}
		else {							// if scanned element is an operator
			while( (!isEmpty()) && (priority(inf[i]) <= priority(Top())) ) {	// pop and append until stack becomes
				post[j] = pop();												// empty or priority of top operator
				j++;															// becomes smaller than scanned operator
			}																	// '(' has priority -1
			push(inf[i]);				// push the scanned operator
		}
	}
	while(!isEmpty()) {					// pop and append residual operators from stack
		post[j] = pop();
		j++;
	}
	post[j] = '\0';						// end postfix string with null character
	return post;
}

/**
 * @brief Safe version of convert that copies result to user-provided buffer
 * @param inf the input infix expression
 * @param output buffer to store the postfix expression (must be at least 25 chars)
 * @param output_size size of the output buffer
 * @returns 0 on success, -1 on error (output buffer too small)
 */
int convert_safe(char inf[], char *output, size_t output_size) {
	if (output == NULL || output_size < 25) {
		return -1;
	}
	initStack();  // Reset stack before conversion
	char *result = convert(inf);
	size_t len = strlen(result);
	if (len >= output_size) {
		return -1;
	}
	strcpy(output, result);
	return 0;
}

/**
 * @brief Get the current stack size (number of elements)
 * @returns number of elements in the stack
 */
int getStackSize() {
	return st.top + 1;
}

/**
 * @brief Check if the stack is full
 * @returns 1 if stack is full, 0 otherwise
 */
uint16_t isFull() {
	return (st.top == 9) ? 1 : 0;
}

/**
 * @brief Peek at a specific position in the stack (for testing)
 * @param pos position to peek (0 = bottom, top = st.top)
 * @returns character at position, or '\0' if invalid position
 */
char peekAt(int pos) {
	if (pos < 0 || pos > st.top) {
		return '\0';
	}
	return st.stack[pos];
}

/**
 * @brief Validate if an infix expression has balanced parentheses
 * @param inf the input infix expression
 * @returns 1 if balanced, 0 if not balanced
 */
int isBalancedParentheses(char inf[]) {
	int count = 0;
	for (int i = 0; inf[i] != '\0'; i++) {
		if (inf[i] == '(') {
			count++;
		} else if (inf[i] == ')') {
			count--;
			if (count < 0) {
				return 0;  // More closing than opening
			}
		}
	}
	return (count == 0) ? 1 : 0;
}

/**
 * @brief Check if a character is a valid operator
 * @param c character to check
 * @returns 1 if valid operator, 0 otherwise
 */
int isOperator(char c) {
	return (c == '+' || c == '-' || c == '*' || c == '/' || c == '%') ? 1 : 0;
}

/**
 * @brief Count the number of operators in an expression
 * @param expr the expression to analyze
 * @returns number of operators found
 */
int countOperators(char expr[]) {
	int count = 0;
	for (int i = 0; expr[i] != '\0'; i++) {
		if (isOperator(expr[i])) {
			count++;
		}
	}
	return count;
}

/**
 * @brief Count the number of operands (alphanumeric) in an expression
 * @param expr the expression to analyze
 * @returns number of operands found
 */
int countOperands(char expr[]) {
	int count = 0;
	for (int i = 0; expr[i] != '\0'; i++) {
		if (isalnum(expr[i])) {
			count++;
		}
	}
	return count;
}
