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

    def function_list(self, root_node, node_list):
        """
        Build a map of all function calls in the program.
        Maps function signatures to their call sites.
        """
        if root_node.type == "call_expression":
            # Get function name
            function_node = root_node.child_by_field_name("function")
            if function_node:
                if function_node.type == "identifier":
                    func_name = function_node.text.decode('utf-8')

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
            # Check if this identifier has a declaration
            arg_index_key = (arg_node.start_point, arg_node.end_point, arg_node.type)
            if arg_index_key in self.index:
                arg_index = self.index[arg_index_key]

                # Check if it's mapped to a declaration
                if arg_index in self.declaration_map:
                    decl_index = self.declaration_map[arg_index]
                    # Get type from symbol table
                    if decl_index in self.symbol_table["data_type"]:
                        return self.symbol_table["data_type"][decl_index]

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
            if field and field.type == "identifier":
                # Try to look up field type
                # For now, we don't have struct field type information
                # This would require parsing struct definitions
                return "unknown"
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
        """
        for (func_name, signature), call_sites in self.records["function_calls"].items():
            # Check if function is defined in this file
            func_key = (func_name, signature)
            if func_key in self.records["function_list"]:
                func_index = self.records["function_list"][func_key]

                for call_id, parent_id in call_sites:
                    # Edge from caller to function
                    self.add_edge(parent_id, func_index, f"function_call|{call_id}")

                    # Add return edges from all return points in the function
                    if func_index in self.records["return_statement_map"]:
                        for return_id in self.records["return_statement_map"][func_index]:
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
        # STEP 5: Build Function Call Map
        # ============================================================
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
        # STEP 6: Add Dummy Nodes
        # ============================================================
        # Add start node (ID=1)
        self.CFG_node_list.append((1, 0, "start_node", "start"))

        # ============================================================
        # STEP 7: Add Control Flow Edges
        # ============================================================
        for key, node in node_list.items():
            current_index = self.get_index(node)

            # -------------------- FUNCTION DEFINITION --------------------
            if node.type == "function_definition":
                func_name = c_nodes.get_function_name(node)

                # Connect start node to main function
                if func_name == "main":
                    self.add_edge(1, current_index, "next")
                else:
                    # Connect start to all top-level functions
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

                    # Edge from last statement in then block to next after if
                    last_node, _ = self.get_block_last_line(node, "consequence")
                    if last_node and (last_node.start_point, last_node.end_point, last_node.type) in node_list:
                        if last_node.type not in ["return_statement", "break_statement", "continue_statement", "goto_statement"]:
                            next_index, _ = self.get_next_index(node, node_list)
                            if next_index != 2:
                                self.add_edge(self.get_index(last_node), next_index, "next_line")

                # Get alternative (else block)
                alternative = node.child_by_field_name("alternative")
                if alternative:
                    # Edge to first statement in else block
                    if alternative.type == "compound_statement":
                        children_list = list(alternative.named_children)
                        if children_list:
                            first_stmt = children_list[0]
                            if (first_stmt.start_point, first_stmt.end_point, first_stmt.type) in node_list:
                                self.add_edge(current_index, self.get_index(first_stmt), "neg_next")
                        else:
                            # Empty else block
                            next_index, _ = self.get_next_index(node, node_list)
                            if next_index != 2:
                                self.add_edge(current_index, next_index, "neg_next")
                    elif alternative.type == "if_statement":
                        # else if
                        self.add_edge(current_index, self.get_index(alternative), "neg_next")
                    else:
                        # Single statement
                        if (alternative.start_point, alternative.end_point, alternative.type) in node_list:
                            self.add_edge(current_index, self.get_index(alternative), "neg_next")

                    # Edge from last statement in else block to next after if
                    last_node, _ = self.get_block_last_line(node, "alternative")
                    if last_node and (last_node.start_point, last_node.end_point, last_node.type) in node_list:
                        if last_node.type not in ["return_statement", "break_statement", "continue_statement", "goto_statement"]:
                            next_index, _ = self.get_next_index(node, node_list)
                            if next_index != 2:
                                self.add_edge(self.get_index(last_node), next_index, "next_line")
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
                if len(children) > 1:  # case value + statements
                    # Find first executable statement after case label
                    for child in children[1:]:
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
        # STEP 8: Add Function Call Edges
        # ============================================================
        self.add_function_call_edges(node_list)

        return self.CFG_node_list, self.CFG_edge_list
