# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Comex** (Tree Sitter Multi Codeview Generator) is a Python package that generates combined multi-code view graphs (AST, CFG, DFG, and combinations) for Java and C# source code. It uses [tree-sitter](https://tree-sitter.github.io/tree-sitter/) for parsing and NetworkX for graph generation. The tool can be used both as a CLI and as a Python package.

### Supported Languages
- Java
- C# (cs)

### Supported Codeviews
- **AST** (Abstract Syntax Tree)
- **CFG** (Control Flow Graph)
- **DFG** (Data Flow Graph)
- **CST** (Concrete Syntax Tree)
- **SDFG** (Statement-level Data Flow Graph)
- **Combined graphs** (any combination of the above)

See [List_Of_Views.pdf](List_Of_Views.pdf) for all 15+ possible combinations.

## Development Setup

### Installation for Development
```bash
pip install -r requirements-dev.txt
```

This performs an editable install, making `comex` available throughout your environment while reflecting code changes without reinstallation.

### Dependencies
- Python >= 3.8 (3.12+ requires setuptools>=69.0, automatically installed)
- **GraphViz** (`dot` command) must be installed separately on your system for PNG/DOT graph visualization
  - Only needed if using `--output "dot"` or `--output "all"`
  - JSON output works without GraphViz
  - Install: `apt install graphviz` (Ubuntu) or `brew install graphviz` (macOS)
- Key packages: networkx==2.6.3, tree-sitter==0.20.1, typer==0.4.1, pydot==1.4.1

### First-time Setup
On first run, comex automatically clones and builds tree-sitter grammars for Java and C# into a temporary directory (`/tmp/comex/`). This is handled by [src/comex/__init__.py](src/comex/__init__.py) in the `get_language_map()` function.

**Note**: If you see "Intial Setup: First time running COMEX" messages, this is normal - the grammars are being downloaded and compiled. This only happens once per system.

## Testing

### Run all tests with coverage
```bash
pytest
```

### Run specific test
```bash
pytest -k 'test_cfg[cs-test7]' --no-cov
```

### View detailed diff output
```bash
pytest -k 'test_cfg[cs-test7]' --no-cov -vv
```

### Test Organization
Tests are dynamically discovered via `pytest_generate_tests()` in [tests/test_codeviews.py](tests/test_codeviews.py):
- Scans `tests/data/{AST,CFG,SDFG,COMBINED}` for `.java` and `.cs` files
- Each test file `testN.{java|cs}` should have a corresponding `testN/testN-gold.json` reference output
- If gold file doesn't exist, it's auto-generated from first run (then test will fail, requiring re-run)
- Tests use `deepdiff` to compare generated JSON against gold files with `ignore_order=True`
- COMBINED tests also require a `testN-config.json` specifying which codeviews to combine
- Test categories: AST, CFG, SDFG, COMBINED

### Adding New Tests
To add a new test case:
1. Create source file: `tests/data/{AST|CFG|SDFG|COMBINED}/testN.{java|cs}`
2. For COMBINED tests, also create `testN-config.json` with codeview configuration
3. Run test once to generate gold file: `pytest -k 'test_cfg[java-testN]' --no-cov`
4. Inspect generated `testN/testN-gold.json` to verify correctness
5. Run test again - it should now pass

## CLI Usage

The CLI can be invoked as `comex` (after pip install) or `python -m comex` (for development).

### Basic Command Structure
```bash
comex --lang <language> --code-file <file> --graphs <graphs> [options]
```

### Examples
```bash
# Generate CFG + DFG for Java
comex --lang "java" --code-file ./test.java --graphs "cfg,dfg"

# Generate AST with collapsed nodes and custom blacklist
comex --lang "cs" --code-file ./test.cs --graphs "ast" --collapsed --blacklisted "import_declaration,package_declaration"

# Generate all three graphs with JSON output
comex --lang "java" --code-file ./example.java --graphs "ast,cfg,dfg" --output "json"
```

### Available CLI Options
- `--lang`: Language (required: "java" or "cs")
- `--code-file`: Path to source file
- `--graphs`: Comma-separated list of graphs (ast, cfg, dfg)
- `--output`: Output format ("dot", "json", or "all")
- `--collapsed`: Collapse duplicate variable nodes
- `--blacklisted`: Comma-separated list of node types to exclude from AST
- `--last-def`: Add last definition information to DFG
- `--last-use`: Add last use information to DFG
- `--debug`: Enable debug logging

## Package Usage

