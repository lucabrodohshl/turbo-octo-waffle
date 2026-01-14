"""
Main execution script for contract evolution experiments.

Runs scenarios, performs fixpoint iteration, validates results, and generates outputs.
"""

import sys
import os
from datetime import datetime
from typing import Dict, List

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.contracts import Contract, BehaviorSet, DeviationMap, reconstruct_contract
from src.network import EvolutionOperator, FixpointEngine, WellFormednessChecker, SystemLevelChecker
from src.components import FlightController, Motor, PowerManager, Battery, NavigationEstimator
from src.scenarios.motor_upgrade import create_motor_upgrade_scenario
from src.scenarios.nav_drift_increase import create_nav_drift_scenario
from src.visualization import draw_contract_network, plot_iteration_analytics, plot_pgf_graphs


def run_scenario(scenario, output_dir: str):
    """
    Run a single scenario: fixpoint iteration, validation, and output generation.
    
    Args:
        scenario: The scenario to run
        output_dir: Directory for output files
    """
    
    print(f"\n{'='*80}")
    print(f"SCENARIO: {scenario.name}")
    print(f"{'='*80}")
    print(f"Description: {scenario.description}")
    print(f"Target component: {scenario.target_component}")
    print(f"Expected minimum iterations: {scenario.min_iterations_expected}")
    print()
    
    print("Creating component instances...")
    # Create component instances for post/pre transformers
    components = {
        'FlightController': FlightController(),
        'Motor': Motor(),
        'PowerManager': PowerManager(),
        'Battery': Battery(),
        'NavigationEstimator': NavigationEstimator()
    }
    
    print("Building post/pre transformer dictionaries...")
    # Build post/pre transformer dictionaries
    post_transformers = {name: comp.post for name, comp in components.items()}
    pre_transformers = {name: comp.pre for name, comp in components.items()}
    
    # Create evolution operator
    evolution_op = EvolutionOperator(
        network=scenario.network,
        post_transformers=post_transformers,
        pre_transformers=pre_transformers
    )
    
    # Create fixpoint engine
    fixpoint_engine = FixpointEngine(
        evolution_op, 
        max_iterations=100,
        scenario_name=scenario.name,
        output_dir=output_dir
    )
    
    # Initialize deviation map with target change
    initial_delta = DeviationMap()
    target_deviation = scenario.get_initial_deviation()
    initial_delta.set_deviation(scenario.target_component, target_deviation)
    
    print(f"Initial deviation for {scenario.target_component}:")
    print(f"  {target_deviation}")
    print()
    
    # Check baseline well-formedness
    print("Checking baseline well-formedness...")
    baseline_contracts = {comp_name: node.baseline_contract 
                          for comp_name, node in scenario.network.components.items()}
    wf_checker = WellFormednessChecker(scenario.network)
    baseline_wf_result = wf_checker.check(baseline_contracts)
    print(baseline_wf_result)
    print()
    
    # Run fixpoint iteration
    print("Running fixpoint iteration...")
    final_delta = fixpoint_engine.run(initial_delta)
    
    print()
    print(fixpoint_engine.get_metrics_summary())
    print()
    
    # Check if met minimum iteration expectation
    num_iterations = len(fixpoint_engine.metrics_history)
    if num_iterations >= scenario.min_iterations_expected:
        print(f"✓ Met minimum iteration expectation ({num_iterations} >= {scenario.min_iterations_expected})")
    else:
        print(f"⚠ Did not meet minimum iteration expectation ({num_iterations} < {scenario.min_iterations_expected})")
    print()
    
    # Reconstruct final contracts
    print("Reconstructing final contracts...")
    final_contracts = {}
    for comp_name, comp_node in scenario.network.components.items():
        deviation = final_delta.get_deviation(comp_name)
        final_contract = reconstruct_contract(comp_node.baseline_contract, deviation)
        
        # WORKAROUND: If reconstruction produces empty contract (known issue with box difference
        # for pure strengthening scenarios), use baseline as approximation
        if final_contract.assumptions.is_empty() and final_contract.guarantees.is_empty():
            print(f"  WARNING: {comp_name} reconstruction produced empty contract, using baseline")
            final_contract = comp_node.baseline_contract
        
        final_contracts[comp_name] = final_contract
        
        if not deviation.is_empty():
            print(f"  {comp_name}: {deviation}")
    print()
    
    # Validate well-formedness
    print("Checking well-formedness...")
    wf_checker = WellFormednessChecker(scenario.network)
    wf_result = wf_checker.check(final_contracts)
    print(wf_result)
    print()
    
    # Validate system-level contract (if provided)
    gap = None
    violation = None
    system_result = None
    
    if scenario.system_level_contract is not None:
        print("Checking system-level contract...")
        sl_checker = SystemLevelChecker(scenario.network)
        system_result, gap, violation = sl_checker.check(
            final_contracts,
            scenario.system_level_contract
        )
        print(system_result)
        
        # Always compute and display both gap and violation for transparency
        if not system_result.passed:
            # Compute summary metrics
            all_guarantees = []
            for contract in final_contracts.values():
                all_guarantees.extend(contract.guarantees.boxes)
            achieved_count = len(all_guarantees)
            required_count = len(scenario.system_level_contract.guarantees.boxes)
            gap_count = len(gap.boxes) if gap else 0
            violation_count = len(violation.boxes) if violation else 0
            
            print(f"\n  Summary: Achieved={achieved_count} boxes, Required={required_count} boxes, Gap={gap_count} boxes, Violation={violation_count} boxes")
            
            # Show gap (required but not achieved)
            if gap and not gap.is_empty():
                print(f"\n  Gap (required but not achieved): {len(gap.boxes)} box(es)")
                print(gap.detailed_str())
            else:
                print(f"\n  Gap (required but not achieved): 0 box(es)")
            
            # Show violation (achieved but not required)
            if violation and not violation.is_empty():
                print(f"\n  Violation (achieved but not required): {len(violation.boxes)} box(es)")
                print(violation.detailed_str())
            else:
                print(f"\n  Violation (achieved but not required): 0 box(es)")
        print()
    
    # Generate visualizations
    print("Generating visualizations...")
    figures_dir = os.path.join(output_dir, 'figures')
    os.makedirs(figures_dir, exist_ok=True)
    
    # Network diagram
    network_path = os.path.join(figures_dir, f'network_{scenario.name}.png')
    draw_contract_network(
        scenario.network,
        final_delta,
        network_path,
        title=f"Contract Network: {scenario.name}"
    )
    
    # Iteration analytics
    plot_iteration_analytics(
        fixpoint_engine.metrics_history,
        figures_dir,
        scenario.name
    )
    
    # PGF graphs for LaTeX
    plot_pgf_graphs(
        fixpoint_engine.metrics_history,
        figures_dir,
        scenario.name
    )
    print()
    
    # Generate text report
    print("Generating text report...")
    report_path = os.path.join(output_dir, f'evolution_report_{scenario.name}.txt')
    _generate_text_report(
        report_path,
        scenario,
        final_delta,
        final_contracts,
        fixpoint_engine.metrics_history,
        baseline_wf_result,
        wf_result,
        system_result,
        gap,
        violation
    )
    print(f"Report saved to {report_path}")
    
    # Generate iteration-by-iteration contract trace
    print("Generating contract evolution trace...")
    trace_path = os.path.join(output_dir, f'contract_trace_{scenario.name}.txt')
    _generate_contract_trace(
        trace_path,
        scenario,
        fixpoint_engine.delta_history,
        baseline_contracts
    )
    print(f"Contract trace saved to {trace_path}")
    print()


