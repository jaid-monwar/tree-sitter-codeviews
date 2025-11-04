// Test typedef expansion and resolution
#include <stdio.h>

// Test 1: Simple typedef
typedef int MyInt;
typedef char* String;

// Test 2: Typedef of primitive with modifier
typedef unsigned long size_t;
typedef unsigned int uint32_t;

// Test 3: Typedef of struct
typedef struct {
    int x;
    int y;
} Point;

// Test 4: Typedef with pointer
typedef Point* PointPtr;

// Test 5: Chained typedefs
typedef MyInt Integer;
typedef Integer Counter;

// Test 6: Typedef of pointer to pointer
typedef char** StringArray;

// Helper functions
int process_int(int x) {
    return x * 2;
}

char* process_string(char* s) {
    return s;
}

unsigned long process_ulong(unsigned long x) {
    return x + 1;
}

int* process_int_ptr(int* p) {
    return p;
}

void test_typedefs() {
    // Test 1: Simple typedef -> int
    MyInt x = 10;
    int result1 = process_int(x);  // Should infer: process_int(int)

    // Test 2: String typedef -> char*
    String s = "Hello";
    char* result2 = process_string(s);  // Should infer: process_string(char*)

    // Test 3: size_t typedef -> unsigned long
    size_t len = 100;
    unsigned long result3 = process_ulong(len);  // Should infer: process_ulong(unsigned long)

    // Test 4: Struct typedef
    Point p;
    p.x = 5;
    p.y = 10;
    int px = process_int(p.x);  // Should infer: process_int(int)

    // Test 5: Pointer typedef
    PointPtr ptr = &p;
    int py = process_int(ptr->y);  // Should infer: process_int(int)

    // Test 6: Chained typedef -> int
    Counter count = 42;
    int result4 = process_int(count);  // Should infer: process_int(int)

    // Test 7: Pointer to pointer typedef
    StringArray arr;
    char* first = process_string(arr[0]);  // Should infer: process_string(char*)
}

int main() {
    test_typedefs();
    return 0;
}
