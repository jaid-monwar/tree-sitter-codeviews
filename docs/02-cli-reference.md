# CLI Reference

Complete reference for Comex command-line interface.

## Basic Syntax

```bash
comex [OPTIONS]
```

## Required Options

### `--lang` (Required)

Specifies the programming language of the input code.

**Values:**
- `java` - Java programming language
- `cs` - C# programming language

**Example:**
```bash
comex --lang "java" --code-file example.java --graphs "ast"
```

## Input Options

You must provide **either** `--code` or `--code-file` (not both).

### `--code-file`

Path to the source code file to analyze.

**Type:** File path (string)

**Example:**
```bash
comex --lang "java" --code-file ./src/Main.java --graphs "cfg"
```

**Supported file extensions:**
- `.java` for Java
- `.cs` for C#

### `--code`

Inline source code as a string (alternative to `--code-file`).

**Type:** String (use quotes for multi-line code)

**Example:**
```bash
comex --lang "java" --code "
public class Test {
    public static void main(String[] args) {
        int x = 5;
        System.out.println(x);
    }
}" --graphs "ast"
```

**Note:** For complex code, using `--code-file` is recommended.

## Graph Selection

### `--graphs`

Specifies which codeview graphs to generate.

**Type:** Comma-separated list (no spaces)

**Available values:**
- `ast` - Abstract Syntax Tree
- `cfg` - Control Flow Graph
- `dfg` - Data Flow Graph

**Default:** `"ast,dfg"`

**Examples:**

Single graph:
```bash
comex --lang "java" --code-file test.java --graphs "cfg"
```

Multiple graphs (combined):
```bash
comex --lang "java" --code-file test.java --graphs "ast,cfg"
comex --lang "java" --code-file test.java --graphs "cfg,dfg"
comex --lang "java" --code-file test.java --graphs "ast,cfg,dfg"
```

**Valid combinations:**
- `ast` - AST only
- `cfg` - CFG only
- `dfg` - DFG only
- `ast,cfg` - Combined AST + CFG
- `ast,dfg` - Combined AST + DFG
- `cfg,dfg` - Combined CFG + DFG
- `ast,cfg,dfg` - Combined AST + CFG + DFG

## Output Options

### `--output`

Specifies the output format(s).

**Type:** String

**Values:**
- `dot` - Generate DOT file and PNG image (default)
- `json` - Generate JSON file only
- `all` - Generate both JSON and DOT/PNG

**Default:** `"dot"`

**Examples:**

JSON only (no visualization):
```bash
comex --lang "java" --code-file test.java --graphs "ast" --output "json"
```

Both formats:
```bash
comex --lang "java" --code-file test.java --graphs "cfg" --output "all"
```

**Output files created:**
- **JSON format:** `output.json` - NetworkX graph in JSON format
- **DOT format:** `output.dot` - GraphViz DOT file
- **PNG format:** `output.png` - Visual graph (requires GraphViz)

## AST Customization Options

### `--blacklisted`

Remove specific node types from the AST.

**Type:** Comma-separated list of node types

**Default:** `""` (empty, no nodes blacklisted)

**Use cases:**
- Remove noise from AST (imports, package declarations)
- Focus on specific code structures
- Reduce graph complexity

**Example:**

Remove import and package declarations:
```bash
comex --lang "java" --code-file test.java --graphs "ast" \
  --blacklisted "import_declaration,package_declaration"
```

Remove method declarations (show only class structure):
```bash
comex --lang "cs" --code-file test.cs --graphs "ast" \
  --blacklisted "method_declaration"
```

**Common node types to blacklist:**

**Java:**
- `import_declaration`
- `package_declaration`
- `comment`
- `line_comment`
- `block_comment`

**C#:**
- `using_directive`
- `namespace_declaration`
- `comment`

**Note:** Use `--debug` to see all node types in your code.

### `--collapsed`

Collapse duplicate variable nodes into single nodes.

**Type:** Boolean flag

**Default:** `False`

**Behavior:**
- Without `--collapsed`: Each variable usage creates a separate node
- With `--collapsed`: All usages of the same variable merge into one node

**Example:**

```bash
comex --lang "java" --code-file test.java --graphs "ast,dfg" --collapsed
```

**When to use:**
- Simplify large graphs with many variable references
- Focus on unique variables rather than usage count
- Works with both AST and DFG

**Visual difference:**

Without `--collapsed`:
```
x (line 5) -> x (line 6) -> x (line 7)
```

With `--collapsed`:
```
x
```

## DFG Customization Options

### `--last-def`

Add last definition information to Data Flow Graph edges.

**Type:** Boolean flag

**Default:** `False`

**Behavior:**
- Annotates DFG edges with the most recent definition of each variable
- Useful for reaching definitions analysis

**Example:**

```bash
comex --lang "java" --code-file test.java --graphs "dfg" --last-def
```

### `--last-use`

Add last use information to Data Flow Graph edges.

