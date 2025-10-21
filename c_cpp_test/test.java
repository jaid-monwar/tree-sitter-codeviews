public class Main {
    public static void main(String[] args) {
        int p = 1;
        int q = 2;
        int r = f1(p, q);
        if(f1(p, q))
            r = r + 1;
    }

    static int f1(int a, int b) {
        int x = f2(a) + f3(b);
        return x;
    }

    static int f2(int a) {
        int y = a + f3(a);
        return y;
    }

    static int f3(int b) {
        int z = b - 3;
        return z;
    }
}

// public class Main {
//     public static void main(String[] args) {
//         p = 1;
//         q = 2;
//         int r = f1(p, q);
//         if(f1(p, q))
//             r = r + 1;
//     }

//     static int f1(int a, int b) {
//         int x = f2(a) + f3(b);
//         return x;
//     }

//     static int f2(int a) {
//         int y = a + f3(a);
//         return y;
//     }

//     static int f3(int b) {
//         int z = b - 3;
//         return z;
//     }
// }