import copy
import time
from collections import defaultdict

import networkx as nx
from deepdiff import DeepDiff
from loguru import logger

from ...utils.c_nodes import statement_types
from ...utils.src_parser import traverse_tree

# C-specific node type definitions
assignment = ["assignment_expression"]
def_statement = ["init_declarator"]
declaration_statement = ["declaration"]  # For uninitialized declarations
increment_statement = ["update_expression"]
variable_type = ['identifier']
function_calls = ["call_expression"]
literal_types = ["number_literal", "string_literal", "char_literal",
                 "true", "false", "null"]

# Input functions that define their pointer arguments
# These functions write to memory through pointer arguments
input_functions = ["scanf", "gets", "fgets", "getline", "fscanf", "sscanf",
                   "fread", "read", "recv", "recvfrom", "getchar", "fgetc"]

# Helpers
inner_types = ["declaration", "expression_statement"]
handled_types = (assignment + def_statement + increment_statement +
                function_calls + ["function_definition", "return_statement",
                                 "for_statement", "switch_statement"])

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

    def __init__(self, parser, node, line=None, declaration=False, full_ref=None):
        self.core = st(node)
        self.unresolved_name = st(full_ref) if full_ref else st(node)
        self.name = self._resolve_name(node, full_ref, parser)
        self.line = line
        self.declaration = declaration
        self.satisfied = False

        # Get scope information from parser
        variable_index = get_index(node, parser.index)
        if variable_index and variable_index in parser.symbol_table["scope_map"]:
            self.variable_scope = parser.symbol_table["scope_map"][variable_index]
            if variable_index in parser.declaration_map:
                decl_index = parser.declaration_map[variable_index]
                self.scope = parser.symbol_table["scope_map"].get(decl_index, [0])
            else:
                self.scope = [0]  # Global scope

            # CRITICAL FIX: For declarations (DEF), the scope used in reaching definitions
            # should be the variable_scope (where it's visible), not the declaration point
            # This prevents function parameters (visible only in function body [0, 1])
            # from reaching call sites in different functions (scope [0, 9, 10])
            if declaration:
                self.scope = self.variable_scope
        else:
            self.variable_scope = [0]
            self.scope = [0]

        # Get real line number
        if line is not None:
            self.real_line_no = read_index(parser.index, line)[0][0]

    def _resolve_name(self, node, full_ref, parser):
        """Resolve identifier name for C"""
        if full_ref is None:
            return st(node)

        # Handle struct field access: s.field
        if full_ref.type == "field_expression":
            obj = full_ref.child_by_field_name("argument")
            field = full_ref.child_by_field_name("field")
            return st(obj) + "." + st(field)

        # Handle pointer dereference: *ptr
        if full_ref.type == "pointer_expression":
            arg = full_ref.child_by_field_name("argument")
            return "*" + st(arg)  # Track dereferenced value

        # Handle array subscript: arr[i]
        if full_ref.type == "subscript_expression":
            arg = full_ref.child_by_field_name("argument")
            return st(arg)  # Use array name

        return st(node)

    def __eq__(self, other):
        return (self.name == other.name and
                self.line == other.line and
                sorted(self.scope) == sorted(other.scope))

    def __hash__(self):
        return hash((self.name, self.line, str(self.scope)))

    def __str__(self):
        result = [self.name]
        if self.line:
            result += [str(self.real_line_no)]
            result += ['|'.join(map(str, self.scope))]
        else:
            result += ["?"]
        return f"{{{','.join(result)}}}"


