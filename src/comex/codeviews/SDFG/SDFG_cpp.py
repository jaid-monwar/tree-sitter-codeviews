import copy
import time
from collections import defaultdict

import networkx as nx
from deepdiff import DeepDiff
from loguru import logger

from ...utils.cpp_nodes import statement_types
from ...utils.src_parser import traverse_tree

# C++ node type definitions
assignment = ["assignment_expression"]
def_statement = ["init_declarator"]
declaration_statement = ["declaration"]
increment_statement = ["update_expression"]
variable_type = ['identifier', 'this']
function_calls = ["call_expression"]
method_calls = ["call_expression"]  # In C++, both functions and methods use call_expression
literal_types = ["number_literal", "string_literal", "char_literal", "raw_string_literal",
                 "true", "false", "nullptr", "null"]

# Input functions that define their pointer/reference arguments
input_functions = ["scanf", "gets", "fgets", "getline", "fscanf", "sscanf",
                   "fread", "read", "recv", "recvfrom", "getchar", "fgetc",
                   "cin", "std::cin"]  # Add C++ iostream input

# Helpers
inner_types = ["declaration", "expression_statement"]
handled_types = (assignment + def_statement + increment_statement +
                function_calls + ["function_definition", "return_statement",
                                 "for_statement", "for_range_loop", "switch_statement"])

debug = False


def st(child):
    """Get text from AST node"""
    if child is None:
        return ""
    else:
        return child.text.decode()


def get_index(node, index):
    """Get unique index for AST node"""
    try:
        return index[(node.start_point, node.end_point, node.type)]
    except:
        return None


def read_index(index, idx):
    """Get AST node key from index value"""
    return list(index.keys())[list(index.values()).index(idx)]


def scope_check(parent_scope, child_scope):
    """
    Check if a definition's scope can reach a use's scope.

    A definition at scope [0, 1, 2] can reach uses at:
    - [0, 1, 2] (same scope)
    - [0, 1, 2, 3] (nested scope)

    But NOT:
    - [0, 1] (parent scope)
    - [0, 1, 3] (sibling scope)
    """
    for p in parent_scope:
        if p not in child_scope:
            return False
    return True


def set_add(lst, item):
    """Add item to list if not already present (set-like behavior)"""
    for entry in lst:
        if item == entry:
            return
    lst.append(item)


def set_union(first_list, second_list):
    """Union of two lists (set-like)"""
    resulting_list = list(first_list)
    resulting_list.extend(x for x in second_list if x not in resulting_list)
    return resulting_list


def set_difference(first_list, second_list):
    """Difference of two lists (set-like)"""
    return [item for item in first_list if item not in second_list]


def return_first_parent_of_types(node, parent_types, stop_types=None):
    """Find first parent of given types"""
    if stop_types is None:
        stop_types = []

    if node.type in parent_types:
        return node

    while node.parent is not None:
        if node.type in stop_types:
            return None
        if node.parent.type in parent_types:
            return node.parent
        node = node.parent

    return None


def recursively_get_children_of_types(node, st_types, check_list=None,
                                     index=None, result=None, stop_types=None):
    """Recursively find child nodes of given types"""
    if isinstance(st_types, str):
        st_types = [st_types]
    if stop_types is None:
        stop_types = []
    if result is None:
        result = []

    if node.type in stop_types:
        return result

    # Filter children by type and symbol table
    if check_list and index:
        result.extend([
            child for child in node.children
            if child.type in st_types and
               get_index(child, index) in check_list
        ])
    else:
        result.extend([
            child for child in node.children
            if child.type in st_types
        ])

    # Recurse on named children
    for child in node.named_children:
        if child.type not in stop_types:
            result = recursively_get_children_of_types(
                child, st_types, result=result, stop_types=stop_types,
                index=index, check_list=check_list
            )

    return result


