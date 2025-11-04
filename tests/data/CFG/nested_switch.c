// Nested switch statements
int main() {
    int x = 1;
    int y = 2;
    int result;

    switch (x) {
        case 1:
            switch (y) {
                case 1:
                    result = 11;
                    break;
                case 2:
                    result = 12;
                    break;
                default:
                    result = 10;
            }
            break;
        case 2:
            result = 20;
            break;
        default:
            result = 0;
    }

    return result;
}
