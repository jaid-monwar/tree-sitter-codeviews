// Basic pointer operations
int main() {
    int x = 10;
    int *ptr = &x;
    int **pptr = &ptr;

    *ptr = 20;
    **pptr = 30;

    int y = *ptr;

    return 0;
}
