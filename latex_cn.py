"""
Generate LaTeX/TikZ diagram of the contract network architecture.

This script reads the contract network structure from the scenario
and generates a TikZ diagram showing components and their interfaces.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.scenarios.motor_upgrade import create_motor_upgrade_scenario


def generate_tikz_network(output_file: str = "contract_network.tex"):
    """
    Generate TikZ diagram of the contract network.
    
    Args:
        output_file: Output LaTeX file path
    """
    
    # Load the scenario to get network structure
    scenario = create_motor_upgrade_scenario()
    network = scenario.network
    
    # Component positions (x, y) for nice layout
    positions = {
        'Battery': (0, 0),
        'PowerManager': (0, 2),
        'Motor': (3, 2),
        'FlightController': (6, 2),
        'NavigationEstimator': (6, 0)
    }
    
    # Start building LaTeX content
    latex_content = []
    latex_content.append(r"\begin{tikzpicture}[node distance=2cm]")
    latex_content.append("")
    latex_content.append("% --- COMPONENT NODES ---")
    
    # Generate nodes
    for comp_name in positions:
        x, y = positions[comp_name]
        # Use shorter labels for display
        display_name = {
            'Battery': 'Battery',
            'PowerManager': 'Power Manager',
            'Motor': 'Motor',
            'FlightController': 'Flight Controller',
            'NavigationEstimator': 'Navigation Estimator'
        }.get(comp_name, comp_name)
        
        latex_content.append(f"\\node[node] ({comp_name}) at ({x},{y}) {{{display_name}}};")
    
    latex_content.append("")
    latex_content.append("% --- INTERFACES ---")
    
    # Generate arrows for each interface
    arrow_num = 1
    for interface in network.interfaces:
        supplier = interface.supplier
        consumer = interface.consumer
        variables = ', '.join(sorted(interface.variables))
        
        # Add comment with variable names
        latex_content.append(f"% {supplier} -> {consumer}: {variables}")
        latex_content.append(f"\\ConArrow[{arrow_num}]{{{supplier}}}{{{consumer}}}")
        arrow_num += 1
    
    latex_content.append("")
    latex_content.append(r"\end{tikzpicture}")
    
    # Write to file
    with open(output_file, 'w') as f:
        f.write('\n'.join(latex_content))
    
    print(f"Generated TikZ diagram: {output_file}")
    print(f"  Components: {len(positions)}")
    print(f"  Interfaces: {len(network.interfaces)}")
    print()
    print("To use this in your LaTeX document, include:")
    print("  \\input{" + output_file + "}")
    print()
    print("Make sure you have the following in your preamble:")
    print(r"  \usepackage{tikz}")
    print(r"  \usetikzlibrary{positioning,arrows.meta}")
    print()
    print("And define the styles:")
    print(r"  \tikzset{")
    print(r"    node/.style={rectangle, draw=black, thick, minimum width=2cm, minimum height=0.8cm, align=center},")
    print(r"    envNode/.style={rectangle, draw=gray, thick, dashed, minimum width=2cm, minimum height=0.8cm, align=center},")
    print(r"    ConArrow/.style n args={3}{-{Stealth}, thick, shorten >=2pt, shorten <=2pt}")
    print(r"  }")
    print(r"  \newcommand{\ConArrow}[3][]{\draw[ConArrow] #2 -- #3;}")


def generate_full_latex_document(output_file: str = "contract_network_full.tex"):
    """
    Generate a complete standalone LaTeX document with the network diagram.
    
    Args:
        output_file: Output LaTeX file path
    """
    
    # Load the scenario to get network structure
    scenario = create_motor_upgrade_scenario()
    network = scenario.network
    
    # Component positions (x, y) for nice layout
    positions = {
        'Battery': (0, 0),
        'PowerManager': (2, 2.5),
        'Motor': (5, 2.5),
        'FlightController': (7.5, 1.25),
        'NavigationEstimator': (5, 0)
    }
    
    latex_doc = []
    latex_doc.append(r"\documentclass[border=10pt]{standalone}")
    latex_doc.append(r"\usepackage{tikz}")
    latex_doc.append(r"\usetikzlibrary{positioning,arrows.meta,shapes}")
    latex_doc.append("")
    latex_doc.append(r"\begin{document}")
    latex_doc.append("")
    latex_doc.append(r"\tikzset{")
    latex_doc.append(r"  node/.style={rectangle, draw=blue!60, fill=blue!5, thick, rounded corners, minimum width=2.5cm, minimum height=0.8cm, align=center, font=\small},")
    latex_doc.append(r"  envNode/.style={rectangle, draw=gray, fill=gray!10, thick, dashed, rounded corners, minimum width=2cm, minimum height=0.8cm, align=center, font=\small},")
    latex_doc.append(r"}")
    latex_doc.append("")
    latex_doc.append(r"\newcommand{\ConArrow}[3][]{\draw[-{Stealth}, thick, shorten >=2pt, shorten <=2pt] (#2) -- (#3);}")
    latex_doc.append("")
    latex_doc.append(r"\begin{tikzpicture}[node distance=2cm]")
    latex_doc.append("")
    latex_doc.append("% --- COMPONENT NODES ---")
    
    # Generate nodes
    for comp_name in positions:
        x, y = positions[comp_name]
        # Use shorter labels for display
        display_name = {
            'Battery': 'Battery',
            'PowerManager': 'Power\\\\Manager',
            'Motor': 'Motor',
            'FlightController': 'Flight\\\\Controller',
            'NavigationEstimator': 'Navigation\\\\Estimator'
        }.get(comp_name, comp_name)
        
        latex_doc.append(f"\\node[node] ({comp_name}) at ({x},{y}) {{{display_name}}};")
    
    latex_doc.append("")
    latex_doc.append("% --- INTERFACES (edges) ---")
    
    # Group interfaces for better visualization
    latex_doc.append("% Battery <-> PowerManager")
    for interface in network.interfaces:
        if (interface.supplier == 'Battery' and interface.consumer == 'PowerManager') or \
           (interface.supplier == 'PowerManager' and interface.consumer == 'Battery'):
            supplier = interface.supplier
            consumer = interface.consumer
            variables = ', '.join(sorted(interface.variables))
            latex_doc.append(f"% {variables}")
            latex_doc.append(f"\\ConArrow{{{supplier}}}{{{consumer}}}")
    
    latex_doc.append("")
    latex_doc.append("% PowerManager <-> Motor")
    for interface in network.interfaces:
        if (interface.supplier == 'PowerManager' and interface.consumer == 'Motor') or \
           (interface.supplier == 'Motor' and interface.consumer == 'PowerManager'):
            supplier = interface.supplier
            consumer = interface.consumer
            variables = ', '.join(sorted(interface.variables))
            latex_doc.append(f"% {variables}")
            latex_doc.append(f"\\ConArrow{{{supplier}}}{{{consumer}}}")
    
    latex_doc.append("")
    latex_doc.append("% Motor -> FlightController")
    for interface in network.interfaces:
        if interface.supplier == 'Motor' and interface.consumer == 'FlightController':
            variables = ', '.join(sorted(interface.variables))
            latex_doc.append(f"% {variables}")
            latex_doc.append(f"\\ConArrow{{Motor}}{{FlightController}}")
    
    latex_doc.append("")
    latex_doc.append("% PowerManager -> FlightController")
    for interface in network.interfaces:
        if interface.supplier == 'PowerManager' and interface.consumer == 'FlightController':
            variables = ', '.join(sorted(interface.variables))
            latex_doc.append(f"% {variables}")
            latex_doc.append(f"\\ConArrow{{PowerManager}}{{FlightController}}")
    
    latex_doc.append("")
    latex_doc.append("% FlightController <-> NavigationEstimator")
    for interface in network.interfaces:
        if (interface.supplier == 'FlightController' and interface.consumer == 'NavigationEstimator') or \
           (interface.supplier == 'NavigationEstimator' and interface.consumer == 'FlightController'):
            supplier = interface.supplier
            consumer = interface.consumer
            variables = ', '.join(sorted(interface.variables))
            latex_doc.append(f"% {variables}")
            latex_doc.append(f"\\ConArrow{{{supplier}}}{{{consumer}}}")
    
    latex_doc.append("")
    latex_doc.append("% Motor -> NavigationEstimator")
    for interface in network.interfaces:
        if interface.supplier == 'Motor' and interface.consumer == 'NavigationEstimator':
            variables = ', '.join(sorted(interface.variables))
            latex_doc.append(f"% {variables}")
            latex_doc.append(f"\\ConArrow{{Motor}}{{NavigationEstimator}}")
    
    latex_doc.append("")
    latex_doc.append("% PowerManager -> NavigationEstimator")
    for interface in network.interfaces:
        if interface.supplier == 'PowerManager' and interface.consumer == 'NavigationEstimator':
            variables = ', '.join(sorted(interface.variables))
            latex_doc.append(f"% {variables}")
            latex_doc.append(f"\\ConArrow{{PowerManager}}{{NavigationEstimator}}")
    
    latex_doc.append("")
    latex_doc.append(r"\end{tikzpicture}")
    latex_doc.append(r"\end{document}")
    
    # Write to file
    with open(output_file, 'w') as f:
        f.write('\n'.join(latex_doc))
    
    print(f"\nGenerated standalone LaTeX document: {output_file}")
    print(f"  Components: {len(positions)}")
    print(f"  Interfaces: {len(network.interfaces)}")
    print()
    print("Compile with:")
    print(f"  pdflatex {output_file}")
    print()
    
    # Print interface summary
    print("Network Interface Summary:")
    print("="*60)
    for interface in network.interfaces:
        variables = ', '.join(sorted(interface.variables))
        print(f"  {interface.supplier:20s} -> {interface.consumer:20s}: {variables}")


if __name__ == "__main__":
    # Generate both versions
    generate_tikz_network("contract_network.tex")
    generate_full_latex_document("contract_network_full.tex")
