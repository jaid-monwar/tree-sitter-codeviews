// Comprehensive CFG correctness validation test
// Tests all control flow constructs to validate CFG correctness

#include <stdio.h>
#include <stdbool.h>

// Test 1: Simple sequential execution
int test_sequential() {
    int a = 1;      // Node A
    int b = 2;      // Node B
    int c = a + b;  // Node C
    return c;       // Node D
    // Expected CFG: A -> B -> C -> D
}

// Test 2: If-else with both branches
int test_if_else(int x) {
    int result;
    if (x > 0) {            // Node A (condition)
        result = x * 2;     // Node B (then)
    } else {
        result = x * -1;    // Node C (else)
    }
    return result;          // Node D (merge)
    // Expected: A -pos-> B -> D
    //           A -neg-> C -> D
}

// Test 3: If without else
int test_if_only(int x) {
    int result = x;         // Node A
    if (x < 0) {            // Node B (condition)
        result = -x;        // Node C (then)
    }
    return result;          // Node D
    // Expected: A -> B -pos-> C -> D
    //           B -neg-> D
}

// Test 4: While loop
int test_while(int n) {
    int sum = 0;            // Node A
    int i = 0;              // Node B
    while (i < n) {         // Node C (condition)
        sum += i;           // Node D (body)
        i++;                // Node E (body)
    }
    return sum;             // Node F
    // Expected: A -> B -> C -pos-> D -> E -> C (back edge)
    //           C -neg-> F
}

// Test 5: For loop
int test_for(int n) {
    int sum = 0;            // Node A
    for (int i = 0; i < n; i++) {  // Node B (for statement)
        sum += i;           // Node C (body)
    }
    return sum;             // Node D
    // Expected: A -> B -pos-> C -> B (back edge)
    //           B -neg-> D
}

// Test 6: Do-while loop
int test_do_while(int n) {
    int i = 0;              // Node A
    do {                    // Node B (do)
        i++;                // Node C (body)
    } while (i < n);        // Node D (condition)
    return i;               // Node E
    // Expected: A -> B -> C -> D -> B (back edge)
    //           D -neg-> E
}

// Test 7: Break statement
int test_break(int n) {
    int i = 0;              // Node A
    while (1) {             // Node B (infinite loop)
        if (i >= n) {       // Node C (condition)
            break;          // Node D (break)
        }
        i++;                // Node E
    }
    return i;               // Node F
    // Expected: A -> B -> C -pos-> D -> F (break jumps out)
    //           C -neg-> E -> B (back edge)
}

// Test 8: Continue statement
int test_continue(int n) {
    int sum = 0;            // Node A
    for (int i = 0; i < n; i++) {  // Node B
        if (i % 2 == 0) {   // Node C
            continue;       // Node D (continue)
        }
        sum += i;           // Node E
    }
    return sum;             // Node F
    // Expected: B -> C -pos-> D -> B (continue jumps to loop header)
    //           C -neg-> E -> B
    //           B -neg-> F (exit)
}

// Test 9: Switch-case with fall-through
int test_switch(int x) {
    int result = 0;         // Node A
    switch (x) {            // Node B (switch)
        case 1:             // Node C
            result = 1;     // Node D
            break;          // Node E
        case 2:             // Node F
            result = 2;     // Node G
            // Fall through
        case 3:             // Node H
            result = 3;     // Node I
            break;          // Node J
        default:            // Node K
            result = -1;    // Node L
    }
    return result;          // Node M
    // Expected: B -> C, B -> F, B -> H, B -> K
    //           C -> D -> E -> M (break)
    //           F -> G -> H (fall through)
    //           H -> I -> J -> M (break)
    //           K -> L -> M
}

// Test 10: Nested if statements
int test_nested_if(int x, int y) {
    if (x > 0) {            // Node A
        if (y > 0) {        // Node B
            return 1;       // Node C
        } else {
            return 2;       // Node D
        }
    } else {
        return 3;           // Node E
    }
    // Expected: A -pos-> B -pos-> C
    //           B -neg-> D
    //           A -neg-> E
}

// Test 11: Nested loops
int test_nested_loops(int n) {
    int sum = 0;            // Node A
    for (int i = 0; i < n; i++) {      // Node B (outer)
        for (int j = 0; j < n; j++) {  // Node C (inner)
            sum += i + j;   // Node D
        }
    }
    return sum;             // Node E
    // Expected: A -> B -pos-> C -pos-> D -> C (inner back edge)
    //           C -neg-> B (inner exit to outer)
    //           B -neg-> E (outer exit)
}

// Test 12: Goto and labels
int test_goto(int x) {
    int result = 0;         // Node A
    if (x < 0) {            // Node B
        goto error;         // Node C (goto)
    }
    result = x * 2;         // Node D
    goto end;               // Node E
error:                      // Node F (label)
    result = -1;            // Node G
end:                        // Node H (label)
    return result;          // Node I
    // Expected: A -> B -pos-> C -> F (goto jump)
    //           B -neg-> D -> E -> H (goto jump)
    //           F -> G -> H
    //           H -> I
}

// Test 13: Multiple returns
int test_multiple_returns(int x) {
    if (x < 0) {            // Node A
        return -1;          // Node B (early return)
    }
    if (x == 0) {           // Node C
        return 0;           // Node D (early return)
    }
    return x;               // Node E (final return)
    // Expected: A -pos-> B (return)
    //           A -neg-> C -pos-> D (return)
    //           C -neg-> E (return)
}

// Test 14: Function calls
int helper(int x) {
    return x * 2;
}

int test_function_calls(int x) {
    int a = helper(x);      // Node A (call)
    int b = helper(a);      // Node B (call)
    return helper(b);       // Node C (call)
    // Expected: A -> B -> C
    // Plus function_call edges: A -> helper, helper -> A
}

// Test 15: Complex control flow
int test_complex(int n) {
    int result = 0;         // Node A
    for (int i = 0; i < n; i++) {  // Node B
        if (i % 2 == 0) {   // Node C
            if (i % 3 == 0) {   // Node D
                continue;   // Node E
            }
            result += i;    // Node F
        } else {
            if (i > 10) {   // Node G
                break;      // Node H
            }
            result -= i;    // Node I
        }
    }
    return result;          // Node J
    // Complex nested control flow with multiple paths
}

int main() {
    test_sequential();
    test_if_else(5);
    test_if_only(-3);
    test_while(10);
    test_for(10);
    test_do_while(5);
    test_break(5);
    test_continue(10);
    test_switch(2);
    test_nested_if(1, 1);
    test_nested_loops(3);
    test_goto(5);
    test_multiple_returns(5);
    test_function_calls(5);
    test_complex(20);
    return 0;
}
