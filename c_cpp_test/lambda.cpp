#include <iostream>
#include <functional> // Needed for std::function
using namespace std;

// A function that takes another function as parameter
void myFunction(function<void(int x)> func) {
  int k = 30;
  func(k);
  func(k+3);
}

int main() {
  auto message = [](int x) {
    cout << x << "Hello World!\n";
  };

  myFunction(message);
  return 0;
}