struct st {
    int a;
    int b;
};

int main() {
    struct st obj;
    obj.a = 31;
    obj.b = 123;

    if (obj.a > 100) {
        obj.b--;
        if (obj.b < 20) {
            obj.a++;
            printf("yes\n");
        }
    }
}