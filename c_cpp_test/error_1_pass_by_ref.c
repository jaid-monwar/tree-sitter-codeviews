int fn(int* c) {
    *c = 100;
    return *c;
}

int main() {
    int k = 0;
    fn(&k);
    printf("%d\n", k);
}