#include <stdio.h>

int main() {
    // Declare an integer variable to hold the number
    int number;

    // Prompt the user to enter a number
    printf("Enter an integer: ");

    // Read the integer entered by the user
    scanf("%d", &number);

    // Check the value of the number using if-else statements
    if (number > 0) {
        // This block is executed if the number is greater than 0
        printf("You entered a positive number: %d\n", number);
    } else if (number < 0) {
        // This block is executed if the number is less than 0
        printf("You entered a negative number: %d\n", number);
    } else {
        // This block is executed if the number is not greater than 0 and not less than 0, meaning it is 0
        printf("You entered zero.\n");
    }

    // The return 0 statement indicates that the program executed successfully
    return 0;
}