# API Reference

Complete API documentation for all classes and functions.

## Core Classes

### CombinedDriver

Main class for generating and combining multiple codeviews.

**Location:** `src/comex/codeviews/combined_graph/combined_driver.py`

#### Constructor

```python
CombinedDriver(
    src_language: str,
    src_code: str,
    output_file: str = None,
    graph_format: str = "dot",
    codeviews: dict = {}
)
```

**Parameters:**
- `src_language` (str): Language identifier ("java" or "cs")
- `src_code` (str): Source code to analyze
- `output_file` (str, optional): Output file path. If None, no files are written
- `graph_format` (str): Output format - "dot", "json", or "all"
- `codeviews` (dict): Configuration for each codeview

**Attributes:**
- `src_language` (str): Language identifier
- `src_code` (str): Source code
- `codeviews` (dict): Codeview configuration
- `graph` (networkx.MultiDiGraph): Combined graph
- `results` (dict): Individual codeview driver results
- `json` (dict): JSON representation (if output_file provided)

**Methods:**

##### get_graph()

Returns the combined NetworkX MultiDiGraph.

**Returns:** `networkx.MultiDiGraph`

**Example:**
```python
driver = CombinedDriver(...)
graph = driver.get_graph()
```

##### check_validity()

Validates codeview combination (currently always returns True).

**Returns:** `bool`

---

### ASTDriver

Driver for AST generation.

**Location:** `src/comex/codeviews/AST/AST_driver.py`

#### Constructor

```python
ASTDriver(
    src_language: str = "java",
    src_code: str = "",
    output_file: str = "AST_output.json",
    properties: dict = {}
)
```

**Parameters:**
- `src_language` (str): Language identifier
- `src_code` (str): Source code
- `output_file` (str): Output path
- `properties` (dict): AST configuration
  - `collapsed` (bool): Merge duplicate nodes
  - `minimized` (bool): Enable blacklisting
  - `blacklisted` (list): Node types to exclude

**Attributes:**
- `graph` (networkx.MultiDiGraph): AST graph
- `json` (dict): JSON representation
- `parser`: Parser instance
- `AST`: ASTGraph instance

---

### CFGDriver

Driver for CFG generation.

**Location:** `src/comex/codeviews/CFG/CFG_driver.py`

#### Constructor

```python
CFGDriver(
    src_language: str = "java",
    src_code: str = "",
    output_file: str = "CFG_output.json",
    properties: dict = {}
)
```

**Parameters:**
- `src_language` (str): Language identifier
- `src_code` (str): Source code
- `output_file` (str): Output path
- `properties` (dict): CFG configuration (currently unused)

**Attributes:**
- `graph` (networkx.MultiDiGraph): CFG graph
- `json` (dict): JSON representation
- `node_list` (list): CFG nodes
- `parser`: Parser instance
- `CFG`: CFGGraph instance (language-specific)

---

### DFGDriver

Driver for DFG generation.

**Location:** `src/comex/codeviews/DFG/DFG_driver.py`

#### Constructor

```python
DFGDriver(
    src_language: str = "java",
    src_code: str = "",
    output_file: str = "DFG_output.json",
    properties: dict = {}
)
```

**Parameters:**
- `src_language` (str): Language identifier
- `src_code` (str): Source code
- `output_file` (str): Output path
- `properties` (dict): DFG configuration
  - Must contain "DFG" key with nested config:
    - `collapsed` (bool): Merge duplicate nodes
    - `statements` (bool): Use statement-level DFG
    - `last_def` (bool): Add last definition annotations
    - `last_use` (bool): Add last use annotations

**Attributes:**
- `graph` (networkx.MultiDiGraph): DFG graph
- `json` (dict): JSON representation
- `rda_table` (dict): Reaching definitions table
- `rda_result`: RDA computation result
- `parser`: Parser instance

---

## Parser Classes

### ParserDriver

Central parser coordination.

**Location:** `src/comex/tree_parser/parser_driver.py`

#### Constructor

```python
ParserDriver(src_language: str, src_code: str)
```

**Attributes:**
- `src_language` (str): Language identifier
- `src_code` (str): Preprocessed code
- `parser`: Language-specific parser
- `root_node`: Parse tree root
- `tree`: Full parse tree
- `all_tokens` (dict): All identifiers and tokens
- `label` (dict): Token labels
- `method_map` (dict): Method declarations
- `method_calls` (dict): Method invocations
- `start_line` (dict): Starting line numbers
- `declaration` (dict): Declaration information
- `declaration_map` (dict): Declaration mappings
- `symbol_table` (dict): Variable scope table

