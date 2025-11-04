// Basic struct operations
struct Point {
    int x;
    int y;
};

struct Rectangle {
    struct Point top_left;
    struct Point bottom_right;
};

int main() {
    struct Point p1;
    p1.x = 10;
    p1.y = 20;

    struct Point p2 = {5, 15};

    struct Rectangle rect;
    rect.top_left.x = 0;
    rect.top_left.y = 0;

    return 0;
}
