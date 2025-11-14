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
        x++;
        return x+a+b;
    }
};

int main()
{
    int p = 23;
    tester t;
    t.func(p, 1);
}