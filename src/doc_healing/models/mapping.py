"""Code mapping service models."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class SymbolType(Enum):
    """Types of code symbols."""

    FUNCTION = "function"
    CLASS = "class"
    INTERFACE = "interface"
    VARIABLE = "variable"


class Visibility(Enum):
    """Visibility levels for code symbols."""

    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"


@dataclass
class CodeSymbol:
    """Represents a code symbol (function, class, etc.)."""

    name: str
    type: SymbolType
    signature: str
    file: str
    line: int
    visibility: Visibility


class ChangeType(Enum):
    """Types of symbol changes."""

    RENAMED = "renamed"
    MOVED = "moved"
    DELETED = "deleted"
    SIGNATURE_CHANGED = "signature_changed"


@dataclass
class SymbolChange:
    """Represents a change to a code symbol."""

    type: ChangeType
    old_symbol: CodeSymbol
    new_symbol: Optional[CodeSymbol]
    affected_snippets: List[str]


class ReferenceType(Enum):
    """Types of documentation references."""

    DIRECT = "direct"
    INDIRECT = "indirect"
    EXAMPLE = "example"


@dataclass
class DocumentationReference:
    """Represents a reference from documentation to code."""

    snippet_id: str
    symbols: List[CodeSymbol]
    confidence: float
    reference_type: ReferenceType
