#include <iostream>

int fn(int &a) {
    a = 100;
    return 0;
}

int fn_value(int a) {
    a = 100;
    return 0;
}

int main() {
    int k = 30;
    fn(k);
    std::cout << k << "\n";     // 30 will be printed
    fn(k);
    std::cout << k << "\n";     // 100 will be printed
}