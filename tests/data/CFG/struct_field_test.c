// Test struct field type resolution
#include <stdio.h>

// Test 1: Simple struct
struct Point {
    int x;
    int y;
};

// Test 2: Struct with pointers
struct Person {
    char* name;
    int age;
    double* salary;
};

// Test 3: Nested struct
struct Rectangle {
    struct Point top_left;
    struct Point bottom_right;
    int* dimensions;
};

// Test 4: Struct with arrays
struct Buffer {
    char data[256];
    int size;
};

// Helper functions for testing
int process_int(int x) {
    return x * 2;
}

char* process_string(char* s) {
    return s;
}

double process_double(double d) {
    return d + 1.0;
}

struct Point process_point(struct Point p) {
    return p;
}

void test_struct_fields() {
    // Test 1: Simple struct field access
    struct Point p;
    p.x = 10;
    p.y = 20;

    // Should infer: process_int(int)
    int result1 = process_int(p.x);
    int result2 = process_int(p.y);

    // Test 2: Pointer struct field access
    struct Person person;
    person.name = "Alice";
    person.age = 30;

    // Should infer: process_string(char*)
    char* name = process_string(person.name);

    // Should infer: process_int(int)
    int age = process_int(person.age);

    // Test 3: Nested struct field access
    struct Rectangle rect;
    rect.top_left.x = 0;
    rect.top_left.y = 0;
    rect.bottom_right.x = 100;
    rect.bottom_right.y = 100;

    // Should infer: process_int(int) - accessing nested field
    int x1 = process_int(rect.top_left.x);
    int y1 = process_int(rect.top_left.y);

    // Should infer: process_point(struct Point)
    struct Point tl = process_point(rect.top_left);

    // Test 4: Pointer to struct
    struct Person* ptr = &person;

    // Should infer: process_string(char*) - ptr->name
    char* ptr_name = process_string(ptr->name);

    // Should infer: process_int(int) - ptr->age
    int ptr_age = process_int(ptr->age);

    // Test 5: Array in struct
    struct Buffer buf;
    buf.size = 256;

    // Should infer: process_int(int)
    int size = process_int(buf.size);

    // buf.data is char* (array decay)
    char* data = process_string(buf.data);
}

int main() {
    test_struct_fields();
    return 0;
}
