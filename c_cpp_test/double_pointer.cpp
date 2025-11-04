#include <stdio.h>

class test_class {
public:
    void test_function() {
        printf("hello world\n");
    }
};

int main() {
  
  	test_class a;
    test_class *b = &a;
    test_class **c = &b;
    a.test_function();
    b->test_function();
    (*c)->test_function();

    return 0;
}