#include <iostream>

int f1() { return 1; }
int f2() { return 2; }

int main() {
    int node = 31;

    (node > 0) ? f1() : f2();

    if (node == 31 || node < 0) {
        std::cout << "a";
    } else if (node > 100) {
        std::cout << "b";
    } else {
        std::cout << "c";
    }

    std::cout << "if done\n";

    switch (node) {
        case 10:
            std::cout << "10";
            break;
        case 31:
            node++;
        default:
            std::cout << "default\n";
    }

    for (int i = 0; i < node; i++) {
        node += 10;
        node /= 2;
        std::cout << node << "\n";
    }

    return 0;
}