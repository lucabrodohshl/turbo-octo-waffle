"""
Exceptions for MILP-based contract transformers.

This module defines the exception raised when MILP optimization fails,
ensuring fail-fast behavior with comprehensive diagnostics.
"""

from typing import Optional, Dict, Tuple, Set, Any
import pulp


class MILPTransformFailure(RuntimeError):
    """
    Exception raised when a MILP optimization in post/pre transformer fails.
    
    This exception ensures fail-fast behavior: if any optimization cannot
    be solved to proven optimality, the entire computation terminates
    with comprehensive diagnostic information.
    
    Attributes:
        component_name: Name of the component where failure occurred
        transformer_type: Either "post" or "pre"
        variable_being_optimized: Name of the variable being min/maximized
        optimization_direction: Either "minimize" or "maximize"
        solver_status: PuLP status code (e.g., pulp.LpStatusInfeasible)
        solver_status_name: Human-readable status name
        input_region: Dict of input variable bounds (for post transformer)
        output_region: Dict of output variable bounds (for pre transformer)
        iteration_number: Fixpoint iteration number when failure occurred
        edge_context: Optional tuple (supplier, consumer, interface_vars)
        solver_name: Name of the solver used (e.g., "PULP_CBC_CMD")
    """
    
    def __init__(self,
                 component_name: str,
                 transformer_type: str,
                 variable_being_optimized: str,
                 optimization_direction: str,
                 solver_status: int,
                 solver_status_name: str,
                 solver_name: str,
                 input_region: Optional[Dict[str, Tuple[float, float]]] = None,
                 output_region: Optional[Dict[str, Tuple[float, float]]] = None,
                 iteration_number: Optional[int] = None,
                 edge_context: Optional[Tuple[str, str, Set[str]]] = None,
                 problem: Optional[pulp.LpProblem] = None):
        """
        Initialize MILP transform failure exception.
        
        Args:
            component_name: Component where failure occurred
            transformer_type: "post" or "pre"
            variable_being_optimized: Variable name being optimized
            optimization_direction: "minimize" or "maximize"
            solver_status: PuLP solver status code
            solver_status_name: Human-readable status
            solver_name: Solver name (e.g., "PULP_CBC_CMD", "GUROBI_CMD")
            input_region: Input variable bounds (for post)
            output_region: Output variable bounds (for pre)
            iteration_number: Iteration when failure occurred
            edge_context: (supplier, consumer, interface_variables) tuple
            problem: The PuLP problem that failed (for debugging)
        """
        self.component_name = component_name
        self.transformer_type = transformer_type
        self.variable_being_optimized = variable_being_optimized
        self.optimization_direction = optimization_direction
        self.solver_status = solver_status
        self.solver_status_name = solver_status_name
        self.solver_name = solver_name
        self.input_region = input_region or {}
        self.output_region = output_region or {}
        self.iteration_number = iteration_number
        self.edge_context = edge_context
        self.problem = problem
        
        # Construct error message
        msg = self._build_message()
        super().__init__(msg)
    
    def _build_message(self) -> str:
        """Build a concise but informative error message."""
        parts = [
            f"MILP optimization failed in {self.component_name}.{self.transformer_type}()",
            f"Variable: {self.variable_being_optimized} ({self.optimization_direction})",
            f"Solver: {self.solver_name}",
            f"Status: {self.solver_status_name}"
        ]
        
        if self.iteration_number is not None:
            parts.append(f"Iteration: {self.iteration_number}")
        
        if self.edge_context:
            supplier, consumer, _ = self.edge_context
            parts.append(f"Edge: {supplier} → {consumer}")
        
        return " | ".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary for JSON serialization.
        
        Returns:
            Dictionary with all exception attributes in serializable form
        """
        result = {
            "component_name": self.component_name,
            "transformer_type": self.transformer_type,
            "variable_being_optimized": self.variable_being_optimized,
            "optimization_direction": self.optimization_direction,
            "solver_status": self.solver_status,
            "solver_status_name": self.solver_status_name,
            "solver_name": self.solver_name,
            "iteration_number": self.iteration_number,
        }
        
        # Add input region if present
        if self.input_region:
            result["input_region"] = {
                var: list(bounds) for var, bounds in self.input_region.items()
            }
        
        # Add output region if present
        if self.output_region:
            result["output_region"] = {
                var: list(bounds) for var, bounds in self.output_region.items()
            }
        
        # Add edge context if present
        if self.edge_context:
            supplier, consumer, iface_vars = self.edge_context
            result["edge_context"] = {
                "supplier": supplier,
                "consumer": consumer,
                "interface_variables": list(iface_vars)
            }
        
        return result
    
    def format_report(self) -> str:
        """
        Format a detailed human-readable report.
        
        Returns:
            Multi-line string with full diagnostic information
        """
        lines = [
            "=" * 80,
            "MILP TRANSFORMER FAILURE",
            "=" * 80,
            "",
            f"Component:    {self.component_name}",
            f"Transformer:  {self.transformer_type}()",
            f"Variable:     {self.variable_being_optimized}",
            f"Direction:    {self.optimization_direction}",
            f"Solver:       {self.solver_name}",
            f"Status:       {self.solver_status_name} (code: {self.solver_status})",
        ]
        
        if self.iteration_number is not None:
            lines.append(f"Iteration:    {self.iteration_number}")
        
        lines.append("")
        
        # Input region (for post transformer)
        if self.input_region:
            lines.append("Input Region:")
            for var in sorted(self.input_region.keys()):
                lb, ub = self.input_region[var]
                lines.append(f"  {var:20s} ∈ [{lb:12.6f}, {ub:12.6f}]")
            lines.append("")
        
        # Output region (for pre transformer)
        if self.output_region:
            lines.append("Output Region:")
            for var in sorted(self.output_region.keys()):
                lb, ub = self.output_region[var]
                lines.append(f"  {var:20s} ∈ [{lb:12.6f}, {ub:12.6f}]")
            lines.append("")
        
        # Edge context
        if self.edge_context:
            supplier, consumer, iface_vars = self.edge_context
            lines.append("Edge Context:")
            lines.append(f"  Supplier:   {supplier}")
            lines.append(f"  Consumer:   {consumer}")
            lines.append(f"  Interface:  {', '.join(sorted(iface_vars))}")
            lines.append("")
        
        lines.append("=" * 80)
        lines.append("")
        lines.append("This failure indicates that the MILP model is infeasible, unbounded,")
        lines.append("or could not be solved to proven optimality within the time limit.")
        lines.append("")
        lines.append("Possible causes:")
        lines.append("  • Model infeasibility (conflicting constraints)")
        lines.append("  • Unbounded objective (missing bounds on variables)")
        lines.append("  • Solver timeout (problem too complex)")
        lines.append("  • Numerical issues (ill-conditioned constraints)")
        lines.append("")
        lines.append("The system terminates immediately to preserve correctness.")
        lines.append("No approximate or fallback bounds are used.")
        lines.append("=" * 80)
        
        # Add MILP problem details if available
        if self.problem:
            lines.append("")
            lines.append("=" * 80)
            lines.append("MILP PROBLEM DETAILS")
            lines.append("=" * 80)
            lines.append("")
            lines.append(f"Problem Name: {self.problem.name}")
            lines.append(f"Sense: {pulp.LpSenses[self.problem.sense]}")
            lines.append(f"Number of Variables: {len(self.problem.variables())}")
            lines.append(f"Number of Constraints: {len(self.problem.constraints)}")
            lines.append("")
            
            # List all variables with bounds
            lines.append("Variables:")
            for var in sorted(self.problem.variables(), key=lambda v: v.name):
                lb = var.lowBound if var.lowBound is not None else "-∞"
                ub = var.upBound if var.upBound is not None else "+∞"
                cat = var.cat if hasattr(var, 'cat') else "Continuous"
                lines.append(f"  {var.name:40s} ∈ [{lb:>10}, {ub:<10}] ({cat})")
            
            lines.append("")
            lines.append("Objective:")
            if self.problem.objective:
                obj_str = str(self.problem.objective)
                if len(obj_str) > 200:
                    obj_str = obj_str[:200] + "..."
                lines.append(f"  {obj_str}")
            else:
                lines.append("  (none)")
            
            lines.append("")
            lines.append("Constraints:")
            for name, constraint in sorted(self.problem.constraints.items()):
                constraint_str = str(constraint)
                if len(constraint_str) > 150:
                    constraint_str = constraint_str[:150] + "..."
                lines.append(f"  {name:30s}: {constraint_str}")
            
            lines.append("")
            lines.append("=" * 80)
        
        return "\n".join(lines)