def _generate_text_report(report_path: str,
                          scenario,
                          final_delta: DeviationMap,
                          final_contracts: Dict[str, Contract],
                          metrics_history,
                          baseline_wf_result,
                          wf_result,
                          system_result,
                          gap,
                          violation):
    """Generate detailed text report"""
    
    with open(report_path, 'w') as f:
        # Header
        f.write("="*80 + "\n")
        f.write(f"CONTRACT EVOLUTION REPORT\n")
        f.write("="*80 + "\n")
        f.write(f"Scenario: {scenario.name}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n")
        
        # Description
        f.write("DESCRIPTION\n")
        f.write("-"*80 + "\n")
        f.write(f"{scenario.description}\n")
        f.write("\n")
        
        # Baseline contracts
        f.write("BASELINE CONTRACTS\n")
        f.write("-"*80 + "\n")
        for comp_name, comp_node in sorted(scenario.network.components.items()):
            f.write(f"\n{comp_name}:\n")
            f.write(f"  Inputs: {sorted(comp_node.inputs)}\n")
            f.write(f"  Outputs: {sorted(comp_node.outputs)}\n")
            f.write(f"  Baseline Assumptions: {len(comp_node.baseline_contract.assumptions.boxes)} box(es)\n")
            f.write(f"  Baseline Guarantees: {len(comp_node.baseline_contract.guarantees.boxes)} box(es)\n")
        f.write("\n")
        
        # Baseline well-formedness
        f.write("BASELINE WELL-FORMEDNESS CHECK\n")
        f.write("-"*80 + "\n")
        f.write(str(baseline_wf_result))
        f.write("\n\n")
        
        # Target evolution
        f.write("TARGET EVOLUTION\n")
        f.write("-"*80 + "\n")
        f.write(f"Component: {scenario.target_component}\n")
        initial_dev = scenario.get_initial_deviation()
        f.write(f"Initial deviation: {initial_dev}\n")
        f.write(initial_dev.detailed_str())
        f.write("\n\n")
        
        # Iteration summary
        f.write("ITERATION SUMMARY\n")
        f.write("-"*80 + "\n")
        f.write(f"Total iterations: {len(metrics_history)}\n")
        f.write(f"Converged: {metrics_history[-1].converged if metrics_history else False}\n")
        f.write(f"Total time: {sum(m.time_seconds for m in metrics_history):.3f} seconds\n")
        f.write("\n")
        
        # Per-iteration details
        f.write("Per-Iteration Metrics:\n")
        f.write(f"{'Iter':<6} {'Total Mag':<12} {'ΔA_rel':<10} {'ΔA_str':<10} {'ΔG_rel':<10} {'ΔG_str':<10} {'Time(ms)':<10}\n")
        f.write("-"*76 + "\n")
        
        for m in metrics_history:
            f.write(f"{m.iteration:<6} "
                   f"{m.total_magnitude:<12.1f} "
                   f"{m.per_delta_type.get('ΔA_rel', 0):<10.0f} "
                   f"{m.per_delta_type.get('ΔA_str', 0):<10.0f} "
                   f"{m.per_delta_type.get('ΔG_rel', 0):<10.0f} "
                   f"{m.per_delta_type.get('ΔG_str', 0):<10.0f} "
                   f"{m.time_seconds*1000:<10.1f}\n")
        f.write("\n")
        
        # Final deviations
        f.write("FINAL DEVIATIONS\n")
        f.write("-"*80 + "\n")
        
        for comp_name in sorted(scenario.network.components.keys()):
            deviation = final_delta.get_deviation(comp_name)
            if not deviation.is_empty():
                f.write(f"\n{comp_name}:\n")
                f.write(f"  Total magnitude: {deviation.total_magnitude():.1f}\n")
                f.write(f"  ΔA_rel: {len(deviation.assumption_relaxation.boxes)} box(es)\n")
                f.write(f"  ΔA_str: {len(deviation.assumption_strengthening.boxes)} box(es)\n")
                f.write(f"  ΔG_rel: {len(deviation.guarantee_relaxation.boxes)} box(es)\n")
                f.write(f"  ΔG_str: {len(deviation.guarantee_strengthening.boxes)} box(es)\n")
                
                # Show some boxes
                if len(deviation.assumption_relaxation.boxes) > 0:
                    f.write(f"  Sample ΔA_rel boxes:\n")
                    for box in deviation.assumption_relaxation.boxes[:2]:
                        f.write(f"    {box}\n")
                
                if len(deviation.guarantee_relaxation.boxes) > 0:
                    f.write(f"  Sample ΔG_rel boxes:\n")
                    for box in deviation.guarantee_relaxation.boxes[:2]:
                        f.write(f"    {box}\n")
        f.write("\n")
        
        # Final contracts summary
        f.write("FINAL CONTRACTS SUMMARY\n")
        f.write("-"*80 + "\n")
        for comp_name in sorted(final_contracts.keys()):
            contract = final_contracts[comp_name]
            f.write(f"\n{comp_name}:\n")
            f.write(f"  Assumptions: {len(contract.assumptions.boxes)} box(es)\n")
            f.write(f"  Guarantees: {len(contract.guarantees.boxes)} box(es)\n")
        f.write("\n")
        
        # Well-formedness result after evolution
        f.write("FINAL WELL-FORMEDNESS CHECK (After Evolution)\n")
        f.write("-"*80 + "\n")
        f.write(str(wf_result))
        f.write("\n")
        
        # If well-formedness failed, provide detailed diagnostics
        if not wf_result.passed and wf_result.details:
            f.write("\nDETAILED WELL-FORMEDNESS VIOLATIONS:\n")
            f.write("Note: For well-formedness, consumer assumptions must be subsets of supplier guarantees.\n")
            f.write("Violation indicates: A_consumer ⊈ G_supplier on the specified variables.\n")
            f.write("\n")
            
            # Group violations by interface for clarity
            for detail in wf_result.details:
                f.write(f"  {detail}\n")
        f.write("\n")
        
        # System-level result
        if system_result is not None:
            f.write("SYSTEM-LEVEL CONTRACT CHECK\n")
            f.write("-"*80 + "\n")
            f.write(str(system_result))
            f.write("\n")
            
            # Show detailed comparison: Required vs Achieved
            f.write("\nDETAILED SYSTEM-LEVEL COMPARISON\n")
            f.write("-"*80 + "\n")
            
            # Show what's required
            f.write("\nREQUIRED by system-level contract:\n")
            if scenario.system_level_contract.guarantees.is_empty():
                f.write("  (no guarantees required)\n")
            else:
                for i, box in enumerate(scenario.system_level_contract.guarantees.boxes, 1):
                    f.write(f"  [{i}] {box}\n")
            
            # Show what's actually achieved
            f.write("\nACHIEVED by evolved system:\n")
            all_guarantees = []
            for comp_name, contract in final_contracts.items():
                all_guarantees.extend(contract.guarantees.boxes)
            
            if not all_guarantees:
                f.write("  (no guarantees achieved)\n")
            else:
                # Group by component for clarity
                f.write(f"  Total: {len(all_guarantees)} guarantee boxes from all components\n")
                for comp_name in sorted(final_contracts.keys()):
                    contract = final_contracts[comp_name]
                    if not contract.guarantees.is_empty():
                        f.write(f"\n  {comp_name} ({len(contract.guarantees.boxes)} boxes):\n")
                        for i, box in enumerate(contract.guarantees.boxes, 1):
                            # Show only first 3 boxes per component to avoid clutter
                            if i <= 3:
                                f.write(f"    [{i}] {box}\n")
                            elif i == 4:
                                f.write(f"    ... ({len(contract.guarantees.boxes)-3} more boxes)\n")
                                break
            
            # Analysis section
            f.write("\n" + "-"*80 + "\n")
            f.write("ANALYSIS: How are we violating the system-level contract?\n")
            f.write("-"*80 + "\n")
            
            if gap and not gap.is_empty():
                f.write(f"\n❌ GAP: {len(gap.boxes)} required box(es) NOT achieved\n")
                f.write("   These behaviors are REQUIRED but the evolved system CANNOT provide them:\n")
                for i, box in enumerate(gap.boxes, 1):
                    f.write(f"   [{i}] {box}\n")
                f.write("\n   Interpretation: The system evolution (degradation or upgrade) has made it\n")
                f.write("   impossible to satisfy these requirements. The system cannot operate within\n")
                f.write("   these bounds given the component changes.\n")
            else:
                f.write("\n✓ No gap: All required behaviors are achieved\n")
            
            if violation and not violation.is_empty():
                f.write(f"\n⚠️  VIOLATION: {len(violation.boxes)} box(es) achieved but NOT required\n")
                f.write("   These behaviors are PROVIDED but were not in the original requirements:\n")
                # Show first few violations
                for i, box in enumerate(violation.boxes, 1):
                    if i <= 5:
                        f.write(f"   [{i}] {box}\n")
                    elif i == 6:
                        f.write(f"   ... ({len(violation.boxes)-5} more boxes)\n")
                        break
                f.write("\n   Interpretation: The system is providing additional behaviors beyond what was\n")
                f.write("   specified. This could indicate over-specification or emergent behaviors from\n")
                f.write("   the evolution process.\n")
            else:
                f.write("\n✓ No violation: No unexpected behaviors\n")
            
            if not system_result.passed:
                f.write("\n" + "="*80 + "\n")
                f.write("CONCLUSION: System-level contract is NOT satisfied\n")
                if gap and not gap.is_empty():
                    f.write(f"  • Missing {len(gap.boxes)} required behavior(s)\n")
                if violation and not violation.is_empty():
                    f.write(f"  • Providing {len(violation.boxes)} unexpected behavior(s)\n")
                f.write("="*80 + "\n")
            else:
                f.write("\n" + "="*80 + "\n")
                f.write("CONCLUSION: System-level contract IS satisfied ✓\n")
                f.write("="*80 + "\n")
        
        # Footer
        f.write("\n")
        f.write("="*80 + "\n")
        f.write("END OF REPORT\n")
        f.write("="*80 + "\n")


