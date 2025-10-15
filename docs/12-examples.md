# Examples

Real-world usage examples and patterns for Comex.

## Table of Contents

- [Basic Usage Examples](#basic-usage-examples)
- [Task-Specific Examples](#task-specific-examples)
- [Integration Examples](#integration-examples)
- [Advanced Patterns](#advanced-patterns)

## Basic Usage Examples

### Example 1: Simple AST Generation

**Task:** Generate AST for a simple Java class.

**Code:**
```bash
# Create test file
cat > Hello.java << 'EOF'
public class Hello {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
EOF

# Generate AST
comex --lang "java" --code-file Hello.java --graphs "ast" --output "all"
```

**Output:**
- `output.json` - AST in JSON
- `output.dot` - AST in DOT
- `output.png` - Visualization

**Nodes in AST:**
- `program`
- `class_declaration` (Hello)
- `method_declaration` (main)
- `method_invocation` (println)
- `string_literal` ("Hello, World!")

---

### Example 2: Control Flow Analysis

**Task:** Analyze control flow of conditional logic.

**Code:**
```bash
cat > Conditional.java << 'EOF'
public class Conditional {
    public String check(int x) {
        if (x > 0) {
            return "positive";
        } else if (x < 0) {
            return "negative";
        } else {
            return "zero";
        }
    }
}
EOF

comex --lang "java" --code-file Conditional.java --graphs "cfg"
```

**CFG Edges:**
- START → if (x > 0)
- if (x > 0) --true--> return "positive"
- if (x > 0) --false--> else if (x < 0)
- else if (x < 0) --true--> return "negative"
- else if (x < 0) --false--> return "zero"
- All returns → END

---

### Example 3: Data Flow Tracking

**Task:** Track data dependencies in calculation.

**Code:**
```bash
cat > Calculate.java << 'EOF'
public class Calculate {
    public int compute(int a, int b) {
        int sum = a + b;
        int product = a * b;
        int result = sum + product;
        return result;
    }
}
EOF

comex --lang "java" --code-file Calculate.java --graphs "dfg" --last-def
```

**DFG Edges:**
- a, b → sum (sum depends on a, b)
- a, b → product (product depends on a, b)
- sum, product → result (result depends on sum, product)
- result → return

**With `--last-def`:** Each edge annotated with line number of last definition.

---

### Example 4: Combined View

**Task:** Get comprehensive code representation.

**Code:**
```bash
comex --lang "java" --code-file Calculate.java \
  --graphs "ast,cfg,dfg" \
  --output "all"
```

**Result:** Single graph with:
- AST edges (green in visualization)
- CFG edges (red)
- DFG edges (blue)

**Use case:** Machine learning training data, comprehensive code analysis.

---

## Task-Specific Examples

### Code Clone Detection

**Task:** Generate graphs for clone detection.

**Python Script:**
```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver
import os
import json

def extract_clone_features(file_path, language="java"):
    """Extract graph-based features for clone detection"""
    with open(file_path) as f:
        code = f.read()

    # Configuration for clone detection
    codeviews = {
        "AST": {
            "exists": True,
            "collapsed": True,  # Reduce graph size
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

    driver = CombinedDriver(
        src_language=language,
        src_code=code,
        output_file=None,  # In-memory only
        graph_format="json",
        codeviews=codeviews
    )

    graph = driver.get_graph()

    # Extract features
    features = {
        'file': file_path,
        'num_nodes': graph.number_of_nodes(),
        'num_edges': graph.number_of_edges(),
        'node_types': {},
        'edge_types': {}
    }

    # Count node types
    for _, data in graph.nodes(data=True):
        node_type = data.get('node_type', 'unknown')
        features['node_types'][node_type] = \
            features['node_types'].get(node_type, 0) + 1

    # Count edge types
    for _, _, data in graph.edges(data=True):
        edge_type = data.get('edge_type', 'unknown')
        features['edge_types'][edge_type] = \
            features['edge_types'].get(edge_type, 0) + 1

    return features

# Process multiple files
files = ['code1.java', 'code2.java', 'code3.java']
features = [extract_clone_features(f) for f in files]

# Compare features to detect clones
# (similarity computation omitted)
```

---

### Bug Detection (Null Pointer Analysis)

**Task:** Detect potential null pointer dereferences.

**Python Script:**
```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver

def find_null_pointer_bugs(code, language="java"):
    """Find potential null pointer dereferences"""
    codeviews = {
        "AST": {"exists": False},
        "CFG": {"exists": True},
        "DFG": {
            "exists": True,
            "collapsed": False,
            "minimized": False,
            "statements": True,
            "last_def": True,  # Track definitions
            "last_use": False
        }
    }

    driver = CombinedDriver(
        src_language=language,
        src_code=code,
        output_file=None,
        graph_format="json",
        codeviews=codeviews
    )

    graph = driver.get_graph()

    # Find potential bugs
    bugs = []

    # Look for null assignments followed by dereferences
    for node, data in graph.nodes(data=True):
        label = data.get('label', '')

        # Find null assignments
        if 'null' in label.lower():
            # Check if this variable is later dereferenced
            successors = list(graph.successors(node))
            for succ in successors:
                succ_label = graph.nodes[succ].get('label', '')
                if '.' in succ_label or '(' in succ_label:
                    bugs.append({
                        'type': 'potential_null_pointer',
                        'assignment': label,
                        'dereference': succ_label,
                        'line': data.get('line_number', 'unknown')
                    })

    return bugs

# Test
code = """
public class Test {
    public void method() {
        String s = null;
        int len = s.length();  // Null pointer!
    }
}
"""

bugs = find_null_pointer_bugs(code)
for bug in bugs:
    print(f"Bug at line {bug['line']}: {bug['type']}")
```

---

### Code Translation

**Task:** Prepare graphs for Java to Python translation.

**Python Script:**
```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver

def prepare_translation_data(java_code, output_path):
    """Generate comprehensive graph for translation"""
    codeviews = {
        "AST": {
            "exists": True,
            "collapsed": False,  # Keep all structure
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

    driver = CombinedDriver(
        src_language="java",
        src_code=java_code,
        output_file=output_path,
        graph_format="json",
        codeviews=codeviews
    )

    return driver.json

# Process Java code
java_code = """
public class Fibonacci {
    public int fib(int n) {
        if (n <= 1) {
            return n;
        }
        return fib(n-1) + fib(n-2);
    }
}
"""

graph_data = prepare_translation_data(java_code, "fib_graph.json")

# Use graph_data for translation model training/inference
```

---

### Code Search

**Task:** Create searchable code representations.

**Python Script:**
```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver
import networkx as nx

def create_search_index(code_files, language="java"):
    """Create search index from code files"""
    index = {}

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

    for file_path in code_files:
        with open(file_path) as f:
            code = f.read()

        driver = CombinedDriver(
            src_language=language,
            src_code=code,
            output_file=None,
            graph_format="json",
            codeviews=codeviews
        )

        graph = driver.get_graph()

        # Index by method names
        for node, data in graph.nodes(data=True):
            if data.get('node_type') == 'method_declaration':
                method_name = data.get('label', '')
                if method_name not in index:
                    index[method_name] = []
                index[method_name].append({
                    'file': file_path,
                    'graph': graph
                })

    return index

def search_methods(index, query):
    """Search for methods matching query"""
    results = []
    for method_name, entries in index.items():
        if query.lower() in method_name.lower():
            results.extend(entries)
    return results

# Build index
files = ['src/Main.java', 'src/Utils.java', 'src/Helper.java']
index = create_search_index(files)

# Search
results = search_methods(index, "calculate")
for result in results:
    print(f"Found in: {result['file']}")
```

---

## Integration Examples

### Flask Web Service

**Task:** Create REST API for codeview generation.

```python
from flask import Flask, request, jsonify, send_file
from comex.codeviews.combined_graph.combined_driver import CombinedDriver
import tempfile
import os

app = Flask(__name__)

@app.route('/analyze', methods=['POST'])
def analyze():
    """Generate codeview from submitted code"""
    data = request.json

    code = data.get('code')
    language = data.get('language', 'java')
    graphs = data.get('graphs', ['ast'])

    if not code:
        return jsonify({'error': 'No code provided'}), 400

    # Build codeviews config
    codeviews = {
        "AST": {"exists": 'ast' in graphs, "collapsed": False,
                "minimized": False, "blacklisted": []},
        "CFG": {"exists": 'cfg' in graphs},
        "DFG": {"exists": 'dfg' in graphs, "collapsed": False,
                "minimized": False, "statements": True,
                "last_def": False, "last_use": False}
    }

    try:
        driver = CombinedDriver(
            src_language=language,
            src_code=code,
            output_file=None,
            graph_format="json",
            codeviews=codeviews
        )

        return jsonify({
            'status': 'success',
            'graph': driver.json
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/visualize', methods=['POST'])
def visualize():
    """Generate and return graph visualization"""
    data = request.json

    code = data.get('code')
    language = data.get('language', 'java')

    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json',
                                     delete=False) as f:
        output_path = f.name

    try:
        driver = CombinedDriver(
            src_language=language,
            src_code=code,
            output_file=output_path,
            graph_format="all",
            codeviews={
                "AST": {"exists": True, "collapsed": False,
                        "minimized": False, "blacklisted": []},
                "CFG": {"exists": False},
                "DFG": {"exists": False}
            }
        )

        # Return PNG image
        png_path = output_path.replace('.json', '.png')
        return send_file(png_path, mimetype='image/png')

    finally:
        # Cleanup
        for ext in ['.json', '.dot', '.png']:
            path = output_path.replace('.json', ext)
            if os.path.exists(path):
                os.remove(path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# Usage:
# curl -X POST http://localhost:5000/analyze \
#   -H "Content-Type: application/json" \
#   -d '{"code": "public class Test {}", "language": "java", "graphs": ["ast"]}'
```

---

### Batch Processing Script

**Task:** Process entire codebase.

```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import json
import time

def process_file(file_path):
    """Process single file"""
    try:
        with open(file_path) as f:
            code = f.read()

        # Determine language from extension
        ext = file_path.suffix
        language = "java" if ext == ".java" else "cs"

        driver = CombinedDriver(
            src_language=language,
            src_code=code,
            output_file=None,
            graph_format="json",
            codeviews={
                "AST": {"exists": True, "collapsed": True,
                        "minimized": True,
                        "blacklisted": ["import_declaration", "package_declaration"]},
                "CFG": {"exists": True},
                "DFG": {"exists": True, "collapsed": True,
                        "minimized": False, "statements": True,
                        "last_def": False, "last_use": False}
            }
        )

        return {
            'file': str(file_path),
            'status': 'success',
            'nodes': driver.graph.number_of_nodes(),
            'edges': driver.graph.number_of_edges(),
            'graph': driver.json
        }

    except Exception as e:
        return {
            'file': str(file_path),
            'status': 'error',
            'error': str(e)
        }

def process_directory(directory, pattern="**/*.java", max_workers=4):
    """Process all matching files in directory"""
    directory = Path(directory)
    files = list(directory.glob(pattern))

    print(f"Found {len(files)} files")

    start = time.time()

    # Process in parallel
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_file, files))

    elapsed = time.time() - start

    # Summary
    success = sum(1 for r in results if r['status'] == 'success')
    failed = len(results) - success

    print(f"\nProcessed {len(results)} files in {elapsed:.2f}s")
    print(f"Success: {success}, Failed: {failed}")

    # Save results
    with open("batch_results.json", "w") as f:
        json.dump(results, f, indent=2)

    return results

# Usage
results = process_directory("./src", pattern="**/*.java", max_workers=8)

# Analyze results
total_nodes = sum(r.get('nodes', 0) for r in results
                  if r['status'] == 'success')
print(f"Total nodes across all files: {total_nodes}")
```

---

## Advanced Patterns

### Custom Graph Analysis

**Task:** Analyze cyclomatic complexity from CFG.

```python
from comex.codeviews.CFG.CFG_driver import CFGDriver
import networkx as nx

def calculate_cyclomatic_complexity(code, language="java"):
    """Calculate cyclomatic complexity from CFG"""
    driver = CFGDriver(
        src_language=language,
        src_code=code,
        output_file=None,
        properties={}
    )

    graph = driver.graph

    # Cyclomatic Complexity = E - N + 2P
    # E = number of edges
    # N = number of nodes
    # P = number of connected components (usually 1)

    E = graph.number_of_edges()
    N = graph.number_of_nodes()
    P = nx.number_weakly_connected_components(graph)

    complexity = E - N + 2 * P

    return complexity

# Test
code = """
public class Test {
    public void method(int x) {
        if (x > 0) {
            if (x > 10) {
                System.out.println("Large");
            } else {
                System.out.println("Small");
            }
        } else {
            System.out.println("Negative");
        }
    }
}
"""

complexity = calculate_cyclomatic_complexity(code)
print(f"Cyclomatic Complexity: {complexity}")
```

---

### Graph Similarity Comparison

**Task:** Compare two code snippets using graph edit distance.

```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver
import networkx as nx

def compare_codes(code1, code2, language="java"):
    """Compare two code snippets"""
    codeviews = {
        "AST": {"exists": True, "collapsed": True,
                "minimized": True,
                "blacklisted": ["import_declaration", "package_declaration"]},
        "CFG": {"exists": False},
        "DFG": {"exists": False}
    }

    # Generate graphs
    driver1 = CombinedDriver(
        src_language=language,
        src_code=code1,
        output_file=None,
        graph_format="json",
        codeviews=codeviews
    )

    driver2 = CombinedDriver(
        src_language=language,
        src_code=code2,
        output_file=None,
        graph_format="json",
        codeviews=codeviews
    )

    g1 = driver1.get_graph()
    g2 = driver2.get_graph()

    # Simple similarity metrics
    similarity = {
        'node_count_diff': abs(g1.number_of_nodes() - g2.number_of_nodes()),
        'edge_count_diff': abs(g1.number_of_edges() - g2.number_of_edges()),
    }

    # Node type distribution similarity
    def get_node_types(g):
        types = {}
        for _, data in g.nodes(data=True):
            t = data.get('node_type', 'unknown')
            types[t] = types.get(t, 0) + 1
        return types

    types1 = get_node_types(g1)
    types2 = get_node_types(g2)

    # Jaccard similarity of node types
    all_types = set(types1.keys()) | set(types2.keys())
    intersection = sum(min(types1.get(t, 0), types2.get(t, 0))
                      for t in all_types)
    union = sum(max(types1.get(t, 0), types2.get(t, 0))
               for t in all_types)

    similarity['jaccard'] = intersection / union if union > 0 else 0

    return similarity

# Example
code1 = "public class A { int x = 5; int y = 10; }"
code2 = "public class B { int x = 5; int y = 10; int z = 15; }"

sim = compare_codes(code1, code2)
print(f"Similarity: {sim}")
```

---

### Export to Custom Format

**Task:** Convert to format for external tool.

```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver
import json

def export_to_custom_format(code, language="java", output_path="custom.json"):
    """Export graph in custom JSON format"""
    driver = CombinedDriver(
        src_language=language,
        src_code=code,
        output_file=None,
        graph_format="json",
        codeviews={
            "AST": {"exists": True, "collapsed": False,
                    "minimized": False, "blacklisted": []},
            "CFG": {"exists": False},
            "DFG": {"exists": False}
        }
    )

    graph = driver.get_graph()

    # Custom format
    custom = {
        "metadata": {
            "language": language,
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges()
        },
        "vertices": [],
        "edges": []
    }

    # Convert nodes
    for node_id, attrs in graph.nodes(data=True):
        custom["vertices"].append({
            "id": node_id,
            "type": attrs.get("node_type", "unknown"),
            "text": attrs.get("label", ""),
            "properties": {k: v for k, v in attrs.items()
                          if k not in ["node_type", "label"]}
        })

    # Convert edges
    for src, dst, attrs in graph.edges(data=True):
        custom["edges"].append({
            "source": src,
            "target": dst,
            "type": attrs.get("edge_type", "unknown"),
            "properties": {k: v for k, v in attrs.items()
                          if k != "edge_type"}
        })

    # Save
    with open(output_path, "w") as f:
        json.dump(custom, f, indent=2)

    return custom

# Usage
code = "public class Test { int x = 5; }"
custom_graph = export_to_custom_format(code, "java", "custom.json")
```

---

## See Also

- [Getting Started](01-getting-started.md) - Installation and basics
- [CLI Reference](02-cli-reference.md) - Command-line options
- [Python API](03-python-api.md) - Programmatic usage
- [Configuration](09-configuration-guide.md) - Advanced configs
