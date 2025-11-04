#include <iostream>
using namespace std;

// Function declarations
int add(int a, int b);
void greet(string name);
int factorial(int n);
void swapNumbers(int& x, int& y);

int main() {
    // Basic function calls
    int sum = add(5, 3);
    cout << "5 + 3 = " << sum << endl;
    
    greet("Alice");
    
    // Recursive function
    int fact = factorial(5);
    cout << "5! = " << fact << endl;
    
    // Pass by reference
    int a = 10, b = 20;
    cout << "Before swap: a=" << a << ", b=" << b << endl;
    swapNumbers(a, b);
    cout << "After swap: a=" << a << ", b=" << b << endl;
    
    // Function calls in expressions
    int result = add(factorial(3), add(2, 4));
    cout << "factorial(3) + add(2,4) = " << result << endl;
    
    return 0;
}

// Function definitions
int add(int a, int b) {
    return a + b;
}

void greet(string name) {
    cout << "Hello, " << name << "!" << endl;
}

int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

void swapNumbers(int& x, int& y) {
    int temp = x;
    x = y;
    y = temp;
}