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
        "goto_statement",
        "switch_statement",
        "case_statement",
        "throw_statement",
        "try_statement",
        "function_definition",
        "class_specifier",
        "struct_specifier",
        "namespace_definition",
        "using_declaration",          # Included for program comprehension (compile-time name resolution)
        "alias_declaration",
        "template_declaration",
        "field_declaration",
        "access_specifier",
        "constructor_or_destructor_definition",
        "operator_cast",
        # "delete_expression",      # Excluded: delete is an expression, always wrapped in expression_statement
        "lambda_expression",
        # HIGH PRIORITY FEATURES ADDED:
        "enum_specifier",           # Enum types
        "union_specifier",          # Union types
        "type_definition",          # Typedef declarations
        "friend_declaration",       # Friend declarations
        "catch_clause",             # Exception catch blocks
        "attributed_statement",     # Statements with C++ attributes (e.g., [[fallthrough]];)
        # MEDIUM PRIORITY FEATURES ADDED:
        # "new_expression",         # Excluded: new is an expression, not a statement (appears within other statements)
        "static_assert_declaration", # Static assertions
        # "using_declaration",      # Excluded: compile-time only (duplicate, already commented above)
        "namespace_alias_definition", # Namespace aliases
        # Preprocessor directives - INCLUDED for macro extraction and conditional evaluation:
        "preproc_include",        # Include directives (won't be added to CFG, just processed)
        "preproc_def",            # Macro definitions (extracted for condition evaluation)
        "preproc_ifdef",          # Conditional compilation
        "preproc_if",             # Conditional compilation
        "preproc_elif",           # Conditional compilation continuation
        "preproc_else",           # Conditional compilation alternative
    ],
    "non_control_statement": [
        "declaration",
        "expression_statement",
        "field_declaration",
        "using_declaration",          # Included for program comprehension
        "alias_declaration",
        "access_specifier",
        "enum_specifier",
        "union_specifier",
        "type_definition",
        "friend_declaration",
        "static_assert_declaration",
        "namespace_alias_definition",
        "attributed_statement",       # Statements with attributes like [[fallthrough]];
        # Preprocessor directives excluded - they are compile-time only, not runtime:
        # "preproc_include",          # Excluded: preprocessor directive
        # "preproc_def",              # Excluded: preprocessor directive
        # "preproc_ifdef",            # Excluded: preprocessor directive
        # "preproc_if",               # Excluded: preprocessor directive
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
        "goto_statement",
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
        "enum_specifier",
        "union_specifier",
        "type_definition",
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


def is_function_declaration(node):
    """
    Check if a declaration node is a function declaration (forward declaration).
    Function declarations have a function_declarator child but NO compound_statement (body).
    Returns True for function declarations (should be excluded from CFG).
    Returns False for variable declarations (should be included in CFG).
    """
    if node.type != "declaration":
        return False

    has_function_declarator = False
    has_body = False

    for child in node.children:
        if child.type == "function_declarator":
            has_function_declarator = True
        if child.type == "compound_statement":
            has_body = True

    # It's a function declaration if it has function_declarator but no body
    return has_function_declarator and not has_body


def find_function_definition(node):
    """Searches for a function definition while going up the tree and returns it"""
    while node.parent is not None:
        if node.parent.type == "function_definition":
            return node.parent
        node = node.parent
    return None


def is_virtual_function(node):
    """Check if a function_definition or field_declaration is virtual"""
    if node.type not in ["function_definition", "field_declaration"]:
        return False

    for child in node.children:
        if child.type == "virtual":
            return True
    return False


def is_pure_virtual_function(node):
    """Check if a function is pure virtual (= 0)"""
    if not is_virtual_function(node):
        return False

    # Check for = 0 pattern
    has_equals = False
    for child in node.children:
        if child.type == "=" or child.text == b"=":
            has_equals = True
        if has_equals and child.type == "number_literal" and child.text == b"0":
            return True
    return False


def has_field_initializer_list(node):
    """Check if a function has a constructor initializer list"""
    if node.type != "function_definition":
        return False

    for child in node.children:
        if child.type == "field_initializer_list":
            return True
    return False


def is_deleted_or_defaulted(node):
    """Check if a function is = default or = delete"""
    if node.type not in ["function_definition", "field_declaration"]:
        return None

    for child in node.children:
        if child.type == "default_method_clause":
            return "default"
        if child.type == "delete_method_clause":
            return "delete"
    return None


def is_operator_overload(node):
    """Check if a function is an operator overload"""
    if node.type != "function_definition":
        return False

    declarator = node.child_by_field_name("declarator")
    if declarator:
        for child in declarator.children:
            if child.type == "operator_name":
                return True
    return False


# MEDIUM PRIORITY FEATURE HELPERS

def is_constexpr_function(node):
    """Check if a function is constexpr"""
    if node.type not in ["function_definition", "field_declaration"]:
        return False

    for child in node.children:
        if child.type == "constexpr":
            return True
    return False


def is_inline_function(node):
    """Check if a function has inline specifier"""
    if node.type not in ["function_definition", "field_declaration"]:
        return False

    for child in node.children:
        if child.type == "inline":
            return True
    return False


def has_noexcept_specifier(node):
    """Check if a function has noexcept specifier"""
    if node.type not in ["function_definition", "field_declaration"]:
        return False

    for child in node.children:
        if child.type == "noexcept":
            return True
    return False


def get_attributes(node):
    """Extract C++ attributes like [[nodiscard]], [[deprecated]]"""
    attributes = []
    for child in node.children:
        if child.type == "attribute_specifier":
            # Extract attribute names
            for attr_child in child.children:
                if attr_child.type == "attribute":
                    for identifier in attr_child.children:
                        if identifier.type == "identifier":
                            attributes.append(identifier.text.decode("utf-8"))
    return attributes


def has_auto_type(node):
    """Check if a declaration uses auto type inference"""
    if node.type not in ["declaration", "parameter_declaration"]:
        return False

    for child in node.children:
        if child.type == "auto":
            return True
        # Check recursively in declarators
        if child.type in ["init_declarator", "parameter_declarator"]:
            for subchild in child.children:
                if subchild.type == "auto":
                    return True
    return False


def is_rvalue_reference(node):
    """Check if a declaration is an rvalue reference (&&)"""
    if node.type not in ["declaration", "parameter_declaration", "field_declaration"]:
        return False

    for child in node.children:
        if child.type == "rvalue_reference_declarator":
            return True
        # Check in nested declarators
        if hasattr(child, 'children'):
            for subchild in child.children:
                if subchild.type == "rvalue_reference_declarator":
                    return True
    return False


def is_template_specialization(node):
    """Check if a template declaration is a specialization"""
    if node.type != "template_declaration":
        return False

    # Check for empty template parameter list (template<>)
    for child in node.children:
        if child.type == "template_parameter_list":
            # Empty or has only whitespace/comments
            named_children = [c for c in child.children if c.is_named]
            if len(named_children) == 0:
                return True
    return False


def get_signature(node):
    """Extract function signature (parameter types) including reference qualifiers"""
    signature = []
    parameter_list = node.child_by_field_name('parameters')
    if parameter_list is None:
        return tuple(signature)

    parameters = list(filter(lambda x: x.type == 'parameter_declaration' or x.type == 'optional_parameter_declaration', parameter_list.children))
    for parameter in parameters:
        # Get the base type from parameter
        base_type = None
        for child in parameter.children:
            if child.type in ['primitive_type', 'type_identifier', 'template_type', 'qualified_identifier', 'sized_type_specifier']:
                base_type = child.text.decode('utf-8')
                break

        if base_type:
            # Check for reference/pointer declarator
            declarator = parameter.child_by_field_name('declarator')
            if declarator:
                if declarator.type == 'reference_declarator':
                    # Check if it's rvalue reference (&&) or lvalue reference (&)
                    declarator_text = declarator.text.decode('utf-8')
                    if declarator_text.startswith('&&'):
                        signature.append(base_type + '&&')
                    else:
                        signature.append(base_type + '&')
                elif declarator.type == 'pointer_declarator':
                    signature.append(base_type + '*')
                else:
                    # Other declarator types (array, etc.)
                    signature.append(base_type)
            else:
                # No declarator, just base type
                signature.append(base_type)
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
    """Returns the class name or namespace when a function definition or method is passed to it.

    For namespaces, builds the fully qualified name (e.g., "Outer::Inner").
    Returns tuple: (index, [name]) where name can be class, struct, or namespace.
    """
    type_identifiers = ["type_identifier", "template_type", "qualified_identifier"]

    # First, check if function is in a namespace by traversing up to build namespace path
    namespace_parts = []
    temp_node = node
    while temp_node is not None:
        if temp_node.type == "namespace_definition":
            # Get namespace name (or mark as anonymous if unnamed)
            namespace_name_node = temp_node.child_by_field_name("name")
            if namespace_name_node:
                namespace_name = namespace_name_node.text.decode("UTF-8")
                # Prepend to build qualified name from outer to inner
                namespace_parts.insert(0, namespace_name)
            else:
                # Anonymous namespace - don't include in qualified name
                # Functions in anonymous namespaces have internal linkage
                # They should be treated as global functions for CFG purposes
                pass
        temp_node = temp_node.parent

    # If we found namespace(s), return the qualified namespace name
    if namespace_parts:
        # Build fully qualified namespace (e.g., "Outer::Inner")
        qualified_namespace = "::".join(namespace_parts)
        # Find the innermost namespace node for index
        temp_node = node
        while temp_node is not None:
            if temp_node.type == "namespace_definition":
                namespace_index = index.get((temp_node.start_point, temp_node.end_point, temp_node.type))
                if namespace_index is not None:
                    return namespace_index, [qualified_namespace]
            temp_node = temp_node.parent

    # Otherwise, check for class/struct as before
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


def evaluate_preprocessor_condition(condition_text, macro_definitions):
    """
    Evaluate a preprocessor condition based on defined macros.
    Returns True if the condition is satisfied, False otherwise, None if cannot evaluate.

    Supports:
    - #ifdef MACRO
    - #ifndef MACRO
    - #if MACRO == VALUE
    - #if defined(MACRO)
    - Simple comparisons and logic
    """
    import re

    # Handle #ifdef and #ifndef (already processed, just check for identifier)
    if not any(op in condition_text for op in ['==', '!=', '>', '<', '&&', '||', 'defined']):
        # Simple identifier check for #ifdef
        identifier = condition_text.strip()
        return identifier in macro_definitions

    # Handle #if defined(MACRO)
    defined_pattern = r'defined\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)'
    condition_text = re.sub(defined_pattern,
                           lambda m: '1' if m.group(1) in macro_definitions else '0',
                           condition_text)

    # Replace macro names with their values
    for macro, value in macro_definitions.items():
        # Use word boundaries to avoid partial replacements
        condition_text = re.sub(r'\b' + macro + r'\b', str(value), condition_text)

    # Try to evaluate the expression
    try:
        # Safe evaluation of simple expressions
        # Only allow basic operators and numbers
        if re.match(r'^[\d\s+\-*/<>=!&|()]+$', condition_text):
            result = eval(condition_text)
            return bool(result)
    except:
        pass

    return None  # Cannot evaluate


def get_nodes(root_node=None, node_list={}, graph_node_list=[], index={}, records={}, macro_definitions=None):
    """
    Returns statement level nodes recursively from the concrete syntax tree passed to it.
    Uses records to maintain required supplementary information.
    node_list maintains an intermediate representation and graph_node_list returns the final list.

    Args:
        macro_definitions: Dictionary of defined macros {name: value} for preprocessor evaluation
    """
    import os  # For debug logging

    if macro_definitions is None:
        macro_definitions = {}

    if root_node.type == "catch_clause":
        node_list[(root_node.start_point, root_node.end_point, root_node.type)] = root_node
        # Get the parameter from catch clause
        catch_parameter = list(filter(lambda child: child.type == "parameter_list", root_node.children))
        if catch_parameter:
            param_text = catch_parameter[0].text.decode("UTF-8")
            # Strip parentheses if present (they're included in parameter_list)
            if param_text.startswith("(") and param_text.endswith(")"):
                param_text = param_text[1:-1]

            # Check for catch-all
            if param_text.strip() == "...":
                label = "catch (...)"
            else:
                label = "catch (" + param_text + ")"
        else:
            label = "catch (...)"
        type_label = "catch"
        graph_node_list.append((index[(root_node.start_point, root_node.end_point, root_node.type)], root_node.start_point[0], label, type_label))

    elif root_node.type in ["preproc_include", "preproc_def", "preproc_function_def", "preproc_call",
                            "preproc_if", "preproc_ifdef", "preproc_elif", "preproc_else"]:
        # Handle preprocessor directives specially - they should NOT be added to graph_node_list
        # Only process them for macro extraction and conditional evaluation
        # The actual traversal logic is at the end of this function

        if root_node.type == "preproc_def":
            # Extract macro definitions for use in condition evaluation
            text = root_node.text.decode("UTF-8")
            parts = text.split(None, 2)  # Split into #define, name, value
            if len(parts) >= 2:
                macro_name = parts[1]
                macro_value = parts[2].strip() if len(parts) > 2 else "1"
                macro_definitions[macro_name] = macro_value
                if os.environ.get('DEBUG_PREPROC'):
                    print(f"[DEFINE] {macro_name} = {macro_value}")

    elif root_node.type in statement_types["node_list_type"]:
        # FIX: Skip field_declaration nodes (class/struct member declarations)
        # These are compile-time constructs and should not appear in CFG
        # Note: This includes static member declarations and member function declarations
        if root_node.type == "field_declaration":
            pass  # Skip this node, but will recurse through children below

        # FIX: Skip struct/class specifiers at global/namespace scope
        # These are type definitions, not executable code
        # Still recurse through children to find member function DEFINITIONS (not declarations)
        elif root_node.type in ["struct_specifier", "class_specifier"]:
            # Check if this is at global/namespace scope or nested inside another class
            parent = root_node.parent
            should_skip = False

            # Check for global scope or namespace scope
            if parent and parent.type in ["translation_unit", "declaration_list"]:
                # Could be namespace's declaration_list or global scope
                if parent.type == "declaration_list":
                    grandparent = parent.parent if parent else None
                    # If grandparent is namespace or translation_unit, skip
                    if grandparent and grandparent.type in ["namespace_definition", "translation_unit"]:
                        should_skip = True
                else:
                    # Direct child of translation_unit - global scope
                    should_skip = True

            # Check for nested class/struct inside another class
            elif parent and parent.type == "field_declaration_list":
                should_skip = True

            if should_skip:
                pass  # Skip this node, will recurse through children to find function definitions
            # else: fall through to normal processing for local struct definitions in functions

        # Skip function declarations (forward declarations without bodies)
        # These are compile-time constructs and should not appear in CFG
        elif is_function_declaration(root_node):
            pass  # Skip this node
        # Skip template_declaration nodes (compile-time constructs)
        # The actual function/class definition inside the template will be processed separately
        elif root_node.type == "template_declaration":
            pass  # Skip template wrapper, process its contents
        # Skip access_specifiers (public:, private:, protected:)
        # These are compile-time directives, not executable code
        # 1. Inside base_class_clause (inheritance specifiers like "public" in "struct Foo : public Bar")
        # 2. Inside class/struct bodies (access modifiers like "public:" in class definitions)
        elif root_node.type == "access_specifier":
            pass  # Skip all access specifiers - they're not executable code
        # Skip statements that are children of attributed_statement (the attributed_statement itself will be processed)
        elif root_node.parent and root_node.parent.type == "attributed_statement":
            pass  # Skip inner statements - the attributed_statement wrapper is the CFG node
        elif (
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

                # Check for special function properties (high priority)
                is_virtual = is_virtual_function(root_node)
                is_pure_virtual = is_pure_virtual_function(root_node)
                is_operator = is_operator_overload(root_node)
                deleted_or_defaulted = is_deleted_or_defaulted(root_node)
                has_initializers = has_field_initializer_list(root_node)

                # Check for medium priority function features
                is_constexpr = is_constexpr_function(root_node)
                is_inline = is_inline_function(root_node)
                has_noexcept = has_noexcept_specifier(root_node)
                attributes = get_attributes(root_node)

                if declarator:
                    # Get function name and parameters
                    for child in root_node.children:
                        if child.type not in ["compound_statement", "function_body", "field_initializer_list"]:
                            label = label + " " + child.text.decode('utf-8')

                # Extract function name
                function_name_node = None
                if declarator:
                    if declarator.type == "function_declarator":
                        # Check for operator overload first (operator_name node)
                        operator_name_node = None
                        for child in declarator.children:
                            if child.type == "operator_name":
                                operator_name_node = child
                                break

                        if operator_name_node:
                            function_name_node = operator_name_node
                        else:
                            function_name_node = declarator.child_by_field_name("declarator")
                    elif declarator.type == "pointer_declarator" or declarator.type == "reference_declarator":
                        # Handle pointer/reference return types
                        # Navigate through pointer/reference layers to find the function_declarator
                        nested = declarator
                        while nested and nested.type in ["pointer_declarator", "reference_declarator"]:
                            # Find the function_declarator child (skip * and & symbols)
                            found_nested = None
                            for child in nested.children:
                                if child.type in ["function_declarator", "pointer_declarator", "reference_declarator"]:
                                    found_nested = child
                                    break
                            nested = found_nested

                        if nested and nested.type == "function_declarator":
                            # Check for operator overload in nested declarator
                            operator_name_node = None
                            for child in nested.children:
                                if child.type == "operator_name":
                                    operator_name_node = child
                                    break

                            if operator_name_node:
                                function_name_node = operator_name_node
                            else:
                                function_name_node = nested.child_by_field_name("declarator")

                if function_name_node:
                    function_name = function_name_node.text.decode("UTF-8")
                else:
                    function_name = "unknown"

                function_index = index[(root_node.start_point, root_node.end_point, root_node.type)]
                type_label = root_node.type

                try:
                    # Find the function_declarator for signature extraction
                    # It may be nested inside pointer_declarator or reference_declarator
                    sig_node = declarator
                    if declarator and declarator.type in ["pointer_declarator", "reference_declarator"]:
                        # Navigate through pointer/reference layers to find function_declarator
                        nested = declarator
                        while nested and nested.type in ["pointer_declarator", "reference_declarator"]:
                            found_nested = None
                            for child in nested.children:
                                if child.type == "function_declarator":
                                    sig_node = child
                                    break
                                elif child.type in ["pointer_declarator", "reference_declarator"]:
                                    found_nested = child
                                    break
                            if sig_node and sig_node.type == "function_declarator":
                                break
                            nested = found_nested

                    signature = get_signature(sig_node if sig_node and sig_node.type == "function_declarator" else root_node)
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

                            # Track C++ specific function features (high priority)
                            if is_virtual or is_pure_virtual:
                                records["virtual_functions"][function_index] = {
                                    "is_virtual": is_virtual,
                                    "is_pure_virtual": is_pure_virtual
                                }
                            if is_operator:
                                records["operator_overloads"][function_index] = function_name
                            if deleted_or_defaulted:
                                records["special_functions"][function_index] = deleted_or_defaulted
                            if has_initializers:
                                records["functions_with_initializers"][function_index] = True

                            # Track medium priority function features
                            if is_constexpr:
                                records["constexpr_functions"][function_index] = True
                            if is_inline:
                                records["inline_functions"][function_index] = True
                            if has_noexcept:
                                records["noexcept_functions"][function_index] = True
                            if attributes:
                                records["attributed_functions"][function_index] = attributes
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
                # Use field-based access to get namespace name
                namespace_name_node = root_node.child_by_field_name("name")
                if namespace_name_node:
                    namespace_name = namespace_name_node.text.decode("UTF-8")
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
                    # Map label to the labeled_statement node itself
                    # Goto statements will jump to this label node
                    # The labeled_statement handler in CFG_cpp.py will then create
                    # an edge from the label to the statement after it
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

            # HIGH PRIORITY FEATURES:
            elif root_node.type == "enum_specifier":
                # enum Color { RED, GREEN } or enum class Status { OK, ERROR }
                enum_name_node = get_child_of_type(root_node, ["type_identifier"])
                is_scoped = "class" in [child.type for child in root_node.children]
                if enum_name_node:
                    enum_name = enum_name_node.text.decode("UTF-8")
                    if is_scoped:
                        label = f"enum class {enum_name}"
                    else:
                        label = f"enum {enum_name}"
                else:
                    label = "enum (anonymous)"
                type_label = "enum"

                enum_index = index[(root_node.start_point, root_node.end_point, root_node.type)]
                if enum_name_node:
                    records["enum_list"][enum_name] = enum_index

            elif root_node.type == "union_specifier":
                # union Data { int i; float f; }
                union_name_node = get_child_of_type(root_node, ["type_identifier"])
                if union_name_node:
                    union_name = union_name_node.text.decode("UTF-8")
                    label = f"union {union_name}"
                else:
                    label = "union (anonymous)"
                type_label = "union"

                union_index = index[(root_node.start_point, root_node.end_point, root_node.type)]
                if union_name_node:
                    records["union_list"][union_name] = union_index

            elif root_node.type == "type_definition":
                # typedef int Integer; or typedef void (*FuncPtr)(int);
                type_identifier_node = get_child_of_type(root_node, ["type_identifier"])
                if type_identifier_node:
                    typedef_name = type_identifier_node.text.decode("UTF-8")
                    label = f"typedef {typedef_name}"
                else:
                    label = "typedef"
                type_label = "typedef"

                typedef_index = index[(root_node.start_point, root_node.end_point, root_node.type)]
                if type_identifier_node:
                    records["typedef_list"][typedef_name] = typedef_index

            elif root_node.type == "friend_declaration":
                # friend class B; or friend void func();
                label = "friend " + root_node.text.decode("UTF-8").replace("friend", "").strip()
                if len(label) > 80:
                    label = label[:77] + "..."
                type_label = "friend"

            # MEDIUM PRIORITY NODE TYPES
            elif root_node.type == "static_assert_declaration":
                # static_assert(sizeof(int) == 4, "int must be 4 bytes");
                label = root_node.text.decode("UTF-8")
                if len(label) > 80:
                    label = label[:77] + "..."
                type_label = "static_assert"

            elif root_node.type == "namespace_alias_definition":
                # namespace short_name = very::long::namespace::name;
                label = root_node.text.decode("UTF-8")
                if len(label) > 80:
                    label = label[:77] + "..."
                type_label = "namespace_alias"

            elif root_node.type == "using_declaration":
                # using std::cout; or using namespace std;
                label = root_node.text.decode("UTF-8")
                if len(label) > 80:
                    label = label[:77] + "..."
                type_label = "using"

            elif root_node.type == "attributed_statement":
                # [[fallthrough]]; or [[maybe_unused]] int x;
                # Extract attribute names for label
                attributes = []
                for child in root_node.children:
                    if child.type == "attribute_declaration":
                        for attr_child in child.named_children:
                            if attr_child.type == "attribute":
                                attr_text = attr_child.text.decode('utf-8')
                                attr_name = attr_text.split('(')[0].strip()
                                attributes.append(attr_name)

                # Get the statement text (excluding the body if it's a compound statement)
                label = root_node.text.decode("UTF-8")
                if len(label) > 80:
                    label = label[:77] + "..."
                type_label = "expression_statement"

            elif root_node.type == "new_expression":
                # new int(5) or new MyClass()
                label = root_node.text.decode("UTF-8")
                if len(label) > 80:
                    label = label[:77] + "..."
                type_label = "new"

            # Exclude preprocessor directives and function_definition from graph_node_list
            # Preprocessor directives are compile-time only, not runtime control flow
            # function_definition is added separately with special handling
            # Compile-time directives should also be excluded from CFG
            excluded_from_graph = {
                "function_definition",
                "preproc_include", "preproc_def", "preproc_function_def", "preproc_call",
                "preproc_if", "preproc_ifdef", "preproc_elif", "preproc_else",
                # Compile-time name resolution directives (not runtime code):
                "using_declaration",          # using namespace std; or using std::cout;
                "alias_declaration",           # using my_type = int;
                "namespace_alias_definition",  # namespace alias = original_namespace;
            }

            if root_node.type not in excluded_from_graph:
                graph_node_list.append(
                    (
                        index[(root_node.start_point, root_node.end_point, root_node.type)],
                        root_node.start_point[0],
                        label,
                        type_label,
                    )
                )

    # Handle preprocessor directives specially
    # For conditional directives (#ifdef, #ifndef, #if/#elif/#else), evaluate the condition
    # and only traverse into the active branch
    if root_node.type in ["preproc_ifdef", "preproc_if", "preproc_elif"]:
        # Extract the condition
        condition = None
        is_ifndef = False

        if root_node.type == "preproc_ifdef":
            # #ifdef MACRO or #ifndef MACRO - check if MACRO is defined
            # Determine if it's #ifdef or #ifndef by checking the directive token
            for child in root_node.children:
                if child.type == "#ifndef":
                    is_ifndef = True
                elif child.type == "identifier":
                    condition = child.text.decode("UTF-8")
                    break
        elif root_node.type == "preproc_if" or root_node.type == "preproc_elif":
            # #if MACRO == VALUE or #elif MACRO == VALUE
            # The condition is a named child (usually binary_expression, identifier, etc.)
            found_directive = False
            for child in root_node.children:
                if child.type in ["#if", "#elif"]:
                    found_directive = True
                elif found_directive and child.is_named and child.type not in ["preproc_elif", "preproc_else", "declaration", "expression_statement"]:
                    # This is the condition expression
                    condition = child.text.decode("UTF-8")
                    break

        # Evaluate the condition
        condition_met = False
        if condition:
            result = evaluate_preprocessor_condition(condition, macro_definitions)
            if result is not None:
                # For #ifndef, invert the result
                condition_met = (not result) if is_ifndef else result
                # DEBUG
                if os.environ.get('DEBUG_PREPROC'):
                    print(f"[PREPROC] {root_node.type} condition='{condition}' is_ifndef={is_ifndef} macros={macro_definitions} result={result} condition_met={condition_met}")
            else:
                # Cannot evaluate - include the branch to be safe
                condition_met = True
                if os.environ.get('DEBUG_PREPROC'):
                    print(f"[PREPROC] {root_node.type} condition='{condition}' macros={macro_definitions} CANNOT_EVALUATE, including by default")

        # Find which children to process based on condition
        # For #ifdef/#if, process content if condition is True
        # For #elif, process its content directly if condition is True
        if root_node.type == "preproc_elif":
            # For elif, process children directly if condition is met
            if condition_met:
                for child in root_node.children:
                    if child.is_named and child.type not in ["preproc_else", "preproc_elif"]:
                        root_node, node_list, graph_node_list, records = get_nodes(
                            root_node=child,
                            node_list=node_list,
                            graph_node_list=graph_node_list,
                            index=index,
                            records=records,
                            macro_definitions=macro_definitions,
                        )
        elif root_node.type == "preproc_ifdef" or root_node.type == "preproc_if":
            # Process children, but skip #elif and #else branches if condition was met
            found_elif_or_else = False
            for child in root_node.children:
                # Skip directive keywords themselves
                if not child.is_named:
                    continue

                # If we found #elif or #else and our condition was met, skip their content
                if child.type in ["preproc_elif", "preproc_else"]:
                    if condition_met:
                        # Our condition was true, skip alternative branches
                        continue
                    found_elif_or_else = True

                # If this is an elif, evaluate its condition
                if child.type == "preproc_elif":
                    # Let the elif handle its own recursion
                    root_node, node_list, graph_node_list, records = get_nodes(
                        root_node=child,
                        node_list=node_list,
                        graph_node_list=graph_node_list,
                        index=index,
                        records=records,
                        macro_definitions=macro_definitions,
                    )
                elif child.type == "preproc_else":
                    # Process else content only if no previous condition was met
                    if not condition_met:
                        for else_child in child.children:
                            if else_child.is_named:
                                root_node, node_list, graph_node_list, records = get_nodes(
                                    root_node=else_child,
                                    node_list=node_list,
                                    graph_node_list=graph_node_list,
                                    index=index,
                                    records=records,
                                    macro_definitions=macro_definitions,
                                )
                elif condition_met:
                    # Process this child if condition is met
                    root_node, node_list, graph_node_list, records = get_nodes(
                        root_node=child,
                        node_list=node_list,
                        graph_node_list=graph_node_list,
                        index=index,
                        records=records,
                        macro_definitions=macro_definitions,
                    )

    elif root_node.type == "preproc_else":
        # Don't process else independently - it's handled by parent #if
        pass

    elif root_node.type in ["preproc_include", "preproc_def", "preproc_function_def", "preproc_call"]:
        # These are non-conditional preprocessor directives
        # Don't traverse into their children (already handled above for #define)
        pass

    else:
        # Normal node - process all children
        for child in root_node.children:
            root_node, node_list, graph_node_list, records = get_nodes(
                root_node=child,
                node_list=node_list,
                graph_node_list=graph_node_list,
                index=index,
                records=records,
                macro_definitions=macro_definitions,
            )

    return root_node, node_list, graph_node_list, records
