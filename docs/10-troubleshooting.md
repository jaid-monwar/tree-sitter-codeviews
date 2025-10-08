# Troubleshooting & FAQ

Common issues, solutions, and frequently asked questions.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Runtime Errors](#runtime-errors)
- [Output Issues](#output-issues)
- [Performance Issues](#performance-issues)
- [FAQ](#faq)

## Installation Issues

### GraphViz Not Found

**Symptom:**
```
Error: dot command not found
FileNotFoundError: [Errno 2] No such file or directory: 'dot'
```

**Solution:**

Install GraphViz:

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install graphviz
```

**Linux (CentOS/RHEL):**
```bash
sudo yum install graphviz
```

**macOS:**
```bash
brew install graphviz
```

**Windows:**
1. Download installer from [graphviz.org](https://graphviz.org/download/)
2. Install and add to PATH
3. Restart terminal

**Verify installation:**
```bash
dot -V
```

**Workaround:** Use JSON output only
```bash
comex --lang "java" --code-file test.java --graphs "ast" --output "json"
```

---

### Python Version Error

**Symptom:**
```
ERROR: Package requires Python >=3.8
```

**Solution:**

Check Python version:
```bash
python --version
```

Upgrade Python:
- Download from [python.org](https://www.python.org/downloads/)
- Or use pyenv: `pyenv install 3.8`

Use virtual environment with correct version:
```bash
python3.8 -m venv venv
source venv/bin/activate
pip install comex
```

---

### Tree-sitter Build Fails

**Symptom:**
```
Error building tree-sitter grammar
git clone failed
```

**Causes:**
1. No internet connection
2. Git not installed
3. Firewall blocking GitHub

**Solution:**

**1. Check internet:**
```bash
ping github.com
```

**2. Install git:**
```bash
# Linux
sudo apt-get install git

# macOS
brew install git

# Windows
# Download from git-scm.com
```

**3. Clear cache and retry:**
```bash
rm -rf /tmp/comex/
comex --lang "java" --code-file test.java --graphs "ast"
```

---

### Permission Denied (Temp Directory)

**Symptom:**
```
PermissionError: [Errno 13] Permission denied: '/tmp/comex/'
```

**Solution:**

**1. Check permissions:**
```bash
ls -ld /tmp/comex/
```

**2. Fix permissions:**
```bash
sudo chmod 755 /tmp/comex/
```

**3. Or use different temp directory:**

Edit `src/comex/__init__.py`:
```python
clone_directory = os.path.join(os.path.expanduser("~"), ".comex")
```

---

## Runtime Errors

### "No code provided"

**Symptom:**
```
Exception: No code provided
```

**Cause:** Neither `--code` nor `--code-file` specified.

**Solution:**

Provide code via file:
```bash
comex --lang "java" --code-file test.java --graphs "ast"
```

Or inline:
```bash
comex --lang "java" --code "public class Test {}" --graphs "ast"
```

---

### Parsing Errors

**Symptom:**
```
Tree-sitter parsing failed
Unexpected token at line X
```

**Cause:** Syntax errors in source code.

**Solution:**

**1. Check syntax:**
Ensure code is syntactically valid (can have logical errors, but not syntax errors).

**2. Use debug mode:**
```bash
comex --lang "java" --code-file test.java --graphs "ast" --debug
```

**3. Simplify code:**
Test with minimal example to isolate issue.

**4. Check language:**
Ensure `--lang` matches file type:
- `.java` → `--lang "java"`
- `.cs` → `--lang "cs"`

---

### Empty Graph Generated

**Symptom:**
Graph has 0 nodes or very few nodes.

**Causes:**
1. Parser not extracting tokens
2. Blacklist too aggressive
3. Code has no executable statements

**Solution:**

**1. Check without blacklist:**
```bash
comex --lang "java" --code-file test.java --graphs "ast"
```

**2. Use debug mode:**
```bash
comex --lang "java" --code-file test.java --graphs "ast" --debug
```

**3. Verify code content:**
```bash
cat test.java
```

**4. Test with simple example:**
```java
public class Test {
    public static void main(String[] args) {
        int x = 5;
    }
}
```

---

### "Language not supported"

**Symptom:**
```
KeyError: 'python'
Language python not supported
```

**Cause:** Language not added to Comex.

**Solution:**

Currently supported: Java and C#.

For other languages:
- Check [Extending Comex](07-extending-comex.md)
- Request feature on [GitHub Issues](https://github.com/IBM/tree-sitter-codeviews/issues)

---

### Memory Error (Large Files)

**Symptom:**
```
MemoryError
Killed (signal 9)
```

**Cause:** File too large, graph exceeds memory.

**Solution:**

**1. Use collapsed mode:**
```bash
comex --lang "java" --code-file large.java --graphs "dfg" --collapsed
```

**2. Disable unused codeviews:**
```bash
# Instead of all three
comex --lang "java" --code-file large.java --graphs "cfg"
```

**3. Process method-level instead of file-level:**
Split file into smaller methods.

**4. Increase memory:**
```bash
export JAVA_TOOL_OPTIONS="-Xmx4g"
python -m comex ...
```

---

## Output Issues

### PNG Not Generated

**Symptom:**
Only `.dot` file created, no `.png`.

**Causes:**
1. GraphViz not installed
2. `output_png=False` in code
3. Dot command failed

**Solution:**

**1. Check GraphViz:**
```bash
dot -V
```

**2. Manually generate PNG:**
```bash
dot -Tpng output.dot -o output.png
```

**3. Check error messages:**
```bash
comex --lang "java" --code-file test.java --graphs "ast" --debug
```

---

### JSON Format Issues

**Symptom:**
Can't load JSON output.

**Cause:** Malformed JSON.

**Solution:**

**1. Validate JSON:**
```bash
python -m json.tool output.json
```

**2. Check for special characters:**
Node labels may contain characters that need escaping.

**3. Use Python to load:**
```python
import json
with open("output.json") as f:
    data = json.load(f)
```

---

### Graph Looks Wrong

**Symptom:**
Visualization doesn't match expected structure.

**Solutions:**

**1. Verify with JSON:**
Inspect raw graph data:
```python
import json
with open("output.json") as f:
    data = json.load(f)
    print(json.dumps(data, indent=2))
```

**2. Check edge types:**
Ensure correct edges are created:
```python
edges = [link for link in data['links']]
for edge in edges:
    print(f"{edge['source']} -> {edge['target']}: {edge.get('edge_type')}")
```

**3. Use debug mode:**
See graph construction process:
```bash
comex --lang "java" --code-file test.java --graphs "cfg" --debug
```

---

## Performance Issues

### Slow First Run

**Symptom:**
First run takes 30+ seconds.

**Cause:** Downloading and building tree-sitter grammars.

**Solution:**

This is normal. Subsequent runs are fast (< 1 second).

**Progress:**
```
Intial Setup: First time running COMEX on tree-sitter-java
Intial Setup: First time running COMEX on tree-sitter-c-sharp
```

Wait for completion. This happens only once.

---

### Slow Processing of Large Files

**Symptom:**
Files > 1000 lines take very long.

**Solutions:**

**1. Disable unused codeviews:**
```python
codeviews = {
    "AST": {"exists": False},
    "CFG": {"exists": True},  # Only what's needed
    "DFG": {"exists": False}
}
```

**2. Use collapsed mode:**
```python
codeviews = {
    "DFG": {
        "exists": True,
        "collapsed": True,
        ...
    }
}
```

**3. Skip file output:**
```python
driver = CombinedDriver(..., output_file=None)
```

**4. Process in parallel:**
```python
from multiprocessing import Pool

def process_file(path):
    driver = CombinedDriver(...)
    return driver.get_graph()

with Pool(4) as pool:
    results = pool.map(process_file, file_paths)
```

---

## FAQ

### Q: Which languages are supported?

**A:** Currently Java and C#. Python, Ruby, Go, and others can be added (see [Extending Comex](07-extending-comex.md)).

---

### Q: Can Comex handle syntax errors?

**A:** No. Code must be syntactically correct (but doesn't need to compile). Comex can handle logical errors and incomplete implementations.

---

### Q: What's the difference between AST and CST?

**A:**
- **CST** (Concrete Syntax Tree): Includes all syntax tokens (semicolons, braces, etc.)
- **AST** (Abstract Syntax Tree): Abstracts away syntax, keeps semantic structure

Comex generates AST. Tree-sitter produces CST internally.

---

### Q: Can I combine more than 3 codeviews?

**A:** Currently, Comex supports AST, CFG, and DFG. You can combine any subset of these three.

---

### Q: How do I visualize large graphs?

**A:**
1. Use collapsed mode to reduce size
2. Use graph visualization tools like Gephi
3. Export to JSON and use custom visualization
4. Filter nodes programmatically before visualization

---

### Q: Can I use Comex for non-OOP languages?

**A:** Yes, as long as tree-sitter supports the language. Comex works with procedural languages too.

---

### Q: Is Comex suitable for production code analysis?

**A:** Yes, but:
- Ensure input code is syntactically valid
- Handle exceptions in production
- Consider memory limits for very large files
- Test thoroughly with your codebase

---

### Q: How accurate is the CFG?

**A:** Very accurate for standard control flow. Limitations:
- Java: Nested function calls as arguments
- C#: Lambda functions, compiler directives
- See README for full list

---

### Q: Can I modify generated graphs?

**A:** Yes! Graphs are NetworkX objects:

```python
driver = CombinedDriver(...)
graph = driver.get_graph()

# Add custom nodes
graph.add_node(999, label="Custom", type="custom")

# Add custom edges
graph.add_edge(123, 999, edge_type="custom")

# Remove nodes
graph.remove_node(456)

# Filter nodes
nodes_to_remove = [n for n, d in graph.nodes(data=True)
                   if d.get('node_type') == 'unwanted']
graph.remove_nodes_from(nodes_to_remove)
```

---

### Q: What's the maximum file size Comex can handle?

**A:** Depends on available memory:
- Typical: 10,000+ lines
- With collapsed mode: 50,000+ lines
- Memory limit is main constraint

For larger files, split into methods or classes.

---

### Q: Can I use Comex in Jupyter notebooks?

**A:** Yes! See [Python API Guide](03-python-api.md#jupyter-notebook).

---

### Q: How do I cite Comex in research?

**A:** Use the BibTeX entry from README:

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

---

### Q: Is Comex suitable for real-time applications?

**A:** For small files (<500 lines), yes. Processing is fast (~100ms). For larger files or all three codeviews, consider caching or pre-processing.

---

### Q: Can I run Comex in Docker?

**A:** Yes:

```dockerfile
FROM python:3.8

RUN apt-get update && apt-get install -y graphviz git
RUN pip install comex

WORKDIR /app
COPY code.java .

CMD ["comex", "--lang", "java", "--code-file", "code.java", "--graphs", "ast,cfg,dfg"]
```

---

### Q: Where are logs stored?

**A:** Logs are printed to stderr. Redirect to file:

```bash
comex --lang "java" --code-file test.java --graphs "ast" --debug 2> log.txt
```

Or in Python:
```python
from loguru import logger
logger.add("comex.log", level="DEBUG")
```

---

## Still Need Help?

- **Bug Reports**: [GitHub Issues](https://github.com/IBM/tree-sitter-codeviews/issues)
- **Feature Requests**: [GitHub Issues](https://github.com/IBM/tree-sitter-codeviews/issues)
- **Questions**: Create issue with "question" label
- **Security Issues**: See [SECURITY.md](../SECURITY.md)

## See Also

- [Getting Started](01-getting-started.md) - Installation and basics
- [CLI Reference](02-cli-reference.md) - Command-line options
- [Development Guide](08-development-guide.md) - Contributing
- [Examples](12-examples.md) - Usage patterns
