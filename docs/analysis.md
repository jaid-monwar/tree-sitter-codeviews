# Comex Codebase Analysis

This document contains a comprehensive analysis of the Comex (Tree Sitter Multi Codeview Generator) codebase architecture and parsing pipeline.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [CLAUDE.md File Status](#claudemd-file-status)
3. [Understanding the Parser Hierarchy](#understanding-the-parser-hierarchy)
4. [Adding C/C++ Support](#adding-cc-support)
5. [Utils Folder Files](#utils-folder-files)
6. [ParserDriver Step - Detailed Explanation](#parserdriver-step---detailed-explanation)
7. [The 7 Key Data Structures](#the-7-key-data-structures)
8. [Language Nodes Classification](#language-nodes-classification)
9. [Connection Between parser_driver and java_nodes](#connection-between-parser_driver-and-java_nodes)
10. [SDFG Explained](#sdfg-explained)

---

## Project Overview

**Comex** (Tree Sitter Multi Codeview Generator) is a Python package that generates combined multi-code view graphs (AST, CFG, DFG, and combinations) for Java and C# source code. It uses [tree-sitter](https://tree-sitter.github.io/tree-sitter/) for parsing and NetworkX for graph generation.

### Supported Languages
- Java
- C# (cs)

### Supported Codeviews
- **AST** (Abstract Syntax Tree)
- **CFG** (Control Flow Graph)
- **DFG** (Data Flow Graph)
- **CST** (Concrete Syntax Tree)
- **SDFG** (Statement-level Data Flow Graph)
- **Combined graphs** (any combination of the above)

---

## CLAUDE.md File Status

The CLAUDE.md file already exists and is well-structured! It covers:

1. **Commands commonly used**:
   - Installation: `pip install -r requirements-dev.txt`
   - Testing commands: `pytest`, `pytest -k 'test_cfg[cs-test7]' --no-cov`, `pytest -k 'test_cfg[cs-test7]' --no-cov -vv`
   - CLI usage examples
   - Publishing workflow

2. **High-level architecture**:
   - Four-layer flow: Parsing → Codeview Generation → Combination → Output
   - Key components in each layer with file references
   - Extension pattern for adding new languages

The file is comprehensive and follows best practices. It doesn't include generic advice or obvious instructions, focuses on the big picture architecture, and provides practical commands.

---

## Understanding the Parser Hierarchy

### Parser Hierarchy

**`custom_parser.py`** is the **base class** that provides common parsing functionality shared by all languages. It's not a standalone parser for a specific language.

**`java_parser.py`** and **`cs_parser.py`** are **language-specific parsers** that **inherit from** `CustomParser` and add language-specific logic.

### How it works:

1. **CustomParser** ([custom_parser.py](src/comex/tree_parser/custom_parser.py)):
   - Base class with common functionality
   - Initializes tree-sitter parser
   - Creates AST node IDs
   - Defines common data structures (symbol_table, method_map, etc.)
   - Provides the generic `parse()` method

2. **JavaParser** ([java_parser.py](src/comex/tree_parser/java_parser.py)):
   - Extends `CustomParser`
   - Implements `create_all_tokens()` with Java-specific logic
   - Handles Java-specific syntax (e.g., Java method declarations, variable declarations)

3. **CSParser** ([cs_parser.py](src/comex/tree_parser/cs_parser.py)):
   - Extends `CustomParser`
   - Implements `create_all_tokens()` with C#-specific logic
   - Handles C#-specific syntax (e.g., C# namespaces, properties)

### The flow in ParserDriver:

```python
self.parser_map = {
    "java": JavaParser,
    "cs": CSParser,
}
self.parser = self.parser_map[self.src_language](...)
```

When you request Java parsing, it instantiates `JavaParser`, which internally calls `CustomParser.__init__()` to set up the tree-sitter parser, then adds Java-specific token extraction logic.

**Think of it like inheritance in OOP:**
- `CustomParser` = Abstract base class
- `JavaParser`, `CSParser` = Concrete implementations for specific languages

---

## Adding C/C++ Support

### Steps to Add C/C++ Support

No, you **do not need to modify** `custom_parser.py` in most cases. Here's what you need to do:

#### 1. **Add tree-sitter grammars** in [src/comex/__init__.py](src/comex/__init__.py)

```python
grammar_repos = [
    ("https://github.com/tree-sitter/tree-sitter-java", "09d650def6cdf7f479f4b78f595e9ef5b58ce31e"),
    ("https://github.com/tree-sitter/tree-sitter-c-sharp", "3ef3f7f99e16e528e6689eae44dff35150993307"),
    # Add these:
    ("https://github.com/tree-sitter/tree-sitter-c", "<commit-hash>"),
    ("https://github.com/tree-sitter/tree-sitter-cpp", "<commit-hash>"),
]
```

And in the `get_language_map()` function:
```python
C_LANGUAGE = Language(shared_languages, "c")
CPP_LANGUAGE = Language(shared_languages, "cpp")

return {
    "java": JAVA_LANGUAGE,
    "cs": C_SHARP_LANGUAGE,
    "c": C_LANGUAGE,
    "cpp": CPP_LANGUAGE,
}
```

#### 2. **Create language-specific parsers**

Create [src/comex/tree_parser/c_parser.py](src/comex/tree_parser/c_parser.py):
```python
from .custom_parser import CustomParser

class CParser(CustomParser):
    def create_all_tokens(self, src_code, root_node, all_tokens, label,
                         method_map, method_calls, start_line,
                         declaration, declaration_map, symbol_table):
        # Implement C-specific token extraction logic
        # Similar to JavaParser but for C syntax
        pass
```

Similarly create [src/comex/tree_parser/cpp_parser.py](src/comex/tree_parser/cpp_parser.py)

#### 3. **Register parsers** in [parser_driver.py](src/comex/tree_parser/parser_driver.py)

```python
from ..tree_parser.java_parser import JavaParser
from ..tree_parser.cs_parser import CSParser
from ..tree_parser.c_parser import CParser
from ..tree_parser.cpp_parser import CppParser

class ParserDriver:
    def __init__(self, src_language, src_code):
        # ...
        self.parser_map = {
            "java": JavaParser,
            "cs": CSParser,
            "c": CParser,      # Add
            "cpp": CppParser,  # Add
        }
```

#### 4. **Create node definitions** in `src/comex/utils/`

- [src/comex/utils/c_nodes.py](src/comex/utils/c_nodes.py)
- [src/comex/utils/cpp_nodes.py](src/comex/utils/cpp_nodes.py)

#### 5. **Add language-specific CFG/SDFG** if needed

- [src/comex/codeviews/CFG/CFG_c.py](src/comex/codeviews/CFG/CFG_c.py)
- [src/comex/codeviews/SDFG/SDFG_c.py](src/comex/codeviews/SDFG/SDFG_c.py)

### When would you modify `custom_parser.py`?

Only if you need to add functionality that **all languages** share, such as:
- A new common data structure
- A new generic helper method
- Changes to the core parsing initialization

**In summary**: `CustomParser` stays unchanged. You just create new subclasses that inherit from it.

---

## Utils Folder Files

### Overview

Here's a breakdown of each file in the `utils/` folder and their role during parsing:

### 1. **[preprocessor.py](src/comex/utils/preprocessor.py)** - Code Cleaning (Pre-parsing)
- **Purpose**: Clean source code before parsing
- **Functions**:
  - `remove_empty_lines()`: Removes blank lines
  - `remove_comments()`: Strips comments (line and block comments for Java/C#/C++, docstrings for Python)
- **Impact**: Called by `ParserDriver` to normalize code before tree-sitter parsing

### 2. **[postprocessor.py](src/comex/utils/postprocessor.py)** - Output Generation (Post-parsing)
- **Purpose**: Convert NetworkX graphs to output formats
- **Functions**:
  - `write_networkx_to_json()`: Exports graph as JSON
  - `write_to_dot()`: Exports graph as DOT/PNG using GraphViz
- **Impact**: Used by `CombinedDriver` to generate final output files

### 3. **[java_nodes.py](src/comex/utils/java_nodes.py)** & **[cs_nodes.py](src/comex/utils/cs_nodes.py)** - Language Definitions
- **Purpose**: Define language-specific AST node types
- **Contains**:
  - `statement_types`: Lists of statement node types (control, non-control, loops)
  - `node_list_type`: All valid statement types
  - Used for CFG/DFG generation to identify control flow points
- **Impact**: Used by language-specific parsers and CFG/SDFG implementations to categorize nodes

### 4. **[DFG_utils.py](src/comex/utils/DFG_utils.py)** - Token Extraction Helpers
- **Purpose**: Helper functions for extracting tokens from tree-sitter AST
- **Functions**:
  - `tree_to_token_index()`: Converts AST to token indices
  - `tree_to_variable_index()`: Extracts variable tokens
  - `index_to_code_token()`: Maps index positions to actual code strings
- **Impact**: Used by DFG generation to identify variables and data dependencies

### 5. **[src_parser.py](src/comex/utils/src_parser.py)** - Code Formatting & Traversal
- **Purpose**: Tree traversal and code reformatting utilities
- **Functions**:
  - `traverse_tree()`: Iterator for walking through AST nodes
  - `pre_process_src()`: Reformats code based on statement boundaries (adds newlines)
- **Impact**: Used for code normalization and preprocessing before analysis

### Parsing Pipeline with Utils

```
Source Code
    ↓
preprocessor.py → Remove comments/empty lines
    ↓
ParserDriver → Parse with tree-sitter
    ↓
{language}_nodes.py → Classify node types
    ↓
DFG_utils.py → Extract tokens (for DFG)
src_parser.py → Traverse & format (for CFG/SDFG)
    ↓
Codeview Generation (AST/CFG/DFG)
    ↓
postprocessor.py → Export to JSON/DOT/PNG
```

**Key takeaway**: Utils are helper modules - preprocessing input, defining language syntax, and formatting output. The actual parsing happens in `tree_parser/`.

---

## ParserDriver Step - Detailed Explanation

The ParserDriver orchestrates the parsing process by routing to language-specific parsers and extracting critical information from the source code.

### File Breakdown

#### 1. **[parser_driver.py](src/comex/tree_parser/parser_driver.py)**
**Language**: ❌ **Language-agnostic** (works for all languages)

##### Purpose
Central coordinator that:
1. Preprocesses source code
2. Routes to the correct language-specific parser
3. Triggers token extraction

##### Key Components

**`__init__(src_language, src_code)`**
```python
def __init__(self, src_language, src_code):
    # 1. Preprocess the code
    self.src_code = self.pre_process_src_code(src_language, src_code)

    # 2. Select the right parser
    self.parser_map = {
        "java": JavaParser,
        "cs": CSParser,
    }

    # 3. Instantiate language-specific parser
    self.parser = self.parser_map[self.src_language](self.src_language, self.src_code)

    # 4. Parse the code
    self.root_node, self.tree = self.parser.parse()

    # 5. Extract all tokens and metadata
    (self.all_tokens, self.label, self.method_map,
     self.method_calls, self.start_line, self.declaration,
     self.declaration_map, self.symbol_table) = self.create_all_tokens()
```

**`pre_process_src_code()`**
- Calls `preprocessor.remove_empty_lines()` and `preprocessor.remove_comments()`
- Returns cleaned code

**`create_all_tokens()`**
- Delegates to the language-specific parser's `create_all_tokens()` method

#### 2. **[custom_parser.py](src/comex/tree_parser/custom_parser.py)**
**Language**: ❌ **Language-agnostic base class**

##### Purpose
Base class providing common parsing infrastructure for all languages.

##### Key Components

**`__init__(src_language, src_code)`**
```python
def __init__(self, src_language, src_code):
    self.src_language = src_language
    self.src_code = src_code
    self.index = {}  # Maps (start_point, end_point, type) → AST node ID

    # Initialize tree-sitter
    self.language_map = get_language_map()  # Gets Java/C# grammars
    self.root_node, self.tree = self.parse()

    # Initialize empty data structures (to be filled by subclasses)
    self.all_tokens = []          # All leaf node IDs
    self.label = {}               # {node_id: text_content}
    self.method_map = []          # List of method identifier node IDs
    self.method_calls = []        # List of method call node IDs
    self.start_line = {}          # {node_id: line_number}
    self.declaration = {}         # {node_id: variable_name} for declarations
    self.declaration_map = {}     # {usage_node_id: declaration_node_id}
    self.symbol_table = {
        "scope_stack": [0],       # Stack of active scope IDs
        "scope_map": {},          # {node_id: [scope_ids]}
        "scope_id": 0,            # Current scope counter
        "data_type": {},          # {node_id: type_string}
    }
```

**`parse()`**
```python
def parse(self):
    # 1. Create tree-sitter parser
    parser = Parser()
    parser.set_language(self.language_map[self.src_language])

    # 2. Parse source code into AST
    tree = parser.parse(bytes(self.src_code, "utf8"))
    self.root_node = tree.root_node

    # 3. Assign unique IDs to all named nodes
    self.create_AST_id(self.root_node, self.index, [5])  # Start from ID 5

    return self.root_node, tree
```

**`create_AST_id(root_node, AST_index, AST_id)`**
```python
def create_AST_id(self, root_node, AST_index, AST_id):
    """Recursively assign unique IDs to all named AST nodes"""
    if root_node.is_named:
        current_node_id = AST_id[0]
        AST_id[0] += 1  # Increment counter

        # Map (start, end, type) → unique_id
        AST_index[(root_node.start_point, root_node.end_point, root_node.type)] = current_node_id

        # Recurse to children
        for child in root_node.children:
            if child.is_named:
                self.create_AST_id(child, AST_index, AST_id)
```

**Key Data Structures Created:**
- `self.index`: `{(start_point, end_point, type): node_id}`
  - Example: `{((0, 0), (0, 5), 'identifier'): 5}`

#### 3. **[java_parser.py](src/comex/tree_parser/java_parser.py)**
**Language**: ✅ **Java-specific**

##### Purpose
Extends `CustomParser` with Java-specific token extraction logic.

##### Key Components

**`__init__(src_language, src_code)`**
```python
def __init__(self, src_language, src_code):
    super().__init__(src_language, src_code)  # Calls CustomParser.__init__()
```

**`create_all_tokens()` - THE MAIN WORKHORSE**

This is a **recursive tree traversal** function that extracts all meaningful information:

```python
def create_all_tokens(self, src_code, root_node, all_tokens, label,
                     method_map, method_calls, start_line,
                     declaration, declaration_map, symbol_table):
```

##### What it does (step by step):

##### Step 1: Scope Management
```python
block_types = ["block", "if_statement", "while_statement", "for_statement", ...]

if root_node.is_named and root_node.type in block_types:
    # Entering a new scope (e.g., entering a method, if-block, loop)
    symbol_table["scope_id"] = symbol_table["scope_id"] + 1
    symbol_table["scope_stack"].append(symbol_table["scope_id"])
```
- **Why?** Tracks variable scope for correct declaration-usage mapping
- **Example**:
  ```java
  void foo() {           // scope 1
      int x = 5;
      if (x > 0) {       // scope 2
          int y = 10;
      }
  }
  ```

##### Step 2: Leaf Node Processing (Tokens)
```python
if (root_node.is_named
    and (len(root_node.children) == 0 or root_node.type == "string")
    and root_node.type != "comment"):

    # Get unique ID for this token
    index = self.index[(root_node.start_point, root_node.end_point, root_node.type)]

    # Extract label (actual text)
    label[index] = root_node.text.decode("UTF-8")

    # Store line number
    start_line[index] = root_node.start_point[0]

    # Add to token list
    all_tokens.append(index)

    # Record which scopes this token belongs to
    symbol_table["scope_map"][index] = symbol_table["scope_stack"].copy()
```

##### Step 3: Method Identification
```python
if (current_node.parent is not None
    and current_node.parent.type in ["method_declaration", "method_invocation"]):
    method_map.append(index)

    if current_node.next_named_sibling.type == "argument_list":
        method_calls.append(index)  # It's a method call
```

##### Step 4: Variable Declaration Detection
```python
if self.check_declaration(current_node):
    variable_name = label[index]
    declaration[index] = variable_name

    variable_type = self.get_type(current_node.parent)
    if variable_type is not None:
        symbol_table["data_type"][index] = variable_type
```

**`check_declaration()` helper:**
```python
def check_declaration(self, current_node):
    parent_types = ["variable_declarator", "catch_formal_parameter", "formal_parameter"]
    current_types = ["identifier"]

    if (current_node.parent is not None
        and current_node.parent.type in parent_types
        and current_node.type in current_types):

        if current_node.parent.type == "variable_declarator":
            # Check if it has '=' (initialization)
            if current_node.next_sibling is not None and current_node.next_sibling.type == "=":
                return True
        return True
    return False
```

**`get_type()` helper:**
```python
def get_type(self, node):
    """Extract the data type from a variable declaration"""
    datatypes = ['type_identifier', 'integral_type', 'floating_point_type',
                 'void_type', 'boolean_type', 'generic_type']

    for child in node.parent.children:
        if child.type in datatypes:
            return child.text.decode('utf-8')
    return None
```

##### Step 5: Variable Usage → Declaration Mapping
```python
else:  # Not a declaration, so it's a usage
    current_scope = symbol_table['scope_map'][index]

    name_matches = []
    for (ind, var) in declaration.items():
        if var == label[index]:  # Same variable name
            parent_scope = symbol_table['scope_map'][ind]
            if self.scope_check(parent_scope, current_scope):  # In scope?
                name_matches.append((ind, var))

    # Find the closest scope match
    closest_index = self.longest_scope_match(name_matches, symbol_table)
    declaration_map[index] = closest_index
```

**`scope_check()` helper:**
```python
def scope_check(self, parent_scope, child_scope):
    """Check if parent_scope is a subset of child_scope"""
    for p in parent_scope:
        if p not in child_scope:
            return False
    return True
```

##### Step 6: Recursion & Scope Exit
```python
else:  # Non-leaf node
    for child in root_node.children:
        self.create_all_tokens(...)  # Recurse

if root_node.is_named and root_node.type in block_types:
    # Exiting scope
    symbol_table["scope_stack"].pop(-1)
```

#### 4. **[cs_parser.py](src/comex/tree_parser/cs_parser.py)**
**Language**: ✅ **C#-specific**

##### Purpose
Same as `JavaParser` but handles C#-specific syntax.

##### Differences from JavaParser:
- Different `block_types`: `["checked_statement", "fixed_statement", "unsafe_statement", ...]`
- Different declaration patterns: `["variable_declarator", "catch_declaration", "parameter"]`
- Handles C#-specific nodes like properties, namespaces

### Complete Data Flow Example

```java
public class Example {
    public void test() {
        int x = 5;
        int y = x + 10;
        System.out.println(y);
    }
}
```

#### After ParserDriver Processing:

**`all_tokens`**: `[5, 6, 7, 8, 9, 10, 11, 12, 13, ...]`

**`label`**:
```python
{
    5: "Example",
    6: "test",
    7: "int",
    8: "x",
    9: "5",
    10: "int",
    11: "y",
    12: "x",
    13: "10",
    ...
}
```

**`declaration`**:
```python
{
    8: "x",    # int x = 5
    11: "y",   # int y = x + 10
}
```

**`declaration_map`**:
```python
{
    12: 8,  # Usage of 'x' at index 12 maps to declaration at index 8
}
```

**`symbol_table["scope_map"]`**:
```python
{
    5: [0],              # class scope
    6: [0, 1],           # method scope
    8: [0, 1, 2],        # inside method body
    11: [0, 1, 2],
    12: [0, 1, 2],
}
```

**`symbol_table["data_type"]`**:
```python
{
    8: "int",
    11: "int",
}
```

**`method_map`**: `[6]` (the "test" identifier)

### Summary: Language-Specific vs Language-Agnostic

| File | Language-Specific? | Role |
|------|-------------------|------|
| [parser_driver.py](src/comex/tree_parser/parser_driver.py) | ❌ No | Coordinator |
| [custom_parser.py](src/comex/tree_parser/custom_parser.py) | ❌ No | Base class, tree-sitter setup |
| [java_parser.py](src/comex/tree_parser/java_parser.py) | ✅ **Yes - Java** | Token extraction for Java |
| [cs_parser.py](src/comex/tree_parser/cs_parser.py) | ✅ **Yes - C#** | Token extraction for C# |

### Key Takeaways

1. **CustomParser** handles generic tree-sitter parsing
2. **Language-specific parsers** (JavaParser/CSParser) implement `create_all_tokens()` with language-specific logic
3. **ParserDriver** orchestrates everything and stores the final results
4. The main output is **7 key data structures** used by all codeview generators (AST/CFG/DFG)

---

## The 7 Key Data Structures

Based on the code analysis, here are the **7 key data structures** that ParserDriver extracts and makes available to all codeview generators:

### 1. **`all_tokens`** (List)
**Type**: `List[int]`

**Purpose**: List of all leaf node IDs (tokens) in the source code

**Example**:
```python
[5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
```

**Used by**:
- AST: To build the tree structure
- DFG: To identify variables and their relationships
- CFG: To identify statement boundaries

### 2. **`label`** (Dictionary)
**Type**: `Dict[int, str]`

**Purpose**: Maps each node ID to its actual text content

**Example**:
```python
{
    5: "Example",      # class name
    6: "test",         # method name
    7: "int",          # type
    8: "x",            # variable name
    9: "5",            # literal value
    10: "int",
    11: "y",
    12: "x",           # variable usage
    13: "10",
    14: "System",
    15: "out"
}
```

**Used by**:
- **All codeviews**: To display readable node labels in the graph
- AST: Node labels
- DFG: Variable names
- CFG: Statement text

### 3. **`method_map`** (List)
**Type**: `List[int]`

**Purpose**: List of node IDs that represent method/function identifiers (both declarations and calls)

**Example**:
```python
[6, 20, 35]  # IDs of method identifiers like "test", "println", "add"
```

**Used by**:
- DFG: To track method calls and their data flow
- CFG: To handle method invocations in control flow
- AST: To identify method nodes

### 4. **`method_calls`** (List)
**Type**: `List[int]`

**Purpose**: Subset of `method_map` - specifically method/function **calls** (not declarations)

**Example**:
```python
[20, 35]  # IDs of "println" and "add" calls (not the "test" declaration)
```

**Used by**:
- DFG: To create data flow edges for method arguments
- CFG: To model control flow through function calls

### 5. **`start_line`** (Dictionary)
**Type**: `Dict[int, int]`

**Purpose**: Maps each node ID to its starting line number in the source code

**Example**:
```python
{
    5: 0,    # "Example" starts at line 0
    6: 1,    # "test" starts at line 1
    8: 2,    # "x" starts at line 2
    11: 3,   # "y" starts at line 3
}
```

**Used by**:
- **All codeviews**: For source location tracking and debugging
- CFG: To order statements by line number
- Output: To annotate nodes with line information

### 6. **`declaration`** (Dictionary)
**Type**: `Dict[int, str]`

**Purpose**: Maps declaration node IDs to the variable/identifier name being declared

**Example**:
```python
{
    8: "x",     # int x = 5;  (node 8 declares "x")
    11: "y",    # int y = x + 10;  (node 11 declares "y")
    25: "i",    # for(int i = 0; ...)  (node 25 declares "i")
}
```

**Used by**:
- **DFG**: Critical for building data dependency edges
- SDFG: For Reaching Definitions Analysis
- Symbol table construction

### 7. **`declaration_map`** (Dictionary)
**Type**: `Dict[int, int]`

**Purpose**: Maps variable **usage** node IDs to their corresponding **declaration** node IDs

**Example**:
```python
{
    12: 8,   # Usage of "x" at node 12 → declared at node 8
    18: 11,  # Usage of "y" at node 18 → declared at node 11
    30: 25,  # Usage of "i" at node 30 → declared at node 25
}
```

**Used by**:
- **DFG**: The foundation for creating "defined-by" edges
- SDFG: Tracks def-use chains
- Data flow analysis

### 8. **`symbol_table`** (Dictionary) - BONUS
**Type**: `Dict[str, Any]`

While technically counted as one structure in the return tuple, it contains multiple sub-structures:

```python
{
    "scope_stack": [0, 1, 2],           # Current active scopes (stack)

    "scope_map": {                      # Maps node_id → list of scopes it belongs to
        5: [0],
        6: [0, 1],
        8: [0, 1, 2],
        12: [0, 1, 2],
    },

    "scope_id": 2,                      # Current scope counter

    "data_type": {                      # Maps node_id → data type
        8: "int",
        11: "int",
        25: "String",
    }
}
```

**Used by**:
- DFG: To resolve variable scoping correctly
- Declaration-usage mapping
- Type information for data flow

### How They're Used in ParserDriver

Looking at [parser_driver.py:26-30](src/comex/tree_parser/parser_driver.py#L26-L30):

```python
(
    self.all_tokens,        # 1
    self.label,             # 2
    self.method_map,        # 3
    self.method_calls,      # 4
    self.start_line,        # 5
    self.declaration,       # 6
    self.declaration_map,   # 7
    self.symbol_table,      # 8 (bonus)
) = self.create_all_tokens()
```

### Visual Example

For this Java code:
```java
public void test() {
    int x = 5;
    int y = x + 10;
}
```

**The 7 data structures would be:**

| Structure | Value |
|-----------|-------|
| `all_tokens` | `[6, 7, 8, 9, 10, 11, 12, 13]` |
| `label` | `{6:"test", 7:"int", 8:"x", 9:"5", 10:"int", 11:"y", 12:"x", 13:"10"}` |
| `method_map` | `[6]` (just "test") |
| `method_calls` | `[]` (no calls in this snippet) |
| `start_line` | `{6:0, 7:1, 8:1, 9:1, 10:2, 11:2, 12:2, 13:2}` |
| `declaration` | `{8:"x", 11:"y"}` |
| `declaration_map` | `{12:8}` (usage of x → declaration of x) |
| `symbol_table` | `{"scope_map": {8:[0,1,2], 12:[0,1,2]}, "data_type": {8:"int", 11:"int"}, ...}` |

### Summary

These 7 (+1) data structures form the **foundation** for all codeview generation:

1. **all_tokens** - What tokens exist
2. **label** - What each token says
3. **method_map** - Which are methods
4. **method_calls** - Which methods are called
5. **start_line** - Where each token is located
6. **declaration** - Which tokens declare variables
7. **declaration_map** - How variables are used
8. **symbol_table** - Scope and type information

Every codeview (AST/CFG/DFG/SDFG) consumes these structures to build its respective graph representation.

---

## Language Nodes Classification

The `{language}_nodes.py` files define **language-specific node classifications** that categorize AST node types into meaningful groups. These classifications are used by **CFG and SDFG generators** to understand control flow and statement structure.

### File Breakdown

#### 1. **[java_nodes.py](src/comex/utils/java_nodes.py)**
**Language**: ✅ **Java-specific**

#### 2. **[cs_nodes.py](src/comex/utils/cs_nodes.py)**
**Language**: ✅ **C#-specific**

Both files have similar structure but define language-specific node types.

### Key Data Structure: `statement_types` Dictionary

This is the **main export** from these files. It categorizes AST node types into logical groups:

#### Java Example ([java_nodes.py:1-81](src/comex/utils/java_nodes.py#L1-L81)):

```python
statement_types = {
    "node_list_type": [...],           # All statement types
    "non_control_statement": [...],     # Simple statements
    "control_statement": [...],         # Control flow statements
    "loop_control_statement": [...],    # Loop statements
    "inner_node_type": [...],          # Inner statements (can be nested)
    "outer_node_type": [...],          # Outer container statements
    "statement_holders": [...],         # Blocks that contain statements
    "definition_types": [...],          # Class/method definitions
}
```

### Detailed Breakdown of Each Category

#### 1. **`node_list_type`** - All Statement Types
**Purpose**: Complete list of all node types that represent statements

**Java Example**:
```python
"node_list_type": [
    "declaration",
    "expression_statement",
    "if_statement",
    "while_statement",
    "for_statement",
    "return_statement",
    "method_declaration",
    "class_declaration",
    ...
]
```

**Used by**:
- CFG: To identify where to create nodes
- SDFG: To determine statement boundaries
- `get_nodes()` function: To recursively extract statements from AST

#### 2. **`non_control_statement`** - Simple Statements
**Purpose**: Statements that don't affect control flow (sequential execution)

**Java Example**:
```python
"non_control_statement": [
    "declaration",
    "expression_statement",
    "local_variable_declaration",
    "assert_statement",
    "field_declaration",
    "import_declaration"
]
```

**Example Code**:
```java
int x = 5;                    // local_variable_declaration
System.out.println(x);        // expression_statement
```

**Used by**:
- CFG: These nodes get simple sequential edges (A → B)
- SDFG: Processed as single statements in reaching definitions

#### 3. **`control_statement`** - Control Flow Statements
**Purpose**: Statements that change program flow (branching, looping, jumping)

**Java Example**:
```python
"control_statement": [
    "if_statement",
    "while_statement",
    "for_statement",
    "do_statement",
    "break_statement",
    "continue_statement",
    "return_statement",
    "switch_expression",
    "try_statement",
]
```

**Example Code**:
```java
if (x > 0) { ... }           // if_statement
while (x < 10) { ... }       // while_statement
return x;                     // return_statement
```

**Used by**:
- **CFG**: These create complex edge patterns:
  - `if_statement`: Creates branching edges (true/false paths)
  - `while_statement`: Creates loop-back edges
  - `return_statement`: Creates edges to method exit
  - `break_statement`: Creates edges that skip loop bodies

#### 4. **`loop_control_statement`** - Loop Constructs
**Purpose**: Subset of control statements that are loops

**Java Example**:
```python
"loop_control_statement": [
    "while_statement",
    "for_statement",
    "enhanced_for_statement",
]
```

**Used by**:
- CFG: To create loop-back edges
- SDFG: To handle iterative data flow

#### 5. **`inner_node_type`** - Inner/Nested Statements
**Purpose**: Statements that can appear inside other statements

**Java Example**:
```python
"inner_node_type": [
    "declaration",
    "expression_statement",
    "local_variable_declaration",
]
```

**Example**:
```java
for (int i = 0; i < 10; i++) {  // for_statement (outer)
    int x = i * 2;                 // local_variable_declaration (inner)
}
```

**Used by**:
- `get_nodes()`: To skip certain nodes when they're inside for-loop initializers

#### 6. **`outer_node_type`** - Container Statements
**Purpose**: Statements that contain other statements

**Java Example**:
```python
"outer_node_type": ["for_statement"]
```

**Used by**:
- `get_nodes()`: Special handling for for-loop initialization/update clauses

#### 7. **`statement_holders`** - Block Containers
**Purpose**: Node types that hold collections of statements

**Java Example**:
```python
"statement_holders": [
    "block",
    "switch_block_statement_group",
    "switch_block",
    "constructor_body",
    "class_body",
    "program"
]
```

**Example**:
```java
public void test() {           // method_declaration
    {                          // block (statement_holder)
        int x = 5;
        int y = 10;
    }
}
```

**Used by**:
- CFG: To traverse into blocks and extract statements
- AST: To understand nesting structure

#### 8. **`definition_types`** - Definitions
**Purpose**: Node types that define classes, methods, etc.

**Java Example**:
```python
"definition_types": [
    "method_declaration",
    "constructor_declaration",
    "class_declaration",
    "field_declaration",
    "interface_declaration"
]
```

**Used by**:
- CFG: Entry points for control flow graphs
- Method resolution and class hierarchy tracking

### C# Differences ([cs_nodes.py:1-76](src/comex/utils/cs_nodes.py#L1-L76))

C# has language-specific additions:

```python
"scope_only_blocks": [
    "checked_statement",      # C# checked block
    "fixed_statement",        # C# fixed (unsafe) block
    "unsafe_statement",       # C# unsafe block
    "using_statement",        # C# using statement
    "local_function_statement",  # C# local functions
]

"control_statements": [
    ...
    "lock_statement",         # C# lock (Java has synchronized)
    "foreach_statement",      # C# foreach (Java has enhanced_for)
]
```

### Helper Functions

Both files include utility functions used by CFG/SDFG generators:

#### Java Functions ([java_nodes.py:85-597](src/comex/utils/java_nodes.py#L85-L597)):

##### 1. **`get_child_of_type(node, type_list)`**
```python
def get_child_of_type(node, type_list):
    """Returns first child matching any type in type_list"""
    out = list(filter(lambda x : x.type in type_list, node.children))
    if len(out) > 0:
        return out[0]
    else:
        return None
```

**Used by**: Finding specific child nodes (e.g., condition in if-statement)

##### 2. **`get_nodes(root_node, node_list, graph_node_list, index, records)`**
**Purpose**: THE MAIN STATEMENT EXTRACTOR - Recursively extracts all statement-level nodes from the AST

**This is the most important function** - it's called by CFG generators.

**What it does**:
1. Traverses the AST recursively
2. Identifies statement nodes using `statement_types["node_list_type"]`
3. Extracts readable labels for each statement
4. Returns a list of statement nodes suitable for CFG construction

**Example Flow**:
```python
if root_node.type in statement_types["node_list_type"]:
    # Extract node information
    node_list[(root_node.start_point, root_node.end_point, root_node.type)] = root_node

    # Create human-readable label
    if root_node.type == "if_statement":
        condition = list(filter(lambda child: child.type == "parenthesized_expression",
                               root_node.children))
        label = "if" + condition[0].text.decode("UTF-8")
        type_label = "if"

    elif root_node.type == "for_statement":
        init = root_node.child_by_field_name("init").text.decode("UTF-8")
        condition = root_node.child_by_field_name("condition").text.decode("UTF-8")
        update = root_node.child_by_field_name("update").text.decode("UTF-8")
        label = "for(" + init + condition + ";" + update + ")"
        type_label = "for"

    # Add to output list
    graph_node_list.append((index[...], line_number, label, type_label))

# Recurse to children
for child in root_node.children:
    get_nodes(child, ...)
```

**Returns**:
```python
graph_node_list = [
    (5, 0, "public void test()", "method_declaration"),
    (10, 1, "int x = 5;", "expression_statement"),
    (15, 2, "if (x > 0)", "if"),
    (20, 3, "return x;", "return"),
]
```

##### 3. **`check_lambda(node)` / `check_anonymous_class(node)`**
**Purpose**: Detect lambda expressions and anonymous classes

**Used by**: `get_nodes()` to handle special label formatting

##### 4. **`get_signature(node)`**
**Purpose**: Extract method signature (parameter types)

```python
def get_signature(node):
    signature = []
    formal_parameters = node.child_by_field_name('parameters')
    formal_parameters = list(filter(lambda x: x.type == 'formal_parameter',
                                   formal_parameters.children))
    for formal_parameter in formal_parameters:
        for child in formal_parameter.children:
            if child.type != "identifier":
                signature.append(child.text.decode('utf-8'))
    return tuple(signature)
```

**Returns**: `("int", "String", "boolean")` for `void foo(int x, String s, boolean b)`

**Used by**: Method resolution and overloading

##### 5. **`get_class_name(node, index)`**
**Purpose**: Find the class that contains a method/constructor

**Used by**: Tracking method ownership for inter-procedural analysis

##### 6. **`abstract_method(node)`**
**Purpose**: Check if a method is abstract (has no body)

**Used by**: CFG generation (skip abstract methods)

### How These Files Are Used

#### In CFG Generation:

```python
# src/comex/codeviews/CFG/CFG_java.py (example)
from ...utils.java_nodes import statement_types, get_nodes

# Extract all statements
root_node, node_list, graph_node_list, records = get_nodes(
    root_node=parser.root_node,
    node_list={},
    graph_node_list=[],
    index=parser.index,
    records={}
)

# Build CFG edges based on statement types
for node in graph_node_list:
    if node.type in statement_types["control_statement"]:
        # Create branching edges
    elif node.type in statement_types["non_control_statement"]:
        # Create sequential edges
```

#### In SDFG Generation ([SDFG_java.py:11](src/comex/codeviews/SDFG/SDFG_java.py#L11)):

```python
from ...utils.java_nodes import statement_types

# Use node classifications for data flow analysis
if node.type in statement_types["control_statement"]:
    # Handle control flow impact on reaching definitions
```

### Summary: Language-Specific vs Language-Agnostic

| File | Language-Specific? | What It Defines |
|------|-------------------|----------------|
| [java_nodes.py](src/comex/utils/java_nodes.py) | ✅ **Yes - Java** | Java statement types, Java-specific helpers |
| [cs_nodes.py](src/comex/utils/cs_nodes.py) | ✅ **Yes - C#** | C# statement types, C#-specific helpers |

### Key Takeaways

1. **`statement_types`** dictionary categorizes AST nodes by purpose (control flow, loops, declarations)
2. **`get_nodes()`** function recursively extracts statement-level nodes from the AST with readable labels
3. **CFG generators** use these classifications to determine edge types
4. **SDFG generators** use these to identify data flow boundaries
5. Each language has its own file because syntax differs (e.g., Java `synchronized` vs C# `lock`)

**For C/C++ support, you'd create**:
- `c_nodes.py` with C-specific statement types
- `cpp_nodes.py` with C++-specific statement types (including classes, templates, etc.)

---

## Connection Between parser_driver and java_nodes

### Key Discovery: There is NO direct connection!

`parser_driver.py` **does NOT import or use** `java_nodes.py`. Instead, the connection happens **later in the pipeline** through the **CFG/SDFG generators**.

### The Actual Flow

```
User Code
    ↓
CombinedDriver (combined_driver.py)
    ↓
CFGDriver (CFG_driver.py)
    ↓
ParserDriver (parser_driver.py)  ← Creates parser, extracts tokens
    ↓
JavaParser (java_parser.py)      ← Language-specific token extraction
    ↓
CFGDriver receives parser ↓
    ↓
CFGGraph_java (CFG_java.py)      ← THIS is where java_nodes.py is used!
    ↓
Uses java_nodes.statement_types
Uses java_nodes.get_nodes()
```

### Step-by-Step Trace

#### Step 1: CFGDriver Creates ParserDriver

**File**: [CFG_driver.py:18](src/comex/codeviews/CFG/CFG_driver.py#L18)

```python
class CFGDriver:
    def __init__(self, src_language="java", src_code="", ...):
        # Step 1: Create ParserDriver (which creates JavaParser internally)
        self.parser = ParserDriver(src_language, src_code).parser
        self.root_node = self.parser.root_node
```

At this point:
- `ParserDriver` has created the AST using tree-sitter
- `JavaParser` has extracted all tokens into the 7 data structures
- `java_nodes.py` has **NOT been used yet**

#### Step 2: CFGDriver Routes to Language-Specific CFG

**File**: [CFG_driver.py:23-35](src/comex/codeviews/CFG/CFG_driver.py#L23-L35)

```python
self.CFG_map = {
    "java": CFGGraph_java,
    "cs": CFGGraph_csharp,
}

# Route to Java-specific CFG generator
self.CFG = self.CFG_map[self.src_language](
    self.src_language,
    self.src_code,
    self.properties,
    self.root_node,
    self.parser,  # ← Passes the parser object
)
```

#### Step 3: CFGGraph_java Imports java_nodes.py

**File**: [CFG_java.py:4](src/comex/codeviews/CFG/CFG_java.py#L4)

```python
from ...utils import java_nodes
```

This is the **first time** `java_nodes.py` enters the picture!

#### Step 4: CFGGraph_java Uses java_nodes

**File**: [CFG_java.py:8-36](src/comex/codeviews/CFG/CFG_java.py#L8-L36)

```python
class CFGGraph_java(CFGGraph):
    def __init__(self, src_language, src_code, properties, root_node, parser):
        super().__init__(src_language, src_code, properties, root_node, parser)

        # Import statement_types from java_nodes.py
        self.statement_types = java_nodes.statement_types  # ← HERE!

        # Access parser data (created by ParserDriver)
        self.index = parser.index
        self.symbol_table = parser.symbol_table
        self.declaration = parser.declaration

        # Generate CFG
        self.CFG_node_list, self.CFG_edge_list = self.CFG_java()
```

#### Step 5: CFGGraph_java Calls java_nodes.get_nodes()

**File**: [CFG_java.py:796](src/comex/codeviews/CFG/CFG_java.py#L796)

```python
def CFG_java(self):
    warning_counter = 0
    node_list = {}
    # node_list is a dictionary that maps from (node.start_point, node.end_point, node.type) to the node object of tree-sitter
    _, self.node_list, self.CFG_node_list, self.records = java_nodes.get_nodes(
        root_node=self.root_node,
        node_list=node_list,
        graph_node_list=self.CFG_node_list,
        index=self.index,
        records=self.records,
    )
    # self.CFG_node_indices = list(map(lambda x: self.index[x], node_list.keys()))
    # Initial for loop required for basic block creation and simple control flow within a block
    for node_key, node_value in node_list.items():
        current_node_type = node_key[2]
        if current_node_type in self.statement_types["non_control_statement"]:
            src_node = self.index[node_key]
            # Create sequential CFG edge
```

### The Complete Connection Flow

#### Visual Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    CombinedDriver                            │
│  (combined_driver.py)                                        │
│  User wants: AST, CFG, DFG                                   │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ Calls CFGDriver
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                     CFGDriver                                │
│  (CFG_driver.py)                                             │
│                                                              │
│  Line 18: self.parser = ParserDriver(...).parser             │
│           ↓                                                  │
│  ┌───────────────────────────────────────────────┐          │
│  │         ParserDriver (parser_driver.py)        │          │
│  │                                                │          │
│  │  • Routes to JavaParser                       │          │
│  │  • Calls JavaParser.create_all_tokens()       │          │
│  │  • Extracts 7 data structures                 │          │
│  │  • Returns: all_tokens, label, declaration,   │          │
│  │    declaration_map, symbol_table, etc.        │          │
│  │                                                │          │
│  │  ❌ Does NOT use java_nodes.py                │          │
│  └───────────────────────────────────────────────┘          │
│           ↓                                                  │
│  Line 29: self.CFG = CFGGraph_java(parser=self.parser)      │
│           ↓                                                  │
└───────────┼──────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                  CFGGraph_java                               │
│  (CFG_java.py)                                               │
│                                                              │
│  Line 4:  from ...utils import java_nodes  ← FIRST IMPORT!  │
│                                                              │
│  Line 12: self.statement_types = java_nodes.statement_types │
│           ↑                                                  │
│           Uses java_nodes.py classifications                 │
│                                                              │
│  Line 796: _, node_list, CFG_nodes, records =               │
│            java_nodes.get_nodes(                             │
│                root_node=self.root_node,   ← From parser    │
│                index=self.index,           ← From parser    │
│                ...                                           │
│            )                                                 │
│           ↑                                                  │
│           Calls java_nodes.get_nodes() to extract statements │
│                                                              │
│  Line 807: if node.type in self.statement_types[            │
│                "non_control_statement"]:                     │
│               # Create sequential CFG edge                   │
│           ↑                                                  │
│           Uses java_nodes classifications                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### The Two-Phase Process

#### **Phase 1: ParserDriver (Token Extraction)**
**File**: `parser_driver.py` + `java_parser.py`

**What happens**:
1. Creates tree-sitter AST
2. Assigns IDs to all nodes
3. Extracts tokens into 7 data structures

**Does NOT use**: `java_nodes.py`

**Output**: Parser object with:
- `all_tokens`
- `label`
- `declaration`
- `declaration_map`
- `symbol_table`
- `index`
- `root_node`

#### **Phase 2: CFGGraph_java (CFG Construction)**
**File**: `CFG_java.py`

**What happens**:
1. Receives parser object from Phase 1
2. **NOW imports** `java_nodes.py`
3. Uses `java_nodes.get_nodes()` to extract statement-level nodes
4. Uses `java_nodes.statement_types` to classify nodes
5. Builds CFG edges based on classifications

**Example Usage in CFG_java.py**:

```python
# Line 796: Extract all statements using java_nodes
_, self.node_list, self.CFG_node_list, self.records = java_nodes.get_nodes(
    root_node=self.root_node,  # From parser
    index=self.index,           # From parser
    ...
)

# Line 807: Use classifications to build edges
for node_key, node_value in node_list.items():
    current_node_type = node_key[2]

    if current_node_type in self.statement_types["non_control_statement"]:
        # Create sequential edge: A → B
        src_node = self.index[node_key]
        next_node = find_next_statement()
        self.CFG_edge_list.append((src_node, next_node, "next"))

    elif current_node_type == "if_statement":
        # Create branching edges: A → B (true), A → C (false)
        condition_node = self.index[node_key]
        true_branch = find_true_branch()
        false_branch = find_false_branch()
        self.CFG_edge_list.append((condition_node, true_branch, "true"))
        self.CFG_edge_list.append((condition_node, false_branch, "false"))
```

### Why This Separation?

#### ParserDriver (Generic)
- Works at the **token level** (identifiers, literals, operators)
- Same structure for all languages
- Outputs raw data structures

#### CFGGraph_java (Language-Specific)
- Works at the **statement level** (if, for, while)
- Different for each language
- Uses `java_nodes.py` to understand Java statement semantics

### Example: Java vs C# Difference

#### Java Code:
```java
synchronized (lock) {
    x = 5;
}
```

#### C# Code:
```csharp
lock (obj) {
    x = 5;
}
```

**ParserDriver doesn't care** - it just extracts tokens: `synchronized`, `lock`, `(`, `)`, `{`, `x`, `=`, `5`, `}`

**CFG generators DO care**:
- `CFG_java.py` uses `java_nodes.statement_types["control_statement"]` which includes `"synchronized_statement"`
- `CFG_csharp.py` uses `cs_nodes.statement_types["control_statement"]` which includes `"lock_statement"`

### Summary Table

| Component | Uses java_nodes.py? | Why? |
|-----------|-------------------|------|
| `parser_driver.py` | ❌ No | Generic - works with any language |
| `java_parser.py` | ❌ No | Extracts tokens, not statements |
| `CFG_driver.py` | ❌ No | Just routes to language-specific CFG |
| **`CFG_java.py`** | ✅ **YES** | Needs to understand Java statement structure |
| **`SDFG_java.py`** | ✅ **YES** | Needs to understand Java control flow |
| `src_parser.py` | ✅ YES | Helper that reformats code using statement types |

### Answer to Your Question

**Q**: How and where is `java_nodes.py` called in `parser_driver`?

**A**: **It's NOT!**

`parser_driver.py` creates the AST and extracts tokens. Only **later**, when `CFGGraph_java` needs to build the control flow graph, does it import and use `java_nodes.py` to:
1. Extract statement-level nodes with `get_nodes()`
2. Classify statements with `statement_types`
3. Build appropriate CFG edges

The connection is **indirect**: `parser_driver` → `parser object` → passed to `CFG_java` → uses `java_nodes.py`

---

## SDFG Explained

### What is SDFG?

#### Full Name
**SDFG = Statement-level Data Flow Graph**

#### Definition

SDFG is a **specialized version of DFG** that:
1. Operates at the **statement level** (not token/variable level)
2. Uses **Reaching Definitions Analysis (RDA)** algorithm
3. Combines aspects of both **CFG** and **DFG**

### Difference Between DFG and SDFG

#### Regular DFG (Token-level)
```java
int x = 5;
int y = x + 10;
System.out.println(y);
```

**Token-level DFG nodes**:
```
Node: x (declaration)
Node: x (usage)
Node: y (declaration)
Node: y (usage)
Edge: x_declaration → x_usage (data flow)
Edge: x_usage → y_declaration (data flow)
Edge: y_declaration → y_usage (data flow)
```

#### SDFG (Statement-level)
```java
int x = 5;              // Statement 1
int y = x + 10;         // Statement 2
System.out.println(y);  // Statement 3
```

**Statement-level SDFG nodes**:
```
Node: "int x = 5;"
Node: "int y = x + 10;"
Node: "System.out.println(y);"
Edge: Statement1 → Statement2 (x reaches Statement2)
Edge: Statement2 → Statement3 (y reaches Statement3)
```

### Key Insight from the Code

Looking at [SDFG.py:45-49](src/comex/codeviews/SDFG/SDFG.py#L45-L49):

```python
# SDFG FIRST creates CFG
self.CFG_Results = CFGDriver(
    self.src_language, self.src_code, "", self.properties["CFG"]
)
end = time.time()
self.CFG = self.CFG_Results.graph
```

**This reveals**: SDFG **depends on CFG** - it creates a CFG first, then adds data flow information on top!

### Is SDFG Required for Creating CFG?

# ❌ **NO! SDFG is NOT required for CFG**

#### The Dependency Goes the OTHER Way:

```
CFG ← SDFG depends on CFG
```

#### Independence of Codeviews:

```
User Request
    ↓
CombinedDriver
    ├─→ AST (independent)
    ├─→ CFG (independent)
    ├─→ DFG (independent)
    └─→ SDFG (depends on CFG!)
```

### How SDFG Works (Step-by-Step)

#### Step 1: Create CFG
```python
self.CFG_Results = CFGDriver(...)
self.CFG = self.CFG_Results.graph
```

This gives us control flow edges between statements.

#### Step 2: Run RDA (Reaching Definitions Analysis)
```python
self.graph, self.debug_graph, self.rda_table, self.rda_result = self.rda(
    self.properties["DFG"]
)
```

**RDA Algorithm** computes:
- Which variable definitions "reach" which statements
- Which variables are "live" at each program point

#### Step 3: Combine CFG + Data Flow
The result is a graph that has:
- **CFG edges**: Control flow (if true → statement A, if false → statement B)
- **DFG edges**: Data flow (variable x defined here → used there)

### Visual Example

#### Java Code:
```java
public void test() {
    int x = 5;          // Statement 1
    if (x > 0) {        // Statement 2
        int y = x + 10; // Statement 3
        x = y;          // Statement 4
    }
    return x;           // Statement 5
}
```

#### CFG Only:
```
[S1: int x = 5]
       ↓
[S2: if (x > 0)]
       ↓ (true)    ↓ (false)
[S3: int y = x+10]  [S5: return x]
       ↓
[S4: x = y]
       ↓
[S5: return x]
```

#### SDFG (CFG + Data Flow):
```
[S1: int x = 5]
       ↓ (CFG edge)
       ↓ (DFG: x reaches S2)
[S2: if (x > 0)]
       ↓ (true, CFG)    ↓ (false, CFG)
       ↓ (DFG: x reaches S3)  ↓ (DFG: x reaches S5)
[S3: int y = x+10]      [S5: return x]
       ↓ (CFG)
       ↓ (DFG: y reaches S4)
[S4: x = y]
       ↓ (CFG)
       ↓ (DFG: x reaches S5)
[S5: return x]
```

### Configuration from List_Of_Views.pdf

Looking at the table, SDFG is called **"Statement Level DFG"**:

| Codeview | AST | DFG (statements, rda) | CFG |
|----------|-----|----------------------|-----|
| **Statement Level DFG** | False | True, True | False |
| **Simple CFG + Statement Level DFG** | False | True, True | True |
| **Simple AST + Simple CFG + Statement Level DFG** | True | True, True | True |

The `statements=True, rda=True` flags mean:
- `statements=True`: Work at statement level (not token level)
- `rda=True`: Use Reaching Definitions Analysis algorithm

### Summary Table

| Feature | CFG | DFG | SDFG |
|---------|-----|-----|------|
| **Full Name** | Control Flow Graph | Data Flow Graph | Statement-level Data Flow Graph |
| **Granularity** | Statement-level | Token/variable-level | Statement-level |
| **Shows** | Control flow (if/loops) | Data dependencies | Both control + data flow |
| **Algorithm** | Graph traversal | Variable tracking | RDA (Reaching Definitions) |
| **Dependencies** | None (independent) | None (independent) | **Requires CFG first!** |
| **Node Type** | Statements | Variables/tokens | Statements |
| **Edge Types** | true/false/next | defined-by/used-by | Both CFG + DFG edges |

### Code Evidence

#### SDFG Depends on CFG ([SDFG.py:43-56](src/comex/codeviews/SDFG/SDFG.py#L43-L56)):
```python
# Line 45: Create CFG FIRST
self.CFG_Results = CFGDriver(
    self.src_language, self.src_code, "", self.properties["CFG"]
)
self.CFG = self.CFG_Results.graph

# Line 54: THEN create DFG on top of CFG
self.graph, self.debug_graph, self.rda_table, self.rda_result = self.rda(
    self.properties["DFG"]
)
```

#### CFG is Independent:
CFG can be created alone without any DFG/SDFG!

### Final Answer to Your Questions

#### Q1: What is SDFG?
**A**: Statement-level Data Flow Graph that combines CFG structure with data flow information using Reaching Definitions Analysis (RDA).

#### Q2: Is SDFG required for creating CFG?
**A**: **No!** CFG is independent and can be created alone. In fact, **SDFG requires CFG** (not the other way around). SDFG creates a CFG first, then adds data flow edges on top of it.

### When to Use Each

- **CFG only**: When you only care about control flow (e.g., finding unreachable code, analyzing loops)
- **DFG only**: When you only care about data dependencies at variable level (e.g., finding unused variables)
- **SDFG**: When you need both control flow AND data flow at statement level (e.g., compiler optimizations, program slicing, vulnerability analysis)

---

## End of Analysis

This document provides a comprehensive analysis of the Comex codebase architecture, focusing on the parsing pipeline, data structures, and codeview generation process.
