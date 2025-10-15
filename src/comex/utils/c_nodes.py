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

def get_function_signature(node):
    """Extract function signature from function definition or declaration"""
    signature = []
    # Find parameter_list in function_declarator
    for child in node.children:
        if child.type == "function_declarator":
            param_list = child.child_by_field_name('parameters')
            if param_list:
                for param in param_list.children:
                    if param.type == "parameter_declaration":
                        # Get the type of the parameter
                        for pchild in param.children:
                            if pchild.type in function_return_types:
                                signature.append(pchild.text.decode('utf-8'))
                                break
    return tuple(signature)

def get_function_name(node):
    """Extract function name from function_definition"""
    for child in node.children:
        if child.type == "function_declarator":
            # Find identifier in function_declarator
            for dchild in child.children:
                if dchild.type == "identifier":
                    return dchild.text.decode('utf-8')
                elif dchild.type == "pointer_declarator":
                    # Handle pointer return types like int *func()
                    for pchild in dchild.children:
                        if pchild.type == "identifier":
                            return pchild.text.decode('utf-8')
    return None

def get_nodes(root_node=None, node_list={}, graph_node_list=[], index={}, records={}):
    """
    Returns statement level nodes recursively from the C AST.
    Extracts nodes that will become CFG nodes and populates records dictionary.
    """

    # Special handling for do-while condition
    if (
        root_node.type == "parenthesized_expression"
        and root_node.parent is not None
        and root_node.parent.type == "do_statement"
    ):
        label = "while" + root_node.text.decode("UTF-8")
        type_label = "while"
        node_list[(root_node.start_point, root_node.end_point, root_node.type)] = root_node
        graph_node_list.append((index[(root_node.start_point, root_node.end_point, root_node.type)], root_node.start_point[0], label, type_label))

    # Handle statement-level nodes
    elif root_node.type in statement_types["node_list_type"]:
        # Skip for loop init/update statements if they're not in the body
        if (
            root_node.type in statement_types["inner_node_type"]
            and root_node.parent is not None
            and root_node.parent.type in statement_types["outer_node_type"]
        ):
            # Check if this is init or update part of for loop (not the body)
            if root_node.parent.type == "for_statement":
                body = root_node.parent.child_by_field_name("body")
                if body != root_node:
                    pass  # Skip this node
                else:
                    # This is the body, process it normally
                    node_list[(root_node.start_point, root_node.end_point, root_node.type)] = root_node
                    label = root_node.text.decode("UTF-8")
                    type_label = root_node.type
                    graph_node_list.append((index[(root_node.start_point, root_node.end_point, root_node.type)], root_node.start_point[0], label, type_label))

        # Check for switch expression in subtree
        elif (
            root_node.type in statement_types["inner_node_type"]
            and return_switch_child(root_node) is not None
        ):
            switch_child = return_switch_child(root_node)
            child_index = index[(switch_child.start_point, switch_child.end_point, switch_child.type)]
            current_index = index[(root_node.start_point, root_node.end_point, root_node.type)]
            records["switch_child_map"][current_index] = child_index

        else:
            node_list[(root_node.start_point, root_node.end_point, root_node.type)] = root_node
            label = root_node.text.decode("UTF-8")
            type_label = root_node.type

            # Customize labels based on node type
            if root_node.type == "function_definition":
                # Extract function signature
                label = ""
                for child in root_node.children:
                    if child.type != "compound_statement":
                        label = label + " " + child.text.decode('utf-8')

                func_name = get_function_name(root_node)
                func_index = index[(root_node.start_point, root_node.end_point, root_node.type)]
                type_label = "function_definition"

                if func_name:
                    signature = get_function_signature(root_node)
                    records["function_list"][(func_name, signature)] = func_index

                    # Check if this is main function
                    if func_name == "main":
                        records["main_function"] = func_index

                    # Get return type
                    return_type = None
                    for child in root_node.children:
                        if child.type in function_return_types:
                            return_type = child.text.decode('utf-8')
                            break
                    records["return_type"][(func_name, signature)] = return_type

                graph_node_list.append((func_index, root_node.start_point[0], label, type_label))

            elif root_node.type == "if_statement":
                condition = root_node.child_by_field_name("condition")
                if condition:
                    label = "if" + condition.text.decode("UTF-8")
                else:
                    label = "if(...)"
                type_label = "if"

            elif root_node.type == "for_statement":
                init = root_node.child_by_field_name("initializer")
                init_str = init.text.decode("UTF-8") + ";" if init else ""

                condition = root_node.child_by_field_name("condition")
                cond_str = condition.text.decode("UTF-8") if condition else ""

                update = root_node.child_by_field_name("update")
                update_str = update.text.decode("UTF-8") if update else ""

                label = "for(" + init_str + " " + cond_str + "; " + update_str + ")"
                type_label = "for"

            elif root_node.type == "while_statement":
                condition = root_node.child_by_field_name("condition")
                if condition:
                    label = "while" + condition.text.decode("UTF-8")
                else:
                    label = "while(...)"
                type_label = "while"

            elif root_node.type == "do_statement":
                label = "do"
                type_label = "do"

            elif root_node.type == "switch_statement":
                condition = root_node.child_by_field_name("condition")
                if condition:
                    label = "switch" + condition.text.decode("UTF-8")
                else:
                    label = "switch(...)"
                type_label = "switch"

            elif root_node.type == "case_statement":
                # Extract case value
                value_node = root_node.child_by_field_name("value")
                if value_node:
                    label = "case " + value_node.text.decode("UTF-8") + ":"
                else:
                    # This might be default case
                    if root_node.children and root_node.children[0].type == "default":
                        label = "default:"
                    else:
                        label = "case:"
                type_label = "case"

            elif root_node.type == "labeled_statement":
                # Extract label name
                label_node = root_node.child_by_field_name("label")
                if label_node:
                    label_name = label_node.text.decode("UTF-8")
                    label = label_name + ":"
                    # Store in label map for goto statements
                    current_index = index[(root_node.start_point, root_node.end_point, root_node.type)]
                    records["label_statement_map"][label_name] = (root_node.start_point, root_node.end_point, root_node.type)
                type_label = "label"

            elif root_node.type == "return_statement":
                label = root_node.text.decode("UTF-8")
                type_label = "return"

            elif root_node.type == "break_statement":
                label = "break;"
                type_label = "break"

            elif root_node.type == "continue_statement":
                label = "continue;"
                type_label = "continue"

            elif root_node.type == "goto_statement":
                # Extract target label
                label_node = root_node.child_by_field_name("label")
                if label_node:
                    label = "goto " + label_node.text.decode("UTF-8") + ";"
                else:
                    label = "goto;"
                type_label = "goto"

            # Add to graph node list if not already added above
            if root_node.type not in ["function_definition"]:
                node_index = index[(root_node.start_point, root_node.end_point, root_node.type)]
                graph_node_list.append((node_index, root_node.start_point[0], label, type_label))

    # Recursively process children
    for child in root_node.children:
        get_nodes(child, node_list, graph_node_list, index, records)

    return node_list, graph_node_list, records
