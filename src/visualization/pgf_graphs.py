"""
PGF graph generator for LaTeX integration.

Creates publication-ready graphs in PGF format:
1. Per-component change per iteration
2. Delta type breakdown per iteration

Also saves raw data in JSON format for replotting.
"""

import matplotlib.pyplot as plt
import json
from typing import List
from ..network import IterationMetrics


# Default styling (will be overridden when using PGF)
DEFAULT_PARAMS = {
    'font.size': 10,
    'axes.titlesize': 12,
    'axes.labelsize': 11,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'legend.fontsize': 8,
    'figure.titlesize': 14,
    'lines.linewidth': 2,
    'lines.markersize': 6,
    'axes.grid': True,
    'grid.alpha': 0.3,
}

FIG_SIZE = (1.95, 1.8)

MARKER_SIZE = 2
LINE_WIDTH  = 1
#system composed of five main components: a battery, a power management unit (PMU), a motor, a flight controller (FC), and a navigation system (NS) with an inertial measurement unit (IMU). These components are connected through assume--guarantee contracts, forming a \graph that models the system architecture. The \graph is depicted in Figure~\ref{fig:example-graph}, where nodes represent components and directed edges represent contract-based connections.


    # Plot line for each component
COLORS = ['#E63946', '#F77F00', '#06AED5', '#2E86AB', '#A8DADC', '#9B5DE5']
MARKERS = ['o', 's', '^', 'D', 'v', 'p']
    
component_to_label = {
    'Motor': 'M',
    'PowerManager': 'PMU',
    'NavigationEstimator': 'NS',
    'FlightController': 'FC',
    'Battery': 'B'
}


BBOX_TO_ANCHOR=(0.5, 1.2)
FRAMEALPHA=0.1
NCOL=5 
COLUMNSPACING=0.5 
HANDLETEXTPAD=0.1
MARKERSCALE=0.7 
BORDERAXESPAD=0.5
HANDLELENGTH=0.8
FRAMEON=False

def plot_pgf_graphs(metrics_history: List[IterationMetrics],
                    output_dir: str,
                    scenario_name: str):
    """
    Create PGF graphs for LaTeX integration and save raw data.
    
    Args:
        metrics_history: List of metrics from each iteration
        output_dir: Directory to save figures and data
        scenario_name: Name of the scenario (for filenames)
    """
    
    if not metrics_history:
        print("No metrics to plot")
        return
    
    # Configure matplotlib for PGF output
    import matplotlib
    matplotlib.use('pgf')
    
    # Set PGF-specific parameters
    pgf_params = {
        **DEFAULT_PARAMS,
        'pgf.texsystem': 'pdflatex',
        'pgf.rcfonts': False,
        'text.usetex': True,
        'pgf.preamble': r'\usepackage[utf8x]{inputenc}\usepackage[T1]{fontenc}',
    }
    
    with plt.rc_context(pgf_params):
        # Save raw data first
        _save_raw_data(metrics_history, output_dir, scenario_name)
        
        # Generate graphs
        _plot_per_component_change(metrics_history, output_dir, scenario_name)
        _plot_delta_type_breakdown(metrics_history, output_dir, scenario_name)
        _plot_delta_type_relative(metrics_history, output_dir, scenario_name)
    
    print(f"PGF graphs and raw data saved to {output_dir}")


def _save_raw_data(metrics_history: List[IterationMetrics],
                   output_dir: str,
                   scenario_name: str):
    """Save raw metrics data to JSON for replotting"""
    
    data = {
        'scenario': scenario_name,
        'iterations': [],
        'total_magnitudes': [],
        'per_component': {},
        'per_delta_type': {
            'ΔA_rel': [],
            'ΔA_str': [],
            'ΔG_rel': [],
            'ΔG_str': []
        },
        'per_delta_type_relative': {
            'ΔA_rel': [],
            'ΔA_str': [],
            'ΔG_rel': [],
            'ΔG_str': []
        },
        'times_seconds': [],
        'converged': metrics_history[-1].converged if metrics_history else False,
        'convergence_iteration': metrics_history[-1].iteration if metrics_history[-1].converged else None
    }
    
    # Extract all component names
    all_components = set()
    for m in metrics_history:
        all_components.update(m.per_component_magnitude.keys())
    
    # Initialize per-component arrays
    for comp in sorted(all_components):
        data['per_component'][comp] = []
    
    # Fill data arrays
    for m in metrics_history:
        data['iterations'].append(m.iteration)
        data['total_magnitudes'].append(m.total_magnitude)
        data['times_seconds'].append(m.time_seconds)
        
        # Per-component data
        for comp in data['per_component'].keys():
            data['per_component'][comp].append(m.per_component_magnitude.get(comp, 0))
        
        # Per-delta-type data (absolute volumes)
        for dt in data['per_delta_type'].keys():
            data['per_delta_type'][dt].append(m.per_delta_type.get(dt, 0))
        
        # Per-delta-type relative data
        for dt in data['per_delta_type_relative'].keys():
            data['per_delta_type_relative'][dt].append(m.per_delta_type_relative.get(dt, 0))
    
    # Save to JSON
    output_path = f"{output_dir}/metrics_data_{scenario_name}.json"
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Raw data saved to {output_path}")