**Methods:**

##### pre_process_src_code(src_language, src_code)

Preprocesses source code (removes comments, empty lines).

**Parameters:**
- `src_language` (str): Language
- `src_code` (str): Raw source

**Returns:** `str` - Preprocessed code

##### create_all_tokens()

Extracts tokens from parse tree (delegates to language parser).

**Returns:** Tuple of (all_tokens, label, method_map, method_calls, start_line, declaration, declaration_map, symbol_table)

---

## Utility Functions

### Preprocessor

**Location:** `src/comex/utils/preprocessor.py`

#### remove_empty_lines(source)

Removes blank lines from source code.

**Parameters:**
- `source` (str): Source code

**Returns:** `str` - Code without empty lines

#### remove_comments(lang, source)

Removes comments from source code.

**Parameters:**
- `lang` (str): Language ("java", "cs", "python")
- `source` (str): Source code

**Returns:** `str` - Code without comments

---

### Postprocessor

**Location:** `src/comex/utils/postprocessor.py`

#### networkx_to_json(graph)

Converts NetworkX graph to JSON object.

**Parameters:**
- `graph` (networkx.Graph): Input graph

**Returns:** `dict` - Node-link JSON representation

#### write_networkx_to_json(graph, filename)

Writes NetworkX graph to JSON file.

**Parameters:**
- `graph` (networkx.Graph): Input graph
- `filename` (str): Output path

**Returns:** `dict` - JSON representation

**Note:** Skips writing if `GITHUB_ACTIONS` env var is set.

#### to_dot(graph)

Converts NetworkX graph to PyDot graph.

**Parameters:**
- `graph` (networkx.Graph): Input graph

**Returns:** `pydot.Dot` - DOT graph object

#### write_to_dot(og_graph, filename, output_png=False)

Writes graph to DOT file and optionally PNG.

**Parameters:**
- `og_graph` (networkx.Graph): Input graph
- `filename` (str): Output DOT path
- `output_png` (bool): Generate PNG if True

**Returns:** None

**Requires:** GraphViz `dot` command for PNG generation

---

## Graph Formats

### NetworkX MultiDiGraph

All graphs are `networkx.MultiDiGraph` objects (directed multigraph).

**Key features:**
- Directed edges
- Multiple edges allowed between nodes
- Node and edge attributes

### Node Attributes

Common attributes across codeviews:

```python
{
    'id': int,           # Unique identifier
    'label': str,        # Display label
    'node_type': str,    # Type identifier
    'shape': str,        # Visualization shape
    'style': str,        # Visualization style
    'fillcolor': str,    # Node color
    'color': str,        # Border color
    'line_number': int   # Source line (if applicable)
}
```

**AST-specific:**
```python
{
    'node_type': 'local_variable_declaration',
    'label': 'int x = 5',
    'shape': 'box',
    'style': 'rounded, filled',
    'fillcolor': '#BFE6D3',  # Green
    'color': 'white'
}
```

**CFG-specific:**
```python
{
    'label': '5_ if (x > 0)',
    'type_label': 'if_statement'
}
```

**DFG-specific:**
```python
{
    'label': 'x',
    'node_type': 'identifier',
    'line_number': 5
}
```

### Edge Attributes

Common attributes:

```python
{
    'edge_type': str,     # Type: AST_edge, CFG_edge, DFG_edge
    'label': str,         # Display label
    'color': str          # Edge color
}
```

**AST edges:**
```python
{
    'edge_type': 'AST_edge'
}
```

**CFG edges:**
```python
{
    'controlflow_type': 'if_true',  # or if_false, sequential, etc.
    'edge_type': 'CFG_edge',
    'label': 'if_true',
    'color': 'red'
}
```

**DFG edges:**
```python
{
    'dataflow_type': 'definition',  # or use, computed_from
    'edge_type': 'DFG_edge',
    'label': 'def',
    'color': 'blue',
    'last_def': int,     # Optional: line of last definition
    'last_use': int      # Optional: line of last use
}
```

### JSON Format

NetworkX node-link format:

