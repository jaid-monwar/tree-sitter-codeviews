# Complete Execution Flow: `comex --lang "java" --code-file sample/test_java.java --graphs "ast"`

This document provides a detailed trace of every file that gets called when running the above command.

---

## Execution Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: CLI Entry Point                                             │
├─────────────────────────────────────────────────────────────────────┤
│ Command: comex --lang "java" --code-file sample/test_java.java ... │
│                                                                      │
│ ┌──> setup.cfg (entry_points)                                      │
│ │    Defines: comex=comex.cli:app                                  │
│ │                                                                   │
│ └──> src/comex/__main__.py                                         │
│      - Imports: from .cli import app                               │
│      - Calls: app()                                                │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: CLI Initialization                                          │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/cli.py                                              │
│                                                                      │
│ Line 14: get_language_map()  ← Called IMMEDIATELY on import        │
│          └──> src/comex/__init__.py                                │
│               - Clones tree-sitter grammars (if first run)          │
│               - Builds shared library: /tmp/comex/languages.so      │
│               - Returns: {'java': JAVA_LANGUAGE, 'cs': ..., ...}   │
│                                                                      │
│ Line 15: app = typer.Typer()  ← Creates Typer CLI application      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: Command Parsing                                             │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/cli.py                                              │
│ Function: main() (Line 19-120)                                      │
│                                                                      │
│ Line 20: lang = "java"                                              │
│ Line 31: code_file = Path("sample/test_java.java")                 │
│ Line 32: graphs = "ast"                                             │
│ Line 33: output = "dot"                                             │
│ Line 34: blacklisted = ""                                           │
│ Line 35: collapsed = False                                          │
│                                                                      │
│ Lines 59-77: Build codeviews configuration:                         │
│   codeviews = {                                                     │
│     "AST": {"exists": False, ...},                                  │
│     "DFG": {"exists": False, ...},                                  │
│     "CFG": {"exists": False, ...}                                   │
│   }                                                                 │
│                                                                      │
│ Lines 79-85: Since "ast" in graphs:                                 │
│   codeviews["AST"]["exists"] = True                                 │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: File Reading                                                │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/cli.py                                              │
│                                                                      │
│ Lines 101-104: Read source file                                     │
│   file_handle = open("sample/test_java.java", "r")                 │
│   src_code = file_handle.read()                                    │
│   file_handle.close()                                               │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5: CombinedDriver Initialization                               │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/cli.py (Line 105-106)                              │
│                                                                      │
│ CombinedDriver(                                                     │
│   src_language="java",                                              │
│   src_code=<contents of test_java.java>,                           │
│   output_file="output.json",                                        │
│   graph_format="dot",                                               │
│   codeviews={"AST": {"exists": True, ...}, ...}                    │
│ )                                                                   │
│                                                                      │
│ ↓ Calls →                                                           │
│ src/comex/codeviews/combined_graph/combined_driver.py               │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 6: CombinedDriver.__init__()                                   │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/codeviews/combined_graph/combined_driver.py        │
│                                                                      │
│ Line 23: self.graph = nx.MultiDiGraph()  ← Create empty graph      │
│                                                                      │
│ Lines 32-36: Since codeviews["AST"]["exists"] == True:             │
│   self.results["AST"] = ASTDriver(                                  │
│     src_language="java",                                            │
│     src_code=<source>,                                              │
│     output_file="",                                                 │
│     properties={"collapsed": False, "blacklisted": [], ...}         │
│   )                                                                 │
│   self.AST = self.results["AST"].graph                             │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 7: ASTDriver Initialization                                    │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/codeviews/AST/AST_driver.py                        │
│                                                                      │
│ Line 17: self.parser = ParserDriver(src_language, src_code).parser │
│          ↓                                                          │
│          Calls → src/comex/tree_parser/parser_driver.py            │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 8: ParserDriver Initialization                                 │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/tree_parser/parser_driver.py                       │
│                                                                      │
│ Line 11: self.src_code = self.pre_process_src_code(lang, code)    │
│          ↓                                                          │
│          Calls → src/comex/utils/preprocessor.py                   │
│          - remove_empty_lines()                                     │
│          - remove_comments()                                        │
│                                                                      │
│ Lines 13-19: Select language-specific parser                        │
│   parser_map = {                                                    │
│     "java": JavaParser,                                             │
│     "cs": CSParser                                                  │
│   }                                                                 │
│   self.parser = JavaParser("java", preprocessed_code)              │
│                ↓                                                    │
│                Calls → src/comex/tree_parser/java_parser.py        │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 9: JavaParser Initialization                                   │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/tree_parser/java_parser.py                         │
│                                                                      │
│ Line 6: super().__init__(src_language, src_code)                   │
│         ↓                                                           │
│         Calls → src/comex/tree_parser/custom_parser.py             │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 10: CustomParser Initialization                                │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/tree_parser/custom_parser.py                       │
│                                                                      │
│ - Gets language from language_map (from __init__.py)                │
│ - Creates tree-sitter Parser                                        │
│ - Sets language: parser.set_language(JAVA_LANGUAGE)                │
│ - Initializes token tracking data structures:                       │
│   * all_tokens = []                                                 │
│   * label = {}                                                      │
│   * method_map = {}                                                 │
│   * method_calls = {}                                               │
│   * declaration = {}                                                │
│   * symbol_table = {}                                               │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 11: Parse Source Code                                          │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/tree_parser/parser_driver.py                       │
│                                                                      │
│ Line 20: self.root_node, self.tree = self.parser.parse()           │
│          ↓                                                          │
│          Calls → custom_parser.parse()                             │
│          - Converts source to bytes                                 │
│          - tree = parser.parse(bytes(src_code, 'utf8'))            │
│          - Returns: (tree.root_node, tree)                         │
│                                                                      │
│ Result: Parse tree created for test_java.java                       │
│         Root node type: "program"                                   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 12: Token Extraction                                           │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/tree_parser/parser_driver.py                       │
│                                                                      │
│ Lines 21-30: Extract all tokens from parse tree                     │
│   (all_tokens, label, method_map, method_calls,                    │
│    start_line, declaration, declaration_map,                        │
│    symbol_table) = self.create_all_tokens()                        │
│                                                                      │
│   ↓ Calls → java_parser.create_all_tokens()                        │
│              Uses: src/comex/utils/java_nodes.py                   │
│              - Traverses entire parse tree                          │
│              - Identifies variables, methods, declarations          │
│              - Builds symbol table with scopes                      │
│              - Assigns unique index to each node                    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 13: AST Graph Generation                                       │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/codeviews/AST/AST_driver.py                        │
│                                                                      │
│ Lines 19-25: Create AST graph                                       │
│   self.AST = ASTGraph(                                              │
│     src_language="java",                                            │
│     src_code=<source>,                                              │
│     properties={"collapsed": False, ...},                           │
│     root_node=<parse tree root>,                                    │
│     parser=<parser with tokens>                                     │
│   )                                                                 │
│   ↓                                                                 │
│   Calls → src/comex/codeviews/AST/AST.py                           │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 14: ASTGraph.__init__()                                        │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/codeviews/AST/AST.py                               │
│                                                                      │
│ Line 17: self.graph = self.to_networkx()                           │
│          ↓                                                          │
│          - Creates NetworkX DiGraph                                 │
│          - Calls get_AST_nodes() recursively                        │
│          - For each named node in parse tree:                       │
│            * Adds node with attributes (type, label, style)         │
│            * Adds edges from parent to children                     │
│          - Applies blacklisting (if configured)                     │
│          - Applies collapsing (if configured)                       │
│                                                                      │
│ Result: Complete AST as NetworkX DiGraph                            │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 15: Return to CombinedDriver                                   │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/codeviews/combined_graph/combined_driver.py        │
│                                                                      │
│ Line 36: self.AST = self.results["AST"].graph                      │
│          ← AST graph stored in CombinedDriver                       │
│                                                                      │
│ Line 44: self.combine()                                             │
│          ↓                                                          │
│          Calls combine() method (Line 161-216)                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 16: Combine Graphs                                             │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/codeviews/combined_graph/combined_driver.py        │
│ Method: combine() (Line 161-216)                                    │
│                                                                      │
│ Since only AST exists (not DFG or CFG):                             │
│   Line 202-206: elif self.codeviews["AST"]["exists"] == True:      │
│                   self.AST_simple()                                 │
│                                                                      │
│   ↓ Calls AST_simple() (Line 62-68)                                │
│   Line 63: self.graph = self.AST                                    │
│            ← Combined graph = AST graph                             │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 17: Write Output Files                                         │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/codeviews/combined_graph/combined_driver.py        │
│                                                                      │
│ Lines 45-53: Since output_file is provided:                         │
│   if graph_format == "dot":  ← In our case                         │
│     postprocessor.write_to_dot(                                     │
│       self.graph,                                                   │
│       "output.dot",                                                 │
│       output_png=True                                               │
│     )                                                               │
│     ↓                                                               │
│     Calls → src/comex/utils/postprocessor.py                       │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 18: Postprocessor - DOT Generation                             │
├─────────────────────────────────────────────────────────────────────┤
│ File: src/comex/utils/postprocessor.py                             │
│ Function: write_to_dot() (Line 30-41)                              │
│                                                                      │
│ Line 32-36: Write DOT file                                          │
│   - Deep copies graph                                               │
│   - Escapes special characters in labels                            │
│   - nx.nx_pydot.write_dot(graph, "output.dot")                     │
│   - Writes: output.dot                                              │
│                                                                      │
│ Lines 37-40: Generate PNG (since output_png=True)                   │
│   check_call(["dot", "-Tpng", "output.dot", "-o", "output.png"])  │
│   - Uses GraphViz 'dot' command                                     │
│   - Writes: output.png                                              │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 19: Complete - Output Files Generated                          │
├─────────────────────────────────────────────────────────────────────┤
│ Files Created:                                                       │
│   ✓ output.dot  - GraphViz DOT format                              │
│   ✓ output.png  - Rendered visualization                           │
│                                                                      │
│ Graph Contents:                                                      │
│   - All nodes from Java source code AST                             │
│   - Hierarchical structure preserved                                │
│   - Node attributes: type, label, style, color                      │
│   - Edges representing parent-child relationships                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## File Call Order Summary