**Type:** Boolean flag

**Default:** `False`

**Behavior:**
- Annotates DFG edges with the most recent use of each variable
- Useful for liveness analysis

**Example:**

```bash
comex --lang "java" --code-file test.java --graphs "dfg" --last-use
```

**Combined example:**
```bash
comex --lang "java" --code-file test.java --graphs "dfg" --last-def --last-use
```

## Debugging Options

### `--debug`

Enable debug-level logging.

**Type:** Boolean flag

**Default:** `False`

**Behavior:**
- Shows detailed parsing information
- Displays tree-sitter AST node types
- Logs graph construction steps
- Helpful for troubleshooting and understanding internals

**Example:**

```bash
comex --lang "java" --code-file test.java --graphs "cfg" --debug
```

**Sample debug output:**
```
DEBUG: Parsing source code with tree-sitter
DEBUG: Root node type: program
DEBUG: Found method: main
DEBUG: Creating CFG node: assignment_expression
DEBUG: Adding CFG edge: if_statement -> block
```

**When to use debug mode:**
- Investigating parsing errors
- Understanding which AST nodes are generated
- Debugging custom configurations
- Contributing to development

### `--throw-parse-error`

Throw an error if code cannot be parsed (instead of continuing with partial results).

**Type:** Boolean flag

**Default:** `False`

**Behavior:**
- Without flag: Comex attempts to generate graphs even with syntax errors
- With flag: Comex stops and raises an error on syntax issues

**Example:**

```bash
comex --lang "java" --code-file broken.java --graphs "ast" --throw-parse-error
```

## Complete Examples

### Example 1: Basic Java AST

```bash
comex --lang "java" \
  --code-file MyClass.java \
  --graphs "ast" \
  --output "all"
```

**Generates:**
- `output.json` - AST in JSON
- `output.dot` - AST in DOT format
- `output.png` - Visual AST

### Example 2: C# CFG + DFG with Collapsed Nodes

```bash
comex --lang "cs" \
  --code-file Program.cs \
  --graphs "cfg,dfg" \
  --collapsed \
  --output "json"
```

**Generates:**
- `output.json` - Combined CFG + DFG with collapsed variables

### Example 3: Minimal AST (Blacklist Imports)

```bash
comex --lang "java" \
  --code-file Complex.java \
  --graphs "ast" \
  --blacklisted "import_declaration,package_declaration,comment" \
  --output "all"
```

**Generates:**
- Clean AST without imports, packages, or comments

### Example 4: Advanced DFG Analysis

```bash
comex --lang "java" \
  --code-file Algorithm.java \
  --graphs "dfg" \
  --last-def \
  --last-use \
  --collapsed \
  --output "all" \
  --debug
```

**Generates:**
- DFG with reaching definitions and liveness info
- Collapsed variable nodes
- Debug output in terminal

### Example 5: Full Analysis (All Graphs)

```bash
comex --lang "java" \
  --code-file Example.java \
  --graphs "ast,cfg,dfg" \
  --output "all"
```

**Generates:**
- Combined graph with all three codeviews
- Both JSON and visual outputs

## Output File Naming

All output files are named `output.*` by default:
- `output.json`
- `output.dot`
- `output.png`

**Note:** To specify custom output file names, use the Python API (see [Python API Guide](03-python-api.md)).

## Exit Codes

- `0` - Success
- `-1` - Error (parsing failed, invalid options, file not found, etc.)

## Environment Variables

Comex respects the following environment variables:

### `GITHUB_ACTIONS`

When set (e.g., in CI/CD), Comex skips writing output files to disk.

```bash
export GITHUB_ACTIONS=true
comex --lang "java" --code-file test.java --graphs "ast"
# No files written, graph generated in memory only
```

## Help Command

Display help message with all options:

```bash
comex --help
```

## Version Information

Check installed Comex version:

```bash
pip show comex
```

## Tips and Best Practices

### 1. Start Simple

Begin with a single graph type to understand the output:
```bash
comex --lang "java" --code-file test.java --graphs "ast"
```

### 2. Use Debug Mode for Learning

Enable debug to see what's happening:
```bash
comex --lang "java" --code-file test.java --graphs "cfg" --debug
```

### 3. Blacklist Noise

Remove boilerplate for cleaner graphs:
```bash
--blacklisted "import_declaration,package_declaration"
```

### 4. Collapse for Large Files

Use `--collapsed` for files with many variable references:
```bash
--collapsed
```

### 5. JSON for Programmatic Use

Use JSON output for post-processing:
```bash
--output "json"
```

### 6. PNG for Presentations

Use visual output for documentation and presentations:
```bash
--output "all"
```

## See Also

- [Python API Guide](03-python-api.md) - Programmatic usage with more control
- [Codeview Types](04-codeview-types.md) - Understanding AST, CFG, DFG
- [Examples](12-examples.md) - Real-world usage patterns
- [Troubleshooting](10-troubleshooting.md) - Common issues and solutions
