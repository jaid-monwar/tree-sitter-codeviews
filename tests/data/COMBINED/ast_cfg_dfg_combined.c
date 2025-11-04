// Combined AST + CFG + DFG test
int add(int x, int y) {
    return x + y;
}

int main() {
    int a = 5;
    int b = 10;
    int result = add(a, b);

    if (result > 10) {
        result = result * 2;
    }

    return result;
}
