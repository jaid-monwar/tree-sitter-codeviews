statement_types = {
    "node_list_type": [
        "declaration",
        "expression_statement",
        "labeled_statement",
        "if_statement",
        "while_statement",
        "for_statement",
        "do_statement",
        "break_statement",
        "continue_statement",
        "return_statement",
        "switch_statement",
        "function_definition",
        "case_statement",
        "goto_statement",
        "compound_statement",
        "preproc_include",
        "preproc_def",
        "preproc_function_def",
        "preproc_call",
        "preproc_if",
        "preproc_ifdef",
        "preproc_elif",
        "preproc_else"
    ],
    "non_control_statement": [
        "declaration",
        "expression_statement",
        "preproc_include",
        "preproc_def",
        "preproc_function_def",
        "preproc_call"
    ],
    "control_statement": [
        "if_statement",
        "while_statement",
        "for_statement",
        "do_statement",
        "break_statement",
        "continue_statement",
        "return_statement",
        "switch_statement",
        "goto_statement",
        "case_statement",
        "preproc_if",
        "preproc_ifdef",
        "preproc_elif",
        "preproc_else"
    ],
    "loop_control_statement": [
        "while_statement",
        "for_statement",
        "do_statement",
    ],
    "not_implemented": [],
    "inner_node_type": [
        "declaration",
        "expression_statement",
    ],
    "outer_node_type": ["for_statement"],
    "statement_holders": [
        "compound_statement",
        "translation_unit",
        "case_statement",
        "function_definition"
    ],
    "definition_types": ["function_definition", "declaration", "struct_specifier", "union_specifier", "enum_specifier"]
}

function_return_types = ['primitive_type', 'type_identifier', 'sized_type_specifier', 'struct_specifier', 'union_specifier', 'enum_specifier', 'pointer_declarator']

def get_child_of_type(node, type_list):
    out = list(filter(lambda x : x.type in type_list, node.children))
    if len(out) > 0:
        return out[0]
    else:
        return None

def return_switch_child(node):
    # Make it breadthfirst search, and return if you hit a node_list_type
    bfs_queue = []
    for child in node.children:
        bfs_queue.append(child)
    while bfs_queue != []:
        top = bfs_queue.pop(0)
        if top.type == "switch_statement":
            return top
        for child in top.children:
            bfs_queue.append(child)
    return None
