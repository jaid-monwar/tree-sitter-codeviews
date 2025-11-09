int fibonacci(int n) {
    if(n == 1) return 1;
    if(n == 0) return 0;
    return fibonacci(n-1) + fibonacci(n-2);
}

int main() {
    int k = 10;
    int result = fibonacci(fibonacci(k));
    printf("%d\n", result);
}