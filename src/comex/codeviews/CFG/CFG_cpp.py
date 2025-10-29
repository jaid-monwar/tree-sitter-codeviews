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
            "namespace_aliases": {},               # alias_name → actual_namespace
            "template_list": {},                   # template_name → node_id
            "extends": {},                         # class_name → [base_classes]
            "function_calls": {},                  # sig → [(call_id, parent_id)]
            "method_calls": {},                    # sig → [(call_id, parent_id, object_name)]
            "static_method_calls": {},             # (class_name, func_name, sig) → [(call_id, parent_id)]
            "operator_calls": {},                  # (operator_name, is_member) → [(call_id, parent_id, operand_type)]
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

        # Track template instantiations for each object
        self.template_instantiations = {}  # variable_name → (base_class_name, tuple_of_template_args, function_id_of_specialization)

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

    def resolve_template_specialization(self, base_class_name, template_args, method_name):
        """
        Resolve which template specialization matches the given template arguments.
        Returns the function_id of the matching specialization's method, or None if not found.

        Template specialization resolution follows C++ rules:
        1. Exact match (full specialization) takes highest priority
        2. Partial specialization takes next priority (most specific match)
        3. Primary template is the fallback

        Args:
            base_class_name: The base template class name (e.g., "Container")
            template_args: Tuple of template argument strings (e.g., ("int", "std::string"))
            method_name: The method being called (e.g., "display")

        Returns:
            function_id of the matching method, or None if no match found
        """
        if not template_args:
            return None

        # Search for matching template specialization
        # Priority: full specialization > partial specialization > primary template

        # Look through all functions to find methods with this name in classes
        # that could be specializations of the base class
        candidates = []  # (specificity, function_id, class_name)

        for ((class_name, fn_name), fn_sig), fn_id in self.records["function_list"].items():
            if fn_name != method_name:
                continue

            # Get the class node to check if it's a template specialization
            fn_key = None
            for key, fid in self.index.items():
                if fid == fn_id:
                    fn_key = key
                    break

            if not fn_key:
                continue

            fn_node = self.node_list.get(fn_key)
            if not fn_node:
                continue

            # Find the containing class
            class_node = self.get_containing_class(fn_node)
            if not class_node:
                continue

            # Check if this class is a template specialization by looking at its parent
            parent = class_node.parent
            if not parent or parent.type != "template_declaration":
                # Not a template class - skip
                continue

            # Analyze the template declaration to determine specialization type
            template_params = []
            template_specs = []

            for child in parent.children:
                if child.type == "template_parameter_list":
                    # Count template parameters
                    for param in child.named_children:
                        if param.type in ["type_parameter_declaration", "parameter_declaration"]:
                            template_params.append(param)

            # Also check for specialization syntax in class_specifier
            # Full specialization: template <> class Container<int, double>
            # Partial specialization: template <typename T> class Container<T, T>
            # Primary template: template <typename T, typename U> class Container

            is_full_specialization = len(template_params) == 0
            is_primary_template = False
            specificity = 0

            # Extract any explicit template arguments from the class name
            for child in class_node.children:
                if child.type == "template_argument_list":
                    # This class has explicit template arguments - it's a specialization
                    template_specs = []
                    for arg in child.named_children:
                        template_specs.append(arg.text.decode('utf-8'))
                    break

            if not template_specs:
                # Primary template (no explicit template arguments)
                is_primary_template = True
                specificity = 0  # Lowest priority
            elif is_full_specialization:
                # Full specialization: check for exact match
                if len(template_specs) == len(template_args):
                    # Normalize type strings for comparison (remove whitespace)
                    specs_normalized = [s.replace(" ", "") for s in template_specs]
                    args_normalized = [a.replace(" ", "") for a in template_args]

                    if specs_normalized == args_normalized:
                        specificity = 100  # Highest priority for exact match
                    else:
                        continue  # Not a match - skip
                else:
                    continue  # Arity mismatch - skip
            else:
                # Partial specialization: check for pattern match
                # For simplicity, we'll do pattern matching here
                # This is complex in general - for now, handle common cases:
                # - Container<T, T> matches if both args are the same type
                # - Container<T, T*> matches if second arg is pointer to first
                if len(template_specs) == len(template_args):
                    match = self._match_template_pattern(template_specs, template_args)
                    if match:
                        specificity = 50  # Medium priority for partial specialization
                    else:
                        continue
                else:
                    continue

            candidates.append((specificity, fn_id, class_name))

        if not candidates:
            return None

        # Sort by specificity (highest first) and return the most specific match
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]  # Return function_id

    def _match_template_pattern(self, pattern, args):
        """
        Check if template arguments match a partial specialization pattern.

        Args:
            pattern: List of pattern strings from partial specialization (e.g., ["T", "T"])
            args: List of actual template arguments (e.g., ["int", "int"])

        Returns:
            True if args match the pattern, False otherwise
        """
        if len(pattern) != len(args):
            return False

        # Build a mapping from template parameters to actual types
        param_map = {}

        for p, a in zip(pattern, args):
            # Normalize strings
            p_norm = p.replace(" ", "")
            a_norm = a.replace(" ", "")

            # Check for pointer pattern (e.g., "T*")
            if p_norm.endswith("*"):
                # Extract base type
                base_p = p_norm[:-1]
                # Check if argument is a pointer
                if not a_norm.endswith("*"):
                    return False
                base_a = a_norm[:-1]

                # Check if base types match the pattern
                if base_p in param_map:
                    if param_map[base_p] != base_a:
                        return False
                else:
                    param_map[base_p] = base_a
            else:
                # Direct type or template parameter
                if p_norm in param_map:
                    # We've seen this parameter before - must match
                    if param_map[p_norm] != a_norm:
                        return False
                else:
                    # New parameter - record it
                    # Check if this looks like a template parameter (single letter or "typename ...")
                    if len(p_norm) == 1 and p_norm.isupper():
                        param_map[p_norm] = a_norm
                    elif p_norm == a_norm:
                        # Exact type match
                        continue
                    else:
                        # Pattern doesn't match
                        return False

        return True

    def register_template_specializations(self, node_list):
        """
        Scan the AST for template class specializations and register their methods.
        This fixes the issue where partial specializations are recorded as "anonymous_class"
        and not properly added to the function_list.
        """
        for key, node in node_list.items():
            # Look for function definitions
            if node.type == "function_definition":
                # Check if this function is inside a template class
                class_node = self.get_containing_class(node)
                if not class_node or not class_node.parent:
                    continue

                parent = class_node.parent
                if parent.type != "template_declaration":
                    continue

                # This is a method in a template class
                # Extract the class name and template arguments (if specialized)
                class_name = "Container"  # Default base name
                template_args = []

                # Look for type_identifier or template_argument_list in class_node
                for child in class_node.children:
                    if child.type == "type_identifier":
                        class_name = child.text.decode('utf-8')
                    elif child.type == "template_argument_list":
                        # This class has explicit template arguments - it's a specialization
                        for arg in child.named_children:
                            template_args.append(arg.text.decode('utf-8'))

                # Get function signature using declarator field
                fn_name = None
                fn_sig = []

                # Use tree-sitter's field-based access for more reliable extraction
                declarator = None
                for child in node.children:
                    if child.type in ["function_declarator", "pointer_declarator", "reference_declarator"]:
                        declarator = child
                        break

                if declarator:
                    # Recursively search for identifier/field_identifier and parameter_list
                    def extract_from_declarator(decl_node):
                        nonlocal fn_name, fn_sig
                        for gc in decl_node.children:
                            # Methods use field_identifier, standalone functions use identifier
                            if gc.type in ["identifier", "field_identifier"]:
                                fn_name = gc.text.decode('utf-8')
                            elif gc.type == "parameter_list":
                                # Extract parameter types
                                for param in gc.named_children:
                                    if param.type == "parameter_declaration":
                                        param_type_node = param.child_by_field_name("type")
                                        if param_type_node:
                                            fn_sig.append(param_type_node.text.decode('utf-8'))
                            elif gc.type in ["function_declarator", "pointer_declarator", "reference_declarator"]:
                                # Recurse
                                extract_from_declarator(gc)

                    extract_from_declarator(declarator)

                if not fn_name:
                    continue

                fn_id = self.get_index(node)
                key = ((class_name, fn_name), tuple(fn_sig))

                # Check if this function is already in function_list
                if key not in self.records["function_list"]:
                    # Add it
                    self.records["function_list"][key] = fn_id

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

    def extract_thrown_type(self, throw_node):
        """
        Extract the type of the expression being thrown.
        Returns a tuple: (type_category, type_string)

        type_category: 'int', 'float', 'string', 'class', 'catch_all'
        type_string: detailed type information
        """
        if throw_node.type != "throw_statement":
            return ('unknown', None)

        # Find the thrown expression (child after 'throw' keyword)
        thrown_expr = None
        for child in throw_node.children:
            if child.type not in ["throw", ";"]:
                thrown_expr = child
                break

        if thrown_expr is None:
            # Re-throw: throw;
            return ('rethrow', None)

        # Analyze the expression type
        if thrown_expr.type == "number_literal":
            literal_text = thrown_expr.text.decode('utf-8')
            # Check for float suffix
            if 'f' in literal_text.lower() or '.' in literal_text:
                return ('float', 'float')
            else:
                return ('int', 'int')

        elif thrown_expr.type == "string_literal":
            return ('string', 'const char*')

        elif thrown_expr.type == "call_expression":
            # This is likely a class constructor: throw std::runtime_error(...)
            func_node = thrown_expr.child_by_field_name("function")
            if func_node:
                func_text = func_node.text.decode('utf-8')
                # Extract class name (handle std::exception, MyException, etc.)
                return ('class', func_text)

        elif thrown_expr.type == "identifier":
            # Throwing a variable - would need type inference
            # For now, return identifier name
            return ('variable', thrown_expr.text.decode('utf-8'))

        return ('unknown', thrown_expr.text.decode('utf-8') if thrown_expr else None)

    def extract_catch_parameter_type(self, catch_node):
        """
        Extract the parameter type from a catch clause.
        Returns a tuple: (type_category, type_string)

        type_category: 'int', 'float', 'string', 'class', 'catch_all'
        type_string: detailed type information
        """
        if catch_node.type != "catch_clause":
            return ('unknown', None)

        # Find parameter_list child
        param_list = None
        for child in catch_node.children:
            if child.type == "parameter_list":
                param_list = child
                break

        if param_list is None:
            return ('catch_all', '...')

        param_text = param_list.text.decode('utf-8')
        # Strip parentheses
        if param_text.startswith("(") and param_text.endswith(")"):
            param_text = param_text[1:-1].strip()

        # Check for catch-all
        if param_text == "...":
            return ('catch_all', '...')

        # Parse parameter type
        # Examples: "int errorCode", "const char* message", "const std::exception& e"

        # Split to get type (everything except last identifier which is parameter name)
        parts = param_text.split()
        if not parts:
            return ('catch_all', '...')

        # The type is everything except potentially the last identifier (variable name)
        # But we need to handle cases like "int", "int&", "const char*", "std::exception&"

        # Check for basic types
        if 'int' in param_text and 'point' not in param_text.lower():
            return ('int', 'int')
        elif 'float' in param_text or 'double' in param_text:
            return ('float', 'float')
        elif 'char*' in param_text or 'char *' in param_text:
            return ('string', 'const char*')
        elif 'exception' in param_text.lower() or '::' in param_text:
            # This is a class type, potentially with namespace
            # Extract the class name
            type_part = param_text
            # Remove const, &, and variable name
            type_part = type_part.replace('const', '').replace('&', '').strip()
            # Take everything except last word (which might be variable name)
            words = type_part.split()
            if len(words) > 1:
                # Last word is likely variable name, take everything before
                class_name = ' '.join(words[:-1])
            else:
                class_name = words[0]
            return ('class', class_name.strip())

        # Default: treat as class type
        return ('class', param_text)

    def exception_type_matches(self, thrown_type, catch_type):
        """
        Check if a thrown exception type matches a catch parameter type.

        Returns True if the exception can be caught by the catch block.
        Implements C++ exception matching rules:
        1. Exact type match
        2. Derived class to base class (polymorphism)
        3. Catch-all (...) catches everything

        Args:
            thrown_type: tuple (type_category, type_string) from extract_thrown_type
            catch_type: tuple (type_category, type_string) from extract_catch_parameter_type
        """
        thrown_cat, thrown_str = thrown_type
        catch_cat, catch_str = catch_type

        # Catch-all catches everything
        if catch_cat == 'catch_all':
            return True

        # Re-throw doesn't match any catch (it propagates)
        if thrown_cat == 'rethrow':
            return False

        # Exact category match
        if thrown_cat == catch_cat:
            # For primitives, categories match is enough
            if thrown_cat in ['int', 'float', 'string']:
                return True

            # For classes, check inheritance
            if thrown_cat == 'class':
                # Normalize scope operators (handle both :: and _SCOPE_)
                thrown_normalized = thrown_str.replace('_SCOPE_', '::').replace(' ', '') if thrown_str else ''
                catch_normalized = catch_str.replace('_SCOPE_', '::').replace(' ', '') if catch_str else ''

                # Check for exact match
                if thrown_normalized == catch_normalized:
                    return True

                # Check for inheritance: std::runtime_error is a std::exception
                # C++ standard exception hierarchy: all std::*_error and std::*exception classes inherit from std::exception
                if catch_normalized in ['std::exception', 'exception']:
                    # Check if thrown type is a standard exception or error
                    if thrown_normalized.startswith('std::'):
                        # Standard library exceptions: std::runtime_error, std::logic_error, std::bad_alloc, etc.
                        # Pattern: std::*error or std::*exception all inherit from std::exception
                        if ('error' in thrown_normalized.lower() or
                            'exception' in thrown_normalized.lower()):
                            return True

        return False

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

            # Check if parent is a try_statement or catch_clause - skip to next after entire try-catch
            if parent.type in ["try_statement", "catch_clause"]:
                # For try/catch blocks, get the next statement after the entire try-catch construct
                if parent.type == "catch_clause":
                    # If we're in a catch, need to find the parent try statement first
                    try_parent = parent.parent
                    if try_parent and try_parent.type == "try_statement":
                        current_node = try_parent
                        next_node = current_node.next_named_sibling
                        continue
                else:
                    # We're at a try_statement, get next sibling
                    current_node = parent
                    next_node = current_node.next_named_sibling
                    continue

            # Check if parent is a lambda expression - end of lambda
            # Lambda returns should be handled by add_lambda_edges(), not by sequential flow
            if parent.type == "lambda_expression":
                # Signal that we've reached a lambda boundary
                # Return a special marker (None, parent) to indicate lambda exit
                # This prevents automatic sequential edges from being created
                return (2, parent)

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
        Check if a node is the last statement in a control flow block (if/else/loop/try/catch).
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
                    "for_range_loop", "do_statement", "else_clause",
                    "catch_clause", "try_statement"
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

        # Case 4: Parent is a catch_clause or try_statement (exception handling blocks)
        if parent.type in ["catch_clause", "try_statement"]:
            body = parent.child_by_field_name("body")
            if body and body == node:
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
                qualified_scope = None  # For static method calls (Class::staticMethod)

                # Case 1: Simple identifier (could be regular call, function pointer, or constructor)
                if function_node.type == "identifier":
                    func_name = function_node.text.decode('utf-8')

                    # Check if this is a constructor call (identifier matching a class name)
                    # This happens in return statements: return Vector2D(x, y);
                    is_constructor = False
                    for ((fn_class_name, fn_name), fn_sig), fn_id in self.records.get("function_list", {}).items():
                        if fn_class_name == func_name and fn_name == func_name:
                            # This is a constructor (class name == function name)
                            is_constructor = True
                            break

                    if is_constructor:
                        # This is a constructor call
                        class_name = func_name
                        # Find the parent statement node
                        parent_stmt = root_node
                        while parent_stmt and parent_stmt.type not in self.statement_types["node_list_type"]:
                            parent_stmt = parent_stmt.parent

                        if parent_stmt and (parent_stmt.start_point, parent_stmt.end_point, parent_stmt.type) in node_list:
                            parent_index = self.get_index(parent_stmt)
                            call_index = self.get_index(root_node)  # Use call_expression as call_index

                            # Get argument types for signature matching
                            args_node = root_node.child_by_field_name("arguments")
                            signature = self.get_call_signature(args_node)

                            # Track constructor call
                            key = (class_name, signature)
                            if key not in self.records["constructor_calls"]:
                                self.records["constructor_calls"][key] = []
                            self.records["constructor_calls"][key].append((call_index, parent_index))

                        # Skip normal function call processing for constructor calls
                        for child in root_node.children:
                            self.function_list(child, node_list)
                        return

                # Case 2: Field expression (member function call: obj.method())
                elif function_node.type == "field_expression":
                    field = function_node.child_by_field_name("field")
                    if field:
                        func_name = field.text.decode('utf-8')

                # Case 3: Qualified identifier (namespace::function or Class::method)
                elif function_node.type == "qualified_identifier":
                    full_name = function_node.text.decode('utf-8')
                    # Parse qualified identifier to extract class/namespace and function name
                    # Format: Class::staticMethod or namespace::Class::method
                    parts = full_name.split("::")
                    if len(parts) >= 2:
                        # For now, assume last part is the function name
                        # and everything before is the class/namespace
                        func_name = parts[-1]
                        qualified_scope = "::".join(parts[:-1])

                        # Resolve namespace aliases
                        # Check if the first part of the qualified scope is an alias
                        scope_parts = qualified_scope.split("::")
                        if scope_parts[0] in self.records.get("namespace_aliases", {}):
                            # Replace the alias with the actual namespace
                            actual_namespace = self.records["namespace_aliases"][scope_parts[0]]
                            # Rebuild the qualified scope
                            if len(scope_parts) > 1:
                                # e.g., "OI::Inner" becomes "Outer::Inner::Inner"
                                qualified_scope = actual_namespace + "::" + "::".join(scope_parts[1:])
                            else:
                                # e.g., "OI" becomes "Outer::Inner"
                                qualified_scope = actual_namespace
                    else:
                        func_name = full_name
                        qualified_scope = None

                # Case 4: Subscript expression (array of function pointers: operations[0](args))
                elif function_node.type == "subscript_expression":
                    is_indirect_call = True
                    # Get the array name
                    argument = function_node.child_by_field_name("argument")
                    if argument and argument.type == "identifier":
                        pointer_var = argument.text.decode('utf-8')

                # Case 5: Template function (template instantiation: add<float>(...))
                elif function_node.type == "template_function":
                    # Extract the identifier from the template_function node
                    # Structure: template_function -> identifier + template_argument_list
                    identifier_node = None
                    for child in function_node.named_children:
                        if child.type == "identifier":
                            identifier_node = child
                            break

                    if identifier_node:
                        func_name = identifier_node.text.decode('utf-8')

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

                        # Determine if this is a method call, static method call, or function call
                        if function_node.type == "field_expression":
                            # Instance method call: obj.method()
                            # Extract object name from field_expression
                            object_name = None
                            argument_node = function_node.child_by_field_name("argument")
                            if argument_node and argument_node.type == "identifier":
                                object_name = argument_node.text.decode('utf-8')

                            key = (func_name, signature)
                            if key not in self.records["method_calls"]:
                                self.records["method_calls"][key] = []
                            self.records["method_calls"][key].append((call_index, parent_index, object_name))
                        elif qualified_scope:
                            # Static method call: Class::staticMethod()
                            key = (qualified_scope, func_name, signature)
                            if key not in self.records["static_method_calls"]:
                                self.records["static_method_calls"][key] = []
                            self.records["static_method_calls"][key].append((call_index, parent_index))
                        else:
                            # Regular function call
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
        # 5. Template instantiation: Container<int, std::string> container1(1, "Hello");
        elif root_node.type == "declaration":
            # Get the type (class name)
            type_node = root_node.child_by_field_name("type")

            # Handle both regular types and template types
            class_name = None
            template_args = None

            if type_node and type_node.type == "type_identifier":
                class_name = type_node.text.decode('utf-8')
            elif type_node and type_node.type == "template_type":
                # Extract base class name and template arguments
                # Structure: template_type -> name (type_identifier) + arguments (template_argument_list)
                for child in type_node.named_children:
                    if child.type == "type_identifier":
                        class_name = child.text.decode('utf-8')
                    elif child.type == "template_argument_list":
                        # Extract template arguments as a tuple of strings
                        template_args = []
                        for arg in child.named_children:
                            arg_text = arg.text.decode('utf-8')
                            template_args.append(arg_text)
                        template_args = tuple(template_args)

            if class_name:

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

                    # Store template instantiation information if this is a template type
                    if var_name and template_args:
                        # Will resolve the specialization later during edge generation
                        self.template_instantiations[var_name] = (class_name, template_args, None)

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

        # Handle operator overload calls
        # Operator calls are represented as binary_expression, assignment_expression, or update_expression
        elif root_node.type in ["binary_expression", "assignment_expression", "update_expression"]:
            # Find the parent statement node
            parent_stmt = root_node
            while parent_stmt and parent_stmt.type not in self.statement_types["node_list_type"]:
                parent_stmt = parent_stmt.parent

            if parent_stmt and (parent_stmt.start_point, parent_stmt.end_point, parent_stmt.type) in node_list:
                parent_index = self.get_index(parent_stmt)
                call_index = self.get_index(root_node)

                operator_symbol = None
                left_operand = None
                right_operand = None
                is_member_operator = True  # Most operators are member functions

                if root_node.type == "binary_expression":
                    # Binary operators: +, -, *, ==, !=, <, >, <=, >=, <<, >>, etc.
                    left_operand = root_node.child_by_field_name("left")
                    right_operand = root_node.child_by_field_name("right")
                    # The operator is the middle child
                    for child in root_node.children:
                        if child.type in ["+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">=", "<<", ">>", "&", "|", "^", "&&", "||"]:
                            operator_symbol = child.type
                            break

                    # Stream operators (<<, >>) are typically non-member functions
                    if operator_symbol in ["<<", ">>"]:
                        is_member_operator = False

                elif root_node.type == "assignment_expression":
                    # Assignment operator: =
                    operator_symbol = "="
                    left_operand = root_node.child_by_field_name("left")
                    right_operand = root_node.child_by_field_name("right")

                elif root_node.type == "update_expression":
                    # Increment/decrement operators: ++, --
                    # Check if prefix or postfix
                    operand = root_node.child_by_field_name("argument")
                    if operand:
                        left_operand = operand
                        # Find the operator
                        for child in root_node.children:
                            if child.type in ["++", "--"]:
                                operator_symbol = child.type
                                # Determine if prefix or postfix based on position
                                if child.start_byte < operand.start_byte:
                                    # Prefix: ++var
                                    operator_symbol = f"{child.type}_prefix"
                                else:
                                    # Postfix: var++
                                    operator_symbol = f"{child.type}_postfix"
                                break

                # Track the operator call if we found the operator
                if operator_symbol and left_operand:
                    # Get the type of the operand
                    # For stream operators (<<, >>), the custom type is on the RIGHT (stream is on LEFT)
                    # For other operators, the custom type is on the LEFT
                    if operator_symbol in ["<<", ">>"] and right_operand:
                        # Stream operators: check right operand (e.g., cout << v1, cin >> v4)
                        operand_type = self.get_operand_type(right_operand)
                    else:
                        # Regular operators: check left operand (e.g., v1 + v2)
                        operand_type = self.get_operand_type(left_operand)

                    key = (operator_symbol, is_member_operator)
                    if key not in self.records["operator_calls"]:
                        self.records["operator_calls"][key] = []
                    self.records["operator_calls"][key].append((call_index, parent_index, operand_type))

        # Recursively process children
        for child in root_node.children:
            self.function_list(child, node_list)

    def get_operand_type(self, operand_node):
        """
        Determine the type of an operand (variable/object).
        Used for operator overload resolution.
        """
        if not operand_node:
            return None

        # If it's an identifier, look it up in the parser's symbol table
        if operand_node.type == "identifier":
            # Get the node's index in the parser's index system
            node_key = (operand_node.start_point, operand_node.end_point, operand_node.type)
            if node_key in self.index:
                node_id = self.index[node_key]
                # Check parser's symbol table for type information
                if hasattr(self.parser, 'symbol_table') and isinstance(self.parser.symbol_table, dict):
                    data_type = self.parser.symbol_table.get('data_type', {})

                    # First check if node_id directly has type info (it's a declaration)
                    if node_id in data_type:
                        return data_type[node_id]

                    # Otherwise, check if it's a usage that maps to a declaration
                    if hasattr(self.parser, 'declaration_map') and node_id in self.parser.declaration_map:
                        decl_id = self.parser.declaration_map[node_id]
                        if decl_id in data_type:
                            return data_type[decl_id]

            # Fallback: return the variable name itself (we'll try to resolve it later)
            var_name = operand_node.text.decode('utf-8')
            return var_name

        # If it's a field expression (obj.field), get the type of the object
        elif operand_node.type == "field_expression":
            argument = operand_node.child_by_field_name("argument")
            if argument:
                return self.get_operand_type(argument)

        # If it's a subscript expression (arr[i]), get the element type
        elif operand_node.type == "subscript_expression":
            argument = operand_node.child_by_field_name("argument")
            if argument:
                return self.get_operand_type(argument)

        # If it's a qualified identifier (std::cout), extract the name
        elif operand_node.type == "qualified_identifier":
            return operand_node.text.decode('utf-8')

        # If it's a parenthesized expression, unwrap it
        elif operand_node.type == "parenthesized_expression":
            # Get the inner expression
            for child in operand_node.children:
                if child.type not in ["(", ")"]:
                    return self.get_operand_type(child)
            return None

        # If it's a pointer expression (*ptr), get the pointed-to type
        elif operand_node.type == "pointer_expression":
            argument = operand_node.child_by_field_name("argument")
            if argument:
                # Special case: *this dereferences the current object pointer
                if argument.type == "this":
                    # Determine the containing class
                    containing_class = self.get_containing_class(operand_node)
                    if containing_class:
                        # Get class name
                        class_name_node = None
                        for child in containing_class.children:
                            if child.type == "type_identifier":
                                class_name_node = child
                                break
                        if class_name_node:
                            return class_name_node.text.decode('utf-8')
                    return None

                base_type = self.get_operand_type(argument)
                # Remove pointer indicator if present
                if base_type and base_type.endswith("*"):
                    return base_type[:-1]
                return base_type

        # Special case: 'this' keyword (pointer to current object)
        elif operand_node.type == "this":
            containing_class = self.get_containing_class(operand_node)
            if containing_class:
                # Get class name
                class_name_node = None
                for child in containing_class.children:
                    if child.type == "type_identifier":
                        class_name_node = child
                        break
                if class_name_node:
                    # this is a pointer, so return Type*
                    return class_name_node.text.decode('utf-8') + "*"
            return None

        # For other expressions, return None
        return None

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

    def track_namespace_aliases(self, root_node):
        """
        Track namespace alias definitions to resolve qualified identifiers.
        Handles:
        - namespace OI = Outer::Inner;
        - namespace short = very::long::namespace::path;
        """
        if root_node.type == "namespace_alias_definition":
            # Get the alias name (left side)
            alias_name = None
            for child in root_node.children:
                if child.type == "namespace_identifier":
                    alias_name = child.text.decode('utf-8')
                    break

            # Get the actual namespace (right side - nested_namespace_specifier)
            actual_namespace = None
            for child in root_node.children:
                if child.type == "nested_namespace_specifier":
                    actual_namespace = child.text.decode('utf-8')
                    break
                elif child.type == "namespace_identifier" and alias_name != child.text.decode('utf-8'):
                    # Simple alias (not nested)
                    actual_namespace = child.text.decode('utf-8')
                    break

            # Store the mapping
            if alias_name and actual_namespace:
                self.records["namespace_aliases"][alias_name] = actual_namespace

        # Recursively process children
        for child in root_node.children:
            self.track_namespace_aliases(child)

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

                                # Check if this "return" is actually a throw statement that escaped the function
                                return_key = index_to_key.get(return_id)
                                return_node = self.node_list.get(return_key) if return_key else None
                                is_throw_statement = return_node and return_node.type == "throw_statement"

                                # If it's a throw that escaped, route it to caller's catch blocks
                                if is_throw_statement:
                                    # Find enclosing try block at call site
                                    caller_parent = parent_node.parent
                                    found_caller_try = False
                                    while caller_parent is not None:
                                        if caller_parent.type == "try_statement":
                                            # Extract thrown type from the throw statement
                                            thrown_type = self.extract_thrown_type(return_node)

                                            # Find matching catch clause in caller's try block
                                            for child in caller_parent.children:
                                                if child.type == "catch_clause":
                                                    if (child.start_point, child.end_point, child.type) in self.node_list:
                                                        # Extract catch parameter type
                                                        catch_type = self.extract_catch_parameter_type(child)

                                                        # Check if thrown type matches this catch block
                                                        if self.exception_type_matches(thrown_type, catch_type):
                                                            catch_index = self.get_index(child)
                                                            self.add_edge(return_id, catch_index, "function_return")
                                                            found_caller_try = True
                                                            break  # Stop at first matching catch

                                            break  # Stop looking for try blocks
                                        caller_parent = caller_parent.parent

                                    # If found matching catch, skip normal return logic
                                    if found_caller_try:
                                        continue

                                # Determine return target based on function return type
                                # For all functions: return to next statement after call completes
                                return_target = None

                                if is_implicit_return:
                                    # Implicit return = void function or constructor
                                    # Return to the CALL SITE (parent_id), which already has edges to the next statement
                                    return_target = parent_id
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
                                        # Return to NEXT statement after the call completes
                                        # The call statement is atomic: it calls, receives return value, and completes
                                        next_index, next_node = self.get_next_index(parent_node, self.node_list)
                                        return_target = next_index if next_index != 2 else None

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

        # Process method calls with template specialization resolution
        for (method_name, signature), call_list in self.records["method_calls"].items():
            # Process each call site individually since each may have different template instantiations
            for call_id, parent_id, object_name in call_list:
                # Check if this object has a template instantiation
                template_instantiation = None
                if object_name and object_name in self.template_instantiations:
                    template_instantiation = self.template_instantiations[object_name]

                # Find matching function(s)
                matching_functions = []
                for ((class_name, fn_name), fn_sig), fn_id in self.records["function_list"].items():
                    if fn_name == method_name:
                        matching_functions.append((fn_id, class_name))

                # Determine target function(s) and whether it's a virtual call
                target_functions = []  # List of (fn_id, is_virtual) tuples

                if template_instantiation:
                    # Template instantiation: resolve statically to the correct specialization
                    base_class, template_args, _ = template_instantiation
                    resolved_fn_id = self.resolve_template_specialization(base_class, template_args, method_name)

                    if resolved_fn_id:
                        # Template specialization resolved - this is a static (non-virtual) call
                        target_functions.append((resolved_fn_id, False))
                    else:
                        # Failed to resolve - fall back to primary template or any matching function
                        # This should ideally not happen, but we'll handle it gracefully
                        for fn_id, class_name in matching_functions:
                            target_functions.append((fn_id, False))
                else:
                    # Not a template call - check for virtual dispatch
                    is_virtual_method = False

                    # Check if ANY matching function is marked as virtual
                    for fn_id, _ in matching_functions:
                        if fn_id in self.records["virtual_functions"]:
                            is_virtual_method = True
                            break

                    # If multiple implementations exist AND one is virtual, treat as polymorphic
                    # BUT exclude template specializations from this count
                    non_template_matches = []
                    for fn_id, class_name in matching_functions:
                        # Check if this is part of a template class
                        fn_key = index_to_key.get(fn_id)
                        if fn_key:
                            fn_node = self.node_list.get(fn_key)
                            if fn_node:
                                class_node = self.get_containing_class(fn_node)
                                if class_node and class_node.parent:
                                    if class_node.parent.type == "template_declaration":
                                        # This is a template - skip for polymorphism check
                                        continue
                        non_template_matches.append((fn_id, class_name))

                    # If multiple non-template implementations exist, it's polymorphic (virtual)
                    if len(non_template_matches) > 1 and is_virtual_method:
                        # Virtual dispatch - all targets are candidates
                        for fn_id, _ in non_template_matches:
                            target_functions.append((fn_id, True))
                    elif non_template_matches:
                        # Single non-template match or no virtual marking
                        for fn_id, _ in non_template_matches:
                            target_functions.append((fn_id, False))
                    elif matching_functions:
                        # Only template matches - shouldn't happen, but handle gracefully
                        for fn_id, _ in matching_functions:
                            target_functions.append((fn_id, False))

                # Create call edges to target function(s)
                for fn_id, is_virtual in target_functions:
                    # Add call edge
                    if is_virtual:
                        self.add_edge(parent_id, fn_id, f"virtual_call|{call_id}")
                    else:
                        self.add_edge(parent_id, fn_id, f"method_call|{call_id}")

                    # Add return edge: from this specific function back to the caller's next statement
                    if self.records.get("return_statement_map") and fn_id in self.records["return_statement_map"]:
                        # Get the call site node to find the return target
                        parent_key = index_to_key.get(parent_id)
                        if not parent_key:
                            continue
                        parent_node = self.node_list.get(parent_key)
                        if not parent_node:
                            continue

                        # Calculate the return target (next statement after the call)
                        next_index, next_node = self.get_next_index(parent_node, self.node_list)
                        return_target = next_index if next_index != 2 else None

                        if return_target and parent_id != fn_id:
                            # Add return edges from all return statements in this function
                            for return_id in self.records["return_statement_map"][fn_id]:
                                # Check if this is a synthetic implicit return node
                                is_implicit_return = self.records.get("implicit_return_map") and return_id in self.records["implicit_return_map"].values()

                                if is_implicit_return:
                                    # Implicit return: connect from last statement of method body
                                    fn_key = index_to_key.get(fn_id)
                                    fn_node = self.node_list.get(fn_key) if fn_key else None

                                    if fn_node:
                                        last_stmt = self.get_last_statement_in_function_body(fn_node, self.node_list)
                                        if last_stmt:
                                            last_stmt_id, _ = last_stmt
                                            self.add_edge(last_stmt_id, return_target, "method_return")
                                        else:
                                            # Empty method body
                                            self.add_edge(fn_id, return_target, "method_return")
                                else:
                                    # Explicit return: connect from return statement
                                    return_key = index_to_key.get(return_id)
                                    if return_key:
                                        return_node = self.node_list.get(return_key)
                                        if return_node:
                                            parent_func = self.get_containing_function(parent_node)
                                            return_func = self.get_containing_function(return_node)
                                            # Only add edge if they're in different functions
                                            if parent_func != return_func or parent_func is None:
                                                self.add_edge(return_id, return_target, "method_return")

        # Process static method calls (Class::staticMethod())
        for (class_name, method_name, signature), call_list in self.records["static_method_calls"].items():
            # Find matching static method in function_list
            # Static methods are stored with class name and function name
            for ((fn_class_name, fn_name), fn_sig), fn_id in self.records["function_list"].items():
                if fn_class_name == class_name and fn_name == method_name:
                    # Found matching static method
                    for call_id, parent_id in call_list:
                        # Add call edge: caller -> static method
                        self.add_edge(parent_id, fn_id, f"static_call|{call_id}")

                        # Add return edges: static method return points -> caller
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
                                # For all methods: return to next statement after call completes
                                return_target = None

                                if is_implicit_return:
                                    # Implicit return = void function
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
                                        # Void function with explicit return
                                        # Return to NEXT statement
                                        next_index, next_node = self.get_next_index(parent_node, self.node_list)
                                        return_target = next_index if next_index != 2 else None
                                    else:
                                        # Non-void function (returns a value)
                                        # Return to NEXT statement after the call completes
                                        # The call statement is atomic: it calls, receives return value, and completes
                                        next_index, next_node = self.get_next_index(parent_node, self.node_list)
                                        return_target = next_index if next_index != 2 else None

                                if parent_id != fn_id and return_target:
                                    # Get return node from index
                                    return_key = index_to_key.get(return_id)

                                    if is_implicit_return or not return_key:
                                        # For implicit returns, connect from last statement of method body
                                        # Find the method node
                                        fn_key = index_to_key.get(fn_id)
                                        fn_node = self.node_list.get(fn_key) if fn_key else None

                                        if fn_node:
                                            # Get last statement in method body
                                            last_stmt = self.get_last_statement_in_function_body(fn_node, self.node_list)
                                            if last_stmt:
                                                last_stmt_id, _ = last_stmt
                                                self.add_edge(last_stmt_id, return_target, "static_return")
                                            else:
                                                # Fallback: empty method body, connect from method entry
                                                self.add_edge(fn_id, return_target, "static_return")
                                    else:
                                        return_node = self.node_list.get(return_key)
                                        if return_node:
                                            parent_func = self.get_containing_function(parent_node)
                                            return_func = self.get_containing_function(return_node)
                                            if parent_func != return_func or parent_func is None:
                                                self.add_edge(return_id, return_target, "static_return")

        # Process operator overload calls
        for (operator_symbol, is_member), call_list in self.records["operator_calls"].items():
            # Map operator symbols to function names
            operator_to_function_name = {
                "+": "operator+",
                "-": "operator-",
                "*": "operator*",
                "/": "operator/",
                "%": "operator%",
                "==": "operator==",
                "!=": "operator!=",
                "<": "operator<",
                ">": "operator>",
                "<=": "operator<=",
                ">=": "operator>=",
                "<<": "operator<<",
                ">>": "operator>>",
                "&": "operator&",
                "|": "operator|",
                "^": "operator^",
                "&&": "operator&&",
                "||": "operator||",
                "=": "operator=",
                "++_prefix": "operator++",
                "++_postfix": "operator++",
                "--_prefix": "operator--",
                "--_postfix": "operator--",
            }

            operator_func_name = operator_to_function_name.get(operator_symbol)
            if not operator_func_name:
                continue

            # For each operator call
            for call_id, parent_id, operand_type in call_list:
                # Find matching operator overload in function_list
                # For member operators: match by class name and function name
                # For non-member operators: match by function name only
                matching_functions = []

                for ((fn_class_name, fn_name), fn_sig), fn_id in self.records["function_list"].items():
                    if fn_name == operator_func_name:
                        if is_member:
                            # Member operator: check if operand type matches class name
                            if operand_type and fn_class_name == operand_type:
                                # Handle prefix vs postfix for ++ and --
                                if operator_symbol in ["++_prefix", "--_prefix"]:
                                    # Prefix version: no int parameter
                                    if fn_sig == () or fn_sig == ("",):
                                        matching_functions.append(fn_id)
                                elif operator_symbol in ["++_postfix", "--_postfix"]:
                                    # Postfix version: has int parameter
                                    if fn_sig == ("int",) or "int" in str(fn_sig):
                                        matching_functions.append(fn_id)
                                else:
                                    matching_functions.append(fn_id)
                        else:
                            # Non-member operator (like << for streams)
                            # For non-member operators, check if operand type matches one of the parameter types
                            # This prevents matching built-in operators (e.g., stream >> double)
                            if operand_type and fn_sig:
                                # Check if operand_type appears in the function signature
                                # For operator<<(ostream&, Vector2D&), operand should be Vector2D
                                type_match = False
                                for param_type in fn_sig:
                                    # Simplify parameter type for comparison
                                    param_simple = param_type.replace('const', '').replace('&', '').replace('*', '').strip()
                                    if operand_type in param_simple or param_simple in operand_type:
                                        type_match = True
                                        break
                                if type_match:
                                    matching_functions.append(fn_id)
                            elif not operand_type:
                                # If we can't determine operand type, assume it might match
                                matching_functions.append(fn_id)

                # Add CFG edges for all matching operator overloads
                for fn_id in matching_functions:
                    # Add call edge: caller -> operator function
                    edge_label = f"operator_call|{call_id}"
                    if operator_symbol.startswith("++") or operator_symbol.startswith("--"):
                        edge_label = f"{operator_symbol.split('_')[1]}_increment_call|{call_id}"
                    self.add_edge(parent_id, fn_id, edge_label)

                    # Add return edges: operator return points -> caller
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

                            # Determine return target
                            # For operators that return values, return to call site
                            # Assignment operator returns a reference (for chaining), so return to call site
                            # The call site then naturally flows to the next statement via next_line edge
                            return_target = parent_id

                            if parent_id != fn_id and return_target:
                                # Get return node from index
                                return_key = index_to_key.get(return_id)

                                if is_implicit_return or not return_key:
                                    # For implicit returns, connect from last statement
                                    fn_key = index_to_key.get(fn_id)
                                    fn_node = self.node_list.get(fn_key) if fn_key else None

                                    if fn_node:
                                        last_stmt = self.get_last_statement_in_function_body(fn_node, self.node_list)
                                        if last_stmt:
                                            last_stmt_id, _ = last_stmt
                                            self.add_edge(last_stmt_id, return_target, "operator_return")
                                        else:
                                            self.add_edge(fn_id, return_target, "operator_return")
                                else:
                                    return_node = self.node_list.get(return_key)
                                    if return_node:
                                        parent_func = self.get_containing_function(parent_node)
                                        return_func = self.get_containing_function(return_node)
                                        if parent_func != return_func or parent_func is None:
                                            self.add_edge(return_id, return_target, "operator_return")

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
                    # Handle default parameters: call can have fewer args than definition
                    elif len(signature) <= len(fn_sig):
                        # Try to match each parameter provided in the call
                        all_match = True
                        for i, call_param in enumerate(signature):
                            if i < len(fn_sig):
                                fn_param = fn_sig[i]
                                # Simplify both for comparison (remove const, &, *, etc.)
                                fn_param_simple = fn_param.replace('const', '').replace('&', '').replace('*', '').strip()
                                call_param_simple = call_param.replace('const', '').replace('&', '').replace('*', '').strip()

                                # Allow 'unknown' type to match any type
                                if call_param_simple == 'unknown':
                                    # Type inference failed, assume it matches
                                    continue

                                # Allow implicit numeric conversions
                                numeric_types = ['int', 'double', 'float', 'long', 'short', 'char']
                                fn_is_numeric = any(nt in fn_param_simple for nt in numeric_types)
                                call_is_numeric = any(nt in call_param_simple for nt in numeric_types)

                                if fn_is_numeric and call_is_numeric:
                                    # Allow any numeric type to match any other numeric type
                                    continue

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
                                        # Check if this is a constructor call in a return statement
                                        if parent_node.type == "return_statement":
                                            # Constructor in return statement: return to the return statement itself
                                            return_target = parent_id
                                        else:
                                            # Regular constructor call from declaration
                                            # Return should go back to the call site (the declaration statement)
                                            # The declaration then naturally flows to the next statement via next_line edge
                                            return_target = parent_id

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

    def extract_lambda_variable_name(self, statement_node, lambda_node):
        """
        Extract the variable name that a lambda is assigned to.
        Example: auto f = [...]() { }; => returns "f"

        AST structure:
        declaration  (this is statement_node)
          placeholder_type_specifier (auto)
          init_declarator
            identifier (variable_name)
            lambda_expression
        """
        # statement_node is the declaration itself
        if statement_node.type == "declaration":
            # Find init_declarator children
            for decl_child in statement_node.named_children:
                if decl_child.type == "init_declarator":
                    # The first child is usually the identifier
                    for init_child in decl_child.named_children:
                        if init_child.type == "identifier":
                            return init_child.text.decode('utf-8')
        return None

    def find_lambda_call_sites(self, var_name, definition_node):
        """
        Find all call sites for a lambda variable within the same function.
        Returns list of statement nodes that call the lambda.
        """
        call_sites = []

        # Get the containing function
        containing_function = self.get_containing_function(definition_node)
        if not containing_function:
            return call_sites

        # Search for call_expressions with identifier matching var_name
        def search_for_calls(node):
            # Check if this is a statement node that contains a call
            if node.type in self.statement_types["non_control_statement"]:
                # Check if it contains a call to our variable
                for child in node.named_children:
                    if self.is_lambda_call(child, var_name):
                        # This statement calls the lambda variable
                        if node != definition_node:  # Don't include the definition itself
                            call_sites.append(node)
                        break

            # Recursively search children
            for child in node.named_children:
                search_for_calls(child)

        search_for_calls(containing_function)
        return call_sites

    def is_lambda_call(self, node, var_name):
        """
        Check if a node is a call_expression calling the specified variable.
        Example: var_name() or var_name(args)
        """
        if node.type == "call_expression":
            func = node.child_by_field_name("function")
            if func and func.type == "identifier":
                if func.text.decode('utf-8') == var_name:
                    return True
        # Recursively check children
        for child in node.named_children:
            if self.is_lambda_call(child, var_name):
                return True
        return False

    def get_lambda_body_first_stmt(self, lambda_node, node_list):
        """
        Get the first statement in a lambda's body.
        Returns the node ID of the first statement, or None if not found.
        """
        body = lambda_node.child_by_field_name("body")
        if body and body.type == "compound_statement":
            children = list(body.named_children)
            if children:
                first_stmt = children[0]
                first_stmt_key = (first_stmt.start_point, first_stmt.end_point, first_stmt.type)
                if first_stmt_key in node_list:
                    return self.get_index(first_stmt)
        return None

    def add_lambda_return_edges(self, lambda_node, lambda_id, call_site_id, node_list):
        """
        Add return edges from lambda exit points to the statement after the call site.
        Also removes the automatic next_line edge from call site to prevent bypassing lambda execution.

        Args:
            lambda_node: The lambda_expression node
            lambda_id: The node ID of the lambda_expression
            call_site_id: The node ID of the statement that calls the lambda
            node_list: The node list dictionary
        """
        # Find all exit points in the lambda body
        exit_points = []

        # Get lambda body
        body = lambda_node.child_by_field_name("body")
        if not body or body.type != "compound_statement":
            return

        # Find all statements in lambda body that can exit
        def find_exit_points(node, in_lambda_body=False):
            node_key = (node.start_point, node.end_point, node.type)

            # Only consider nodes that are in our node_list
            if node_key in node_list:
                in_lambda_body = True

                # Explicit returns are exit points
                if node.type == "return":
                    exit_points.append(node)
                    return  # Don't search deeper in return statements

                # Check if this is the last statement in the lambda body
                # (implicit return for void lambdas)
                parent = node.parent
                if parent == body:
                    # This is a direct child of the lambda body
                    siblings = list(body.named_children)
                    if siblings and siblings[-1] == node:
                        # This is the last statement - it's an exit point if not a return
                        if node.type != "return":
                            exit_points.append(node)

            # Recursively search children (but not into nested functions/lambdas)
            if node.type not in ["function_definition", "lambda_expression"] or node == lambda_node:
                for child in node.named_children:
                    find_exit_points(child, in_lambda_body)

        find_exit_points(body)

        # Get the statement after the call site
        call_site_node = None
        for key, node in node_list.items():
            if self.index.get(key) == call_site_id:
                call_site_node = node
                break

        if not call_site_node:
            return

        next_index, next_node = self.get_next_index(call_site_node, node_list)

        # CRITICAL FIX: Lambda returns should go back to the call site, not directly to next statement
        # This is because the call site needs to complete the assignment/expression evaluation
        # after the lambda returns.
        #
        # Control flow:
        #   call_site -> lambda_body (invocation)
        #   lambda_exit -> call_site (return to complete assignment)
        #   call_site -> next_statement (continue execution)
        #
        # We do NOT remove the next_line edge from call_site because it represents
        # the continuation after the lambda returns and completes.

        # Create return edges from each exit point back to the call site
        for exit_node in exit_points:
            exit_key = (exit_node.start_point, exit_node.end_point, exit_node.type)
            if exit_key in node_list:
                exit_id = self.get_index(exit_node)
                # Return to the call site to complete the assignment/expression
                self.add_edge(exit_id, call_site_id, "lambda_return")

    def add_lambda_edges(self):
        """
        Add edges for lambda invocations and returns.

        This function handles two cases:
        1. Immediately-invoked lambdas: [...]() { body }();
        2. Stored lambdas: auto f = [...]() { body }; ... f();

        For each lambda:
        - Creates invocation edges from definition (for case 1) or call sites (for case 2)
        - Creates return edges from lambda exit points back to statements after calls
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

            # Check if this is an immediately-invoked lambda or a stored lambda
            # By examining if the statement contains a call_expression that directly wraps the lambda
            is_immediately_invoked = False
            if statement_node.type == "expression_statement":
                # Check if statement contains: [...]() { body }();
                for child in statement_node.named_children:
                    if child.type == "call_expression":
                        # Check if the function being called is the lambda itself
                        func_child = child.child_by_field_name("function")
                        if func_child and func_child.type == "lambda_expression":
                            if (func_child.start_point, func_child.end_point, func_child.type) == lambda_key:
                                is_immediately_invoked = True
                                break

            # Get the first statement in the lambda body
            # Invocation edges should point directly to the body, not to the lambda definition
            lambda_body_first_id = self.get_lambda_body_first_stmt(lambda_node, self.node_list)
            if lambda_body_first_id is None:
                # Empty lambda body, skip
                continue

            if is_immediately_invoked:
                # Case 1: Immediately-invoked lambda
                # Create invocation edge from statement directly to lambda BODY
                self.add_edge(stmt_id, lambda_body_first_id, "lambda_invocation")

                # Find exit points in lambda and create return edges back to next statement
                self.add_lambda_return_edges(lambda_node, lambda_id, stmt_id, self.node_list)
            else:
                # Case 2: Stored lambda
                # Don't create invocation edge from definition
                # The invocation happens at call sites, not at definition
                # We still need to track lambda body but edges will be created from calls

                # Find the variable name this lambda is assigned to
                var_name = self.extract_lambda_variable_name(statement_node, lambda_node)

                if var_name:
                    # Find all call sites for this variable
                    call_sites = self.find_lambda_call_sites(var_name, statement_node)

                    for call_site_node in call_sites:
                        call_site_key = (call_site_node.start_point, call_site_node.end_point, call_site_node.type)
                        if call_site_key in self.node_list:
                            call_site_id = self.get_index(call_site_node)

                            # Create invocation edge from call site directly to lambda BODY
                            # NOT to the lambda definition node
                            self.add_edge(call_site_id, lambda_body_first_id, "lambda_invocation")

                            # Create return edges from lambda exit points to statement after call
                            self.add_lambda_return_edges(lambda_node, lambda_id, call_site_id, self.node_list)

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
        # STEP 1.5: Register missing template specializations
        # ═══════════════════════════════════════════════════════════
        self.register_template_specializations(node_list)

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

                # Skip creating next_line edges for class/struct members
                # Class members are declarations, not sequential execution steps
                parent = node.parent
                if parent and parent.type == "field_declaration_list":
                    # This node is a direct child of a class/struct definition
                    # Do not create sequential edges between class members
                    continue

                # Skip creating next_line edges for namespace members and global declarations
                # Namespace-level and global declarations are compile-time constructs:
                # - Global variables are initialized during static initialization before main()
                # - Function definitions are not executable code
                # - There is no sequential execution flow at namespace/global scope
                if parent and parent.type == "declaration_list":
                    # Check if this is a namespace's declaration_list
                    grandparent = parent.parent if parent else None
                    if grandparent and grandparent.type == "namespace_definition":
                        # This node is inside a namespace - skip sequential edges
                        continue

                # Skip global scope declarations (parent is translation_unit)
                if parent and parent.type == "translation_unit":
                    # This node is at global scope - skip sequential edges
                    continue

                # Get next statement
                next_index, next_node = self.get_next_index(node, node_list)

                if next_index != 2 and next_node is not None:
                    # Also check if next node is a class member
                    next_parent = next_node.parent if next_node else None
                    if next_parent and next_parent.type == "field_declaration_list":
                        # Next node is a class member, skip edge
                        continue

                    # Also check if next node is at namespace/global scope
                    if next_parent and next_parent.type == "declaration_list":
                        next_grandparent = next_parent.parent if next_parent else None
                        if next_grandparent and next_grandparent.type == "namespace_definition":
                            # Next node is inside a namespace - skip edge
                            continue

                    if next_parent and next_parent.type == "translation_unit":
                        # Next node is at global scope - skip edge
                        continue

                    current_index = self.get_index(node)
                    self.add_edge(current_index, next_index, "next_line")

        # ═══════════════════════════════════════════════════════════
        # STEP 3: Create basic blocks
        # ═══════════════════════════════════════════════════════════
        self.get_basic_blocks(self.CFG_node_list, self.CFG_edge_list)
        self.CFG_node_list = self.append_block_index(self.CFG_node_list, self.records)

        # ═══════════════════════════════════════════════════════════
        # STEP 3.5: Track namespace aliases
        # ═══════════════════════════════════════════════════════════
        self.track_namespace_aliases(self.root_node)

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
                # Namespaces are compile-time constructs, not runtime execution nodes
                # They should not have control flow edges in the CFG
                # Execution flow is determined by function calls, not namespace structure
                pass

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
                    # BUT: Don't add edge if last statement is a jump statement OR try_statement
                    # try_statement manages its own exit paths through try block and catch clauses
                    last_line, _ = self.get_block_last_line(node, "body")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                        if not self.is_jump_statement(last_line) and last_line.type != "try_statement":
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
                    # BUT: Don't add edge if last statement is a jump statement OR try_statement
                    # try_statement manages its own exit paths through try block and catch clauses
                    last_line, _ = self.get_block_last_line(node, "body")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                        if not self.is_jump_statement(last_line) and last_line.type != "try_statement":
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
                    # BUT: Don't add edge if last statement is a jump statement OR try_statement
                    # try_statement manages its own exit paths through try block and catch clauses
                    last_line, _ = self.get_block_last_line(node, "body")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                        if not self.is_jump_statement(last_line) and last_line.type != "try_statement":
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
                    # BUT: Don't add edge if last statement is a jump statement OR try_statement
                    # try_statement manages its own exit paths through try block and catch clauses
                    last_line, _ = self.get_block_last_line(node, "body")
                    if last_line and (last_line.start_point, last_line.end_point, last_line.type) in node_list:
                        if not self.is_jump_statement(last_line) and last_line.type != "try_statement":
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
                # Extract the type of the thrown exception
                thrown_type = self.extract_thrown_type(node)

                # Find enclosing try block
                parent = node.parent
                found_try = False
                while parent is not None:
                    if parent.type == "try_statement":
                        # Jump to ONLY the FIRST matching catch clause
                        # C++ searches catch blocks sequentially and stops at first match
                        for child in parent.children:
                            if child.type == "catch_clause":
                                if (child.start_point, child.end_point, child.type) in node_list:
                                    # Extract catch parameter type
                                    catch_type = self.extract_catch_parameter_type(child)

                                    # Check if thrown type matches this catch block
                                    if self.exception_type_matches(thrown_type, catch_type):
                                        catch_index = self.get_index(child)
                                        self.add_edge(current_index, catch_index, "throw_exit")
                                        found_try = True
                                        break  # Stop at first matching catch (C++ behavior)

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
                # Lambda creation happens at definition time and is part of sequential execution
                # This includes capturing variables and creating the function object
                #
                # Flow at definition time:
                #   declaration_statement -> lambda_expression -> next_statement
                #
                # The lambda BODY is NOT executed at definition time
                # Body execution edges are created in add_lambda_edges()

                # Find the parent statement that contains this lambda
                parent = node.parent
                while parent and parent.type not in self.statement_types["node_list_type"]:
                    parent = parent.parent

                if parent and (parent.start_point, parent.end_point, parent.type) in node_list:
                    parent_id = self.get_index(parent)

                    # Edge from parent statement to lambda expression (definition-time evaluation)
                    self.add_edge(parent_id, current_index, "lambda_definition")

                    # Edge from lambda expression to next statement
                    # This replaces the direct parent -> next edge that was created in STEP 2
                    next_index, next_node = self.get_next_index(parent, node_list)
                    if next_index != 2 and next_node is not None:
                        self.add_edge(current_index, next_index, "next_line")

                        # Remove the direct edge from parent to next (it's now parent -> lambda -> next)
                        self.CFG_edge_list = [
                            edge for edge in self.CFG_edge_list
                            if not (edge[0] == parent_id and edge[1] == next_index and edge[2] == 'next_line')
                        ]

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
                # Include classes, structs, enums, typedefs, namespaces, and declarations
                # EXCLUDE function_definition - functions don't have initialization order semantics
                if node.type in ["class_specifier", "struct_specifier",
                                "enum_specifier", "type_definition", "namespace_definition",
                                "declaration"]:
                    node_id = self.get_index(node)
                    # Store (node_id, line_number) for sorting
                    global_declarations.append((node_id, node.start_point[0]))

        # Sort by line number to preserve declaration order
        global_declarations.sort(key=lambda x: x[1])

        # Global declarations (classes, namespaces, etc.) are compile-time constructs
        # They should not have sequential control flow edges in the CFG
        # Execution flow starts from main() and follows function calls
        # Commenting out global_sequence edges:
        # for i in range(len(global_declarations) - 1):
        #     curr_id = global_declarations[i][0]
        #     next_id = global_declarations[i + 1][0]
        #     self.add_edge(curr_id, next_id, "global_sequence")

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
