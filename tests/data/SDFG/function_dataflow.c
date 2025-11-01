// Data flow with function calls
int add(int a, int b) {
    return a + b;
}

int main() {
    int x = 5;
    int y = 10;
    int result = add(x, y);
    int final = result * 2;
    return final;
}