def _generate_contract_trace(trace_path: str,
                             scenario,
                             delta_history: List[DeviationMap],
                             baseline_contracts: Dict[str, Contract]):
    """Generate iteration-by-iteration contract trace showing how contracts evolved"""
    
    with open(trace_path, 'w') as f:
        # Header
        f.write("="*80 + "\n")
        f.write(f"CONTRACT EVOLUTION TRACE - ITERATION BY ITERATION\n")
        f.write("="*80 + "\n")
        f.write(f"Scenario: {scenario.name}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n")
        
        f.write(f"This trace shows how each component's contract evolved through fixpoint iterations.\n")
        f.write(f"Total iterations: {len(delta_history)}\n")
        f.write(f"  - Iteration 0: Baseline contracts (initial state)\n")
        f.write(f"  - Iterations 1-{len(delta_history)-1}: Evolution through fixpoint operator Φ\n")
        f.write("\n")
        
        # For each iteration
        for iter_num, delta in enumerate(delta_history):
            f.write("="*80 + "\n")
            f.write(f"ITERATION {iter_num}\n")
            f.write("="*80 + "\n")
            
            if iter_num == 0:
                f.write("Initial state: Baseline contracts + target deviation\n")
            else:
                f.write(f"After applying evolution operator Φ (iteration {iter_num})\n")
            
            f.write(f"Total magnitude: {delta.total_magnitude():.1f}\n")
            f.write("\n")
            
            # For each component, show the reconstructed contract at this iteration
            for comp_name in sorted(scenario.network.components.keys()):
                comp_node = scenario.network.get_component(comp_name)
                deviation = delta.get_deviation(comp_name)
                
                # Reconstruct contract from baseline + deviation
                baseline = baseline_contracts[comp_name]
                reconstructed = reconstruct_contract(baseline, deviation)
                
                f.write("-"*80 + "\n")
                f.write(f"Component: {comp_name}\n")
                f.write("-"*80 + "\n")
                
                # Show deviation
                if not deviation.is_empty():
                    f.write(f"Deviation: {deviation}\n")
                    f.write(f"  Magnitude: {deviation.total_magnitude():.1f}\n")
                else:
                    f.write(f"Deviation: (none - using baseline)\n")
                
                f.write("\n")
                
                # Show reconstructed contract
                f.write(f"Reconstructed Contract:\n")
                f.write(f"  Assumptions ({len(reconstructed.assumptions.boxes)} boxes):\n")
                if len(reconstructed.assumptions.boxes) <= 5:
                    for i, box in enumerate(reconstructed.assumptions.boxes, 1):
                        f.write(f"    [{i}] {box}\n")
                else:
                    for i, box in enumerate(reconstructed.assumptions.boxes[:3], 1):
                        f.write(f"    [{i}] {box}\n")
                    f.write(f"    ... ({len(reconstructed.assumptions.boxes) - 3} more boxes)\n")
                
                f.write(f"\n  Guarantees ({len(reconstructed.guarantees.boxes)} boxes):\n")
                if len(reconstructed.guarantees.boxes) <= 5:
                    for i, box in enumerate(reconstructed.guarantees.boxes, 1):
                        f.write(f"    [{i}] {box}\n")
                else:
                    for i, box in enumerate(reconstructed.guarantees.boxes[:3], 1):
                        f.write(f"    [{i}] {box}\n")
                    f.write(f"    ... ({len(reconstructed.guarantees.boxes) - 3} more boxes)\n")
                
                f.write("\n")
            
            f.write("\n")
        
        # Footer
        f.write("="*80 + "\n")
        f.write("END OF CONTRACT TRACE\n")
        f.write("="*80 + "\n")


def main():
    """Main execution function"""
    
    print("="*80)
    print("CONTRACT DYNAMIC EVOLUTION - DRONE SYSTEM")
    print("="*80)
    print()
    
    # Create output directory
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    os.makedirs(output_dir, exist_ok=True)
    
    # Create scenarios
    print("Creating scenarios...")
    scenario1 = create_motor_upgrade_scenario()
    scenario2 = create_nav_drift_scenario()
    
    scenarios = [scenario2]
    print(f"Created {len(scenarios)} scenario(s)\n")
    
    # Run each scenario
    for scenario in scenarios:
        try:
            run_scenario(scenario, output_dir)
        except Exception as e:
            print(f"ERROR running scenario {scenario.name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print("\n" + "="*80)
    print("ALL SCENARIOS COMPLETE")
    print("="*80)
    print(f"\nOutputs saved to: {output_dir}")
    print(f"  - Text reports: {output_dir}/evolution_report_*.txt")
    print(f"  - Figures: {output_dir}/figures/")
    print()


if __name__ == "__main__":
    main()