class Identifier:
    """Represents a variable at a specific line with scope information"""

    def __init__(self, parser, node, line=None, declaration=False, full_ref=None, method_call=False):
        self.core = st(node)
        self.unresolved_name = st(full_ref) if full_ref else st(node)
        self.name = self._resolve_name(node, full_ref, parser)
        self.line = line
        self.declaration = declaration
        self.method_call = method_call
        self.satisfied = method_call  # Method calls are initially satisfied

        # Get parent class/struct if this is a member
        class_node = return_first_parent_of_types(node, ["class_specifier", "struct_specifier"])
        self.parent_class = None
        if class_node is not None:
            class_name_node = None
            for child in class_node.children:
                if child.type == "type_identifier":
                    class_name_node = child
                    break
            if class_name_node:
                self.parent_class = st(class_name_node)

        # Get scope information from parser
        variable_index = get_index(node, parser.index)
        if variable_index and variable_index in parser.symbol_table["scope_map"]:
            self.variable_scope = parser.symbol_table["scope_map"][variable_index]
            if variable_index in parser.declaration_map:
                decl_index = parser.declaration_map[variable_index]
                self.scope = parser.symbol_table["scope_map"].get(decl_index, [0])
            else:
                self.scope = [0]  # Global scope

            # For declarations, scope should be where it's visible
            if declaration:
                self.scope = self.variable_scope
        else:
            self.variable_scope = [0]
            self.scope = [0]

        # Get real line number
        if line is not None:
            self.real_line_no = read_index(parser.index, line)[0][0]

    def _resolve_name(self, node, full_ref, parser):
        """Resolve identifier name for C++"""
        if full_ref is None:
            return st(node)

        # Handle field access: obj.field
        if full_ref.type == "field_expression":
            # Get the object and field
            argument = full_ref.child_by_field_name("argument")
            field = full_ref.child_by_field_name("field")

            # Handle chained field access (a.b.c)
            if argument:
                arg_text = st(argument)
                field_text = st(field) if field else ""
                return arg_text + "." + field_text
            return st(full_ref)

        # Handle pointer member access: obj->field (same as obj.field for DFG)
        if full_ref.type == "pointer_expression":
            arg = full_ref.child_by_field_name("argument")
            return "*" + st(arg) if arg else st(full_ref)

        # Handle array subscript: arr[i]
        if full_ref.type == "subscript_expression":
            arg = full_ref.child_by_field_name("argument")
            return st(arg) if arg else st(full_ref)

        # Handle reference: &x (address-of)
        if full_ref.type == "unary_expression":
            # Check if this is an address-of
            for child in full_ref.children:
                if child.type == "&":
                    arg = full_ref.child_by_field_name("argument")
                    return st(arg) if arg else st(full_ref)

        # Handle qualified identifier: std::cout, MyClass::staticVar
        if full_ref.type == "qualified_identifier":
            return st(full_ref)

        # Handle this pointer
        if st(node) == "this":
            return "this"

        return st(node)

    def __eq__(self, other):
        return (self.name == other.name and
                self.line == other.line and
                sorted(self.scope) == sorted(other.scope) and
                self.method_call == other.method_call)

    def __hash__(self):
        return hash((self.name, self.line, str(self.scope), self.method_call))

    def __str__(self):
        result = [self.name]
        if self.line:
            result += [str(self.real_line_no)]
            result += ['|'.join(map(str, self.scope))]
        else:
            result += ["?"]
        if self.method_call:
            result += ["()"]
        return f"{{{','.join(result)}}}"


class Literal:
    """Represents a literal constant (number, string, etc.) as a data flow source"""

    def __init__(self, parser, node, line=None):
        self.core = st(node)
        self.name = f"LITERAL_{st(node)}"
        self.value = st(node)
        self.line = line
        self.declaration = True
        self.satisfied = False
        self.scope = [0]
        self.variable_scope = [0]
        self.method_call = False

        if line is not None:
            self.real_line_no = read_index(parser.index, line)[0][0]

    def __eq__(self, other):
        return (self.name == other.name and
                self.line == other.line)

    def __hash__(self):
        return hash((self.name, self.line))

    def __str__(self):
        result = [f"Literal({self.value})"]
        if self.line:
            result += [str(self.real_line_no)]
        else:
            result += ["?"]
        return f"{{{','.join(result)}}}"


def extract_identifier_from_declarator(declarator_node):
    """Extract identifier from declarator (may be wrapped in pointer/array/reference)"""
    if declarator_node.type == "identifier":
        return declarator_node
    elif declarator_node.type == "pointer_declarator":
        for child in declarator_node.children:
            if child.type in ["identifier", "pointer_declarator", "array_declarator", "reference_declarator"]:
                return extract_identifier_from_declarator(child)
    elif declarator_node.type == "reference_declarator":
        for child in declarator_node.children:
            if child.type in ["identifier", "pointer_declarator", "array_declarator", "reference_declarator"]:
                return extract_identifier_from_declarator(child)
    elif declarator_node.type == "array_declarator":
        if declarator_node.children:
            return extract_identifier_from_declarator(declarator_node.children[0])
    elif declarator_node.type == "function_declarator":
        for child in declarator_node.children:
            if child.type in ["identifier", "pointer_declarator", "parenthesized_declarator"]:
                return extract_identifier_from_declarator(child)
    elif declarator_node.type == "parenthesized_declarator":
        for child in declarator_node.children:
            if child.type in ["identifier", "pointer_declarator", "array_declarator", "reference_declarator"]:
                return extract_identifier_from_declarator(child)
    return None


def extract_param_identifier(param_node):
    """Extract identifier from parameter_declaration"""
    for child in param_node.children:
        if child.type == "identifier":
            return child
        elif child.type in ["pointer_declarator", "array_declarator",
                           "function_declarator", "reference_declarator"]:
            return extract_identifier_from_declarator(child)
    return None


def extract_operator_text(assign_node, left_node, right_node):
    """Extract operator from assignment (=, +=, -=, etc.)"""
    left_text = left_node.text
    right_text = right_node.text
    operator_bytes = (
        assign_node.text.split(left_text, 1)[-1]
        .rsplit(right_text, 1)[0]
        .strip()
    )
    return operator_bytes.decode()


