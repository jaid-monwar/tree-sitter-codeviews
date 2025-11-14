#include <iostream>

int fn(int &a) {
    a = a + 100;
    return 0;
}

int fn_value(int a) {
    a = a + 100;
    return 0;
}

int main() {
    int k = 30;
    fn(k);
    std::cout << k << "\n";     // 130 will be printed
    fn(k);
    std::cout << k << "\n";     // 230 will be printed
}