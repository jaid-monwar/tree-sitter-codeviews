# ATLAS Docker Guide

This guide covers running ATLAS using Docker.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose v2 (optional)

## Building the Image

```bash
docker build -t atlas .
```

## Running with Docker

### Show Help

```bash
docker run --rm atlas --help
```

### Process a Single File

Mount your working directory and run:

```bash
docker run --rm -v "$(pwd):/work" -w /work atlas --lang c --code-file test.c --graphs cfg
```

### Generate Multiple Graph Types

```bash
docker run --rm -v "$(pwd):/work" -w /work atlas --lang cpp --code-file main.cpp --graphs "cfg,dfg,ast"
```

### Output to a Specific File

```bash
docker run --rm -v "$(pwd):/work" -w /work atlas --lang c --code-file test.c --graphs cfg --output-file result.json
```

## Running with Docker Compose

Docker Compose provides a convenient setup with predefined volume mounts.

### Setup

Create input and output directories:

```bash
mkdir -p input output
```

Place your source files in the `./input` directory.

### Run ATLAS

```bash
docker compose run --rm atlas --lang c --code-file /input/test.c --graphs cfg
```

Output files will be written to the `./output` directory.

### Examples

Generate CFG for a C file:

```bash
docker compose run --rm atlas --lang c --code-file /input/example.c --graphs cfg --output-file example_cfg.json
```

Generate combined AST, CFG, and DFG:

```bash
docker compose run --rm atlas --lang cpp --code-file /input/main.cpp --graphs "ast,cfg,dfg" --output-file combined.json
```

## Volume Mounts

The docker-compose.yml configures three volumes:

| Mount | Purpose |
|-------|---------|
| `./input:/input` | Read-only mount for source files |
| `./output:/output` | Output directory for generated graphs |
| `atlas-grammars:/tmp/atlas` | Persists tree-sitter grammars between runs |

## Supported Languages

- `c` - C source files
- `cpp` - C++ source files

## Graph Types

- `ast` - Abstract Syntax Tree
- `cfg` - Control Flow Graph
- `dfg` - Data Flow Graph
- `ast,cfg,dfg` - Combined graph with all views
