/**
 * @file
 * @brief Implementation of [Floyd's Cycle
 * Detection](https://en.wikipedia.org/wiki/Cycle_detection) algorithm
 * @details
 * Given an array of integers containing `n + 1` integers, where each
 * integer is in the range [1, n] inclusive. If there is only one duplicate
 * number in the input array, this algorithm returns the duplicate number in
 * O(1) space and the time complexity is less than O(n^2) without modifying the
 * original array, otherwise, it returns -1.
 * @author [Swastika Gupta](https://github.com/Swastyy)
 */

/**
 * @brief The main function implements the search algorithm
 * @param in_arr the input array
 * @param n size of the array
 * @returns the duplicate number
 */
public class FloydCycleDetection {
    
    public static int duplicateNumber(final int[] in_arr, int n) {
        if (n <= 1) {  // to find duplicate in an array its size should be at least 2
            return -1;
        }
        int tortoise = in_arr[0];  ///< variable tortoise is used for the longer
                                  ///< jumps in the array
        int hare = in_arr[0];  ///< variable hare is used for shorter jumps in the array
        do {                                   // loop to enter the cycle
            tortoise = in_arr[tortoise];       // tortoise is moving by one step
            hare = in_arr[in_arr[hare]];       // hare is moving by two steps
        } while (tortoise != hare);
        tortoise = in_arr[0];
        while (tortoise != hare) {             // loop to find the entry point of cycle
            tortoise = in_arr[tortoise];
            hare = in_arr[hare];
        }
        return tortoise;
    }

    /**
     * @brief Self-test implementations
     * @returns void
     */
    private static void test() {
        int[] arr = {1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610}; // input array
        int n = arr.length;

        System.out.print("1st test... ");
        int index = duplicateNumber(arr, n); // calling the duplicateNumber function to check which number occurs twice in the array
        assert index == 1 : "Failed"; // the number which occurs twice is 1 or not
        System.out.println("passed");
    }

    /**
     * @brief Main function
     * @returns 0 on exit
     */
    public static void main(String[] args) {
        test();  // run self-test implementations
    }
}