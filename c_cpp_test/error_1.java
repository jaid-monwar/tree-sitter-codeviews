public class Main {
    
    public static double average(int num, int... args) {
        double sum = 0.0;
        
        /* access all the arguments assigned to args */
        for (int i = 0; i < num; i++) {
            sum += args[i];
        }
        
        return sum / num;
    }
    
    public static void main(String[] args) {
        System.out.printf("Average of 2, 3, 4, 5 = %f\n", average(4, 2, 3, 4, 5));
        System.out.printf("Average of 5, 10, 15 = %f\n", average(3, 5, 10, 15));
    }
}