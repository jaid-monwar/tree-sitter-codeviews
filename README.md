# Tree Sitter Multi Codeview Generator

Tree Sitter Multi Codeview Generator aims to generate combined multi-code view graphs that can be used with various types of machine learning models (sequence models, graph neural networks, etc). 

# Comex
`comex` is a rebuild of Tree Sitter Multi Codeview Generator for easier invocation as a Python package. This rebuild also includes a cli interface. Currently, ```comex``` generates codeviews for C and C++, for both function-level and file-level code snippets.  ```comex``` can be used to generate over $15$ possible combinations of codeviews for both languages (complete list [here](https://github.com/IBM/tree-sitter-codeviews/blob/main/List_Of_Views.pdf)). ```comex``` is designed to be easily extendable to various programming languages. This is primarliy because we use [tree-sitter](https://tree-sitter.github.io/tree-sitter/) for parsing, a highly efficient incremental parser that supports over $40$ languages. If you wish to add support for more languages, please refer to the [contributing](https://github.com/IBM/tree-sitter-codeviews/blob/main/CONTRIBUTING.md) guide.

If you wish to learn more about the approach taken, here are some conference talks and publications:
- ASE 2023 demonstration: [COMEX: A Tool for Generating Customized Source Code Representations](https://arxiv.org/abs/2307.04693)
- ICSE 2023 tutorial: [The Landscape of Source Code Representation Learning in AI-Driven Software Engineering Tasks](https://research.ibm.com/publications/the-landscape-of-source-code-representation-learning-in-ai-driven-software-engineering-tasks)

Comex played a critical role in developing `CodeSAM`, a novel framework for infusing multiple code-views into transformer-based models. CodeSAM builds on tools like `comex` to create structured code representations (e.g., AST, CFG, DFG), enabling fine-tuning of language models like CodeBERT. Experimental results show that by using this technique, we can improve downstream performance when compared to SLMs like GraphCodeBERT and CodeBERT on ML for SE tasks by utilizing individual code-views or a combination of code-views during fine-tuning.

You can find more details about `CodeSAM` in the following pre-print:
- [CodeSAM: Source Code Representation Learning by Infusing Self-Attention with Multi-Code-View Graphs](https://arxiv.org/abs/2411.14611)

## Cite Comex
If you use Comex in your research, please cite our work by using the following BibTeX entry:
```
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
## Installation from PyPi

`comex` is published on the Python Registry and can be easily installed via pip:

```console
pip install comex
```

**Note**: You would need to install GraphViz([dot](https://graphviz.org/download/)) so that the graph visualizations are generated

## Installation from source

To setup `comex` for development using the source code in your python environment:

```console
pip install -r requirements-dev.txt
```

This performs an editable install, meaning that comex would be available throughout your environment (particularly relevant if you use conda or something of the sort). This means now you can interact and import from `comex` just like any other package while remaining standalone but also reflecting any code side updates without any other manual steps

---
## Usage as a CLI

This is the recommended way to get started with `comex` as it is the most user friendly

The attributes and options supported by the CLI are well documented and can be viewed by running:
```console
comex --help
```

For example, to generate a combined CFG and DFG graph for a C file, you can run:
```console
comex --lang "c" --code-file ./test.c --graphs "cfg,dfg"
```

## Usage as a Python Package

The comex package can be used by importing required drivers as follows:

```python
from comex.codeviews.combined_graph.combined_driver import CombinedDriver

CombinedDriver(
    src_language=lang,
    src_code=code,
    output_file="output.json",
    graph_format=output,
    codeviews=codeviews
)
```
In most cases the required combination can be obtained via the `combined_driver` module as shown above.

````
src_language: denotes one of the supported languages hence currently "c" or "cpp"

src_code: denotes the source code to be parsed

output_file: denotes the output file to which the generated graph is written

graph_format: denotes the format of the output graph. Currently supported formats are "dot" and "json". To generate both pass "all"

codeviews: refers to the configuration passed for each codeview
````
---
## Limitations

While `comex` provides _function-level_ and _file-level_ support for both C and C++, it's important to note the following limitations and known issues:

### C/C++
- **No Inter-file Analysis Support**: The tool currently does not support codeviews that involve interactions between multiple source files. It is designed to generate codeviews for individual files only.

- **Syntax Errors in Code**: Despite supporting non-compileable code, to ensure accurate codeviews, the input code must be free of syntax errors. Code with syntax errors may not be correctly parsed and displayed in the generated codeviews.

- **Limited Support for Function Call Arguments**: The tool does not provide proper support for when a function call is passed as an argument to another function call. The resulting codeview might not accurately represent the intended behavior in such cases.

Please note that while we continuously work to improve the tool and address these limitations, the current implementation may not be perfect. We appreciate your understanding and encourage you to provide feedback and report any issues you encounter, as this helps us enhance the tool's capabilities.

---


## Output Examples:

Combined simple AST+CFG+DFG for a simple C program that finds the maximum among 2 numbers:

![Sample AST CFG DFG](https://github.com/IBM/tree-sitter-codeviews/raw/main/sample/sample.png)

Below we present an example of input code and generated codeviews.

---

**CLI Command**:

```bash
comex --lang "c" --code-file sample/example.c --graphs "cfg,dfg"
```
---

**C Code Snippet**:

```C
#include <stdio.h>

int max(int a, int b) {
    if (a > b) {
        return a;
    }
    return b;
}

int main() {
    int x = 5;
    int y = 10;
    int result = max(x, y);
    printf("Max: %d\n", result);
    return 0;
}
```
---

### Code Organization
The code is structured in the following way:
1. For each code-view, first the source code is parsed using the tree-sitter parser and then the various code-views are generated. In the [tree_parser](https://github.com/IBM/tree-sitter-codeviews/tree/main/src/comex/tree_parser) directory, the Parser and ParserDriver is implemented with various funcitonalities commonly required by all code-views. Language-specific features are further developed in the language-specific parsers also placed in this directory.
2. The [codeviews](https://github.com/IBM/tree-sitter-codeviews/tree/main/src/comex/codeviews) directory contains the core logic for the various codeviews. Each codeview has a driver class and a codeview class, which is further inherited and extended by language in case of code-views that require language-specific implementation.
3. The [cli.py](https://github.com/IBM/tree-sitter-codeviews/tree/main/src/comex/cli.py) file is the CLI implementation. The drivers can also be directly imported and used like a python package. It is responsible for parsing the source code and generating the codeviews.

### Publishing

Make sure to bump the version in `setup.cfg`.

Then run the following commands:

```bash
rm -rf build dist
python setup.py sdist bdist_wheel
```

Then upload it to PyPI using [twine](https://twine.readthedocs.io/en/latest/#installation) (`pip install twine` if not installed):

```bash
twine upload dist/*
```


### About the IBM OSCP Project
This tool was developed for research purposes as a part of the OSCP Project. Efficient representation of source code is essential for various software engineering tasks using AI pipelines such as code translation, code search and code clone detection. Code Representation aims at extracting the both syntactic and semantic features of source code and representing them by a vector which can be readily used for the downstream tasks. Multiple works exist that attempt to encode the code as sequential data to easily leverage state of art NN models like transformers. But it leads to a loss of information. Graphs are a natural representation for the code but very few works(MVG-AAAI’22) have tried to represent the different code features obtained from different code views like Program Dependency Graph, Data Flow Graph etc. as a multi-view graph. In this work, we want to explore more code views and its relevance to different code tasks as well as leverage transformers model for the multi-code view graphs. We believe such a work will help to 
1. Establish influence of specific code views for common tasks 
2. Demonstrate how graphs can combined with transformers 
3. Create re-usable models

### Team

This tool is based on the ongoing joint research effort between IBM and [Risha Lab](https://rishalab.in/) at [IIT Tirupati](https://www.iittp.ac.in/) to explore the effects of different code representations on code based tasks involving: 
 - [Srikanth Tamilselvam](https://www.linkedin.com/in/srikanth-tamilselvam-913a2ab/)
 - [Sridhar Chimalakonda](https://www.linkedin.com/in/sridharch/)
 - [Alex Mathai](https://www.linkedin.com/in/alex-mathai-403117131/)
 - [Debeshee Das](https://www.linkedin.com/in/debeshee-das/) 
 - [Noble Saji Mathews](https://www.linkedin.com/in/noble-saji-mathews/) 
 - [Kranthi Sedamaki](https://www.linkedin.com/in/kranthisedamaki/)
