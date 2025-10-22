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
            "constexpr_functions": {},             # function_id → True
            "inline_functions": {},                # function_id → True
            "noexcept_functions": {},              # function_id → True
            "attributed_functions": {},            # function_id → [attributes]
        }
        self.index_counter = max(self.index.values())
        self.CFG_node_indices = []

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

                # Case 1: Simple identifier (regular function call)
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

                if func_name:
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

    def add_function_call_edges(self):
        """
        Add edges for function calls and returns.
        Handles:
        - Regular function calls
        - Member function calls
        - Constructor calls
        - Virtual function dispatch
        """
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
                        if fn_id in self.records["return_statement_map"]:
                            for return_id in self.records["return_statement_map"][fn_id]:
                                self.add_edge(return_id, parent_id, "function_return")

        # Process method calls (similar pattern but consider class context)
        for (method_name, signature), call_list in self.records["method_calls"].items():
            for ((class_name, fn_name), fn_sig), fn_id in self.records["function_list"].items():
                if fn_name == method_name:
                    for call_id, parent_id in call_list:
                        # Check if it's a virtual function
                        if fn_id in self.records["virtual_functions"]:
                            self.add_edge(parent_id, fn_id, f"virtual_call|{call_id}")
                        else:
                            self.add_edge(parent_id, fn_id, f"method_call|{call_id}")

                        # Add return edges
                        if fn_id in self.records["return_statement_map"]:
                            for return_id in self.records["return_statement_map"][fn_id]:
                                self.add_edge(return_id, parent_id, "method_return")

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

                # Skip nodes with inner definitions
                if cpp_nodes.has_inner_definition(node):
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

                # Track last line for return edges
                last_line, last_type = self.get_block_last_line(node, "body")
                if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                    last_index = self.get_index(last_line)
                    if current_index not in self.records["return_statement_map"]:
                        self.records["return_statement_map"][current_index] = []
                    if last_index not in self.records["return_statement_map"][current_index]:
                        self.records["return_statement_map"][current_index].append(last_index)

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
                    last_line, _ = self.get_block_last_line(node, "consequence")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                        next_index, next_node = self.get_next_index(node, node_list)
                        if next_index != 2:
                            self.add_edge(self.get_index(last_line), next_index, "next_line")

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
                    # Need to find last statement in the else body
                    if alternative.type == "else_clause":
                        # For else_clause, we need to get the body and find its last statement
                        if else_body.type == "compound_statement":
                            children = list(else_body.named_children)
                            if children:
                                last_stmt = children[-1]
                                if (last_stmt.start_point, last_stmt.end_point, last_stmt.type) in node_list:
                                    next_index, next_node = self.get_next_index(node, node_list)
                                    if next_index != 2:
                                        self.add_edge(self.get_index(last_stmt), next_index, "next_line")
                        else:
                            # Single statement after else
                            if (else_body.start_point, else_body.end_point, else_body.type) in node_list:
                                next_index, next_node = self.get_next_index(node, node_list)
                                if next_index != 2:
                                    self.add_edge(self.get_index(else_body), next_index, "next_line")
                    elif else_body.type == "compound_statement" or else_body.type != "if_statement":
                        # Direct compound_statement (not wrapped in else_clause)
                        last_line, _ = self.get_block_last_line(node, "alternative")
                        if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                            next_index, next_node = self.get_next_index(node, node_list)
                            if next_index != 2:
                                self.add_edge(self.get_index(last_line), next_index, "next_line")
                else:
                    # No else branch - if condition false, go to next statement
                    next_index, next_node = self.get_next_index(node, node_list)
                    if next_index != 2:
                        self.add_edge(current_index, next_index, "neg_next")

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
                    last_line, _ = self.get_block_last_line(node, "body")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
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
                    last_line, _ = self.get_block_last_line(node, "body")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
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

                    # Back edge
                    last_line, _ = self.get_block_last_line(node, "body")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
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
                    last_line, _ = self.get_block_last_line(node, "body")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
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
                # Edge to first line in labeled block
                first_line = self.edge_first_line(node, node_list)
                if first_line:
                    first_index, first_node = first_line
                    self.add_edge(current_index, first_index, "first_next_line")

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
                    # First child is the value, rest are statements
                    for i in range(1, len(children)):
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
                last_line, _ = self.get_block_last_line(node, "body")
                if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
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
                last_line, _ = self.get_block_last_line(node, "body")
                if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
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
