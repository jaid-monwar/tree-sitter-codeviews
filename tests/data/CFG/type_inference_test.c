// Comprehensive test for type inference in function call signatures
#include <stdio.h>
#include <stdint.h>

// Function declarations with various signatures
int add_int(int a, int b) {
    return a + b;
}

double add_double(double x, double y) {
    return x + y;
}

char* concat(char* s1, char* s2) {
    return s1;  // Simplified
}

uint32_t process_array(uint32_t* arr, size_t n) {
    return arr[0];
}

int* get_pointer(int x) {
    static int val = 0;
    val = x;
    return &val;
}

void test_literals() {
    // Test 1: Integer literals
    int result1 = add_int(5, 10);           // Should infer: (int, int)

    // Test 2: Float/double literals
    double result2 = add_double(3.14, 2.71);  // Should infer: (double, double)
    double result3 = add_double(1.5f, 2.0f);  // Should infer: (float, float)

    // Test 3: String literals
    char* result4 = concat("Hello", "World");  // Should infer: (char*, char*)

    // Test 4: Mixed literals
    int result5 = add_int(42, 0x2A);        // Should infer: (int, int)
    int result6 = add_int(100L, 200);       // Should infer: (long, int)
}

void test_variables() {
    int x = 10;
    int y = 20;
    double d1 = 1.5;
    double d2 = 2.5;
    char* str1 = "Test";
    char* str2 = "String";

    // Test 5: Variable arguments
    int result1 = add_int(x, y);            // Should infer: (int, int)
    double result2 = add_double(d1, d2);    // Should infer: (double, double)
    char* result3 = concat(str1, str2);     // Should infer: (char*, char*)
}

void test_expressions() {
    int a = 5;
    int b = 10;
    double x = 2.5;

    // Test 6: Binary expressions
    int result1 = add_int(a + b, a - b);    // Should infer: (int, int)
    double result2 = add_double(x * 2.0, x / 2.0);  // Should infer: (double, double)

    // Test 7: Mixed type expressions (promotion)
    double result3 = add_double(a + x, b * x);  // Should infer: (double, double)
}

void test_pointers() {
    int val = 42;
    int* ptr = &val;
    uint32_t arr[5] = {1, 2, 3, 4, 5};
    size_t len = 5;

    // Test 8: Pointer arguments
    int* result1 = get_pointer(val);        // Should infer: (int)
    int* result2 = get_pointer(*ptr);       // Should infer: (int) - dereferenced

    // Test 9: Array arguments
    uint32_t result3 = process_array(arr, len);  // Should infer: (uint32_t*, size_t)

    // Test 10: Address-of operator
    int** result4 = (int**)get_pointer(*ptr);  // Testing nested pointers
}

void test_nested_calls() {
    int x = 5;
    int y = 10;

    // Test 11: Nested function calls
    int result1 = add_int(add_int(x, y), add_int(y, x));
    // Inner calls: (int, int) -> returns int
    // Outer call: (int, int)

    // Test 12: Function call as argument
    int* ptr = get_pointer(add_int(x, y));  // Should infer add_int returns int
}

void test_casts() {
    int x = 10;
    double d = 3.14;

    // Test 13: Cast expressions
    double result1 = add_double((double)x, d);  // Should infer: (double, double)
    int result2 = add_int((int)d, x);           // Should infer: (int, int)
}

void test_array_subscript() {
    uint32_t arr[10] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9};
    int i = 3;

    // Test 14: Array subscript expressions
    int result1 = add_int(arr[0], arr[i]);  // Should infer: (uint32_t, uint32_t)
}

int main() {
    test_literals();
    test_variables();
    test_expressions();
    test_pointers();
    test_nested_calls();
    test_casts();
    test_array_subscript();

    return 0;
}
