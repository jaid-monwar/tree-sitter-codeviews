// Nested loops
int main() {
    int sum = 0;

    for (int i = 0; i < 5; i++) {
        for (int j = 0; j < 5; j++) {
            sum = sum + i * j;
        }
    }

    return sum;
}