### 1. **Entry Points**
1. `setup.cfg` - Entry point configuration
2. `src/comex/__main__.py` - Module execution
3. `src/comex/cli.py` - CLI interface

### 2. **Initialization Phase**
4. `src/comex/__init__.py` - Language map initialization
   - Clones tree-sitter grammars
   - Builds shared library

### 3. **Parsing Phase**
5. `src/comex/codeviews/combined_graph/combined_driver.py` - Orchestrates everything
6. `src/comex/codeviews/AST/AST_driver.py` - AST driver
7. `src/comex/tree_parser/parser_driver.py` - Parser orchestration
8. `src/comex/utils/preprocessor.py` - Code preprocessing
9. `src/comex/tree_parser/java_parser.py` - Java-specific parsing
10. `src/comex/tree_parser/custom_parser.py` - Base parser functionality
11. `src/comex/utils/java_nodes.py` - Java node type definitions

### 4. **Graph Generation Phase**
12. `src/comex/codeviews/AST/AST.py` - AST graph construction

### 5. **Output Phase**
13. `src/comex/utils/postprocessor.py` - Output file generation
14. External: GraphViz `dot` command - PNG rendering

---

## Key Data Structures

### Parse Tree (from tree-sitter)
```
Node {
  type: "program",
  start_point: (line, column),
  end_point: (line, column),
  children: [Node, Node, ...],
  is_named: boolean
}
```

### AST Graph (NetworkX DiGraph)
```
Nodes: {
  node_id: {
    "node_type": "class_declaration",
    "label": "test_java",
    "shape": "box",
    "style": "rounded, filled",
    "fillcolor": "#BFE6D3"
  },
  ...
}

Edges: [(parent_id, child_id), ...]
```

### Codeviews Configuration
```python
{
  "AST": {
    "exists": True,
    "collapsed": False,
    "minimized": False,
    "blacklisted": []
  },
  "DFG": {"exists": False, ...},
  "CFG": {"exists": False, ...}
}
```

---

## Important Notes

1. **Language Map Initialization**: Called ONCE on CLI import, not per command
2. **Tree-sitter Grammars**: Cloned to `/tmp/comex/` on first run only
3. **Parser Selection**: Based on `src_language` parameter, routed to JavaParser
4. **AST Only**: Since only "ast" was requested, DFG and CFG drivers are NOT called
5. **Output Format**: "dot" generates both `.dot` and `.png` files
6. **Graph Type**: AST uses regular DiGraph, Combined uses MultiDiGraph

This is the complete execution flow for the command!
