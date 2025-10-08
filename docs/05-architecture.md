# Architecture Overview

Comprehensive guide to Comex's internal architecture and design patterns.

## Table of Contents

- [High-Level Architecture](#high-level-architecture)
- [Component Overview](#component-overview)
- [Processing Pipeline](#processing-pipeline)
- [Data Flow](#data-flow)
- [Key Design Patterns](#key-design-patterns)
- [Extension Points](#extension-points)

## High-Level Architecture

Comex follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────┐
│                   CLI / Python API                   │  Entry Points
├─────────────────────────────────────────────────────┤
│                  Combined Driver                     │  Orchestration
├─────────────────────────────────────────────────────┤
│     AST Driver  │  CFG Driver  │  DFG Driver        │  Codeview Drivers
├─────────────────────────────────────────────────────┤
│   AST Generator │ CFG Generator│ DFG Generator      │  Codeview Logic
│                 │  (Java/C#)   │ (with RDA)         │
├─────────────────────────────────────────────────────┤
│              Parser Driver                           │  Parsing Layer
│         (Java Parser / C# Parser)                    │
├─────────────────────────────────────────────────────┤
│              Tree-sitter Library                     │  Core Parsing
├─────────────────────────────────────────────────────┤
│         Preprocessor │ Postprocessor                 │  Utilities
│    (Comment removal) │ (JSON/DOT export)            │
└─────────────────────────────────────────────────────┘
```

## Component Overview

### 1. Entry Points

#### CLI (`src/comex/cli.py`)

Command-line interface built with Typer.

**Responsibilities:**
- Parse command-line arguments
- Validate inputs
- Configure codeview options
- Invoke CombinedDriver
- Handle errors and logging

**Key functions:**
```python
@app.callback(invoke_without_command=True)
def main(lang, code, code_file, graphs, output, ...)
```

#### Python API

Direct import and usage of drivers.

**Typical usage:**
```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver
driver = CombinedDriver(...)
```

### 2. Initialization (`src/comex/__init__.py`)

Manages tree-sitter grammar setup.

**Responsibilities:**
- Clone tree-sitter grammars (first run only)
- Build language parsers
- Create language map (Java, C#)
- Cache in temporary directory

**Key function:**
```python
def get_language_map():
    # Returns: {"java": JAVA_LANGUAGE, "cs": C_SHARP_LANGUAGE}
```

**Process:**
1. Check if grammars exist in `/tmp/comex/`
2. If not, clone from GitHub (specific commits)
3. Build `.so` shared library
4. Load languages into tree-sitter

### 3. Orchestration Layer

#### CombinedDriver (`src/comex/codeviews/combined_graph/combined_driver.py`)

Main orchestrator that combines multiple codeviews.

**Responsibilities:**
- Initialize individual codeview drivers
- Combine graphs into single MultiDiGraph
- Export to JSON/DOT/PNG

**Key methods:**
```python
def __init__(src_language, src_code, output_file, graph_format, codeviews)
def get_graph()  # Returns combined NetworkX graph
def combine()    # Merges individual graphs
```

**Combination logic:**
```python
if AST and CFG and DFG:
    combine_AST_CFG_DFG_simple()
elif AST and DFG:
    combine_AST_DFG_simple()
elif CFG and DFG:
    combine_CFG_DFG_simple()
# ... etc
```

### 4. Codeview Drivers

Each codeview has a driver that manages its generation.

#### ASTDriver (`src/comex/codeviews/AST/AST_driver.py`)

**Responsibilities:**
- Initialize parser
- Create ASTGraph instance
- Export AST graph

**Flow:**
```python
parser = ParserDriver(language, code).parser
ast_graph = ASTGraph(language, code, properties, root_node, parser)
graph = ast_graph.graph
```

#### CFGDriver (`src/comex/codeviews/CFG/CFG_driver.py`)

**Responsibilities:**
- Initialize parser
- Route to language-specific CFG generator
- Export CFG graph

**Language routing:**
```python
CFG_map = {
    "java": CFGGraph_java,
    "cs": CFGGraph_csharp
}
cfg = CFG_map[language](...)
```

#### DFGDriver (`src/comex/codeviews/DFG/DFG_driver.py`)

**Responsibilities:**
- Initialize parser
- Use SDFG with RDA for statement-level DFG
- Export DFG graph

**Key feature:**
```python
if properties.get("statements", False):
    result = DfgRda(...)  # Statement-level DFG with RDA
```

### 5. Parsing Layer

#### ParserDriver (`src/comex/tree_parser/parser_driver.py`)

Central parser routing and coordination.

**Responsibilities:**
- Preprocess source code (remove comments, empty lines)
- Route to language-specific parser
- Extract tokens, labels, method maps

**Language routing:**
```python
parser_map = {
    "java": JavaParser,
    "cs": CSParser
}
parser = parser_map[language](language, code)
```

**Preprocessing:**
```python
def pre_process_src_code(language, code):
    code = preprocessor.remove_empty_lines(code)
    code = preprocessor.remove_comments(language, code)
    return code
```

#### JavaParser (`src/comex/tree_parser/java_parser.py`)

Java-specific parsing logic.

**Responsibilities:**
- Parse Java code with tree-sitter
- Extract Java-specific constructs
- Build symbol tables
- Map method declarations and calls

**Key data structures:**
```python
self.all_tokens      # All identifiers and tokens
self.label          # Token labels (variable names, etc.)
self.method_map     # Method declarations
self.method_calls   # Method invocations
self.symbol_table   # Variable scope information
```

#### CSParser (`src/comex/tree_parser/cs_parser.py`)

C#-specific parsing logic (similar structure to JavaParser).

### 6. Codeview Generators

#### ASTGraph (`src/comex/codeviews/AST/AST.py`)

Generates Abstract Syntax Tree.

**Key methods:**
```python
def get_AST_nodes(root_node, AST, AST_index)
    # Recursively builds AST from tree-sitter nodes

def collapse(graph)
    # Merges duplicate variable nodes

def minimize(root_node, blacklisted_nodes)
    # Removes blacklisted node types

def to_networkx()
    # Converts to NetworkX graph
```

**Process:**
1. Traverse tree-sitter CST
2. Extract named nodes (ignore syntax tokens)
3. Create AST nodes with attributes
4. Add parent-child edges
5. Apply transformations (collapse, minimize)

#### CFGGraph_java (`src/comex/codeviews/CFG/CFG_java.py`)

Generates Control Flow Graph for Java.

**Key methods:**
```python
def create_CFG()
    # Main CFG generation

def handle_if_statement(node)
    # Creates true/false branches

def handle_loop(node)
    # Creates loop entry/back edges

def handle_method_call(node)
    # Creates method call edges
```

**Process:**
1. Identify control flow statements (if, for, while, etc.)
2. Create CFG nodes for each statement
3. Add edges based on control flow:
   - Sequential for normal flow
   - Branching for conditionals
   - Loops for iteration

#### CFGGraph_csharp (`src/comex/codeviews/CFG/CFG_csharp.py`)

C#-specific CFG generation (handles C#-specific constructs like `using`, `foreach`, etc.).

#### DfgRda (`src/comex/codeviews/SDFG/SDFG.py`)

Statement-level Data Flow Graph with Reaching Definitions Analysis.

**Key components:**
```python
def compute_reaching_definitions()
    # RDA algorithm

def create_DFG()
    # Build DFG from RDA results

def track_variable_usage()
    # Track definitions and uses
```

**RDA Algorithm:**
1. Identify all variable definitions (assignments)
2. For each statement, compute reaching definitions (which defs reach this point)
3. Build DFG edges from definitions to uses
4. Annotate with last_def and last_use if configured

### 7. Utility Modules

#### Preprocessor (`src/comex/utils/preprocessor.py`)

Cleans source code before parsing.

**Functions:**
```python
def remove_empty_lines(source)
    # Removes blank lines

def remove_comments(language, source)
    # Removes comments (language-specific)
```

**Comment removal:**
- Java/C#: Regex-based removal of `//` and `/* */`
- Python: Token-based removal (if supported)

#### Postprocessor (`src/comex/utils/postprocessor.py`)

Exports graphs to various formats.

**Functions:**
```python
def write_networkx_to_json(graph, filename)
    # Exports to JSON using node-link format

def write_to_dot(graph, filename, output_png=False)
    # Exports to DOT format
    # Optionally generates PNG using GraphViz
```

**JSON format:**
```json
{
  "directed": true,
  "multigraph": true,
  "nodes": [...],
  "links": [...]
}
```

#### Node Definitions

**java_nodes.py / cs_nodes.py**

Define node type mappings for each language.

**Purpose:**
- Map tree-sitter node types to semantic categories
- Define node type hierarchies
- Used for blacklisting and filtering

## Processing Pipeline

### Full Pipeline Flow

```
1. Input (Code + Config)
        ↓
2. Preprocessing
   - Remove comments
   - Remove empty lines
        ↓
3. Tree-sitter Parsing
   - Generate CST
   - Extract tokens
        ↓
4. Parser Driver
   - Build symbol tables
   - Extract method maps
   - Create token lists
        ↓
5. Codeview Generation
   ├─→ AST Generator → AST Graph
   ├─→ CFG Generator → CFG Graph
   └─→ DFG Generator → DFG Graph
        ↓
6. Graph Combination
   - Merge nodes and edges
   - Preserve edge types
        ↓
7. Post-processing
   - Apply transformations
   - Export to JSON/DOT/PNG
        ↓
8. Output (Files + In-Memory Graph)
```

### Detailed Example: Generating CFG + DFG

**Step 1: Entry**
```python
CombinedDriver(
    src_language="java",
    src_code=code,
    output_file="output.json",
    graph_format="all",
    codeviews={
        "AST": {"exists": False},
        "CFG": {"exists": True},
        "DFG": {"exists": True, ...}
    }
)
```

**Step 2: Initialize Drivers**
```python
# CombinedDriver.__init__
if codeviews["CFG"]["exists"]:
    self.results["CFG"] = CFGDriver(...)
    self.CFG = self.results["CFG"].graph

if codeviews["DFG"]["exists"]:
    self.results["DFG"] = DFGDriver(...)
    self.DFG = self.results["DFG"].graph
```

**Step 3: Parsing (in each driver)**
```python
# CFGDriver.__init__
parser = ParserDriver(src_language, src_code).parser
# ParserDriver preprocesses code, parses with tree-sitter
```

**Step 4: CFG Generation**
```python
# CFGDriver.__init__
cfg = CFGGraph_java(language, code, properties, root_node, parser)
# CFGGraph_java.create_CFG() builds CFG
```

**Step 5: DFG Generation**
```python
# DFGDriver.__init__
result = DfgRda(src_language, src_code, properties)
# DfgRda computes RDA and builds DFG
```

**Step 6: Combination**
```python
# CombinedDriver.combine()
graph.add_nodes_from(CFG.nodes(data=True))
graph.add_nodes_from(DFG.nodes(data=True))
graph.add_edges_from(CFG.edges(data=True))
graph.add_edges_from(DFG.edges(data=True))
```

**Step 7: Export**
```python
# CombinedDriver.__init__
if output_file:
    postprocessor.write_networkx_to_json(graph, output_file)
    postprocessor.write_to_dot(graph, filename, output_png=True)
```

## Data Flow

### Input → Parser → Graph → Output

```
Source Code (String)
    ↓
[Preprocessor]
    ↓
Cleaned Code
    ↓
[Tree-sitter Parser]
    ↓
Concrete Syntax Tree (CST)
    ↓
[Parser Driver]
    ↓
Parsed Data:
- root_node
- all_tokens
- label
- method_map
- symbol_table
    ↓
[Codeview Generators]
    ↓
NetworkX MultiDiGraph
    ↓
[Postprocessor]
    ↓
Output Files:
- output.json
- output.dot
- output.png
```

### Data Structures

#### Tree-sitter Node
```python
{
    "type": "local_variable_declaration",
    "start_point": (5, 4),  # (line, column)
    "end_point": (5, 17),
    "children": [...]
}
```

#### NetworkX Node
```python
{
    "id": 123,
    "label": "int x = 5",
    "node_type": "local_variable_declaration",
    "shape": "box",
    "fillcolor": "#BFE6D3"
}
```

#### NetworkX Edge
```python
{
    "source": 123,
    "target": 456,
    "edge_type": "CFG_edge",
    "controlflow_type": "sequential",
    "color": "red"
}
```

## Key Design Patterns

### 1. Factory Pattern

Language-specific parsers and CFG generators use factory pattern:

```python
parser_map = {
    "java": JavaParser,
    "cs": CSParser
}
parser = parser_map[language](...)
```

### 2. Strategy Pattern

Different codeview combinations use strategy pattern:

```python
if AST and CFG and DFG:
    combine_AST_CFG_DFG_simple()
elif AST and DFG:
    combine_AST_DFG_simple()
# ... different strategies for different combinations
```

### 3. Decorator Pattern

Graph transformations (collapse, minimize) decorate base graph:

```python
graph = to_networkx()
if collapsed:
    collapse(graph)
if minimized:
    remove_blacklisted_nodes(graph)
```

### 4. Template Method Pattern

Codeview drivers follow template:
1. Initialize parser
2. Generate graph
3. Export if output_file provided

```python
class XXXDriver:
    def __init__(self, ...):
        self.parser = ParserDriver(...)
        self.graph = XXXGraph(...)
        if output_file:
            export(self.graph, output_file)
```

### 5. Composite Pattern

Combined graphs compose multiple codeview graphs:

```python
combined_graph = NetworkX.MultiDiGraph()
combined_graph.add_nodes_from(AST.nodes())
combined_graph.add_nodes_from(CFG.nodes())
combined_graph.add_nodes_from(DFG.nodes())
```

## Extension Points

### Adding a New Language

**Required implementations:**

1. **Parser** (`src/comex/tree_parser/<lang>_parser.py`)
   - Extend `CustomParser`
   - Implement language-specific token extraction

2. **Node Definitions** (`src/comex/utils/<lang>_nodes.py`)
   - Define node type mappings

3. **CFG Generator** (`src/comex/codeviews/CFG/CFG_<lang>.py`)
   - Extend `CFGGraph`
   - Implement control flow logic

4. **Register Language**
   - Add to `src/comex/__init__.py:grammar_repos`
   - Add to `parser_driver.py:parser_map`
   - Add to `CFGDriver:CFG_map`

### Adding a New Codeview Type

**Required implementations:**

1. **Codeview Class** (`src/comex/codeviews/<TYPE>/<TYPE>.py`)
   - Implement graph generation logic

2. **Driver** (`src/comex/codeviews/<TYPE>/<TYPE>_driver.py`)
   - Initialize parser
   - Create codeview instance
   - Export graph

3. **Integration**
   - Add to `CombinedDriver` combination logic

### Adding New Transformations

Implement in codeview class:

```python
def custom_transformation(self, graph):
    # Custom graph transformation logic
    return graph
```

Apply in `to_networkx()` or after graph creation.

## Performance Considerations

### Parsing

- **Tree-sitter** is incremental and fast
- **First run** downloads grammars (one-time cost)
- **Subsequent runs** are instant

### Graph Construction

- **AST**: O(n) where n = number of AST nodes
- **CFG**: O(n) where n = number of statements
- **DFG**: O(n*m) where n = statements, m = variables (RDA)

### Memory Usage

- **NetworkX MultiDiGraph** is memory-efficient for most code files
- **Large files** (>1000 lines) may generate large graphs
- Use `collapsed` mode to reduce graph size

### Optimization Tips

1. **Disable unused codeviews** (set `exists: False`)
2. **Use `output_file=None`** for in-memory only
3. **Blacklist unnecessary nodes** to reduce AST size
4. **Process files in parallel** for batch operations

## See Also

- [Module Reference](06-module-reference.md) - Detailed file documentation
- [Extending Comex](07-extending-comex.md) - Add new languages
- [Development Guide](08-development-guide.md) - Contributing
- [Python API](03-python-api.md) - Using the API
