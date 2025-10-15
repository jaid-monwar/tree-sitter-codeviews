# Getting Started with Comex

This guide will help you install Comex and generate your first codeview graphs.

## Prerequisites

Before installing Comex, ensure you have:

- **Python 3.8 or higher**
- **GraphViz** (for visualization) - [Download here](https://graphviz.org/download/)
  - Linux: `sudo apt-get install graphviz` or `sudo yum install graphviz`
  - macOS: `brew install graphviz`
  - Windows: Download installer from GraphViz website
- **pip** (Python package manager)

### Verify GraphViz Installation

After installing GraphViz, verify it's available:

```bash
dot -V
```

You should see output like: `dot - graphviz version 2.43.0 (0)`

## Installation

### Option 1: Install from PyPI (Recommended)

Install the latest stable version from PyPI:

```bash
pip install comex
```

### Option 2: Install from Source (For Development)

Clone the repository and install in editable mode:

```bash
# Clone the repository
git clone https://github.com/IBM/tree-sitter-codeviews.git
cd tree-sitter-codeviews

# Install in development mode
pip install -r requirements-dev.txt
```

The `-e` flag in `requirements-dev.txt` installs Comex in editable mode, so code changes are immediately reflected without reinstalling.

### Verify Installation

Check if Comex is installed correctly:

```bash
comex --help
```

You should see the CLI help message with available options.

## First Run - Important Note

**On first run**, Comex will automatically:
1. Download tree-sitter grammars for Java and C#
2. Build language parsers
3. Cache them in `/tmp/comex/` (Linux/macOS) or equivalent temp directory

This process takes a few seconds and happens only once. You'll see output like:

```
Intial Setup: First time running COMEX on tree-sitter-java
Intial Setup: First time running COMEX on tree-sitter-c-sharp
```

## Quick Start Examples

### Example 1: Generate AST for Java Code

Create a simple Java file `hello.java`:

```java
public class Hello {
    public static void main(String[] args) {
        int x = 5;
        int y = 10;
        int sum = x + y;
        System.out.println(sum);
    }
}
```

Generate the AST:

```bash
comex --lang "java" --code-file hello.java --graphs "ast"
```

**Output files created:**
- `output.json` - AST in JSON format
- `output.dot` - AST in DOT format
- `output.png` - Visual representation of the AST

### Example 2: Generate CFG for C# Code

Create a C# file `example.cs`:

```csharp
public class Example {
    public void CheckValue(int x) {
        if (x > 0) {
            Console.WriteLine("Positive");
        } else {
            Console.WriteLine("Non-positive");
        }
    }
}
```

Generate the Control Flow Graph:

```bash
comex --lang "cs" --code-file example.cs --graphs "cfg"
```

### Example 3: Generate Combined CFG + DFG

For the same Java file, generate both Control Flow and Data Flow graphs:

```bash
comex --lang "java" --code-file hello.java --graphs "cfg,dfg"
```

This creates a combined graph showing both control flow and data dependencies.

### Example 4: All Three Graphs (AST + CFG + DFG)

```bash
comex --lang "java" --code-file hello.java --graphs "ast,cfg,dfg"
```

### Example 5: Using Inline Code

Instead of a file, you can provide code directly:

```bash
comex --lang "java" --code "
public class Max {
    public static void main(String[] args) {
        int a = 3;
        int b = 5;
        int max = (a > b) ? a : b;
    }
}" --graphs "cfg,dfg"
```

## Understanding the Output

### JSON Output (`output.json`)

The JSON file contains a NetworkX graph representation with:
- **nodes**: Array of graph nodes with attributes (id, label, type, etc.)
- **links**: Array of edges connecting nodes (source, target, edge_type)

Example structure:

```json
{
  "directed": true,
  "multigraph": true,
  "graph": {},
  "nodes": [
    {
      "id": 123,
      "label": "x",
      "node_type": "identifier",
      "shape": "box"
    }
  ],
  "links": [
    {
      "source": 123,
      "target": 456,
      "edge_type": "AST_edge"
    }
  ]
}
```

### DOT Output (`output.dot`)

The DOT file is a GraphViz format that describes the graph structure. It's used to generate the PNG visualization.

### PNG Output (`output.png`)

The PNG file is a visual representation of your codeview graph. Open it with any image viewer to see:
- **Green boxes**: AST nodes
- **Blue boxes**: CFG nodes
- **Orange boxes**: DFG nodes
- **Arrows**: Different edge types (parent-child, control flow, data flow)

## Common Options

### Specify Output Format

Generate only JSON (no visualization):

```bash
comex --lang "java" --code-file hello.java --graphs "ast" --output "json"
```

Generate both JSON and DOT/PNG (default):

```bash
comex --lang "java" --code-file hello.java --graphs "ast" --output "all"
```

### Collapsed Mode

Collapse duplicate variable nodes into single nodes:

```bash
comex --lang "java" --code-file hello.java --graphs "dfg" --collapsed
```

This is useful for reducing graph complexity when the same variable appears multiple times.

### Blacklist AST Nodes

Remove specific AST node types (e.g., import statements):

```bash
comex --lang "java" --code-file hello.java --graphs "ast" \
  --blacklisted "import_declaration,package_declaration"
```

### Enable Debug Logging

See detailed parsing and graph generation logs:

```bash
comex --lang "java" --code-file hello.java --graphs "cfg" --debug
```

## Next Steps

Now that you've generated your first codeviews, explore:

- [**CLI Reference**](02-cli-reference.md) - All CLI options and flags
- [**Python API Guide**](03-python-api.md) - Using Comex programmatically
- [**Codeview Types**](04-codeview-types.md) - Deep dive into AST, CFG, DFG
- [**Examples**](12-examples.md) - Real-world usage patterns

## Troubleshooting

### GraphViz Not Found

If you see an error like `dot: command not found`:
1. Install GraphViz (see Prerequisites)
2. Ensure `dot` is in your system PATH
3. Restart your terminal

### Python Version Issues

If you get compatibility errors:
```bash
python --version  # Should be 3.8+
pip install --upgrade comex
```

### First Run Takes Too Long

The first run downloads and builds parsers. This is normal and happens only once. Subsequent runs are much faster.

For more troubleshooting, see [Troubleshooting Guide](10-troubleshooting.md).
