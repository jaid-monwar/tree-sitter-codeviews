# Development Guide

Guide for contributing to Comex development.

## Table of Contents

- [Development Setup](#development-setup)
- [Testing](#testing)
- [Code Style](#code-style)
- [Contributing Workflow](#contributing-workflow)
- [Publishing](#publishing)

## Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/IBM/tree-sitter-codeviews.git
cd tree-sitter-codeviews
```

### 2. Create Virtual Environment

```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using conda
conda create -n comex python=3.8
conda activate comex
```

### 3. Install Development Dependencies

```bash
pip install -r requirements-dev.txt
```

This installs Comex in editable mode (`-e`) plus development tools:
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `tqdm`, `pqdm` - Progress bars for batch processing
- `loguru` - Logging
- `GitPython` - Git operations
- `pandas` - Data analysis

### 4. Verify Installation

```bash
comex --help
pytest --version
```

## Testing

### Running Tests

#### All Tests with Coverage

```bash
pytest
```

Output shows:
- Number of tests passed/failed
- Coverage percentage
- Missing lines

#### Specific Test

```bash
# Run single test
pytest -k 'test_cfg[java-test1]'

# Run all CFG tests
pytest -k 'test_cfg'

# Run all Java tests
pytest -k 'java'
```

#### Verbose Output

```bash
# Show test names
pytest -v

# Show detailed differences
pytest -vv

# Without coverage report
pytest --no-cov
```

#### Analyze Differences

When tests fail, use verbose mode to see DeepDiff output:

```bash
pytest -k 'test_cfg[cs-test7]' --no-cov -vv
```

This shows exactly what differs between gold and generated output.

### Writing Tests

#### Test Structure

Tests are in `tests/test_codeviews.py` and use dynamic test generation:

```python
def test_ast(extension, test_folder, test_name):
    driver = ASTDriver(
        src_language=extension,
        src_code=src_code,
        output_file=saving_path,
        properties={}
    )
    # Compare with gold file
    assert ddiff == {}
```

#### Adding Test Cases

1. **Create test file**:
   ```bash
   # For AST test
   echo 'public class Test { int x = 5; }' > tests/data/AST/test_new.java
   ```

2. **Run test** (will create gold file on first run):
   ```bash
   pytest -k 'test_ast[java-test_new]'
   ```

3. **Verify gold file**:
   ```bash
   cat tests/data/AST/test_new/test_new-gold.json
   ```

4. **Re-run to verify**:
   ```bash
   pytest -k 'test_ast[java-test_new]'
   ```

#### Test Data Organization

```
tests/data/
├── AST/
│   ├── test1.java
│   ├── test1/test1-gold.json
│   ├── test2.cs
│   └── test2/test2-gold.json
├── CFG/
├── SDFG/
└── COMBINED/
    ├── test1.java
    ├── test1-config.json  # Configuration for combined tests
    └── test1/test1-gold.json
```

#### Combined Test Configuration

For combined tests, create a config file:

```json
{
  "combined_views": {
    "AST": {
      "exists": true,
      "collapsed": false,
      "minimized": false,
      "blacklisted": []
    },
    "CFG": {
      "exists": true
    },
    "DFG": {
      "exists": true,
      "collapsed": false,
      "minimized": false,
      "statements": true,
      "last_def": false,
      "last_use": false
    }
  }
}
```

### Continuous Integration

Tests run automatically on GitHub Actions for:
- Push to `main` or `development` branches
- Pull requests

Configuration: `.github/workflows/CI.yml`

```yaml
- name: Install Dependencies and Run Tests
  run: |
    pip install -r requirements-dev.txt
    pytest --cov=src \
           --capture=tee-sys \
           --cov-report=term-missing:skip-covered \
           tests
```

## Code Style

### Python Style Guide

Follow PEP 8 with these conventions:

#### Naming

- **Modules**: lowercase with underscores (`ast_driver.py`)
- **Classes**: PascalCase (`ASTDriver`, `CFGGraph_java`)
- **Functions**: lowercase with underscores (`create_all_tokens`)
- **Constants**: UPPERCASE (`JAVA_LANGUAGE`)
- **Private**: prefix with underscore (`_internal_method`)

#### Imports

Order imports as:
1. Standard library
2. Third-party (networkx, tree-sitter, etc.)
3. Local imports (relative imports)

```python
import os
import tempfile

import networkx as nx
from tree_sitter import Language

from .AST import ASTGraph
from ..utils import postprocessor
```

#### Docstrings

Use docstrings for classes and public methods:

```python
def create_node(self, label, line, type_label):
    """Create a CFG node.

    Args:
        label: Node label (code snippet)
        line: Line number
        type_label: Node type identifier

    Returns:
        Node ID (integer)
    """
    node_id = len(self.node_list)
    self.node_list.append((node_id, line, label, type_label))
    return node_id
```

### Code Formatting

#### Recommended Tools

```bash
# Install formatters
pip install black isort flake8

# Format code
black src/
isort src/

# Check style
flake8 src/
```

### Comments

- Use comments to explain **why**, not **what**
- Document complex algorithms
- Mark TODO/FIXME for incomplete code

```python
# Good comment
# Use RDA to track which definitions reach each use point
result = compute_reaching_definitions()

# Bad comment
# Create variable x
x = 5
```

## Contributing Workflow

### 1. Fork and Clone

```bash
# Fork on GitHub, then clone
git clone https://github.com/YOUR_USERNAME/tree-sitter-codeviews.git
cd tree-sitter-codeviews
```

### 2. Create Branch

```bash
git checkout -b feature/add-python-support
```

Branch naming:
- `feature/` - New features
- `bugfix/` - Bug fixes
- `docs/` - Documentation
- `refactor/` - Code refactoring

### 3. Make Changes

- Write code
- Add tests
- Update documentation

### 4. Test Your Changes

```bash
# Run tests
pytest

# Run specific tests
pytest -k 'test_cfg'

# Check coverage
pytest --cov=src --cov-report=html
# View coverage report in htmlcov/index.html
```

### 5. Commit

```bash
git add .
git commit -m "Add Python language support

- Implement PythonParser for token extraction
- Add CFGGraph_python for control flow
- Add test cases for Python
- Update documentation
"
```

Commit message format:
- First line: Short summary (50 chars max)
- Blank line
- Detailed description (wrap at 72 chars)

### 6. Push and Create PR

```bash
git push origin feature/add-python-support
```

Then create Pull Request on GitHub.

### Pull Request Guidelines

**PR Title:** Clear and descriptive

**PR Description:**
```markdown
## Description
Brief description of changes

## Changes
- Item 1
- Item 2

## Testing
- [ ] All tests pass
- [ ] Added new tests
- [ ] Manual testing performed

## Documentation
- [ ] Updated relevant docs
- [ ] Added examples if applicable
```

**Before submitting:**
- [ ] Tests pass locally
- [ ] Code follows style guide
- [ ] Documentation updated
- [ ] No merge conflicts

### Code Review Process

1. Maintainers review PR
2. Address feedback
3. Make requested changes
4. Update PR (push to same branch)
5. Approval and merge

## Publishing

### Version Bump

Edit `setup.cfg`:

```ini
[metadata]
name = comex
version = 0.1.5  # Increment version
```

Versioning scheme (Semantic Versioning):
- `0.1.5` → `0.1.6` - Patch (bug fixes)
- `0.1.5` → `0.2.0` - Minor (new features)
- `0.1.5` → `1.0.0` - Major (breaking changes)

### Build Distribution

```bash
# Clean previous builds
rm -rf build dist

# Build source distribution and wheel
python setup.py sdist bdist_wheel
```

Creates:
- `dist/comex-0.1.5.tar.gz` - Source distribution
- `dist/comex-0.1.5-py3-none-any.whl` - Wheel

### Upload to PyPI

```bash
# Install twine if not installed
pip install twine

# Upload to PyPI
twine upload dist/*
```

You'll be prompted for PyPI credentials.

### Test Upload (Optional)

Upload to TestPyPI first to verify:

```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ comex
```

### Verify Release

```bash
pip install comex==0.1.5
comex --help
```

### Tag Release

```bash
git tag v0.1.5
git push origin v0.1.5
```

### GitHub Release

1. Go to GitHub repository
2. Click "Releases" → "Create a new release"
3. Select tag `v0.1.5`
4. Add release notes
5. Attach distribution files (optional)
6. Publish release

## Development Tips

### Debug Mode

Use debug logging to understand flow:

```bash
comex --lang "java" --code-file test.java --graphs "cfg" --debug
```

Or in code:

```python
from loguru import logger
logger.debug("Processing node: {}", node.type)
```

### Interactive Development

Use IPython or Jupyter for exploration:

```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver

code = "public class Test { int x = 5; }"
driver = CombinedDriver(
    src_language="java",
    src_code=code,
    output_file=None,
    graph_format="json",
    codeviews={...}
)

# Explore graph
graph = driver.get_graph()
list(graph.nodes(data=True))
list(graph.edges(data=True))
```

### Profiling

For performance analysis:

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here
driver = CombinedDriver(...)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

### Memory Profiling

```bash
pip install memory_profiler

# Add @profile decorator to functions
python -m memory_profiler script.py
```

## Resources

- [Contributing Guidelines](../CONTRIBUTING.md)
- [Code of Conduct](../CODE_OF_CONDUCT.md)
- [Architecture Overview](05-architecture.md)
- [GitHub Repository](https://github.com/IBM/tree-sitter-codeviews)

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/IBM/tree-sitter-codeviews/issues)
- **Discussions**: Create issue with "question" label
- **Security**: See [SECURITY.md](../SECURITY.md)
