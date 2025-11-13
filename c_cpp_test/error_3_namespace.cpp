#include <iostream>  
namespace Room1 {
    int p = 30;
    // Function greet inside namespace Room1
    void greet(int x) {
        x++;
        std::cout << x << "Hello from Room 1!" << std::endl;
    }
}

namespace Room2 {
    int p = 100;
    // Function greet inside namespace Room2
    void greet(int a, int b) {
        a++;
        b--;
        std::cout << a << b << "Hello from Room 2!" << std::endl;
    }
}

int main() {
    // Use the scope resolution operator (::) to access greet() function inside namespace Room1
    Room1::greet(1);  
    Room2::greet(2, 3); 

    Room1::p = 61;
    std::cout << Room1::p << std::endl;
    
    return 0;  
}