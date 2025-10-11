statement_types = {
    "node_list_type": [
        "declaration",
        "expression_statement",
        "labeled_statement",
        "if_statement",
        "while_statement",
        "for_statement",
        "for_range_loop",
        "do_statement",
        "break_statement",
        "continue_statement",
        "return_statement",
        "switch_statement",
        "case_statement",
        "throw_statement",
        "try_statement",
        "function_definition",
        "class_specifier",
        "struct_specifier",
        "namespace_definition",
        "using_declaration",
        "alias_declaration",
        "template_declaration",
        "field_declaration",
        "access_specifier",
        "constructor_or_destructor_definition",
        "operator_cast",
        "delete_expression",
        "lambda_expression",
    ],
    "non_control_statement": [
        "declaration",
        "expression_statement",
        "field_declaration",
        "using_declaration",
        "alias_declaration",
        "access_specifier",
    ],
    "control_statement": [
        "if_statement",
        "while_statement",
        "for_statement",
        "for_range_loop",
        "do_statement",
        "break_statement",
        "continue_statement",
        "return_statement",
        "switch_statement",
        "try_statement",
        "throw_statement",
    ],
    "loop_control_statement": [
        "while_statement",
        "for_statement",
        "for_range_loop",
    ],
    "not_implemented": [],
    "inner_node_type": [
        "declaration",
        "expression_statement",
    ],
    "outer_node_type": ["for_statement", "for_range_loop"],
    "statement_holders": [
        "compound_statement",
        "case_statement",
        "function_definition",
        "class_specifier",
        "struct_specifier",
        "namespace_definition",
        "translation_unit",
    ],
    "definition_types": [
        "function_definition",
        "class_specifier",
        "struct_specifier",
        "field_declaration",
        "namespace_definition",
        "template_declaration",
    ]
}

method_return_types = [
    'primitive_type',
    'type_identifier',
    'template_type',
    'qualified_identifier',
    'sized_type_specifier',
    'auto',
    'decltype'
]


def get_child_of_type(node, type_list):
    """Get first child of node matching any type in type_list"""
    out = list(filter(lambda x: x.type in type_list, node.children))
    if len(out) > 0:
        return out[0]
    else:
        return None


def return_switch_child(node):
    """Make it breadthfirst search, and return if you hit a node_list_type"""
    bfs_queue = []
    for child in node.children:
        bfs_queue.append(child)
    while bfs_queue != []:
        top = bfs_queue.pop(0)
        if top.type == "switch_statement":
            return top
        if top.type in statement_types["node_list_type"]:
            return None
        for child in top.children:
            bfs_queue.append(child)
    return None


def return_switch_parent(node, non_control_statement):
    """Searches for a switch expression while going up the tree and returns it"""
    while node.parent is not None and (node.parent.type != "class_specifier" and node.parent.type != "compound_statement"):
        if node.parent.type == "compound_statement" and node.type == "switch_statement":
            return node
        if node.parent.type in non_control_statement:
            return node.parent
        node = node.parent
    return None


def return_switch_parent_statement(node, non_control_statement):
    """Searches for a switch expression while going up the tree and returns it"""
    while node.parent is not None and (node.parent.type != "class_specifier" and node.parent.type != "compound_statement"):
        if node.parent.type in non_control_statement:
            return node.parent
        node = node.parent
    return None


def has_inner_definition(node):
    """Checks if a node has a definition inside it"""
    if node.type in statement_types["definition_types"]:
        return True
    for child in node.children:
        if has_inner_definition(child):
            return True
    return False


def find_function_definition(node):
    """Searches for a function definition while going up the tree and returns it"""
    while node.parent is not None:
        if node.parent.type == "function_definition":
            return node.parent
        node = node.parent
    return None


def get_signature(node):
    """Extract function signature (parameter types)"""
    signature = []
    parameter_list = node.child_by_field_name('parameters')
    if parameter_list is None:
        return tuple(signature)

    parameters = list(filter(lambda x: x.type == 'parameter_declaration' or x.type == 'optional_parameter_declaration', parameter_list.children))
    for parameter in parameters:
        # Get the type from parameter
        for child in parameter.children:
            if child.type in ['primitive_type', 'type_identifier', 'template_type', 'qualified_identifier', 'sized_type_specifier']:
                signature.append(child.text.decode('utf-8'))
                break
    return tuple(signature)


