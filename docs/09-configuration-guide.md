# Configuration Guide

Advanced configuration options and customization for Comex.

## Table of Contents

- [Codeview Configuration](#codeview-configuration)
- [AST Configuration](#ast-configuration)
- [CFG Configuration](#cfg-configuration)
- [DFG Configuration](#dfg-configuration)
- [Output Configuration](#output-configuration)
- [Performance Tuning](#performance-tuning)

## Codeview Configuration

### Configuration Dictionary Structure

The `codeviews` parameter controls which graphs are generated and how they are customized:

```python
codeviews = {
    "AST": {...},  # Abstract Syntax Tree config
    "CFG": {...},  # Control Flow Graph config
    "DFG": {...}   # Data Flow Graph config
}
```

### Enabling/Disabling Codeviews

```python
# Generate only AST
codeviews = {
    "AST": {"exists": True, ...},
    "CFG": {"exists": False},
    "DFG": {"exists": False}
}

# Generate CFG + DFG (no AST)
codeviews = {
    "AST": {"exists": False},
    "CFG": {"exists": True},
    "DFG": {"exists": True, ...}
}

# Generate all three
codeviews = {
    "AST": {"exists": True, ...},
    "CFG": {"exists": True},
    "DFG": {"exists": True, ...}
}
```

## AST Configuration

### Full Configuration Options

```python
ast_config = {
    "exists": True,              # Enable AST generation
    "collapsed": False,          # Collapse duplicate variable nodes
    "minimized": False,          # Enable node blacklisting
    "blacklisted": []            # List of node types to exclude
}
```

### Examples

#### 1. Basic AST

```python
codeviews = {
    "AST": {
        "exists": True,
        "collapsed": False,
        "minimized": False,
        "blacklisted": []
    },
    "CFG": {"exists": False},
    "DFG": {"exists": False}
}
```

**Use case:** Get complete AST with all nodes.

#### 2. Collapsed AST

```python
codeviews = {
    "AST": {
        "exists": True,
        "collapsed": True,         # Merge duplicate nodes
        "minimized": False,
        "blacklisted": []
    },
    "CFG": {"exists": False},
    "DFG": {"exists": False}
}
```

**Use case:** Simplify AST by merging variables that appear multiple times.

**Example effect:**
```
Before: x(line 3) → x(line 5) → x(line 7)
After:  x
```

#### 3. Minimized AST (Remove Noise)

```python
codeviews = {
    "AST": {
        "exists": True,
        "collapsed": False,
        "minimized": True,
        "blacklisted": [
            "import_declaration",
            "package_declaration",
            "comment",
            "line_comment"
        ]
    },
    "CFG": {"exists": False},
    "DFG": {"exists": False}
}
```

**Use case:** Focus on code logic by removing imports, packages, and comments.

#### 4. Collapsed + Minimized

```python
codeviews = {
    "AST": {
        "exists": True,
        "collapsed": True,
        "minimized": True,
        "blacklisted": ["import_declaration", "package_declaration"]
    },
    "CFG": {"exists": False},
    "DFG": {"exists": False}
}
```

**Use case:** Maximum simplification - clean AST with merged variables.

### Common Blacklist Patterns

#### Java

```python
# Remove boilerplate
blacklisted = ["import_declaration", "package_declaration"]

# Remove all comments
blacklisted = ["comment", "line_comment", "block_comment"]

# Keep only method bodies
blacklisted = ["import_declaration", "package_declaration", "class_declaration"]

# Remove annotations
blacklisted = ["marker_annotation", "annotation"]
```

#### C#

```python
# Remove boilerplate
blacklisted = ["using_directive", "namespace_declaration"]

# Remove comments
blacklisted = ["comment"]

# Remove attributes
blacklisted = ["attribute_list"]
```

### Finding Node Types to Blacklist

**Method 1: Use debug mode**

```bash
comex --lang "java" --code-file test.java --graphs "ast" --debug
```

Debug output shows all node types encountered.

**Method 2: Read node definitions**

Check `src/comex/utils/java_nodes.py` or `src/comex/utils/cs_nodes.py` for all available node types.

**Method 3: Inspect output JSON**

```python
import json

driver = CombinedDriver(...)
with open("output.json") as f:
    data = json.load(f)

node_types = {node['node_type'] for node in data['nodes'] if 'node_type' in node}
print(node_types)
```

## CFG Configuration

### Configuration Options

```python
cfg_config = {
    "exists": True  # Enable CFG generation
}
```

CFG has no additional customization options currently.

### Examples

#### Basic CFG

```python
codeviews = {
    "AST": {"exists": False},
    "CFG": {"exists": True},
    "DFG": {"exists": False}
}
```

**Output:** Control flow graph showing execution paths.

## DFG Configuration

### Full Configuration Options

```python
dfg_config = {
    "exists": True,              # Enable DFG generation
    "collapsed": False,          # Collapse duplicate variable nodes
    "minimized": False,          # Reserved for future use
    "statements": True,          # Use statement-level DFG (always True)
    "last_def": False,           # Annotate with last definition
    "last_use": False            # Annotate with last use
}
```

### Examples

#### 1. Basic DFG

```python
codeviews = {
    "AST": {"exists": False},
    "CFG": {"exists": False},
    "DFG": {
        "exists": True,
        "collapsed": False,
        "minimized": False,
        "statements": True,
        "last_def": False,
        "last_use": False
    }
}
```

**Use case:** Basic data flow tracking.

#### 2. DFG with Last Definition

```python
codeviews = {
    "AST": {"exists": False},
    "CFG": {"exists": False},
    "DFG": {
        "exists": True,
        "collapsed": False,
        "minimized": False,
        "statements": True,
        "last_def": True,          # Track last definition
        "last_use": False
    }
}
```

**Use case:** Reaching definitions analysis - know which definition reaches each use.

**Effect:** Edges annotated with `last_def` attribute indicating line number of last definition.

#### 3. DFG with Last Use

```python
codeviews = {
    "AST": {"exists": False},
    "CFG": {"exists": False},
    "DFG": {
        "exists": True,
        "collapsed": False,
        "minimized": False,
        "statements": True,
        "last_def": False,
        "last_use": True           # Track last use
    }
}
```

**Use case:** Liveness analysis - know where variables are last used.

**Effect:** Edges annotated with `last_use` attribute.

#### 4. Complete DFG Analysis

```python
codeviews = {
    "AST": {"exists": False},
    "CFG": {"exists": False},
    "DFG": {
        "exists": True,
        "collapsed": True,         # Merge duplicates
        "minimized": False,
        "statements": True,
        "last_def": True,
        "last_use": True
    }
}
```

**Use case:** Full data flow analysis with all annotations.

## Output Configuration

### Graph Format Options

```python
driver = CombinedDriver(
    ...,
    graph_format="all"  # "dot", "json", or "all"
)
```

#### Options

**1. DOT only (default)**

```python
graph_format="dot"
```

Creates:
- `output.dot` - GraphViz DOT file
- `output.png` - PNG visualization (requires GraphViz)

**2. JSON only**

```python
graph_format="json"
```

Creates:
- `output.json` - NetworkX node-link JSON

**3. Both formats**

```python
graph_format="all"
```

Creates:
- `output.json`
- `output.dot`
- `output.png`

### Output File Naming

**CLI:** Always outputs to `output.*`

**Python API:** Specify custom name

```python
driver = CombinedDriver(
    ...,
    output_file="my_custom_name.json",
    graph_format="all"
)
```

Creates:
- `my_custom_name.json`
- `my_custom_name.dot`
- `my_custom_name.png`

### In-Memory Only (No Files)

```python
driver = CombinedDriver(
    ...,
    output_file=None,     # No file output
    graph_format="json"   # Ignored when output_file=None
)

graph = driver.get_graph()  # Access in-memory graph
```

**Use case:** Batch processing, web services, programmatic analysis.

## Performance Tuning

### 1. Disable Unused Codeviews

Generate only what you need:

```python
# Instead of all three
codeviews = {
    "AST": {"exists": True, ...},
    "CFG": {"exists": True},
    "DFG": {"exists": True, ...}
}

# Generate only CFG
codeviews = {
    "AST": {"exists": False},
    "CFG": {"exists": True},
    "DFG": {"exists": False}
}
```

**Impact:** ~3x faster for single codeview vs. all three.

### 2. Use Collapsed Mode for Large Files

```python
codeviews = {
    "DFG": {
        "exists": True,
        "collapsed": True,  # Reduce graph size
        ...
    }
}
```

**Impact:** Smaller graphs, faster processing, less memory.

### 3. Skip File Output for Batch Processing

```python
driver = CombinedDriver(
    ...,
    output_file=None  # Skip I/O
)
```

**Impact:** Faster when processing many files.

### 4. Minimize AST Size

```python
codeviews = {
    "AST": {
        "exists": True,
        "minimized": True,
        "blacklisted": [
            "import_declaration",
            "package_declaration",
            "comment"
        ]
    }
}
```

**Impact:** Smaller AST, faster generation.

### 5. Batch Processing Pattern

```python
def process_files_efficiently(file_paths):
    results = []

    for path in file_paths:
        with open(path) as f:
            code = f.read()

        driver = CombinedDriver(
            src_language="java",
            src_code=code,
            output_file=None,        # No I/O
            graph_format="json",     # Ignored
            codeviews={
                "CFG": {"exists": True},  # Only what's needed
                "AST": {"exists": False},
                "DFG": {"exists": False}
            }
        )

        results.append(driver.get_graph())

    return results
```

## Common Configuration Recipes

### Recipe 1: Code Clone Detection

```python
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
        "collapsed": True,
        "minimized": False,
        "statements": True,
        "last_def": False,
        "last_use": False
    }
}
```

**Rationale:** AST + DFG with collapsed nodes reduces graph size while preserving semantic structure.

### Recipe 2: Bug Detection

```python
codeviews = {
    "AST": {"exists": False},
    "CFG": {"exists": True},
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

**Rationale:** CFG + DFG with RDA annotations for finding null pointer, resource leaks, etc.

### Recipe 3: Code Translation

```python
codeviews = {
    "AST": {
        "exists": True,
        "collapsed": False,
        "minimized": False,
        "blacklisted": []
    },
    "CFG": {"exists": True},
    "DFG": {
        "exists": True,
        "collapsed": False,
        "minimized": False,
        "statements": True,
        "last_def": True,
        "last_use": False
    }
}
```

**Rationale:** Complete representation for understanding code semantics.

### Recipe 4: Code Search

```python
codeviews = {
    "AST": {
        "exists": True,
        "collapsed": True,
        "minimized": True,
        "blacklisted": [
            "import_declaration",
            "package_declaration",
            "comment"
        ]
    },
    "CFG": {"exists": False},
    "DFG": {"exists": False}
}
```

**Rationale:** Simplified AST for fast matching.

### Recipe 5: ML Training Data

```python
codeviews = {
    "AST": {
        "exists": True,
        "collapsed": False,
        "minimized": False,
        "blacklisted": []
    },
    "CFG": {"exists": True},
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

**Rationale:** Maximum information for model training.

## See Also

- [CLI Reference](02-cli-reference.md) - Command-line options
- [Python API](03-python-api.md) - Programmatic usage
- [Codeview Types](04-codeview-types.md) - Understanding graph types
- [Examples](12-examples.md) - Real-world patterns