def add_entry(parser, rda_table, statement_id, used=None, defined=None,
              declaration=False, core=None, method_call=False):
    """
    Add variable USE or DEF to RDA table.

    Args:
        parser: C++ parser
        rda_table: RDA table
        statement_id: Statement where this occurs
        used: Variable being used (read)
        defined: Variable being defined (written)
        declaration: True if declaration
        core: Full reference node
        method_call: True if this is a method call
    """
    if statement_id not in rda_table:
        rda_table[statement_id] = defaultdict(list)

    if not used and not defined:
        return

    current_node = used or defined
    if core is None:
        core = current_node

    # Handle literal constants
    if current_node.type in literal_types:
        if used:
            set_add(rda_table[statement_id]["use"],
                   Literal(parser, current_node, statement_id))
        return

    # Handle field access: obj.field or obj->field
    if current_node.type == "field_expression":
        argument = current_node.child_by_field_name("argument")

        if defined is not None:
            set_add(rda_table[statement_id]["def"],
                   Identifier(parser, argument, statement_id,
                            full_ref=current_node, declaration=declaration,
                            method_call=method_call))
        else:
            set_add(rda_table[statement_id]["use"],
                   Identifier(parser, argument, full_ref=current_node,
                            method_call=method_call))
        return

    # Handle address-of operator: &x
    if used and used.type == "unary_expression":
        operator = None
        argument = None
        for child in used.children:
            if child.type == "&":
                operator = child
            elif child.is_named:
                argument = child

        if operator is not None and argument is not None:
            if argument.type in variable_type:
                arg_index = get_index(argument, parser.index)
                if arg_index and arg_index in parser.symbol_table["scope_map"]:
                    set_add(rda_table[statement_id]["use"],
                           Identifier(parser, argument, full_ref=argument))
            return

    # Handle pointer dereference: *ptr
    if current_node.type == "pointer_expression":
        pointer = current_node.child_by_field_name("argument")

        # Track USE of the base pointer
        pointer_index = get_index(pointer, parser.index)
        if pointer_index and pointer_index in parser.symbol_table["scope_map"]:
            set_add(rda_table[statement_id]["use"],
                   Identifier(parser, pointer, full_ref=pointer))

        # Track DEF/USE of dereferenced value
        if defined is not None:
            set_add(rda_table[statement_id]["def"],
                   Identifier(parser, pointer, statement_id,
                            full_ref=core, declaration=declaration))
        else:
            set_add(rda_table[statement_id]["use"],
                   Identifier(parser, pointer, full_ref=core))
        return

    # Handle array subscript: arr[i]
    if current_node.type == "subscript_expression":
        array = current_node.child_by_field_name("argument")
        index_expr = current_node.child_by_field_name("index")

        # C++ uses subscript_argument_list instead of direct index field
        if index_expr is None:
            for child in current_node.children:
                if child.type == "subscript_argument_list":
                    # The subscript_argument_list contains the index expression(s)
                    if child.named_children:
                        index_expr = child.named_children[0]
                    break

        # Conservative: both use and define the array
        if defined is not None:
            set_add(rda_table[statement_id]["def"],
                   Identifier(parser, array, statement_id,
                            full_ref=core, declaration=declaration))
        set_add(rda_table[statement_id]["use"],
               Identifier(parser, array, full_ref=core))

        # Track index expression
        if index_expr:
            if index_expr.type in variable_type:
                index_id = get_index(index_expr, parser.index)
                if index_id and index_id in parser.symbol_table["scope_map"]:
                    set_add(rda_table[statement_id]["use"],
                           Identifier(parser, index_expr, full_ref=index_expr))
            elif index_expr.type in literal_types:
                set_add(rda_table[statement_id]["use"],
                       Literal(parser, index_expr, statement_id))
            else:
                identifiers_in_index = recursively_get_children_of_types(
                    index_expr, variable_type + ["field_expression"],
                    index=parser.index,
                    check_list=parser.symbol_table["scope_map"]
                )
                for identifier in identifiers_in_index:
                    set_add(rda_table[statement_id]["use"],
                           Identifier(parser, identifier, full_ref=identifier))
                literals_in_index = recursively_get_children_of_types(
                    index_expr, literal_types, index=parser.index
                )
                for literal in literals_in_index:
                    set_add(rda_table[statement_id]["use"],
                           Literal(parser, literal, statement_id))
        return

    # Handle qualified identifiers: std::cout, MyClass::member
    if current_node.type == "qualified_identifier":
        # For qualified identifiers, treat as a single entity
        # The parser should have already resolved these in the symbol table
        node_index = get_index(current_node, parser.index)
        if node_index is None or node_index not in parser.symbol_table["scope_map"]:
            return

        if defined is not None:
            set_add(rda_table[statement_id]["def"],
                   Identifier(parser, current_node, statement_id,
                            full_ref=core, declaration=declaration,
                            method_call=method_call))
        else:
            set_add(rda_table[statement_id]["use"],
                   Identifier(parser, current_node, full_ref=core,
                            method_call=method_call))
        return

    # Handle 'this' pointer
    if current_node.type == "this":
        if used:
            set_add(rda_table[statement_id]["use"],
                   Identifier(parser, current_node, full_ref=current_node))
        return

    # Simple identifier
    node_index = get_index(current_node, parser.index)
    if node_index is None or node_index not in parser.symbol_table["scope_map"]:
        return

    if defined is not None:
        set_add(rda_table[statement_id]["def"],
               Identifier(parser, defined, statement_id,
                        full_ref=core, declaration=declaration,
                        method_call=method_call))
    else:
        set_add(rda_table[statement_id]["use"],
               Identifier(parser, used, full_ref=core,
                        method_call=method_call))