class Literal:
    """Represents a literal constant (number, string, etc.) as a data flow source"""

    def __init__(self, parser, node, line=None):
        self.core = st(node)
        self.name = f"LITERAL_{st(node)}"  # Prefix to distinguish from variables
        self.value = st(node)
        self.line = line
        self.declaration = True  # Literals are always "definitions"
        self.satisfied = False
        self.scope = [0]  # Literals have global scope
        self.variable_scope = [0]

        # Get real line number
        if line is not None:
            self.real_line_no = read_index(parser.index, line)[0][0]

    def __eq__(self, other):
        # Literals are equal if they're at the same line (different literal instances)
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
    """Extract identifier from declarator (may be wrapped in pointer/array)"""
    if declarator_node.type == "identifier":
        return declarator_node
    elif declarator_node.type == "pointer_declarator":
        # Recurse to find identifier inside
        for child in declarator_node.children:
            if child.type in ["identifier", "pointer_declarator", "array_declarator"]:
                return extract_identifier_from_declarator(child)
    elif declarator_node.type == "array_declarator":
        # First child is the identifier
        if declarator_node.children:
            return extract_identifier_from_declarator(declarator_node.children[0])
    elif declarator_node.type == "function_declarator":
        # For function pointers: int (*func_ptr)(int)
        for child in declarator_node.children:
            if child.type in ["identifier", "pointer_declarator", "parenthesized_declarator"]:
                return extract_identifier_from_declarator(child)
    elif declarator_node.type == "parenthesized_declarator":
        # For parenthesized declarators like (*ptr)
        for child in declarator_node.children:
            if child.type in ["identifier", "pointer_declarator", "array_declarator"]:
                return extract_identifier_from_declarator(child)
    return None


