// Test comprehensive preprocessor directive evaluation
#define DEBUG 1
#define VERSION 2
#define FEATURE_X

int main() {
    // Test #ifdef - should include
    #ifdef DEBUG
    int debug_var = 1;
    #endif

    // Test #ifndef - should include (RELEASE not defined)
    #ifndef RELEASE
    int not_release = 2;
    #endif

    // Test #ifdef with undefined - should exclude
    #ifdef UNDEFINED_MACRO
    int undefined_var = 3;
    #endif

    // Test #if with comparison - should exclude VERSION == 1
    #if VERSION == 1
    int version_one = 4;
    #elif VERSION == 2
    int version_two = 5;  // Should include this
    #else
    int version_other = 6;
    #endif

    // Test simple #if - should include
    #if DEBUG
    int debug_active = 7;
    #endif

    // Test nested conditionals
    #ifdef FEATURE_X
    int feature_x = 8;
        #ifdef DEBUG
        int feature_x_debug = 9;
        #endif
    #endif

    return 0;
}
