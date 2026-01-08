"""
Contract representation with assume-guarantee structure.
"""

from dataclasses import dataclass
from typing import Set
from .behavior import BehaviorSet


@dataclass
class Contract:
    """
    An assume-guarantee contract C = (A, G) where:
    - A (assumptions): behaviors expected from the environment
    - G (guarantees): behaviors promised by the component
    
    Both A and G are BehaviorSets (finite unions of boxes).
    """
    assumptions: BehaviorSet
    guarantees: BehaviorSet
    
    def __init__(self, assumptions: BehaviorSet = None, guarantees: BehaviorSet = None):
        self.assumptions = assumptions if assumptions is not None else BehaviorSet([])
        self.guarantees = guarantees if guarantees is not None else BehaviorSet([])
    
    def is_empty(self) -> bool:
        """Check if contract is essentially empty"""
        return self.assumptions.is_empty() and self.guarantees.is_empty()
    
    def project_assumptions(self, variables: Set[str]) -> BehaviorSet:
        """Project assumptions onto a subset of variables"""
        return self.assumptions.project(variables)
    
    def project_guarantees(self, variables: Set[str]) -> BehaviorSet:
        """Project guarantees onto a subset of variables"""
        return self.guarantees.project(variables)
    
    def __str__(self) -> str:
        return f"Contract(A: {self.assumptions}, G: {self.guarantees})"
    
    def detailed_str(self) -> str:
        """Detailed string representation"""
        lines = ["Contract:"]
        lines.append("  Assumptions:")
        if self.assumptions.is_empty():
            lines.append("    ∅")
        else:
            for i, box in enumerate(self.assumptions.boxes[:3]):
                lines.append(f"    [{i+1}] {box}")
            if len(self.assumptions.boxes) > 3:
                lines.append(f"    ... and {len(self.assumptions.boxes) - 3} more boxes")
        
        lines.append("  Guarantees:")
        if self.guarantees.is_empty():
            lines.append("    ∅")
        else:
            for i, box in enumerate(self.guarantees.boxes[:3]):
                lines.append(f"    [{i+1}] {box}")
            if len(self.guarantees.boxes) > 3:
                lines.append(f"    ... and {len(self.guarantees.boxes) - 3} more boxes")
        
        return "\n".join(lines)