def extract_param_identifier(param_node):
    """Extract identifier from parameter_declaration"""
    for child in param_node.children:
        if child.type == "identifier":
            return child
        elif child.type in ["pointer_declarator", "array_declarator", "function_declarator"]:
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
              declaration=False, core=None):
    """
    Add variable USE or DEF to RDA table.

    Args:
        parser: C parser
        rda_table: RDA table
        statement_id: Statement where this occurs
        used: Variable being used (read)
        defined: Variable being defined (written)
        declaration: True if declaration
        core: Full reference node
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
        if used:  # Literals are always USEs (data sources)
            set_add(rda_table[statement_id]["use"],
                   Literal(parser, current_node, statement_id))
        return

    # Handle struct field access
    if current_node.type == "field_expression":
        if defined is not None:
            set_add(rda_table[statement_id]["def"],
                   Identifier(parser, current_node.child_by_field_name("argument"),
                            statement_id, full_ref=current_node,
                            declaration=declaration))
        else:
            set_add(rda_table[statement_id]["use"],
                   Identifier(parser, current_node.child_by_field_name("argument"),
                            full_ref=current_node))
        return

    # Handle address-of operator: &x
    if used and used.type == "unary_expression":
        # Check if this is an address-of expression
        operator = None
        argument = None
        for child in used.children:
            if child.type == "&":
                operator = child
            elif child.is_named:
                argument = child

        if operator is not None and argument is not None:
            # This is &x, which USEs x
            if argument.type in variable_type:
                arg_index = get_index(argument, parser.index)
                if arg_index and arg_index in parser.symbol_table["scope_map"]:
                    set_add(rda_table[statement_id]["use"],
                           Identifier(parser, argument, full_ref=argument))
            return

    # Handle pointer dereference: *ptr
    if current_node.type == "pointer_expression":
        pointer = current_node.child_by_field_name("argument")

        # Track USE of the base pointer (ptr) - needed to know the address
        pointer_index = get_index(pointer, parser.index)
        if pointer_index and pointer_index in parser.symbol_table["scope_map"]:
            set_add(rda_table[statement_id]["use"],
                   Identifier(parser, pointer, full_ref=pointer))

        # Track DEF/USE of the dereferenced value (*ptr)
        if defined is not None:
            set_add(rda_table[statement_id]["def"],
                   Identifier(parser, pointer, statement_id,
                            full_ref=core, declaration=declaration))
        else:
            set_add(rda_table[statement_id]["use"],
                   Identifier(parser, pointer, full_ref=core))
        return

    # Handle array subscript
    if current_node.type == "subscript_expression":
        array = current_node.child_by_field_name("argument")
        index_expr = current_node.child_by_field_name("index")

        # Conservative: both use and define the array
        if defined is not None:
            set_add(rda_table[statement_id]["def"],
                   Identifier(parser, array, statement_id,
                            full_ref=core, declaration=declaration))
        set_add(rda_table[statement_id]["use"],
               Identifier(parser, array, full_ref=core))

        # Track the index expression - this is crucial for loop-carried dependencies
        # Example: tortoise = in_arr[tortoise] uses tortoise in the index
        if index_expr:
            # If index is a simple identifier
            if index_expr.type in variable_type:
                index_id = get_index(index_expr, parser.index)
                if index_id and index_id in parser.symbol_table["scope_map"]:
                    set_add(rda_table[statement_id]["use"],
                           Identifier(parser, index_expr, full_ref=index_expr))
            # If index is a literal (like arr[0])
            elif index_expr.type in literal_types:
                set_add(rda_table[statement_id]["use"],
                       Literal(parser, index_expr, statement_id))
            else:
                # Recursively find all identifiers in the index expression
                # Example: arr[i + 1] or arr[func(x)]
                identifiers_in_index = recursively_get_children_of_types(
                    index_expr, variable_type + ["field_expression"],
                    index=parser.index,
                    check_list=parser.symbol_table["scope_map"]
                )
                for identifier in identifiers_in_index:
                    set_add(rda_table[statement_id]["use"],
                           Identifier(parser, identifier, full_ref=identifier))
                # Also track literals in index
                literals_in_index = recursively_get_children_of_types(
                    index_expr, literal_types,
                    index=parser.index
                )
                for literal in literals_in_index:
                    set_add(rda_table[statement_id]["use"],
                           Literal(parser, literal, statement_id))
        return

    # Simple identifier
    node_index = get_index(current_node, parser.index)
    if node_index is None or node_index not in parser.symbol_table["scope_map"]:
        return  # Not in symbol table

    if defined is not None:
        set_add(rda_table[statement_id]["def"],
               Identifier(parser, defined, statement_id,
                        full_ref=core, declaration=declaration))
    else:
        set_add(rda_table[statement_id]["use"],
               Identifier(parser, used, full_ref=core, declaration=declaration))


def build_rda_table(parser, CFG_results):
    """
    Build RDA table by traversing AST and tracking DEF/USE.

    Follows Java SDFG pattern: traverse tree stopping at identifiers,
    check each node's type to determine DEF/USE relationships.

    Returns:
        rda_table: Dict mapping statement_id to {"def": set, "use": set}
    """
    rda_table = {}
    index = parser.index
    tree = parser.tree

    # Define inner types that need special handling
    inner_types = ["parenthesized_expression", "binary_expression", "unary_expression"]
    handled_cases = ["compound_statement", "translation_unit"]

    # Traverse tree, stopping descent at identifiers
    # This yields ALL nodes but doesn't descend past identifiers
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
                if parent_statement and parent_statement.type in inner_types:
                    parent_statement = return_first_parent_of_types(
                        parent_statement, statement_types["node_list_type"]
                    )
                    parent_id = get_index(parent_statement, index)
                elif parent_statement.type in handled_cases:
                    continue
                else:
                    continue  # Skip if not in CFG

            # Extract variable name from declarator
            declarator = root_node.child_by_field_name("declarator")
            if declarator is None and len(root_node.children) > 0:
                declarator = root_node.children[0]

            var_identifier = extract_identifier_from_declarator(declarator)

            if var_identifier:
                add_entry(parser, rda_table, parent_id,
                         defined=var_identifier, declaration=True)

            # Extract initializer if present
            initializer = root_node.child_by_field_name("value")
            if initializer:
                # If initializer is directly an identifier, field_expression, pointer_expression, subscript_expression, literal, or unary_expression (for &x)
                if initializer.type in variable_type + ["field_expression", "pointer_expression", "subscript_expression", "unary_expression"] + literal_types:
                    add_entry(parser, rda_table, parent_id, used=initializer)
                else:
                    # Otherwise, recursively find identifiers AND field_expressions in the expression
                    vars_used = recursively_get_children_of_types(
                        initializer, variable_type + ["field_expression"],
                        index=parser.index,
                        check_list=parser.symbol_table["scope_map"]
                    )
                    for var in vars_used:
                        add_entry(parser, rda_table, parent_id, used=var)
                    # Also find literals
                    literals_used = recursively_get_children_of_types(
                        initializer, literal_types,
                        index=parser.index
                    )
                    for literal in literals_used:
                        add_entry(parser, rda_table, parent_id, used=literal)

        # 2a. Handle uninitialized declarations (int x;)
        # These don't have init_declarator nodes, identifier is direct child
        elif root_node.type in declaration_statement:
            # Only process if this is a statement-level declaration in CFG
            parent_id = get_index(root_node, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue

            # Skip if this declaration has init_declarator children
            # (those are handled by case 2 above)
            has_init_declarator = any(
                child.type == "init_declarator" for child in root_node.named_children
            )
            if has_init_declarator:
                continue

            # Find identifier children (uninitialized variables)
            for child in root_node.named_children:
                if child.type == "identifier":
                    # Check if this identifier is in the symbol table
                    child_id = get_index(child, index)
                    if child_id and child_id in parser.symbol_table["scope_map"]:
                        # This is a variable declaration: int x;
                        add_entry(parser, rda_table, parent_id,
                                 defined=child, declaration=True)
                elif child.type in ["pointer_declarator", "array_declarator"]:
                    # Handle int *ptr; or int arr[10];
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
                if parent_statement and parent_statement.type in inner_types:
                    parent_statement = return_first_parent_of_types(
                        parent_statement, statement_types["node_list_type"]
                    )
                    parent_id = get_index(parent_statement, index)
                elif parent_statement.type in handled_cases:
                    continue
                else:
                    continue  # Skip if not in CFG

            left_node = root_node.child_by_field_name("left")
            right_node = root_node.child_by_field_name("right")

            if left_node is None or right_node is None:
                continue

            # Get operator
            operator_text = extract_operator_text(root_node, left_node, right_node)

            # Compound assignments: x += y means USE x first, then DEFINE
            if operator_text != "=":
                add_entry(parser, rda_table, parent_id, used=left_node)

            # Left side is always defined
            add_entry(parser, rda_table, parent_id, defined=left_node)

            # Right side identifiers, field expressions, pointer expressions, subscript expressions, literals, and unary expressions are used
            if right_node.type in variable_type + ["field_expression", "pointer_expression", "subscript_expression", "unary_expression"] + literal_types:
                add_entry(parser, rda_table, parent_id, used=right_node)
            else:
                vars_used = recursively_get_children_of_types(
                    right_node, variable_type + ["field_expression"],
                    index=parser.index,
                    check_list=parser.symbol_table["scope_map"]
                )
                for var in vars_used:
                    add_entry(parser, rda_table, parent_id, used=var)
                # Also find literals
                literals_used = recursively_get_children_of_types(
                    right_node, literal_types,
                    index=parser.index
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
                if parent_statement and parent_statement.type in inner_types:
                    parent_statement = return_first_parent_of_types(
                        parent_statement, statement_types["node_list_type"]
                    )
                    parent_id = get_index(parent_statement, index)
                elif parent_statement.type in handled_cases:
                    continue
                else:
                    continue  # Skip if not in CFG

            # Get all identifiers in the update expression
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

        # 5. Handle function calls
        elif root_node.type in function_calls:
            parent_statement = return_first_parent_of_types(
                root_node, statement_types["node_list_type"]
            )
            if parent_statement is None:
                continue

            parent_id = get_index(parent_statement, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                if parent_statement and parent_statement.type in inner_types:
                    parent_statement = return_first_parent_of_types(
                        parent_statement, statement_types["node_list_type"]
                    )
                    parent_id = get_index(parent_statement, index)
                elif parent_statement.type in handled_cases:
                    continue
                else:
                    continue  # Skip if not in CFG

            # Check if this is an input function like scanf
            function_name = None
            if root_node.children and root_node.children[0].type == "identifier":
                function_name = st(root_node.children[0])

            is_input_function = function_name in input_functions

            # Process arguments
            for child in root_node.children[1:]:  # Skip function name
                # For input functions, pointer arguments are DEFINITIONs
                if is_input_function and child.type == "argument_list":
                    for arg in child.named_children:
                        # scanf("%d", &number) - the &number is a definition
                        if arg.type == "pointer_expression":
                            # This is &var - it DEFINES var
                            inner_arg = arg.child_by_field_name("argument")
                            if inner_arg:
                                # The variable being written to
                                if inner_arg.type in variable_type:
                                    add_entry(parser, rda_table, parent_id,
                                             defined=inner_arg, declaration=False)
                                elif inner_arg.type in ["field_expression", "subscript_expression"]:
                                    # scanf(&s.field) or scanf(&arr[i])
                                    add_entry(parser, rda_table, parent_id,
                                             defined=inner_arg, declaration=False)
                                    # Also USE the base variable for indexing
                                    if inner_arg.type == "subscript_expression":
                                        index_expr = inner_arg.child_by_field_name("index")
                                        if index_expr:
                                            vars_in_index = recursively_get_children_of_types(
                                                index_expr, variable_type + ["field_expression"],
                                                index=parser.index,
                                                check_list=parser.symbol_table["scope_map"]
                                            )
                                            for var in vars_in_index:
                                                add_entry(parser, rda_table, parent_id, used=var)
                        # Regular arguments (format string, other values) are USEs
                        elif arg.type in variable_type + ["field_expression"]:
                            add_entry(parser, rda_table, parent_id, used=arg)
                        elif arg.type in literal_types:
                            # Track literal constants
                            add_entry(parser, rda_table, parent_id, used=arg)
                        else:
                            # Find identifiers, field expressions, and literals
                            identifiers_used = recursively_get_children_of_types(
                                arg, variable_type + ["field_expression"],
                                index=parser.index,
                                check_list=parser.symbol_table["scope_map"]
                            )
                            for identifier in identifiers_used:
                                add_entry(parser, rda_table, parent_id, used=identifier)
                            # Also find literals
                            literals_used = recursively_get_children_of_types(
                                arg, literal_types,
                                index=parser.index
                            )
                            for literal in literals_used:
                                add_entry(parser, rda_table, parent_id, used=literal)
                # For non-input functions, all arguments are USEs (existing behavior)
                elif child.type in variable_type + ["field_expression"]:
                    add_entry(parser, rda_table, parent_id, used=child)
                elif child.type in literal_types:
                    # Track literal constants
                    add_entry(parser, rda_table, parent_id, used=child)
                else:
                    # Find identifiers, field expressions, and literals
                    identifiers_used = recursively_get_children_of_types(
                        child, variable_type + ["field_expression"],
                        index=parser.index,
                        check_list=parser.symbol_table["scope_map"]
                    )
                    for identifier in identifiers_used:
                        add_entry(parser, rda_table, parent_id, used=identifier)
                    # Also find literals
                    literals_used = recursively_get_children_of_types(
                        child, literal_types,
                        index=parser.index
                    )
                    for literal in literals_used:
                        add_entry(parser, rda_table, parent_id, used=literal)

        # 6. Handle function definitions (parameters)
        # Parameters are defined at the function_definition node, but we need to ensure
        # they get the correct scope from the symbol table (function-local, not global)
        elif root_node.type == "function_definition":
            parent_id = get_index(root_node, index)
            if parent_id is None:
                continue

            # Find and define parameters with their proper scope from symbol table
            for child in root_node.named_children:
                if child.type == "function_declarator":
                    param_list = child.child_by_field_name('parameters')
                    if param_list:
                        for param in param_list.named_children:
                            if param.type == "parameter_declaration":
                                param_id = extract_param_identifier(param)
                                if param_id:
                                    # Define parameter at function_definition node
                                    # The Identifier class will get the correct scope from symbol_table
                                    add_entry(parser, rda_table, parent_id,
                                            defined=param_id, declaration=True)
                    break

        # 7. Handle switch statements
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

        # 8. Handle for statements
        elif root_node.type == "for_statement":
            parent_id = get_index(root_node, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue

            # Handle condition (e.g., i < n)
            condition = root_node.child_by_field_name("condition")
            if condition:
                identifiers_used = recursively_get_children_of_types(
                    condition, variable_type + ["field_expression"],
                    index=parser.index,
                    check_list=parser.symbol_table["scope_map"]
                )
                for identifier in identifiers_used:
                    add_entry(parser, rda_table, parent_id, used=identifier)

        # 9. Handle while statements
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

        # 9a. Handle do-while condition (separate parenthesized_expression node)
        elif (root_node.type == "parenthesized_expression" and
              root_node.parent is not None and
              root_node.parent.type == "do_statement"):
            # The do-while condition is a separate CFG node (parenthesized_expression)
            # It's labeled as "while" in the CFG (see c_nodes.py:204-213)
            parent_id = get_index(root_node, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue

            # Extract identifiers used in the condition
            identifiers_used = recursively_get_children_of_types(
                root_node, variable_type + ["field_expression"],
                index=parser.index,
                check_list=parser.symbol_table["scope_map"]
            )
            for identifier in identifiers_used:
                add_entry(parser, rda_table, parent_id, used=identifier)

        # 9b. Handle do statements (just the "do" keyword - no variables used)
        elif root_node.type == "do_statement":
            # The "do" keyword itself doesn't use any variables
            # The condition is handled separately as a parenthesized_expression node
            pass

        # 10. Handle if statements
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

        # 10a. Handle ternary/conditional expressions: (condition)? true_expr : false_expr
        elif root_node.type == "conditional_expression":
            # Find the parent statement (usually expression_statement)
            parent_statement = return_first_parent_of_types(
                root_node, statement_types["node_list_type"]
            )
            if parent_statement is None:
                continue

            parent_id = get_index(parent_statement, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue

            # Extract identifiers from the condition
            condition = root_node.child_by_field_name("condition")
            if condition:
                # Direct identifier/field_expression in condition
                if condition.type in variable_type + ["field_expression"]:
                    add_entry(parser, rda_table, parent_id, used=condition)
                else:
                    # Recursively find all identifiers in the condition
                    identifiers_used = recursively_get_children_of_types(
                        condition, variable_type + ["field_expression"],
                        index=parser.index,
                        check_list=parser.symbol_table["scope_map"]
                    )
                    for identifier in identifiers_used:
                        add_entry(parser, rda_table, parent_id, used=identifier)
                    # Also track literals in condition
                    literals_used = recursively_get_children_of_types(
                        condition, literal_types,
                        index=parser.index
                    )
                    for literal in literals_used:
                        add_entry(parser, rda_table, parent_id, used=literal)

            # Extract identifiers from consequence (true branch)
            consequence = root_node.child_by_field_name("consequence")
            if consequence:
                if consequence.type in variable_type + ["field_expression"]:
                    add_entry(parser, rda_table, parent_id, used=consequence)
                else:
                    identifiers_used = recursively_get_children_of_types(
                        consequence, variable_type + ["field_expression"],
                        index=parser.index,
                        check_list=parser.symbol_table["scope_map"]
                    )
                    for identifier in identifiers_used:
                        add_entry(parser, rda_table, parent_id, used=identifier)
                    literals_used = recursively_get_children_of_types(
                        consequence, literal_types,
                        index=parser.index
                    )
                    for literal in literals_used:
                        add_entry(parser, rda_table, parent_id, used=literal)

            # Extract identifiers from alternative (false branch)
            alternative = root_node.child_by_field_name("alternative")
            if alternative:
                if alternative.type in variable_type + ["field_expression"]:
                    add_entry(parser, rda_table, parent_id, used=alternative)
                else:
                    identifiers_used = recursively_get_children_of_types(
                        alternative, variable_type + ["field_expression"],
                        index=parser.index,
                        check_list=parser.symbol_table["scope_map"]
                    )
                    for identifier in identifiers_used:
                        add_entry(parser, rda_table, parent_id, used=identifier)
                    literals_used = recursively_get_children_of_types(
                        alternative, literal_types,
                        index=parser.index
                    )
                    for literal in literals_used:
                        add_entry(parser, rda_table, parent_id, used=literal)

        # 11. Catch-all: handle any other identifiers as USEs
        else:
            # Skip if this is not an identifier
            if root_node.type not in variable_type:
                continue

            # Skip identifiers inside do-while condition (already handled in case 9a)
            # Check if this identifier is within a parenthesized_expression that's a child of do_statement
            in_do_while_condition = False
            temp_parent = root_node.parent
            while temp_parent is not None:
                if (temp_parent.type == "parenthesized_expression" and
                    temp_parent.parent is not None and
                    temp_parent.parent.type == "do_statement"):
                    # This identifier is in a do-while condition, already handled by case 9a
                    in_do_while_condition = True
                    break
                temp_parent = temp_parent.parent

            if in_do_while_condition:
                continue

            # Find the statement this identifier belongs to
            handled_types = (def_statement + assignment + increment_statement +
                           function_calls + ["return_statement"])
            parent_statement = return_first_parent_of_types(
                root_node,
                statement_types["non_control_statement"] + statement_types["control_statement"],
                stop_types=statement_types.get("statement_holders", []) + handled_types
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
    Perform Reaching Definitions Analysis.

    Fixed-point iteration algorithm:
        Initialize all IN/OUT to empty
        Repeat until convergence:
            For each statement s:
                IN[s] = union of OUT[p] for predecessors p
                OUT[s] = (IN[s] - KILL[s]) ∪ DEF[s]
    """
    # Optionally remove function call edges
    graph = copy.deepcopy(cfg_graph)
    if pre_solve:
        remove_edges = []
        for edge in graph.edges:
            edge_data = graph.edges[edge]
            if "label" in edge_data and edge_data["label"] in \
               ["function_call", "function_return"]:
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
            # KILL[node] = defs of variables redefined in node
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
    """Add edge to graph with attributes"""
    # Always add edge - MultiDiGraph supports multiple edges between same nodes
    final_graph.add_edge(source, target)
    if attrib is not None:
        # Get the key of the edge we just added (it will be the highest key)
        edge_keys = [k for u, v, k in final_graph.edges(keys=True) if u == source and v == target]
        if edge_keys:
            edge_key = max(edge_keys)
        else:
            edge_key = 0
        nx.set_edge_attributes(final_graph, {(source, target, edge_key): attrib})


