#include <stdio.h>

// Helper function 1
int add(int a, int b) {
    return a + b;
}

// Helper function 2
int multiply(int a, int b) {
    return a * b;
}

// Main function
int main() {
    int x = 5;
    int y = 10;
    int sum = add(x, y);
    int product = multiply(x, y);
    printf("Sum: %d, Product: %d\n", sum, product);
    return 0;
}
