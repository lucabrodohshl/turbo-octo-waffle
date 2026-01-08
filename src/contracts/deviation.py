r"""
Deviation lattice for contract evolution.

A deviation δ = (ΔA_rel, ΔA_str, ΔG_rel, ΔG_str) represents changes to a contract:
- ΔA_rel: relaxation of assumptions (behaviors added to A - accepts more inputs)
- ΔA_str: strengthening of assumptions (behaviors removed from A - restricts inputs)
- ΔG_rel: relaxation of guarantees (behaviors added to G - weakens commitments)
- ΔG_str: strengthening of guarantees (behaviors removed from G - stronger commitments)

Contract reconstruction: C★ = C₀ ⊕ δ where:
- A★ = (A₀ ∪ ΔA_rel) \ ΔA_str
- G★ = (G₀ ∪ ΔG_rel) \ ΔG_str
"""

from dataclasses import dataclass, field
from typing import Dict
from .behavior import BehaviorSet
from .contract import Contract


@dataclass
class Deviation:
    """
    Deviation for a single component.
    Represents incremental changes to a contract.
    """
    assumption_relaxation: BehaviorSet = field(default_factory=BehaviorSet)  # ΔA_rel
    assumption_strengthening: BehaviorSet = field(default_factory=BehaviorSet)  # ΔA_str
    guarantee_relaxation: BehaviorSet = field(default_factory=BehaviorSet)  # ΔG_rel
    guarantee_strengthening: BehaviorSet = field(default_factory=BehaviorSet)  # ΔG_str
    
    def is_empty(self) -> bool:
        """Check if deviation is empty (no changes)"""
        return (self.assumption_relaxation.is_empty() and
                self.assumption_strengthening.is_empty() and
                self.guarantee_relaxation.is_empty() and
                self.guarantee_strengthening.is_empty())
    
    def total_magnitude(self) -> float:
        """
        Total magnitude of deviation (sum of box counts).
        Used for iteration metrics.
        """
        return (len(self.assumption_relaxation.boxes) +
                len(self.assumption_strengthening.boxes) +
                len(self.guarantee_relaxation.boxes) +
                len(self.guarantee_strengthening.boxes))
    
    def subset_of(self, other: 'Deviation') -> bool:
        """
        Check if this deviation is a subset of another (partial order ⊑).
        Component-wise subset check on behavior sets.
        """
        return (self.assumption_relaxation.subset_of(other.assumption_relaxation) and
                self.assumption_strengthening.subset_of(other.assumption_strengthening) and
                self.guarantee_relaxation.subset_of(other.guarantee_relaxation) and
                self.guarantee_strengthening.subset_of(other.guarantee_strengthening))
    
    def union_with(self, other: 'Deviation') -> 'Deviation':
        """
        Union of two deviations (join in lattice).
        Component-wise union of behavior sets.
        """
        return Deviation(
            assumption_relaxation=self.assumption_relaxation.union(other.assumption_relaxation),
            assumption_strengthening=self.assumption_strengthening.union(other.assumption_strengthening),
            guarantee_relaxation=self.guarantee_relaxation.union(other.guarantee_relaxation),
            guarantee_strengthening=self.guarantee_strengthening.union(other.guarantee_strengthening)
        )
    
    def __eq__(self, other) -> bool:
        """
        Equality check for deviation (for fixpoint detection).
        We check if the box sets are structurally equal (same number of boxes).
        This is conservative but sufficient for finite convergence.
        """
        if not isinstance(other, Deviation):
            return False
        
        return (len(self.assumption_relaxation.boxes) == len(other.assumption_relaxation.boxes) and
                len(self.assumption_strengthening.boxes) == len(other.assumption_strengthening.boxes) and
                len(self.guarantee_relaxation.boxes) == len(other.guarantee_relaxation.boxes) and
                len(self.guarantee_strengthening.boxes) == len(other.guarantee_strengthening.boxes) and
                self._boxes_equal(self.assumption_relaxation, other.assumption_relaxation) and
                self._boxes_equal(self.assumption_strengthening, other.assumption_strengthening) and
                self._boxes_equal(self.guarantee_relaxation, other.guarantee_relaxation) and
                self._boxes_equal(self.guarantee_strengthening, other.guarantee_strengthening))
    
    @staticmethod
    def _boxes_equal(bs1: BehaviorSet, bs2: BehaviorSet) -> bool:
        """Check if two behavior sets have the same boxes (order-independent)"""
        if len(bs1.boxes) != len(bs2.boxes):
            return False
        # Convert to sets of frozen representations
        set1 = {box.bounds for box in bs1.boxes}
        set2 = {box.bounds for box in bs2.boxes}
        return set1 == set2
    
    def __str__(self) -> str:
        parts = []
        if not self.assumption_relaxation.is_empty():
            parts.append(f"ΔA_rel:{len(self.assumption_relaxation.boxes)}")
        if not self.assumption_strengthening.is_empty():
            parts.append(f"ΔA_str:{len(self.assumption_strengthening.boxes)}")
        if not self.guarantee_relaxation.is_empty():
            parts.append(f"ΔG_rel:{len(self.guarantee_relaxation.boxes)}")
        if not self.guarantee_strengthening.is_empty():
            parts.append(f"ΔG_str:{len(self.guarantee_strengthening.boxes)}")
        
        if not parts:
            return "Deviation(∅)"
        return "Deviation(" + ", ".join(parts) + ")"
    
    def detailed_str(self) -> str:
        """Detailed string representation"""
        lines = ["Deviation:"]
        
        lines.append(f"  ΔA_rel (assumption relaxation): {len(self.assumption_relaxation.boxes)} boxes")
        for i, box in enumerate(self.assumption_relaxation.boxes[:2]):
            lines.append(f"    [{i+1}] {box}")
        
        lines.append(f"  ΔA_str (assumption strengthening): {len(self.assumption_strengthening.boxes)} boxes")
        for i, box in enumerate(self.assumption_strengthening.boxes[:2]):
            lines.append(f"    [{i+1}] {box}")
        
        lines.append(f"  ΔG_rel (guarantee relaxation): {len(self.guarantee_relaxation.boxes)} boxes")
        for i, box in enumerate(self.guarantee_relaxation.boxes[:2]):
            lines.append(f"    [{i+1}] {box}")
        
        lines.append(f"  ΔG_str (guarantee strengthening): {len(self.guarantee_strengthening.boxes)} boxes")
        for i, box in enumerate(self.guarantee_strengthening.boxes[:2]):
            lines.append(f"    [{i+1}] {box}")
        
        return "\n".join(lines)