def build_rda_table(parser, CFG_results):
    """
    Build RDA table by traversing AST and tracking DEF/USE.

    Combines C and Java approaches for C++ support.

    Returns:
        rda_table: Dict mapping statement_id to {"def": set, "use": set}
    """
    rda_table = {}
    index = parser.index
    tree = parser.tree

    inner_types_local = ["parenthesized_expression", "binary_expression", "unary_expression"]
    handled_cases = ["compound_statement", "translation_unit", "class_specifier",
                     "struct_specifier", "namespace_definition"]

    # Traverse tree, stopping descent at identifiers
    for root_node in traverse_tree(tree, variable_type):
        if not root_node.is_named:
            continue

        # 1. Handle return statements
        if root_node.type == "return_statement":
            parent_id = get_index(root_node, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue
            vars_used = recursively_get_children_of_types(
                root_node, variable_type + ["field_expression"],
                index=parser.index,
                check_list=parser.symbol_table["scope_map"]
            )
            for var in vars_used:
                add_entry(parser, rda_table, parent_id, used=var)

        # 2. Handle variable declarations (init_declarator)
        elif root_node.type in def_statement:
            parent_statement = return_first_parent_of_types(
                root_node, statement_types["node_list_type"]
            )
            if parent_statement is None:
                continue

            parent_id = get_index(parent_statement, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                if parent_statement and parent_statement.type in inner_types_local:
                    parent_statement = return_first_parent_of_types(
                        parent_statement, statement_types["node_list_type"]
                    )
                    parent_id = get_index(parent_statement, index)
                elif parent_statement.type in handled_cases:
                    continue
                else:
                    continue

            # Extract variable name from declarator
            declarator = root_node.child_by_field_name("declarator")
            if declarator is None and len(root_node.children) > 0:
                declarator = root_node.children[0]

            var_identifier = extract_identifier_from_declarator(declarator)

            if var_identifier:
                add_entry(parser, rda_table, parent_id,
                         defined=var_identifier, declaration=True)

            # Extract initializer
            initializer = root_node.child_by_field_name("value")
            if initializer:
                if initializer.type in variable_type + ["field_expression", "pointer_expression",
                                                       "subscript_expression", "unary_expression"] + literal_types:
                    add_entry(parser, rda_table, parent_id, used=initializer)
                else:
                    vars_used = recursively_get_children_of_types(
                        initializer, variable_type + ["field_expression"],
                        index=parser.index,
                        check_list=parser.symbol_table["scope_map"]
                    )
                    for var in vars_used:
                        add_entry(parser, rda_table, parent_id, used=var)
                    literals_used = recursively_get_children_of_types(
                        initializer, literal_types, index=parser.index
                    )
                    for literal in literals_used:
                        add_entry(parser, rda_table, parent_id, used=literal)

        # 2a. Handle uninitialized declarations
        elif root_node.type in declaration_statement:
            parent_id = get_index(root_node, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue

            has_init_declarator = any(
                child.type == "init_declarator" for child in root_node.named_children
            )
            if has_init_declarator:
                continue

            for child in root_node.named_children:
                if child.type == "identifier":
                    child_id = get_index(child, index)
                    if child_id and child_id in parser.symbol_table["scope_map"]:
                        add_entry(parser, rda_table, parent_id,
                                 defined=child, declaration=True)
                elif child.type in ["pointer_declarator", "array_declarator", "reference_declarator"]:
                    var_identifier = extract_identifier_from_declarator(child)
                    if var_identifier:
                        var_id = get_index(var_identifier, index)
                        if var_id and var_id in parser.symbol_table["scope_map"]:
                            add_entry(parser, rda_table, parent_id,
                                     defined=var_identifier, declaration=True)

        # 3. Handle assignments
        elif root_node.type in assignment:
            parent_statement = return_first_parent_of_types(
                root_node, statement_types["node_list_type"]
            )
            if parent_statement is None:
                continue

            parent_id = get_index(parent_statement, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                if parent_statement and parent_statement.type in inner_types_local:
                    parent_statement = return_first_parent_of_types(
                        parent_statement, statement_types["node_list_type"]
                    )
                    parent_id = get_index(parent_statement, index)
                elif parent_statement.type in handled_cases:
                    continue
                else:
                    continue

            left_node = root_node.child_by_field_name("left")
            right_node = root_node.child_by_field_name("right")

            if left_node is None or right_node is None:
                continue

            operator_text = extract_operator_text(root_node, left_node, right_node)

            # Compound assignments: x += y means USE x first, then DEFINE
            if operator_text != "=":
                add_entry(parser, rda_table, parent_id, used=left_node)

            # Left side is defined
            add_entry(parser, rda_table, parent_id, defined=left_node)

            # Right side is used
            if right_node.type in variable_type + ["field_expression", "pointer_expression",
                                                   "subscript_expression", "unary_expression"] + literal_types:
                add_entry(parser, rda_table, parent_id, used=right_node)
            else:
                vars_used = recursively_get_children_of_types(
                    right_node, variable_type + ["field_expression"],
                    index=parser.index,
                    check_list=parser.symbol_table["scope_map"]
                )
                for var in vars_used:
                    add_entry(parser, rda_table, parent_id, used=var)
                literals_used = recursively_get_children_of_types(
                    right_node, literal_types, index=parser.index
                )
                for literal in literals_used:
                    add_entry(parser, rda_table, parent_id, used=literal)

        # 4. Handle update expressions (i++, --i, etc.)
        elif root_node.type in increment_statement:
            parent_statement = return_first_parent_of_types(
                root_node, statement_types["node_list_type"]
            )
            if parent_statement is None:
                continue

            parent_id = get_index(parent_statement, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                if parent_statement and parent_statement.type in inner_types_local:
                    parent_statement = return_first_parent_of_types(
                        parent_statement, statement_types["node_list_type"]
                    )
                    parent_id = get_index(parent_statement, index)
                elif parent_statement.type in handled_cases:
                    continue
                else:
                    continue

            if root_node.type in variable_type + ["field_expression"]:
                add_entry(parser, rda_table, parent_id, used=root_node)
                add_entry(parser, rda_table, parent_id, defined=root_node)
            else:
                identifiers = recursively_get_children_of_types(
                    root_node, variable_type + ["field_expression"],
                    index=parser.index,
                    check_list=parser.symbol_table["scope_map"]
                )
                for identifier in identifiers:
                    add_entry(parser, rda_table, parent_id, used=identifier)
                    add_entry(parser, rda_table, parent_id, defined=identifier)

        # 5. Handle function/method calls
        elif root_node.type in function_calls:
            parent_statement = return_first_parent_of_types(
                root_node, statement_types["node_list_type"]
            )
            if parent_statement is None:
                continue

            parent_id = get_index(parent_statement, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                if parent_statement and parent_statement.type in inner_types_local:
                    parent_statement = return_first_parent_of_types(
                        parent_statement, statement_types["node_list_type"]
                    )
                    parent_id = get_index(parent_statement, index)
                elif parent_statement.type in handled_cases:
                    continue
                else:
                    continue

            # Get function being called
            function_node = root_node.child_by_field_name("function")
            function_name = None

            if function_node:
                function_name = st(function_node)

                # Track method calls on objects (obj.method())
                if function_node.type == "field_expression":
                    # This is a method call: obj.method()
                    # Track USE and potential DEF of the object
                    add_entry(parser, rda_table, parent_id, used=function_node, method_call=True)
                    add_entry(parser, rda_table, parent_id, defined=function_node, method_call=True)
                elif function_node.type in variable_type:
                    # Simple function call
                    add_entry(parser, rda_table, parent_id, used=function_node, method_call=True)

            # Check if this is an input function
            is_input_function = function_name in input_functions or \
                               (function_name and any(inp in function_name for inp in ["cin", "scanf"]))

            # Process arguments
            args_node = root_node.child_by_field_name("arguments")
            if args_node:
                for arg in args_node.named_children:
                    # For input functions, special handling
                    if is_input_function:
                        # Check for &var or pointer arguments - these are definitions
                        if arg.type == "unary_expression":
                            # Check for address-of
                            has_address_of = any(child.type == "&" for child in arg.children)
                            if has_address_of:
                                inner_arg = arg.child_by_field_name("argument")
                                if inner_arg:
                                    if inner_arg.type in variable_type:
                                        add_entry(parser, rda_table, parent_id,
                                                 defined=inner_arg, declaration=False)
                                    elif inner_arg.type in ["field_expression", "subscript_expression"]:
                                        add_entry(parser, rda_table, parent_id,
                                                 defined=inner_arg, declaration=False)
                                continue
                        # References in input functions are also definitions
                        if arg.type in variable_type + ["field_expression"]:
                            # Could be a reference parameter
                            add_entry(parser, rda_table, parent_id, defined=arg, declaration=False)
                            continue

                    # Regular arguments are USEs
                    if arg.type in variable_type + ["field_expression"]:
                        add_entry(parser, rda_table, parent_id, used=arg)
                    elif arg.type in literal_types:
                        add_entry(parser, rda_table, parent_id, used=arg)
                    else:
                        identifiers_used = recursively_get_children_of_types(
                            arg, variable_type + ["field_expression"],
                            index=parser.index,
                            check_list=parser.symbol_table["scope_map"]
                        )
                        for identifier in identifiers_used:
                            add_entry(parser, rda_table, parent_id, used=identifier)
                        literals_used = recursively_get_children_of_types(
                            arg, literal_types, index=parser.index
                        )
                        for literal in literals_used:
                            add_entry(parser, rda_table, parent_id, used=literal)

        # 6. Handle function definitions (parameters)
        elif root_node.type == "function_definition":
            parent_id = get_index(root_node, index)
            if parent_id is None:
                continue

            # Find parameters
            declarator = root_node.child_by_field_name("declarator")
            if declarator:
                # Navigate through pointer/reference declarators if needed
                func_declarator = declarator
                while func_declarator and func_declarator.type in ["pointer_declarator", "reference_declarator"]:
                    for child in func_declarator.children:
                        if child.type == "function_declarator":
                            func_declarator = child
                            break
                    else:
                        break

                if func_declarator and func_declarator.type == "function_declarator":
                    param_list = func_declarator.child_by_field_name('parameters')
                    if param_list:
                        for param in param_list.named_children:
                            if param.type in ["parameter_declaration", "optional_parameter_declaration"]:
                                param_id = extract_param_identifier(param)
                                if param_id:
                                    add_entry(parser, rda_table, parent_id,
                                            defined=param_id, declaration=True)

        # 7. Handle control flow conditions
        elif root_node.type == "if_statement":
            parent_id = get_index(root_node, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue

            condition = root_node.child_by_field_name("condition")
            if condition:
                identifiers_used = recursively_get_children_of_types(
                    condition, variable_type + ["field_expression"],
                    index=parser.index,
                    check_list=parser.symbol_table["scope_map"]
                )
                for identifier in identifiers_used:
                    add_entry(parser, rda_table, parent_id, used=identifier)

        elif root_node.type == "while_statement":
            parent_id = get_index(root_node, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue

            condition = root_node.child_by_field_name("condition")
            if condition:
                identifiers_used = recursively_get_children_of_types(
                    condition, variable_type + ["field_expression"],
                    index=parser.index,
                    check_list=parser.symbol_table["scope_map"]
                )
                for identifier in identifiers_used:
                    add_entry(parser, rda_table, parent_id, used=identifier)

        elif root_node.type == "for_statement":
            parent_id = get_index(root_node, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue

            condition = root_node.child_by_field_name("condition")
            if condition:
                identifiers_used = recursively_get_children_of_types(
                    condition, variable_type + ["field_expression"],
                    index=parser.index,
                    check_list=parser.symbol_table["scope_map"]
                )
                for identifier in identifiers_used:
                    add_entry(parser, rda_table, parent_id, used=identifier)

        elif root_node.type == "for_range_loop":
            parent_id = get_index(root_node, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue

            # Range-based for: for (auto x : container)
            declarator = root_node.child_by_field_name("declarator")
            if declarator:
                # Define the loop variable
                var_id = extract_identifier_from_declarator(declarator)
                if var_id:
                    add_entry(parser, rda_table, parent_id, defined=var_id, declaration=True)

            # Use the range expression
            range_expr = root_node.child_by_field_name("right")
            if range_expr:
                if range_expr.type in variable_type + ["field_expression"]:
                    add_entry(parser, rda_table, parent_id, used=range_expr)
                else:
                    identifiers_used = recursively_get_children_of_types(
                        range_expr, variable_type + ["field_expression"],
                        index=parser.index,
                        check_list=parser.symbol_table["scope_map"]
                    )
                    for identifier in identifiers_used:
                        add_entry(parser, rda_table, parent_id, used=identifier)

        elif root_node.type == "do_statement":
            # The "do" keyword itself doesn't use variables
            pass

        # Handle do-while condition
        elif (root_node.type == "parenthesized_expression" and
              root_node.parent is not None and
              root_node.parent.type == "do_statement"):
            parent_id = get_index(root_node, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue

            identifiers_used = recursively_get_children_of_types(
                root_node, variable_type + ["field_expression"],
                index=parser.index,
                check_list=parser.symbol_table["scope_map"]
            )
            for identifier in identifiers_used:
                add_entry(parser, rda_table, parent_id, used=identifier)

        elif root_node.type == "switch_statement":
            parent_id = get_index(root_node, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue

            condition = root_node.child_by_field_name("condition")
            if condition:
                identifiers_used = recursively_get_children_of_types(
                    condition, variable_type + ["field_expression"],
                    index=parser.index,
                    check_list=parser.symbol_table["scope_map"]
                )
                for identifier in identifiers_used:
                    add_entry(parser, rda_table, parent_id, used=identifier)

        # 8. Handle lambda expressions
        elif root_node.type == "lambda_expression":
            parent_id = get_index(root_node, index)
            if parent_id is None:
                continue

            # Handle lambda captures [x, &y, =]
            # Look for lambda_capture_specifier
            for child in root_node.children:
                if child.type == "lambda_capture_specifier":
                    # Process captured variables
                    for capture in child.named_children:
                        if capture.type in variable_type:
                            # Captured variable is used
                            add_entry(parser, rda_table, parent_id, used=capture)

        # 9. Handle exception handling
        elif root_node.type == "catch_clause":
            parent_id = get_index(root_node, index)
            if parent_id is None:
                continue

            # Define the exception variable
            for child in root_node.children:
                if child.type == "parameter_list":
                    for param in child.named_children:
                        if param.type == "parameter_declaration":
                            param_id = extract_param_identifier(param)
                            if param_id:
                                add_entry(parser, rda_table, parent_id,
                                        defined=param_id, declaration=True)

        elif root_node.type == "throw_statement":
            parent_id = get_index(root_node, index)
            if parent_id is None:
                continue

            # Use variables in throw expression
            identifiers_used = recursively_get_children_of_types(
                root_node, variable_type + ["field_expression"],
                index=parser.index,
                check_list=parser.symbol_table["scope_map"]
            )
            for identifier in identifiers_used:
                add_entry(parser, rda_table, parent_id, used=identifier)

        # 10. Catch-all: handle any other identifiers as USEs
        else:
            if root_node.type not in variable_type:
                continue

            # Skip identifiers in do-while condition (handled above)
            in_do_while_condition = False
            temp_parent = root_node.parent
            while temp_parent is not None:
                if (temp_parent.type == "parenthesized_expression" and
                    temp_parent.parent is not None and
                    temp_parent.parent.type == "do_statement"):
                    in_do_while_condition = True
                    break
                temp_parent = temp_parent.parent

            if in_do_while_condition:
                continue

            # Find the statement this identifier belongs to
            handled_types_local = (def_statement + assignment + increment_statement +
                                  function_calls + ["return_statement", "lambda_expression",
                                                   "catch_clause", "throw_statement"])
            parent_statement = return_first_parent_of_types(
                root_node,
                statement_types["non_control_statement"] + statement_types["control_statement"],
                stop_types=statement_types.get("statement_holders", []) + handled_types_local
            )

            if parent_statement is None:
                continue

            parent_id = get_index(parent_statement, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue

            # This identifier is a USE
            add_entry(parser, rda_table, parent_id, used=root_node)

    return rda_table


def start_rda(index, rda_table, cfg_graph, pre_solve=False):
    """
    Perform Reaching Definitions Analysis using fixed-point iteration.

    Algorithm:
        Initialize all IN/OUT to empty
        Repeat until convergence:
            For each statement s:
                IN[s] = union of OUT[p] for predecessors p
                OUT[s] = (IN[s] - KILL[s]) ∪ DEF[s]
    """
    graph = copy.deepcopy(cfg_graph)
    if pre_solve:
        remove_edges = []
        for edge in graph.edges:
            edge_data = graph.edges[edge]
            if "label" in edge_data and edge_data["label"] in \
               ["method_call", "method_return", "class_return", "constructor_call"]:
                remove_edges.append(edge)
        graph.remove_edges_from(remove_edges)

    cfg = graph
    nodes = graph.nodes

    # Initialize
    old_result = {}
    for node in nodes:
        old_result[node] = {"IN": set(), "OUT": set()}

    new_result = copy.deepcopy(old_result)
    iteration = 0

    # Fixed-point iteration
    while True:
        iteration += 1

        for node in nodes:
            # Collect predecessors
            predecessors = [s for (s, t) in cfg.in_edges(node)]

            # IN[node] = union of OUT[pred]
            in_set = set()
            for pred in predecessors:
                in_set = in_set.union(old_result[pred]["OUT"])

            new_result[node]["IN"] = in_set

            # Get DEF[node]
            def_info = rda_table[node]["def"] if node in rda_table else set()
            names_defined = [d.name for d in def_info]

            # OUT[node] = (IN[node] - KILL[node]) ∪ DEF[node]
            surviving_defs = set()
            for incoming_def in in_set:
                if incoming_def.name not in names_defined:
                    surviving_defs.add(incoming_def)

            new_result[node]["OUT"] = surviving_defs.union(def_info)

        # Check convergence
        ddiff = DeepDiff(old_result, new_result, ignore_order=True)
        if ddiff == {}:
            if debug:
                logger.info("RDA: Converged in {} iterations", iteration)
            break

        old_result = copy.deepcopy(new_result)

    return new_result


def add_edge(final_graph, source, target, attrib=None):
    """Add edge to MultiDiGraph with attributes"""
    final_graph.add_edge(source, target)
    if attrib is not None:
        edge_keys = [k for u, v, k in final_graph.edges(keys=True) if u == source and v == target]
        if edge_keys:
            edge_key = max(edge_keys)
        else:
            edge_key = 0
        nx.set_edge_attributes(final_graph, {(source, target, edge_key): attrib})


def name_match_with_fields(name1, name2):
    """Check if two names match (handling field access)"""
    if name1 == name2:
        return True

    # One is prefix of other (field access)
    if name1.startswith(name2 + ".") or name2.startswith(name1 + "."):
        return True

    return False


def get_required_edges_from_def_to_use(index, cfg, rda_solution, rda_table,
                                       graph_nodes, processed_edges, properties):
    """
    Generate DFG edges from RDA solution.

    For each statement s:
        For each use u in USE[s]:
            For each def d in IN[s]:
                If d.name == u.name and scope_check(d.scope, u.scope):
                    Add edge: d.line → s
    """
    final_graph = copy.deepcopy(cfg)
    final_graph.remove_edges_from(list(final_graph.edges()))

    for node in graph_nodes:
        if node not in rda_table:
            continue

        use_info = rda_table[node]["use"]

        for used in use_info:
            # Literals are self-contained
            if isinstance(used, Literal):
                used.satisfied = True
                continue

            # Find reaching definitions
            for available_def in rda_solution[node]["IN"]:
                # Exact match
                if available_def.name == used.name:
                    if scope_check(available_def.scope, used.scope):
                        add_edge(final_graph, available_def.line, node,
                               {'dataflow_type': 'comesFrom',
                                'edge_type': 'DFG_edge',
                                'color': '#00A3FF',
                                'used_def': used.name})
                        used.satisfied = True

                # Partial match for field access
                elif "." in used.name or "." in available_def.name:
                    if name_match_with_fields(used.name, available_def.name):
                        if scope_check(available_def.scope, used.scope):
                            add_edge(final_graph, available_def.line, node,
                                   {'dataflow_type': 'comesFrom',
                                    'edge_type': 'DFG_edge',
                                    'color': '#00A3FF',
                                    'used_def': used.name})
                            used.satisfied = True

        # Optional: last_def edges
        if properties.get("last_def", False):
            killed_defs = rda_solution[node]["IN"] - rda_solution[node]["OUT"]
            for killed_def in killed_defs:
                node_type = read_index(index, node)[-1]
                def_node_type = read_index(index, killed_def.line)[-1]
                ignore_types = ['for_statement', 'for_range_loop', 'while_statement',
                               'if_statement', 'switch_statement']
                if node_type not in ignore_types and \
                   def_node_type not in ignore_types:
                    add_edge(final_graph, killed_def.line, node,
                           {'color': 'orange', 'dataflow_type': 'lastDef'})

    # Add function parameter/return edges
    for edge in processed_edges:
        add_edge(final_graph, edge[0], edge[1],
               {'dataflow_type': 'parameter', 'edge_type': 'DFG_edge'})

    return final_graph


def rda_cfg_map(rda_solution, CFG_results):
    """Create debug graph showing RDA info on CFG edges"""
    graph = copy.deepcopy(CFG_results.graph)

    for edge in list(graph.edges):
        out_set = rda_solution[edge[0]]["OUT"]
        in_set = rda_solution[edge[1]]["IN"]

        intersection = [d for d in out_set if d in in_set]

        if intersection:
            edge_data = graph.get_edge_data(*edge)
            edge_data['rda_info'] = ",".join([str(d) for d in intersection])
        else:
            graph.remove_edge(*edge)

    return graph


def dfg_cpp(properties, CFG_results):
    """
    Main driver for generating DFG for C++ programs.

    Combines C procedural features with Java OOP features.

    Args:
        properties: Configuration dict with DFG options
        CFG_results: CFG driver results with graph, parser, etc.

    Returns:
        (final_graph, debug_graph, rda_table, rda_solution)
    """
    parser = CFG_results.parser
    index = parser.index
    tree = parser.tree

    cfg_graph = copy.deepcopy(CFG_results.graph)
    node_list = CFG_results.node_list

    # Phase 1: Preprocess CFG for function/method calls
    processed_edges = []

    # Handle method returns
    for edge in list(cfg_graph.edges()):
        edge_data = cfg_graph.get_edge_data(*edge)
        if edge_data and len(edge_data) > 0:
            edge_data = edge_data[0]
            if edge_data.get("label") == "method_return":
                return_statement = node_list.get(read_index(index, edge[0]))
                if return_statement and return_statement.type == "return_statement":
                    if return_statement.named_children:
                        processed_edges.append(edge)

    # Phase 2: Build RDA table
    start_rda_init_time = time.time()
    rda_table = build_rda_table(parser, CFG_results)
    end_rda_init_time = time.time()

    # Phase 3: Run RDA
    start_rda_time = time.time()
    rda_solution = start_rda(index, rda_table, cfg_graph)
    end_rda_time = time.time()

    # Phase 4: Generate DFG edges
    final_graph = get_required_edges_from_def_to_use(
        index, cfg_graph, rda_solution, rda_table,
        cfg_graph.nodes, processed_edges, properties
    )

    if debug:
        logger.info("RDA init: {:.3f}s, RDA: {:.3f}s",
                   end_rda_init_time - start_rda_init_time,
                   end_rda_time - start_rda_time)

    # Create debug graph
    debug_graph = rda_cfg_map(rda_solution, CFG_results)

    return final_graph, debug_graph, rda_table, rda_solution
