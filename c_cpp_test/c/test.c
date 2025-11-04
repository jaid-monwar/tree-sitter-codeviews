#include <stdio.h>

int f1(int a, int b);
int f2(int a);
int f3(int b);

int main() {
    int p = 1;
    int q = 2;
    int r = f1(p, q);
    if(f1(p, q))
        r = r + 1;
    
    return 0;
}

int f1(int a, int b) {
    int x = f2(a) + f3(b);
    return x;
}

int f2(int a) {
    int y = a + f3(a);
    return y;
}

int f3(int b) {
    int z = b - 3;
    return z;
}