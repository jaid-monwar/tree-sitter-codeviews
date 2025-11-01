#include <iostream>
#include <vector>
using namespace std;

// Function demonstrating return statements
int findNumber(const vector<int>& numbers, int target) {
    for (int i = 0; i < numbers.size(); i++) {
        if (numbers[i] == target) {
            return i;  // Return with value - early exit
        }
    }
    return -1;  // Return with value - default case
}

// Void function demonstrating return
void printUntilNegative(const vector<int>& numbers) {
    for (int num : numbers) {
        if (num < 0) {
            cout << "Found negative number, stopping!\n";
            return;  // Return void - early exit
        }
        cout << num << " ";
    }
    cout << "All numbers processed!\n";
    // Implicit return for void function
}

// Function with multiple return points
string evaluateNumber(int num) {
    if (num > 100) {
        return "Very large";  // First return point
    }
    else if (num > 50) {
        return "Large";       // Second return point
    }
    else if (num > 0) {
        return "Small";       // Third return point
    }
    else {
        return "Non-positive"; // Fourth return point
    }
}

int main() {
    cout << "=== DEMONSTRATING JUMP STATEMENTS ===\n\n";
    
    // 1. BREAK FROM LOOPS
    cout << "1. Break from Loops (searching for 5):\n";
    vector<int> numbers = {1, 3, 7, 5, 9, 2, 8};
    
    for (int num : numbers) {
        cout << "Checking: " << num << "\n";
        if (num == 5) {
            cout << "Found 5! Breaking loop.\n";
            break;  // Break from loop
        }
    }
    cout << "\n";
    
    // 2. BREAK FROM SWITCH
    cout << "2. Break from Switch (menu selection):\n";
    int choice = 2;
    
    switch(choice) {
        case 1:
            cout << "Option 1 selected\n";
            break;  // Break from switch
        case 2:
            cout << "Option 2 selected\n";
            break;  // Break from switch
        case 3:
            cout << "Option 3 selected\n";
            break;  // Break from switch
        default:
            cout << "Invalid option\n";
    }
    cout << "\n";
    
    // 3. CONTINUE IN LOOPS
    cout << "3. Continue in Loops (skip even numbers):\n";
    cout << "Odd numbers from 1-10: ";
    for (int i = 1; i <= 10; i++) {
        if (i % 2 == 0) {
            continue;  // Skip even numbers
        }
        cout << i << " ";
    }
    cout << "\n\n";
    
    // 4. RETURN WITH VALUE
    cout << "4. Return with Value (search function):\n";
    vector<int> data = {10, 20, 30, 40, 50};
    int target = 30;
    int position = findNumber(data, target);
    cout << "Number " << target << " found at position: " << position << "\n\n";
    
    // 5. RETURN VOID
    cout << "5. Return Void (print until negative):\n";
    vector<int> mixedNumbers = {1, 3, 5, -2, 7, 9};
    cout << "Printing numbers: ";
    printUntilNegative(mixedNumbers);
    cout << "\n";
    
    // 6. MULTIPLE RETURN POINTS
    cout << "6. Multiple Return Points (number evaluation):\n";
    cout << "75 is: " << evaluateNumber(75) << "\n";
    cout << "25 is: " << evaluateNumber(25) << "\n";
    cout << "150 is: " << evaluateNumber(150) << "\n";
    cout << "-5 is: " << evaluateNumber(-5) << "\n\n";
    
    // 7. GOTO WITH LABELS
    cout << "7. Goto with Labels (error handling simulation):\n";
    int userInput;
    
    cout << "Enter a positive number: ";
    cin >> userInput;
    
    if (userInput <= 0) {
        goto error_handler;  // Goto to label
    }
    
    cout << "You entered a valid number: " << userInput << "\n";
    goto success_exit;  // Goto to label
    
    // Label declarations
    error_handler:
        cout << "ERROR: Number must be positive!\n";
        goto end_program;
    
    success_exit:
        cout << "SUCCESS: Number accepted!\n";
        goto end_program;
    
    end_program:
        cout << "Program completed.\n\n";
    
    // 8. MORE COMPLEX GOTO EXAMPLE
    cout << "8. Complex Goto (matrix search):\n";
    int matrix[3][3] = {
        {1, 2, 3},
        {4, 5, 6},
        {7, 8, 9}
    };
    int searchValue = 5;
    
    // Nested loops with goto break
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            if (matrix[i][j] == searchValue) {
                cout << "Found " << searchValue << " at position [" << i << "][" << j << "]\n";
                goto found;  // Break out of nested loops
            }
        }
    }
    cout << searchValue << " not found in matrix\n";
    goto not_found;
    
    found:
        cout << "Search completed successfully!\n";
        goto end_search;
    
    not_found:
        cout << "Search failed!\n";
    
    end_search:
        cout << "Matrix search finished.\n\n";
    
    // 9. CONTINUE WITH WHILE LOOP
    cout << "9. Continue with While Loop (skip multiples of 3):\n";
    int counter = 0;
    cout << "Numbers 1-10 that are not multiples of 3: ";
    while (counter < 10) {
        counter++;
        if (counter % 3 == 0) {
            continue;  // Skip multiples of 3
        }
        cout << counter << " ";
    }
    cout << "\n\n";
    
    // 10. BREAK WITH DO-WHILE LOOP
    cout << "10. Break with Do-While Loop (count until 5):\n";
    int count = 1;
    do {
        cout << count << " ";
        if (count == 5) {
            break;  // Break from do-while
        }
        count++;
    } while (count <= 10);
    cout << "\nLoop broken at 5\n";
    
    return 0;  // Final return from main
}