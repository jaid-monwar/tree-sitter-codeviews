// Data flow with arrays
int main() {
    int arr[5] = {1, 2, 3, 4, 5};
    int x = arr[0];
    arr[1] = x + 10;
    int y = arr[1];
    return y;
}
