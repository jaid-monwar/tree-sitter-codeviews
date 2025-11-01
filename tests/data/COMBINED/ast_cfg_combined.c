// Combined AST + CFG test
int main() {
    int x = 10;

    if (x > 5) {
        x = x * 2;
    } else {
        x = x / 2;
    }

    return x;
}
