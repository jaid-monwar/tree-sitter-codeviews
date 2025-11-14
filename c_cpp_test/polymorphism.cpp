#include <iostream>
#include <cmath>

class A {
public:
    static void f1(int &a) {
        a = a + 30;
        a = a / 2;
    }
};

class B {
public:
    static void f1(int *a) {
        *a = *a + 130.50;
        *a = *a * 5.3;
    }
};

int main() {
    int x = 0;
    A::f1(x);
    B::f1(&x);
    std::cout << x;
}