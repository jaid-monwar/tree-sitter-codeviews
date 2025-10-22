import traceback

import networkx as nx
from loguru import logger

from ...utils import c_nodes
from .CFG import CFGGraph


class CFGGraph_c(CFGGraph):
    def __init__(self, src_language, src_code, properties, root_node, parser):
        super().__init__(src_language, src_code, properties, root_node, parser)

        self.node_list = None
        # Import statement types from c_nodes
        self.statement_types = c_nodes.statement_types
        self.CFG_node_list = []
        self.CFG_edge_list = []
        self.records = {
            "basic_blocks": {},
            "function_list": {},
            "return_type": {},
            "function_calls": {},
            "switch_child_map": {},
            "label_statement_map": {},
            "return_statement_map": {},
            "function_pointer_map": {},  # Maps function pointer variables to their target functions
        }
        self.index_counter = max(self.index.values())
        self.CFG_node_indices = []

        # Access parser data (created by parser_driver)
        self.symbol_table = self.parser.symbol_table
        self.declaration = self.parser.declaration
        self.declaration_map = self.parser.declaration_map
        self.CFG_node_list, self.CFG_edge_list = self.CFG_c()
        self.graph = self.to_networkx(self.CFG_node_list, self.CFG_edge_list)

    def get_index(self, node):
        """Get the unique index for a given AST node"""
        return self.index[(node.start_point, node.end_point, node.type)]

    def get_basic_blocks(self, CFG_node_list, CFG_edge_list):
        """Partition CFG into basic blocks using weakly connected components"""
        G = self.to_networkx(CFG_node_list, CFG_edge_list)
        components = nx.weakly_connected_components(G)
        block_index = 1
        for block in components:
            block_list = sorted(list(block))
            self.records["basic_blocks"][block_index] = block_list
            block_index += 1

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

    def get_next_index(self, current_node, node_list):
        """
        Find the next executable statement after current_node.
        Handles:
        - Sequential statements (next_named_sibling)
        - End of blocks (traverse up to parent)
        - Loop back edges
        - Function boundaries
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
                return (2, None)

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

        Handles two cases:
        1. Last statement in a compound_statement that belongs to a control structure
        2. Single statement (no braces) that is the consequence/body of a control structure
        """
        if node.parent is None:
            return False

        parent = node.parent

        # Case 1: Parent is a compound_statement (block with braces)
        if parent.type == "compound_statement":
            # Check if this node is the last named child
            children = list(parent.named_children)
            if children and children[-1] == node:
                # Now check if the compound_statement's parent is a control structure
                grandparent = parent.parent
                if grandparent and grandparent.type in ["if_statement", "while_statement", "for_statement", "do_statement", "else_clause"]:
                    return True

        # Case 2: Parent is a control structure directly (single statement, no braces)
        # This happens with syntax like: if (cond) statement;
        if parent.type in ["if_statement", "while_statement", "for_statement", "do_statement"]:
            # Check if this node is the consequence/body of the control structure
            consequence = parent.child_by_field_name("consequence")
            body = parent.child_by_field_name("body")

            # For if_statement, check if this is the consequence
            if consequence and consequence == node:
                return True

            # For loops (while/for/do), check if this is the body
            if body and body == node:
                return True

        # Case 3: Parent is an else_clause (single statement after else)
        if parent.type == "else_clause":
            # Check if this node is a direct child of else_clause (single statement)
            # In else_clause, the statement is a named child
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

    def add_edge(self, src, dest, edge_type, additional_data=None):
        """Add an edge to the CFG edge list with validation"""
        if src is None or dest is None:
            logger.error(f"Attempting to add edge with None: {src} -> {dest}")
            return

        if additional_data:
            self.CFG_edge_list.append((src, dest, edge_type, additional_data))
        else:
            self.CFG_edge_list.append((src, dest, edge_type))

    def track_function_pointers(self, root_node):
        """
        Track function pointer assignments in the program.
        Records mappings like: fptr -> add when we see fptr = &add
        """
        if root_node.type == "assignment_expression":
            left = root_node.child_by_field_name("left")
            right = root_node.child_by_field_name("right")

            if left and right:
                # Check if right side is &function_name
                if right.type == "pointer_expression":
                    arg = right.child_by_field_name("argument")
                    if arg and arg.type == "identifier":
                        # This is something like: fptr = &add
                        ptr_var = left.text.decode('utf-8')
                        target_func = arg.text.decode('utf-8')
                        self.records["function_pointer_map"][ptr_var] = target_func

        # Recursively process children
        for child in root_node.children:
            self.track_function_pointers(child)

    def function_list(self, root_node, node_list):
        """
        Build a map of all function calls in the program.
        Maps function signatures to their call sites.

        Handles both direct calls (add(10, 5)) and function pointer calls (fptr(10, 5)).
        """
        if root_node.type == "call_expression":
            # Get function name
            function_node = root_node.child_by_field_name("function")
            if function_node:
                if function_node.type == "identifier":
                    func_name = function_node.text.decode('utf-8')

                    # Check if this is a function pointer call
                    # If func_name is in function_pointer_map, resolve to actual function
                    if func_name in self.records["function_pointer_map"]:
                        actual_func_name = self.records["function_pointer_map"][func_name]
                        func_name = actual_func_name

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

                        key = (func_name, signature)
                        if key not in self.records["function_calls"]:
                            self.records["function_calls"][key] = []
                        self.records["function_calls"][key].append((call_index, parent_index))

        # Recursively process children
        for child in root_node.children:
            self.function_list(child, node_list)

    def get_argument_type(self, arg_node):
        """
        Infer the type of an argument expression.
        Returns the type as a string, or "unknown" if type cannot be determined.

        Handles:
        - Identifiers (variables): Look up in symbol_table
        - Literals: Map to C types
        - Cast expressions: Use the cast type
        - Arithmetic/binary expressions: Infer from operands
        - Function calls: Look up return type
        - Pointer/address operations: Modify base type
        - Array subscript: Get element type
        - Field access: Look up field type
        """

        if arg_node is None:
            return "unknown"

        node_type = arg_node.type

        # ============================================================
        # IDENTIFIERS - Look up in symbol table
        # ============================================================
        if node_type == "identifier":
            var_name = arg_node.text.decode('utf-8')

            # Method 1: Try declaration_map (if populated)
            arg_index_key = (arg_node.start_point, arg_node.end_point, arg_node.type)
            if arg_index_key in self.index:
                arg_index = self.index[arg_index_key]

                # Check if it's mapped to a declaration
                if arg_index in self.declaration_map:
                    decl_index = self.declaration_map[arg_index]
                    # Get type from symbol table
                    if decl_index in self.symbol_table["data_type"]:
                        return self.symbol_table["data_type"][decl_index]

            # Method 2: Look up by name in declaration dict (fallback for C)
            # Find the declaration index for this variable name
            for decl_idx, decl_name in self.declaration.items():
                if decl_name == var_name:
                    # Check if this declaration has a type
                    if decl_idx in self.symbol_table["data_type"]:
                        var_type = self.symbol_table["data_type"][decl_idx]
                        # Expand typedef if applicable
                        if hasattr(self.parser, 'expand_typedef'):
                            return self.parser.expand_typedef(var_type)
                        return var_type

            return "unknown"

        # ============================================================
        # LITERALS - Map to C types
        # ============================================================
        elif node_type == "number_literal":
            # Check if it's a float or int
            text = arg_node.text.decode('utf-8').lower()
            if '.' in text or 'e' in text:
                if text.endswith('f'):
                    return "float"
                return "double"
            else:
                # Integer literal - check suffixes
                if text.endswith('ll') or text.endswith('LL'):
                    return "long long"
                elif text.endswith('l') or text.endswith('L'):
                    return "long"
                elif text.endswith('u') or text.endswith('U'):
                    return "unsigned int"
                else:
                    return "int"

        elif node_type == "string_literal":
            return "char*"

        elif node_type == "char_literal":
            return "char"

        elif node_type == "true" or node_type == "false":
            return "int"  # C uses int for bool

        elif node_type == "null":
            return "void*"

        # ============================================================
        # CAST EXPRESSION - Use the explicit cast type
        # ============================================================
        elif node_type == "cast_expression":
            # cast_expression has type_descriptor and value
            type_desc = arg_node.child_by_field_name("type")
            if type_desc:
                # Get the type from type_descriptor
                for child in type_desc.children:
                    if child.type in ["primitive_type", "type_identifier", "sized_type_specifier"]:
                        return child.text.decode('utf-8')
            return "unknown"

        # ============================================================
        # POINTER/ADDRESS OPERATIONS
        # ============================================================
        elif node_type == "pointer_expression":
            # Dereference: *ptr -> if ptr is int*, result is int
            # Get the operand
            operand = arg_node.child_by_field_name("argument")
            if operand:
                operand_type = self.get_argument_type(operand)
                # Remove one level of pointer
                if operand_type.endswith('*'):
                    return operand_type[:-1].strip()
            return "unknown"

        elif node_type == "unary_expression":
            # Check for address-of operator: &var -> var*
            operator = arg_node.child_by_field_name("operator")
            if operator and operator.text.decode('utf-8') == '&':
                operand = arg_node.child_by_field_name("argument")
                if operand:
                    operand_type = self.get_argument_type(operand)
                    if operand_type != "unknown":
                        return operand_type + "*"
            return "unknown"

        # ============================================================
        # BINARY EXPRESSIONS - Infer from operands
        # ============================================================
        elif node_type == "binary_expression":
            # Get operator to determine result type
            left = arg_node.child_by_field_name("left")
            right = arg_node.child_by_field_name("right")

            if left and right:
                left_type = self.get_argument_type(left)
                right_type = self.get_argument_type(right)

                # Type promotion rules (simplified)
                # If either is double, result is double
                if "double" in left_type or "double" in right_type:
                    return "double"
                elif "float" in left_type or "float" in right_type:
                    return "float"
                elif "long" in left_type or "long" in right_type:
                    return "long"
                elif left_type != "unknown":
                    return left_type
                elif right_type != "unknown":
                    return right_type

            return "int"  # Default for arithmetic

        # ============================================================
        # ARRAY SUBSCRIPT - Get element type
        # ============================================================
        elif node_type == "subscript_expression":
            # arr[i] -> if arr is int[], result is int
            array = arg_node.child_by_field_name("argument")
            if array:
                array_type = self.get_argument_type(array)
                # Remove array notation
                if array_type.endswith('[]'):
                    return array_type[:-2]
                elif array_type.endswith('*'):
                    return array_type[:-1].strip()
            return "unknown"

        # ============================================================
        # FIELD ACCESS - Look up field type
        # ============================================================
        elif node_type == "field_expression":
            # struct.field or ptr->field
            field = arg_node.child_by_field_name("field")
            argument = arg_node.child_by_field_name("argument")

            if field and field.type in ["field_identifier", "identifier"]:
                field_name = field.text.decode('utf-8')

                # Try to get the type of the struct/pointer being accessed
                if argument:
                    struct_type = self.get_argument_type(argument)

                    # Remove pointer indicators if this is ptr->field (for pointer access)
                    # struct_type might be "struct Point*" or "struct Point"
                    base_type = struct_type.rstrip('*').strip()

                    # Look up field type in struct definitions
                    if hasattr(self.parser, 'struct_definitions'):
                        field_type = self.parser.get_struct_field_type(base_type, field_name)
                        if field_type != "unknown":
                            return field_type

            return "unknown"

        # ============================================================
        # FUNCTION CALL - Look up return type
        # ============================================================
        elif node_type == "call_expression":
            function = arg_node.child_by_field_name("function")
            if function and function.type == "identifier":
                func_name = function.text.decode('utf-8')

                # Look up in records["return_type"]
                # Need to find the matching signature (simplified: use any match)
                for (name, sig), return_type in self.records["return_type"].items():
                    if name == func_name:
                        return return_type if return_type else "unknown"

            return "unknown"

        # ============================================================
        # PARENTHESIZED EXPRESSION - Unwrap
        # ============================================================
        elif node_type == "parenthesized_expression":
            # (expr) -> type of expr
            for child in arg_node.named_children:
                return self.get_argument_type(child)
            return "unknown"

        # ============================================================
        # SIZEOF EXPRESSION - Always size_t
        # ============================================================
        elif node_type == "sizeof_expression":
            return "size_t"

        # ============================================================
        # CONDITIONAL EXPRESSION - Use true branch type
        # ============================================================
        elif node_type == "conditional_expression":
            # condition ? true_expr : false_expr
            consequence = arg_node.child_by_field_name("consequence")
            if consequence:
                return self.get_argument_type(consequence)
            return "unknown"

        # ============================================================
        # COMMA EXPRESSION - Use last expression
        # ============================================================
        elif node_type == "comma_expression":
            # expr1, expr2 -> type of expr2
            children = list(arg_node.named_children)
            if children:
                return self.get_argument_type(children[-1])
            return "unknown"

        # ============================================================
        # UPDATE EXPRESSIONS - Same as operand type
        # ============================================================
        elif node_type == "update_expression":
            # ++x or x++ -> type of x
            argument = arg_node.child_by_field_name("argument")
            if argument:
                return self.get_argument_type(argument)
            return "unknown"

        # ============================================================
        # DEFAULT - Unknown
        # ============================================================
        else:
            return "unknown"

    def get_call_signature(self, args_node):
        """
        Extract the signature (parameter types) from a function call.
        Uses type inference to determine actual argument types.

        Returns: tuple of type strings, e.g., ("int", "char*", "double")
        """
        signature = []

        if args_node is None:
            return tuple(signature)

        # args_node is an argument_list
        # Iterate through all named children (skip parentheses and commas)
        for arg in args_node.named_children:
            arg_type = self.get_argument_type(arg)
            signature.append(arg_type)

        return tuple(signature)

    def add_function_call_edges(self, node_list):
        """
        Add edges for function calls and returns.
        Connects call sites to function definitions and returns back to callers.

        Supports:
        - Exact signature matching
        - Variadic functions
        - Fuzzy matching by name when signature can't be inferred
        """
        for (func_name, call_signature), call_sites in self.records["function_calls"].items():
            # Try exact signature match first
            func_key = (func_name, call_signature)
            func_index = None

            if func_key in self.records["function_list"]:
                # Exact match found
                func_index = self.records["function_list"][func_key]
            else:
                # No exact match - try fallback strategies

                # Strategy 1: Check for variadic function match
                for (def_name, def_signature), idx in self.records["function_list"].items():
                    if def_name == func_name and len(def_signature) > 0 and def_signature[-1] == '...':
                        # Variadic function - check if call signature matches required parameters
                        required_params = def_signature[:-1]  # Remove '...'
                        if len(call_signature) >= len(required_params):
                            func_index = idx
                            break

                # Strategy 2: Fuzzy match by name only (for cases with 'unknown' types)
                # This handles cases where type inference fails (e.g., fibonacci(i) where i's type is unknown)
                if func_index is None and 'unknown' in call_signature:
                    # Look for function with same name and same number of parameters
                    for (def_name, def_signature), idx in self.records["function_list"].items():
                        if def_name == func_name and len(def_signature) == len(call_signature):
                            func_index = idx
                            break

            if func_index is not None:
                for call_id, parent_id in call_sites:
                    # Edge from caller to function
                    self.add_edge(parent_id, func_index, f"function_call|{call_id}")

                    # Add return edges from all return points in the function
                    # IMPORTANT: Only add return edge if parent_id is NOT itself a return statement
                    # This prevents incorrect edges like "return -> return"
                    parent_node = None
                    for key, node in node_list.items():
                        if self.get_index(node) == parent_id:
                            parent_node = node
                            break

                    # Check if parent is a return statement
                    is_parent_return = parent_node and parent_node.type == "return_statement"

                    if func_index in self.records["return_statement_map"]:
                        for return_id in self.records["return_statement_map"][func_index]:
                            # Only add return edge if parent is not a return statement
                            # For recursive calls in return statements, the return edge
                            # will be handled when the recursive call returns
                            if not is_parent_return:
                                self.add_edge(return_id, parent_id, "function_return")

    def find_enclosing_loop(self, node):
        """Find the nearest enclosing loop for break/continue statements"""
        while node:
            if node.type in self.statement_types["loop_control_statement"]:
                return node
            node = node.parent
        return None

    def CFG_c(self):
        """
        Main CFG construction function for C language.
        Returns (CFG_node_list, CFG_edge_list).

        This implements the multi-pass algorithm:
        1. Extract statement nodes from AST
        2. Create initial sequential edges
        3. Create basic blocks
        4. Build function call map
        5. Add dummy nodes (start/exit)
        6. Add control flow edges
        7. Add function call edges
        """

        # ============================================================
        # STEP 1: Extract Statement Nodes from AST
        # ============================================================
        node_list, self.CFG_node_list, self.records = c_nodes.get_nodes(
            self.root_node,
            node_list={},
            graph_node_list=[],
            index=self.index,
            records=self.records
        )

        # Filter out nodes that shouldn't be in CFG
        # 1. Preprocessor directives (compile-time only, not runtime control flow)
        # 2. Compound statements (redundant - individual statements already represented)
        # 3. Function declarations (forward declarations/prototypes - compile-time only)
        cfg_excluded_types = [
            "preproc_include", "preproc_def", "preproc_function_def", "preproc_call",
            "preproc_if", "preproc_ifdef", "preproc_elif", "preproc_else",
            "compound_statement"
        ]

        # Filter node_list dictionary
        node_list = {key: node for key, node in node_list.items()
                     if node.type not in cfg_excluded_types and not c_nodes.is_function_declaration(node)}

        # Filter CFG_node_list
        filtered_cfg_nodes = []
        excluded_indices = set()
        for node_tuple in self.CFG_node_list:
            node_id = node_tuple[0]
            # Find the node type from index
            node_found = False
            for key, node in node_list.items():
                if self.get_index(node) == node_id:
                    filtered_cfg_nodes.append(node_tuple)
                    node_found = True
                    break
            if not node_found:
                # This node was filtered out
                excluded_indices.add(node_id)

        self.CFG_node_list = filtered_cfg_nodes

        # ============================================================
        # STEP 2: Create Initial Sequential Edges
        # ============================================================
        for key, node in node_list.items():
            current_index = self.get_index(node)

            # Handle non-control statements (simple sequential flow)
            if node.type in self.statement_types["non_control_statement"]:
                # Skip if node has switch in subtree
                if current_index in self.records["switch_child_map"]:
                    continue

                # Skip empty blocks
                if node.type == "compound_statement" and len(list(node.named_children)) == 0:
                    continue

                # Skip if this is the last statement in a control flow block
                # Those edges will be handled in the control flow step
                if self.is_last_in_control_block(node):
                    continue

                # Find next statement
                next_index, next_node = self.get_next_index(node, node_list)

                if next_node is not None:
                    self.add_edge(current_index, next_index, "next_line")

        # ============================================================
        # STEP 3: Create Basic Blocks
        # ============================================================
        self.get_basic_blocks(self.CFG_node_list, self.CFG_edge_list)

        # ============================================================
        # STEP 4: Append Block Indices to Nodes
        # ============================================================
        # Add block index to each node tuple
        updated_node_list = []
        for node_tuple in self.CFG_node_list:
            node_id = node_tuple[0]
            block_idx = self.get_key(node_id, self.records["basic_blocks"])
            if block_idx:
                updated_node_list.append(node_tuple + (block_idx,))
            else:
                updated_node_list.append(node_tuple + (0,))  # No block
        self.CFG_node_list = updated_node_list

        # ============================================================
        # STEP 5: Detect Main Function
        # ============================================================
        # Check if a main function exists and record it
        for key, node in node_list.items():
            if node.type == "function_definition":
                func_name = c_nodes.get_function_name(node)
                if func_name == "main":
                    self.records["main_function"] = self.get_index(node)
                    break

        # ============================================================
        # STEP 6: Build Function Call Map
        # ============================================================
        # First, track function pointer assignments (e.g., fptr = &add)
        self.track_function_pointers(self.root_node)

        # Then, build function call map (including function pointer calls)
        self.function_list(self.root_node, node_list)

        # Track return statements
        for key, node in node_list.items():
            if node.type == "return_statement":
                func_node = self.get_containing_function(node)
                if func_node:
                    func_index = self.get_index(func_node)
                    if func_index not in self.records["return_statement_map"]:
                        self.records["return_statement_map"][func_index] = []
                    self.records["return_statement_map"][func_index].append(self.get_index(node))

        # Add last line of each function as implicit return
        for key, node in node_list.items():
            if node.type == "function_definition":
                func_index = self.get_index(node)
                last_line_result = self.get_block_last_line(node, "body")
                if last_line_result:
                    last_node, _ = last_line_result
                    if last_node and (last_node.start_point, last_node.end_point, last_node.type) in node_list:
                        last_index = self.get_index(last_node)
                        if func_index not in self.records["return_statement_map"]:
                            self.records["return_statement_map"][func_index] = []
                        if last_index not in self.records["return_statement_map"][func_index]:
                            self.records["return_statement_map"][func_index].append(last_index)

        # ============================================================
        # STEP 7: Add Dummy Nodes
        # ============================================================
        # Add start node (ID=1)
        self.CFG_node_list.append((1, 0, "start_node", "start"))

        # ============================================================
        # STEP 8: Add Control Flow Edges
        # ============================================================
        for key, node in node_list.items():
            current_index = self.get_index(node)

            # -------------------- FUNCTION DEFINITION --------------------
            if node.type == "function_definition":
                func_name = c_nodes.get_function_name(node)

                # Connect start node based on whether main function exists
                # This follows the same logic as Java CFG implementation
                if "main_function" in self.records:
                    # Main function exists: only connect start_node to main
                    # Other functions become disjoint graphs
                    if func_name == "main":
                        self.add_edge(1, current_index, "next")
                else:
                    # No main function: connect start_node to all functions
                    self.add_edge(1, current_index, "next")

                # Connect function to first statement in body
                first_line_result = self.edge_first_line(node, node_list)
                if first_line_result:
                    first_index, _ = first_line_result
                    self.add_edge(current_index, first_index, "first_next_line")

            # -------------------- IF STATEMENT --------------------
            elif node.type == "if_statement":
                # Get consequence (then block)
                consequence = node.child_by_field_name("consequence")
                if consequence:
                    # Edge to first statement in then block
                    if consequence.type == "compound_statement":
                        children_list = list(consequence.named_children)
                        if children_list:
                            first_stmt = children_list[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "pos_next")
                        else:
                            # Empty then block - go to next after if
                            next_index, _ = self.get_next_index(node, node_list)
                            if next_index != 2:
                                self.add_edge(current_index, next_index, "pos_next")
                    else:
                        # Single statement
                        if (consequence.start_point, consequence.end_point, consequence.type) in node_list:
                            self.add_edge(current_index, self.get_index(consequence), "pos_next")

                    # Edge from last statement in then block to next after entire if-else chain
                    # We need to find the outermost if statement in the chain
                    last_node, _ = self.get_block_last_line(node, "consequence")
                    if last_node and (last_node.start_point, last_node.end_point, last_node.type) in node_list:
                        if last_node.type not in ["return_statement", "break_statement", "continue_statement", "goto_statement"]:
                            # Find the outermost if statement by traversing up while parent is if_statement with this node as alternative
                            outermost_if = node
                            parent = node.parent
                            while parent and parent.type == "if_statement":
                                parent_alt = parent.child_by_field_name("alternative")
                                if parent_alt == outermost_if:
                                    outermost_if = parent
                                    parent = parent.parent
                                else:
                                    break

                            next_index, _ = self.get_next_index(outermost_if, node_list)
                            if next_index != 2:
                                self.add_edge(self.get_index(last_node), next_index, "next_line")

                # Get alternative (else block)
                alternative = node.child_by_field_name("alternative")
                if alternative:
                    # alternative is an else_clause node, need to get the actual content
                    # Get the first named child of else_clause (skip the "else" keyword)
                    alt_content = None
                    for child in alternative.named_children:
                        alt_content = child
                        break

                    if alt_content is None:
                        # Empty else clause
                        next_index, _ = self.get_next_index(node, node_list)
                        if next_index != 2:
                            self.add_edge(current_index, next_index, "neg_next")
                    elif alt_content.type == "if_statement":
                        # else if - connect to the else-if node
                        self.add_edge(current_index, self.get_index(alt_content), "neg_next")
                    elif alt_content.type == "compound_statement":
                        # else { ... } - connect to first statement in block
                        children_list = list(alt_content.named_children)
                        if children_list:
                            first_stmt = children_list[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "neg_next")
                        else:
                            # Empty else block
                            next_index, _ = self.get_next_index(node, node_list)
                            if next_index != 2:
                                self.add_edge(current_index, next_index, "neg_next")

                        # Edge from last statement in else block to next after entire if-else chain
                        last_node = None
                        if children_list:
                            last_stmt = children_list[-1]
                            if (last_stmt.start_point, last_stmt.end_point, last_stmt.type) in node_list:
                                last_node = last_stmt

                        if last_node and (last_node.start_point, last_node.end_point, last_node.type) in node_list:
                            if last_node.type not in ["return_statement", "break_statement", "continue_statement", "goto_statement"]:
                                # Find the outermost if statement
                                outermost_if = node
                                parent = node.parent
                                while parent and parent.type == "if_statement":
                                    parent_alt = parent.child_by_field_name("alternative")
                                    if parent_alt:
                                        # Check if outermost_if is inside parent's alternative
                                        parent_alt_content = None
                                        for child in parent_alt.named_children:
                                            parent_alt_content = child
                                            break
                                        if parent_alt_content == outermost_if:
                                            outermost_if = parent
                                            parent = parent.parent
                                        else:
                                            break
                                    else:
                                        break

                                next_index, _ = self.get_next_index(outermost_if, node_list)
                                if next_index != 2:
                                    self.add_edge(self.get_index(last_node), next_index, "next_line")
                    else:
                        # Single statement (no braces)
                        if (alt_content.start_point, alt_content.end_point, alt_content.type) in node_list:
                            self.add_edge(current_index, self.get_index(alt_content), "neg_next")

                            # Edge from that statement to next after if
                            if alt_content.type not in ["return_statement", "break_statement", "continue_statement", "goto_statement"]:
                                # Find the outermost if statement
                                outermost_if = node
                                parent = node.parent
                                while parent and parent.type == "if_statement":
                                    parent_alt = parent.child_by_field_name("alternative")
                                    if parent_alt:
                                        parent_alt_content = None
                                        for child in parent_alt.named_children:
                                            parent_alt_content = child
                                            break
                                        if parent_alt_content == outermost_if:
                                            outermost_if = parent
                                            parent = parent.parent
                                        else:
                                            break
                                    else:
                                        break

                                next_index, _ = self.get_next_index(outermost_if, node_list)
                                if next_index != 2:
                                    self.add_edge(self.get_index(alt_content), next_index, "next_line")
                else:
                    # No else - direct edge to next statement
                    next_index, _ = self.get_next_index(node, node_list)
                    if next_index != 2:
                        self.add_edge(current_index, next_index, "neg_next")

            # -------------------- WHILE STATEMENT --------------------
            elif node.type == "while_statement":
                # Edge to first statement in body (loop entry)
                body = node.child_by_field_name("body")
                if body:
                    if body.type == "compound_statement":
                        children_list = list(body.named_children)
                        if children_list:
                            first_stmt = children_list[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "pos_next")
                    else:
                        if (body.start_point, body.end_point, body.type) in node_list:
                            self.add_edge(current_index, self.get_index(body), "pos_next")

                    # Back edge from last statement in body to loop header
                    last_node, _ = self.get_block_last_line(node, "body")
                    if last_node and (last_node.start_point, last_node.end_point, last_node.type) in node_list:
                        if last_node.type not in ["break_statement", "return_statement", "goto_statement"]:
                            self.add_edge(self.get_index(last_node), current_index, "loop_control")

                # Edge to next statement (loop exit)
                next_index, _ = self.get_next_index(node, node_list)
                if next_index != 2:
                    self.add_edge(current_index, next_index, "neg_next")

                # Self-loop for update
                self.add_edge(current_index, current_index, "loop_update")

            # -------------------- FOR STATEMENT --------------------
            elif node.type == "for_statement":
                # Edge to first statement in body (loop entry)
                body = node.child_by_field_name("body")
                if body:
                    if body.type == "compound_statement":
                        children_list = list(body.named_children)
                        if children_list:
                            first_stmt = children_list[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "pos_next")
                    else:
                        if (body.start_point, body.end_point, body.type) in node_list:
                            self.add_edge(current_index, self.get_index(body), "pos_next")

                    # Back edge from last statement in body to loop header
                    last_node, _ = self.get_block_last_line(node, "body")
                    if last_node and (last_node.start_point, last_node.end_point, last_node.type) in node_list:
                        if last_node.type not in ["break_statement", "return_statement", "goto_statement"]:
                            self.add_edge(self.get_index(last_node), current_index, "loop_control")

                # Edge to next statement (loop exit)
                next_index, _ = self.get_next_index(node, node_list)
                if next_index != 2:
                    self.add_edge(current_index, next_index, "neg_next")

                # Self-loop for update
                self.add_edge(current_index, current_index, "loop_update")

            # -------------------- DO STATEMENT --------------------
            elif node.type == "do_statement":
                # Edge to first statement in body
                body = node.child_by_field_name("body")
                if body:
                    if body.type == "compound_statement":
                        children_list = list(body.named_children)
                        if children_list:
                            first_stmt = children_list[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "pos_next")
                    else:
                        if (body.start_point, body.end_point, body.type) in node_list:
                            self.add_edge(current_index, self.get_index(body), "pos_next")

                    # Edge from last statement to while condition
                    last_node, _ = self.get_block_last_line(node, "body")
                    if last_node and (last_node.start_point, last_node.end_point, last_node.type) in node_list:
                        # Find the while condition node
                        condition = node.child_by_field_name("condition")
                        if condition:
                            cond_key = (condition.start_point, condition.end_point, condition.type)
                            if cond_key in node_list:
                                cond_index = self.get_index(condition)
                                self.add_edge(self.get_index(last_node), cond_index, "next_line")

                # Find the while condition and create back edge
                condition = node.child_by_field_name("condition")
                if condition:
                    cond_key = (condition.start_point, condition.end_point, condition.type)
                    if cond_key in node_list:
                        cond_index = self.get_index(condition)
                        # Back edge from condition to do
                        self.add_edge(cond_index, current_index, "loop_control")
                        # Exit edge from condition to next
                        next_index, _ = self.get_next_index(node, node_list)
                        if next_index != 2:
                            self.add_edge(cond_index, next_index, "neg_next")

            # -------------------- SWITCH STATEMENT --------------------
            elif node.type == "switch_statement":
                body = node.child_by_field_name("body")
                if body:
                    # Find all case statements
                    case_statements = []
                    default_stmt = None

                    def find_cases(n):
                        if n.type == "case_statement":
                            case_statements.append(n)
                            # Check if it's default
                            if n.children and n.children[0].type == "default":
                                nonlocal default_stmt
                                default_stmt = n
                        for child in n.children:
                            find_cases(child)

                    find_cases(body)

                    # Edge from switch to each case
                    for case in case_statements:
                        if (case.start_point, case.end_point, case.type) in node_list:
                            self.add_edge(current_index, self.get_index(case), "switch_case")

                    # If no default case, add edge to next statement
                    if not default_stmt:
                        next_index, _ = self.get_next_index(node, node_list)
                        if next_index != 2:
                            self.add_edge(current_index, next_index, "switch_exit")

            # -------------------- CASE STATEMENT --------------------
            elif node.type == "case_statement":
                # Edge to first statement in case body
                children = list(node.named_children)

                # Check if this is a default case
                # default: printf(...); has NO case value, so children[0] is the first statement
                # case 1: printf(...); has case value at children[0], first statement at children[1]
                is_default = node.children and node.children[0].type == "default"

                # For default case, start from children[0] (first statement)
                # For regular case, start from children[1] (skip case value)
                start_index = 0 if is_default else 1

                if len(children) > start_index:
                    # Find first executable statement after case label
                    for child in children[start_index:]:
                        if (child.start_point, child.end_point, child.type) in node_list:
                            self.add_edge(current_index, self.get_index(child), "case_next")
                            break

            # -------------------- BREAK STATEMENT --------------------
            elif node.type == "break_statement":
                # Find enclosing loop or switch
                parent = node.parent
                while parent:
                    if parent.type in self.statement_types["loop_control_statement"] or parent.type == "switch_statement":
                        # Edge to statement after the loop/switch
                        next_index, _ = self.get_next_index(parent, node_list)
                        if next_index != 2:
                            self.add_edge(current_index, next_index, "jump_next")
                        break
                    parent = parent.parent

            # -------------------- CONTINUE STATEMENT --------------------
            elif node.type == "continue_statement":
                # Find enclosing loop
                loop_node = self.find_enclosing_loop(node)
                if loop_node and (loop_node.start_point, loop_node.end_point, loop_node.type) in node_list:
                    self.add_edge(current_index, self.get_index(loop_node), "jump_next")

            # -------------------- GOTO STATEMENT --------------------
            elif node.type == "goto_statement":
                # Find target label
                label_node = node.child_by_field_name("label")
                if label_node:
                    label_name = label_node.text.decode("UTF-8")
                    if label_name in self.records["label_statement_map"]:
                        target_key = self.records["label_statement_map"][label_name]
                        if target_key in node_list:
                            target_node = node_list[target_key]
                            self.add_edge(current_index, self.get_index(target_node), "jump_next")

            # -------------------- LABELED STATEMENT --------------------
            elif node.type == "labeled_statement":
                # Edge to the statement after the label
                stmt = node.child_by_field_name("statement")
                if stmt and (stmt.start_point, stmt.end_point, stmt.type) in node_list:
                    self.add_edge(current_index, self.get_index(stmt), "next_line")

        # ============================================================
        # STEP 9: Add Function Call Edges
        # ============================================================
        self.add_function_call_edges(node_list)

        return self.CFG_node_list, self.CFG_edge_list