def _plot_per_component_change(metrics_history: List[IterationMetrics],
                               output_dir: str,
                               scenario_name: str):
    """Create per-component change graph in PGF format"""
    
    fig, ax = plt.subplots(figsize=FIG_SIZE)
    
    iterations = [m.iteration for m in metrics_history]
    
    # Collect all component names
    all_components = set()
    for m in metrics_history:
        all_components.update(m.per_component_magnitude.keys())
    

    
    for i, comp in enumerate(sorted(all_components)):
        comp_magnitudes = [m.per_component_magnitude.get(comp, 0) for m in metrics_history]
        if any(v > 0 for v in comp_magnitudes):  # Only plot if component changed
            ax.plot(iterations, comp_magnitudes, 
                   marker=MARKERS[i % len(MARKERS)], 
                   linewidth=LINE_WIDTH, 
                   markersize=MARKER_SIZE,
                   color=COLORS[i % len(COLORS)], 
                   label=   component_to_label.get(comp, comp),
                   alpha=0.8)
    

    ax.set_yscale('log')
    ax.set_xticks(iterations)
    #ax.set_xlabel('Iteration', labelpad=1)
    ax.tick_params(axis='y', pad=0) 
    ax.tick_params(axis='x', pad=1)
    #ax.set_ylabel('Component Change Magnitude')
    #legend outside the plot, upper center, 3 columns
    ax.legend(loc='upper center', 
              bbox_to_anchor=BBOX_TO_ANCHOR,
              framealpha=FRAMEALPHA, ncol=NCOL, columnspacing=COLUMNSPACING, 
              handletextpad=HANDLETEXTPAD, 
              markerscale=MARKERSCALE, 
              borderaxespad=BORDERAXESPAD,
              handlelength=HANDLELENGTH, 
              frameon=FRAMEON)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save as PGF
    output_path = f"{output_dir}/per_component_{scenario_name}.pgf"
    plt.savefig(output_path, format='pgf', bbox_inches='tight')

    #save as PNG
    output_path_png = f"{output_dir}/per_component_{scenario_name}.png"
    plt.savefig(output_path_png, format='png', bbox_inches='tight')
    plt.close()
    
    print(f"Per-component graph saved to {output_path}")


def _plot_delta_type_breakdown(metrics_history: List[IterationMetrics],
                               output_dir: str,
                               scenario_name: str):
    """Create delta type breakdown graph in PGF format"""
    
    fig, ax = plt.subplots(figsize=FIG_SIZE)
    
    iterations = [m.iteration for m in metrics_history]
    # Use LaTeX-compatible labels
    delta_types = [r'$\Delta A_{rel}$', r'$\Delta A_{str}$', r'$\Delta G_{rel}$', r'$\Delta G_{str}$']
    delta_keys = ['ΔA_rel', 'ΔA_str', 'ΔG_rel', 'ΔG_str']
    delta_colors = ['#06AED5', '#086788', '#E63946', '#C1121F']
    delta_markers = ['o', 's', '^', 'D']
    
    for dt, key, color, marker in zip(delta_types, delta_keys, delta_colors, delta_markers):
        values = [m.per_delta_type.get(key, 0) for m in metrics_history]
        # Only plot if there are non-zero values
        if any(v > 0 for v in values):
            ax.plot(iterations, values, 
                marker=marker, 
                linewidth=LINE_WIDTH, 
                markersize=MARKER_SIZE,
                color=color, 
                label=dt, 
                alpha=0.8)
    
    #show all 5 ticks in the x axis
    ax.set_xticks(iterations)


    #ax.set_xlabel('Iteration', labelpad=1)
    #ax.set_ylabel('Magnitude', labelpad=1)
    ax.tick_params(axis='y', pad=0) 
    ax.tick_params(axis='x', pad=1) 
    ax.set_yscale('log')
    #have the legend in 2 columns, north ourside of the plot
    #distance to columns adjusted to fit nicely
    #reduce marker size inb the legend
    ax.legend(loc='upper center', 
              bbox_to_anchor=BBOX_TO_ANCHOR,
              framealpha=FRAMEALPHA, ncol=NCOL, columnspacing=COLUMNSPACING, 
              handletextpad=HANDLETEXTPAD, 
              markerscale=MARKERSCALE, 
              borderaxespad=BORDERAXESPAD,
              handlelength=HANDLELENGTH,
              frameon=FRAMEON)
    #
    #ax.legend(loc='best', framealpha=0.9, ncol=2)

    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save as PGF
    format='pgf'
    output_path = f"{output_dir}/delta_type_{scenario_name}.{format}"
    plt.savefig(output_path, format=format, bbox_inches='tight')

    #save as PNG
    output_path_png = f"{output_dir}/delta_type_{scenario_name}.png"
    plt.savefig(output_path_png, format='png', bbox_inches='tight')

    plt.close()
    
    print(f"Delta type graph saved to {output_path}")


