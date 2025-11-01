// Combined test with pointers
int main() {
    int x = 10;
    int *ptr = &x;
    *ptr = 20;

    if (*ptr > 15) {
        x = x + 5;
    }

    return x;
}
