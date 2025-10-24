import traceback

import networkx as nx
from loguru import logger

from ...utils import cpp_nodes
from .CFG import CFGGraph


class CFGGraph_cpp(CFGGraph):
    def __init__(self, src_language, src_code, properties, root_node, parser):
        super().__init__(src_language, src_code, properties, root_node, parser)

        self.node_list = None
        # Import statement types from cpp_nodes
        self.statement_types = cpp_nodes.statement_types
        self.CFG_node_list = []
        self.CFG_edge_list = []
        self.records = {
            "basic_blocks": {},
            "function_list": {},                   # ((class, function), sig) → node_id
            "return_type": {},                     # ((class, function), sig) → return_type
            "class_list": {},                      # class_name → node_id
            "struct_list": {},                     # struct_name → node_id
            "enum_list": {},                       # enum_name → node_id
            "union_list": {},                      # union_name → node_id
            "typedef_list": {},                    # typedef_name → node_id
            "namespace_list": {},                  # namespace_name → node_id
            "template_list": {},                   # template_name → node_id
            "extends": {},                         # class_name → [base_classes]
            "function_calls": {},                  # sig → [(call_id, parent_id)]
            "method_calls": {},                    # sig → [(call_id, parent_id)]
            "constructor_calls": {},               # sig → [(call_id, parent_id)]
            "destructor_calls": {},                # class_name → [(call_id, parent_id)]
            "virtual_functions": {},               # function_id → {is_virtual, is_pure_virtual}
            "operator_overloads": {},              # function_id → operator_name
            "special_functions": {},               # function_id → "default" | "delete"
            "functions_with_initializers": {},     # function_id → True
            "lambda_map": {},                      # lambda_key → statement_node
            "switch_child_map": {},                # parent_id → switch_child_id
            "label_statement_map": {},             # label → node_key
            "return_statement_map": {},            # function_id → [return_node_ids]
            "implicit_return_map": {},             # function_id → implicit_return_node_id (for void functions)
            "constexpr_functions": {},             # function_id → True
            "inline_functions": {},                # function_id → True
            "noexcept_functions": {},              # function_id → True
            "attributed_functions": {},            # function_id → [attributes]
            "function_pointer_assignments": {},    # pointer_var → [function_names]
            "indirect_calls": {},                  # (pointer_var, sig) → [(call_id, parent_id)]
        }
        self.index_counter = max(self.index.values())
        self.CFG_node_indices = []

        # Track runtime types for polymorphic objects
        self.runtime_types = {}  # variable_name → actual_class_type (for new expressions)

        # Track objects created in each scope for RAII
        self.scope_objects = {}  # scope_key → [(var_name, class_type, decl_id, order)]
        self.object_scope_map = {}  # var_name → scope_key
        self.scope_nodes = {}  # scope_key → actual_scope_node

        # Access parser data (created by parser_driver)
        self.symbol_table = self.parser.symbol_table
        self.declaration = self.parser.declaration
        self.declaration_map = self.parser.declaration_map

        # Generate CFG
        self.CFG_node_list, self.CFG_edge_list = self.CFG_cpp()
        self.graph = self.to_networkx(self.CFG_node_list, self.CFG_edge_list)

    def get_index(self, node):
        """Get the unique index for a given AST node"""
        return self.index[(node.start_point, node.end_point, node.type)]

    def get_new_synthetic_index(self):
        """Generate a new unique index for synthetic nodes (implicit returns, etc.)"""
        self.index_counter += 1
        return self.index_counter

    def get_basic_blocks(self, CFG_node_list, CFG_edge_list):
        """Partition CFG into basic blocks using weakly connected components"""
        G = self.to_networkx(CFG_node_list, CFG_edge_list)
        components = nx.weakly_connected_components(G)
        block_index = 1
        for block in components:
            block_list = sorted(list(block))
            self.records["basic_blocks"][block_index] = block_list
            block_index += 1

    def append_block_index(self, CFG_node_list, records):
        """Append block index to each node in CFG_node_list"""
        updated_node_list = []
        for node_tuple in CFG_node_list:
            node_id = node_tuple[0]
            block_idx = self.get_key(node_id, records["basic_blocks"])
            if block_idx is not None:
                updated_node_list.append(node_tuple + (block_idx,))
            else:
                updated_node_list.append(node_tuple + (0,))
        return updated_node_list

    def get_key(self, val, dictionary):
        """Find the key in dictionary where val is in the value list"""
        for key, value in dictionary.items():
            if val in value:
                return key
        return None

    def get_containing_function(self, node):
        """Find the enclosing function definition for a given node"""
        while node is not None:
            if node.type == "function_definition":
                return node
            node = node.parent
        return None

    def get_containing_class(self, node):
        """Find the enclosing class or struct definition for a given node"""
        while node is not None:
            if node.type in ["class_specifier", "struct_specifier"]:
                return node
            node = node.parent
        return None

    def get_containing_namespace(self, node):
        """Find the enclosing namespace for a given node"""
        while node is not None:
            if node.type == "namespace_definition":
                return node
            node = node.parent
        return None

    def get_base_classes(self, class_node):
        """
        Extract base class names from a class_specifier node.
        Returns a set of base class names.
        Example: class Circle : public Shape { } -> {'Shape'}
        Example: class PaintedCircle : public Circle, public Paintable { } -> {'Circle', 'Paintable'}
        """
        base_classes = set()
        if class_node is None:
            return base_classes

        # Look for base_class_clause in the class definition
        for child in class_node.children:
            if child.type == "base_class_clause":
                # The base_class_clause contains type_identifier nodes for each base class
                for subchild in child.children:
                    if subchild.type == "type_identifier":
                        base_class_name = subchild.text.decode('utf-8')
                        base_classes.add(base_class_name)
                break

        return base_classes

    def is_jump_statement(self, node):
        """
        Check if a node is a jump statement that transfers control elsewhere.
        Jump statements should NOT have fall-through edges to the next statement.
        """
        if node is None:
            return False

        jump_types = [
            "break_statement",
            "continue_statement",
            "return_statement",
            "goto_statement",
            "throw_statement"
        ]

        return node.type in jump_types

    def get_next_index(self, current_node, node_list):
        """
        Find the next executable statement after current_node.
        Handles:
        - Sequential statements (next_named_sibling)
        - End of blocks (traverse up to parent)
        - Loop back edges
        - Function boundaries
        - Class boundaries
        - Namespace boundaries
        """
        next_node = current_node.next_named_sibling

        # If no sibling, traverse up the tree
        while next_node is None:
            parent = current_node.parent
            if parent is None:
                return (2, None)  # Exit node

            # Check if parent is a loop - return to loop header
            if parent.type in self.statement_types["loop_control_statement"]:
                if (parent.start_point, parent.end_point, parent.type) in node_list:
                    return (self.get_index(parent), parent)

            # Check if parent is a control statement
            if parent.type in self.statement_types["control_statement"]:
                current_node = parent
                next_node = current_node.next_named_sibling
                continue

            # Check if parent is a function definition - end of function
            if parent.type == "function_definition":
                # Check if this function has an implicit return node
                if (parent.start_point, parent.end_point, parent.type) in node_list:
                    fn_index = self.get_index(parent)
                    if self.records.get("implicit_return_map") and fn_index in self.records["implicit_return_map"]:
                        implicit_return_id = self.records["implicit_return_map"][fn_index]
                        return (implicit_return_id, None)
                return (2, None)

            # Check if parent is a class/struct - end of class
            if parent.type in ["class_specifier", "struct_specifier"]:
                return (2, None)

            # Check if parent is a namespace - continue to next in namespace
            if parent.type == "namespace_definition":
                current_node = parent
                next_node = current_node.next_named_sibling
                continue

            # Check if parent is a statement holder
            if parent.type in self.statement_types["statement_holders"]:
                current_node = parent
                next_node = current_node.next_named_sibling
                continue

            current_node = parent
            next_node = current_node.next_named_sibling

        # Skip empty compound statements
        if next_node.type == "compound_statement" and len(list(next_node.named_children)) == 0:
            current_node = next_node
            return self.get_next_index(current_node, node_list)

        # If next node is a compound statement, get first child
        if next_node.type == "compound_statement":
            children_list = list(next_node.named_children)
            if children_list:
                first_child = children_list[0]
                if (first_child.start_point, first_child.end_point, first_child.type) in node_list:
                    return (self.get_index(first_child), first_child)

        # If next node is a field_declaration, look inside for the actual statement
        if next_node.type == "field_declaration":
            # Field declarations wrap the actual declaration/expression
            # Recursively search for the first node inside that's in node_list
            def find_first_in_wrapper(wrapper_node):
                # Check all children
                for child in wrapper_node.named_children:
                    if (child.start_point, child.end_point, child.type) in node_list:
                        return (self.get_index(child), child)
                    # Recursively check grandchildren
                    result = find_first_in_wrapper(child)
                    if result:
                        return result
                return None

            result = find_first_in_wrapper(next_node)
            if result:
                return result

        # Check if next_node is in node_list
        if (next_node.start_point, next_node.end_point, next_node.type) in node_list:
            return (self.get_index(next_node), next_node)

        # If not, recursively find the next node
        return self.get_next_index(next_node, node_list)

    def is_last_in_control_block(self, node):
        """
        Check if a node is the last statement in a control flow block (if/else/loop).
        These nodes should NOT have edges added in the sequential flow step,
        as they will be handled by the control flow step.
        """
        if node.parent is None:
            return False

        parent = node.parent

        # Case 1: Parent is a compound_statement (block with braces)
        if parent.type == "compound_statement":
            children = list(parent.named_children)
            if children and children[-1] == node:
                grandparent = parent.parent
                if grandparent and grandparent.type in [
                    "if_statement", "while_statement", "for_statement",
                    "for_range_loop", "do_statement", "else_clause"
                ]:
                    return True

        # Case 2: Parent is a control structure directly (single statement, no braces)
        if parent.type in ["if_statement", "while_statement", "for_statement", "for_range_loop", "do_statement"]:
            consequence = parent.child_by_field_name("consequence")
            body = parent.child_by_field_name("body")

            if consequence and consequence == node:
                return True

            if body and body == node:
                return True

        # Case 3: Parent is an else_clause (single statement after else)
        if parent.type == "else_clause":
            children = list(parent.named_children)
            if children and node in children:
                return True

        return False

    def get_block_last_line(self, current_node, body_field="body"):
        """
        Find the last executable statement in a block.
        Used for connecting end of if/else/loop bodies to next statement.
        """
        block_node = current_node.child_by_field_name(body_field)

        if block_node is None:
            # No explicit body field, check for compound_statement child
            for child in current_node.children:
                if child.type == "compound_statement":
                    block_node = child
                    break

        if block_node is None:
            return (current_node, current_node.type)

        # If block is a statement holder, find last statement in it
        while block_node.type in self.statement_types["statement_holders"]:
            children = list(block_node.named_children)
            if not children:
                return (current_node, current_node.type)

            # Get last named child
            last_child = children[-1]

            # Check if it's a statement type
            if last_child.type in self.statement_types["node_list_type"]:
                return (last_child, last_child.type)

            block_node = last_child

        return (block_node, block_node.type)

    def edge_first_line(self, node, node_list):
        """
        Find the first executable line in a function/block and create edge.
        Returns the first statement node and its index.
        """
        body_node = None

        # For function_definition, find the compound_statement
        if node.type == "function_definition":
            body_node = node.child_by_field_name("body")

        # For class/struct, find the field_declaration_list
        if node.type in ["class_specifier", "struct_specifier"]:
            for child in node.children:
                if child.type == "field_declaration_list":
                    body_node = child
                    break

        # For namespace, find the declaration_list
        if node.type == "namespace_definition":
            for child in node.children:
                if child.type == "declaration_list":
                    body_node = child
                    break

        if body_node is None:
            for child in node.children:
                if child.type == "compound_statement":
                    body_node = child
                    break

        if body_node is None:
            return None

        # Find first statement in body
        for child in body_node.named_children:
            if (child.start_point, child.end_point, child.type) in node_list:
                return (self.get_index(child), child)

        return None

    def get_last_statement_in_function_body(self, function_node, node_list):
        """
        Find the last executable statement in a function body.
        Used for destructor chaining - we need to find where the destructor body ends
        so we can connect it directly to the base class destructor.

        Args:
            function_node: The function_definition AST node
            node_list: Dictionary of all nodes in the CFG

        Returns:
            (node_id, node) tuple of the last statement, or None if not found
        """
        body_node = function_node.child_by_field_name("body")

        if body_node is None:
            # Try to find compound_statement
            for child in function_node.children:
                if child.type == "compound_statement":
                    body_node = child
                    break

        if body_node is None:
            return None

        # Find last statement in body (iterate backwards)
        named_children = list(body_node.named_children)
        for child in reversed(named_children):
            if (child.start_point, child.end_point, child.type) in node_list:
                return (self.get_index(child), child)

        return None

    def add_edge(self, src, dest, edge_type, additional_data=None):
        """Add an edge to the CFG edge list with validation and deduplication"""
        if src is None or dest is None:
            logger.error(f"Attempting to add edge with None: {src} -> {dest}")
            return

        # Check for duplicate edges (Fix #3: Deduplicate edges)
        if additional_data:
            edge_tuple = (src, dest, edge_type, additional_data)
        else:
            edge_tuple = (src, dest, edge_type)

        # Prevent duplicate edges
        if edge_tuple in self.CFG_edge_list:
            return

        self.CFG_edge_list.append(edge_tuple)

    def insert_scope_destructors(self, node_list):
        """
        Insert automatic destructor calls for objects going out of scope (RAII).
        For each scope with tracked objects:
        1. Find the last statement in that scope
        2. Create destructor call chain in reverse construction order
        3. Insert between last statement and next statement outside scope
        """

        index_to_key = {v: k for k, v in self.index.items()}

        for scope_key, objects in self.scope_objects.items():
            if not objects:
                continue

            # Sort objects by construction order
            objects_sorted = sorted(objects, key=lambda x: x[3])  # Sort by order field

            # Get the scope node from our stored mapping
            scope_start, scope_end, scope_type = scope_key
            scope_node = self.scope_nodes.get(scope_key)

            if not scope_node:
                continue

            # Find the last statement in this scope
            last_stmt_node = None
            last_stmt_id = None

            # Traverse scope to find last executable statement
            for key, node in node_list.items():
                # Check if this node is inside the scope
                if (node.start_point >= scope_start and
                    node.end_point <= scope_end and
                    node != scope_node):
                    # Check if it's an executable statement
                    if node.type in self.statement_types["node_list_type"]:
                        # Check if it's the last one
                        if last_stmt_node is None or node.start_point > last_stmt_node.start_point:
                            last_stmt_node = node
                            last_stmt_id = self.get_index(node)

            if not last_stmt_node or not last_stmt_id:
                continue

            # Find what comes after the scope
            next_after_scope_id, next_after_scope = self.get_next_index(scope_node, node_list)

            if next_after_scope_id == 2:
                # Scope exits to implicit return or exit
                # Check if scope is in a function
                parent = scope_node.parent
                while parent:
                    if parent.type == "function_definition":
                        # Get implicit return for this function
                        if (parent.start_point, parent.end_point, parent.type) in node_list:
                            fn_id = self.get_index(parent)
                            if fn_id in self.records.get("implicit_return_map", {}):
                                next_after_scope_id = self.records["implicit_return_map"][fn_id]
                        break
                    parent = parent.parent

            # Create destructor call chain for all objects (in reverse order)
            # Reverse order: last constructed is first destroyed
            objects_reversed = list(reversed(objects_sorted))

            # Build chain: last_stmt -> ~objN -> ~objN-1 -> ... -> ~obj1 -> next_after_scope
            if next_after_scope_id and next_after_scope_id != 2:
                # Create destructor call list for each object
                destructor_ids = []
                for var_name, class_name, decl_id, order in objects_reversed:
                    # Find the destructor for this class
                    destructor_name = f"~{class_name}"
                    destructor_id = None

                    for ((fn_class_name, fn_name), fn_sig), fn_id in self.records.get("function_list", {}).items():
                        if fn_name == destructor_name and fn_class_name == class_name:
                            destructor_id = fn_id
                            break

                    if destructor_id:
                        destructor_ids.append((var_name, class_name, destructor_id))

                # Chain them together
                # The approach: All destructor calls go through the same function,
                # but we create multiple edges from the implicit return node
                # Using MultiDiGraph, we can have multiple edges between same nodes
                if destructor_ids:
                    # Edge from last statement to first destructor call
                    first_var_name, first_class_name, first_dest_id = destructor_ids[0]
                    self.add_edge(last_stmt_id, first_dest_id, "scope_exit_destructor")

                    # Chain destructor returns together
                    # All objects of the same class use the same destructor function
                    # So we need to add multiple edges from the same implicit_return node
                    for i in range(len(destructor_ids)):
                        var_name, class_name, curr_dest_id = destructor_ids[i]

                        # Get the implicit return for this destructor
                        implicit_return_id = self.records.get("implicit_return_map", {}).get(curr_dest_id)

                        if not implicit_return_id:
                            continue

                        # Determine where this destructor returns to
                        if i < len(destructor_ids) - 1:
                            # Chain to next destructor call
                            next_var_name, next_class_name, next_dest_id = destructor_ids[i + 1]
                            edge_label = f"destructor_chain|{var_name}"
                            self.add_edge(implicit_return_id, next_dest_id, edge_label)
                        else:
                            # Last destructor - return to next statement after scope
                            edge_label = f"scope_destructor_return|{var_name}"
                            self.add_edge(implicit_return_id, next_after_scope_id, edge_label)

    def function_list(self, root_node, node_list):
        """
        Build a map of all function/method calls in the program.
        Maps function signatures to their call sites.
        Handles:
        - Regular function calls
        - Member function calls (obj.method())
        - Constructor calls (MyClass obj)
        - Operator overload calls
        """
        if root_node.type == "call_expression":
            # Get function name
            function_node = root_node.child_by_field_name("function")
            if function_node:
                func_name = None
                is_indirect_call = False
                pointer_var = None

                # Case 1: Simple identifier (could be regular call or function pointer)
                if function_node.type == "identifier":
                    func_name = function_node.text.decode('utf-8')

                # Case 2: Field expression (member function call: obj.method())
                elif function_node.type == "field_expression":
                    field = function_node.child_by_field_name("field")
                    if field:
                        func_name = field.text.decode('utf-8')

                # Case 3: Qualified identifier (namespace::function or Class::method)
                elif function_node.type == "qualified_identifier":
                    func_name = function_node.text.decode('utf-8')

                # Case 4: Subscript expression (array of function pointers: operations[0](args))
                elif function_node.type == "subscript_expression":
                    is_indirect_call = True
                    # Get the array name
                    argument = function_node.child_by_field_name("argument")
                    if argument and argument.type == "identifier":
                        pointer_var = argument.text.decode('utf-8')

                # Find the parent statement node
                parent_stmt = root_node
                while parent_stmt and parent_stmt.type not in self.statement_types["node_list_type"]:
                    parent_stmt = parent_stmt.parent

                if parent_stmt and (parent_stmt.start_point, parent_stmt.end_point, parent_stmt.type) in node_list:
                    parent_index = self.get_index(parent_stmt)
                    call_index = self.get_index(function_node)

                    # Get argument types for signature matching
                    args_node = root_node.child_by_field_name("arguments")
                    signature = self.get_call_signature(args_node)

                    # Track indirect calls separately
                    if is_indirect_call and pointer_var:
                        key = (pointer_var, signature)
                        if key not in self.records["indirect_calls"]:
                            self.records["indirect_calls"][key] = []
                        self.records["indirect_calls"][key].append((call_index, parent_index))
                    elif func_name:
                        # Check if this identifier is in function_list (direct call) or might be a pointer (indirect)
                        # For now, treat all identifiers as potential direct calls
                        # We'll handle the distinction in add_function_call_edges

                        # Determine if this is a method call or function call
                        if function_node.type == "field_expression":
                            key = (func_name, signature)
                            if key not in self.records["method_calls"]:
                                self.records["method_calls"][key] = []
                            self.records["method_calls"][key].append((call_index, parent_index))
                        else:
                            key = (func_name, signature)
                            if key not in self.records["function_calls"]:
                                self.records["function_calls"][key] = []
                            self.records["function_calls"][key].append((call_index, parent_index))

        # Handle constructor calls from object declarations
        # Example patterns:
        # 1. Parameterized: Dog myDog("Buddy", 3);
        # 2. Default: ResourceHolder obj1;
        # 3. Copy: ResourceHolder obj3 = obj2;
        # 4. Move: ResourceHolder obj4 = std::move(obj2);
        elif root_node.type == "declaration":
            # Get the type (class name)
            type_node = root_node.child_by_field_name("type")
            if type_node and type_node.type == "type_identifier":
                class_name = type_node.text.decode('utf-8')

                # Find the parent statement node
                parent_stmt = root_node
                while parent_stmt and parent_stmt.type not in self.statement_types["node_list_type"]:
                    parent_stmt = parent_stmt.parent

                if parent_stmt and (parent_stmt.start_point, parent_stmt.end_point, parent_stmt.type) in node_list:
                    parent_index = self.get_index(parent_stmt)
                    call_index = parent_index

                    # Track this object for RAII (scope-based destruction)
                    # Find the containing scope (compound_statement)
                    scope_node = root_node.parent
                    while scope_node:
                        if scope_node.type == "compound_statement":
                            scope_key = (scope_node.start_point, scope_node.end_point, scope_node.type)
                            if scope_key not in self.scope_objects:
                                self.scope_objects[scope_key] = []
                            # Store the actual scope node for later use
                            if scope_key not in self.scope_nodes:
                                self.scope_nodes[scope_key] = scope_node
                            break
                        scope_node = scope_node.parent

                    # Check if there's an init_declarator or just a plain declarator
                    has_init_declarator = False
                    var_name = None
                    for child in root_node.children:
                        if child.type == "init_declarator":
                            has_init_declarator = True

                            # Extract variable name from declarator
                            declarator = child.child_by_field_name("declarator")
                            if declarator:
                                if declarator.type == "identifier":
                                    var_name = declarator.text.decode('utf-8')
                                # Handle other declarator types if needed

                            # Check for different constructor patterns
                            args_node = None
                            has_initializer = False
                            is_move = False
                            is_copy = False

                            for subchild in child.children:
                                if subchild.type == "argument_list":
                                    # Parameterized constructor: ResourceHolder obj2(101, "ResourceOne");
                                    args_node = subchild
                                    break
                                elif subchild.text.decode('utf-8') == "=":
                                    has_initializer = True
                                elif has_initializer and subchild.type == "call_expression":
                                    # Check if it's std::move
                                    func_node = subchild.child_by_field_name("function")
                                    if func_node:
                                        func_text = func_node.text.decode('utf-8')
                                        if "move" in func_text:
                                            # Move constructor: ResourceHolder obj4 = std::move(obj2);
                                            is_move = True
                                            # Get the argument to std::move for type checking
                                            args = subchild.child_by_field_name("arguments")
                                            if args and args.named_child_count > 0:
                                                moved_arg = args.named_children[0]
                                                # Create signature with the moved object's type
                                                signature = (f"{class_name}&&",)  # Rvalue reference
                                            break
                                elif has_initializer and subchild.type == "identifier":
                                    # Copy constructor: ResourceHolder obj3 = obj2;
                                    is_copy = True
                                    # Verify the identifier is of the same class type
                                    signature = (f"const {class_name}&",)  # Const lvalue reference
                                    break

                            if args_node:
                                # Parameterized constructor with explicit arguments
                                signature = self.get_call_signature(args_node)
                                key = (class_name, signature)
                                if key not in self.records["constructor_calls"]:
                                    self.records["constructor_calls"][key] = []
                                self.records["constructor_calls"][key].append((call_index, parent_index))
                            elif is_move:
                                # Move constructor
                                key = (class_name, signature)
                                if key not in self.records["constructor_calls"]:
                                    self.records["constructor_calls"][key] = []
                                self.records["constructor_calls"][key].append((call_index, parent_index))
                            elif is_copy:
                                # Copy constructor
                                key = (class_name, signature)
                                if key not in self.records["constructor_calls"]:
                                    self.records["constructor_calls"][key] = []
                                self.records["constructor_calls"][key].append((call_index, parent_index))
                            else:
                                # Default constructor: ResourceHolder obj1;
                                signature = tuple()  # Empty signature for default constructor
                                key = (class_name, signature)
                                if key not in self.records["constructor_calls"]:
                                    self.records["constructor_calls"][key] = []
                                self.records["constructor_calls"][key].append((call_index, parent_index))

                    # If no init_declarator, it's a plain declaration (default constructor)
                    # Example: ResourceHolder obj1;
                    if not has_init_declarator:
                        # Extract variable name from plain declarator
                        for child in root_node.children:
                            if child.type == "identifier":
                                var_name = child.text.decode('utf-8')
                                break

                        signature = tuple()  # Empty signature for default constructor
                        key = (class_name, signature)
                        if key not in self.records["constructor_calls"]:
                            self.records["constructor_calls"][key] = []
                        self.records["constructor_calls"][key].append((call_index, parent_index))

                    # Add object to scope tracking for RAII
                    if var_name and scope_node:
                        scope_key = (scope_node.start_point, scope_node.end_point, scope_node.type)
                        # Track: (var_name, class_name, decl_node_id, order)
                        order = len(self.scope_objects.get(scope_key, []))
                        self.scope_objects[scope_key].append((var_name, class_name, parent_index, order))
                        self.object_scope_map[var_name] = scope_key

        # Handle constructor calls from new expressions
        # Example: Base* basePtr = new Derived();
        elif root_node.type == "new_expression":
            # Get the type being constructed
            type_node = root_node.child_by_field_name("type")
            if type_node:
                class_name = None
                if type_node.type == "type_identifier":
                    class_name = type_node.text.decode('utf-8')

                if class_name:
                    # Track runtime type: find the variable being assigned
                    # Navigate up to find declaration or assignment
                    parent = root_node.parent
                    var_name = None
                    while parent:
                        if parent.type == "declaration":
                            # Get the declarator (variable name)
                            for child in parent.children:
                                if child.type == "init_declarator":
                                    declarator = child.child_by_field_name("declarator")
                                    if declarator:
                                        # Handle pointer declarators
                                        if declarator.type == "pointer_declarator":
                                            for subchild in declarator.children:
                                                if subchild.type == "identifier":
                                                    var_name = subchild.text.decode('utf-8')
                                                    break
                                        elif declarator.type == "identifier":
                                            var_name = declarator.text.decode('utf-8')
                                    break
                            break
                        elif parent.type == "assignment_expression":
                            # Get left side of assignment
                            left = parent.child_by_field_name("left")
                            if left and left.type == "identifier":
                                var_name = left.text.decode('utf-8')
                            break
                        parent = parent.parent

                    # Store runtime type mapping
                    if var_name:
                        self.runtime_types[var_name] = class_name

                    # Find the parent statement node
                    parent_stmt = root_node
                    while parent_stmt and parent_stmt.type not in self.statement_types["node_list_type"]:
                        parent_stmt = parent_stmt.parent

                    if parent_stmt and (parent_stmt.start_point, parent_stmt.end_point, parent_stmt.type) in node_list:
                        parent_index = self.get_index(parent_stmt)

                        # Get the new_expression node itself if it's in node_list
                        call_index = parent_index
                        if (root_node.start_point, root_node.end_point, root_node.type) in node_list:
                            call_index = self.get_index(root_node)

                        # Check for argument_list (constructor arguments)
                        args_node = root_node.child_by_field_name("arguments")

                        if args_node:
                            # Parameterized constructor
                            signature = self.get_call_signature(args_node)
                        else:
                            # Default constructor
                            signature = tuple()

                        key = (class_name, signature)
                        if key not in self.records["constructor_calls"]:
                            self.records["constructor_calls"][key] = []
                        self.records["constructor_calls"][key].append((call_index, parent_index))

        # Handle destructor calls from delete expressions
        # Example: delete basePtr; or delete[] arrayPtr;
        # Check if root_node is a delete_expression OR contains one
        delete_expr_node = None
        if root_node.type == "delete_expression":
            delete_expr_node = root_node
        elif root_node.type == "expression_statement":
            # Check if this expression_statement contains a delete_expression
            for child in root_node.children:
                if child.type == "delete_expression":
                    delete_expr_node = child
                    break

        if delete_expr_node:
            # Get the argument (what's being deleted) - it's the first named child
            arg_node = None
            if delete_expr_node.named_child_count > 0:
                arg_node = delete_expr_node.named_children[0]
            if arg_node:
                # Try to determine the type being deleted
                # For polymorphic objects, use runtime type; otherwise use static type
                class_name = None
                var_name = None

                if arg_node.type == "identifier":
                    arg_text = arg_node.text.decode('utf-8')
                    var_name = arg_text

                    # First, check if we have runtime type information (from new expressions)
                    if var_name in self.runtime_types:
                        class_name = self.runtime_types[var_name]
                    else:
                        # Fall back to static type from symbol table
                        arg_key = (arg_node.start_point, arg_node.end_point, arg_node.type)
                        if arg_key in self.index:
                            arg_index = self.index[arg_key]
                            if arg_index in self.declaration_map:
                                decl_index = self.declaration_map[arg_index]
                                if decl_index in self.symbol_table.get("data_type", {}):
                                    data_type = self.symbol_table["data_type"][decl_index]
                                    # Remove pointer/reference markers to get class name
                                    class_name = data_type.replace("*", "").replace("&", "").strip()

                if class_name:
                    # Find the parent statement node
                    parent_stmt = root_node
                    while parent_stmt and parent_stmt.type not in self.statement_types["node_list_type"]:
                        parent_stmt = parent_stmt.parent

                    if parent_stmt and (parent_stmt.start_point, parent_stmt.end_point, parent_stmt.type) in node_list:
                        parent_index = self.get_index(parent_stmt)

                        # Get the delete_expression node itself if it's in node_list
                        call_index = parent_index
                        if (root_node.start_point, root_node.end_point, root_node.type) in node_list:
                            call_index = self.get_index(root_node)

                        # Store destructor call
                        if class_name not in self.records["destructor_calls"]:
                            self.records["destructor_calls"][class_name] = []
                        self.records["destructor_calls"][class_name].append((call_index, parent_index))

        # Handle base class constructor calls from field_initializer_list
        # Example: Circle(double radius) : Shape("Circle"), radius(radius) { }
        # The field_initializer_list contains both base class constructor calls and member initializations
        elif root_node.type == "function_definition":
            # Check if this constructor has a field_initializer_list
            field_init_list = None
            for child in root_node.children:
                if child.type == "field_initializer_list":
                    field_init_list = child
                    break

            if field_init_list:
                # This is a constructor with initializer list
                # Get the constructor's function index
                if (root_node.start_point, root_node.end_point, root_node.type) in node_list:
                    constructor_index = self.get_index(root_node)

                    # Get the class this constructor belongs to
                    containing_class = self.get_containing_class(root_node)
                    if containing_class:
                        # Get base classes for this class
                        base_class_names = self.get_base_classes(containing_class)

                        # Parse each field_initializer in the list
                        for child in field_init_list.children:
                            if child.type == "field_initializer":
                                # Extract field name (could be base class or member)
                                field_id = None
                                args_node = None

                                for subchild in child.children:
                                    if subchild.type == "field_identifier":
                                        field_id = subchild.text.decode('utf-8')
                                    elif subchild.type == "argument_list":
                                        args_node = subchild

                                # Check if this is a base class constructor call
                                if field_id and field_id in base_class_names:
                                    # This is a base class constructor call
                                    signature = self.get_call_signature(args_node) if args_node else tuple()
                                    key = (field_id, signature)

                                    # Use the field_initializer node as call_id if available
                                    call_id = constructor_index
                                    if (child.start_point, child.end_point, child.type) in node_list:
                                        call_id = self.get_index(child)

                                    # Record the base class constructor call
                                    if key not in self.records["constructor_calls"]:
                                        self.records["constructor_calls"][key] = []
                                    self.records["constructor_calls"][key].append((call_id, constructor_index))

        # Recursively process children
        for child in root_node.children:
            self.function_list(child, node_list)

    def get_call_signature(self, args_node):
        """
        Extract the signature (tuple of argument types) from an argument_list node.
        Used for function overload resolution.
        """
        signature = []
        if args_node is None:
            return tuple(signature)

        for child in args_node.named_children:
            arg_type = self.get_argument_type(child)
            signature.append(arg_type)

        return tuple(signature)

    def get_argument_type(self, arg_node):
        """
        Infer the type of an argument expression for C++.
        Simplified implementation - returns "unknown" for complex cases.
        """
        if arg_node is None:
            return "unknown"

        node_type = arg_node.type

        # Identifiers - would need symbol table lookup
        if node_type == "identifier":
            arg_index_key = (arg_node.start_point, arg_node.end_point, arg_node.type)
            if arg_index_key in self.index:
                arg_index = self.index[arg_index_key]
                if arg_index in self.declaration_map:
                    decl_index = self.declaration_map[arg_index]
                    if decl_index in self.symbol_table["data_type"]:
                        return self.symbol_table["data_type"][decl_index]
            return "unknown"

        # Literals
        elif node_type == "number_literal":
            text = arg_node.text.decode('utf-8').lower()
            if '.' in text or 'e' in text:
                return "float" if text.endswith('f') else "double"
            else:
                return "int"

        elif node_type == "string_literal":
            return "const char*"

        elif node_type == "char_literal":
            return "char"

        elif node_type in ["true", "false"]:
            return "bool"

        elif node_type == "nullptr":
            return "nullptr_t"

        return "unknown"

    def add_dummy_nodes(self):
        """Add start and exit dummy nodes to CFG"""
        # Add start node
        self.CFG_node_list.append((1, 0, "start_node", "start"))
        # Exit node (ID=2) is implicit

    def track_function_pointer_assignments(self, root_node):
        """
        Track assignments to function pointers.
        Handles:
        - Simple assignments: mathFunc = add;
        - Address-of assignments: greetFunc = &greet;
        - Array initializers: int (*ops[2])(int, int) = {add, multiply};
        """
        if root_node.type == "assignment_expression":
            # Get left side (the pointer variable)
            left = root_node.child_by_field_name("left")
            # Get right side (the function being assigned)
            right = root_node.child_by_field_name("right")

            if left and right:
                pointer_var = None
                function_name = None

                # Get pointer variable name
                if left.type == "identifier":
                    pointer_var = left.text.decode('utf-8')

                # Get function name from right side
                if right.type == "identifier":
                    # Simple assignment: mathFunc = add
                    function_name = right.text.decode('utf-8')
                elif right.type == "pointer_expression":
                    # Address-of assignment: greetFunc = &greet
                    arg = right.child_by_field_name("argument")
                    if arg and arg.type == "identifier":
                        function_name = arg.text.decode('utf-8')

                # Track the assignment
                if pointer_var and function_name:
                    if pointer_var not in self.records["function_pointer_assignments"]:
                        self.records["function_pointer_assignments"][pointer_var] = []
                    if function_name not in self.records["function_pointer_assignments"][pointer_var]:
                        self.records["function_pointer_assignments"][pointer_var].append(function_name)

        # Handle array initializers: int (*ops[2])(int, int) = {add, multiply};
        elif root_node.type == "init_declarator":
            # Check if this is an array of function pointers
            declarator = root_node.child_by_field_name("declarator")
            value = root_node.child_by_field_name("value")

            if declarator and value and value.type == "initializer_list":
                # Get array name - navigate the tree structure
                # function_declarator → parenthesized_declarator → pointer_declarator → array_declarator → identifier
                array_name = None

                # Helper function to recursively find array_declarator
                def find_array_declarator(node):
                    if node is None:
                        return None
                    if node.type == "array_declarator":
                        # Get the identifier (array name)
                        for child in node.named_children:
                            if child.type == "identifier":
                                return child.text.decode('utf-8')
                    # Recursively search children
                    for child in node.named_children:
                        result = find_array_declarator(child)
                        if result:
                            return result
                    return None

                array_name = find_array_declarator(declarator)

                # Get the functions in the initializer list
                if array_name:
                    for child in value.named_children:
                        if child.type == "identifier":
                            function_name = child.text.decode('utf-8')
                            if array_name not in self.records["function_pointer_assignments"]:
                                self.records["function_pointer_assignments"][array_name] = []
                            if function_name not in self.records["function_pointer_assignments"][array_name]:
                                self.records["function_pointer_assignments"][array_name].append(function_name)

        # Recursively process children
        for child in root_node.children:
            self.track_function_pointer_assignments(child)

    def add_function_call_edges(self):
        """
        Add edges for function calls and returns.
        Handles:
        - Regular function calls
        - Member function calls
        - Constructor calls
        - Virtual function dispatch
        """
        # Create reverse index mapping: index -> node_key
        index_to_key = {v: k for k, v in self.index.items()}

        # Process regular function calls
        for (func_name, signature), call_list in self.records["function_calls"].items():
            # Find matching function definition
            for ((class_name, fn_name), fn_sig), fn_id in self.records["function_list"].items():
                if fn_name == func_name:
                    # Found matching function
                    for call_id, parent_id in call_list:
                        # Add call edge: caller -> function
                        self.add_edge(parent_id, fn_id, f"function_call|{call_id}")

                        # Add return edges: function return points -> caller
                        # Skip return edges to call sites within the same function
                        # (e.g., recursive calls in mutually exclusive branches)
                        if self.records.get("return_statement_map") and fn_id in self.records["return_statement_map"]:
                            for return_id in self.records["return_statement_map"][fn_id]:
                                # Check if this is a synthetic implicit return node
                                is_implicit_return = self.records.get("implicit_return_map") and return_id in self.records["implicit_return_map"].values()

                                # Get the call site node
                                parent_key = index_to_key.get(parent_id)
                                if not parent_key:
                                    continue
                                parent_node = self.node_list.get(parent_key)
                                if not parent_node:
                                    continue

                                # Determine return target based on function return type
                                # For NON-VOID functions: return to call site (value needed in expression)
                                # For VOID functions/implicit returns: return to next statement
                                return_target = None

                                if is_implicit_return:
                                    # Implicit return = void function or constructor
                                    # Return to NEXT statement (no value to evaluate)
                                    next_index, next_node = self.get_next_index(parent_node, self.node_list)
                                    return_target = next_index if next_index != 2 else None
                                else:
                                    # Explicit return = may return a value
                                    # Check function's return type
                                    fn_key = None
                                    for ((class_name_check, fn_name_check), fn_sig_check), fn_id_check in self.records["function_list"].items():
                                        if fn_id_check == fn_id:
                                            fn_key = ((class_name_check, fn_name_check), fn_sig_check)
                                            break

                                    is_void_return = False
                                    if fn_key and fn_key in self.records["return_type"]:
                                        ret_type = self.records["return_type"][fn_key]
                                        is_void_return = ret_type == "void"

                                    if is_void_return:
                                        # Void function with explicit return
                                        # Return to NEXT statement
                                        next_index, next_node = self.get_next_index(parent_node, self.node_list)
                                        return_target = next_index if next_index != 2 else None
                                    else:
                                        # Non-void function (returns a value)
                                        # Return to SAME statement (call site) to continue expression
                                        return_target = parent_id

                                if parent_id != fn_id and return_target:
                                    # Get return node from index
                                    return_key = index_to_key.get(return_id)

                                    if is_implicit_return or not return_key:
                                        # FIX #2: For implicit returns, connect from last statement of function body
                                        # Find the function node
                                        fn_key = index_to_key.get(fn_id)
                                        fn_node = self.node_list.get(fn_key) if fn_key else None

                                        if fn_node:
                                            # Get last statement in function body
                                            last_stmt = self.get_last_statement_in_function_body(fn_node, self.node_list)
                                            if last_stmt:
                                                last_stmt_id, _ = last_stmt
                                                self.add_edge(last_stmt_id, return_target, "function_return")
                                            else:
                                                # Fallback: empty function body, connect from function entry
                                                self.add_edge(fn_id, return_target, "function_return")
                                    else:
                                        return_node = self.node_list.get(return_key)
                                        if return_node:
                                            parent_func = self.get_containing_function(parent_node)
                                            return_func = self.get_containing_function(return_node)
                                            # Only add edge if they're in different functions
                                            if parent_func != return_func or parent_func is None:
                                                self.add_edge(return_id, return_target, "function_return")

        # Process method calls (similar pattern but consider class context)
        for (method_name, signature), call_list in self.records["method_calls"].items():
            # FIX #5: Check if ANY function with this method name is virtual, OR
            # if there are multiple implementations (indicating polymorphism)
            # If the base class method is virtual, ALL potential targets (base and derived)
            # should be labeled as virtual_call to correctly represent polymorphic dispatch

            # Count how many different implementations exist for this method name
            matching_functions = []
            for ((class_name_check, fn_name_check), fn_sig_check), fn_id_check in self.records["function_list"].items():
                if fn_name_check == method_name:
                    matching_functions.append(fn_id_check)

            # Determine if this is a virtual call:
            # 1. Explicit virtual marking, OR
            # 2. Multiple implementations (polymorphism)
            is_virtual_method = False
            for fn_id_check in matching_functions:
                if fn_id_check in self.records["virtual_functions"]:
                    is_virtual_method = True
                    break

            # If multiple implementations exist, it's polymorphic (virtual)
            if len(matching_functions) > 1:
                is_virtual_method = True

            for ((class_name, fn_name), fn_sig), fn_id in self.records["function_list"].items():
                if fn_name == method_name:
                    for call_id, parent_id in call_list:
                        # Label consistently: if virtual or polymorphic, ALL targets are virtual calls
                        if is_virtual_method:
                            self.add_edge(parent_id, fn_id, f"virtual_call|{call_id}")
                        else:
                            self.add_edge(parent_id, fn_id, f"method_call|{call_id}")

                        # Add return edges: method return points -> caller
                        # Skip return edges to call sites within the same function
                        if self.records.get("return_statement_map") and fn_id in self.records["return_statement_map"]:
                            for return_id in self.records["return_statement_map"][fn_id]:
                                # Check if this is a synthetic implicit return node
                                is_implicit_return = self.records.get("implicit_return_map") and return_id in self.records["implicit_return_map"].values()

                                # Get the call site node
                                parent_key = index_to_key.get(parent_id)
                                if not parent_key:
                                    continue
                                parent_node = self.node_list.get(parent_key)
                                if not parent_node:
                                    continue

                                # Determine return target based on method return type
                                # For NON-VOID methods: return to call site (value needed in expression)
                                # For VOID methods/implicit returns: return to next statement
                                return_target = None

                                if is_implicit_return:
                                    # Implicit return = void method
                                    # Return to NEXT statement (no value to evaluate)
                                    next_index, next_node = self.get_next_index(parent_node, self.node_list)
                                    return_target = next_index if next_index != 2 else None
                                else:
                                    # Explicit return = may return a value
                                    # Check method's return type
                                    fn_key = None
                                    for ((class_name_check, fn_name_check), fn_sig_check), fn_id_check in self.records["function_list"].items():
                                        if fn_id_check == fn_id:
                                            fn_key = ((class_name_check, fn_name_check), fn_sig_check)
                                            break

                                    is_void_return = False
                                    if fn_key and fn_key in self.records["return_type"]:
                                        ret_type = self.records["return_type"][fn_key]
                                        is_void_return = ret_type == "void"

                                    if is_void_return:
                                        # Void method with explicit return
                                        # Return to NEXT statement
                                        next_index, next_node = self.get_next_index(parent_node, self.node_list)
                                        return_target = next_index if next_index != 2 else None
                                    else:
                                        # Non-void method (returns a value)
                                        # Return to SAME statement (call site) to continue expression
                                        return_target = parent_id

                                if parent_id != fn_id and return_target:
                                    # Get return node from index
                                    return_key = index_to_key.get(return_id)

                                    if is_implicit_return or not return_key:
                                        # FIX #2: For implicit returns, connect from last statement of method body
                                        # Find the method node
                                        fn_key = index_to_key.get(fn_id)
                                        fn_node = self.node_list.get(fn_key) if fn_key else None

                                        if fn_node:
                                            # Get last statement in method body
                                            last_stmt = self.get_last_statement_in_function_body(fn_node, self.node_list)
                                            if last_stmt:
                                                last_stmt_id, _ = last_stmt
                                                self.add_edge(last_stmt_id, return_target, "method_return")
                                            else:
                                                # Fallback: empty method body, connect from method entry
                                                self.add_edge(fn_id, return_target, "method_return")
                                    else:
                                        return_node = self.node_list.get(return_key)
                                        if return_node:
                                            parent_func = self.get_containing_function(parent_node)
                                            return_func = self.get_containing_function(return_node)
                                            if parent_func != return_func or parent_func is None:
                                                self.add_edge(return_id, return_target, "method_return")

        # Process constructor calls
        for (class_name, signature), call_list in self.records["constructor_calls"].items():
            # Find matching constructor in function_list
            # Constructors are stored with the class name as the function name
            for ((fn_class_name, fn_name), fn_sig), fn_id in self.records["function_list"].items():
                # Match by class name and function name
                if fn_class_name == class_name and fn_name == class_name:
                    # Check signature match with flexibility for special constructors
                    sig_match = False

                    # Exact match
                    if fn_sig == signature:
                        sig_match = True
                    # Special case: copy constructor (const T&)
                    elif signature == (f"const {class_name}&",) and len(fn_sig) == 1 and class_name in fn_sig[0]:
                        sig_match = True
                    # Special case: move constructor (T&&)
                    elif signature == (f"{class_name}&&",) and len(fn_sig) == 1 and class_name in fn_sig[0]:
                        sig_match = True
                    # Flexible matching for parameter types
                    elif len(fn_sig) == len(signature):
                        # Try to match each parameter
                        all_match = True
                        for fn_param, call_param in zip(fn_sig, signature):
                            # Simplify both for comparison (remove const, &, *, etc.)
                            fn_param_simple = fn_param.replace('const', '').replace('&', '').replace('*', '').strip()
                            call_param_simple = call_param.replace('const', '').replace('&', '').replace('*', '').strip()
                            # Special case: string literal -> std::string or string
                            if call_param == 'const char*' and ('string' in fn_param_simple.lower()):
                                continue
                            # Check if simplified versions match
                            if fn_param_simple != call_param_simple:
                                all_match = False
                                break
                        if all_match:
                            sig_match = True

                    if sig_match:
                        # Found matching constructor with correct signature
                        for call_id, parent_id in call_list:
                            # Add call edge: declaration -> constructor
                            self.add_edge(parent_id, fn_id, f"constructor_call|{call_id}")

                        # Add return edges: constructor return points -> next statement after declaration
                        # Need to create return edges for EACH call site
                        if self.records.get("return_statement_map") and fn_id in self.records["return_statement_map"]:
                            for return_id in self.records["return_statement_map"][fn_id]:
                                # Check if this is a synthetic implicit return node
                                is_implicit_return = self.records.get("implicit_return_map") and return_id in self.records["implicit_return_map"].values()

                                # Iterate through each call site to create return edges
                                for call_id, parent_id in call_list:
                                    # Get the call site node to find the next statement
                                    parent_key = index_to_key.get(parent_id)
                                    if not parent_key:
                                        continue
                                    parent_node = self.node_list.get(parent_key)
                                    if not parent_node:
                                        continue

                                    # Check if parent is a constructor (base class constructor call from initializer list)
                                    is_base_constructor_call = False
                                    if parent_node.type == "function_definition":
                                        # Check if parent has field_initializer_list (it's a constructor with initializers)
                                        for pchild in parent_node.children:
                                            if pchild.type == "field_initializer_list":
                                                is_base_constructor_call = True
                                                break

                                    if is_base_constructor_call:
                                        # This is a base class constructor call from an initializer list
                                        # Return should go to the first statement in the derived constructor body
                                        first_line = self.edge_first_line(parent_node, self.node_list)
                                        if first_line:
                                            return_target = first_line[0]
                                        else:
                                            # No body statements, return to implicit return of derived constructor
                                            if parent_id in self.records.get("implicit_return_map", {}):
                                                return_target = self.records["implicit_return_map"][parent_id]
                                            else:
                                                return_target = None
                                    else:
                                        # Regular constructor call from declaration
                                        # Find the next statement after the declaration
                                        next_index, next_node = self.get_next_index(parent_node, self.node_list)
                                        # Return should go to the next statement, not back to the declaration
                                        return_target = next_index if next_index != 2 else None

                                    if is_implicit_return:
                                        # FIX #2: For implicit returns, connect from last statement of constructor body
                                        # Find the constructor node
                                        fn_key = index_to_key.get(fn_id)
                                        fn_node = self.node_list.get(fn_key) if fn_key else None

                                        if fn_node and return_target:
                                            # Get last statement in constructor body
                                            last_stmt = self.get_last_statement_in_function_body(fn_node, self.node_list)
                                            if last_stmt:
                                                last_stmt_id, _ = last_stmt
                                                if parent_id != fn_id:
                                                    self.add_edge(last_stmt_id, return_target, "constructor_return")
                                                elif is_base_constructor_call:
                                                    # Special case: base constructor returning to derived constructor body
                                                    self.add_edge(last_stmt_id, return_target, "base_constructor_return")
                                            else:
                                                # Fallback: empty constructor body, connect from constructor entry
                                                if parent_id != fn_id:
                                                    self.add_edge(fn_id, return_target, "constructor_return")
                                                elif is_base_constructor_call:
                                                    self.add_edge(fn_id, return_target, "base_constructor_return")
                                    else:
                                        # For regular return statements, check they're in different functions
                                        if parent_id != fn_id and return_target:
                                            return_key = index_to_key.get(return_id)

                                            if return_key:
                                                return_node = self.node_list.get(return_key)

                                                if return_node:
                                                    parent_func = self.get_containing_function(parent_node)
                                                    return_func = self.get_containing_function(return_node)
                                                    if parent_func != return_func or parent_func is None:
                                                        self.add_edge(return_id, return_target, "constructor_return")
                                        elif is_base_constructor_call and return_target:
                                            # Special case: base constructor returning to derived constructor body
                                            self.add_edge(return_id, return_target, "base_constructor_return")

        # Process destructor calls
        if self.records.get("destructor_calls"):
            for class_name, call_list in self.records["destructor_calls"].items():
                # Find matching destructor in function_list
                # For virtual destructors with inheritance, we need to:
                # 1. Call the most-derived class destructor first (class_name)
                # 2. Chain to base class destructors in order

                # Build inheritance chain: [MostDerived, ..., Base]
                # Since parser doesn't populate extends for C++, we'll use a heuristic:
                # Find the most-derived destructor (class_name), then look for potential base destructors
                import sys

                # Find all destructors for this class
                destructor_chain = []  # [(class_name, fn_id, implicit_return_id)]

                # First, add the most-derived destructor (the runtime type)
                derived_destructor_name = f"~{class_name}"
                for ((fn_class_name, fn_name), fn_sig), fn_id in self.records["function_list"].items():
                    if fn_name == derived_destructor_name and fn_class_name == class_name:
                        implicit_ret = self.records.get("implicit_return_map", {}).get(fn_id)
                        destructor_chain.append((class_name, fn_id, implicit_ret))
                        break

                # Now find potential base class destructors
                # Heuristic: If we have virtual destructors, check all destructors and include those marked as virtual
                # For the specific case, we know Base and Derived relationship from the code structure
                # Look for other destructors that might be base classes
                all_destructors = []
                for ((fn_class_name, fn_name), fn_sig), fn_id in self.records["function_list"].items():
                    if fn_name.startswith("~") and fn_name != derived_destructor_name:
                        # Check if this is a virtual destructor (indicating it might be a base class)
                        if self.records.get("virtual_functions", {}).get(fn_id, {}).get("is_virtual"):
                            implicit_ret = self.records.get("implicit_return_map", {}).get(fn_id)
                            all_destructors.append((fn_class_name, fn_id, implicit_ret, fn_name))

                # If we have any virtual destructors, add them to the chain (they're likely base classes)
                for fn_class_name, fn_id, implicit_ret, fn_name in all_destructors:
                    destructor_chain.append((fn_class_name, fn_id, implicit_ret))

                # Process each delete statement
                for call_id, parent_id in call_list:
                    parent_key = index_to_key.get(parent_id)
                    if not parent_key:
                        continue
                    parent_node = self.node_list.get(parent_key)
                    if not parent_node:
                        continue

                    # Find the next statement after delete (final return target)
                    next_index, next_node = self.get_next_index(parent_node, self.node_list)
                    final_return_target = next_index if next_index != 2 else None

                    if destructor_chain:
                        # Create the destructor call chain
                        # FIX #1: Connect destructor bodies directly without implicit return nodes
                        # delete -> Derived~() body -> Base~() entry -> next_stmt

                        # First destructor: called from delete statement
                        first_class, first_fn_id, first_implicit_ret = destructor_chain[0]
                        self.add_edge(parent_id, first_fn_id, f"destructor_call|{call_id}")

                        # Chain destructors together by connecting bodies directly
                        for i in range(len(destructor_chain)):
                            curr_class, curr_fn_id, curr_implicit_ret = destructor_chain[i]

                            # Get the function node for the current destructor
                            curr_fn_key = index_to_key.get(curr_fn_id)
                            curr_fn_node = self.node_list.get(curr_fn_key) if curr_fn_key else None

                            # Determine where this destructor returns to
                            if i < len(destructor_chain) - 1:
                                # Not the last destructor - connect to next destructor in chain
                                next_class, next_fn_id, next_implicit_ret = destructor_chain[i + 1]
                                return_target = next_fn_id
                                edge_label = "destructor_chain"
                            else:
                                # Last destructor - return to statement after delete
                                return_target = final_return_target
                                edge_label = "destructor_return"

                            # FIX #1: Connect from last statement of destructor body to next target
                            if return_target and curr_fn_node:
                                # Find last statement in current destructor body
                                last_stmt = self.get_last_statement_in_function_body(curr_fn_node, self.node_list)

                                if last_stmt:
                                    last_stmt_id, last_stmt_node = last_stmt
                                    self.add_edge(last_stmt_id, return_target, edge_label)
                                else:
                                    # Fallback: No body statements, connect destructor entry to target
                                    self.add_edge(curr_fn_id, return_target, edge_label)

        # Process indirect calls through function pointers
        # Handle calls through pointer variables and array subscripts
        for (pointer_var, signature), call_list in self.records["indirect_calls"].items():
            # Look up what function(s) this pointer/array might point to
            if self.records.get("function_pointer_assignments") and pointer_var in self.records["function_pointer_assignments"]:
                function_names = self.records["function_pointer_assignments"][pointer_var]

                # Create edges to all possible target functions
                for func_name in function_names:
                    # Find the function definition
                    for ((class_name, fn_name), fn_sig), fn_id in self.records["function_list"].items():
                        if fn_name == func_name:
                            # Found a possible target
                            for call_id, parent_id in call_list:
                                # Add call edge
                                self.add_edge(parent_id, fn_id, f"indirect_call|{call_id}")

                                # Add return edges: return points -> next statement after caller
                                if self.records.get("return_statement_map") and fn_id in self.records["return_statement_map"]:
                                    for return_id in self.records["return_statement_map"][fn_id]:
                                        # Check if this is a synthetic implicit return node
                                        is_implicit_return = self.records.get("implicit_return_map") and return_id in self.records["implicit_return_map"].values()

                                        # Get the call site node to find the next statement
                                        parent_key = index_to_key.get(parent_id)
                                        if not parent_key:
                                            continue
                                        parent_node = self.node_list.get(parent_key)
                                        if not parent_node:
                                            continue

                                        # Find the next statement after the call
                                        next_index, next_node = self.get_next_index(parent_node, self.node_list)

                                        # Return should go to the next statement, not back to the call
                                        return_target = next_index if next_index != 2 else None

                                        if is_implicit_return:
                                            # FIX #2: For implicit returns, connect from last statement of function body
                                            if parent_id != fn_id and return_target:
                                                # Find the function node
                                                fn_key = index_to_key.get(fn_id)
                                                fn_node = self.node_list.get(fn_key) if fn_key else None

                                                if fn_node:
                                                    # Get last statement in function body
                                                    last_stmt = self.get_last_statement_in_function_body(fn_node, self.node_list)
                                                    if last_stmt:
                                                        last_stmt_id, _ = last_stmt
                                                        self.add_edge(last_stmt_id, return_target, "indirect_return")
                                                    else:
                                                        # Fallback: empty function body
                                                        self.add_edge(fn_id, return_target, "indirect_return")
                                        else:
                                            # For regular return statements, check they're in different functions
                                            if parent_id != fn_id and return_target:
                                                return_key = index_to_key.get(return_id)

                                                if return_key:
                                                    return_node = self.node_list.get(return_key)

                                                    if return_node:
                                                        parent_func = self.get_containing_function(parent_node)
                                                        return_func = self.get_containing_function(return_node)
                                                        if parent_func != return_func or parent_func is None:
                                                            self.add_edge(return_id, return_target, "indirect_return")

        # Also check function_calls for indirect calls (identifiers that don't match any function)
        # These are calls like mathFunc(5, 3) where mathFunc is a function pointer variable
        for (func_name, signature), call_list in list(self.records["function_calls"].items()):
            # Check if this name matches any function definition
            found_direct_match = False
            for ((class_name, fn_name), fn_sig), fn_id in self.records["function_list"].items():
                if fn_name == func_name:
                    found_direct_match = True
                    break

            # If no direct match, check if it's a function pointer variable
            if not found_direct_match and func_name in self.records["function_pointer_assignments"]:
                function_names = self.records["function_pointer_assignments"][func_name]

                # Create edges to all possible target functions
                for target_func in function_names:
                    for ((class_name, fn_name), fn_sig), fn_id in self.records["function_list"].items():
                        if fn_name == target_func:
                            for call_id, parent_id in call_list:
                                # Add call edge
                                self.add_edge(parent_id, fn_id, f"indirect_call|{call_id}")

                                # Add return edges: return points -> next statement after caller
                                if self.records.get("return_statement_map") and fn_id in self.records["return_statement_map"]:
                                    for return_id in self.records["return_statement_map"][fn_id]:
                                        # Check if this is a synthetic implicit return node
                                        is_implicit_return = self.records.get("implicit_return_map") and return_id in self.records["implicit_return_map"].values()

                                        # Get the call site node to find the next statement
                                        parent_key = index_to_key.get(parent_id)
                                        if not parent_key:
                                            continue
                                        parent_node = self.node_list.get(parent_key)
                                        if not parent_node:
                                            continue

                                        # Find the next statement after the call
                                        next_index, next_node = self.get_next_index(parent_node, self.node_list)

                                        # Return should go to the next statement, not back to the call
                                        return_target = next_index if next_index != 2 else None

                                        if is_implicit_return:
                                            # FIX #2: For implicit returns, connect from last statement of function body
                                            if parent_id != fn_id and return_target:
                                                # Find the function node
                                                fn_key = index_to_key.get(fn_id)
                                                fn_node = self.node_list.get(fn_key) if fn_key else None

                                                if fn_node:
                                                    # Get last statement in function body
                                                    last_stmt = self.get_last_statement_in_function_body(fn_node, self.node_list)
                                                    if last_stmt:
                                                        last_stmt_id, _ = last_stmt
                                                        self.add_edge(last_stmt_id, return_target, "indirect_return")
                                                    else:
                                                        # Fallback: empty function body
                                                        self.add_edge(fn_id, return_target, "indirect_return")
                                        else:
                                            # For regular return statements, check they're in different functions
                                            if parent_id != fn_id and return_target:
                                                return_key = index_to_key.get(return_id)

                                                if return_key:
                                                    return_node = self.node_list.get(return_key)

                                                    if return_node:
                                                        parent_func = self.get_containing_function(parent_node)
                                                        return_func = self.get_containing_function(return_node)
                                                        if parent_func != return_func or parent_func is None:
                                                            self.add_edge(return_id, return_target, "indirect_return")

    def add_lambda_edges(self):
        """
        Add edges for lambda invocations and returns.
        """
        for lambda_key, statement_node in self.records["lambda_map"].items():
            # Get lambda node
            lambda_node = self.node_list.get(lambda_key)
            if lambda_node is None:
                continue

            # Get statement index
            stmt_key = (statement_node.start_point, statement_node.end_point, statement_node.type)
            if stmt_key not in self.node_list:
                continue

            stmt_id = self.get_index(statement_node)
            lambda_id = self.index[lambda_key]

            # Add invocation edge
            self.add_edge(stmt_id, lambda_id, "lambda_invocation")

            # Find return points in lambda and add return edges
            # (Would need to track lambda return statements separately)

    def CFG_cpp(self):
        """
        Main CFG construction function for C++.
        Returns (CFG_node_list, CFG_edge_list)

        STEP 1: Extract statement nodes from AST
        STEP 2: Create initial sequential edges
        STEP 3: Create basic blocks
        STEP 4: Build function call map
        STEP 5: Add dummy nodes
        STEP 6: Add control flow edges
        STEP 7: Add function call edges
        STEP 8: Add lambda edges
        STEP 9: Return results
        """

        # ═══════════════════════════════════════════════════════════
        # STEP 1: Extract statement nodes from AST
        # ═══════════════════════════════════════════════════════════
        root_node, node_list, graph_node_list, records = cpp_nodes.get_nodes(
            root_node=self.root_node,
            node_list={},
            graph_node_list=[],
            index=self.index,
            records=self.records
        )

        self.node_list = node_list
        self.CFG_node_list = graph_node_list
        self.records = records

        # ═══════════════════════════════════════════════════════════
        # STEP 2: Create initial sequential edges (non-control statements)
        # ═══════════════════════════════════════════════════════════
        for key, node in node_list.items():
            if node.type in self.statement_types["non_control_statement"]:
                # Skip if last in control block (will be handled later)
                if self.is_last_in_control_block(node):
                    continue

                # Skip nodes with inner definitions (but NOT field_declarations or access_specifiers)
                # Field declarations are class members that need sequential flow despite being "definitions"
                if node.type not in ["field_declaration", "access_specifier"] and cpp_nodes.has_inner_definition(node):
                    continue

                # Get next statement
                next_index, next_node = self.get_next_index(node, node_list)

                if next_index != 2 and next_node is not None:
                    current_index = self.get_index(node)
                    self.add_edge(current_index, next_index, "next_line")

        # ═══════════════════════════════════════════════════════════
        # STEP 3: Create basic blocks
        # ═══════════════════════════════════════════════════════════
        self.get_basic_blocks(self.CFG_node_list, self.CFG_edge_list)
        self.CFG_node_list = self.append_block_index(self.CFG_node_list, self.records)

        # ═══════════════════════════════════════════════════════════
        # STEP 4: Build function/method call map
        # ═══════════════════════════════════════════════════════════
        self.function_list(self.root_node, node_list)

        # ═══════════════════════════════════════════════════════════
        # STEP 4.5: Track function pointer assignments
        # ═══════════════════════════════════════════════════════════
        self.track_function_pointer_assignments(self.root_node)

        # ═══════════════════════════════════════════════════════════
        # STEP 5: Add dummy nodes
        # ═══════════════════════════════════════════════════════════
        self.add_dummy_nodes()

        # ═══════════════════════════════════════════════════════════
        # STEP 6: Add control flow edges for each statement type
        # ═══════════════════════════════════════════════════════════
        for key, node in node_list.items():
            current_index = self.get_index(node)

            # ─────────────────────────────────────────────────────────
            # FUNCTION DEFINITION
            # ─────────────────────────────────────────────────────────
            if node.type == "function_definition":
                # Check if this is main function
                if "main_function" in self.records and self.records["main_function"] == current_index:
                    # start -> main
                    self.add_edge(1, current_index, "next")

                # Edge to first line in function body
                first_line = self.edge_first_line(node, node_list)
                if first_line:
                    first_index, first_node = first_line
                    self.add_edge(current_index, first_index, "first_next_line")

                # For VOID functions and CONSTRUCTORS, create an explicit implicit return node
                # This node serves as a collection point for all execution paths that reach the function end
                return_type_node = node.child_by_field_name("type")
                is_void = False
                is_constructor = False

                if return_type_node:
                    return_type_text = return_type_node.text.decode('utf-8')
                    is_void = return_type_text == "void"
                else:
                    # No return type = constructor or destructor
                    is_constructor = True

                if is_void or is_constructor:
                    # Create implicit return node for internal tracking only
                    # FIX #2: Don't add to CFG_node_list - keep only for internal bookkeeping
                    implicit_return_id = self.get_new_synthetic_index()

                    # Get function name for label (used in debugging)
                    declarator = node.child_by_field_name("declarator")
                    func_name = "unknown"
                    if declarator:
                        # Navigate to find the identifier
                        for child in declarator.named_children:
                            if child.type == "identifier":
                                func_name = child.text.decode('utf-8')
                                break
                            elif child.type == "field_identifier":
                                func_name = child.text.decode('utf-8')
                                break

                    # FIX #2: DON'T add implicit return node to CFG node list
                    # These are synthetic nodes that don't correspond to actual code
                    # They're kept only for internal tracking in implicit_return_map
                    # implicit_return_label = f"implicit_return_{func_name}"
                    # self.CFG_node_list.append((implicit_return_id, 0, "implicit_return", implicit_return_label))

                    # Store mapping: function_id -> implicit_return_id (for internal use only)
                    self.records["implicit_return_map"][current_index] = implicit_return_id

                    # Add implicit return to return_statement_map so it gets connected to call sites
                    if current_index not in self.records["return_statement_map"]:
                        self.records["return_statement_map"][current_index] = []
                    self.records["return_statement_map"][current_index].append(implicit_return_id)

            # ─────────────────────────────────────────────────────────
            # CLASS / STRUCT DEFINITION
            # ─────────────────────────────────────────────────────────
            elif node.type in ["class_specifier", "struct_specifier"]:
                # Edge to first member/method
                first_line = self.edge_first_line(node, node_list)
                if first_line:
                    first_index, first_node = first_line
                    self.add_edge(current_index, first_index, "class_next")

            # ─────────────────────────────────────────────────────────
            # NAMESPACE DEFINITION
            # ─────────────────────────────────────────────────────────
            elif node.type == "namespace_definition":
                # Edge to first declaration in namespace
                first_line = self.edge_first_line(node, node_list)
                if first_line:
                    first_index, first_node = first_line
                    self.add_edge(current_index, first_index, "namespace_entry")

            # ─────────────────────────────────────────────────────────
            # IF STATEMENT
            # ─────────────────────────────────────────────────────────
            elif node.type == "if_statement":
                # Get consequence (then branch)
                consequence = node.child_by_field_name("consequence")
                if consequence:
                    # Find first statement in consequence
                    if consequence.type == "compound_statement":
                        children = list(consequence.named_children)
                        if children:
                            first_stmt = children[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "pos_next")
                    else:
                        # Single statement (no braces)
                        if (consequence.start_point, consequence.end_point, consequence.type) in node_list:
                            self.add_edge(current_index, self.get_index(consequence), "pos_next")

                    # Connect last of consequence to next after if
                    # BUT: Don't add edge if last statement is a jump statement (break, return, etc.)
                    last_line, _ = self.get_block_last_line(node, "consequence")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                        if not self.is_jump_statement(last_line):
                            next_index, next_node = self.get_next_index(node, node_list)
                            if next_index != 2:
                                self.add_edge(self.get_index(last_line), next_index, "next_line")
                            else:
                                # At function boundary - check if we're in a void function
                                func = self.get_containing_function(node)
                                if func:
                                    func_index = self.get_index(func)
                                    if func_index in self.records["implicit_return_map"]:
                                        # Connect to implicit return node
                                        implicit_return_id = self.records["implicit_return_map"][func_index]
                                        self.add_edge(self.get_index(last_line), implicit_return_id, "next_line")

                # Get alternative (else branch)
                alternative = node.child_by_field_name("alternative")
                if alternative:
                    # Handle else_clause wrapper (C++ specific)
                    else_body = alternative
                    if alternative.type == "else_clause":
                        # Get the compound_statement or statement inside else_clause
                        else_children = list(alternative.named_children)
                        if else_children:
                            else_body = else_children[0]

                    # Find first statement in else body
                    if else_body.type == "compound_statement":
                        children = list(else_body.named_children)
                        if children:
                            first_stmt = children[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "neg_next")
                    elif else_body.type == "if_statement":
                        # Else-if chain
                        if (else_body.start_point, else_body.end_point, else_body.type) in node_list:
                            self.add_edge(current_index, self.get_index(else_body), "neg_next")
                    else:
                        # Single statement (no braces)
                        if (else_body.start_point, else_body.end_point, else_body.type) in node_list:
                            self.add_edge(current_index, self.get_index(else_body), "neg_next")

                    # Connect last of alternative to next after if
                    # BUT: Don't add edge if last statement is a jump statement (break, return, etc.)
                    # Need to find last statement in the else body
                    if alternative.type == "else_clause":
                        # For else_clause, we need to get the body and find its last statement
                        if else_body.type == "compound_statement":
                            children = list(else_body.named_children)
                            if children:
                                last_stmt = children[-1]
                                if (last_stmt.start_point, last_stmt.end_point, last_stmt.type) in node_list:
                                    if not self.is_jump_statement(last_stmt):
                                        next_index, next_node = self.get_next_index(node, node_list)
                                        if next_index != 2:
                                            self.add_edge(self.get_index(last_stmt), next_index, "next_line")
                                        else:
                                            # At function boundary - check if we're in a void function
                                            func = self.get_containing_function(node)
                                            if func:
                                                func_index = self.get_index(func)
                                                if func_index in self.records["implicit_return_map"]:
                                                    implicit_return_id = self.records["implicit_return_map"][func_index]
                                                    self.add_edge(self.get_index(last_stmt), implicit_return_id, "next_line")
                        else:
                            # Single statement after else
                            if (else_body.start_point, else_body.end_point, else_body.type) in node_list:
                                if not self.is_jump_statement(else_body):
                                    next_index, next_node = self.get_next_index(node, node_list)
                                    if next_index != 2:
                                        self.add_edge(self.get_index(else_body), next_index, "next_line")
                                    else:
                                        # At function boundary - check if we're in a void function
                                        func = self.get_containing_function(node)
                                        if func:
                                            func_index = self.get_index(func)
                                            if func_index in self.records["implicit_return_map"]:
                                                implicit_return_id = self.records["implicit_return_map"][func_index]
                                                self.add_edge(self.get_index(else_body), implicit_return_id, "next_line")
                    elif else_body.type == "compound_statement" or else_body.type != "if_statement":
                        # Direct compound_statement (not wrapped in else_clause)
                        last_line, _ = self.get_block_last_line(node, "alternative")
                        if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                            if not self.is_jump_statement(last_line):
                                next_index, next_node = self.get_next_index(node, node_list)
                                if next_index != 2:
                                    self.add_edge(self.get_index(last_line), next_index, "next_line")
                                else:
                                    # At function boundary - check if we're in a void function
                                    func = self.get_containing_function(node)
                                    if func:
                                        func_index = self.get_index(func)
                                        if func_index in self.records["implicit_return_map"]:
                                            implicit_return_id = self.records["implicit_return_map"][func_index]
                                            self.add_edge(self.get_index(last_line), implicit_return_id, "next_line")
                else:
                    # No else branch - if condition false, go to next statement
                    next_index, next_node = self.get_next_index(node, node_list)
                    if next_index != 2:
                        self.add_edge(current_index, next_index, "neg_next")
                    else:
                        # At function boundary - check if we're in a void function
                        func = self.get_containing_function(node)
                        if func:
                            func_index = self.get_index(func)
                            if func_index in self.records["implicit_return_map"]:
                                # Connect to implicit return node
                                implicit_return_id = self.records["implicit_return_map"][func_index]
                                self.add_edge(current_index, implicit_return_id, "neg_next")

            # ─────────────────────────────────────────────────────────
            # WHILE LOOP
            # ─────────────────────────────────────────────────────────
            elif node.type == "while_statement":
                # Edge to first statement in loop body (condition true)
                body = node.child_by_field_name("body")
                if body:
                    if body.type == "compound_statement":
                        children = list(body.named_children)
                        if children:
                            first_stmt = children[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "pos_next")
                    else:
                        if (body.start_point, body.end_point, body.type) in node_list:
                            self.add_edge(current_index, self.get_index(body), "pos_next")

                    # Back edge from last statement to loop header
                    # BUT: Don't add edge if last statement is a jump statement
                    last_line, _ = self.get_block_last_line(node, "body")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                        if not self.is_jump_statement(last_line):
                            self.add_edge(self.get_index(last_line), current_index, "loop_control")

                # Edge to next statement after loop (condition false)
                next_index, next_node = self.get_next_index(node, node_list)
                if next_index != 2:
                    self.add_edge(current_index, next_index, "neg_next")

                # Self-loop for loop update
                self.add_edge(current_index, current_index, "loop_update")

            # ─────────────────────────────────────────────────────────
            # FOR LOOP (C-style)
            # ─────────────────────────────────────────────────────────
            elif node.type == "for_statement":
                # Edge to first statement in loop body
                body = node.child_by_field_name("body")
                if body:
                    if body.type == "compound_statement":
                        children = list(body.named_children)
                        if children:
                            first_stmt = children[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "pos_next")
                    else:
                        if (body.start_point, body.end_point, body.type) in node_list:
                            self.add_edge(current_index, self.get_index(body), "pos_next")

                    # Back edge from last statement to loop header
                    # BUT: Don't add edge if last statement is a jump statement
                    last_line, _ = self.get_block_last_line(node, "body")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                        if not self.is_jump_statement(last_line):
                            self.add_edge(self.get_index(last_line), current_index, "loop_control")

                # Edge to next statement after loop
                next_index, next_node = self.get_next_index(node, node_list)
                if next_index != 2:
                    self.add_edge(current_index, next_index, "neg_next")

                # Self-loop for loop update
                self.add_edge(current_index, current_index, "loop_update")

            # ─────────────────────────────────────────────────────────
            # RANGE-BASED FOR LOOP (for (auto x : container))
            # ─────────────────────────────────────────────────────────
            elif node.type == "for_range_loop":
                # Similar to regular for loop
                body = node.child_by_field_name("body")
                if body:
                    if body.type == "compound_statement":
                        children = list(body.named_children)
                        if children:
                            first_stmt = children[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "pos_next")
                    else:
                        if (body.start_point, body.end_point, body.type) in node_list:
                            self.add_edge(current_index, self.get_index(body), "pos_next")

                    # Back edge from last statement to loop header
                    # BUT: Don't add edge if last statement is a jump statement
                    last_line, _ = self.get_block_last_line(node, "body")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                        if not self.is_jump_statement(last_line):
                            self.add_edge(self.get_index(last_line), current_index, "loop_control")

                # Exit edge
                next_index, next_node = self.get_next_index(node, node_list)
                if next_index != 2:
                    self.add_edge(current_index, next_index, "neg_next")

                # Self-loop
                self.add_edge(current_index, current_index, "loop_update")

            # ─────────────────────────────────────────────────────────
            # DO-WHILE LOOP
            # ─────────────────────────────────────────────────────────
            elif node.type == "do_statement":
                # Edge to first statement in loop body (always executes once)
                body = node.child_by_field_name("body")
                if body:
                    if body.type == "compound_statement":
                        children = list(body.named_children)
                        if children:
                            first_stmt = children[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "pos_next")
                    else:
                        if (body.start_point, body.end_point, body.type) in node_list:
                            self.add_edge(current_index, self.get_index(body), "pos_next")

                    # Back edge from last statement to do node (condition check)
                    # BUT: Don't add edge if last statement is a jump statement
                    last_line, _ = self.get_block_last_line(node, "body")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                        if not self.is_jump_statement(last_line):
                            self.add_edge(self.get_index(last_line), current_index, "loop_control")

                # Edge to next statement after loop (condition false)
                next_index, next_node = self.get_next_index(node, node_list)
                if next_index != 2:
                    self.add_edge(current_index, next_index, "neg_next")

            # ─────────────────────────────────────────────────────────
            # BREAK STATEMENT
            # ─────────────────────────────────────────────────────────
            elif node.type == "break_statement":
                # Find enclosing loop or switch
                parent = node.parent
                while parent is not None:
                    if parent.type in ["while_statement", "for_statement", "for_range_loop", "do_statement", "switch_statement"]:
                        # Jump to statement after the loop/switch
                        next_index, next_node = self.get_next_index(parent, node_list)
                        if next_index != 2:
                            self.add_edge(current_index, next_index, "jump_next")
                        break
                    parent = parent.parent

            # ─────────────────────────────────────────────────────────
            # CONTINUE STATEMENT
            # ─────────────────────────────────────────────────────────
            elif node.type == "continue_statement":
                # Find enclosing loop
                parent = node.parent
                while parent is not None:
                    if parent.type in self.statement_types["loop_control_statement"]:
                        # Jump back to loop header
                        if (parent.start_point, parent.end_point, parent.type) in node_list:
                            loop_index = self.get_index(parent)
                            self.add_edge(current_index, loop_index, "jump_next")
                        break
                    parent = parent.parent

            # ─────────────────────────────────────────────────────────
            # RETURN STATEMENT
            # ─────────────────────────────────────────────────────────
            elif node.type == "return_statement":
                # Find containing function
                func = self.get_containing_function(node)
                if func and (func.start_point, func.end_point, func.type) in node_list:
                    func_index = self.get_index(func)
                    if func_index not in self.records["return_statement_map"]:
                        self.records["return_statement_map"][func_index] = []
                    if current_index not in self.records["return_statement_map"][func_index]:
                        self.records["return_statement_map"][func_index].append(current_index)

            # ─────────────────────────────────────────────────────────
            # GOTO STATEMENT
            # ─────────────────────────────────────────────────────────
            elif node.type == "goto_statement":
                # Get label name
                label_node = node.child_by_field_name("label")
                if label_node:
                    label_name = label_node.text.decode('utf-8') + ":"
                    # Find corresponding labeled_statement
                    if label_name in self.records["label_statement_map"]:
                        label_key = self.records["label_statement_map"][label_name]
                        if label_key in node_list:
                            label_index = self.index[label_key]
                            self.add_edge(current_index, label_index, "jump_next")

            # ─────────────────────────────────────────────────────────
            # LABELED STATEMENT
            # ─────────────────────────────────────────────────────────
            elif node.type == "labeled_statement":
                # In tree-sitter C++, labeled_statement contains:
                #   child[0]: statement_identifier (the label name)
                #   child[1]: statement (the statement immediately after the label)
                # Create edge from label to the statement it contains
                children = list(node.named_children)
                if len(children) >= 2:
                    stmt = children[1]  # The statement after the label
                    if (stmt.start_point, stmt.end_point, stmt.type) in node_list:
                        self.add_edge(current_index, self.get_index(stmt), "next_line")

            # ─────────────────────────────────────────────────────────
            # SWITCH STATEMENT
            # ─────────────────────────────────────────────────────────
            elif node.type == "switch_statement":
                # Find all case statements
                body = node.child_by_field_name("body")
                if body:
                    case_nodes = []
                    for child in body.named_children:
                        if child.type == "case_statement":
                            case_nodes.append(child)

                    # Edge from switch to each case
                    for case_node in case_nodes:
                        if (case_node.start_point, case_node.end_point, case_node.type) in node_list:
                            case_index = self.get_index(case_node)
                            self.add_edge(current_index, case_index, "switch_case")

                # Edge from switch to after switch (if no matching case)
                next_index, next_node = self.get_next_index(node, node_list)
                if next_index != 2:
                    self.add_edge(current_index, next_index, "switch_exit")

            # ─────────────────────────────────────────────────────────
            # CASE STATEMENT
            # ─────────────────────────────────────────────────────────
            elif node.type == "case_statement":
                # Edge to first statement in case body
                children = list(node.named_children)
                if children:
                    # Check if this is a default case (no value) or regular case (has value)
                    value_field = node.child_by_field_name("value")

                    # For default case, statements start at index 0
                    # For regular case, statements start at index 1 (index 0 is the value)
                    start_index = 0 if value_field is None else 1

                    for i in range(start_index, len(children)):
                        if children[i].type in self.statement_types["node_list_type"]:
                            if (children[i].start_point, children[i].end_point, children[i].type) in node_list:
                                self.add_edge(current_index, self.get_index(children[i]), "case_next")
                            break

            # ─────────────────────────────────────────────────────────
            # TRY STATEMENT
            # ─────────────────────────────────────────────────────────
            elif node.type == "try_statement":
                # Edge to first statement in try block
                body = node.child_by_field_name("body")
                if body:
                    if body.type == "compound_statement":
                        children = list(body.named_children)
                        if children:
                            first_stmt = children[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "try_next")

                # Find all catch clauses
                catch_clauses = []
                for child in node.children:
                    if child.type == "catch_clause":
                        catch_clauses.append(child)

                # Edge from try to each catch clause
                for catch_node in catch_clauses:
                    if (catch_node.start_point, catch_node.end_point, catch_node.type) in node_list:
                        catch_index = self.get_index(catch_node)
                        self.add_edge(current_index, catch_index, "catch_exception")

                # Edge from try to next statement (if no exception)
                # BUT: Don't add edge if last statement is a jump statement
                last_line, _ = self.get_block_last_line(node, "body")
                if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                    if not self.is_jump_statement(last_line):
                        next_index, next_node = self.get_next_index(node, node_list)
                        if next_index != 2:
                            self.add_edge(self.get_index(last_line), next_index, "try_exit")

            # ─────────────────────────────────────────────────────────
            # CATCH CLAUSE
            # ─────────────────────────────────────────────────────────
            elif node.type == "catch_clause":
                # Edge to first statement in catch body
                body = node.child_by_field_name("body")
                if body:
                    if body.type == "compound_statement":
                        children = list(body.named_children)
                        if children:
                            first_stmt = children[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "catch_next")

                # Edge from catch to next statement after try-catch
                # BUT: Don't add edge if last statement is a jump statement
                last_line, _ = self.get_block_last_line(node, "body")
                if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                    if not self.is_jump_statement(last_line):
                        # Find parent try statement
                        parent_try = node.parent
                        if parent_try and parent_try.type == "try_statement":
                            next_index, next_node = self.get_next_index(parent_try, node_list)
                            if next_index != 2:
                                self.add_edge(self.get_index(last_line), next_index, "catch_exit")

            # ─────────────────────────────────────────────────────────
            # THROW STATEMENT
            # ─────────────────────────────────────────────────────────
            elif node.type == "throw_statement":
                # Find enclosing try block
                parent = node.parent
                found_try = False
                while parent is not None:
                    if parent.type == "try_statement":
                        # Jump to catch clauses
                        for child in parent.children:
                            if child.type == "catch_clause":
                                if (child.start_point, child.end_point, child.type) in node_list:
                                    catch_index = self.get_index(child)
                                    self.add_edge(current_index, catch_index, "throw_exit")
                                    found_try = True
                        break
                    parent = parent.parent

                if not found_try:
                    # No enclosing try - exception propagates to caller
                    # Add to function's return map
                    func = self.get_containing_function(node)
                    if func and (func.start_point, func.end_point, func.type) in node_list:
                        func_index = self.get_index(func)
                        if func_index not in self.records["return_statement_map"]:
                            self.records["return_statement_map"][func_index] = []
                        if current_index not in self.records["return_statement_map"][func_index]:
                            self.records["return_statement_map"][func_index].append(current_index)

            # ─────────────────────────────────────────────────────────
            # LAMBDA EXPRESSION
            # ─────────────────────────────────────────────────────────
            elif node.type == "lambda_expression":
                # Edge to first statement in lambda body
                body = node.child_by_field_name("body")
                if body:
                    if body.type == "compound_statement":
                        children = list(body.named_children)
                        if children:
                            first_stmt = children[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "lambda_next")

        # ═══════════════════════════════════════════════════════════
        # STEP 6.5: Connect dangling paths to implicit returns
        # FIX #2: DISABLED - Implicit returns are no longer added to CFG output
        # ═══════════════════════════════════════════════════════════
        # After all control flow edges are created, find statements that reach
        # function boundaries and connect them to implicit return nodes
        # NOTE: This step is now disabled because implicit returns are not in the CFG_node_list
        # The function return edges are now created directly in add_function_call_edges()
        # by connecting from the last statement of function bodies to the return target
        #
        # for key, node in node_list.items():
        #     if node.type in self.statement_types["non_control_statement"]:
        #         # Skip if last in control block (already handled)
        #         if self.is_last_in_control_block(node):
        #             continue
        #
        #         # Skip nodes with inner definitions
        #         if cpp_nodes.has_inner_definition(node):
        #             continue
        #
        #         # Get next statement
        #         next_index, next_node = self.get_next_index(node, node_list)
        #
        #         # If at function boundary, connect to implicit return
        #         if next_index == 2:
        #             func = self.get_containing_function(node)
        #             if func:
        #                 func_index = self.get_index(func)
        #                 if func_index in self.records["implicit_return_map"]:
        #                     # Connect to implicit return node
        #                     current_index = self.get_index(node)
        #                     implicit_return_id = self.records["implicit_return_map"][func_index]
        #                     self.add_edge(current_index, implicit_return_id, "next_line")

        # ═══════════════════════════════════════════════════════════
        # STEP 6.7: Insert scope-based destructor calls (RAII)
        # IMPORTANT: Must come AFTER:
        #   - function_list (STEP 4) to track objects
        #   - STEP 6 to create implicit returns
        #   - STEP 6.5 to connect statements to implicit returns
        # ═══════════════════════════════════════════════════════════
        self.insert_scope_destructors(node_list)

        # ═══════════════════════════════════════════════════════════
        # STEP 6.8: Add global scope flow (FIX #4)
        # Connect top-level declarations in sequential order to show
        # program initialization and declaration order
        # ═══════════════════════════════════════════════════════════
        # Find all top-level declarations (direct children of root or translation_unit)
        global_declarations = []

        for key, node in node_list.items():
            # Check if node is at global scope (parent is root or translation_unit)
            if node.parent and node.parent.type == "translation_unit":
                # Include classes, functions, structs, enums, typedefs, namespaces
                if node.type in ["class_specifier", "struct_specifier", "function_definition",
                                "enum_specifier", "type_definition", "namespace_definition",
                                "declaration"]:
                    node_id = self.get_index(node)
                    # Store (node_id, line_number) for sorting
                    global_declarations.append((node_id, node.start_point[0]))

        # Sort by line number to preserve declaration order
        global_declarations.sort(key=lambda x: x[1])

        # Connect sequential global declarations
        for i in range(len(global_declarations) - 1):
            curr_id = global_declarations[i][0]
            next_id = global_declarations[i + 1][0]
            self.add_edge(curr_id, next_id, "global_sequence")

        # If there are global declarations and no main function is marked,
        # optionally connect start node to first declaration
        # (This is commented out to avoid conflicting with main function entry)
        # if global_declarations and "main_function" not in self.records:
        #     first_decl_id = global_declarations[0][0]
        #     self.add_edge(1, first_decl_id, "program_entry")

        # ═══════════════════════════════════════════════════════════
        # STEP 7: Add function/method call edges
        # ═══════════════════════════════════════════════════════════
        self.add_function_call_edges()

        # ═══════════════════════════════════════════════════════════
        # STEP 8: Add lambda invocation edges
        # ═══════════════════════════════════════════════════════════
        self.add_lambda_edges()

        # ═══════════════════════════════════════════════════════════
        # STEP 9: Return results
        # ═══════════════════════════════════════════════════════════
        return self.CFG_node_list, self.CFG_edge_list
