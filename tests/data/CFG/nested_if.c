// Nested if statements
int main() {
    int x = 10;
    int y = 5;
    int result;

    if (x > 0) {
        if (y > 0) {
            result = x + y;
        } else {
            result = x - y;
        }
    } else {
        result = 0;
    }

    return result;
}
