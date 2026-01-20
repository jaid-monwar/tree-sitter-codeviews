/*------------------Trie Data Structure----------------------------------*/
/*-------------Implimented for search a word in dictionary---------------*/

/*-----character - 97 used for get the character from the ASCII value-----*/

// needed for strnlen
#define _POSIX_C_SOURCE 200809L

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ALPHABET_SIZE 26

/*--Node in the Trie--*/
struct trie {
    struct trie *children[ALPHABET_SIZE];
    bool end_of_word;
};


/*--Create new trie node--*/
int trie_new (
    struct trie ** trie
)
{
    *trie = calloc(1, sizeof(struct trie));
    if (NULL == *trie) {
        // memory allocation failed
        return -1;
    }
    return 0;
}


/*--Insert new word to Trie--*/
int trie_insert (
    struct trie * trie,
    char *word,
    unsigned word_len
)
{
    int ret = 0;

    // this is the end of this word; add an end-of-word marker here and we're
    // done.
    if (0 == word_len) {
        trie->end_of_word = true;
        return 0;
    }

    // if you have some more complex mapping, you could introduce one here. In
    // this easy example, we just subtract 'a' (97) from it, meaning that 'a' is 0,
    // 'b' is 1, and so on.
    const unsigned int index = word[0] - 'a';

    // this index is outside the alphabet size; indexing this would mean an
    // out-of-bound memory access (bad!). If you introduce a separate map
    // function for indexing, then you could move the out-of-bounds index in
    // there.
    if (ALPHABET_SIZE <= index) {
        return -1;
    }

    // The index does not exist yet, allocate it.
    if (NULL == trie->children[index]) {
        ret = trie_new(&trie->children[index]);
        if (-1 == ret) {
            // creating new trie node failed
            return -1;
        }
    }
    
    // recurse into the child node
    return trie_insert(
        /* trie = */ trie->children[index],
        /* word = */ word + 1,
        /* word_len = */ word_len - 1
    );
}


/*--Search a word in the Trie--*/
int trie_search(
    struct trie * trie,
    char *word,
    unsigned word_len,
    struct trie ** result
)
{
    // we found a match
    if (0 == word_len) {
        *result = trie;
        return 0;
    }

    // same here as in trie_insert, if you have a separate index mapping, add
    // it here. In this example, we just subtract 'a'.
    const unsigned int index = word[0] - 'a';

    // This word contains letters outside the alphabet length; it's invalid.
    // Remember to do this to prevent buffer overflows.
    if (ALPHABET_SIZE <= index) {
        return -1;
    }

    // No match
    if (NULL == trie->children[index]) {
        return -1;
    }

    // traverse the trie
    return trie_search(
        /* trie = */ trie->children[index],
        /* word = */ word + 1,
        /* word_len = */ word_len - 1,
        /* result = */ result
    );
}

/*---Return all the related words------*/
void trie_print (
    struct trie * trie,
    char prefix[],
    unsigned prefix_len
)
{

    // An end-of-word marker means that this is a complete word, print it.
    if (true == trie->end_of_word) {
        printf("%.*s\n", prefix_len, prefix);
    }

    // However, there can be longer words with the same prefix; traverse into
    // those as well.
    for (int i = 0; i < ALPHABET_SIZE; i++) {

        // No words on this character
        if (NULL == trie->children[i]) {
            continue;
        }

        // If you have a separate index mapping, then you'd need the inverse of
        // the map here. Since we subtracted 'a' for the index, we can just add
        // 'a' to get the inverse map function.
        prefix[prefix_len] = i + 'a';

        // traverse the print into the child
        trie_print(trie->children[i], prefix, prefix_len + 1);
    }
}


/*--Free trie recursively--*/
void trie_free(
    struct trie * trie
)
{
    if (NULL == trie) {
        return;
    }

    for (int i = 0; i < ALPHABET_SIZE; i++) {
        if (NULL != trie->children[i]) {
            trie_free(trie->children[i]);
        }
    }
    free(trie);
}


/*--Count total nodes in trie--*/
int trie_count_nodes(
    struct trie * trie
)
{
    if (NULL == trie) {
        return 0;
    }

    int count = 1;  // Count current node
    for (int i = 0; i < ALPHABET_SIZE; i++) {
        if (NULL != trie->children[i]) {
            count += trie_count_nodes(trie->children[i]);
        }
    }
    return count;
}


/*--Count total words in trie--*/
int trie_count_words(
    struct trie * trie
)
{
    if (NULL == trie) {
        return 0;
    }

    int count = 0;
    if (true == trie->end_of_word) {
        count = 1;
    }

    for (int i = 0; i < ALPHABET_SIZE; i++) {
        if (NULL != trie->children[i]) {
            count += trie_count_words(trie->children[i]);
        }
    }
    return count;
}


/*--Check if word exists in trie--*/
int trie_contains(
    struct trie * trie,
    char *word,
    unsigned word_len
)
{
    struct trie * result = NULL;
    int ret = trie_search(trie, word, word_len, &result);

    if (-1 == ret || NULL == result) {
        return 0;  // Word not found
    }

    return result->end_of_word ? 1 : 0;
}


