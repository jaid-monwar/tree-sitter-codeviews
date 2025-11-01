// Typedef and enum declarations
typedef int Integer;
typedef float Real;

enum Color {
    RED,
    GREEN,
    BLUE
};

typedef enum {
    MONDAY,
    TUESDAY,
    WEDNESDAY
} Day;

int main() {
    Integer x = 10;
    Real y = 3.14;

    enum Color c = RED;
    Day d = MONDAY;

    return 0;
}
