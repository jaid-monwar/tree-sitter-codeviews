#include <stdio.h>

int main() {
    int day;
    
    printf("Enter a number (1-7) for day of week: ");
    scanf("%d", &day);
    
    switch(day) {
        case 1:
            printf("Monday\n");
            break;
        case 2:
            printf("Tuesday\n");
            break;
        default:
            printf("Invalid day! Please enter 1-7.\n");
            break;
    }
    
    // Another example with characters
    char grade;
    printf("\nEnter your grade (A, B, C, D, F): ");
    scanf(" %c", &grade);
    
    switch(grade) {
        case 'A':
        case 'a':
            printf("Excellent!\n");
            break;
        case 'B':
        case 'b':
            printf("Good job!\n");
            break;
        default:
            printf("Invalid grade!\n");
            break;
    }
    
    return 0;
}