```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver

codeviews = {
    "AST": {"exists": True, "collapsed": False, "minimized": False, "blacklisted": []},
    "CFG": {"exists": True},
    "DFG": {"exists": True, "collapsed": False, "minimized": False, "statements": True, "last_def": False, "last_use": False}
}

driver = CombinedDriver(
    src_language="java",
    src_code=source_code,
    output_file="output.json",
    graph_format="all",  # "dot", "json", or "all"
    codeviews=codeviews
)

# Access the generated graph
graph = driver.get_graph()
```

## Architecture Overview

### High-Level Flow
1. **Parsing Layer** ([tree_parser/](src/comex/tree_parser/)): Tree-sitter-based parsing with language-specific extensions
2. **Codeview Generation** ([codeviews/](src/comex/codeviews/)): Each codeview has a driver and implementation class
3. **Combination** ([combined_graph/combined_driver.py](src/comex/codeviews/combined_graph/combined_driver.py)):
   - Merges multiple codeviews into a single NetworkX MultiDiGraph
   - Each edge type (AST, CFG, DFG, etc.) becomes a separate edge in the multigraph
   - Nodes are merged by ID, with attributes combined from all codeviews
4. **Output** ([utils/postprocessor.py](src/comex/utils/postprocessor.py)): Exports to JSON or DOT (with PNG via GraphViz)

### Key Components

#### Parsing Layer (`src/comex/tree_parser/`)
- **[parser_driver.py](src/comex/tree_parser/parser_driver.py)**: Central driver that routes to language-specific parsers
- **[java_parser.py](src/comex/tree_parser/java_parser.py)**: Java-specific tree-sitter wrapper
- **[cs_parser.py](src/comex/tree_parser/cs_parser.py)**: C#-specific tree-sitter wrapper
- **[custom_parser.py](src/comex/tree_parser/custom_parser.py)**: Base parser class with common functionality

All parsers:
- Preprocess code (remove comments, empty lines via [utils/preprocessor.py](src/comex/utils/preprocessor.py))
- Build symbol tables
- Extract method maps and declarations
- Generate token lists for codeview construction

#### Codeview Generation (`src/comex/codeviews/`)
Each codeview directory contains:
- **Driver class**: Entry point that initializes the parser and calls the codeview class
- **Codeview class**: Core logic, often with language-specific subclasses

Structure:
- `AST/`: Abstract Syntax Tree generation
- `CFG/`: Control Flow Graph generation (has language-specific implementations: `CFG_java.py`, `CFG_csharp.py`)
- `DFG/`: Data Flow Graph generation
- `SDFG/`: Statement-level DFG with Reaching Definitions Analysis (RDA)
- `CST/`: Concrete Syntax Tree generation
- `combined_graph/`: Combines multiple codeviews into a single graph

#### Language-Specific Node Definitions (`src/comex/utils/`)
- **[java_nodes.py](src/comex/utils/java_nodes.py)**: Java AST node type definitions and mappings
- **[cs_nodes.py](src/comex/utils/cs_nodes.py)**: C# AST node type definitions and mappings
- **[DFG_utils.py](src/comex/utils/DFG_utils.py)**: Helper functions for DFG generation

#### CLI Entry Point
- **[cli.py](src/comex/cli.py)**: Typer-based CLI that parses arguments and invokes `CombinedDriver`
  - Registered as `comex` console script in [setup.cfg](setup.cfg)
- **[__main__.py](src/comex/__main__.py)**: Enables `python -m comex` invocation for development

### Extension Pattern for New Languages
1. Add tree-sitter grammar URL and commit to `src/comex/__init__.py:grammar_repos`
2. Create language-specific parser in `src/comex/tree_parser/<lang>_parser.py`
3. Add parser to `parser_driver.py:parser_map`
4. Create node definitions in `src/comex/utils/<lang>_nodes.py`
5. Add language-specific CFG/SDFG implementations in respective codeview directories if needed

## Publishing to PyPI

1. Bump version in [setup.cfg](setup.cfg)
2. Build distributions:
   ```bash
   rm -rf build dist
   python setup.py sdist bdist_wheel
   ```
3. Upload to PyPI:
   ```bash
   twine upload dist/*
   ```

## Known Limitations

### Java
- No inter-file analysis support
- Input code must be free of syntax errors (supports non-compileable but syntactically valid code)
- Limited support for nested function calls as arguments

### C#
- All Java limitations apply
- No support for lambda functions and arrow expressions
- No support for compiler directives (e.g., `#pragma`)
- Incomplete operator declaration support
- Limited inheritance and abstraction support

## Continuous Integration
CI runs automatically on push/PR to main and development branches via [.github/workflows/CI.yml](.github/workflows/CI.yml). Tests run on Python 3.8 with full coverage reporting.
