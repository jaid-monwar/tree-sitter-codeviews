# Comex Documentation

Welcome to the comprehensive documentation for **Comex** (Tree Sitter Multi Codeview Generator) - a Python package for generating combined multi-code view graphs from source code.

## Table of Contents

### Getting Started
- [**Installation & Quick Start**](01-getting-started.md) - Install Comex and run your first codeview generation
- [**CLI Reference**](02-cli-reference.md) - Complete command-line interface documentation
- [**Python API Guide**](03-python-api.md) - Using Comex as a Python package

### Core Concepts
- [**Codeview Types**](04-codeview-types.md) - Understanding AST, CFG, DFG, and combined graphs
- [**Architecture Overview**](05-architecture.md) - High-level design and component interaction
- [**Module Reference**](06-module-reference.md) - Detailed file-by-file documentation

### Advanced Topics
- [**Extending Comex**](07-extending-comex.md) - Adding support for new programming languages
- [**Development Guide**](08-development-guide.md) - Contributing, testing, and debugging
- [**Configuration Guide**](09-configuration-guide.md) - Advanced configuration options and customization

### Reference
- [**Troubleshooting & FAQ**](10-troubleshooting.md) - Common issues and solutions
- [**API Reference**](11-api-reference.md) - Complete API documentation
- [**Examples**](12-examples.md) - Real-world usage examples and patterns

## What is Comex?

Comex is a powerful tool for generating structured representations of source code. It parses Java and C# code to create various graph-based representations:

- **Abstract Syntax Trees (AST)** - Hierarchical representation of code structure
- **Control Flow Graphs (CFG)** - Execution flow and branching logic
- **Data Flow Graphs (DFG)** - Variable definitions and usage patterns
- **Combined Graphs** - Multiple representations merged into a single graph

These codeviews are essential for:
- Machine learning models for code
- Program analysis and understanding
- Code clone detection
- Code translation and transformation
- Software engineering research

## Quick Links

- [GitHub Repository](https://github.com/IBM/tree-sitter-codeviews)
- [PyPI Package](https://pypi.org/project/comex/)
- [Research Paper (ASE 2023)](https://arxiv.org/abs/2307.04693)
- [CodeSAM Framework](https://arxiv.org/abs/2411.14611)

## Key Features

✅ **Multi-language Support** - Java and C# with extensible architecture for more languages
✅ **Multiple Codeviews** - 15+ combinations of AST, CFG, DFG, CST, and SDFG
✅ **Flexible Output** - JSON and DOT formats with PNG visualization
✅ **CLI & API** - Use as command-line tool or Python package
✅ **Customizable** - Configure node collapsing, blacklisting, and more
✅ **Tree-sitter Based** - Fast, incremental parsing with 40+ language support potential

## Getting Help

- **Issues**: Report bugs or request features on [GitHub Issues](https://github.com/IBM/tree-sitter-codeviews/issues)
- **Documentation**: Browse this documentation for detailed guides
- **Contributing**: See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines

## Research & Citations

If you use Comex in your research, please cite:

```bibtex
@inproceedings{das2023comex,
  title={COMEX: A Tool for Generating Customized Source Code Representations},
  author={Das, Debeshee and Mathews, Noble Saji and Mathai, Alex and Tamilselvam, Srikanth and Sedamaki, Kranthi and Chimalakonda, Sridhar and Kumar, Atul},
  booktitle={2023 38th IEEE/ACM International Conference on Automated Software Engineering (ASE)},
  pages={2054--2057},
  year={2023},
  organization={IEEE}
}
```

## License

Apache License 2.0 - See [LICENSE](../LICENSE) file for details.

---

**Next Steps**: Start with the [Getting Started Guide](01-getting-started.md) to install Comex and generate your first codeview!