def get_lambda_body(node):
    """Returns the body of a lambda expression, breadthfirst"""
    bfs_queue = []
    bfs_queue.append(node)
    while bfs_queue != []:
        top = bfs_queue.pop(0)
        if top.type == "lambda_expression":
            return top
        for child in top.children:
            bfs_queue.append(child)
    return None


def get_all_lambda_body(node):
    """Returns all lambda expressions in the node, breadthfirst"""
    bfs_queue = []
    output = []
    bfs_queue.append(node)
    while bfs_queue != []:
        top = bfs_queue.pop(0)
        if top.type == "lambda_expression":
            output.append(top)
        for child in top.children:
            if child.type == "lambda_expression" or child.type not in statement_types["node_list_type"]:
                bfs_queue.append(child)
    return output


def check_lambda(node):
    """Checks if a node contains a lambda expression"""
    if get_lambda_body(node) is None:
        return False
    else:
        initial_node = node
        lambda_node = get_lambda_body(node)
        parent_node = lambda_node.parent
        while parent_node is not None:
            if parent_node.type in statement_types["node_list_type"]:
                if parent_node == initial_node:
                    return True
                else:
                    return False
            parent_node = parent_node.parent


def get_class_name(node, index):
    """Returns the class name when a function definition or method is passed to it"""
    type_identifiers = ["type_identifier", "template_type", "qualified_identifier"]
    while node is not None:
        if node.type == "field_declaration_list" and node.parent.type == "class_specifier":
            node = node.parent
            class_index = index[(node.start_point, node.end_point, node.type)]
            class_name_node = get_child_of_type(node, ["type_identifier"])
            if class_name_node:
                class_name = [class_name_node.text.decode("UTF-8")]
            else:
                class_name = ["anonymous_class"]

            # Check for base classes
            base_list = node.child_by_field_name("base_class_clause")
            if base_list is not None:
                for child in base_list.children:
                    if child.type in type_identifiers:
                        class_name.append(child.text.decode("UTF-8"))

            return class_index, class_name

        elif node.type == "field_declaration_list" and node.parent.type == "struct_specifier":
            node = node.parent
            class_index = index[(node.start_point, node.end_point, node.type)]
            class_name_node = get_child_of_type(node, ["type_identifier"])
            if class_name_node:
                class_name = [class_name_node.text.decode("UTF-8")]
            else:
                class_name = ["anonymous_struct"]

            return class_index, class_name

        node = node.parent
    return None


