"""Base scenario class."""

from dataclasses import dataclass
from typing import Dict, Optional
from ..contracts import Contract, BehaviorSet, Deviation
from ..network import ContractNetwork


@dataclass
class Scenario:
    """
    A scenario defines:
    - Name and description
    - The contract network (baseline)
    - The target component to evolve
    - The target evolved contract
    - Expected minimum iterations (for validation)
    - Optional system-level contract
    """
    name: str
    description: str
    network: ContractNetwork
    target_component: str
    target_contract: Contract
    min_iterations_expected: int = 1
    system_level_contract: Optional[Contract] = None
    
    def get_initial_deviation(self) -> Deviation:
        """
        Compute initial deviation from baseline to target for the target component.
        This represents the local change that triggers propagation.
        """
        baseline = self.network.get_component(self.target_component).baseline_contract
        target = self.target_contract
        
        # Compute deviations
        # ΔA_rel: behaviors added to assumptions (accept more inputs = weaker requirement)
        assumption_relaxation = target.assumptions.difference(baseline.assumptions)
        
        # ΔA_str: behaviors removed from assumptions (accept fewer inputs = stronger requirement)
        assumption_strengthening = baseline.assumptions.difference(target.assumptions)
        
        # ΔG_rel: behaviors added to guarantees (allow more outputs = weaker promise)
        guarantee_relaxation = target.guarantees.difference(baseline.guarantees)
        
        # ΔG_str: behaviors removed from guarantees (allow fewer outputs = stronger promise)
        guarantee_strengthening = baseline.guarantees.difference(target.guarantees)
        
        return Deviation(
            assumption_relaxation=assumption_relaxation,
            assumption_strengthening=assumption_strengthening,
            guarantee_relaxation=guarantee_relaxation,
            guarantee_strengthening=guarantee_strengthening
        )
