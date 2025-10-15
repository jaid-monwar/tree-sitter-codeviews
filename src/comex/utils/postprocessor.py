import copy
import json
import os
import re
from subprocess import check_call

import networkx as nx
from networkx.readwrite import json_graph


def networkx_to_json(graph):
    """Convert a networkx graph to a json object"""
    graph_json = json_graph.node_link_data(graph)
    return graph_json


def write_networkx_to_json(graph, filename):
    """Convert a networkx graph to a json object"""
    graph_json = json_graph.node_link_data(graph)
    if not os.getenv("GITHUB_ACTIONS"):
        with open(filename, "w") as f:
            json.dump(graph_json, f)
    return graph_json


def to_dot(graph):
    return nx.nx_pydot.to_pydot(graph)


def write_to_dot(og_graph, filename, output_png=False, src_language=None):
    graph = copy.deepcopy(og_graph)
    if not os.getenv("GITHUB_ACTIONS"):
        # DOT reserved keywords that need to be quoted
        dot_reserved_keywords = {
            'node', 'edge', 'graph', 'digraph', 'subgraph', 'strict',
            'Node', 'Edge', 'Graph', 'Digraph', 'Subgraph', 'Strict'
        }

        for node in graph.nodes:
            if 'label' in graph.nodes[node]:
                label = graph.nodes[node]['label']

                # C and C++ specific handling for namespace qualifiers and other special chars
                if src_language in ['c', 'cpp']:
                    label = str(label)
                    # Replace colons (from C++ namespace qualifiers like std::cout)
                    label = label.replace('::', '_SCOPE_')
                    # Escape backslashes first (before other replacements) to preserve escape sequences
                    label = label.replace('\\', '\\\\')
                    # Replace other potentially problematic characters
                    label = label.replace('\n', ' ')
                    label = label.replace('\r', ' ')
                else:
                    # Original behavior for Java, C#, and other languages
                    label = re.escape(label)

                # Quote the label if it's a DOT reserved keyword
                if label in dot_reserved_keywords:
                    label = f'"{label}"'

                graph.nodes[node]['label'] = label
        nx.nx_pydot.write_dot(graph, filename)
        if output_png:
            check_call(
                ["dot", "-Tpng", filename, "-o", filename.rsplit(".", 1)[0] + ".png"]
            )