```json
{
  "directed": true,
  "multigraph": true,
  "graph": {},
  "nodes": [
    {
      "id": 123,
      "label": "x",
      "node_type": "identifier"
    }
  ],
  "links": [
    {
      "source": 123,
      "target": 456,
      "edge_type": "DFG_edge",
      "dataflow_type": "definition"
    }
  ]
}
```

**Fields:**
- `directed` (bool): Always true
- `multigraph` (bool): Always true
- `graph` (dict): Graph-level attributes (usually empty)
- `nodes` (list): Array of node objects
- `links` (list): Array of edge objects

**Node object:**
- `id`: Unique identifier
- Other attributes vary by codeview

**Edge object:**
- `source`: Source node ID
- `target`: Target node ID
- `key`: Edge key (for multigraph)
- Other attributes vary by codeview

---

## Constants

### Language Map

**Function:** `get_language_map()`

**Returns:**
```python
{
    "java": Language,    # Tree-sitter Java
    "cs": Language       # Tree-sitter C#
}
```

### Node Types

#### Java Nodes

**File:** `src/comex/utils/java_nodes.py`

**Content:** List of all Java tree-sitter node types

**Usage:** Reference for blacklisting

#### C# Nodes

**File:** `src/comex/utils/cs_nodes.py`

**Content:** List of all C# tree-sitter node types

**Usage:** Reference for blacklisting

---

## Environment Variables

### GITHUB_ACTIONS

When set, Comex skips writing output files (for CI/CD).

**Example:**
```bash
export GITHUB_ACTIONS=true
comex --lang "java" --code-file test.java --graphs "ast"
# No files written, graph generated in memory only
```

---

## Exceptions

Comex raises standard Python exceptions:

### FileNotFoundError

When code file doesn't exist.

```python
try:
    driver = CombinedDriver(...)
except FileNotFoundError as e:
    print(f"File not found: {e}")
```

### KeyError

When unsupported language specified.

```python
try:
    driver = CombinedDriver(src_language="ruby", ...)
except KeyError as e:
    print(f"Language not supported: {e}")
```

### Exception

Generic exceptions for various errors (parsing, graph construction, etc.).

```python
try:
    driver = CombinedDriver(...)
except Exception as e:
    print(f"Error: {e}")
```

---

## Type Hints

Comex doesn't currently use type hints extensively, but expected types:

```python
from typing import Dict, List, Optional, Tuple
import networkx as nx

def example_types():
    src_language: str = "java"
    src_code: str = "public class Test {}"
    output_file: Optional[str] = "output.json"
    graph_format: str = "all"
    codeviews: Dict[str, Dict] = {...}
    graph: nx.MultiDiGraph
    json_output: Dict
    nodes: List[Tuple[int, Dict]]
    edges: List[Tuple[int, int, Dict]]
```

---

## Examples

### Basic API Usage

```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver

# Generate graph
driver = CombinedDriver(
    src_language="java",
    src_code="public class Test { int x = 5; }",
    output_file="output.json",
    graph_format="all",
    codeviews={
        "AST": {"exists": True, "collapsed": False,
                "minimized": False, "blacklisted": []},
        "CFG": {"exists": False},
        "DFG": {"exists": False}
    }
)

# Access graph
graph = driver.get_graph()
print(f"Nodes: {graph.number_of_nodes()}")
print(f"Edges: {graph.number_of_edges()}")
```

### Graph Manipulation

```python
# Get nodes
for node_id, attributes in graph.nodes(data=True):
    print(f"Node {node_id}: {attributes}")

# Get edges
for src, dst, key, attributes in graph.edges(data=True, keys=True):
    print(f"{src} -> {dst}: {attributes}")

# Filter nodes by type
ast_nodes = [n for n, d in graph.nodes(data=True)
             if d.get('edge_type') == 'AST_edge']

# Add custom attribute
for node in graph.nodes():
    graph.nodes[node]['custom'] = "value"
```

### Export Custom Format

```python
import json

# Custom serialization
custom_format = {
    "nodes": [
        {"id": n, **attrs}
        for n, attrs in graph.nodes(data=True)
    ],
    "edges": [
        {"from": s, "to": t, **attrs}
        for s, t, attrs in graph.edges(data=True)
    ]
}

with open("custom.json", "w") as f:
    json.dump(custom_format, f, indent=2)
```

---

## See Also

- [Python API Guide](03-python-api.md) - Usage patterns
- [Architecture](05-architecture.md) - Internal design
- [Module Reference](06-module-reference.md) - File documentation
- [Examples](12-examples.md) - Real-world usage