def name_match_with_fields(name1, name2):
    """Check if two names match (handling struct fields)"""
    # Exact match
    if name1 == name2:
        return True

    # One is prefix of other (struct field access)
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
    # Copy CFG to preserve node attributes (labels, types, etc.)
    final_graph = copy.deepcopy(cfg)
    # Remove all CFG edges - we'll add DFG edges instead
    final_graph.remove_edges_from(list(final_graph.edges()))

    for node in graph_nodes:
        if node not in rda_table:
            continue

        use_info = rda_table[node]["use"]

        for used in use_info:
            # Special handling for literals - they are "defined" at the statement where they're used
            if isinstance(used, Literal):
                # Literals flow directly from the statement where they appear (which is 'node')
                # This creates a self-edge showing the literal is defined and used in the same statement
                # We mark it as satisfied and don't create an edge (self-edges would be confusing)
                used.satisfied = True
                continue

            # Find reaching definitions for regular variables
            for available_def in rda_solution[node]["IN"]:
                # Exact name match
                if available_def.name == used.name:
                    if scope_check(available_def.scope, used.scope):
                        add_edge(final_graph, available_def.line, node,
                               {'dataflow_type': 'comesFrom',
                                'edge_type': 'DFG_edge',
                                'color': '#00A3FF',
                                'used_def': used.name})
                        used.satisfied = True

                # Partial match for struct fields
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
                # Avoid adding for control flow nodes
                node_type = read_index(index, node)[-1]
                def_node_type = read_index(index, killed_def.line)[-1]
                ignore_types = ['for_statement', 'while_statement',
                               'if_statement', 'switch_statement']
                if node_type not in ignore_types and \
                   def_node_type not in ignore_types:
                    add_edge(final_graph, killed_def.line, node,
                           {'color': 'orange', 'dataflow_type': 'lastDef'})

    # Add function parameter edges
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

        # Find common definitions
        intersection = [d for d in out_set if d in in_set]

        if intersection:
            # For MultiDiGraph, edge is (u, v, key), so get_edge_data(*edge) returns the dict directly
            edge_data = graph.get_edge_data(*edge)
            edge_data['rda_info'] = ",".join([str(d) for d in intersection])
        else:
            graph.remove_edge(*edge)

    return graph


def dfg_c(properties, CFG_results):
    """
    Main driver for generating DFG for C programs.

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

    # Phase 1: Preprocess CFG (function calls)
    processed_edges = []
    # For C, simpler than Java - just track function_return edges
    for edge in list(cfg_graph.edges()):
        edge_data = cfg_graph.get_edge_data(*edge)
        if edge_data and len(edge_data) > 0:
            edge_data = edge_data[0]
            if edge_data.get("label") == "function_return":
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

    # Create debug graph (optional)
    debug_graph = rda_cfg_map(rda_solution, CFG_results)

    return final_graph, debug_graph, rda_table, rda_solution
