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
                    # Escape backslashes first (before other replacements) to preserve escape sequences
                    label = label.replace('\\', '\\\\')
                    # Escape double quotes to prevent breaking the label string
                    label = label.replace('"', '\\"')
                    # Replace newlines and carriage returns with spaces
                    label = label.replace('\n', ' ')
                    label = label.replace('\r', ' ')
                    # For C++, keep :: but ensure label is quoted (quotes added below)
                else:
                    # Original behavior for other languages
                    label = re.escape(label)

                # Always quote labels for C/C++ (to handle :: and other special chars)
                # or if it's a DOT reserved keyword
                if src_language in ['c', 'cpp'] or label in dot_reserved_keywords:
                    label = f'"{label}"'

                graph.nodes[node]['label'] = label

        # Fix edge attributes that might contain DOT reserved keywords or special characters
        for u, v, key, data in graph.edges(keys=True, data=True):
            # Check string-valued attributes like used_def, used_var, returned_value
            for attr_name in ['used_def', 'used_var', 'returned_value']:
                if attr_name in data:
                    attr_value = str(data[attr_name])
                    # Quote if it's a DOT reserved keyword or contains special characters
                    # For C/C++, quote if it contains :: (namespace qualifier)
                    needs_quoting = (
                        attr_value in dot_reserved_keywords or
                        (src_language in ['c', 'cpp'] and '::' in attr_value)
                    )
                    if needs_quoting:
                        graph.edges[u, v, key][attr_name] = f'"{attr_value}"'

        nx.nx_pydot.write_dot(graph, filename)
        if output_png:
            check_call(
                ["dot", "-Tpng", filename, "-o", filename.rsplit(".", 1)[0] + ".png"]
            )
