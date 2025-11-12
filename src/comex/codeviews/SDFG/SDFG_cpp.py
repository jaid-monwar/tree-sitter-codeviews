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


def is_node_inside_loop(ast_node):
    """
    Check if an AST node is inside a loop structure.

    Args:
        ast_node: AST node to check

    Returns:
        True if node is inside a loop (for/while/do-while), False otherwise
    """
    if ast_node is None:
        return False

    current = ast_node
    while current.parent is not None:
        if current.parent.type in ["for_statement", "while_statement",
                                   "do_statement", "for_range_loop"]:
            return True
        current = current.parent
    return False


def get_loop_condition_node(ast_node, parser):
    """
    Get the loop condition CFG node for a node inside a loop body.

    Args:
        ast_node: AST node inside a loop body
        parser: Parser with index

    Returns:
        Tuple (is_in_loop_body, loop_condition_id):
        - is_in_loop_body: True if node is inside a loop body
        - loop_condition_id: CFG node ID of the loop condition, or None
    """
    if ast_node is None:
        return False, None

    # Find the parent loop structure
    current = ast_node
    while current.parent is not None:
        parent_type = current.parent.type

        if parent_type in ["for_statement", "while_statement",
                          "do_statement", "for_range_loop"]:
            # Found a parent loop - get its CFG node ID (the condition node)
            loop_condition_id = get_index(current.parent, parser.index)
            return True, loop_condition_id

        current = current.parent

    return False, None


def get_variable_type(parser, node):
    """
    Get the type of a variable from parser's symbol table.

    Args:
        parser: C++ parser with symbol table
        node: AST node representing the variable

    Returns:
        String representing the type, or None if not found
    """
    var_index = get_index(node, parser.index)
    if var_index is None:
        return None

    # Check if this variable has a declaration
    if var_index in parser.declaration_map:
        decl_index = parser.declaration_map[var_index]
        if decl_index in parser.symbol_table.get("data_type", {}):
            return parser.symbol_table["data_type"][decl_index]

    # Check if the node itself has type info (for declarations)
    if var_index in parser.symbol_table.get("data_type", {}):
        return parser.symbol_table["data_type"][var_index]

    return None


def is_primitive_type(type_string):
    """
    Check if a type string represents a C++ primitive type.

    Args:
        type_string: String representing the type

    Returns:
        True if primitive, False otherwise
    """
    if type_string is None:
        return False

    # C++ primitive types and their variants
    primitive_types = {
        # Integer types
        'int', 'short', 'long', 'char', 'wchar_t', 'char8_t', 'char16_t', 'char32_t',
        'signed', 'unsigned',
        # Fixed-width integer types from <cstdint>
        'int8_t', 'int16_t', 'int32_t', 'int64_t',
        'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t',
        'int_fast8_t', 'int_fast16_t', 'int_fast32_t', 'int_fast64_t',
        'uint_fast8_t', 'uint_fast16_t', 'uint_fast32_t', 'uint_fast64_t',
        'int_least8_t', 'int_least16_t', 'int_least32_t', 'int_least64_t',
        'uint_least8_t', 'uint_least16_t', 'uint_least32_t', 'uint_least64_t',
        'intmax_t', 'uintmax_t', 'intptr_t', 'uintptr_t',
        'size_t', 'ssize_t', 'ptrdiff_t',
        # Floating-point types
        'float', 'double',
        # Boolean
        'bool',
        # Void
        'void',
        # C types
        'DWORD', 'WORD', 'BYTE',
    }

    # Remove const, volatile, and whitespace
    type_clean = type_string.strip().replace('const', '').replace('volatile', '').strip()

    # Check for exact match
    if type_clean in primitive_types:
        return True

    # Check for compound types (e.g., "unsigned int", "long long")
    tokens = type_clean.split()
    if all(token in primitive_types for token in tokens):
        return True

    # Check if any primitive type keyword appears in the string
    # This handles cases like "unsigned int" or "long double"
    for prim in primitive_types:
        if prim in type_clean:
            # Make sure it's not part of a class name (e.g., MyIntClass)
            # For now, use simple heuristic: if it's the only token or starts the string
            if type_clean == prim or type_clean.startswith(prim + ' '):
                return True

    return False


def is_class_or_struct_type(parser, type_string):
    """
    Check if a type string represents a class or struct type.

    Args:
        parser: C++ parser with symbol table
        type_string: String representing the type

    Returns:
        True if class/struct, False otherwise
    """
    if type_string is None:
        return False

    # Not a primitive = likely a class or struct
    # Also check parser.records if available (for OOP tracking)
    if not is_primitive_type(type_string):
        # Check if it's in the parser's records (classes/structs)
        if hasattr(parser, 'records') and type_string in parser.records:
            return True

        # Check for std:: types (which are classes)
        if 'std::' in type_string or '::' in type_string:
            return True

        # If not primitive and looks like a type identifier, assume class/struct
        # (conservative: better to miss a use than create false edges)
        return True

    return False


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

    def __init__(self, parser, node, line=None, declaration=False, full_ref=None, method_call=False, has_initializer=False):
        self.core = st(node)
        self.unresolved_name = st(full_ref) if full_ref else st(node)
        self.name = self._resolve_name(node, full_ref, parser)
        self.line = line
        self.declaration = declaration
        self.has_initializer = has_initializer  # True if declaration has an initializer
        self.method_call = method_call
        # Method calls on objects (obj.method) should be satisfied
        # But namespace-qualified function calls (Room1::getId) need matching
        # Check if this is a namespace function call (qualified_identifier where first part is a namespace)
        if method_call and node.type == "qualified_identifier":
            # This is a qualified function call like Room1::getId
            self.satisfied = False  # Needs to find matching function definition
        else:
            self.satisfied = method_call  # Regular method calls are initially satisfied

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

        # Special handling for qualified functions
        if hasattr(node, 'qualified_name'):
            # This is a pseudo node, use the real node for scope
            if hasattr(node, 'real_node'):
                variable_index = get_index(node.real_node, parser.index)

        # Special handling for qualified identifiers
        if variable_index is None and node.type == "qualified_identifier":
            # Try to get scope from the innermost identifier
            innermost = extract_identifier_from_declarator(node)
            if innermost:
                variable_index = get_index(innermost, parser.index)

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
            # For qualified identifiers, use the current statement's scope
            # First check if line is a statement ID in the CFG nodes
            if line and line in parser.symbol_table.get("scope_map", {}):
                self.variable_scope = parser.symbol_table["scope_map"][line]
                self.scope = self.variable_scope
            elif line:
                # Line might be a statement ID not in scope_map, find a parent scope
                # For function calls, the scope should be the scope of the calling function
                # Use a default main function scope
                self.variable_scope = [0, 11, 12]  # Temporary: assume main scope
                self.scope = [0]  # Function definitions are global
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


def get_namespace_for_node(node, parser):
    """
    Get the namespace that contains this node, if any.

    Returns the namespace name or None if not in a namespace.
    """
    parent = node.parent
    while parent:
        if parent.type == "namespace_definition":
            # Get the namespace identifier
            for child in parent.children:
                if child.type == "namespace_identifier":
                    return st(child)
        parent = parent.parent
    return None

def extract_identifier_from_declarator(declarator_node):
    """Extract identifier from declarator (may be wrapped in pointer/array/reference/qualified)"""
    if declarator_node.type == "identifier":
        return declarator_node
    elif declarator_node.type == "qualified_identifier":
        # Handle qualified identifiers like enclose::inner::x
        # Recursively extract the innermost identifier
        for child in declarator_node.children:
            if child.type in ["identifier", "qualified_identifier"]:
                result = extract_identifier_from_declarator(child)
                if result:
                    return result
        return None
    elif declarator_node.type == "pointer_declarator":
        for child in declarator_node.children:
            if child.type in ["identifier", "pointer_declarator", "array_declarator", "reference_declarator", "qualified_identifier"]:
                return extract_identifier_from_declarator(child)
    elif declarator_node.type == "reference_declarator":
        for child in declarator_node.children:
            if child.type in ["identifier", "pointer_declarator", "array_declarator", "reference_declarator", "qualified_identifier"]:
                return extract_identifier_from_declarator(child)
    elif declarator_node.type == "array_declarator":
        if declarator_node.children:
            return extract_identifier_from_declarator(declarator_node.children[0])
    elif declarator_node.type == "function_declarator":
        for child in declarator_node.children:
            if child.type in ["identifier", "pointer_declarator", "parenthesized_declarator", "qualified_identifier"]:
                return extract_identifier_from_declarator(child)
    elif declarator_node.type == "parenthesized_declarator":
        for child in declarator_node.children:
            if child.type in ["identifier", "pointer_declarator", "array_declarator", "reference_declarator", "qualified_identifier"]:
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


