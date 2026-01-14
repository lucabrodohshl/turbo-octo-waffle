"""
Evolution operator Φ and fixpoint iteration engine.

The evolution operator propagates contract changes through the network
using forward and backward propagation based on post/pre transformers.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional
import time
import json
import os
from .contract_network import ContractNetwork
from ..contracts import BehaviorSet, Deviation, DeviationMap
from ..exceptions import MILPTransformFailure


@dataclass
class IterationMetrics:
    """Metrics for a single iteration"""
    iteration: int
    total_magnitude: float
    per_component_magnitude: Dict[str, float]
    per_delta_type: Dict[str, float]  # ΔA_rel, ΔA_str, ΔG_rel, ΔG_str (absolute volumes)
    per_delta_type_relative: Dict[str, float]  # Relative change from baseline
    time_seconds: float
    num_propagations: int = 0
    converged: bool = False


class EvolutionOperator:
    """
    Evolution operator Φ that propagates deviations through the network.
    
    Implements:
    1. Forward propagation: supplier ΔG_rel → consumer ΔA_rel, then consumer ΔG_rel via post
    2. Backward propagation: consumer ΔA_str → supplier ΔG_str, then supplier ΔA_str via pre
    """
    
    def __init__(self, 
                 network: ContractNetwork,
                 post_transformers: Dict[str, Callable[[BehaviorSet], BehaviorSet]],
                 pre_transformers: Dict[str, Callable[[BehaviorSet], BehaviorSet]]):
        """
        Args:
            network: The contract network
            post_transformers: Dict mapping component name to its post() function
            pre_transformers: Dict mapping component name to its pre() function
        """
        self.network = network
        self.post_transformers = post_transformers
        self.pre_transformers = pre_transformers
    
    def apply(self, delta: DeviationMap) -> tuple[DeviationMap, int]:
        """
        Apply evolution operator Φ once to current deviation map.
        
        Returns (updated deviation map, propagation count).
        This does NOT modify the input delta.
        
        Raises:
            MILPTransformFailure: If any transformer optimization fails
        """
        new_delta = delta.copy()
        propagation_count = 0
        
        # Forward propagation through each interface
        for iface in self.network.interfaces:
            supplier = iface.supplier
            consumer = iface.consumer
            
            # Get supplier's current ΔG_rel
            supplier_dev = delta.get_deviation(supplier)
            if not supplier_dev.guarantee_relaxation.is_empty():
                # Project onto interface variables
                delta_g_rel_proj = supplier_dev.guarantee_relaxation.project(iface.variables)
                
                if not delta_g_rel_proj.is_empty():
                    # This becomes consumer's ΔA_rel (relaxed assumptions)
                    consumer_dev_update = Deviation(assumption_relaxation=delta_g_rel_proj)
                    new_delta.update_deviation(consumer, consumer_dev_update)
                    propagation_count += 1
                    
                    # Consumer computes ΔG_rel via post(ΔA_rel)
                    if consumer in self.post_transformers:
                        try:
                            post_result = self.post_transformers[consumer](delta_g_rel_proj)
                        except MILPTransformFailure as e:
                            # Enrich exception with edge context if not already present
                            if e.edge_context is None:
                                e.edge_context = (supplier, consumer, iface.variables)
                            raise
                        
                        if not post_result.is_empty():
                            consumer_comp = self.network.get_component(consumer)
                            if consumer_comp:
                                # Project onto consumer's outputs
                                post_result_proj = post_result.project(consumer_comp.outputs)
                                consumer_dev_update2 = Deviation(guarantee_relaxation=post_result_proj)
                                new_delta.update_deviation(consumer, consumer_dev_update2)
                                propagation_count += 1
        
        # Backward propagation through each interface
        for iface in self.network.interfaces:
            supplier = iface.supplier
            consumer = iface.consumer
            
            # Consumer ΔA_str → Supplier ΔG_str
            # When consumer strengthens assumptions (demands less), supplier can strengthen guarantees
            consumer_dev = delta.get_deviation(consumer)
            if not consumer_dev.assumption_strengthening.is_empty():
                # Project onto interface variables
                delta_a_str_proj = consumer_dev.assumption_strengthening.project(iface.variables)
                
                if not delta_a_str_proj.is_empty():
                    # This becomes supplier's ΔG_str (strengthened guarantees)
                    supplier_dev_update = Deviation(guarantee_strengthening=delta_a_str_proj)
                    new_delta.update_deviation(supplier, supplier_dev_update)
                    propagation_count += 1
                    
                    # Supplier computes ΔA_str via pre(ΔG_str)
                    if supplier in self.pre_transformers:
                        try:
                            pre_result = self.pre_transformers[supplier](delta_a_str_proj)
                        except MILPTransformFailure as e:
                            # Enrich exception with edge context if not already present
                            if e.edge_context is None:
                                e.edge_context = (supplier, consumer, iface.variables)
                            raise
                        
                        if not pre_result.is_empty():
                            supplier_comp = self.network.get_component(supplier)
                            if supplier_comp:
                                # Project onto supplier's inputs
                                pre_result_proj = pre_result.project(supplier_comp.inputs)
                                supplier_dev_update2 = Deviation(assumption_strengthening=pre_result_proj)
                                new_delta.update_deviation(supplier, supplier_dev_update2)
                                propagation_count += 1
        
        return new_delta, propagation_count


class FixpointEngine:
    """
    Fixpoint iteration engine for contract evolution.
    
    Repeatedly applies the evolution operator Φ until convergence (fixpoint).
    Collects iteration metrics for analysis and visualization.
    """
    
    def __init__(self, 
                 evolution_operator: EvolutionOperator,
                 max_iterations: int = 100,
                 scenario_name: str = None,
                 output_dir: str = None):
        self.evolution_operator = evolution_operator
        self.max_iterations = max_iterations
        self.scenario_name = scenario_name
        self.output_dir = output_dir
        self.metrics_history: List[IterationMetrics] = []
        self.delta_history: List[DeviationMap] = []  # Track delta at each iteration
        
        # Calculate baseline contract volumes for relative magnitude
        self.baseline_volumes = self._calculate_baseline_volumes()
    
    def _calculate_baseline_volumes(self) -> Dict[str, Dict[str, float]]:
        """Calculate volume of baseline contracts for each component"""
        volumes = {}
        for comp_name, comp_node in self.evolution_operator.network.components.items():
            volumes[comp_name] = {
                'assumption': comp_node.baseline_contract.assumptions.volume(),
                'guarantee': comp_node.baseline_contract.guarantees.volume()
            }
        return volumes
    
    def run(self, initial_delta: DeviationMap) -> DeviationMap:
        """
        Run fixpoint iteration starting from initial deviation.
        
        Args:
            initial_delta: Initial deviation map (usually contains the target local change)
        
        Returns:
            Final deviation map at fixpoint (or max iterations)
            
        Raises:
            MILPTransformFailure: If any transformer optimization fails.
                Reports are written to output/ before re-raising.
        """
        current_delta = initial_delta.copy()
        self.delta_history = []
        
        # Store iteration 0 (initial state)
        self.delta_history.append(current_delta.copy())
        self.metrics_history = []
        
        # Create CN snapshots directory (scenario-specific)
        if self.output_dir and self.scenario_name:
            cn_dir = os.path.join(self.output_dir, f"CN_{self.scenario_name}")
            os.makedirs(cn_dir, exist_ok=True)
        
        # Save initial state (iteration 0)
        self._save_cn_snapshot(0, current_delta)
        
        print(f"Starting fixpoint iteration (max {self.max_iterations} iterations)...")
        
        for iteration in range(1, self.max_iterations + 1):
            iter_start = time.time()
            
            # Apply evolution operator - may raise MILPTransformFailure
            try:
                next_delta, num_propagations = self.evolution_operator.apply(current_delta)
            except MILPTransformFailure as e:
                # Add iteration number to exception if not already present
                if e.iteration_number is None:
                    e.iteration_number = iteration
                
                # Generate failure reports
                self._write_failure_reports(e, iteration, current_delta)
                
                # Re-raise to stop execution
                raise
            
            # Store delta after this iteration
            self.delta_history.append(next_delta.copy())
            
            # Save CN snapshot for this iteration
            self._save_cn_snapshot(iteration, next_delta)
            
            # Compute metrics
            metrics = self._compute_metrics(iteration, next_delta, time.time() - iter_start)
            metrics.num_propagations = num_propagations
            self.metrics_history.append(metrics)
            
            # Check convergence
            if next_delta == current_delta:
                print(f"  Iteration {iteration}: Converged (fixpoint reached)")
                metrics.converged = True
                break
            
            # Print progress
            print(f"  Iteration {iteration}: Total magnitude = {metrics.total_magnitude:.1f}, "
                  f"{num_propagations} propagations, "
                  f"components changed: {len([c for c, m in metrics.per_component_magnitude.items() if m > 0])}")
            
            current_delta = next_delta
        else:
            print(f"  Reached max iterations ({self.max_iterations}) without convergence")
        
        return current_delta
    
    def _compute_metrics(self, iteration: int, delta: DeviationMap, time_elapsed: float) -> IterationMetrics:
        """Compute metrics for current iteration"""
        
        # Per-component magnitude
        per_comp = {}
        for comp_name in self.evolution_operator.network.components.keys():
            dev = delta.get_deviation(comp_name)
            per_comp[comp_name] = dev.total_magnitude()
        
        # Per delta type (summed across all components)
        per_type = {
            'ΔA_rel': 0.0,
            'ΔA_str': 0.0,
            'ΔG_rel': 0.0,
            'ΔG_str': 0.0
        }
        
        for comp_name in self.evolution_operator.network.components.keys():
            dev = delta.get_deviation(comp_name)
            per_type['ΔA_rel'] += dev.assumption_relaxation.volume()
            per_type['ΔA_str'] += dev.assumption_strengthening.volume()
            per_type['ΔG_rel'] += dev.guarantee_relaxation.volume()
            per_type['ΔG_str'] += dev.guarantee_strengthening.volume()
        
        # Per delta type relative (normalized by baseline volumes)
        per_type_relative = {
            'ΔA_rel': 0.0,
            'ΔA_str': 0.0,
            'ΔG_rel': 0.0,
            'ΔG_str': 0.0
        }
        
        total_baseline_assumption = sum(v['assumption'] for v in self.baseline_volumes.values())
        total_baseline_guarantee = sum(v['guarantee'] for v in self.baseline_volumes.values())
        
        # Relative magnitude = deviation_volume / baseline_volume
        if total_baseline_assumption > 0:
            per_type_relative['ΔA_rel'] = per_type['ΔA_rel'] / total_baseline_assumption
            per_type_relative['ΔA_str'] = per_type['ΔA_str'] / total_baseline_assumption
        if total_baseline_guarantee > 0:
            per_type_relative['ΔG_rel'] = per_type['ΔG_rel'] / total_baseline_guarantee
            per_type_relative['ΔG_str'] = per_type['ΔG_str'] / total_baseline_guarantee
        
        return IterationMetrics(
            iteration=iteration,
            total_magnitude=delta.total_magnitude(),
            per_component_magnitude=per_comp,
            per_delta_type=per_type,
            per_delta_type_relative=per_type_relative,
            time_seconds=time_elapsed,
            num_propagations=0  # Could be tracked if needed
        )
    
    def get_metrics_summary(self) -> str:
        """Get summary of iteration metrics"""
        if not self.metrics_history:
            return "No iterations recorded"
        
        lines = [f"Fixpoint iteration completed in {len(self.metrics_history)} iteration(s)"]
        lines.append(f"Total time: {sum(m.time_seconds for m in self.metrics_history):.3f} seconds")
        lines.append(f"Final magnitude: {self.metrics_history[-1].total_magnitude:.1f}")
        
        if self.metrics_history[-1].converged:
            lines.append("Status: Converged to fixpoint")
        else:
            lines.append("Status: Reached max iterations")
        
        return "\n".join(lines)
    
    def _write_failure_reports(self, exception: MILPTransformFailure, 
                               iteration: int, current_delta: DeviationMap) -> None:
        """
        Write failure reports to output directory.
        
        Generates both human-readable text and structured JSON reports.
        
        Args:
            exception: The MILPTransformFailure that occurred
            iteration: Current iteration number
            current_delta: Current deviation map state
        """
        # Ensure output directory exists
        os.makedirs("output", exist_ok=True)
        
        # Write human-readable report
        txt_path = "output/solver_failure_report.txt"
        with open(txt_path, 'w') as f:
            f.write(exception.format_report())
            f.write("\n\n")
            f.write("=" * 80 + "\n")
            f.write("FIXPOINT ITERATION STATE\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Iteration when failure occurred: {iteration}\n")
            f.write(f"Total iterations completed: {iteration - 1}\n")
            f.write(f"Current deviation magnitude: {current_delta.total_magnitude():.2f}\n\n")
            
            f.write("Per-component deviation magnitudes:\n")
            for comp_name in sorted(self.evolution_operator.network.components.keys()):
                dev = current_delta.get_deviation(comp_name)
                mag = dev.total_magnitude()
                if mag > 0:
                    f.write(f"  {comp_name:30s}  {mag:8.2f}\n")
            
            f.write("\n")
        
        print(f"\n✗ MILP transformer failure detected!")
        print(f"  Reports written to:")
        print(f"    - {txt_path}")
        
        # Write JSON report
        json_path = "output/solver_failure_report.json"
        report_data = {
            "failure": exception.to_dict(),
            "fixpoint_state": {
                "iteration": iteration,
                "iterations_completed": iteration - 1,
                "total_magnitude": current_delta.total_magnitude(),
                "per_component_magnitude": {
                    comp_name: current_delta.get_deviation(comp_name).total_magnitude()
                    for comp_name in self.evolution_operator.network.components.keys()
                },
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        with open(json_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"    - {json_path}\n")
    
    def _save_cn_snapshot(self, iteration: int, delta: DeviationMap) -> None:
        """
        Save contract network snapshot for this iteration.
        
        Creates output/CN_ScenarioName/iteration_X/ directory with one txt file per component
        showing the component's reconstructed contract and deviation.
        
        Args:
            iteration: Current iteration number
            delta: Current deviation map
        """
        from ..contracts import reconstruct_contract
        
        # Create iteration directory (scenario-specific in output folder)
        if self.output_dir and self.scenario_name:
            cn_base = os.path.join(self.output_dir, f"CN_{self.scenario_name}")
        else:
            cn_base = "CN"
        
        iter_dir = os.path.join(cn_base, f"iteration_{iteration}")
        os.makedirs(iter_dir, exist_ok=True)
        
        # Save snapshot for each component
        for comp_name, component_node in self.evolution_operator.network.components.items():
            # Get deviation for this component
            deviation = delta.get_deviation(comp_name)
            
            # Get baseline contract from component node
            baseline_contract = component_node.baseline_contract
            
            # Reconstruct contract
            evolved_contract = reconstruct_contract(baseline_contract, deviation)
            
            # Write component snapshot
            snapshot_path = f"{iter_dir}/{comp_name}.txt"
            with open(snapshot_path, 'w') as f:
                f.write("=" * 80 + "\n")
                f.write(f"COMPONENT: {comp_name}\n")
                f.write(f"ITERATION: {iteration}\n")
                f.write("=" * 80 + "\n\n")
                
                # Component info
                f.write("Component Information:\n")
                f.write(f"  Inputs:  {sorted(component_node.inputs)}\n")
                f.write(f"  Outputs: {sorted(component_node.outputs)}\n\n")
                
                # Deviation
                f.write("Deviation:\n")
                f.write(f"  ΔA_rel (assumption relaxation):      {len(deviation.assumption_relaxation.boxes)} boxes\n")
                f.write(f"  ΔA_str (assumption strengthening):   {len(deviation.assumption_strengthening.boxes)} boxes\n")
                f.write(f"  ΔG_rel (guarantee relaxation):       {len(deviation.guarantee_relaxation.boxes)} boxes\n")
                f.write(f"  ΔG_str (guarantee strengthening):    {len(deviation.guarantee_strengthening.boxes)} boxes\n")
                f.write(f"  Total magnitude:                     {deviation.total_magnitude():.2f}\n\n")
                
                # Baseline contract
                f.write("Baseline Contract:\n")
                f.write(f"  Assumptions:  {len(baseline_contract.assumptions.boxes)} boxes\n")
                f.write(f"  Guarantees:   {len(baseline_contract.guarantees.boxes)} boxes\n\n")
                
                if baseline_contract.assumptions.boxes:
                    f.write("  Sample baseline assumption:\n")
                    box = baseline_contract.assumptions.boxes[0]
                    for var in sorted(box.as_dict.keys()):
                        lb, ub = box.as_dict[var]
                        f.write(f"    {var:30s} ∈ [{lb:10.4f}, {ub:10.4f}]\n")
                    f.write("\n")
                
                if baseline_contract.guarantees.boxes:
                    f.write("  Sample baseline guarantee:\n")
                    box = baseline_contract.guarantees.boxes[0]
                    for var in sorted(box.as_dict.keys()):
                        lb, ub = box.as_dict[var]
                        f.write(f"    {var:30s} ∈ [{lb:10.4f}, {ub:10.4f}]\n")
                    f.write("\n")
                
                # Evolved contract
                f.write("Evolved Contract (Baseline + Deviation):\n")
                f.write(f"  Assumptions:  {len(evolved_contract.assumptions.boxes)} boxes\n")
                f.write(f"  Guarantees:   {len(evolved_contract.guarantees.boxes)} boxes\n\n")
                
                # List all assumption boxes
                if evolved_contract.assumptions.boxes:
                    f.write("  All Assumption Boxes:\n")
                    for i, box in enumerate(evolved_contract.assumptions.boxes, 1):
                        f.write(f"    Box {i}:\n")
                        for var in sorted(box.as_dict.keys()):
                            lb, ub = box.as_dict[var]
                            f.write(f"      {var:28s} ∈ [{lb:10.4f}, {ub:10.4f}]\n")
                        f.write("\n")
                else:
                    f.write("  (No assumption boxes)\n\n")
                
                # List all guarantee boxes
                if evolved_contract.guarantees.boxes:
                    f.write("  All Guarantee Boxes:\n")
                    for i, box in enumerate(evolved_contract.guarantees.boxes, 1):
                        f.write(f"    Box {i}:\n")
                        for var in sorted(box.as_dict.keys()):
                            lb, ub = box.as_dict[var]
                            f.write(f"      {var:28s} ∈ [{lb:10.4f}, {ub:10.4f}]\n")
                        f.write("\n")
                else:
                    f.write("  (No guarantee boxes)\n\n")
                
                f.write("=" * 80 + "\n")
