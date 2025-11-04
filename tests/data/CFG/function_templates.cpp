#include <iostream>

template <typename T>
T add(T a, T b) {
  return a + b;
}

template char add<char>(char a, char b);

int main() {
  int int_sum = add(5, 10);
  std::cout << "The sum of the integers is: " << int_sum << std::endl;

  double double_sum = add(3.5, 7.2);
  std::cout << "The sum of the doubles is: " << double_sum << std::endl;

  char char_sum = add('a', 'b');
  std::cout << "The sum of the characters is: " << char_sum << std::endl;

  float float_sum = add<float>(2.3f, 4.5f);
  std::cout << "The sum of the floats is: " << float_sum << std::endl;

  return 0;
}