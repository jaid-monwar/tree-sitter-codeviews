// Data flow with nested scopes
int main() {
    int x = 10;

    if (x > 0) {
        int y = x * 2;
        x = y + 5;
    }

    int z = x + 1;
    return z;
}
