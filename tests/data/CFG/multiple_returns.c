// Multiple return statements
int max(int a, int b) {
    if (a > b) {
        return a;
    }
    return b;
}

int main() {
    int x = 10;
    int y = 20;

    if (x > 0) {
        return max(x, y);
    } else if (x < 0) {
        return -1;
    }

    return 0;
}
