# Module Reference

Complete file-by-file documentation of all modules in Comex.

## Table of Contents

- [Project Structure](#project-structure)
- [Entry Points](#entry-points)
- [Core Modules](#core-modules)
- [Parsing Layer](#parsing-layer)
- [Codeview Generators](#codeview-generators)
- [Utilities](#utilities)
- [Tests](#tests)

## Project Structure

```
tree-sitter-codeviews/
├── src/comex/              # Main package
│   ├── __init__.py         # Language initialization
│   ├── __main__.py         # Module entry point
│   ├── cli.py              # Command-line interface
│   ├── tree_parser/        # Parsing layer
│   ├── codeviews/          # Codeview generators
│   └── utils/              # Utility functions
├── tests/                  # Test suite
├── sample/                 # Example files
├── docs/                   # Documentation
└── setup.py / setup.cfg    # Package configuration
```

## Entry Points

### `src/comex/__init__.py`

**Purpose:** Initialize tree-sitter language parsers for Java and C#.

**Key Functions:**

#### `get_language_map()`
Returns a dictionary mapping language names to tree-sitter Language objects.

**Return value:**
```python
{
    "java": JAVA_LANGUAGE,    # Tree-sitter Java parser
    "cs": C_SHARP_LANGUAGE    # Tree-sitter C# parser
}
```

**Process:**
1. Define grammar repositories with specific commits:
   ```python
   grammar_repos = [
       ("https://github.com/tree-sitter/tree-sitter-java", "09d650def6cdf7f479f4b78f595e9ef5b58ce31e"),
       ("https://github.com/tree-sitter/tree-sitter-c-sharp", "3ef3f7f99e16e528e6689eae44dff35150993307")
   ]
   ```

2. Clone grammars to `/tmp/comex/` if not present

3. Build shared library (`languages.so`) using `Language.build_library()`

4. Load languages and return map

**First-run behavior:**
- Clones tree-sitter grammars from GitHub
- Builds parsers (takes a few seconds)
- Caches in temporary directory
- Subsequent runs are instant

**Called by:** Imported at package level, executed when `comex` is imported

---

### `src/comex/__main__.py`

**Purpose:** Enable running Comex as a module (`python -m comex`).

**Content:**
```python
from .cli import app
app()
```

**Usage:**
```bash
python -m comex --lang java --code-file test.java --graphs ast
```

---

### `src/comex/cli.py`

**Purpose:** Command-line interface using Typer framework.

**Key Function:**

#### `main(...)`
Main CLI entry point with all command-line options.

**Parameters:**
- `lang`: Language (java/cs) - **Required**
- `code`: Inline source code - Optional
- `code_file`: Path to source file - Optional
- `graphs`: Comma-separated graph types - Default: "ast,dfg"
- `output`: Output format (dot/json/all) - Default: "dot"
- `blacklisted`: Comma-separated node types to exclude - Default: ""
- `collapsed`: Collapse duplicate nodes - Default: False
- `last_def`: Add last definition info - Default: False
- `last_use`: Add last use info - Default: False
- `throw_parse_error`: Throw error on parse failure - Default: False
- `debug`: Enable debug logging - Default: False

**Process:**
1. Configure logging based on `debug` flag
2. Build `codeviews` configuration dictionary
3. Read code from file or use inline code
4. Call `CombinedDriver` with configuration
5. Handle exceptions and exit with appropriate code

**Example:**
```bash
comex --lang "java" --code-file test.java --graphs "cfg,dfg" --output "all" --debug
```

---

## Core Modules

### `src/comex/codeviews/combined_graph/combined_driver.py`

**Purpose:** Main orchestrator for combining multiple codeviews.

**Class:** `CombinedDriver`

**Constructor:**
```python
CombinedDriver(
    src_language="java",
    src_code="",
    output_file=None,
    graph_format="dot",
    codeviews={}
)
```

**Attributes:**
- `src_language`: Language identifier ("java" or "cs")
- `src_code`: Source code string
- `codeviews`: Configuration dictionary
- `graph`: Combined NetworkX MultiDiGraph
- `results`: Dictionary of individual codeview drivers
- `json`: JSON representation (if output_file provided)

**Methods:**

#### `get_graph()`
Returns the combined NetworkX MultiDiGraph.

#### `check_validity()`
Validates codeview combination (currently returns True).

#### Combination Methods:
- `AST_simple()`: Generate AST only
- `CFG_simple()`: Generate CFG only
- `DFG_simple()`: Generate DFG only
- `combine_AST_DFG_simple()`: Merge AST + DFG
- `combine_CFG_DFG_simple()`: Merge CFG + DFG
- `combine_AST_CFG_simple()`: Merge AST + CFG
- `combine_AST_CFG_DFG_simple()`: Merge all three

#### `combine()`
Main combination logic that routes to appropriate method based on `codeviews` configuration.

**Process:**
1. Initialize requested codeview drivers (AST, CFG, DFG)
2. Extract individual graphs
3. Call `combine()` to merge
4. Export to file if `output_file` provided

**Usage:**
```python
driver = CombinedDriver(
    src_language="java",
    src_code=code,
    output_file="output.json",
    graph_format="all",
    codeviews={...}
)
graph = driver.get_graph()
```

---

## Parsing Layer

### `src/comex/tree_parser/parser_driver.py`

**Purpose:** Central parser routing and coordination.

**Class:** `ParserDriver`

**Constructor:**
```python
ParserDriver(src_language, src_code)
```

**Attributes:**
- `src_language`: Language identifier
- `src_code`: Preprocessed source code
- `parser`: Language-specific parser instance
- `root_node`: Root of parse tree
- `tree`: Full parse tree
- `all_tokens`: All identifiers and tokens
- `label`: Token labels
- `method_map`: Method declarations
- `method_calls`: Method invocations
- `start_line`: Starting line numbers
- `declaration`: Declaration information
- `declaration_map`: Declaration mappings
- `symbol_table`: Variable scope table

**Methods:**

#### `pre_process_src_code(src_language, src_code)`
Preprocesses source code:
1. Remove empty lines
2. Remove comments (language-specific)

#### `create_all_tokens()`
Delegates to language-specific parser to extract tokens and metadata.

**Parser Map:**
```python
parser_map = {
    "java": JavaParser,
    "cs": CSParser
}
```

**Used by:** All codeview drivers (AST, CFG, DFG)

---

### `src/comex/tree_parser/java_parser.py`

**Purpose:** Java-specific parsing logic.

**Class:** `JavaParser` (extends `CustomParser`)

**Key Methods:**

#### `parse()`
Parses Java code using tree-sitter, returns root node and tree.

#### `create_all_tokens(...)`
Traverses parse tree and extracts:
- Variable identifiers
- Method names
- Literals
- Expressions
- Symbol tables

#### Helper methods:
- `handle_variable_declaration()`: Process variable declarations
- `handle_method_declaration()`: Process method definitions
- `handle_expression()`: Process expressions and operators
- `build_symbol_table()`: Track variable scopes

**Java-specific handling:**
- Class declarations
- Interface declarations
- Generics
- Annotations
- Lambda expressions (limited)

---

### `src/comex/tree_parser/cs_parser.py`

**Purpose:** C#-specific parsing logic.

**Class:** `CSParser` (extends `CustomParser`)

**Similar to JavaParser but handles C#-specific constructs:**
- Properties
- Events
- `using` statements
- `namespace` declarations
- Attributes
- Extension methods

**Limitations:**
- Lambda functions not fully supported
- Compiler directives (#pragma) not supported
- Operator overloading limited

---

### `src/comex/tree_parser/custom_parser.py`

**Purpose:** Base parser class with common functionality.

**Class:** `CustomParser`

**Attributes:**
- `src_language`: Language identifier
- `src_code`: Source code
- `index`: Node index map
- `all_tokens`: Token list
- `label`: Label map
- `method_map`: Method definitions
- `method_calls`: Method calls
- `start_line`: Line numbers
- `declaration`: Declaration info
- `declaration_map`: Declaration mappings
- `symbol_table`: Symbol table

**Common methods inherited by language-specific parsers.**

---

## Codeview Generators

### AST Module

#### `src/comex/codeviews/AST/AST_driver.py`

**Class:** `ASTDriver`

**Purpose:** Driver for AST generation.

**Constructor:**
```python
ASTDriver(
    src_language="java",
    src_code="",
    output_file="AST_output.json",
    properties={}
)
```

**Properties:**
- `collapsed`: Merge duplicate variable nodes
- `minimized`: Enable blacklisting
- `blacklisted`: List of node types to exclude

**Process:**
1. Initialize `ParserDriver`
2. Create `ASTGraph` instance
3. Export to JSON and DOT/PNG

---

#### `src/comex/codeviews/AST/AST.py`

**Class:** `ASTGraph`

**Purpose:** Generate Abstract Syntax Tree from parse tree.

**Key Methods:**

##### `get_AST_nodes(root_node, AST, AST_index)`
Recursively traverse tree-sitter parse tree and build AST.

**Process:**
- Only include named nodes (ignore syntax tokens)
- Create node with attributes:
  - `node_type`: Tree-sitter node type
  - `label`: Variable name or code snippet
  - `shape`: "box"
  - `style`: "rounded, filled"
  - `fillcolor`: "#BFE6D3" (green)
- Add edges from parent to children

##### `collapse(graph)`
Merge duplicate variable nodes.

**Algorithm:**
1. Build name-to-index map for all variables
2. For each variable name, find all nodes
3. Choose minimum node ID as representative
4. Merge all incoming/outgoing edges to representative
5. Remove duplicate nodes

##### `minimize(root_node, blacklisted_nodes)`
Find nodes to remove based on blacklist.

##### `remove_blacklisted_nodes(graph)`
Remove blacklisted nodes and reconnect graph.

**Algorithm:**
1. Find all blacklisted node IDs
2. For each blacklisted node:
   - Connect predecessors to successors
   - Remove node

##### `to_networkx()`
Main method that generates NetworkX graph.

**Process:**
1. Build initial AST
2. Apply collapse if configured
3. Apply minimize if configured
4. Return NetworkX MultiDiGraph

---

### CFG Module

#### `src/comex/codeviews/CFG/CFG_driver.py`

**Class:** `CFGDriver`

**Purpose:** Driver for CFG generation.

**Constructor:**
```python
CFGDriver(
    src_language="java",
    src_code="",
    output_file="CFG_output.json",
    properties={}
)
```

**Language Routing:**
```python
CFG_map = {
    "java": CFGGraph_java,
    "cs": CFGGraph_csharp
}
```

**Attributes:**
- `graph`: CFG NetworkX graph
- `node_list`: List of CFG nodes

---

#### `src/comex/codeviews/CFG/CFG.py`

**Class:** `CFGGraph` (base class)

**Purpose:** Base CFG functionality.

**Methods:**

##### `to_networkx(CFG_node_list, CFG_edge_list)`
Convert CFG nodes and edges to NetworkX graph.

**Node format:**
```python
(node_id, line_number, label, type_label)
```

**Edge format:**
```python
(source_id, target_id, edge_type, additional_data)
```

**Edge types:**
- `sequential`: Normal flow
- `if_true` / `if_false`: Conditional branches
- `loop_entry` / `loop_back`: Loop flow
- `method_call`: Method invocation
- `return`: Return statement

**Node attributes:**
```python
{
    "label": "5_ if (x > 0)",  # Line number + statement
    "type_label": "if_statement"
}
```

**Edge attributes:**
```python
{
    "controlflow_type": "if_true",
    "edge_type": "CFG_edge",
    "label": "if_true",
    "color": "red"
}
```

---

#### `src/comex/codeviews/CFG/CFG_java.py`

**Class:** `CFGGraph_java` (extends `CFGGraph`)

**Purpose:** Java-specific CFG generation.

**Key Methods:**

##### `create_CFG()`
Main CFG construction method.

**Process:**
1. Find all method declarations
2. For each method:
   - Create START node
   - Process method body
   - Create END node
3. Handle statements recursively

##### Statement Handlers:
- `handle_if_statement()`: Creates true/false branches
- `handle_while_statement()`: Creates loop with back edge
- `handle_for_statement()`: Creates loop with initialization
- `handle_switch_statement()`: Creates multi-way branch
- `handle_try_statement()`: Creates try-catch-finally flow
- `handle_return_statement()`: Creates return edge to END
- `handle_break_statement()`: Creates edge to loop exit
- `handle_continue_statement()`: Creates edge to loop condition

##### `handle_method_call()`
Handles method invocations (creates method_call edge).

**Node numbering:**
Nodes are numbered by line number for easy identification.

---

#### `src/comex/codeviews/CFG/CFG_csharp.py`

**Class:** `CFGGraph_csharp` (extends `CFGGraph`)

**Purpose:** C#-specific CFG generation.

**Additional handlers for C#-specific constructs:**
- `using` statements
- `foreach` loops
- `switch` expressions
- `property` getters/setters
- `event` handlers

**Similar structure to Java CFG but with C#-specific logic.**

---

### DFG Module

#### `src/comex/codeviews/DFG/DFG_driver.py`

**Class:** `DFGDriver`

**Purpose:** Driver for DFG generation.

**Constructor:**
```python
DFGDriver(
    src_language="java",
    src_code="",
    output_file="DFG_output.json",
    properties={}
)
```

**Properties (nested under "DFG" key):**
- `collapsed`: Merge duplicate nodes
- `statements`: Use statement-level DFG (always True)
- `last_def`: Annotate with last definition
- `last_use`: Annotate with last use

**Implementation:**
Uses `DfgRda` (Statement-level DFG with RDA) when `statements: True`.

**Attributes:**
- `graph`: DFG NetworkX graph
- `rda_table`: Reaching definitions table
- `rda_result`: RDA computation result

---

#### `src/comex/codeviews/SDFG/SDFG.py`

**Class:** `DfgRda`

**Purpose:** Statement-level Data Flow Graph with Reaching Definitions Analysis.

**Key Methods:**

##### `compute_reaching_definitions()`
Implements RDA algorithm.

**Algorithm:**
1. Initialize IN and OUT sets for each statement
2. Iterate until fixed point:
   ```
   IN[s] = ∪ OUT[p] for all predecessors p
   OUT[s] = GEN[s] ∪ (IN[s] - KILL[s])
   ```
3. GEN[s]: Definitions generated by statement s
4. KILL[s]: Definitions killed by statement s

**RDA Table:**
```python
{
    statement_id: {
        'gen': set of definitions,
        'kill': set of definitions,
        'in': set of reaching definitions,
        'out': set of reaching definitions
    }
}
```

##### `create_DFG()`
Build DFG from RDA results.

**Process:**
1. For each variable use:
   - Find reaching definitions
   - Create edge from definition to use
2. Annotate edges with `last_def` if configured
3. Annotate edges with `last_use` if configured

**Edge types:**
- `definition`: Variable is defined
- `use`: Variable is used
- `computed_from`: Expression uses variable

**Node attributes:**
```python
{
    "label": "x",
    "node_type": "identifier",
    "line_number": 5
}
```

**Edge attributes:**
```python
{
    "dataflow_type": "definition",
    "edge_type": "DFG_edge",
    "label": "def",
    "color": "blue",
    "last_def": 3,  # Optional
    "last_use": 7   # Optional
}
```

---

### CST Module

#### `src/comex/codeviews/CST/CST_driver.py`

**Purpose:** Driver for Concrete Syntax Tree generation.

**Note:** CST is generated as an intermediate step by tree-sitter but not typically exported as final output. The parse tree from tree-sitter IS the CST.

---

## Utilities

### `src/comex/utils/preprocessor.py`

**Purpose:** Clean source code before parsing.

**Functions:**

#### `remove_empty_lines(source)`
Removes blank lines from source code.

**Returns:** Source code with empty lines removed.

**Note:** Currently keeps all lines (including empty) based on commented code.

#### `remove_comments(lang, source)`
Removes comments from source code (language-specific).

**Parameters:**
- `lang`: Language ("java", "cs", "python", etc.)
- `source`: Source code string

**Returns:** Source code without comments.

**Implementation:**

**For Java/C#:**
Uses regex to match and remove:
- Line comments: `// ...`
- Block comments: `/* ... */`

**Pattern:**
```python
pattern = re.compile(
    r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
    re.DOTALL | re.MULTILINE
)
```

Preserves string literals while removing comments.

**For Python:**
Uses tokenize module to remove:
- Line comments: `# ...`
- Docstrings: `"""..."""` or `'''...'''`

**Source:** Adapted from [Microsoft CodeBERT](https://github.com/microsoft/CodeBERT)

---

### `src/comex/utils/postprocessor.py`

**Purpose:** Export graphs to various formats.

**Functions:**

#### `networkx_to_json(graph)`
Convert NetworkX graph to JSON object (in-memory).

**Returns:** Dictionary in node-link format.

#### `write_networkx_to_json(graph, filename)`
Write NetworkX graph to JSON file.

**Format:** NetworkX node-link data format
```json
{
  "directed": true,
  "multigraph": true,
  "graph": {},
  "nodes": [{...}],
  "links": [{...}]
}
```

**Note:** Skips writing if `GITHUB_ACTIONS` environment variable is set.

#### `to_dot(graph)`
Convert NetworkX graph to PyDot graph (DOT format).

**Returns:** PyDot graph object.

#### `write_to_dot(og_graph, filename, output_png=False)`
Write graph to DOT file and optionally generate PNG.

**Parameters:**
- `og_graph`: NetworkX graph
- `filename`: Output DOT filename
- `output_png`: If True, generate PNG using GraphViz

**Process:**
1. Create deep copy of graph (to avoid modifying original)
2. Escape special characters in node labels
3. Write DOT file using NetworkX
4. If `output_png`, call GraphViz:
   ```bash
   dot -Tpng input.dot -o output.png
   ```

**Note:** Requires GraphViz `dot` command to be installed.

---

### `src/comex/utils/java_nodes.py`

**Purpose:** Java AST node type definitions.

**Content:**
- Comprehensive list of Java tree-sitter node types
- Node type categorizations
- Used for blacklisting and AST filtering

**Example node types:**
```python
JAVA_NODE_TYPES = [
    "program",
    "class_declaration",
    "method_declaration",
    "local_variable_declaration",
    "if_statement",
    "for_statement",
    # ... hundreds more
]
```

---

### `src/comex/utils/cs_nodes.py`

**Purpose:** C# AST node type definitions.

**Similar to `java_nodes.py` but for C#.**

**Example node types:**
```python
CS_NODE_TYPES = [
    "compilation_unit",
    "class_declaration",
    "method_declaration",
    "local_declaration_statement",
    "if_statement",
    # ... hundreds more
]
```

---

### `src/comex/utils/DFG_utils.py`

**Purpose:** Helper functions for DFG generation.

**Functions:**
- Variable tracking utilities
- Expression analysis helpers
- Data flow computation utilities

---

### `src/comex/utils/src_parser.py`

**Purpose:** Additional source parsing utilities.

**Functions:**
- Helper methods for token extraction
- Source code manipulation utilities

---

## Tests

### `tests/test_codeviews.py`

**Purpose:** Main test suite for codeview generation.

**Test Functions:**

#### `test_ast(extension, test_folder, test_name)`
Test AST generation for Java and C# files.

#### `test_cfg(extension, test_folder, test_name)`
Test CFG generation for Java and C# files.

#### `test_sdfg(extension, test_folder, test_name)`
Test SDFG generation for Java and C# files.

#### `test_combined(extension, test_folder, test_name)`
Test combined codeview generation.

**Test Process:**
1. Read test file (`test_name.java` or `test_name.cs`)
2. Generate codeview using appropriate driver
3. Save result as `test_name-answer.json`
4. Compare with `test_name-gold.json` using DeepDiff
5. Assert no differences

**Gold File Creation:**
If gold file doesn't exist, copy answer file as gold (for first run).

**Test Discovery:**
```python
def pytest_generate_tests(metafunc):
    # Dynamically discover test files in tests/data/
    # Generate test cases for each .java and .cs file
```

**Test Data Structure:**
```
tests/data/
├── AST/
│   ├── test1.java
│   ├── test1/
│   │   └── test1-gold.json
│   ├── test2.cs
│   └── test2/
│       └── test2-gold.json
├── CFG/
├── SDFG/
└── COMBINED/
```

**Running Tests:**
```bash
# All tests
pytest

# Specific test
pytest -k 'test_cfg[java-test1]'

# With verbose output
pytest -k 'test_cfg[java-test1]' -vv --no-cov
```

---

### Test Data (`tests/data/`)

**Structure:**
- `AST/`: AST test cases
- `CFG/`: CFG test cases
- `SDFG/`: SDFG test cases
- `COMBINED/`: Combined codeview test cases

**Each test case includes:**
- Source file (`.java` or `.cs`)
- Gold standard output (`test_name-gold.json`)
- Configuration file for combined tests (`test_name-config.json`)

---

### Analysis Scripts

#### `tests/analyze_*.py`

Various analysis scripts for research purposes:
- `analyze_clone_cfg.py`: CFG for clone detection
- `analyze_translation_dfg.py`: DFG for code translation
- `analyze_search_cfg.py`: CFG for code search
- etc.

**Purpose:** Research experiments and dataset generation.

---

## Configuration Files

### `setup.cfg`

**Purpose:** Package configuration for setuptools.

**Key sections:**
- `[metadata]`: Package name, version, description, license
- `[options]`: Dependencies, Python version, package discovery
- `[options.entry_points]`: CLI entry point (`comex=comex.cli:app`)
- `[options.extras_require]`: Development dependencies
- `[tool:pytest]`: Pytest configuration

**Dependencies:**
```
networkx==2.6.3
tree-sitter==0.20.1
deepdiff==5.8.1
pydot==1.4.1
typer==0.4.1
loguru==0.6.0
setuptools>=69.0 (for Python 3.12+)
```

---

### `setup.py`

**Purpose:** Minimal setup file that delegates to `setup.cfg`.

**Content:**
```python
from setuptools import setup
setup()
```

---

### `requirements-dev.txt`

**Purpose:** Development dependencies.

**Content:**
```
-e .[dev]
```

Installs package in editable mode with dev extras (pytest, pytest-cov, etc.).

---

## See Also

- [Architecture Overview](05-architecture.md) - High-level design
- [Extending Comex](07-extending-comex.md) - Add new features
- [Development Guide](08-development-guide.md) - Contributing
- [Python API](03-python-api.md) - Using the modules
