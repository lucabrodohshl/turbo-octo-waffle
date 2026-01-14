"""
Standalone visualization script for paper figures.

Loads pre-computed metrics data from JSON files and generates
publication-ready PGF graphs without re-running the simulations.
"""

import os
from src.visualization import plot_pgf_graphs_from_json


def visualize_scenario(scenario_name: str, figures_dir: str):
    """Generate all visualizations for a single scenario"""
    
    print(f"\n{'='*80}")
    print(f"Generating visualizations for: {scenario_name}")
    print(f"{'='*80}")
    
    # Check if metrics data exists
    json_path = os.path.join(figures_dir, f'metrics_data_{scenario_name}.json')
    
    if not os.path.exists(json_path):
        print(f"ERROR: Metrics data not found at {json_path}")
        print(f"Please run main.py or main2.py first to generate the data.")
        return False
    
    # Generate PGF graphs using the visualization module
    plot_pgf_graphs_from_json(json_path, figures_dir, scenario_name)
    
    print(f"✓ Visualizations complete for {scenario_name}")
    return True


def main():
    """Generate all paper visualizations"""
    
    print("="*80)
    print("PAPER VISUALIZATION GENERATOR")
    print("="*80)
    print()
    print("Generating PGF graphs for LaTeX integration...")
    print("Figure size: 2.5 x 2.3 inches")
    print()
    
    # Set paths
    output_dir = 'output'
    figures_dir = os.path.join(output_dir, 'figures')
    
    # Check if figures directory exists
    if not os.path.exists(figures_dir):
        print(f"ERROR: Figures directory not found at {figures_dir}")
        print(f"Please run main.py or main2.py first to generate the data.")
        return
    
    # Generate visualizations for both scenarios
    scenarios = ['MotorUpgrade', 'NavDriftIncrease']
    success_count = 0
    
    for scenario in scenarios:
        if visualize_scenario(scenario, figures_dir):
            success_count += 1
    
    print()
    print("="*80)
    print(f"VISUALIZATION COMPLETE: {success_count}/{len(scenarios)} scenarios")
    print("="*80)
    print()
    print(f"Output location: {figures_dir}")
    print()
    print("Generated files:")
    for scenario in scenarios:
        print(f"  - per_component_{scenario}.pgf")
        print(f"  - delta_type_{scenario}.pgf")
        print(f"  - delta_type_relative_{scenario}.pgf")
    print()
    print("To use in LaTeX:")
    print(r"  \usepackage{pgf}")
    print(r"  \input{per_component_MotorUpgrade.pgf}")
    print()


    #copy the directory output/figures to /Users/brdlcu/Documents/paper/2026/MEMOCODE/DynamicContract/assets/figures
    import shutil
    dest_dir = '/Users/brdlcu/Documents/paper/2026/MEMOCODE/DynamicContract/assets/figures'
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    for file_name in os.listdir(figures_dir):
        full_file_name = os.path.join(figures_dir, file_name)
        if os.path.isfile(full_file_name):
            shutil.copy(full_file_name, dest_dir)
    

if __name__ == '__main__':
    main()
