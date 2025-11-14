#include <iostream>
using namespace std;

class tester
{
    public:
    int x = 0;

    tester() {
        x = 100;
    }

    int func(int a, int b) {
        x += 1;
        return x+a+b;
    }
};

struct tester2
{
    public:
    int x = 0;

    tester2() {
        x = 100;
    }

    int func(int a, int b) {
        x += 2;
        return x+a+b;
    }
};

class tester3
{
    public:
    int x = 0;

    tester3() {
        x = 100;
    }

    int func(int a, int b) {
        x += 3;
        return x+a+b;
    }
};

int main()
{
    int p = 23;
    tester t;
    t.func(p+1, 1);

    tester2 t2;
    t2.func(p+2, 1);

    tester3 t3;
    t3.func(p+3, 1);
}