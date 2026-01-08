"""
Evolution operator Φ and fixpoint iteration engine.

The evolution operator propagates contract changes through the network
using forward and backward propagation based on post/pre transformers.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional
import time
from .contract_network import ContractNetwork
from ..contracts import BehaviorSet, Deviation, DeviationMap


@dataclass
class IterationMetrics:
    """Metrics for a single iteration"""
    iteration: int
    total_magnitude: float
    per_component_magnitude: Dict[str, float]
    per_delta_type: Dict[str, float]  # ΔA_rel, ΔA_str, ΔG_rel, ΔG_str
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
                        post_result = self.post_transformers[consumer](delta_g_rel_proj)
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
                        pre_result = self.pre_transformers[supplier](delta_a_str_proj)
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
                 max_iterations: int = 100):
        self.evolution_operator = evolution_operator
        self.max_iterations = max_iterations
        self.metrics_history: List[IterationMetrics] = []
        self.delta_history: List[DeviationMap] = []  # Track delta at each iteration
    
    def run(self, initial_delta: DeviationMap) -> DeviationMap:
        """
        Run fixpoint iteration starting from initial deviation.
        
        Args:
            initial_delta: Initial deviation map (usually contains the target local change)
        
        Returns:
            Final deviation map at fixpoint (or max iterations)
        """
        current_delta = initial_delta.copy()
        self.delta_history = []
        
        # Store iteration 0 (initial state)
        self.delta_history.append(current_delta.copy())
        self.metrics_history = []
        
        print(f"Starting fixpoint iteration (max {self.max_iterations} iterations)...")
        
        for iteration in range(1, self.max_iterations + 1):
            iter_start = time.time()
            
            # Apply evolution operator
            next_delta, num_propagations = self.evolution_operator.apply(current_delta)
            
            # Store delta after this iteration
            self.delta_history.append(next_delta.copy())
            
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
            per_type['ΔA_rel'] += len(dev.assumption_relaxation.boxes)
            per_type['ΔA_str'] += len(dev.assumption_strengthening.boxes)
            per_type['ΔG_rel'] += len(dev.guarantee_relaxation.boxes)
            per_type['ΔG_str'] += len(dev.guarantee_strengthening.boxes)
        
        return IterationMetrics(
            iteration=iteration,
            total_magnitude=delta.total_magnitude(),
            per_component_magnitude=per_comp,
            per_delta_type=per_type,
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