class DeviationMap:
    """
    Map from component names to their deviations.
    Represents the global deviation state δ across the entire contract network.
    """
    
    def __init__(self):
        self.deviations: Dict[str, Deviation] = {}
    
    def set_deviation(self, component: str, deviation: Deviation):
        """Set deviation for a component"""
        self.deviations[component] = deviation
    
    def get_deviation(self, component: str) -> Deviation:
        """Get deviation for a component (returns empty if not set)"""
        return self.deviations.get(component, Deviation())
    
    def update_deviation(self, component: str, new_delta: Deviation):
        """
        Update deviation for a component by taking union with new delta.
        Implements the monotone update in the fixpoint iteration.
        """
        current = self.get_deviation(component)
        updated = current.union_with(new_delta)
        self.deviations[component] = updated
    
    def total_magnitude(self) -> float:
        """Total magnitude across all components"""
        return sum(dev.total_magnitude() for dev in self.deviations.values())
    
    def __eq__(self, other) -> bool:
        """Check if two deviation maps are equal (for fixpoint detection)"""
        if not isinstance(other, DeviationMap):
            return False
        
        if set(self.deviations.keys()) != set(other.deviations.keys()):
            return False
        
        for comp in self.deviations:
            if self.deviations[comp] != other.deviations[comp]:
                return False
        
        return True
    
    def copy(self) -> 'DeviationMap':
        """Create a deep copy of the deviation map"""
        new_map = DeviationMap()
        for comp, dev in self.deviations.items():
            # Create new deviation with copies of behavior sets
            new_dev = Deviation(
                assumption_relaxation=BehaviorSet(dev.assumption_relaxation.boxes[:]),
                assumption_strengthening=BehaviorSet(dev.assumption_strengthening.boxes[:]),
                guarantee_relaxation=BehaviorSet(dev.guarantee_relaxation.boxes[:]),
                guarantee_strengthening=BehaviorSet(dev.guarantee_strengthening.boxes[:])
            )
            new_map.deviations[comp] = new_dev
        return new_map


def reconstruct_contract(baseline: Contract, deviation: Deviation) -> Contract:
    r"""
    Reconstruct evolved contract from baseline and deviation.
    
    FORMAL SEMANTICS:
    C★ = C₀ ⊕ δ where:
    - A★ = (A₀ ∪ ΔA_rel) \ ΔA_str
    - G★ = (G₀ ∪ ΔG_rel) \ ΔG_str
    
    INTUITION:
    - Relaxation (ΔA_rel, ΔG_rel): UNION adds behaviors → sets grow
    - Strengthening (ΔA_str, ΔG_str): DIFFERENCE removes behaviors → sets shrink
    
    CRITICAL FIX: Previous version had G★ formula inverted (unioned with ΔG_str, 
    subtracted ΔG_rel) causing all guarantees to vanish.
    """
    # Reconstruct assumptions: A★ = (A₀ ∪ ΔA_rel) \ ΔA_str
    assumptions_star = baseline.assumptions.union(deviation.assumption_relaxation)
    assumptions_star = assumptions_star.difference(deviation.assumption_strengthening)
    
    # Reconstruct guarantees: G★ = (G₀ ∪ ΔG_rel) \ ΔG_str
    # FIXED: Was incorrectly (G₀ ∪ ΔG_str) \ ΔG_rel
    guarantees_star = baseline.guarantees.union(deviation.guarantee_relaxation)
    guarantees_star = guarantees_star.difference(deviation.guarantee_strengthening)
    
    return Contract(assumptions_star, guarantees_star)
