// Combined CFG + DFG test
int main() {
    int a = 5;
    int b = 10;
    int sum = a + b;

    if (sum > 10) {
        sum = sum * 2;
    }

    return sum;
}
