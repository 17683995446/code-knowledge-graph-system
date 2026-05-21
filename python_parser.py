"""
Python Parser Module
Implements the CodeParser interface for Python using tree-sitter.
"""

import os
import threading
from typing import Optional
from parser_interface import (
    CodeParser, ParseResult, TypeInfo, FunctionInfo,
    CallInfo, ReferenceInfo, register_parser
)

from logging_config import get_logger

logger = get_logger(__name__)

# Try to import tree-sitter, fallback to regex if not available
try:
    from tree_sitter import Language, Parser
    from tree_sitter_python import language as python_language
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    import re


class PythonParser(CodeParser):
    """Parser for Python source code."""
    
    def __init__(self):
        # Use thread-local storage for tree-sitter parser (not thread-safe)
        self._thread_local = threading.local()
        if TREE_SITTER_AVAILABLE:
            self._initialize_parser()
    
    def _get_parser(self):
        """Get or create a thread-local parser instance."""
        if not hasattr(self._thread_local, 'parser') or self._thread_local.parser is None:
            try:
                self._thread_local.parser = Parser(python_language)
            except Exception as error:
                print(f"Failed to initialize tree-sitter parser: {error}")
                self._thread_local.parser = None
        return self._thread_local.parser
    
    def _initialize_parser(self):
        """Initialize the tree-sitter parser for the current thread."""
        self._get_parser()
    
    @property
    def _parser(self):
        """Property accessor for backward compatibility."""
        return self._get_parser()
    
    @property
    def supported_extensions(self) -> list:
        """Return Python file extensions."""
        return ['.py', '.pyw']
    
    @property
    def language_name(self) -> str:
        """Return language name."""
        return 'python'
    
    def parse_file(self, file_path: str, source_code: Optional[str] = None) -> ParseResult:
        """
        Parse a Python file and extract code structure.
        
        Args:
            file_path: Path to the Python file
            source_code: Optional pre-read source code
        
        Returns:
            ParseResult with extracted types, functions, calls, and references
        """
        logger.debug("Parsing file: %s", file_path)
        result = ParseResult()
        
        # Read source code if not provided
        if source_code is None:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    source_code = file.read()
            except Exception as error:
                logger.error("Failed to read file %s: %s", file_path, error)
                result.errors.append(f"Failed to read file: {error}")
                return result
        
        # Use tree-sitter if available, otherwise fallback
        if TREE_SITTER_AVAILABLE and self._parser:
            logger.debug("Using tree-sitter parser")
            result = self._parse_with_tree_sitter(source_code, file_path)
        else:
            logger.debug("Falling back to regex parser")
            result = self._parse_with_regex(source_code, file_path)
        
        logger.debug("Parse result: %d types, %d functions, %d calls",
                     len(result.types), len(result.functions), len(result.calls))
        return result
    
    def _parse_with_tree_sitter(self, source_code: str, file_path: str) -> ParseResult:
        """Parse using tree-sitter for accurate AST analysis."""
        result = ParseResult()
        
        try:
            tree = self._parser.parse(source_code.encode('utf-8'))
            root_node = tree.root_node
            
            # Extract classes and functions
            self._extract_python_entities(root_node, source_code, result, None)
            
            # Extract imports
            self._extract_imports(root_node, source_code, result)
            
            logger.debug("Tree-sitter parse successful")
            
        except Exception as error:
            logger.warning("Tree-sitter parse failed: %s, falling back to regex", error)
            result.errors.append(f"Tree-sitter parsing error: {error}")
            # Fallback to regex
            return self._parse_with_regex(source_code, file_path)
        
        return result
    
    def _extract_python_entities(self, node, source_code: str, result: ParseResult, 
                                  current_class: Optional[str]):
        """Recursively extract classes and functions from AST."""
        for child in node.children:
            node_type = child.type
            
            if node_type == 'class_definition':
                class_info = self._parse_class_definition(child, source_code)
                if class_info:
                    result.types.append(class_info)
                    # Recursively extract methods within class
                    self._extract_python_entities(child, source_code, result, class_info.name)
                    
                    # Extract inheritance
                    self._extract_inheritance(child, class_info.name, source_code, result)
                    
            elif node_type == 'function_definition':
                func_info = self._parse_function_definition(child, source_code, current_class)
                if func_info:
                    result.functions.append(func_info)
                    # Extract function calls within the function
                    self._extract_function_calls(child, func_info, source_code, result)
                    
            else:
                # Recurse into other nodes
                self._extract_python_entities(child, source_code, result, current_class)
    
    def _parse_class_definition(self, node, source_code: str) -> Optional[TypeInfo]:
        """Parse a class definition node."""
        try:
            name_node = None
            for child in node.children:
                if child.type == 'identifier':
                    name_node = child
                    break
            
            if name_node:
                name = source_code[name_node.start_byte:name_node.end_byte]
                return TypeInfo(
                    name=name,
                    kind='class',
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1
                )
        except Exception:
            pass
        return None
    
    def _parse_function_definition(self, node, source_code: str, 
                                   class_name: Optional[str]) -> Optional[FunctionInfo]:
        """Parse a function definition node."""
        try:
            name_node = None
            parameters_node = None
            
            for child in node.children:
                if child.type == 'identifier':
                    name_node = child
                elif child.type == 'parameters':
                    parameters_node = child
            
            if name_node:
                name = source_code[name_node.start_byte:name_node.end_byte]
                signature = ''
                if parameters_node:
                    signature = source_code[parameters_node.start_byte:parameters_node.end_byte]
                
                return FunctionInfo(
                    name=name,
                    type_name=class_name,
                    signature=signature,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1
                )
        except Exception:
            pass
        return None
    
    def _extract_inheritance(self, class_node, class_name: str, source_code: str, 
                             result: ParseResult):
        """Extract inheritance relationships from class definition."""
        try:
            for child in class_node.children:
                if child.type == 'argument_list':
                    for arg in child.children:
                        if arg.type == 'identifier':
                            parent_name = source_code[arg.start_byte:arg.end_byte]
                            if parent_name != 'object':
                                result.references.append(ReferenceInfo(
                                    from_name=class_name,
                                    from_kind='class',
                                    to_name=parent_name,
                                    to_kind='class',
                                    ref_kind='inherit',
                                    line_number=class_node.start_point[0] + 1
                                ))
        except Exception:
            pass
    
    def _extract_function_calls(self, func_node, func_info: FunctionInfo, 
                                source_code: str, result: ParseResult):
        """Extract function calls within a function."""
        try:
            for child in func_node.children:
                if child.type == 'call':
                    callee_name = self._get_call_name(child, source_code)
                    if callee_name:
                        result.calls.append(CallInfo(
                            caller_name=func_info.name,
                            caller_type=func_info.type_name,
                            callee_name=callee_name,
                            callee_type=None,
                            line_number=child.start_point[0] + 1
                        ))
                else:
                    self._extract_function_calls(child, func_info, source_code, result)
        except Exception:
            pass
    
    def _get_call_name(self, call_node, source_code: str) -> Optional[str]:
        """Extract the function name from a call node."""
        try:
            for child in call_node.children:
                if child.type == 'identifier':
                    return source_code[child.start_byte:child.end_byte]
                elif child.type == 'attribute':
                    # Handle method calls like obj.method()
                    return source_code[child.start_byte:child.end_byte]
        except Exception:
            pass
        return None
    
    def _extract_imports(self, root_node, source_code: str, result: ParseResult):
        """Extract import statements."""
        try:
            for child in root_node.children:
                if child.type in ('import_statement', 'import_from_statement'):
                    # Simplified import extraction
                    for subchild in child.children:
                        if subchild.type == 'dotted_name':
                            import_name = source_code[subchild.start_byte:subchild.end_byte]
                            result.references.append(ReferenceInfo(
                                from_name='__module__',
                                from_kind='module',
                                to_name=import_name,
                                to_kind='module',
                                ref_kind='import',
                                line_number=child.start_point[0] + 1
                            ))
        except Exception:
            pass
    
    def _parse_with_regex(self, source_code: str, file_path: str) -> ParseResult:
        """Fallback parser using regex for basic extraction."""
        result = ParseResult()
        lines = source_code.split('\n')
        
        current_class = None
        class_indent = 0  # Track the indentation level where the class was defined
        
        # Track whether we are inside a triple-quoted string (""" or ''')
        in_triple_quote = False
        triple_quote_char = None  # '"' or "'"
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip empty lines and comments FIRST (before triple-quote detection)
            if not stripped or stripped.startswith('#'):
                continue

            # Track triple-quoted string boundaries across lines.
            # We count occurrences of the opening/closing triple-quote on each line.
            # When in_triple_quote is False, the first occurrence opens a string;
            # when True, the first occurrence closes it.
            if not in_triple_quote:
                # Check for opening triple-quote
                if '"""' in line:
                    in_triple_quote = True
                    triple_quote_char = '"'
                    # If there is a closing triple-quote on the same line, toggle back
                    if line.count('"""') >= 2:
                        in_triple_quote = False
                        triple_quote_char = None
                    continue
                elif "'''" in line:
                    in_triple_quote = True
                    triple_quote_char = "'"
                    if line.count("'''") >= 2:
                        in_triple_quote = False
                        triple_quote_char = None
                    continue
            else:
                # We are inside a triple-quoted string; look for the closing quote
                close_marker = triple_quote_char * 3
                if close_marker in line:
                    in_triple_quote = False
                    triple_quote_char = None
                continue

            # Calculate current indentation level
            current_indent = len(line) - len(line.lstrip())
            
            # If we're inside a class and the indentation drops to or below the class level,
            # the class scope has ended
            if current_class is not None and current_indent <= class_indent:
                current_class = None
            
            # Match class definitions
            class_match = re.match(r'^class\s+(\w+)\s*(?:\(([^)]*)\))?:', stripped)
            if class_match:
                class_name = class_match.group(1)
                logger.debug("Regex parse: line %d: detected class '%s'", line_num, class_name)
                result.types.append(TypeInfo(
                    name=class_name,
                    kind='class',
                    line_start=line_num
                ))
                current_class = class_name
                class_indent = current_indent
                
                # Extract inheritance
                parents = class_match.group(2)
                if parents:
                    for parent in parents.split(','):
                        parent = parent.strip()
                        if parent and parent != 'object':
                            result.references.append(ReferenceInfo(
                                from_name=class_name,
                                from_kind='class',
                                to_name=parent,
                                to_kind='class',
                                ref_kind='inherit',
                                line_number=line_num
                            ))
            
            # Match function definitions
            func_match = re.match(r'^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)', stripped)
            if func_match:
                func_name = func_match.group(1)
                logger.debug("Regex parse: line %d: detected function '%s'", line_num, func_name)
                signature = f"({func_match.group(2)})"
                result.functions.append(FunctionInfo(
                    name=func_name,
                    type_name=current_class,
                    signature=signature,
                    line_start=line_num
                ))

            # Match imports (check early so we can skip call extraction on import lines)
            import_match = re.match(r'^(?:from\s+(\S+)\s+)?import\s+(.+)$', stripped)

            # Extract function calls within function/method bodies
            # Skip extraction on class/def/import lines
            is_definition_line = class_match or func_match or import_match
            if not is_definition_line:
                # Determine caller context
                caller_name = None
                caller_type = None
                if current_class is not None:
                    caller_type = current_class
                    # Only use _last_func_name if we're actually inside a method body
                    # Check that current indent is deeper than the method's indent
                    method_indent = getattr(result, '_method_indent', None)
                    if method_indent is not None and current_indent > method_indent:
                        caller_name = result._last_func_name
                elif hasattr(result, '_last_func_name'):
                    caller_name = result._last_func_name

                call_matches = re.finditer(
                    r'(?<!\w)([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)?)\s*\(',
                    stripped
                )
                for cm in call_matches:
                    call_expr = cm.group(1)
                    base_name = call_expr.split('.')[0]
                    skip_names = {
                        'if', 'else', 'elif', 'for', 'while', 'with', 'class',
                        'def', 'return', 'yield', 'raise', 'except', 'assert',
                        'print', 'len', 'range', 'str', 'int', 'float', 'list',
                        'dict', 'set', 'tuple', 'bool', 'type', 'isinstance',
                        'hasattr', 'getattr', 'setattr', 'super', 'property',
                        'staticmethod', 'classmethod', 'enumerate', 'zip',
                        'map', 'filter', 'sorted', 'reversed', 'any', 'all',
                        'min', 'max', 'sum', 'abs', 'round', 'open', 'input',
                        'format', 'repr', 'hash', 'id', 'dir', 'vars', 'hex',
                        'oct', 'bin', 'chr', 'ord', 'pow', 'divmod', 'iter',
                        'next', 'slice', 'object', 'Exception', 'ValueError',
                        'TypeError', 'KeyError', 'IndexError', 'AttributeError',
                        'RuntimeError', 'ImportError', 'FileNotFoundError',
                        'NotImplementedError', 'OSError', 'IOError',
                    }
                    if base_name in skip_names:
                        continue
                    if base_name in ('self', 'cls'):
                        continue
                    callee_name = call_expr.split('.')[-1] if '.' in call_expr else call_expr
                    logger.debug("Regex parse: line %d: detected call '%s'", line_num, callee_name)
                    result.calls.append(CallInfo(
                        caller_name=caller_name,
                        caller_type=caller_type,
                        callee_name=callee_name,
                        callee_type=None,
                        line_number=line_num
                    ))

            # Track last function name and its indent for call context
            if func_match:
                if not hasattr(result, '_last_func_name'):
                    result._last_func_name = None
                result._last_func_name = func_match.group(1)
                result._method_indent = current_indent
            elif current_class is None:
                # Module level - reset function context
                if not hasattr(result, '_last_func_name'):
                    result._last_func_name = None
                result._last_func_name = None
                if hasattr(result, '_method_indent'):
                    result._method_indent = None

            # Process imports
            if import_match:
                module = import_match.group(1) or import_match.group(2).split(',')[0].strip()
                result.references.append(ReferenceInfo(
                    from_name='__module__',
                    from_kind='module',
                    to_name=module,
                    to_kind='module',
                    ref_kind='import',
                    line_number=line_num
                ))
        
        return result


# Register the parser
python_parser = PythonParser()
register_parser(python_parser)


if __name__ == '__main__':
    # Test the parser
    test_code = '''
class Animal:
    def speak(self):
        pass

class Dog(Animal):
    def speak(self):
        return "Woof"
    
    def fetch(self):
        return "Fetching"

def main():
    dog = Dog()
    print(dog.speak())
'''
    
    parser = PythonParser()
    result = parser.parse_file("test.py", test_code)
    
    print(f"Types found: {len(result.types)}")
    for t in result.types:
        print(f"  - {t.kind}: {t.name}")
    
    print(f"\nFunctions found: {len(result.functions)}")
    for f in result.functions:
        print(f"  - {f.name} (in {f.type_name or 'module'})")
    
    print(f"\nReferences found: {len(result.references)}")
    for r in result.references:
        print(f"  - {r.from_name} {r.ref_kind}s {r.to_name}")
