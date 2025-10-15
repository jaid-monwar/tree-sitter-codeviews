# Python API Guide

Use Comex as a Python package for programmatic graph generation and integration into your applications.

## Table of Contents

- [Basic Usage](#basic-usage)
- [CombinedDriver API](#combineddriver-api)
- [Individual Codeview Drivers](#individual-codeview-drivers)
- [Configuration Options](#configuration-options)
- [Working with Generated Graphs](#working-with-generated-graphs)
- [Advanced Usage](#advanced-usage)
- [Integration Examples](#integration-examples)

## Basic Usage

### Simple Example

```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver

# Your Java source code
code = """
public class Example {
    public static void main(String[] args) {
        int x = 5;
        int y = 10;
        int sum = x + y;
    }
}
"""

# Generate combined AST + CFG + DFG
codeviews = {
    "AST": {"exists": True, "collapsed": False, "minimized": False, "blacklisted": []},
    "CFG": {"exists": True},
    "DFG": {"exists": True, "collapsed": False, "minimized": False,
            "statements": True, "last_def": False, "last_use": False}
}

driver = CombinedDriver(
    src_language="java",
    src_code=code,
    output_file="output.json",
    graph_format="all",  # Generates JSON and DOT/PNG
    codeviews=codeviews
)

# Access the NetworkX graph
graph = driver.get_graph()
print(f"Graph has {len(graph.nodes())} nodes and {len(graph.edges())} edges")
```

### Reading from File

```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver

# Read source code from file
with open("MyClass.java", "r") as f:
    code = f.read()

codeviews = {
    "AST": {"exists": True, "collapsed": False, "minimized": False, "blacklisted": []},
    "CFG": {"exists": False},
    "DFG": {"exists": False}
}

driver = CombinedDriver(
    src_language="java",
    src_code=code,
    output_file="ast_output.json",
    graph_format="json",
    codeviews=codeviews
)
```

## CombinedDriver API

The `CombinedDriver` class is the main entry point for generating codeviews.

### Constructor Parameters

```python
CombinedDriver(
    src_language: str,
    src_code: str,
    output_file: str = None,
    graph_format: str = "dot",
    codeviews: dict = {}
)
```

#### `src_language` (required)

The programming language of the source code.

**Type:** `str`

**Values:** `"java"` or `"cs"`

**Example:**
```python
driver = CombinedDriver(src_language="java", ...)
```

#### `src_code` (required)

The source code to analyze.

**Type:** `str`

**Example:**
```python
code = """
public class Test {
    public void method() {
        int x = 5;
    }
}
"""
driver = CombinedDriver(src_code=code, ...)
```

#### `output_file` (optional)

Path where the output files will be saved. If `None`, files are not written to disk.

**Type:** `str` or `None`

**Default:** `None`

**Behavior:**
- If provided: Writes files based on `graph_format`
- If `None`: Graph is generated in memory only (accessible via `get_graph()`)

**Example:**
```python
# Write to files
driver = CombinedDriver(..., output_file="result.json")
# Creates: result.json, result.dot, result.png (depending on graph_format)

# In-memory only
driver = CombinedDriver(..., output_file=None)
# No files written, use driver.get_graph() to access
```

#### `graph_format` (optional)

Output format(s) to generate.

**Type:** `str`

**Values:**
- `"dot"` - DOT file and PNG image (default)
- `"json"` - JSON file only
- `"all"` - Both JSON and DOT/PNG

**Default:** `"dot"`

**Example:**
```python
driver = CombinedDriver(..., graph_format="all")
```

#### `codeviews` (required)

Configuration dictionary specifying which codeviews to generate and their options.

**Type:** `dict`

**Structure:**
```python
codeviews = {
    "AST": {
        "exists": bool,           # Whether to generate AST
        "collapsed": bool,        # Collapse duplicate nodes
        "minimized": bool,        # Enable blacklisting
        "blacklisted": list       # Node types to exclude
    },
    "CFG": {
        "exists": bool            # Whether to generate CFG
    },
    "DFG": {
        "exists": bool,           # Whether to generate DFG
        "collapsed": bool,        # Collapse duplicate nodes
        "minimized": bool,        # Reserved for future use
        "statements": bool,       # Use statement-level DFG (always True)
        "last_def": bool,         # Add last definition info
        "last_use": bool          # Add last use info
    }
}
```

**Example:**
```python
# Generate only CFG
codeviews = {
    "AST": {"exists": False},
    "CFG": {"exists": True},
    "DFG": {"exists": False}
}

# Generate AST + DFG with custom options
codeviews = {
    "AST": {
        "exists": True,
        "collapsed": True,
        "minimized": True,
        "blacklisted": ["import_declaration", "package_declaration"]
    },
    "CFG": {"exists": False},
    "DFG": {
        "exists": True,
        "collapsed": False,
        "minimized": False,
        "statements": True,
        "last_def": True,
        "last_use": True
    }
}
```

### Methods

#### `get_graph()`

Returns the generated NetworkX MultiDiGraph.

**Returns:** `networkx.MultiDiGraph`

**Example:**
```python
driver = CombinedDriver(...)
graph = driver.get_graph()

# Now use NetworkX methods
print(f"Nodes: {graph.number_of_nodes()}")
print(f"Edges: {graph.number_of_edges()}")

# Iterate over nodes
for node_id, attributes in graph.nodes(data=True):
    print(f"Node {node_id}: {attributes}")

# Iterate over edges
for source, target, key, attributes in graph.edges(data=True, keys=True):
    print(f"Edge {source} -> {target}: {attributes}")
```

### Attributes

After initialization, the driver provides these attributes:

```python
driver.graph        # The NetworkX MultiDiGraph
driver.results      # Dictionary of individual codeview results
driver.json         # JSON representation (if output_file was provided)
```

**Example:**
```python
driver = CombinedDriver(...)

# Access individual codeview graphs
if "AST" in driver.results:
    ast_graph = driver.results["AST"].graph

if "CFG" in driver.results:
    cfg_graph = driver.results["CFG"].graph

if "DFG" in driver.results:
    dfg_graph = driver.results["DFG"].graph
```

## Individual Codeview Drivers

You can use individual drivers for specific codeviews.

### ASTDriver

Generate only Abstract Syntax Tree.

```python
from comex.codeviews.AST.AST_driver import ASTDriver

code = "public class Test { int x = 5; }"

driver = ASTDriver(
    src_language="java",
    src_code=code,
    output_file="ast.json",
    properties={
        "collapsed": False,
        "minimized": True,
        "blacklisted": ["import_declaration"]
    }
)

graph = driver.graph
json_output = driver.json
```

**Properties:**
- `collapsed`: Collapse duplicate nodes
- `minimized`: Enable blacklisting
- `blacklisted`: List of node types to exclude

### CFGDriver

Generate only Control Flow Graph.

```python
from comex.codeviews.CFG.CFG_driver import CFGDriver

code = """
public class Test {
    public void method(int x) {
        if (x > 0) {
            x = x + 1;
        } else {
            x = x - 1;
        }
    }
}
"""

driver = CFGDriver(
    src_language="java",
    src_code=code,
    output_file="cfg.json",
    properties={}
)

graph = driver.graph
node_list = driver.node_list  # List of CFG nodes
```

### DFGDriver

Generate only Data Flow Graph.

```python
from comex.codeviews.DFG.DFG_driver import DFGDriver

code = """
public class Test {
    public void method() {
        int x = 5;
        int y = x + 3;
        int z = y * 2;
    }
}
"""

driver = DFGDriver(
    src_language="java",
    src_code=code,
    output_file="dfg.json",
    properties={
        "DFG": {
            "collapsed": False,
            "statements": True,
            "last_def": True,
            "last_use": True
        }
    }
)

graph = driver.graph
rda_table = driver.rda_table      # Reaching definitions table
rda_result = driver.rda_result    # RDA analysis result
```

## Configuration Options

### AST Configuration

```python
ast_config = {
    "exists": True,
    "collapsed": False,        # Merge duplicate variable nodes
    "minimized": True,         # Enable node blacklisting
    "blacklisted": [           # Node types to remove
        "import_declaration",
        "package_declaration",
        "comment",
        "line_comment"
    ]
}
```

**Common blacklist patterns:**

```python
# Remove boilerplate
blacklisted = ["import_declaration", "package_declaration"]

# Remove all comments
blacklisted = ["comment", "line_comment", "block_comment"]

# Keep only method bodies
blacklisted = ["class_declaration", "interface_declaration"]
```

### CFG Configuration

```python
cfg_config = {
    "exists": True
}
```

CFG has no additional configuration options.

### DFG Configuration

```python
dfg_config = {
    "exists": True,
    "collapsed": False,        # Merge duplicate variable nodes
    "minimized": False,        # Reserved for future use
    "statements": True,        # Always True (statement-level DFG)
    "last_def": True,          # Add last definition annotations
    "last_use": True           # Add last use annotations
}
```

## Working with Generated Graphs

### NetworkX Graph Structure

Comex generates `networkx.MultiDiGraph` objects (directed multigraph allowing multiple edges between nodes).

#### Node Attributes

Nodes have different attributes depending on the codeview:

**AST Nodes:**
```python
{
    'node_type': 'local_variable_declaration',
    'label': 'int x = 5',
    'shape': 'box',
    'style': 'rounded, filled',
    'fillcolor': '#BFE6D3',
    'color': 'white'
}
```

**CFG Nodes:**
```python
{
    'label': '5_ if (x > 0)',
    'type_label': 'if_statement'
}
```

**DFG Nodes:**
```python
{
    'label': 'x',
    'node_type': 'identifier',
    'line_number': 5
}
```

#### Edge Attributes

**AST Edges:**
```python
{
    'edge_type': 'AST_edge'
}
```

**CFG Edges:**
```python
{
    'controlflow_type': 'if_true',
    'edge_type': 'CFG_edge',
    'label': 'if_true',
    'color': 'red'
}
```

**DFG Edges:**
```python
{
    'dataflow_type': 'definition',
    'edge_type': 'DFG_edge',
    'label': 'def',
    'color': 'blue'
}
```

### Graph Analysis Examples

#### Count Node Types

```python
from collections import Counter

driver = CombinedDriver(...)
graph = driver.get_graph()

# Count AST node types
node_types = [data.get('node_type', 'unknown')
              for _, data in graph.nodes(data=True)]
type_counts = Counter(node_types)
print(type_counts)
```

#### Find All Variables

```python
graph = driver.get_graph()

variables = [
    data['label']
    for node, data in graph.nodes(data=True)
    if data.get('node_type') == 'identifier'
]
print(f"Variables: {set(variables)}")
```

#### Trace Data Flow

```python
graph = driver.get_graph()

# Find all data flow edges
dfg_edges = [
    (src, dst, data)
    for src, dst, data in graph.edges(data=True)
    if data.get('edge_type') == 'DFG_edge'
]

for src, dst, data in dfg_edges:
    src_label = graph.nodes[src]['label']
    dst_label = graph.nodes[dst]['label']
    flow_type = data.get('dataflow_type', 'unknown')
    print(f"{src_label} --[{flow_type}]--> {dst_label}")
```

#### Export to Custom Format

```python
import json

driver = CombinedDriver(...)
graph = driver.get_graph()

# Convert to custom format
custom_format = {
    "nodes": [
        {"id": node, "label": data.get("label", "")}
        for node, data in graph.nodes(data=True)
    ],
    "edges": [
        {"from": src, "to": dst, "type": data.get("edge_type", "")}
        for src, dst, data in graph.edges(data=True)
    ]
}

with open("custom_output.json", "w") as f:
    json.dump(custom_format, f, indent=2)
```

## Advanced Usage

### Batch Processing

Process multiple files:

```python
import os
from pathlib import Path

def process_directory(directory, language="java"):
    results = {}

    for filepath in Path(directory).rglob(f"*.{language}"):
        with open(filepath, "r") as f:
            code = f.read()

        try:
            driver = CombinedDriver(
                src_language=language,
                src_code=code,
                output_file=None,  # In-memory only
                graph_format="json",
                codeviews={
                    "AST": {"exists": True, "collapsed": False,
                            "minimized": False, "blacklisted": []},
                    "CFG": {"exists": True},
                    "DFG": {"exists": True, "collapsed": False,
                            "minimized": False, "statements": True,
                            "last_def": False, "last_use": False}
                }
            )

            results[str(filepath)] = driver.get_graph()
            print(f"✓ Processed {filepath}")
        except Exception as e:
            print(f"✗ Error processing {filepath}: {e}")

    return results

# Process all Java files in a directory
graphs = process_directory("./src", language="java")
print(f"Processed {len(graphs)} files")
```

### Custom Graph Post-Processing

```python
def remove_small_components(graph, min_size=5):
    """Remove small disconnected components from graph"""
    import networkx as nx

    # Convert to undirected for component analysis
    undirected = graph.to_undirected()

    # Find connected components
    components = list(nx.connected_components(undirected))

    # Remove small components
    for component in components:
        if len(component) < min_size:
            graph.remove_nodes_from(component)

    return graph

driver = CombinedDriver(...)
graph = driver.get_graph()
cleaned_graph = remove_small_components(graph)
```

### Merging Multiple Graphs

```python
import networkx as nx

# Generate graphs for multiple code snippets
graphs = []

for code_snippet in code_snippets:
    driver = CombinedDriver(
        src_language="java",
        src_code=code_snippet,
        output_file=None,
        graph_format="json",
        codeviews={...}
    )
    graphs.append(driver.get_graph())

# Merge into single graph
merged = nx.compose_all(graphs)
```

### Custom Visualization

```python
import matplotlib.pyplot as plt
import networkx as nx

driver = CombinedDriver(...)
graph = driver.get_graph()

# Create layout
pos = nx.spring_layout(graph)

# Draw nodes by type
ast_nodes = [n for n, d in graph.nodes(data=True)
             if d.get('edge_type') == 'AST_edge']
cfg_nodes = [n for n, d in graph.nodes(data=True)
             if d.get('edge_type') == 'CFG_edge']

nx.draw_networkx_nodes(graph, pos, nodelist=ast_nodes,
                       node_color='green', label='AST')
nx.draw_networkx_nodes(graph, pos, nodelist=cfg_nodes,
                       node_color='red', label='CFG')
nx.draw_networkx_edges(graph, pos)
nx.draw_networkx_labels(graph, pos)

plt.legend()
plt.savefig("custom_visualization.png")
```

## Integration Examples

### Flask Web Service

```python
from flask import Flask, request, jsonify
from comex.codeviews.combined_graph.combined_driver import CombinedDriver

app = Flask(__name__)

@app.route('/analyze', methods=['POST'])
def analyze_code():
    data = request.json
    code = data.get('code')
    language = data.get('language', 'java')
    graphs = data.get('graphs', ['ast', 'cfg', 'dfg'])

    codeviews = {
        "AST": {"exists": 'ast' in graphs, "collapsed": False,
                "minimized": False, "blacklisted": []},
        "CFG": {"exists": 'cfg' in graphs},
        "DFG": {"exists": 'dfg' in graphs, "collapsed": False,
                "minimized": False, "statements": True,
                "last_def": False, "last_use": False}
    }

    driver = CombinedDriver(
        src_language=language,
        src_code=code,
        output_file=None,
        graph_format="json",
        codeviews=codeviews
    )

    return jsonify(driver.json)

if __name__ == '__main__':
    app.run(debug=True)
```

### Jupyter Notebook

```python
# In Jupyter notebook
from comex.codeviews.combined_graph.combined_driver import CombinedDriver
from IPython.display import Image, display

code = """
public class Example {
    public static void main(String[] args) {
        int x = 5;
        System.out.println(x);
    }
}
"""

driver = CombinedDriver(
    src_language="java",
    src_code=code,
    output_file="notebook_output.json",
    graph_format="all",
    codeviews={
        "AST": {"exists": True, "collapsed": False, "minimized": False, "blacklisted": []},
        "CFG": {"exists": True},
        "DFG": {"exists": True, "collapsed": False, "minimized": False,
                "statements": True, "last_def": False, "last_use": False}
    }
)

# Display the graph image
display(Image("notebook_output.png"))

# Analyze the graph
graph = driver.get_graph()
print(f"Generated graph with {graph.number_of_nodes()} nodes")
```

### Data Science Pipeline

```python
import pandas as pd
import networkx as nx

def extract_features(code, language="java"):
    """Extract graph-based features from code"""
    driver = CombinedDriver(
        src_language=language,
        src_code=code,
        output_file=None,
        graph_format="json",
        codeviews={
            "AST": {"exists": True, "collapsed": False, "minimized": False, "blacklisted": []},
            "CFG": {"exists": True},
            "DFG": {"exists": True, "collapsed": False, "minimized": False,
                    "statements": True, "last_def": False, "last_use": False}
        }
    )

    graph = driver.get_graph()

    return {
        'num_nodes': graph.number_of_nodes(),
        'num_edges': graph.number_of_edges(),
        'density': nx.density(graph),
        'avg_degree': sum(dict(graph.degree()).values()) / graph.number_of_nodes(),
        # Add more features...
    }

# Build dataset
df = pd.DataFrame([
    extract_features(code) for code in code_samples
])
```

## See Also

- [CLI Reference](02-cli-reference.md) - Command-line interface
- [Codeview Types](04-codeview-types.md) - Understanding graph types
- [Architecture Overview](05-architecture.md) - Internal design
- [Examples](12-examples.md) - More usage patterns
