"""
Interface between components in the contract network.
"""

from dataclasses import dataclass
from typing import Set


@dataclass
class Interface:
    """
    Represents an interface between two components.
    
    An interface defines the shared variables between a supplier (producer)
    and a consumer (user) component.
    """
    supplier: str  # Component name providing the interface
    consumer: str  # Component name using the interface
    variables: Set[str]  # Shared interface variables
    
    def __str__(self) -> str:
        vars_str = ", ".join(sorted(self.variables))
        return f"Interface({self.supplier} → {self.consumer}, vars={{{vars_str}}})"
    
    def __hash__(self) -> int:
        return hash((self.supplier, self.consumer, frozenset(self.variables)))
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Interface):
            return False
        return (self.supplier == other.supplier and
                self.consumer == other.consumer and
                self.variables == other.variables)
