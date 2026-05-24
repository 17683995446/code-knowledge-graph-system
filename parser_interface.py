"""
Parser Interface Module
Defines the universal parser interface that all language-specific parsers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from enum import Enum


# ============================================================
# Shared constants - canonical source of truth for all modules
# ============================================================

SUPPORTED_CODE_EXTENSIONS: Set[str] = {
    '.py', '.pyw', '.java', '.js', '.jsx', '.ts', '.tsx', '.go', '.rs',
    '.c', '.h', '.cpp', '.hpp', '.cs', '.php', '.rb', '.swift',
    '.kt', '.scala', '.dart', '.lua'
}

SKIP_DIRECTORY_NAMES: Set[str] = {
    '.git', '__pycache__', 'node_modules', 'venv', '.venv',
    'dist', 'build', '.idea', '.vscode'
}


class EntityKind(Enum):
    """Enumeration of entity kinds supported across all languages."""
    CLASS = "class"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM = "enum"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    MODULE = "module"
    NAMESPACE = "namespace"


class ReferenceKind(Enum):
    """Enumeration of reference kinds."""
    INHERIT = "inherit"
    IMPLEMENT = "implement"
    IMPORT = "import"
    USE = "use"
    CALL = "call"


@dataclass
class TypeInfo:
    """Represents a type (class, interface, struct, enum) in the code."""
    name: str
    kind: str  # class, interface, struct, enum
    line_start: int = 0
    line_end: int = 0
    flags: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FunctionInfo:
    """Represents a function or method in the code."""
    name: str
    type_name: Optional[str]  # None for standalone functions
    signature: Optional[str]
    line_start: int = 0
    line_end: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CallInfo:
    """Represents a function call relationship."""
    caller_name: str
    caller_type: Optional[str]
    callee_name: str
    callee_type: Optional[str]
    line_number: int = 0


@dataclass
class ReferenceInfo:
    """Represents a reference relationship (inheritance, implementation, import)."""
    from_name: str
    from_kind: str
    to_name: str
    to_kind: str
    ref_kind: str  # inherit, implement, import, use
    line_number: int = 0


@dataclass
class ParseResult:
    """Universal parse result format - all parsers output this structure."""
    types: List[TypeInfo] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    calls: List[CallInfo] = field(default_factory=list)
    references: List[ReferenceInfo] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    # Internal state for regex parser (not part of public API)
    _last_func_name: Optional[str] = None
    _method_indent: Optional[int] = None
    
    def is_empty(self) -> bool:
        """Check if parse result contains any data."""
        return len(self.types) == 0 and len(self.functions) == 0
    
    def merge(self, other: 'ParseResult'):
        """Merge another parse result into this one."""
        self.types.extend(other.types)
        self.functions.extend(other.functions)
        self.calls.extend(other.calls)
        self.references.extend(other.references)
        self.errors.extend(other.errors)


class CodeParser(ABC):
    """Abstract base class for all language-specific parsers."""
    
    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this parser supports (e.g., ['.py', '.pyw'])."""
        pass
    
    @property
    @abstractmethod
    def language_name(self) -> str:
        """Return the language name (e.g., 'python', 'java')."""
        pass
    
    @abstractmethod
    def parse_file(self, file_path: str, source_code: Optional[str] = None) -> ParseResult:
        """
        Parse a code file and return structured information.
        
        Args:
            file_path: Path to the file to parse
            source_code: Optional pre-read source code (for performance)
        
        Returns:
            ParseResult containing all extracted information
        """
        pass
    
    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle the given file."""
        lower_path = file_path.lower()
        return any(lower_path.endswith(ext) for ext in self.supported_extensions)


class ParserRegistry:
    """Registry for managing multiple language parsers."""
    
    def __init__(self):
        self._parsers: Dict[str, CodeParser] = {}
        self._extension_map: Dict[str, CodeParser] = {}
    
    def register(self, parser: CodeParser):
        """Register a parser for its supported extensions."""
        self._parsers[parser.language_name] = parser
        for ext in parser.supported_extensions:
            self._extension_map[ext.lower()] = parser
    
    def get_parser_by_extension(self, file_path: str) -> Optional[CodeParser]:
        """Get appropriate parser based on file extension."""
        lower_path = file_path.lower()
        for ext, parser in self._extension_map.items():
            if lower_path.endswith(ext):
                return parser
        return None
    
    def get_parser_by_language(self, language: str) -> Optional[CodeParser]:
        """Get parser by language name."""
        return self._parsers.get(language.lower())
    
    def get_supported_languages(self) -> List[str]:
        """Get list of all supported languages."""
        return list(self._parsers.keys())
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of all supported file extensions."""
        return list(self._extension_map.keys())


# Global parser registry instance
parser_registry = ParserRegistry()


def register_parser(parser: CodeParser):
    """Register a parser with the global registry."""
    parser_registry.register(parser)


def get_parser_for_file(file_path: str) -> Optional[CodeParser]:
    """Get the appropriate parser for a file."""
    return parser_registry.get_parser_by_extension(file_path)


def identify_language(file_path: str) -> Optional[str]:
    """Identify the programming language of a file."""
    # First try to get from registered parser
    parser = get_parser_for_file(file_path)
    if parser:
        return parser.language_name
    
    # Fallback to extension map
    return get_language_by_extension(file_path)


# Extension to language mapping for quick identification
EXTENSION_LANGUAGE_MAP = {
    '.py': 'python',
    '.pyw': 'python',
    '.java': 'java',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.go': 'go',
    '.rs': 'rust',
    '.c': 'c',
    '.h': 'c',
    '.cpp': 'cpp',
    '.hpp': 'cpp',
    '.cc': 'cpp',
    '.cs': 'csharp',
    '.php': 'php',
    '.rb': 'ruby',
    '.swift': 'swift',
    '.kt': 'kotlin',
    '.scala': 'scala',
    '.r': 'r',
    '.m': 'objectivec',
    '.mm': 'objectivec',
    '.dart': 'dart',
    '.lua': 'lua',
    '.pl': 'perl',
    '.sh': 'bash',
    '.ps1': 'powershell',
    '.groovy': 'groovy',
    '.ets': 'arkts',
}


def get_language_by_extension(file_path: str) -> Optional[str]:
    """Get language name from file extension without needing a parser."""
    lower_path = file_path.lower()
    for ext, lang in EXTENSION_LANGUAGE_MAP.items():
        if lower_path.endswith(ext):
            return lang
    return None


if __name__ == '__main__':
    # Test the interface
    print("Parser Interface Module loaded successfully")
    print(f"Supported extensions: {list(EXTENSION_LANGUAGE_MAP.keys())}")
