"""
Iteration analytics graphs.

Produces multiple graphs showing:
1. Total change magnitude per iteration
2. Per-component change per iteration
3. Breakdown by delta type per iteration
4. Iteration time per iteration
"""

import matplotlib.pyplot as plt
from typing import List
from ..network import IterationMetrics


def plot_iteration_analytics(metrics_history: List[IterationMetrics],
                            output_dir: str,
                            scenario_name: str):
    """
    Create comprehensive iteration analytics graphs.
    
    Args:
        metrics_history: List of metrics from each iteration
        output_dir: Directory to save figures
        scenario_name: Name of the scenario (for filenames)
    """
    
    if not metrics_history:
        print("No metrics to plot")
        return
    
    iterations = [m.iteration for m in metrics_history]
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f'Iteration Analytics: {scenario_name}', fontsize=16, fontweight='bold')
    
    # 1. Total change magnitude per iteration
    ax1 = axes[0, 0]
    total_magnitudes = [m.total_magnitude for m in metrics_history]
    ax1.plot(iterations, total_magnitudes, marker='o', linewidth=2, markersize=8,
            color='#2E86AB', label='Total Magnitude')
    ax1.set_xlabel('Iteration', fontsize=12)
    ax1.set_ylabel('Total Change Magnitude (box count)', fontsize=12)
    ax1.set_title('Total Change Magnitude per Iteration', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Add convergence marker if converged
    if metrics_history[-1].converged:
        ax1.axvline(x=metrics_history[-1].iteration, color='green', 
                   linestyle='--', alpha=0.5, label='Converged')
        ax1.text(metrics_history[-1].iteration, max(total_magnitudes) * 0.9,
                'Converged', rotation=90, va='top', fontsize=10)
    
    # 2. Per-component change per iteration
    ax2 = axes[0, 1]
    
    # Collect all component names
    all_components = set()
    for m in metrics_history:
        all_components.update(m.per_component_magnitude.keys())
    
    # Plot line for each component
    colors = ['#E63946', '#F77F00', '#06AED5', '#2E86AB', '#A8DADC', '#9B5DE5']
    for i, comp in enumerate(sorted(all_components)):
        comp_magnitudes = [m.per_component_magnitude.get(comp, 0) for m in metrics_history]
        if any(v > 0 for v in comp_magnitudes):  # Only plot if component changed
            ax2.plot(iterations, comp_magnitudes, marker='s', linewidth=2, markersize=6,
                    color=colors[i % len(colors)], label=comp, alpha=0.8)
    
    ax2.set_xlabel('Iteration', fontsize=12)
    ax2.set_ylabel('Component Change Magnitude', fontsize=12)
    ax2.set_title('Per-Component Change per Iteration', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=9, loc='best')
    
    # 3. Breakdown by delta type per iteration
    ax3 = axes[1, 0]
    
    delta_types = ['ΔA_rel', 'ΔA_str', 'ΔG_rel', 'ΔG_str']
    delta_colors = ['#06AED5', '#086788', '#E63946', '#C1121F']
    
    bottom = [0] * len(iterations)
    for dt, color in zip(delta_types, delta_colors):
        values = [m.per_delta_type.get(dt, 0) for m in metrics_history]
        ax3.bar(iterations, values, bottom=bottom, label=dt, color=color, alpha=0.8)
        bottom = [b + v for b, v in zip(bottom, values)]
    
    ax3.set_xlabel('Iteration', fontsize=12)
    ax3.set_ylabel('Box Count by Type', fontsize=12)
    ax3.set_title('Breakdown by Delta Type per Iteration', fontsize=13, fontweight='bold')
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. Iteration time per iteration
    ax4 = axes[1, 1]
    times = [m.time_seconds * 1000 for m in metrics_history]  # Convert to milliseconds
    ax4.bar(iterations, times, color='#457B9D', alpha=0.7)
    ax4.set_xlabel('Iteration', fontsize=12)
    ax4.set_ylabel('Time (milliseconds)', fontsize=12)
    ax4.set_title('Iteration Time per Iteration', fontsize=13, fontweight='bold')
    ax4.grid(True, alpha=0.3, axis='y')
    
    # Add average line
    avg_time = sum(times) / len(times)
    ax4.axhline(y=avg_time, color='red', linestyle='--', alpha=0.5, 
               label=f'Average: {avg_time:.1f}ms')
    ax4.legend()
    
    plt.tight_layout()
    
    # Save figure
    output_path = f"{output_dir}/iteration_analytics_{scenario_name}.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Iteration analytics saved to {output_path}")
    
    # Also create a separate detailed delta type figure
    _plot_delta_type_breakdown(metrics_history, output_dir, scenario_name)


def _plot_delta_type_breakdown(metrics_history: List[IterationMetrics],
                               output_dir: str,
                               scenario_name: str):
    """Create detailed delta type breakdown as separate figure"""
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    iterations = [m.iteration for m in metrics_history]
    delta_types = ['ΔA_rel', 'ΔA_str', 'ΔG_rel', 'ΔG_str']
    delta_colors = ['#06AED5', '#086788', '#E63946', '#C1121F']
    delta_markers = ['o', 's', '^', 'D']
    
    for dt, color, marker in zip(delta_types, delta_colors, delta_markers):
        values = [m.per_delta_type.get(dt, 0) for m in metrics_history]
        ax.plot(iterations, values, marker=marker, linewidth=2, markersize=8,
               color=color, label=dt, alpha=0.8)
    
    ax.set_xlabel('Iteration', fontsize=12)
    ax.set_ylabel('Box Count', fontsize=12)
    ax.set_title(f'Delta Type Breakdown: {scenario_name}', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    output_path = f"{output_dir}/delta_breakdown_{scenario_name}.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Delta breakdown saved to {output_path}")