/*--Insert word from null-terminated string--*/
int trie_insert_string(
    struct trie * trie,
    const char *word
)
{
    if (NULL == trie || NULL == word) {
        return -1;
    }
    return trie_insert(trie, (char *)word, strnlen(word, 100));
}


/*--Check if string exists in trie--*/
int trie_contains_string(
    struct trie * trie,
    const char *word
)
{
    if (NULL == trie || NULL == word) {
        return 0;
    }
    return trie_contains(trie, (char *)word, strnlen(word, 100));
}


/*--Check if trie is empty (no words)--*/
int trie_is_empty(
    struct trie * trie
)
{
    if (NULL == trie) {
        return 1;
    }
    return trie_count_words(trie) == 0 ? 1 : 0;
}


/*--Get number of children for a node--*/
int trie_get_child_count(
    struct trie * trie
)
{
    if (NULL == trie) {
        return 0;
    }

    int count = 0;
    for (int i = 0; i < ALPHABET_SIZE; i++) {
        if (NULL != trie->children[i]) {
            count++;
        }
    }
    return count;
}


/*--Check if node is a leaf (no children)--*/
int trie_is_leaf(
    struct trie * trie
)
{
    if (NULL == trie) {
        return 1;
    }
    return trie_get_child_count(trie) == 0 ? 1 : 0;
}


/*--Get trie node for prefix (for testing traversal)--*/
int trie_get_prefix_node(
    struct trie * trie,
    const char *prefix,
    struct trie ** result
)
{
    if (NULL == trie || NULL == prefix || NULL == result) {
        return -1;
    }
    return trie_search(trie, (char *)prefix, strnlen(prefix, 100), result);
}


/*--Insert words from string array (for bulk testing)--*/
int trie_insert_words(
    struct trie * trie,
    const char **words,
    int word_count
)
{
    if (NULL == trie || NULL == words || word_count < 0) {
        return -1;
    }

    int inserted = 0;
    for (int i = 0; i < word_count; i++) {
        if (NULL != words[i]) {
            int ret = trie_insert_string(trie, words[i]);
            if (0 == ret) {
                inserted++;
            }
        }
    }
    return inserted;
}


/*--Check if all words from array exist in trie--*/
int trie_contains_all(
    struct trie * trie,
    const char **words,
    int word_count
)
{
    if (NULL == trie || NULL == words || word_count < 0) {
        return 0;
    }

    for (int i = 0; i < word_count; i++) {
        if (NULL != words[i]) {
            if (0 == trie_contains_string(trie, words[i])) {
                return 0;  // Word not found
            }
        }
    }
    return 1;  // All words found
}


/*--Collect words to buffer (for testing trie_print alternative)--*/
static void trie_collect_words_helper(
    struct trie * trie,
    char prefix[],
    unsigned prefix_len,
    char **buffer,
    int *buffer_index,
    int max_words
)
{
    if (NULL == trie || *buffer_index >= max_words) {
        return;
    }

    if (true == trie->end_of_word) {
        // Allocate and copy word
        buffer[*buffer_index] = malloc(prefix_len + 1);
        if (NULL != buffer[*buffer_index]) {
            memcpy(buffer[*buffer_index], prefix, prefix_len);
            buffer[*buffer_index][prefix_len] = '\0';
            (*buffer_index)++;
        }
    }

    for (int i = 0; i < ALPHABET_SIZE && *buffer_index < max_words; i++) {
        if (NULL == trie->children[i]) {
            continue;
        }
        prefix[prefix_len] = i + 'a';
        trie_collect_words_helper(trie->children[i], prefix, prefix_len + 1,
                                   buffer, buffer_index, max_words);
    }
}


/*--Collect all words starting with prefix into array--*/
int trie_collect_words(
    struct trie * trie,
    const char *prefix,
    char **buffer,
    int max_words
)
{
    if (NULL == trie || NULL == buffer || max_words <= 0) {
        return 0;
    }

    struct trie * start_node = trie;
    char word_buffer[100] = {0};
    unsigned prefix_len = 0;

    // If prefix is provided, navigate to that node first
    if (NULL != prefix && prefix[0] != '\0') {
        prefix_len = strnlen(prefix, 100);
        struct trie * result = NULL;
        int ret = trie_search(trie, (char *)prefix, prefix_len, &result);
        if (-1 == ret || NULL == result) {
            return 0;  // Prefix not found
        }
        start_node = result;
        memcpy(word_buffer, prefix, prefix_len);
    }

    int buffer_index = 0;
    trie_collect_words_helper(start_node, word_buffer, prefix_len,
                               buffer, &buffer_index, max_words);
    return buffer_index;
}


/*--Free collected words buffer--*/
void trie_free_collected_words(
    char **buffer,
    int count
)
{
    if (NULL == buffer) {
        return;
    }
    for (int i = 0; i < count; i++) {
        if (NULL != buffer[i]) {
            free(buffer[i]);
            buffer[i] = NULL;
        }
    }
}
