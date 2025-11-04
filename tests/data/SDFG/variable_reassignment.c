// Variable reassignment tracking
int main() {
    int x = 10;
    int y = x;
    x = 20;
    int z = x + y;
    return z;
}