def _plot_delta_type_relative(metrics_history: List[IterationMetrics],
                               output_dir: str,
                               scenario_name: str):
    """Create delta type relative magnitude graph in PGF format"""
    
    fig, ax = plt.subplots(figsize=FIG_SIZE)
    
    iterations = [m.iteration for m in metrics_history]
    # Use LaTeX-compatible labels
    delta_types = [r'$\Delta A_{rel}$', r'$\Delta A_{str}$', r'$\Delta G_{rel}$', r'$\Delta G_{str}$']
    delta_keys = ['ΔA_rel', 'ΔA_str', 'ΔG_rel', 'ΔG_str']
    delta_colors = ['#06AED5', '#086788', '#E63946', '#C1121F']
    delta_markers = ['o', 's', '^', 'D']
    
    for dt, key, color, marker in zip(delta_types, delta_keys, delta_colors, delta_markers):
        values = [m.per_delta_type_relative.get(key, 0) for m in metrics_history]
        # Only plot if there are non-zero values
        if any(v > 0 for v in values):
            ax.plot(iterations, values, 
                   marker=marker, 
                   linewidth=LINE_WIDTH, 
                   markersize=MARKER_SIZE,
                   color=color, 
                   label=dt, 
                   alpha=0.8)
    
    ax.set_xlabel('Iteration')
    ax.set_ylabel('Relative Magnitude')
    ax.legend(loc='best', framealpha=0.9, ncol=2)
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save as PGF
    format='pgf'
    output_path = f"{output_dir}/delta_type_relative_{scenario_name}.{format}"
    plt.savefig(output_path, format=format, bbox_inches='tight')

    #save as PNG
    output_path_png = f"{output_dir}/delta_type_relative_{scenario_name}.png"
    plt.savefig(output_path_png, format='png', bbox_inches='tight')

    plt.close()
    
    print(f"Delta type relative graph saved to {output_path}")


def plot_pgf_graphs_from_json(json_path: str, output_dir: str, scenario_name: str):
    """
    Create PGF graphs from saved JSON metrics data.
    
    Useful for regenerating visualizations without re-running simulations.
    
    Args:
        json_path: Path to metrics_data JSON file
        output_dir: Directory to save PGF figures
        scenario_name: Name of the scenario (for filenames)
    """
    import json
    import matplotlib
    
    # Load JSON data
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Convert JSON to IterationMetrics objects
    from ..network import IterationMetrics
    metrics_history = []
    
    iterations = data['iterations']
    for i, iter_num in enumerate(iterations):
        # Extract per-component magnitudes for this iteration
        per_component = {comp: values[i] for comp, values in data['per_component'].items()}
        
        # Extract per-delta-type for this iteration
        per_delta_type = {dt: values[i] for dt, values in data['per_delta_type'].items()}
        
        # Extract per-delta-type relative (if available)
        per_delta_type_relative = {}
        if 'per_delta_type_relative' in data:
            per_delta_type_relative = {dt: values[i] for dt, values in data['per_delta_type_relative'].items()}
        
        metrics = IterationMetrics(
            iteration=iter_num,
            total_magnitude=data['total_magnitudes'][i],
            per_component_magnitude=per_component,
            per_delta_type=per_delta_type,
            per_delta_type_relative=per_delta_type_relative,
            time_seconds=data['times_seconds'][i],
            converged=(i == len(iterations) - 1 and data.get('converged', False))
        )
        metrics_history.append(metrics)
    
    # Configure matplotlib for PGF output
    matplotlib.use('pgf')
    
    # Set PGF-specific parameters
    pgf_params = {
        **DEFAULT_PARAMS,
        'pgf.texsystem': 'pdflatex',
        'pgf.rcfonts': False,
        'text.usetex': True,
        'pgf.preamble': r'\usepackage[utf8x]{inputenc}\usepackage[T1]{fontenc}',
    }
    
    with plt.rc_context(pgf_params):
        # Generate graphs using existing functions
        _plot_per_component_change(metrics_history, output_dir, scenario_name)
        _plot_delta_type_breakdown(metrics_history, output_dir, scenario_name)
        _plot_delta_type_relative(metrics_history, output_dir, scenario_name)
    
    print(f"PGF graphs regenerated for {scenario_name}")