def get_nodes(root_node=None, node_list={}, graph_node_list=[], index={}, records={}):
    """
    Returns statement level nodes recursively from the concrete syntax tree passed to it.
    Uses records to maintain required supplementary information.
    node_list maintains an intermediate representation and graph_node_list returns the final list.
    """

    if root_node.type == "catch_clause":
        node_list[(root_node.start_point, root_node.end_point, root_node.type)] = root_node
        # Get the parameter from catch clause
        catch_parameter = list(filter(lambda child: child.type == "parameter_declaration", root_node.children))
        if catch_parameter:
            label = "catch (" + catch_parameter[0].text.decode("UTF-8") + ")"
        else:
            label = "catch (...)"
        type_label = "catch"
        graph_node_list.append((index[(root_node.start_point, root_node.end_point, root_node.type)], root_node.start_point[0], label, type_label))

    elif root_node.type in statement_types["node_list_type"]:
        if (
            root_node.type in statement_types["inner_node_type"]
            and root_node.parent is not None
            and root_node.parent.type in statement_types["outer_node_type"]
            and root_node.parent.child_by_field_name("body") != root_node
        ):
            pass
            # If it has a parent and the parent is a for loop type and it is an initialization or update statement, omit it
        elif (
            root_node.type in statement_types["inner_node_type"]
            and return_switch_child(root_node) is not None
        ):
            # There is a switch statement in the subtree starting from this statement_node
            switch_child = return_switch_child(root_node)
            child_index = index[(switch_child.start_point, switch_child.end_point, switch_child.type)]
            current_index = index[(root_node.start_point, root_node.end_point, root_node.type)]
            records["switch_child_map"][current_index] = child_index
        else:
            node_list[(root_node.start_point, root_node.end_point, root_node.type)] = root_node
            # Set default label values for the node and then modify based on node type if required
            label = root_node.text.decode("UTF-8")
            type_label = "expression_statement"

            if check_lambda(root_node) and root_node.type not in statement_types["definition_types"]:
                raw_label = root_node.text.decode("utf-8")
                label = ""
                for lambda_expression in get_all_lambda_body(root_node):
                    split_label = raw_label.split(lambda_expression.text.decode("utf-8"), 2)
                    raw_label = split_label[0]
                    if len(split_label) > 1:
                        label = split_label[1] + label
                    lambda_node = (lambda_expression.start_point, lambda_expression.end_point, lambda_expression.type)
                    records["lambda_map"][lambda_node] = root_node
                label = raw_label + label

            elif root_node.type == "lambda_expression":
                try:
                    if "{" in label:
                        label = label.split("{")[0] + label.split("}")[-1]
                    else:
                        label = root_node.text.decode('utf-8')
                except:
                    pass

            elif root_node.type == "function_definition":
                label = ""
                declarator = root_node.child_by_field_name("declarator")
                if declarator:
                    # Get function name and parameters
                    for child in root_node.children:
                        if child.type != "compound_statement" and child.type != "function_body":
                            label = label + " " + child.text.decode('utf-8')

                # Extract function name
                function_name_node = None
                if declarator:
                    if declarator.type == "function_declarator":
                        function_name_node = declarator.child_by_field_name("declarator")
                    elif declarator.type == "pointer_declarator" or declarator.type == "reference_declarator":
                        # Handle pointer/reference return types
                        nested = declarator
                        while nested and nested.type in ["pointer_declarator", "reference_declarator"]:
                            nested = nested.children[0] if nested.children else None
                        if nested and nested.type == "function_declarator":
                            function_name_node = nested.child_by_field_name("declarator")

                if function_name_node:
                    function_name = function_name_node.text.decode("UTF-8")
                else:
                    function_name = "unknown"

                function_index = index[(root_node.start_point, root_node.end_point, root_node.type)]
                type_label = root_node.type

                try:
                    signature = get_signature(declarator if declarator and declarator.type == "function_declarator" else root_node)
                    class_info = get_class_name(root_node, index)

                    if class_info:
                        class_index, class_name_list = class_info
                        if function_name == "main":
                            records["main_function"] = function_index
                            records["main_class"] = class_index

                        for class_name in class_name_list:
                            records["function_list"][((class_name, function_name), signature)] = function_index

                            # Get return type
                            return_type_node = root_node.child_by_field_name("type")
                            if return_type_node:
                                return_type = return_type_node.text.decode("UTF-8")
                            else:
                                return_type = "void"
                            records["return_type"][((class_name, function_name), signature)] = return_type
                    else:
                        # Global function
                        if function_name == "main":
                            records["main_function"] = function_index

                        records["function_list"][((None, function_name), signature)] = function_index
                        return_type_node = root_node.child_by_field_name("type")
                        if return_type_node:
                            return_type = return_type_node.text.decode("UTF-8")
                        else:
                            return_type = "void"
                        records["return_type"][((None, function_name), signature)] = return_type
                except:
                    pass

                graph_node_list.append((function_index, root_node.start_point[0], label, type_label))

            elif root_node.type == "class_specifier" or root_node.type == "struct_specifier":
                class_name_node = get_child_of_type(root_node, ["type_identifier"])
                if class_name_node:
                    class_name = class_name_node.text.decode("UTF-8")
                    label = f"{root_node.type.replace('_specifier', '')} {class_name}"
                else:
                    label = f"anonymous_{root_node.type.replace('_specifier', '')}"
                    class_name = label

                type_label = root_node.type
                class_index = index[(root_node.start_point, root_node.end_point, root_node.type)]
                records["class_list"][class_name] = class_index

                # Check for base classes
                base_list = root_node.child_by_field_name("base_class_clause")
                if base_list is not None:
                    for child in base_list.children:
                        if child.type in ["type_identifier", "template_type", "qualified_identifier"]:
                            parent_name = child.text.decode("UTF-8")
                            try:
                                records['extends'][class_name].append(parent_name)
                            except:
                                records['extends'][class_name] = [parent_name]

            elif root_node.type == "namespace_definition":
                namespace_name = None
                for child in root_node.children:
                    if child.type == "identifier":
                        namespace_name = child.text.decode("UTF-8")
                        break
                if namespace_name:
                    label = f"namespace {namespace_name}"
                else:
                    label = "anonymous namespace"
                type_label = "namespace_definition"

            elif root_node.type == "if_statement":
                condition = root_node.child_by_field_name("condition")
                if condition:
                    label = "if(" + condition.text.decode("UTF-8") + ")"
                else:
                    label = "if"
                type_label = "if"

            elif root_node.type == "for_statement":
                try:
                    init = root_node.child_by_field_name("initializer")
                    init_text = init.text.decode("UTF-8") if init else ""
                    if init_text and not init_text.endswith(";"):
                        init_text = init_text + ";"
                except:
                    init_text = ""
                try:
                    condition = root_node.child_by_field_name("condition")
                    condition_text = condition.text.decode("UTF-8") if condition else ""
                except:
                    condition_text = ""
                try:
                    update = root_node.child_by_field_name("update")
                    update_text = update.text.decode("UTF-8") if update else ""
                except:
                    update_text = ""
                label = "for(" + init_text + condition_text + ";" + update_text + ")"
                type_label = "for"

            elif root_node.type == "for_range_loop":
                try:
                    declarator = root_node.child_by_field_name("declarator")
                    declarator_text = declarator.text.decode("UTF-8") if declarator else ""
                    range_expr = root_node.child_by_field_name("right")
                    range_text = range_expr.text.decode("UTF-8") if range_expr else ""
                    label = f"for({declarator_text} : {range_text})"
                except:
                    label = "for(range)"
                type_label = "for"

            elif root_node.type == "while_statement":
                condition = root_node.child_by_field_name("condition")
                if condition:
                    label = "while(" + condition.text.decode("UTF-8") + ")"
                else:
                    label = "while"
                type_label = "while"

            elif root_node.type == "do_statement":
                label = "do"
                type_label = "do"

            elif root_node.type == "switch_statement":
                condition = root_node.child_by_field_name("condition")
                if condition:
                    label = "switch(" + condition.text.decode("UTF-8") + ")"
                else:
                    label = "switch"
                type_label = "switch"

            elif root_node.type == "case_statement":
                value = root_node.child_by_field_name("value")
                if value:
                    label = "case " + value.text.decode("UTF-8") + ":"
                else:
                    label = "default:"
                type_label = "case"

            elif root_node.type == "try_statement":
                label = "try"
                type_label = "try"

            elif root_node.type == "labeled_statement":
                label_node = root_node.child_by_field_name("label")
                if label_node:
                    label = label_node.text.decode("UTF-8") + ":"
                    records["label_statement_map"][label] = (
                        root_node.start_point,
                        root_node.end_point,
                        root_node.type,
                    )
                else:
                    label = "label:"
                type_label = "label"

            elif root_node.type == "return_statement":
                if has_inner_definition(root_node):
                    label = "return"
                else:
                    label = root_node.text.decode("UTF-8")
                type_label = "return"

            if root_node.type != "function_definition":
                graph_node_list.append(
                    (
                        index[(root_node.start_point, root_node.end_point, root_node.type)],
                        root_node.start_point[0],
                        label,
                        type_label,
                    )
                )

    for child in root_node.children:
        root_node, node_list, graph_node_list, records = get_nodes(
            root_node=child,
            node_list=node_list,
            graph_node_list=graph_node_list,
            index=index,
            records=records,
        )

    return root_node, node_list, graph_node_list, records
