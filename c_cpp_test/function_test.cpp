#include <iostream>

class temp {
public:
    temp() {
        printf("construction");
    }
    void f1() {
        printf("in f1");
    }
};

int f2() {
    printf("in f2");
    return 100;
}

void f3() {
    printf("in f3");
    return;
}

void f4() {
    printf("in f4");
}

int main() {
    temp t;
    t.f1();
    f2();
    f3();
    f4();
    printf("test over");
}