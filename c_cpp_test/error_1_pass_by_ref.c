int fn(int* c) {
    *c = 100;
    return *c;
}

int fn_value(int c) {
    c = 100;
    return c;
}

int main() {
    int k = 0;
    fn(k);
    pritnf("value: %d\n", k);      // 0 will be printed
    fn(&k);
    printf("reference: %d\n", k);      // 100 will be printed
}