# Extending Comex

Guide for extending Comex with new programming languages and features.

## Table of Contents

- [Adding a New Language](#adding-a-new-language)
- [Step-by-Step Tutorial](#step-by-step-tutorial)
- [Testing Your Extension](#testing-your-extension)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Adding a New Language

Comex is designed to be extensible. Adding support for a new programming language requires implementing several components.

### Required Components

1. **Tree-sitter Grammar** - Parser for the language
2. **Language Parser** - Extract tokens and build symbol tables
3. **Node Definitions** - AST node type mappings
4. **CFG Generator** - Control flow graph logic (language-specific)
5. **Integration** - Register language in drivers

### Prerequisites

- Tree-sitter grammar exists for the language (check [tree-sitter.github.io](https://tree-sitter.github.io/tree-sitter/))
- Understanding of language syntax and semantics
- Familiarity with control flow concepts

## Step-by-Step Tutorial

We'll add support for **Python** as an example.

### Step 1: Add Tree-sitter Grammar

Edit `src/comex/__init__.py`:

```python
def get_language_map():
    clone_directory = os.path.join(tempfile.gettempdir(), "comex")
    shared_languages = os.path.join(clone_directory, "languages.so")

    grammar_repos = [
        ("https://github.com/tree-sitter/tree-sitter-java", "09d650def6cdf7f479f4b78f595e9ef5b58ce31e"),
        ("https://github.com/tree-sitter/tree-sitter-c-sharp", "3ef3f7f99e16e528e6689eae44dff35150993307"),
        # Add Python grammar
        ("https://github.com/tree-sitter/tree-sitter-python", "4bfdd9033a2225cc95032ce77066b7aeca9e2ebd"),
    ]

    # ... existing code ...

    JAVA_LANGUAGE = Language(shared_languages, "java")
    C_SHARP_LANGUAGE = Language(shared_languages, "c_sharp")
    PYTHON_LANGUAGE = Language(shared_languages, "python")  # Add this

    return {
        "java": JAVA_LANGUAGE,
        "cs": C_SHARP_LANGUAGE,
        "python": PYTHON_LANGUAGE,  # Add this
    }
```

**Finding the commit hash:**
1. Visit the tree-sitter grammar repo on GitHub
2. Find a stable, recent commit
3. Use the full commit hash

### Step 2: Create Language Parser

Create `src/comex/tree_parser/python_parser.py`:

```python
from .custom_parser import CustomParser

class PythonParser(CustomParser):
    def __init__(self, src_language, src_code):
        super().__init__(src_language, src_code)

    def create_all_tokens(
        self,
        src_code,
        root_node,
        all_tokens,
        label,
        method_map,
        method_calls,
        start_line,
        declaration,
        declaration_map,
        symbol_table,
    ):
        """Extract tokens from Python parse tree"""
        self.traverse_tree(
            root_node,
            all_tokens,
            label,
            method_map,
            method_calls,
            start_line,
            declaration,
            declaration_map,
            symbol_table,
        )
        return (
            all_tokens,
            label,
            method_map,
            method_calls,
            start_line,
            declaration,
            declaration_map,
            symbol_table,
        )

    def traverse_tree(
        self,
        node,
        all_tokens,
        label,
        method_map,
        method_calls,
        start_line,
        declaration,
        declaration_map,
        symbol_table,
    ):
        """Recursively traverse parse tree"""
        node_type = node.type

        # Handle variable declarations
        if node_type == "assignment":
            self.handle_assignment(node, all_tokens, label, ...)

        # Handle function definitions
        elif node_type == "function_definition":
            self.handle_function_definition(node, method_map, ...)

        # Handle function calls
        elif node_type == "call":
            self.handle_function_call(node, method_calls, ...)

        # Handle identifiers
        elif node_type == "identifier":
            self.handle_identifier(node, all_tokens, label, ...)

        # Recursively process children
        for child in node.children:
            self.traverse_tree(child, all_tokens, label, ...)

    def handle_assignment(self, node, all_tokens, label, ...):
        """Process variable assignment"""
        # Extract variable name
        # Add to all_tokens
        # Update symbol table
        pass

    def handle_function_definition(self, node, method_map, ...):
        """Process function definition"""
        # Extract function name
        # Add to method_map
        # Track scope
        pass

    def handle_function_call(self, node, method_calls, ...):
        """Process function call"""
        # Extract function name
        # Add to method_calls
        pass

    def handle_identifier(self, node, all_tokens, label, ...):
        """Process identifier (variable/function reference)"""
        # Add to all_tokens
        # Set label
        pass
```

**Key implementation points:**

1. **Extend `CustomParser`**: Inherit base functionality
2. **Implement `create_all_tokens()`**: Main entry point
3. **Traverse parse tree**: Recursively process nodes
4. **Extract language constructs**: Variables, functions, classes
5. **Build symbol tables**: Track scopes and declarations

### Step 3: Create Node Definitions

Create `src/comex/utils/python_nodes.py`:

```python
"""Python AST node type definitions"""

PYTHON_NODE_TYPES = [
    # Module structure
    "module",

    # Statements
    "expression_statement",
    "assignment",
    "augmented_assignment",
    "return_statement",
    "if_statement",
    "for_statement",
    "while_statement",
    "with_statement",
    "try_statement",
    "import_statement",
    "import_from_statement",

    # Expressions
    "identifier",
    "integer",
    "float",
    "string",
    "list",
    "dict",
    "call",
    "attribute",
    "subscript",
    "binary_operator",
    "unary_operator",
    "comparison_operator",
    "boolean_operator",

    # Definitions
    "function_definition",
    "class_definition",
    "parameters",
    "parameter",

    # Other
    "block",
    "comment",
    # ... add all Python node types
]

# Common node types to blacklist
COMMON_BLACKLIST = [
    "import_statement",
    "import_from_statement",
    "comment",
]
```

**Finding node types:**
1. Parse sample Python code
2. Print the tree-sitter parse tree
3. Identify all node types
4. Categorize them

**Helper script:**
```python
from tree_sitter import Language, Parser
import os

# Load Python language
lang = Language('/path/to/languages.so', 'python')
parser = Parser()
parser.set_language(lang)

# Parse sample code
code = b"""
def hello(name):
    x = 5
    return x + 1
"""

tree = parser.parse(code)

def print_tree(node, indent=0):
    print("  " * indent + node.type)
    for child in node.children:
        print_tree(child, indent + 1)

print_tree(tree.root_node)
```

### Step 4: Create CFG Generator

Create `src/comex/codeviews/CFG/CFG_python.py`:

```python
import networkx as nx
from .CFG import CFGGraph

class CFGGraph_python(CFGGraph):
    def __init__(self, src_language, src_code, properties, root_node, parser):
        super().__init__(src_language, src_code, properties, root_node, parser)
        self.node_list = []
        self.edge_list = []
        self.create_CFG()
        self.graph = self.to_networkx(self.node_list, self.edge_list)

    def create_CFG(self):
        """Main CFG construction method"""
        # Find all function definitions
        functions = self.find_functions(self.root_node)

        for func_node in functions:
            self.process_function(func_node)

    def find_functions(self, node):
        """Find all function definitions"""
        functions = []
        if node.type == "function_definition":
            functions.append(node)
        for child in node.children:
            functions.extend(self.find_functions(child))
        return functions

    def process_function(self, func_node):
        """Process a function and create CFG"""
        # Create START node
        start_id = self.create_node("START", 0, "start")

        # Process function body
        body = self.find_body(func_node)
        last_nodes = self.process_statement_block(body, [start_id])

        # Create END node
        end_id = self.create_node("END", 999, "end")

        # Connect last nodes to END
        for node_id in last_nodes:
            self.create_edge(node_id, end_id, "sequential")

    def process_statement_block(self, block_node, entry_nodes):
        """Process a block of statements"""
        current_nodes = entry_nodes

        for statement in block_node.children:
            current_nodes = self.process_statement(statement, current_nodes)

        return current_nodes

    def process_statement(self, stmt_node, entry_nodes):
        """Process a single statement"""
        stmt_type = stmt_node.type

        if stmt_type == "if_statement":
            return self.handle_if(stmt_node, entry_nodes)
        elif stmt_type == "while_statement":
            return self.handle_while(stmt_node, entry_nodes)
        elif stmt_type == "for_statement":
            return self.handle_for(stmt_node, entry_nodes)
        elif stmt_type == "return_statement":
            return self.handle_return(stmt_node, entry_nodes)
        else:
            # Simple statement
            return self.handle_simple(stmt_node, entry_nodes)

    def handle_if(self, node, entry_nodes):
        """Handle if statement"""
        # Create condition node
        cond_id = self.create_node_from_tree(node, "if_statement")

        # Connect entry nodes to condition
        for entry_id in entry_nodes:
            self.create_edge(entry_id, cond_id, "sequential")

        # Process true branch
        true_branch = self.find_true_branch(node)
        true_nodes = self.process_statement_block(true_branch, [cond_id])

        # Process false branch (else)
        false_branch = self.find_false_branch(node)
        if false_branch:
            false_nodes = self.process_statement_block(false_branch, [cond_id])
        else:
            false_nodes = [cond_id]

        # Merge branches
        return true_nodes + false_nodes

    def handle_while(self, node, entry_nodes):
        """Handle while loop"""
        # Create condition node
        cond_id = self.create_node_from_tree(node, "while_statement")

        # Connect entry to condition
        for entry_id in entry_nodes:
            self.create_edge(entry_id, cond_id, "sequential")

        # Process loop body
        body = self.find_loop_body(node)
        body_exit_nodes = self.process_statement_block(body, [cond_id])

        # Create back edge from body to condition
        for exit_id in body_exit_nodes:
            self.create_edge(exit_id, cond_id, "loop_back")

        # Exit edge (loop false)
        return [cond_id]

    def handle_for(self, node, entry_nodes):
        """Handle for loop"""
        # Similar to while, but handle iterator
        # Create initialization
        # Create condition
        # Create update
        # Process body
        pass

    def handle_return(self, node, entry_nodes):
        """Handle return statement"""
        ret_id = self.create_node_from_tree(node, "return_statement")

        for entry_id in entry_nodes:
            self.create_edge(entry_id, ret_id, "sequential")

        # Return nodes connect to END (handled in process_function)
        return [ret_id]

    def handle_simple(self, node, entry_nodes):
        """Handle simple statement"""
        stmt_id = self.create_node_from_tree(node, node.type)

        for entry_id in entry_nodes:
            self.create_edge(entry_id, stmt_id, "sequential")

        return [stmt_id]

    # Helper methods

    def create_node(self, label, line, type_label):
        """Create a CFG node"""
        node_id = len(self.node_list)
        self.node_list.append((node_id, line, label, type_label))
        return node_id

    def create_node_from_tree(self, tree_node, type_label):
        """Create node from tree-sitter node"""
        label = self.src_code[tree_node.start_byte:tree_node.end_byte]
        line = tree_node.start_point[0]
        return self.create_node(label, line, type_label)

    def create_edge(self, source, target, edge_type):
        """Create a CFG edge"""
        self.edge_list.append((source, target, edge_type))

    def find_body(self, node):
        """Find function body block"""
        for child in node.children:
            if child.type == "block":
                return child
        return None

    def find_true_branch(self, if_node):
        """Find if-true branch"""
        # Parse if_statement structure
        pass

    def find_false_branch(self, if_node):
        """Find else branch"""
        # Parse if_statement structure
        pass

    def find_loop_body(self, loop_node):
        """Find loop body"""
        # Parse loop structure
        pass
```

**Key CFG implementation points:**

1. **Find control structures**: if, while, for, try, etc.
2. **Create nodes**: One per statement
3. **Create edges**: Based on control flow
4. **Handle branches**: True/false paths
5. **Handle loops**: Entry and back edges
6. **Handle returns**: Connect to END node

### Step 5: Register Language in Drivers

#### Update ParserDriver

Edit `src/comex/tree_parser/parser_driver.py`:

```python
from ..tree_parser.java_parser import JavaParser
from ..tree_parser.cs_parser import CSParser
from ..tree_parser.python_parser import PythonParser  # Add import

class ParserDriver:
    def __init__(self, src_language, src_code):
        # ... existing code ...

        self.parser_map = {
            "java": JavaParser,
            "cs": CSParser,
            "python": PythonParser,  # Add mapping
        }

        # ... rest of code ...
```

#### Update CFGDriver

Edit `src/comex/codeviews/CFG/CFG_driver.py`:

```python
from .CFG_csharp import CFGGraph_csharp
from .CFG_java import CFGGraph_java
from .CFG_python import CFGGraph_python  # Add import

class CFGDriver:
    def __init__(self, ...):
        # ... existing code ...

        self.CFG_map = {
            "java": CFGGraph_java,
            "cs": CFGGraph_csharp,
            "python": CFGGraph_python,  # Add mapping
        }

        # ... rest of code ...
```

#### Update CLI

Edit `src/comex/cli.py`:

Update the help text for `--lang`:

```python
@app.callback(invoke_without_command=True)
def main(
        lang: str = typer.Option(..., help="java, cs, python"),  # Update help
        # ... rest of parameters
):
```

### Step 6: Test Your Implementation

Create a test file `tests/data/CFG/test_python.py`:

```python
def fibonacci(n):
    if n <= 1:
        return n
    else:
        return fibonacci(n-1) + fibonacci(n-2)

def main():
    x = 5
    result = fibonacci(x)
    print(result)
```

Run the test:

```bash
comex --lang "python" --code-file tests/data/CFG/test_python.py --graphs "cfg" --debug
```

Check the output:
1. Verify nodes are created correctly
2. Check edge types (sequential, if_true, if_false)
3. Ensure control flow is accurate

## Testing Your Extension

### Unit Tests

Create `tests/test_python.py`:

```python
import pytest
from comex.codeviews.AST.AST_driver import ASTDriver
from comex.codeviews.CFG.CFG_driver import CFGDriver
from comex.codeviews.DFG.DFG_driver import DFGDriver

def test_python_ast():
    code = """
    def hello():
        x = 5
        return x
    """

    driver = ASTDriver(
        src_language="python",
        src_code=code,
        output_file=None,
        properties={}
    )

    graph = driver.graph
    assert graph.number_of_nodes() > 0
    assert graph.number_of_edges() > 0

def test_python_cfg():
    code = """
    def test(x):
        if x > 0:
            return True
        else:
            return False
    """

    driver = CFGDriver(
        src_language="python",
        src_code=code,
        output_file=None,
        properties={}
    )

    graph = driver.graph

    # Check for if-true and if-false edges
    edge_types = [data.get('controlflow_type')
                  for _, _, data in graph.edges(data=True)]
    assert 'if_true' in edge_types
    assert 'if_false' in edge_types
```

Run tests:

```bash
pytest tests/test_python.py -v
```

### Integration Tests

Add to existing test suite:

1. Create test files in `tests/data/CFG/`
2. Add Python files with various control structures
3. Run full test suite:

```bash
pytest tests/test_codeviews.py -v
```

## Best Practices

### 1. Study Existing Implementations

Before implementing, study `java_parser.py` and `CFG_java.py`:
- Understand the pattern
- Reuse common logic
- Follow naming conventions

### 2. Start Simple

Begin with basic constructs:
1. Variable declarations
2. Assignments
3. Simple if statements
4. Simple loops

Add complexity incrementally.

### 3. Use Debug Mode

Enable debug logging to see what's happening:

```bash
comex --lang "python" --code-file test.py --graphs "cfg" --debug
```

### 4. Test Incrementally

Test each feature as you add it:
- Parser extraction
- AST generation
- CFG generation
- Edge connections

### 5. Handle Edge Cases

Consider:
- Nested structures
- Multiple return statements
- Break and continue
- Exception handling
- Lambda functions
- Generators

### 6. Document Language Limitations

Document known limitations in `README.md` or `LIMITATIONS.md`.

Example:
```markdown
### Python
- Lambda functions not fully supported
- Generators may have incomplete data flow
- Decorators are ignored in CFG
```

## Troubleshooting

### Issue: Parser Fails to Load

**Symptom:** Error loading tree-sitter grammar

**Solution:**
1. Check grammar URL is correct
2. Verify commit hash is valid
3. Clear cache: `rm -rf /tmp/comex/`
4. Rebuild: Run comex again

### Issue: No Nodes Generated

**Symptom:** Empty graph or no AST nodes

**Solution:**
1. Check parser is extracting tokens
2. Add debug prints in `create_all_tokens()`
3. Verify node types match tree-sitter output
4. Check `traverse_tree()` logic

### Issue: Incorrect CFG Edges

**Symptom:** Missing or wrong control flow edges

**Solution:**
1. Print CFG node_list and edge_list
2. Verify edge creation logic
3. Check branch handling (if/else)
4. Test with simple examples first

### Issue: Tests Failing

**Symptom:** DeepDiff shows differences

**Solution:**
1. Examine diff output carefully
2. Check node attributes match expected format
3. Verify edge types are consistent
4. Regenerate gold files if implementation is correct

## See Also

- [Architecture Overview](05-architecture.md) - Understanding the design
- [Module Reference](06-module-reference.md) - Detailed file documentation
- [Development Guide](08-development-guide.md) - Contributing process
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
