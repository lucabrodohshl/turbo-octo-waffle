"""
Validation checks for contract networks.
"""

from typing import List, Tuple, Optional
from .contract_network import ContractNetwork
from ..contracts import Contract, BehaviorSet, DeviationMap, reconstruct_contract


class ValidationResult:
    """Result of a validation check"""
    
    def __init__(self, passed: bool, message: str = "", details: List[str] = None):
        self.passed = passed
        self.message = message
        self.details = details if details is not None else []
    
    def __str__(self) -> str:
        status = "✓ PASSED" if self.passed else "✗ FAILED"
        result = f"{status}: {self.message}"
        if self.details:
            result += "\n  Details:\n    " + "\n    ".join(self.details)
        return result


class WellFormednessChecker:
    """
    Checks well-formedness of a contract network.
    
    Well-formedness requires that along each interface, the consumer's
    assumption (projected onto interface variables) CONTAINS the supplier's
    guarantee (projected onto interface variables).
    
    Formally: A_consumer|_I ⊇ G_supplier|_I
    where I is the set of interface variables.
    
    Equivalently: G_supplier|_I ⊆ A_consumer|_I
    (supplier guarantee is subset of consumer assumption)
    """
    
    def __init__(self, network: ContractNetwork):
        self.network = network
    
    def check(self, contracts: dict[str, Contract]) -> ValidationResult:
        """
        Check well-formedness given current contracts for all components.
        
        Args:
            contracts: Dict mapping component name to its current contract
        
        Returns:
            ValidationResult indicating if network is well-formed
        """
        violations = []
        
        for iface in self.network.interfaces:
            supplier_comp = self.network.get_component(iface.supplier)
            consumer_comp = self.network.get_component(iface.consumer)
            
            if supplier_comp is None or consumer_comp is None:
                continue
            
            # Get contracts
            supplier_contract = contracts.get(iface.supplier)
            consumer_contract = contracts.get(iface.consumer)
            
            if supplier_contract is None or consumer_contract is None:
                violations.append(f"Missing contract for {iface.supplier} or {iface.consumer}")
                continue
            
            # Project onto interface variables
            supplier_guarantee_proj = supplier_contract.project_guarantees(iface.variables)
            consumer_assumption_proj = consumer_contract.project_assumptions(iface.variables)
            
            # Check if supplier guarantee ⊆ consumer assumption
            # (i.e., consumer assumption CONTAINS supplier guarantee)
            # Equivalently: consumer_assumption ⊇ supplier_guarantee
            if not supplier_guarantee_proj.subset_of(consumer_assumption_proj):
                violations.append(
                    f"{iface.supplier} → {iface.consumer}: "
                    f"Consumer assumption does not contain supplier guarantee on {iface.variables}"
                )
        
        if violations:
            return ValidationResult(
                passed=False,
                message="Network is NOT well-formed",
                details=violations
            )
        else:
            return ValidationResult(
                passed=True,
                message="Network is well-formed"
            )


class SystemLevelChecker:
    """
    Checks system-level contract satisfaction.
    
    Verifies that the composed system satisfies a given system-level
    contract C_S = (A_S, G_S).
    """
    
    def __init__(self, network: ContractNetwork):
        self.network = network
    
    def check(self, 
              contracts: dict[str, Contract],
              system_contract: Contract) -> Tuple[ValidationResult, Optional[BehaviorSet], Optional[BehaviorSet]]:
        r"""
        Check if network satisfies system-level contract.
        
        Args:
            contracts: Current contracts for all components
            system_contract: Required system-level contract (A_S, G_S)
        
        Returns:
            Tuple of:
            - ValidationResult indicating satisfaction
            - Gap (required but not achieved): G_S \ G_achieved
            - Violation (achieved but not required): G_achieved \ G_S
        """
        # For simplicity, we compute system guarantee as union of all component guarantees
        # This is conservative but works for demonstration
        all_guarantees = []
        for comp_name, contract in contracts.items():
            all_guarantees.extend(contract.guarantees.boxes)
        
        system_guarantee_achieved = BehaviorSet(all_guarantees)
        required_guarantee = system_contract.guarantees
        
        # Check if achieved ⊆ required (no violations)
        # and required ⊆ achieved (no gaps)
        
        achieved_covers_required = required_guarantee.subset_of(system_guarantee_achieved)
        no_violations = system_guarantee_achieved.subset_of(required_guarantee)
        
        gap = None
        violation = None
        
        if not achieved_covers_required:
            # Gap: what's required but not achieved
            gap = required_guarantee.difference(system_guarantee_achieved)
        
        if not no_violations:
            # Violation: what's achieved but not required
            violation = system_guarantee_achieved.difference(required_guarantee)
        
        if achieved_covers_required and no_violations:
            return (ValidationResult(
                passed=True,
                message="System-level contract is SATISFIED"
            ), None, None)
        else:
            details = []
            if gap and not gap.is_empty():
                details.append(f"Gap detected: {len(gap.boxes)} box(es) required but not achieved")
            if violation and not violation.is_empty():
                details.append(f"Violation detected: {len(violation.boxes)} box(es) achieved but not required")
            
            return (ValidationResult(
                passed=False,
                message="System-level contract is NOT satisfied",
                details=details
            ), gap, violation)
    
    def compute_gap_and_violation(self,
                                   contracts: dict[str, Contract],
                                   system_contract: Contract) -> Tuple[BehaviorSet, BehaviorSet]:
        r"""
        Compute gap and violation regions.
        
        Returns:
            (gap, violation) where:
            - gap = required_G \ achieved_G (what's missing)
            - violation = achieved_G \ required_G (what's violating)
        """
        all_guarantees = []
        for comp_name, contract in contracts.items():
            all_guarantees.extend(contract.guarantees.boxes)
        
        system_guarantee_achieved = BehaviorSet(all_guarantees)
        required_guarantee = system_contract.guarantees
        
        gap = required_guarantee.difference(system_guarantee_achieved)
        violation = system_guarantee_achieved.difference(required_guarantee)
        
        return gap, violation