def is_reference_variable(parser, node):
    """
    Check if a variable node represents a reference variable.

    This is determined by checking if the variable's declaration
    involves a reference_declarator in the AST.

    Args:
        parser: C++ parser with declaration_map and tree
        node: AST node representing the variable (identifier)

    Returns:
        True if the variable is a reference, False otherwise
    """
    if node is None or node.type not in ['identifier']:
        return False

    # Get the variable's index
    var_index = get_index(node, parser.index)
    if var_index is None:
        return False

    # Look up declaration using declaration_map
    if var_index not in parser.declaration_map:
        return False

    decl_index = parser.declaration_map[var_index]

    # Find the declaration node by matching its index and position
    def find_node_by_index(root, target_index):
        """Find node with matching index by traversing tree"""
        stack = [root]
        while stack:
            current = stack.pop()
            # Check if this node has the target index
            node_idx = get_index(current, parser.index)
            if node_idx == target_index:
                return current
            # Add children to stack
            for child in current.children:
                stack.append(child)
        return None

    # Search for the declaration node
    decl_node = find_node_by_index(parser.tree.root_node, decl_index)

    if decl_node:
        # Check if this declaration node's parent is a reference_declarator
        parent = decl_node.parent
        depth = 0
        while parent and depth < 5:  # Limit search depth
            if parent.type == "reference_declarator":
                return True
            # Stop at declaration boundaries
            if parent.type in ["parameter_declaration", "declaration",
                              "function_definition", "translation_unit"]:
                break
            depth += 1
            parent = parent.parent

    return False


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
              declaration=False, core=None, method_call=False, has_initializer=False):
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
        has_initializer: True if this is a declaration with an initializer
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

    # Handle pseudo nodes for qualified functions
    if hasattr(current_node, 'qualified_name'):
        # This is a pseudo node for a namespace-qualified function
        if defined is not None:
            # Create an identifier with the qualified name
            identifier = Identifier(parser, current_node, statement_id,
                                   full_ref=current_node, declaration=declaration,
                                   method_call=method_call, has_initializer=has_initializer)
            # Override the name with the qualified name
            identifier.name = current_node.qualified_name
            set_add(rda_table[statement_id]["def"], identifier)
        return

    # Handle field access: obj.field or obj->field
    if current_node.type == "field_expression":
        argument = current_node.child_by_field_name("argument")

        if defined is not None:
            # When a field is being defined (e.g., obj.field = value),
            # the object itself is USED (to access the member), and the field is DEFINED
            # First, track USE of the base object (just the object, not the full field expression)
            if argument:
                set_add(rda_table[statement_id]["use"],
                       Identifier(parser, argument, line=statement_id))  # Track object with line number
            # Then track DEF of the full field expression
            set_add(rda_table[statement_id]["def"],
                   Identifier(parser, argument, statement_id,
                            full_ref=current_node, declaration=declaration,
                            method_call=method_call, has_initializer=has_initializer))
        else:
            # When a field is being used (e.g., reading obj.field),
            # Track both the object USE and the full field expression USE
            if argument:
                # Track the base object as being used with the current line number
                set_add(rda_table[statement_id]["use"],
                       Identifier(parser, argument, line=statement_id))
            # Also track the full field expression as being used
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
                # Check if it's a variable in scope_map
                if arg_index and arg_index in parser.symbol_table["scope_map"]:
                    set_add(rda_table[statement_id]["use"],
                           Identifier(parser, argument, full_ref=argument))
                # Also check if it's a function in method_map (for function pointers)
                elif arg_index and arg_index in parser.method_map:
                    set_add(rda_table[statement_id]["use"],
                           Identifier(parser, argument, full_ref=argument))
            return

    # Handle pointer expressions: both &x (address-of) and *ptr (dereference)
    if current_node.type == "pointer_expression":
        # Distinguish between & and * by checking the first child
        is_address_of = False
        is_dereference = False

        if current_node.children:
            operator = current_node.children[0]
            if operator.type == "&":
                is_address_of = True
            elif operator.type == "*":
                is_dereference = True

        pointer = current_node.child_by_field_name("argument")

        if is_address_of:
            # This is &x - taking the address of a variable or function
            # The identifier is being used (its address is taken)
            if pointer and pointer.type in variable_type:
                pointer_index = get_index(pointer, parser.index)
                if pointer_index and pointer_index in parser.symbol_table["scope_map"]:
                    set_add(rda_table[statement_id]["use"],
                           Identifier(parser, pointer, full_ref=pointer))
            return

        elif is_dereference:
            # This is *ptr - dereferencing a pointer
            # Track USE of the base pointer
            pointer_index = get_index(pointer, parser.index)
            if pointer_index and pointer_index in parser.symbol_table["scope_map"]:
                set_add(rda_table[statement_id]["use"],
                       Identifier(parser, pointer, full_ref=pointer))

            # Track DEF/USE of dereferenced value
            if defined is not None:
                set_add(rda_table[statement_id]["def"],
                       Identifier(parser, pointer, statement_id,
                                full_ref=core, declaration=declaration, has_initializer=has_initializer))
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
                            full_ref=core, declaration=declaration, has_initializer=has_initializer))
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

    # Handle qualified identifiers: std::cout, MyClass::member, enclose::inner::x
    if current_node.type == "qualified_identifier":
        # Extract the innermost identifier for scope checking
        # The qualified_identifier itself is NOT in scope_map, only the innermost identifier is
        innermost_id = extract_identifier_from_declarator(current_node)

        # For function calls, we want to preserve the qualified name even if
        # the innermost identifier isn't in the scope_map
        if method_call:
            # Use the qualified_identifier itself as the node for function calls
            # This preserves the full qualified name like Room1::getId
            if defined is not None:
                set_add(rda_table[statement_id]["def"],
                       Identifier(parser, current_node, statement_id,
                                full_ref=current_node, declaration=declaration,
                                method_call=method_call, has_initializer=has_initializer))
            else:
                set_add(rda_table[statement_id]["use"],
                       Identifier(parser, current_node, statement_id, full_ref=current_node,
                                method_call=method_call))
            return

        # For non-method calls, use the original logic
        if innermost_id is None:
            return

        node_index = get_index(innermost_id, parser.index)
        if node_index is None or node_index not in parser.symbol_table["scope_map"]:
            # For qualified identifiers, allow them even if not in scope_map
            # as they might be external symbols like std::cout
            if defined is not None:
                set_add(rda_table[statement_id]["def"],
                       Identifier(parser, current_node, statement_id,
                                full_ref=current_node, declaration=declaration,
                                method_call=method_call, has_initializer=has_initializer))
            else:
                set_add(rda_table[statement_id]["use"],
                       Identifier(parser, current_node, statement_id, full_ref=current_node,
                                method_call=method_call))
            return

        if defined is not None:
            set_add(rda_table[statement_id]["def"],
                   Identifier(parser, innermost_id, statement_id,
                            full_ref=current_node, declaration=declaration,
                            method_call=method_call, has_initializer=has_initializer))
        else:
            set_add(rda_table[statement_id]["use"],
                   Identifier(parser, innermost_id, full_ref=current_node,
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
        # Even if not in scope_map, we should still track the identifier
        # It might be a namespace variable or external symbol
        if defined is not None:
            set_add(rda_table[statement_id]["def"],
                   Identifier(parser, defined, statement_id,
                            full_ref=core, declaration=declaration,
                            method_call=method_call, has_initializer=has_initializer))
        else:
            set_add(rda_table[statement_id]["use"],
                   Identifier(parser, used, statement_id, full_ref=core,
                            method_call=method_call))
        return

    if defined is not None:
        set_add(rda_table[statement_id]["def"],
               Identifier(parser, defined, statement_id,
                        full_ref=core, declaration=declaration,
                        method_call=method_call, has_initializer=has_initializer))
    else:
        set_add(rda_table[statement_id]["use"],
               Identifier(parser, used, statement_id, full_ref=core,
                        method_call=method_call))


def discover_lambdas(parser, CFG_results):
    """
    Discover all lambda expressions and build a mapping.

    Returns:
        lambda_map: Dict mapping variable names to lambda information
            {
                "variable_name": {
                    "definition_node": <node_id>,  # Statement where lambda is defined
                    "lambda_node": <node_id>,      # The lambda_expression AST node
                    "body_nodes": [<node_ids>],    # CFG nodes in lambda body
                    "captures": [<var_names>]      # Captured variables
                }
            }
    """
    lambda_map = {}
    index = parser.index
    tree = parser.tree
    cfg_nodes = CFG_results.graph.nodes

    # Find all lambda expressions
    for node in traverse_tree(tree, ["lambda_expression"]):
        if node.type != "lambda_expression":
            continue

        # Find the variable this lambda is assigned to
        parent = node.parent
        variable_name = None
        definition_node_id = None

        # Check if lambda is in an init_declarator (auto var = [](){...})
        if parent and parent.type == "init_declarator":
            # Get the declarator (variable name)
            declarator = parent.child_by_field_name("declarator")
            if declarator and declarator.type == "identifier":
                variable_name = st(declarator)

                # Find the enclosing statement (declaration)
                statement = parent.parent  # init_declarator -> declaration
                if statement:
                    definition_node_id = get_index(statement, index)

        if not variable_name or not definition_node_id:
            # Lambda not assigned to a simple variable (could be inline, etc.)
            continue

        # Extract lambda body nodes (statements in compound_statement)
        body_nodes = []
        for child in node.children:
            if child.type == "compound_statement":
                # Get all statement children
                for stmt in child.named_children:
                    stmt_id = get_index(stmt, index)
                    if stmt_id and stmt_id in cfg_nodes:
                        body_nodes.append(stmt_id)
                break

        # Extract captured variables
        captures = []
        for child in node.children:
            if child.type == "lambda_capture_specifier":
                # Process captured variables
                for capture in child.named_children:
                    if capture.type in variable_type:
                        captures.append(st(capture))
                break

        # Get lambda_expression node ID
        lambda_node_id = get_index(node, index)

        # Store in lambda_map
        lambda_map[variable_name] = {
            "definition_node": definition_node_id,
            "lambda_node": lambda_node_id,
            "body_nodes": body_nodes,
            "captures": captures
        }

        if debug:
            logger.info(f"Discovered lambda: {variable_name} at node {definition_node_id}, "
                       f"body nodes: {body_nodes}, captures: {captures}")

    return lambda_map


def is_return_value_used(call_expr_statement):
    """
    Check if a function call's return value is actually used.

    Args:
        call_expr_statement: The expression_statement or parent node containing the call

    Returns:
        True if return value is used (assigned, passed as argument, returned, in conditional)
        False if return value is discarded (standalone statement like fn();)
    """
    # If this is a declaration statement with initialization, return value is used
    # Example: Book myBook = createBook(...);
    if call_expr_statement.type == "declaration":
        # Check if it has an init_declarator with an initializer
        for child in call_expr_statement.children:
            if child.type == "init_declarator":
                # Has initializer, so return value is used
                return True
        return False  # Declaration without initialization

    # If this is an expression_statement with a single call_expression child,
    # the return value is discarded
    if call_expr_statement.type == "expression_statement":
        if len(call_expr_statement.named_children) == 1:
            child = call_expr_statement.named_children[0]
            if child.type == "call_expression":
                return False  # Discarded: fn();

    # Check parent context
    parent = call_expr_statement.parent
    while parent:
        parent_type = parent.type

        # If parent is assignment or declaration, return value is used
        if parent_type in ["init_declarator", "assignment_expression"]:
            return True

        # If parent is return statement, return value is used
        if parent_type == "return_statement":
            return True

        # If parent is argument_list, return value is used as argument
        if parent_type == "argument_list":
            return True

        # If parent is conditional, return value is used
        if parent_type in ["if_statement", "while_statement", "for_statement",
                          "do_statement", "switch_statement"]:
            return True

        # If we hit expression_statement at top level, it's discarded
        if parent_type == "expression_statement":
            return False

        parent = parent.parent

    return False  # Default: assume not used


def collect_function_metadata(parser):
    """
    Collect metadata about all functions in the program.

    For each function, track:
    - Function name
    - Parameter names and whether they're pointers/references
    - Parameter indices

    Returns:
        Dict mapping function_name -> {
            "params": [(param_name, is_pointer, is_reference, param_index), ...],
            "node": function_definition AST node
        }
    """
    metadata = {}

    # Find all function definitions
    for node in traverse_tree(parser.tree.root_node):
        if node.type == "function_definition":
            # Extract function name and parameters
            func_name = None
            params = []

            for child in node.named_children:
                if child.type == "function_declarator":
                    # Get function name
                    declarator = child.child_by_field_name("declarator")
                    if declarator:
                        if declarator.type == "identifier":
                            func_name = st(declarator)
                        elif declarator.type in ["pointer_declarator", "reference_declarator"]:
                            # Handle function that returns pointer/reference
                            inner = declarator
                            while inner and inner.type in ["pointer_declarator", "reference_declarator"]:
                                inner_declarator = inner.child_by_field_name("declarator")
                                if inner_declarator:
                                    inner = inner_declarator
                                else:
                                    break
                            if inner and inner.type == "identifier":
                                func_name = st(inner)
                        elif declarator.type == "qualified_identifier":
                            # Handle qualified names like Class::method
                            name_node = declarator.child_by_field_name("name")
                            if name_node:
                                func_name = st(name_node)

                    # Get parameters
                    param_list = child.child_by_field_name('parameters')
                    if param_list:
                        param_idx = 0
                        for param in param_list.named_children:
                            if param.type == "parameter_declaration":
                                param_name = None
                                is_pointer = False
                                is_reference = False

                                # Check if parameter is a pointer or reference
                                for p_child in param.named_children:
                                    if p_child.type in ["pointer_declarator", "reference_declarator"]:
                                        if p_child.type == "pointer_declarator":
                                            is_pointer = True
                                        else:
                                            is_reference = True
                                        # Extract parameter name from pointer/reference_declarator
                                        inner = p_child
                                        while inner:
                                            if inner.type == "identifier":
                                                param_name = st(inner)
                                                break
                                            elif inner.type in ["pointer_declarator", "reference_declarator"]:
                                                inner_decl = inner.child_by_field_name("declarator")
                                                if inner_decl:
                                                    inner = inner_decl
                                                else:
                                                    # No field named "declarator" - check named children
                                                    # For reference_declarator, the identifier is the named child
                                                    if inner.named_children:
                                                        for child in inner.named_children:
                                                            if child.type == "identifier":
                                                                param_name = st(child)
                                                                break
                                                    break
                                            else:
                                                break
                                    elif p_child.type == "identifier":
                                        if param_name is None:  # Only if not already found
                                            param_name = st(p_child)

                                if param_name:
                                    params.append((param_name, is_pointer, is_reference, param_idx))
                                    param_idx += 1
                    break

            if func_name:
                metadata[func_name] = {
                    "params": params,
                    "node": node
                }

    return metadata


def analyze_pointer_modifications(parser, function_metadata):
    """
    Analyze which pointer/reference parameters are modified within each function.

    A pointer/reference parameter is considered "modified" if:
    - It's dereferenced on the left side of an assignment: *param = ...
    - Used in pointer arithmetic with assignment: param[i] = ...
    - Passed to another function that modifies it (transitive)
    - Used in field assignment: param->field = ...
    - For references: direct assignment also counts: ref = ...

    Args:
        parser: Parser with AST
        function_metadata: Dict from collect_function_metadata()

    Returns:
        Dict mapping function_name -> set of parameter indices that are modified
    """
    modifications = {}

    for func_name, meta in function_metadata.items():
        modified_params = set()
        func_node = meta["node"]

        # Build map of parameter names to indices (only for pointer/ref params)
        param_name_to_idx = {}
        for param_name, is_pointer, is_reference, param_idx in meta["params"]:
            if is_pointer or is_reference:
                param_name_to_idx[param_name] = param_idx

        if not param_name_to_idx:
            # No pointer/reference parameters
            modifications[func_name] = modified_params
            continue

        # Traverse function body looking for modifications
        for node in traverse_tree(func_node):
            # Check for assignment expressions where LHS dereferences/uses a pointer/ref param
            if node.type == "assignment_expression":
                left = node.child_by_field_name("left")
                if left:
                    # Check for *param = ... (pointer dereference)
                    if left.type == "pointer_expression":
                        arg = left.child_by_field_name("argument")
                        if arg and arg.type == "identifier":
                            var_name = st(arg)
                            if var_name in param_name_to_idx:
                                modified_params.add(param_name_to_idx[var_name])

                    # Check for param[i] = ... (subscript)
                    elif left.type == "subscript_expression":
                        array_arg = left.child_by_field_name("argument")
                        if array_arg and array_arg.type == "identifier":
                            var_name = st(array_arg)
                            if var_name in param_name_to_idx:
                                modified_params.add(param_name_to_idx[var_name])

                    # Check for param->field = ... or param.field = ... (field access)
                    elif left.type == "field_expression":
                        obj = left.child_by_field_name("argument")
                        if obj and obj.type == "identifier":
                            var_name = st(obj)
                            if var_name in param_name_to_idx:
                                modified_params.add(param_name_to_idx[var_name])

                    # For references: direct assignment counts as modification
                    # ref = ... (identifier on left side)
                    elif left.type == "identifier":
                        var_name = st(left)
                        if var_name in param_name_to_idx:
                            # This is a reference parameter being assigned
                            modified_params.add(param_name_to_idx[var_name])

            # Check for update expressions (++, --)
            elif node.type == "update_expression":
                arg = node.child_by_field_name("argument")
                if arg:
                    # Check for (*param)++ or ++(*param)
                    if arg.type == "pointer_expression":
                        inner_arg = arg.child_by_field_name("argument")
                        if inner_arg and inner_arg.type == "identifier":
                            var_name = st(inner_arg)
                            if var_name in param_name_to_idx:
                                modified_params.add(param_name_to_idx[var_name])
                    # Check for param[i]++ or param->field++ or ref++
                    elif arg.type == "subscript_expression":
                        array_arg = arg.child_by_field_name("argument")
                        if array_arg and array_arg.type == "identifier":
                            var_name = st(array_arg)
                            if var_name in param_name_to_idx:
                                modified_params.add(param_name_to_idx[var_name])
                    elif arg.type == "field_expression":
                        obj = arg.child_by_field_name("argument")
                        if obj and obj.type == "identifier":
                            var_name = st(obj)
                            if var_name in param_name_to_idx:
                                modified_params.add(param_name_to_idx[var_name])
                    elif arg.type == "identifier":
                        var_name = st(arg)
                        if var_name in param_name_to_idx:
                            modified_params.add(param_name_to_idx[var_name])

        modifications[func_name] = modified_params

    return modifications


def build_rda_table(parser, CFG_results, lambda_map=None, function_metadata=None, pointer_modifications=None):
    """
    Build RDA table by traversing AST and tracking DEF/USE.

    Combines C and Java approaches for C++ support.

    Args:
        parser: C++ parser with symbol table
        CFG_results: CFG driver results
        lambda_map: Dict mapping variable names to lambda information

    Returns:
        rda_table: Dict mapping statement_id to {"def": set, "use": set}
    """
    if lambda_map is None:
        lambda_map = {}

    rda_table = {}
    index = parser.index
    tree = parser.tree

    inner_types_local = ["parenthesized_expression", "binary_expression", "unary_expression"]
    handled_cases = ["compound_statement", "translation_unit", "class_specifier",
                     "struct_specifier", "namespace_definition"]

    # Traverse entire tree without stopping (lambda bodies need to be processed)
    # We filter by node type in each handler instead
    for root_node in traverse_tree(tree, []):
        if not root_node.is_named:
            continue

        # 1. Handle return statements
        if root_node.type == "return_statement":
            parent_id = get_index(root_node, index)
            if parent_id is None or parent_id not in CFG_results.graph.nodes:
                continue

            # Check if return value is a direct expression we can track
            return_expr = root_node.named_children[0] if root_node.named_children else None
            if return_expr and return_expr.type in variable_type + ["field_expression",
                                                                      "pointer_expression",
                                                                      "subscript_expression"] + literal_types:
                add_entry(parser, rda_table, parent_id, used=return_expr)
            else:
                # Recursively find all variables in the return expression
                vars_used = recursively_get_children_of_types(
                    root_node, variable_type + ["field_expression", "pointer_expression", "subscript_expression"],
                    index=parser.index,
                    check_list=parser.symbol_table["scope_map"]
                )
                for var in vars_used:
                    add_entry(parser, rda_table, parent_id, used=var)

            # Also track literals
            literals_used = recursively_get_children_of_types(
                root_node, literal_types,
                index=parser.index
            )
            for literal in literals_used:
                add_entry(parser, rda_table, parent_id, used=literal)

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

            # Check if this declaration has an initializer
            initializer = root_node.child_by_field_name("value")
            has_initializer = initializer is not None

            if var_identifier:
                add_entry(parser, rda_table, parent_id,
                         defined=var_identifier, declaration=True,
                         has_initializer=has_initializer)

            # Extract initializer
            if initializer:
                # Special handling for lambda expressions
                # Lambda bodies are separate execution contexts with their own CFG nodes
                # Do NOT extract variables from inside the lambda body
                if initializer.type == "lambda_expression":
                    # Only process captured variables (in lambda_capture_specifier)
                    for child in initializer.children:
                        if child.type == "lambda_capture_specifier":
                            for capture in child.named_children:
                                if capture.type in variable_type:
                                    add_entry(parser, rda_table, parent_id, used=capture)
                    # Lambda body will be processed as its own CFG node
                elif initializer.type in variable_type + ["field_expression", "pointer_expression",
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
            # For C++, regular assignments on class types also USE the left side
            # (assignment operator is called on the existing object)
            if operator_text != "=":
                # Compound assignment - definitely uses left side
                add_entry(parser, rda_table, parent_id, used=left_node)
            else:
                # Regular assignment: For class/struct types, this calls the assignment
                # operator on the existing object, so it uses the old value.
                # For primitive types, this is a simple copy and does NOT use the old value.
                # EXCEPTION: Reference types always USE the reference binding, even for primitives.
                if left_node.type in variable_type:
                    # Get the variable's type
                    var_type = get_variable_type(parser, left_node)

                    # Track USE if:
                    # 1. It's a class/struct type (operator= is called), OR
                    # 2. It's a reference variable (uses the reference binding established by parameter/declaration)
                    if is_class_or_struct_type(parser, var_type) or is_reference_variable(parser, left_node):
                        # Class/struct assignment calls operator=, so it uses the old value
                        # Reference assignment uses the reference binding from parameter/declaration
                        add_entry(parser, rda_table, parent_id, used=left_node)
                    # For primitive non-reference types: no USE, only DEF (handled below)

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

                # Track method calls on objects (obj.method() or obj->method())
                if function_node.type == "field_expression":
                    # This is a method call: obj.method() or obj->method()
                    # Only track USE of the base object (not the whole field expression)
                    # Extract the base object from the field_expression
                    argument = function_node.child_by_field_name("argument")
                    if argument:
                        # Track USE of the base object only
                        add_entry(parser, rda_table, parent_id, used=argument)
                    # Note: We do NOT add a DEF entry - method calls don't define the object
                elif function_node.type in variable_type:
                    # Simple function call
                    add_entry(parser, rda_table, parent_id, used=function_node, method_call=True)
                elif function_node.type == "qualified_identifier":
                    # Qualified function call like Room1::getId or std::cout
                    # Use the full qualified_identifier node to preserve namespace
                    add_entry(parser, rda_table, parent_id, used=function_node, method_call=True)

            # Check if this is an input function
            is_input_function = function_name in input_functions or \
                               (function_name and any(inp in function_name for inp in ["cin", "scanf"]))

            # Special handling for variadic function macros
            is_variadic_macro = function_name in ["va_start", "va_arg", "va_end"]

            # Process arguments
            args_node = root_node.child_by_field_name("arguments")
            if args_node:
                arg_list = list(args_node.named_children)
                for idx, arg in enumerate(arg_list):
                    # Special handling for variadic macros
                    if is_variadic_macro:
                        # va_start(valist, last_arg): valist is DEFINED (initialized)
                        if function_name == "va_start" and idx == 0:
                            # First argument is the va_list being initialized
                            if arg.type in variable_type:
                                add_entry(parser, rda_table, parent_id, defined=arg, declaration=False, has_initializer=True)
                            else:
                                # Extract identifiers from complex expression
                                identifiers_defined = recursively_get_children_of_types(
                                    arg, variable_type,
                                    index=parser.index,
                                    check_list=parser.symbol_table["scope_map"]
                                )
                                for identifier in identifiers_defined:
                                    add_entry(parser, rda_table, parent_id, defined=identifier, declaration=False, has_initializer=True)
                            continue  # Don't process as regular argument

                        # va_arg(valist, type): valist is both USED and DEFINED (read and modify)
                        elif function_name == "va_arg" and idx == 0:
                            # First argument is the va_list being read and modified
                            if arg.type in variable_type:
                                add_entry(parser, rda_table, parent_id, used=arg)
                                add_entry(parser, rda_table, parent_id, defined=arg, declaration=False)
                            else:
                                # Extract identifiers from complex expression
                                identifiers_used = recursively_get_children_of_types(
                                    arg, variable_type,
                                    index=parser.index,
                                    check_list=parser.symbol_table["scope_map"]
                                )
                                for identifier in identifiers_used:
                                    add_entry(parser, rda_table, parent_id, used=identifier)
                                    add_entry(parser, rda_table, parent_id, defined=identifier, declaration=False)
                            continue  # Don't process as regular argument

                        # va_end(valist): valist is only USED (finalization)
                        # This is handled by the regular argument processing below

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

                    # Check if this is a user-defined function with pointer/reference params
                    if not is_input_function and not is_variadic_macro:
                        # Check if we have metadata for this function
                        modifies_params = set()
                        if function_name and function_metadata and function_name in function_metadata:
                            if pointer_modifications and function_name in pointer_modifications:
                                modifies_params = pointer_modifications[function_name]

                        # Check if this argument corresponds to a modified pointer/reference parameter
                        is_modified_param = idx in modifies_params

                        # If argument is passed by address/reference and the function modifies it
                        if is_modified_param:
                            # Check for &var (pointer_expression in C++)
                            if arg.type == "pointer_expression":
                                inner_arg = arg.child_by_field_name("argument")
                                if not inner_arg:
                                    # Fallback: get first child that's an identifier
                                    inner_arg = arg.named_children[0] if arg.named_children else None

                                if inner_arg:
                                    if inner_arg.type in variable_type:
                                        # USE: Taking address of variable (reads the variable)
                                        add_entry(parser, rda_table, parent_id, used=inner_arg)
                                        # DEF: Variable is modified through pointer
                                        add_entry(parser, rda_table, parent_id,
                                                 defined=inner_arg, declaration=False)
                                    elif inner_arg.type in ["field_expression", "subscript_expression"]:
                                        # Handle &s.field or &arr[i]
                                        # USE: Taking address requires reading the base variable
                                        add_entry(parser, rda_table, parent_id, used=inner_arg)
                                        # DEF: The field/element is modified
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
                                continue
                            # Also check for unary_expression (older tree-sitter versions or alternative syntax)
                            elif arg.type == "unary_expression":
                                has_address_of = any(child.type == "&" for child in arg.children)
                                if has_address_of:
                                    inner_arg = arg.child_by_field_name("argument")
                                    if inner_arg:
                                        if inner_arg.type in variable_type:
                                            # USE: Taking address of variable
                                            add_entry(parser, rda_table, parent_id, used=inner_arg)
                                            # DEF: Variable is modified through pointer
                                            add_entry(parser, rda_table, parent_id,
                                                     defined=inner_arg, declaration=False)
                                        elif inner_arg.type in ["field_expression", "subscript_expression"]:
                                            # USE: Taking address requires reading the base variable
                                            add_entry(parser, rda_table, parent_id, used=inner_arg)
                                            # DEF: The field/element is modified
                                            add_entry(parser, rda_table, parent_id,
                                                     defined=inner_arg, declaration=False)
                                    continue

                            # Check if argument is passed by reference (no &, just the variable)
                            # In C++, references can be passed directly
                            elif arg.type in variable_type + ["field_expression"]:
                                # This could be a reference parameter being modified
                                # Add USE first (variable is read to pass to function)
                                add_entry(parser, rda_table, parent_id, used=arg)
                                # Then add DEF (variable will be modified through reference)
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

        # 6. Handle function definitions (name and parameters)
        elif root_node.type == "function_definition":
            parent_id = get_index(root_node, index)
            if parent_id is None:
                continue

            # Extract function name and define it (for function pointers)
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
                    # Extract function name
                    func_name_node = func_declarator.child_by_field_name("declarator")
                    if func_name_node and func_name_node.type in variable_type:
                        func_name_idx = get_index(func_name_node, index)
                        if func_name_idx and func_name_idx in parser.symbol_table["scope_map"]:
                            # Check if this function is inside a namespace
                            namespace_name = get_namespace_for_node(root_node, parser)

                            # If in a namespace, create a qualified identifier node for the function
                            if namespace_name:
                                # Create a synthetic qualified name for the function definition
                                # We'll store the namespace-qualified name as a special identifier
                                qualified_name = f"{namespace_name}::{st(func_name_node)}"
                                # We need to pass the namespace-qualified name to add_entry
                                # Create a pseudo-node that represents the qualified name
                                class PseudoNode:
                                    def __init__(self, name, real_node):
                                        self.type = "qualified_function"
                                        self.text = name.encode('utf-8')
                                        self.qualified_name = name
                                        self.parent = real_node.parent if real_node else None
                                        self.real_node = real_node
                                pseudo_node = PseudoNode(qualified_name, func_name_node)
                                # Define the function with its namespace-qualified name
                                add_entry(parser, rda_table, parent_id,
                                         defined=pseudo_node, declaration=True)
                            else:
                                # No namespace, use the regular function name
                                add_entry(parser, rda_table, parent_id,
                                         defined=func_name_node, declaration=True)

                    # Extract parameters
                    param_list = func_declarator.child_by_field_name('parameters')
                    if param_list:
                        for param in param_list.named_children:
                            if param.type in ["parameter_declaration", "optional_parameter_declaration"]:
                                param_id = extract_param_identifier(param)
                                if param_id:
                                    add_entry(parser, rda_table, parent_id,
                                            defined=param_id, declaration=True, has_initializer=True)

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

        elif root_node.type == "conditional_expression":
            # Handle ternary operator: condition ? true_expr : false_expr
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

            # Extract and track the condition
            condition = root_node.child_by_field_name("condition")
            if condition:
                if condition.type in variable_type + ["field_expression", "pointer_expression",
                                                     "subscript_expression", "unary_expression"] + literal_types:
                    add_entry(parser, rda_table, parent_id, used=condition)
                else:
                    identifiers_used = recursively_get_children_of_types(
                        condition, variable_type + ["field_expression"],
                        index=parser.index,
                        check_list=parser.symbol_table["scope_map"]
                    )
                    for identifier in identifiers_used:
                        add_entry(parser, rda_table, parent_id, used=identifier)
                    literals_used = recursively_get_children_of_types(
                        condition, literal_types, index=parser.index
                    )
                    for literal in literals_used:
                        add_entry(parser, rda_table, parent_id, used=literal)

            # Extract and track consequence (true branch)
            consequence = root_node.child_by_field_name("consequence")
            if consequence:
                if consequence.type in variable_type + ["field_expression"]:
                    add_entry(parser, rda_table, parent_id, used=consequence)
                elif consequence.type in literal_types:
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
                        consequence, literal_types, index=parser.index
                    )
                    for literal in literals_used:
                        add_entry(parser, rda_table, parent_id, used=literal)

            # Extract and track alternative (false branch)
            alternative = root_node.child_by_field_name("alternative")
            if alternative:
                if alternative.type in variable_type + ["field_expression"]:
                    add_entry(parser, rda_table, parent_id, used=alternative)
                elif alternative.type in literal_types:
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
                        alternative, literal_types, index=parser.index
                    )
                    for literal in literals_used:
                        add_entry(parser, rda_table, parent_id, used=literal)

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
            # Note: "lambda_expression" is NOT in stop_types so that identifiers inside
            # lambda bodies can find their parent statement (e.g., Node 51 in lambda body)
            handled_types_local = (def_statement + assignment + increment_statement +
                                  function_calls + declaration_statement +
                                  ["return_statement", "catch_clause", "throw_statement",
                                   "conditional_expression"])
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

            # Skip if this identifier is part of a declaration (being declared, not used)
            if parent_statement.type in declaration_statement:
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


def name_match_with_fields(use_name, def_name):
    """
    Check if a definition satisfies a use (handling field access).

    Args:
        use_name: The name being used (e.g., "obj" or "obj.field")
        def_name: The name being defined (e.g., "obj" or "obj.field")

    Returns:
        True if the definition can satisfy the use
    """
    # Exact match
    if use_name == def_name:
        return True

    # If using a field (obj.field), it can be satisfied by:
    # 1. A definition of the same field (obj.field)
    # 2. A definition of the whole object (obj)
    if "." in use_name:
        # Check if def_name is the base object
        base_obj = use_name.split(".")[0]
        if def_name == base_obj:
            return True

    # If using just an object (obj), it can only be satisfied by
    # a definition of the object itself, not its fields
    # So we don't match if def_name is a field of use_name

    return False


def get_required_edges_from_def_to_use(index, cfg, rda_solution, rda_table,
                                       graph_nodes, processed_edges, properties, lambda_map=None, node_list=None, parser=None):
    """
    Generate DFG edges from RDA solution.

    For each statement s:
        For each use u in USE[s]:
            For each def d in IN[s]:
                If d.name == u.name and scope_check(d.scope, u.scope):
                    Add edge: d.line → s

    Args:
        lambda_map: Dict mapping variable names to lambda information
        node_list: Dict mapping node indices to AST nodes
    """
    if lambda_map is None:
        lambda_map = {}
    if node_list is None:
        node_list = {}
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
            # Collect all matching definitions first
            matching_defs = []
            matching_field_defs = []

            for available_def in rda_solution[node]["IN"]:
                # In C++, even declarations without explicit initializers can define values
                # (e.g., "Book obj;" calls the default constructor)
                # So we don't skip declarations for C++
                # For other languages, skip uninitialized declarations
                if parser.src_language != "cpp":
                    if hasattr(available_def, 'declaration') and hasattr(available_def, 'has_initializer'):
                        if available_def.declaration and not available_def.has_initializer:
                            continue

                # Exact match
                if available_def.name == used.name:
                    # Check if DEF's scope can reach where the USE appears (variable_scope)
                    if scope_check(available_def.scope, used.variable_scope):
                        matching_defs.append(available_def)
                # Partial match for field access
                elif "." in used.name or "." in available_def.name:
                    if name_match_with_fields(used.name, available_def.name):
                        if scope_check(available_def.scope, used.variable_scope):
                            matching_field_defs.append(available_def)

            # Filter out definitions that are "killed" by later definitions in the same path
            # If this node defines the same variable, prefer self-loop over earlier definitions
            def_info = rda_table[node]["def"] if node in rda_table else []
            defines_same_var = any(d.name == used.name for d in def_info)

            if defines_same_var:
                # This node both USES and DEFINES the variable
                # Create self-loop ONLY if:
                # 1. It's inside a loop, AND
                # 2. The reaching definitions include this same node (from a previous iteration)
                # Otherwise, it's either a sequential update (e.g., node++ in switch) or
                # the value comes from a different statement in the previous iteration
                if matching_defs:
                    # Get the AST node to check if it's inside a loop
                    node_key = read_index(index, node) if node in index.values() else None
                    ast_node = node_list.get(node_key) if node_list and node_key else None

                    # Check if any of the reaching definitions is from this same node
                    # This indicates a true loop-carried dependency where the statement
                    # uses its own output from a previous iteration
                    has_loop_carried_def = any(d.line == node for d in matching_defs)

                    # Only create self-loop if there's actually a loop-carried dependency
                    if has_loop_carried_def and ast_node and is_node_inside_loop(ast_node):
                        add_edge(final_graph, node, node,
                               {'dataflow_type': 'loop_carried',
                                'edge_type': 'DFG_edge',
                                'color': '#FFA500',
                                'used_def': used.name})

                    # Also add edges from reaching definitions (initial flow into the loop or statement)
                    for available_def in matching_defs:
                        if available_def.line != node:
                            add_edge(final_graph, available_def.line, node,
                                   {'dataflow_type': 'comesFrom',
                                    'edge_type': 'DFG_edge',
                                    'color': '#00A3FF',
                                    'used_def': used.name})
                    used.satisfied = True
            elif matching_defs:
                # For each matching definition, create an edge
                for available_def in matching_defs:
                    if available_def.line != node:
                        add_edge(final_graph, available_def.line, node,
                               {'dataflow_type': 'comesFrom',
                                'edge_type': 'DFG_edge',
                                'color': '#00A3FF',
                                'used_def': used.name})
                        used.satisfied = True
                # Only mark satisfied after creating edges
                if matching_defs:
                    used.satisfied = True
            elif matching_field_defs:
                # Handle field access matches
                for available_def in matching_field_defs:
                    if name_match_with_fields(used.name, available_def.name):
                        if scope_check(available_def.scope, used.variable_scope):
                            # Prevent self-loops: don't create edge from a node to itself
                            if available_def.line != node:
                                add_edge(final_graph, available_def.line, node,
                                       {'dataflow_type': 'comesFrom',
                                        'edge_type': 'DFG_edge',
                                        'color': '#00A3FF',
                                        'used_def': used.name})
                            used.satisfied = True

            # Handle unsatisfied function identifier references (e.g., &function_name)
            # Functions are globally available, not limited by control flow
            if not used.satisfied:
                # Search all DEF entries globally for a matching function definition
                for def_node in graph_nodes:
                    if def_node not in rda_table:
                        continue
                    for definition in rda_table[def_node]["def"]:
                        # Enhanced matching for qualified names
                        # Check if names match (either exact match or matching base names)
                        names_match = False

                        # Exact match (e.g., "Room1::getId" == "Room1::getId")
                        if definition.name == used.name:
                            names_match = True
                        # Extract base names for comparison
                        else:
                            def_base = definition.name.split("::")[-1] if "::" in definition.name else definition.name
                            used_base = used.name.split("::")[-1] if "::" in used.name else used.name

                            # If base names match, check if the qualified parts match
                            if def_base == used_base:
                                # If used.name has namespace qualifier, it must match
                                if "::" in used.name:
                                    # The qualified name must match exactly
                                    names_match = (definition.name == used.name)
                                else:
                                    # If used.name has no qualifier, we can't match to a specific namespace
                                    # This would be ambiguous, so skip
                                    names_match = False

                        if names_match:
                            # Check if this is a function definition node
                            node_type = read_index(index, def_node)[-1] if def_node in index.values() else None
                            if node_type == "function_definition":
                                # For a proper DFG, we need to track data flow from return statements
                                # to the call site, not from function definition to call site

                                # Find return statements that belong to this specific function
                                # Strategy: Use namespace scope + line number proximity
                                # A return belongs to a function if:
                                # 1. It has the same namespace scope (first N-1 elements of function scope)
                                # 2. Its line number is greater than the function's line number
                                # 3. It's the closest return after the function definition

                                func_scope = definition.scope
                                func_line = definition.line
                                # Namespace scope is all but the last element (last is function scope ID)
                                namespace_scope = func_scope[:-1] if len(func_scope) > 1 else func_scope

                                return_nodes = []

                                for rnode in graph_nodes:
                                    # Check if this is a return statement
                                    rnode_type = read_index(index, rnode)[-1] if rnode in index.values() else None
                                    if rnode_type == "return_statement":
                                        # Check if return has a value (not void)
                                        has_return_value = False
                                        return_scope = None
                                        return_line = None

                                        # Check use entries (for the returned variable)
                                        if rnode in rda_table and rda_table[rnode].get("use"):
                                            for ret_use in rda_table[rnode]["use"]:
                                                return_scope = ret_use.scope
                                                return_line = ret_use.line
                                                has_return_value = True
                                                break

                                        # Check if this return belongs to the same namespace and comes after the function
                                        if has_return_value and return_scope and return_line:
                                            # Check if namespace scope matches
                                            namespace_matches = (len(return_scope) == len(namespace_scope) and
                                                               all(return_scope[i] == namespace_scope[i]
                                                                   for i in range(len(namespace_scope))))

                                            # Check if return comes after function definition
                                            # We need to check that the return is inside this specific function
                                            # by verifying it's between this function and the next function/block
                                            if namespace_matches and return_line > func_line:
                                                # Additional check: find all function definitions in the same namespace
                                                # and verify this return comes before the next function
                                                is_in_this_function = True

                                                # Find the next function definition in the same namespace after func_line
                                                next_func_line = float('inf')
                                                for other_node in graph_nodes:
                                                    other_type = read_index(index, other_node)[-1] if other_node in index.values() else None
                                                    if other_type == "function_definition" and other_node != def_node:
                                                        if other_node in rda_table:
                                                            for other_def in rda_table[other_node].get("def", []):
                                                                other_scope = other_def.scope
                                                                other_line = other_def.line
                                                                # Check if in same namespace
                                                                other_namespace = other_scope[:-1] if len(other_scope) > 1 else other_scope
                                                                if (other_namespace == namespace_scope and
                                                                    other_line > func_line and
                                                                    other_line < next_func_line):
                                                                    next_func_line = other_line

                                                # Return belongs to this function if it's before the next function
                                                if return_line < next_func_line:
                                                    return_nodes.append(rnode)

                                # Create edges from return statements to the call site
                                if return_nodes:
                                    for ret_node in return_nodes:
                                        if ret_node != node:
                                            # Data flows from the return statement to the variable assignment
                                            add_edge(final_graph, ret_node, node,
                                                   {'dataflow_type': 'comesFrom',
                                                    'edge_type': 'DFG_edge',
                                                    'color': '#00A3FF',
                                                    'used_def': used.name})
                                    used.satisfied = True
                                    break
                                # If no return statements found (void function or no explicit return),
                                # don't create any edge - void functions don't flow data

            # Handle unsatisfied global/static variable references
            # Global and static variables are available throughout the program
            if not used.satisfied:
                # Search all DEF entries globally for matching global-scope definitions
                for def_node in graph_nodes:
                    if def_node not in rda_table:
                        continue
                    for definition in rda_table[def_node]["def"]:
                        if definition.name == used.name:
                            # Check if this is a global-scope definition (scope = [0])
                            if definition.scope == [0] and scope_check(definition.scope, used.scope):
                                # Prevent self-loops: don't create edge from a node to itself
                                if definition.line != node:
                                    # Add edge from global definition to usage
                                    add_edge(final_graph, definition.line, node,
                                           {'dataflow_type': 'comesFrom',
                                        'edge_type': 'DFG_edge',
                                        'color': '#00A3FF',
                                        'used_def': used.name})
                                used.satisfied = True
                                break
                    if used.satisfied:
                        break

            # Handle unsatisfied namespace variable references
            # Namespace variables are available within their namespace
            if not used.satisfied:
                # Search all DEF entries globally for matching namespace-scope definitions
                for def_node in graph_nodes:
                    if def_node not in rda_table:
                        continue
                    for definition in rda_table[def_node]["def"]:
                        if definition.name == used.name:
                            # Check if this is a namespace-scope variable
                            # Both definition and use should be in the same namespace
                            if len(definition.scope) >= 2 and len(used.scope) >= 2:
                                # Check if they share the same namespace (first two elements of scope)
                                if definition.scope[0] == used.scope[0] and definition.scope[1] == used.scope[1]:
                                    # Prevent self-loops: don't create edge from a node to itself
                                    if definition.line != node:
                                        # Add edge from namespace definition to usage
                                        add_edge(final_graph, definition.line, node,
                                               {'dataflow_type': 'comesFrom',
                                                'edge_type': 'DFG_edge',
                                                'color': '#00A3FF',
                                                'used_def': used.name})
                                    used.satisfied = True
                                    break
                    if used.satisfied:
                        break

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

    # Add function parameter/return and OOP edges
    for edge in processed_edges:
        # Get edge label to determine the type of data flow
        edge_data = cfg.get_edge_data(*edge)
        if edge_data and len(edge_data) > 0:
            edge_data = edge_data[0]
            label = edge_data.get("label", "")

            # Determine the data flow type and description
            if label == "constructor_call":
                # Object declaration → constructor: 'this' pointer creation
                source_node = node_list.get(read_index(index, edge[0]))
                # Extract the object name from the declaration
                obj_name = "this"
                if source_node and source_node.type == "declaration":
                    # Try to get the declarator
                    for child in source_node.named_children:
                        if child.type in ["init_declarator", "identifier", "type_identifier"]:
                            if child.type == "init_declarator":
                                decl = child.child_by_field_name("declarator")
                                if decl and decl.type == "identifier":
                                    obj_name = st(decl)
                            elif child.type == "identifier":
                                obj_name = st(child)

                add_edge(final_graph, edge[0], edge[1],
                       {'dataflow_type': 'constructor_call',
                        'edge_type': 'DFG_edge',
                        'color': '#FF6B6B',
                        'object_name': obj_name})

            elif label == "base_constructor_call":
                # Derived constructor → base constructor: 'this' pointer chain
                add_edge(final_graph, edge[0], edge[1],
                       {'dataflow_type': 'base_constructor_call',
                        'edge_type': 'DFG_edge',
                        'color': '#FF6B6B',
                        'object_name': 'this'})

            elif label == "scope_exit_destructor":
                # Scope exit → destructor: object destruction
                add_edge(final_graph, edge[0], edge[1],
                       {'dataflow_type': 'destructor_call',
                        'edge_type': 'DFG_edge',
                        'color': '#C44569',
                        'object_name': 'this'})

            elif label == "base_destructor_call":
                # Derived destructor → base destructor: 'this' pointer chain
                add_edge(final_graph, edge[0], edge[1],
                       {'dataflow_type': 'base_destructor_call',
                        'edge_type': 'DFG_edge',
                        'color': '#C44569',
                        'object_name': 'this'})

            elif label == "virtual_call":
                # Virtual method call → implementation: polymorphic dispatch
                # Extract the object variable name from the call site
                source_node = node_list.get(read_index(index, edge[0]))
                obj_name = "this"

                if source_node and source_node.type == "expression_statement":
                    # Get the call_expression
                    call_expr = source_node.named_children[0] if source_node.named_children else None
                    if call_expr and call_expr.type == "call_expression":
                        # Get the function being called (should be field_expression)
                        func_node = call_expr.child_by_field_name("function")
                        if func_node and func_node.type == "field_expression":
                            # Extract the base object (argument)
                            arg_node = func_node.child_by_field_name("argument")
                            if arg_node:
                                obj_name = st(arg_node)

                add_edge(final_graph, edge[0], edge[1],
                       {'dataflow_type': 'virtual_dispatch',
                        'edge_type': 'DFG_edge',
                        'color': '#4834DF',
                        'object_name': obj_name})

            elif label == "method_call":
                # Non-virtual method call → implementation: static dispatch
                # Extract the object variable name from the call site
                source_node = node_list.get(read_index(index, edge[0]))
                obj_name = "this"

                if source_node and source_node.type == "expression_statement":
                    # Get the call_expression
                    call_expr = source_node.named_children[0] if source_node.named_children else None
                    if call_expr and call_expr.type == "call_expression":
                        # Get the function being called (should be field_expression)
                        func_node = call_expr.child_by_field_name("function")
                        if func_node and func_node.type == "field_expression":
                            # Extract the base object (argument)
                            arg_node = func_node.child_by_field_name("argument")
                            if arg_node:
                                obj_name = st(arg_node)

                add_edge(final_graph, edge[0], edge[1],
                       {'dataflow_type': 'method_call',
                        'edge_type': 'DFG_edge',
                        'color': '#00CED1',
                        'object_name': obj_name})

            else:
                # Only add parameter edges for function returns, not function calls
                # Function calls (call -> function) don't represent data flow in this simple model
                # Return statements (return -> call) do represent data flow
                if label in ["method_return", "function_return"]:
                    add_edge(final_graph, edge[0], edge[1],
                           {'dataflow_type': 'parameter',
                            'edge_type': 'DFG_edge'})
                # Skip function_call edges - they would be backwards (call -> function)
                # We already handle argument-to-parameter flow via RDA

    # Phase 3: Lambda indirect call resolution
    # Connect function pointer/lambda calls to their execution targets
    if lambda_map:
        # Build a reverse map: parameter_name -> lambda_name
        # This tracks which parameters might hold which lambdas
        param_to_lambda = {}  # {(param_name, func_def_node): lambda_var_name}

        # Analyze parameter flow edges to find lambda->parameter mappings
        for call_node, func_def_node in processed_edges:
            # Check if the call passes a lambda variable as argument
            if call_node not in rda_table:
                continue

            # Get arguments used at call site
            uses = rda_table[call_node].get("use", [])

            # Get parameters defined at function definition
            if func_def_node not in rda_table:
                continue
            params = rda_table[func_def_node].get("def", [])

            # At a function_definition node, the first DEF is the function name itself,
            # followed by the actual parameters. We only want to map parameters, not the function name.
            # So skip the first param if it's a function_definition node.
            node_type = read_index(index, func_def_node)[-1] if func_def_node in index.values() else None
            actual_params = params[1:] if node_type == "function_definition" and params else params

            # Match arguments to parameters (simplified: assumes order correspondence)
            # In reality, would need more sophisticated matching
            for used_var in uses:
                if not isinstance(used_var, Identifier):
                    continue
                if used_var.method_call:
                    continue  # Skip function calls, we want variable references

                # Check if this variable holds a lambda
                if used_var.name in lambda_map:
                    # This argument is a lambda!
                    # Map all actual parameters (not function name) to this lambda
                    for param in actual_params:
                        if isinstance(param, Identifier) and not param.method_call:
                            param_to_lambda[(param.name, func_def_node)] = used_var.name
                            if debug:
                                logger.info(f"Mapped parameter {param.name} in func {func_def_node} "
                                          f"to lambda {used_var.name}")

        # Now find indirect calls through function pointers/parameters
        for node in graph_nodes:
            if node not in rda_table:
                continue

            uses = rda_table[node].get("use", [])

            # Check if this is a function call (has method_call=True)
            for used_var in uses:
                if not isinstance(used_var, Identifier):
                    continue
                if not used_var.method_call:
                    continue  # Not a function call

                # Check if this is calling a parameter that holds a lambda
                # Find which function this call is in
                node_type = read_index(index, node)[-1] if node in index.values() else None

                # Search for reaching definitions of this variable
                reaching_defs = rda_solution[node]["IN"]
                for def_var in reaching_defs:
                    if not isinstance(def_var, Identifier):
                        continue
                    if def_var.name != used_var.name:
                        continue

                    # Check if this definition is a parameter that maps to a lambda
                    key = (def_var.name, def_var.line)
                    if key in param_to_lambda:
                        lambda_var = param_to_lambda[key]
                        lambda_info = lambda_map[lambda_var]

                        # Add edges from call site to lambda body execution
                        for body_node in lambda_info["body_nodes"]:
                            add_edge(final_graph, node, body_node,
                                   {'dataflow_type': 'lambda_call',
                                    'edge_type': 'DFG_edge',
                                    'color': '#FF6B6B',
                                    'lambda_var': lambda_var})
                            if debug:
                                logger.info(f"Added lambda call edge: {node} -> {body_node} "
                                          f"(calling lambda {lambda_var})")

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


def collect_call_site_information(parser, function_metadata, cfg_graph):
    """
    Collect information about function call sites for interprocedural analysis.

    For each call site, track:
    - Which function is called
    - Which arguments are passed by reference (&var)
    - The mapping of actual arguments to formal parameters

    Returns:
        List of dicts with call site information:
        {
            "call_site_node": AST node,
            "call_site_id": CFG node ID,
            "function_name": str,
            "pass_by_ref_args": [(arg_idx, var_name, var_node), ...]
        }
    """
    call_sites = []
    index = parser.index

    # Find all function call expressions
    for node in traverse_tree(parser.tree.root_node):
        if node.type == "call_expression":
            # Get function name
            function_name = None
            func_node = node.child_by_field_name("function")
            if func_node:
                if func_node.type == "identifier":
                    function_name = st(func_node)
                elif func_node.type == "qualified_identifier":
                    # Handle qualified names like std::function
                    function_name = st(func_node)
                elif func_node.type == "field_expression":
                    # Method call - skip for now, focus on functions
                    continue

            if not function_name or function_name not in function_metadata:
                continue  # Not a user-defined function we have metadata for

            # Get call site CFG node ID
            parent_statement = return_first_parent_of_types(
                node, statement_types["node_list_type"]
            )
            if not parent_statement:
                continue

            call_site_id = get_index(parent_statement, index)
            if call_site_id is None or call_site_id not in cfg_graph.nodes:
                continue

            # Extract pass-by-reference arguments
            pass_by_ref_args = []
            args_node = node.child_by_field_name("arguments")
            if args_node:
                # Check if this function has pointer parameters
                func_params = function_metadata[function_name]["params"]

                for arg_idx, arg in enumerate(args_node.named_children):
                    # Check if the corresponding parameter is a pointer or reference
                    if arg_idx < len(func_params):
                        param_name, is_pointer, is_reference, param_idx = func_params[arg_idx]

                        if is_pointer or is_reference:
                            # Check if this is &var (address-of expression)
                            if arg.type == "pointer_expression":
                                # Check if it's actually & operator (not dereference *)
                                has_ampersand = False
                                arg_node = None
                                for arg_child in arg.children:
                                    if arg_child.type == "&":
                                        has_ampersand = True
                                    elif arg_child.is_named:
                                        arg_node = arg_child

                                if has_ampersand and arg_node:
                                    if arg_node.type in ["identifier", "this"]:
                                        var_name = st(arg_node)
                                        pass_by_ref_args.append((arg_idx, var_name, arg_node))
                            # C++ references can be passed directly without &
                            elif is_reference and arg.type in ["identifier", "this"]:
                                var_name = st(arg)
                                pass_by_ref_args.append((arg_idx, var_name, arg))
                            # Arrays decay to pointers - handle direct array passing
                            elif is_pointer and arg.type in ["identifier", "this"]:
                                var_name = st(arg)
                                # Check if this is an array variable in the symbol table
                                arg_index = get_index(arg, index)
                                if arg_index and arg_index in parser.symbol_table["scope_map"]:
                                    pass_by_ref_args.append((arg_idx, var_name, arg))

            if pass_by_ref_args:
                call_sites.append({
                    "call_site_node": node,
                    "call_site_id": call_site_id,
                    "function_name": function_name,
                    "pass_by_ref_args": pass_by_ref_args
                })

    return call_sites


def find_modification_sites(parser, function_metadata, pointer_modifications):
    """
    Find all modification sites for pointer/reference parameters inside functions.

    For each function, find all statements where a pointer/reference parameter is modified.

    Returns:
        Dict mapping function_name -> list of (param_idx, modification_node, statement_id)
    """
    modification_sites = {}
    index = parser.index

    for func_name, meta in function_metadata.items():
        modifications = []
        func_node = meta["node"]
        modified_params = pointer_modifications.get(func_name, set())

        # Build map of parameter names to indices (only for modified pointer/reference params)
        param_name_to_idx = {}
        for param_name, is_pointer, is_reference, param_idx in meta["params"]:
            if (is_pointer or is_reference) and param_idx in modified_params:
                param_name_to_idx[param_name] = param_idx

        if not param_name_to_idx:
            modification_sites[func_name] = modifications
            continue

        # Find all modification sites in function body
        for node in traverse_tree(func_node):
            modification_param_idx = None
            mod_node = None

            # Check for assignment expressions
            if node.type == "assignment_expression":
                left = node.child_by_field_name("left")
                if left:
                    # Check for *param = ... (pointer dereference)
                    if left.type == "pointer_expression":
                        arg = left.child_by_field_name("argument")
                        if arg and arg.type in ["identifier", "this"]:
                            var_name = st(arg)
                            if var_name in param_name_to_idx:
                                modification_param_idx = param_name_to_idx[var_name]
                                mod_node = node

                    # Check for param[i] = ... or param = ... (subscript or direct)
                    elif left.type == "subscript_expression":
                        array_arg = left.child_by_field_name("argument")
                        if array_arg and array_arg.type in ["identifier", "this"]:
                            var_name = st(array_arg)
                            if var_name in param_name_to_idx:
                                modification_param_idx = param_name_to_idx[var_name]
                                mod_node = node

                    # Check for direct assignment to reference parameter
                    elif left.type in ["identifier", "this"]:
                        var_name = st(left)
                        if var_name in param_name_to_idx:
                            modification_param_idx = param_name_to_idx[var_name]
                            mod_node = node

            # Check for update expressions (++, --)
            elif node.type == "update_expression":
                arg = node.child_by_field_name("argument")
                if arg:
                    # Handle parenthesized expressions like (*n)++
                    if arg.type == "parenthesized_expression":
                        # Get the inner expression
                        inner_children = [c for c in arg.named_children if c.is_named]
                        if inner_children:
                            arg = inner_children[0]

                    # Check for (*param)++ or ++(*param)
                    if arg.type == "pointer_expression":
                        inner_arg = arg.child_by_field_name("argument")
                        if inner_arg and inner_arg.type in ["identifier", "this"]:
                            var_name = st(inner_arg)
                            if var_name in param_name_to_idx:
                                modification_param_idx = param_name_to_idx[var_name]
                                mod_node = node
                    # Check for param++ or param[i]++
                    elif arg.type == "subscript_expression":
                        array_arg = arg.child_by_field_name("argument")
                        if array_arg and array_arg.type in ["identifier", "this"]:
                            var_name = st(array_arg)
                            if var_name in param_name_to_idx:
                                modification_param_idx = param_name_to_idx[var_name]
                                mod_node = node
                    elif arg.type in ["identifier", "this"]:
                        var_name = st(arg)
                        if var_name in param_name_to_idx:
                            modification_param_idx = param_name_to_idx[var_name]
                            mod_node = node

            if modification_param_idx is not None and mod_node is not None:
                # Get the statement CFG node ID
                parent_statement = return_first_parent_of_types(
                    mod_node, statement_types["node_list_type"]
                )
                if parent_statement:
                    statement_id = get_index(parent_statement, index)
                    if statement_id is not None:
                        modifications.append((modification_param_idx, mod_node, statement_id))

        modification_sites[func_name] = modifications

    return modification_sites


def add_interprocedural_edges(final_graph, parser, call_sites, modification_sites,
                               function_metadata, cfg_graph, rda_table):
    """
    Add interprocedural DFG edges for pass-by-reference.

    For each call site where &var or reference is passed to a pointer/reference parameter:
    1. Add edge from call site to function definition (argument-parameter binding)
    2. Add edges from modification sites inside function to uses after the call

    Args:
        final_graph: The DFG graph to add edges to
        parser: C++ parser
        call_sites: List of call site information from collect_call_site_information()
        modification_sites: Dict from find_modification_sites()
        function_metadata: Dict from collect_function_metadata()
        cfg_graph: Control flow graph
        rda_table: RDA table with def/use information
    """
    index = parser.index

    for call_site_info in call_sites:
        call_site_id = call_site_info["call_site_id"]
        function_name = call_site_info["function_name"]
        pass_by_ref_args = call_site_info["pass_by_ref_args"]

        if function_name not in function_metadata or function_name not in modification_sites:
            continue

        func_meta = function_metadata[function_name]
        func_node = func_meta["node"]
        func_def_id = get_index(func_node, index)

        if func_def_id is None:
            continue

        # For each pass-by-reference argument
        for arg_idx, var_name, var_node in pass_by_ref_args:
            # 1. Add edge from call site to function definition (argument-parameter binding)
            add_edge(final_graph, call_site_id, func_def_id,
                   {'dataflow_type': 'comesFrom',
                    'edge_type': 'DFG_edge',
                    'color': '#00A3FF',
                    'used_def': var_name,
                    'interprocedural': 'call_to_function'})

            # 2. Find modification sites for this parameter
            mods = modification_sites.get(function_name, [])
            for mod_param_idx, mod_node, mod_statement_id in mods:
                if mod_param_idx == arg_idx:
                    # Find all uses of var_name after the call site
                    # We need to find successor nodes in CFG that use var_name
                    successors = []
                    visited = set()
                    queue = [call_site_id]

                    while queue:
                        current = queue.pop(0)
                        if current in visited:
                            continue
                        visited.add(current)

                        # Check if this node uses var_name
                        uses_var = False
                        defines_var = False
                        if current != call_site_id and current in rda_table:
                            for used in rda_table[current]["use"]:
                                if used.name == var_name:
                                    uses_var = True
                                    successors.append(current)
                                    break  # Found a use at this node

                            # Check if this node also defines var_name
                            for defined in rda_table[current]["def"]:
                                if defined.name == var_name:
                                    defines_var = True
                                    break

                        # Continue exploring if:
                        # 1. We're at the call site
                        # 2. We haven't found a use yet at this node
                        # 3. We found a use but it's also defined (pass-through like another function call)
                        if current == call_site_id or not uses_var or (uses_var and defines_var):
                            for edge in cfg_graph.out_edges(current):
                                if edge[1] not in visited:
                                    queue.append(edge[1])

                    # Add edges from modification site to uses after call
                    for use_site in successors:
                        add_edge(final_graph, mod_statement_id, use_site,
                               {'dataflow_type': 'comesFrom',
                                'edge_type': 'DFG_edge',
                                'color': '#00A3FF',
                                'used_def': var_name,
                                'interprocedural': 'modification_to_use'})


def add_argument_parameter_edges(final_graph, parser, cfg_graph, rda_table):
    """
    Add interprocedural DFG edges for argument-to-parameter data flow.

    For each function call:
    1. Extract arguments from call site
    2. Extract parameters from function definition
    3. Create edges from arguments to parameters

    Args:
        final_graph: The DFG graph to add edges to
        parser: C++ parser
        cfg_graph: Control flow graph with function_call edges
        rda_table: RDA table with def/use information
    """
    index = parser.index
    node_list = {(node.start_point, node.end_point, node.type): node
                 for node in traverse_tree(parser.tree, [])}

    # Process all function_call edges in CFG
    for edge in list(cfg_graph.edges()):
        edge_data = cfg_graph.get_edge_data(*edge)
        if edge_data and len(edge_data) > 0:
            edge_data = edge_data[0]
            label = edge_data.get("label", "")

            # Check if this is a function call edge
            if label.startswith("function_call|"):
                call_site_id = edge[0]     # Call site
                func_def_id = edge[1]      # Function definition

                # Get AST nodes
                call_site_node = node_list.get(read_index(index, call_site_id))
                func_def_node = node_list.get(read_index(index, func_def_id))

                if not (call_site_node and func_def_node):
                    continue

                # Verify function definition
                if func_def_node.type != "function_definition":
                    continue

                # Find the call_expression within the call site statement
                call_expr = None
                for child in traverse_tree(call_site_node, []):
                    if child.type == "call_expression":
                        call_expr = child
                        break

                if not call_expr:
                    continue

                # Extract arguments from call expression
                args_node = call_expr.child_by_field_name("arguments")
                if not args_node or not args_node.named_children:
                    continue  # No arguments

                arguments = args_node.named_children

                # Extract parameters from function definition
                declarator = func_def_node.child_by_field_name("declarator")
                if not declarator:
                    continue

                # Navigate through pointer/reference declarators if needed
                func_declarator = declarator
                while func_declarator and func_declarator.type in ["pointer_declarator", "reference_declarator"]:
                    for child in func_declarator.children:
                        if child.type == "function_declarator":
                            func_declarator = child
                            break
                    else:
                        break

                if not func_declarator or func_declarator.type != "function_declarator":
                    continue

                params_node = func_declarator.child_by_field_name("parameters")
                if not params_node or not params_node.named_children:
                    continue  # No parameters

                parameters = [p for p in params_node.named_children if p.type == "parameter_declaration"]

                # Match arguments to parameters (positional)
                for idx, (arg, param) in enumerate(zip(arguments, parameters)):
                    # Extract parameter name
                    param_declarator = param.child_by_field_name("declarator")
                    if not param_declarator:
                        continue

                    # Navigate through complex declarators
                    param_id = param_declarator
                    while param_id and param_id.type not in ["identifier"]:
                        if param_id.type in ["pointer_declarator", "reference_declarator"]:
                            for child in param_id.named_children:
                                if child.type == "identifier":
                                    param_id = child
                                    break
                                elif child.type in ["pointer_declarator", "reference_declarator", "function_declarator", "array_declarator"]:
                                    param_id = child
                                    break
                            else:
                                break
                        else:
                            break

                    if not param_id or param_id.type != "identifier":
                        continue

                    param_name = param_id.text.decode('utf-8')

                    # Create edge from argument (at call site) to parameter (at function definition)
                    # Note: We create edge from call_site to func_def, with metadata about which arg→param
                    add_edge(final_graph, call_site_id, func_def_id,
                           {'dataflow_type': 'comesFrom',
                            'edge_type': 'DFG_edge',
                            'color': '#00A3FF',
                            'used_def': param_name,
                            'interprocedural': 'argument_to_parameter',
                            'argument_index': idx})


def add_method_member_access_edges(final_graph, parser, cfg_graph, rda_table):
    """
    Add interprocedural DFG edges for method member access.

    When an object's method is called (obj.method()), create edges showing:
    1. The object flows to the method (as implicit 'this' parameter)
    2. Member accesses within the method (this->field) use the object's data

    Args:
        final_graph: The DFG graph to add edges to
        parser: C++ parser
        cfg_graph: Control flow graph with method_call edges
        rda_table: RDA table with def/use information
    """
    index = parser.index
    node_list = {(node.start_point, node.end_point, node.type): node
                 for node in traverse_tree(parser.tree, [])}

    # Process all method_call edges in CFG
    for edge in list(cfg_graph.edges()):
        edge_data = cfg_graph.get_edge_data(*edge)
        if edge_data and len(edge_data) > 0:
            edge_data = edge_data[0]
            label = edge_data.get("label", "")
            object_name = edge_data.get("object_name", "")

            # Check if this is a method call edge
            if label in ["method_call", "virtual_call"]:
                call_site_id = edge[0]     # Call site
                method_def_id = edge[1]    # Method definition

                # Get AST nodes
                call_site_node = node_list.get(read_index(index, call_site_id))
                method_def_node = node_list.get(read_index(index, method_def_id))

                if not (call_site_node and method_def_node):
                    continue

                # Verify method definition
                if method_def_node.type != "function_definition":
                    continue

                # Find field_expression nodes (member accesses) within the method body
                method_body = method_def_node.child_by_field_name("body")
                if not method_body:
                    continue

                # Collect all field accesses in the method body
                field_accesses = []
                for node in traverse_tree(method_body, []):
                    if node.type == "field_expression":
                        # Check if this is accessing a member (not calling a method on another object)
                        # We want field accesses like: title, author, pages (implicit this->field)
                        # or explicit: this->title
                        argument = node.child_by_field_name("argument")
                        field = node.child_by_field_name("field")

                        if argument and field:
                            arg_text = argument.text.decode('utf-8')
                            # Check if accessing via 'this' pointer or similar
                            if arg_text == "this" or arg_text == object_name:
                                # Find the statement containing this field access
                                parent_stmt = node
                                while parent_stmt and parent_stmt.type not in statement_types["node_list_type"]:
                                    parent_stmt = parent_stmt.parent

                                if parent_stmt:
                                    stmt_id = get_index(parent_stmt, index)
                                    if stmt_id and stmt_id in cfg_graph.nodes:
                                        field_name = field.text.decode('utf-8')
                                        field_accesses.append((stmt_id, field_name))

                # Also check for implicit member accesses (accessing members without 'this->')
                # In C++, members can be accessed directly within methods: cout << title;
                # Find the class/struct definition to get member names
                class_members = set()
                # Navigate up from method to find the class/struct
                parent = method_def_node.parent
                while parent:
                    if parent.type in ["class_specifier", "struct_specifier"]:
                        # Found the class/struct - extract member names
                        for node in traverse_tree(parent, []):
                            if node.type == "field_declaration":
                                declarator = node.child_by_field_name("declarator")
                                if declarator:
                                    if declarator.type == "identifier":
                                        class_members.add(declarator.text.decode('utf-8'))
                                    elif declarator.type == "field_identifier":
                                        class_members.add(declarator.text.decode('utf-8'))
                                    # Also check init_declarator
                                    for child in declarator.children:
                                        if child.type == "identifier":
                                            class_members.add(child.text.decode('utf-8'))
                        break
                    parent = parent.parent

                # Now check for implicit member accesses in USE entries within method
                for node_id in cfg_graph.nodes:
                    # Check if this node is within the method body
                    node_key = read_index(index, node_id) if node_id in index.values() else None
                    if not node_key:
                        continue
                    ast_node = node_list.get(node_key)
                    if not ast_node:
                        continue

                    # Check if this node is inside the method body
                    is_in_method = False
                    temp = ast_node
                    while temp:
                        if temp == method_body:
                            is_in_method = True
                            break
                        temp = temp.parent

                    if not is_in_method:
                        continue

                    # Check USE entries for this node
                    if node_id in rda_table:
                        for used in rda_table[node_id].get("use", []):
                            if isinstance(used, Identifier):
                                # Check if this identifier matches a class member
                                if used.core in class_members:
                                    field_accesses.append((node_id, used.core))

                # Create edges from call site object to member accesses within method
                for stmt_id, field_name in field_accesses:
                    # Add edge showing object's member is used by this statement in the method
                    add_edge(final_graph, call_site_id, stmt_id,
                           {'dataflow_type': 'comesFrom',
                            'edge_type': 'DFG_edge',
                            'color': '#00A3FF',
                            'used_def': f"{object_name}.{field_name}",
                            'interprocedural': 'method_member_access',
                            'object': object_name,
                            'member': field_name})


def add_function_return_edges(final_graph, parser, cfg_graph, rda_table):
    """
    Add interprocedural DFG edges for function return values.

    For each function call where the return value is used:
    1. Find the return statement(s) in the called function
    2. Extract the returned expression/variable
    3. Find the variable being initialized at the call site
    4. Create edge from returned expression to initialized variable

    Args:
        final_graph: The DFG graph to add edges to
        parser: C++ parser
        cfg_graph: Control flow graph with function_return/method_return edges
        rda_table: RDA table with def/use information
    """
    index = parser.index
    node_list = {(node.start_point, node.end_point, node.type): node
                 for node in traverse_tree(parser.tree, [])}

    # Process all function_return and method_return edges in CFG
    for edge in list(cfg_graph.edges()):
        edge_data = cfg_graph.get_edge_data(*edge)
        if edge_data and len(edge_data) > 0:
            edge_data = edge_data[0]
            label = edge_data.get("label", "")

            # Check if this is a function/method return edge
            if label in ["function_return", "method_return"]:
                return_node_id = edge[0]  # Return statement
                call_site_id = edge[1]     # Call site

                # Get AST nodes
                return_statement = node_list.get(read_index(index, return_node_id))
                call_site_node = node_list.get(read_index(index, call_site_id))

                if not (return_statement and call_site_node):
                    continue

                # Verify return statement has a value
                if return_statement.type != "return_statement" or not return_statement.named_children:
                    continue

                # Check if return value is actually used at call site
                if not is_return_value_used(call_site_node):
                    continue

                # Extract returned expression/variable from return statement
                # The return statement should have USE entries in rda_table
                returned_vars = []
                if return_node_id in rda_table:
                    for used in rda_table[return_node_id].get("use", []):
                        if isinstance(used, Identifier):
                            returned_vars.append(used.name)

                if not returned_vars:
                    continue

                # Extract the variable being initialized/assigned at call site
                # Look for DEF entries at the call site
                initialized_vars = []
                if call_site_id in rda_table:
                    for defined in rda_table[call_site_id].get("def", []):
                        if isinstance(defined, Identifier):
                            initialized_vars.append(defined.name)

                # Create edges from returned variable to initialized variable
                # For now, create edges for all combinations (could be refined)
                for ret_var in returned_vars:
                    for init_var in initialized_vars:
                        # Add edge from return statement to call site
                        # showing data flow from returned value to initialized variable
                        add_edge(final_graph, return_node_id, call_site_id,
                               {'dataflow_type': 'comesFrom',
                                'edge_type': 'DFG_edge',
                                'color': '#00A3FF',
                                'used_def': init_var,
                                'interprocedural': 'return_to_caller',
                                'returned_value': ret_var})


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

    # Phase 1: Preprocess CFG for function/method calls and OOP features
    processed_edges = []

    # Handle function/method calls and returns
    for edge in list(cfg_graph.edges()):
        edge_data = cfg_graph.get_edge_data(*edge)
        if edge_data and len(edge_data) > 0:
            edge_data = edge_data[0]
            label = edge_data.get("label", "")

            # Handle function calls (argument → parameter flow)
            if label.startswith("function_call|"):
                call_statement = node_list.get(read_index(index, edge[0]))
                function_def = node_list.get(read_index(index, edge[1]))

                # Verify we have a valid function call with arguments
                if call_statement and function_def:
                    if function_def.type == "function_definition":
                        # Check if function has parameters
                        declarator = function_def.child_by_field_name("declarator")
                        if declarator:
                            params_node = declarator.child_by_field_name("parameters")
                            if params_node and params_node.named_children:
                                # Function has parameters, add edge to track argument flow
                                processed_edges.append(edge)

            # Handle function returns (return value → caller flow)
            elif label in ["method_return", "function_return"]:
                return_statement = node_list.get(read_index(index, edge[0]))
                call_site_node = node_list.get(read_index(index, edge[1]))

                if return_statement and return_statement.type == "return_statement":
                    if return_statement.named_children:  # Function returns a value
                        # Only add edge if return value is actually used at call site
                        if call_site_node and is_return_value_used(call_site_node):
                            processed_edges.append(edge)

            # Handle constructor calls (object declaration → constructor)
            elif label == "constructor_call":
                # Edge from declaration statement to constructor
                # This represents the 'this' pointer (the object being constructed)
                processed_edges.append(edge)

            # Handle base constructor calls (derived constructor → base constructor)
            elif label == "base_constructor_call":
                # Edge from derived class constructor to base class constructor
                # This represents the 'this' pointer being passed up the constructor chain
                processed_edges.append(edge)

            # Handle destructor calls on scope exit (scope exit → destructor)
            elif label == "scope_exit_destructor":
                # Edge from scope exit (e.g., return statement, end of block) to destructor
                # This represents the object being destroyed
                processed_edges.append(edge)

            # Handle base destructor calls (derived destructor → base destructor)
            elif label == "base_destructor_call":
                # Edge from derived class destructor to base class destructor
                # This represents the 'this' pointer being passed up the destructor chain
                processed_edges.append(edge)

            # Handle virtual method calls (call site → actual implementation)
            elif label == "virtual_call":
                # Edge from call site to virtual method implementation
                # This represents the polymorphic dispatch
                processed_edges.append(edge)

            # Handle non-virtual method calls (call site → static method)
            elif label == "method_call":
                # Edge from call site to non-virtual method implementation
                # This represents static (compile-time) dispatch
                processed_edges.append(edge)

    # Phase 2: Discover lambdas
    start_lambda_time = time.time()
    lambda_map = discover_lambdas(parser, CFG_results)
    end_lambda_time = time.time()

    # Phase 2.5: Collect function metadata for interprocedural analysis
    function_metadata = collect_function_metadata(parser)
    pointer_modifications = analyze_pointer_modifications(parser, function_metadata)

    # Phase 3: Build RDA table
    start_rda_init_time = time.time()
    rda_table = build_rda_table(parser, CFG_results, lambda_map, function_metadata, pointer_modifications)
    end_rda_init_time = time.time()

    # Phase 4: Run RDA
    start_rda_time = time.time()
    rda_solution = start_rda(index, rda_table, cfg_graph)
    end_rda_time = time.time()

    # Phase 5: Generate DFG edges
    final_graph = get_required_edges_from_def_to_use(
        index, cfg_graph, rda_solution, rda_table,
        cfg_graph.nodes, processed_edges, properties, lambda_map, node_list, parser
    )

    # Phase 6: Add interprocedural edges for pass-by-reference
    call_sites = collect_call_site_information(parser, function_metadata, cfg_graph)
    modification_sites = find_modification_sites(parser, function_metadata, pointer_modifications)
    add_interprocedural_edges(final_graph, parser, call_sites, modification_sites,
                               function_metadata, cfg_graph, rda_table)

    # Phase 7: Add interprocedural edges for argument-to-parameter flow
    add_argument_parameter_edges(final_graph, parser, cfg_graph, rda_table)

    # Phase 8: Add interprocedural edges for function return values
    add_function_return_edges(final_graph, parser, cfg_graph, rda_table)

    # Phase 9: Add interprocedural edges for method member access
    add_method_member_access_edges(final_graph, parser, cfg_graph, rda_table)

    if debug:
        logger.info("RDA init: {:.3f}s, RDA: {:.3f}s",
                   end_rda_init_time - start_rda_init_time,
                   end_rda_time - start_rda_time)

    # Create debug graph
    debug_graph = rda_cfg_map(rda_solution, CFG_results)

    return final_graph, debug_graph, rda_table, rda_solution
