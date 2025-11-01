// Data flow with conditionals
int main() {
    int x = 10;
    int y;

    if (x > 5) {
        y = x * 2;
    } else {
        y = x / 2;
    }

    int z = y + 1;
    return z;
}
