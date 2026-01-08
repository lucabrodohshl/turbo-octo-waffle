"""
Contract network diagram visualization.

Creates a directed graph showing components, interfaces, and cycles.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import networkx as nx
from typing import Dict, List
from ..network import ContractNetwork
from ..contracts import DeviationMap


def draw_contract_network(network: ContractNetwork,
                          deviation_map: DeviationMap,
                          output_path: str,
                          title: str = "Contract Network"):
    """
    Draw contract network diagram showing components and interfaces.
    
    Args:
        network: The contract network to visualize
        deviation_map: Deviation map to show which components changed
        output_path: Path to save the figure
        title: Title for the diagram
    """
    
    # Create directed graph
    G = nx.DiGraph()
    
    # Add nodes (components)
    for comp_name in network.components.keys():
        G.add_node(comp_name)
    
    # Add edges (interfaces)
    cycle_edges = set()
    selected_scc = None
    
    # Find strongly connected components (SCCs)
    sccs = network.find_strongly_connected_components()
    
    # Select the main cycle SCC using the following priority:
    # 1. SCC containing {FlightController, Motor, PowerManager} with size >= 3
    # 2. Any SCC with size >= 3
    # 3. Largest SCC with size >= 2
    if sccs:
        target_nodes = {'FlightController', 'Motor', 'PowerManager'}
        
        # Priority 1: SCC with target nodes and size >= 3
        for scc in sccs:
            if len(scc) >= 3 and target_nodes.issubset(set(scc)):
                selected_scc = scc
                break
        
        # Priority 2: Any SCC with size >= 3
        if not selected_scc:
            for scc in sccs:
                if len(scc) >= 3:
                    selected_scc = scc
                    break
        
        # Priority 3: Largest SCC with size >= 2 (already sorted by size)
        if not selected_scc:
            for scc in sccs:
                if len(scc) >= 2:
                    selected_scc = scc
                    break
        
        # Mark all edges within the selected SCC as cycle edges
        if selected_scc:
            scc_set = set(selected_scc)
            for iface in network.interfaces:
                if iface.supplier in scc_set and iface.consumer in scc_set:
                    cycle_edges.add((iface.supplier, iface.consumer))
    
    for iface in network.interfaces:
        G.add_edge(iface.supplier, iface.consumer)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set_title(title, fontsize=16, fontweight='bold')
    ax.axis('off')
    
    # Layout - use hierarchical layout if possible, otherwise spring
    try:
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    except:
        pos = nx.circular_layout(G)
    
    # Determine node colors based on deviation magnitude
    node_colors = []
    node_sizes = []
    
    for node in G.nodes():
        deviation = deviation_map.get_deviation(node)
        magnitude = deviation.total_magnitude()
        
        if magnitude > 10:
            color = '#ff6b6b'  # Red - high change
            size = 3000
        elif magnitude > 5:
            color = '#ffd93d'  # Yellow - medium change
            size = 2500
        elif magnitude > 0:
            color = '#a8dadc'  # Light blue - small change
            size = 2000
        else:
            color = '#e0e0e0'  # Gray - no change
            size = 1800
        
        node_colors.append(color)
        node_sizes.append(size)
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes,
                          alpha=0.9, ax=ax)
    
    # Draw node labels
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', ax=ax)
    
    # Draw edges with different styles for cycle edges
    regular_edges = [e for e in G.edges() if e not in cycle_edges]
    cycle_edge_list = [e for e in G.edges() if e in cycle_edges]
    
    # Draw regular edges
    if regular_edges:
        nx.draw_networkx_edges(G, pos, edgelist=regular_edges,
                              edge_color='#666666', width=2, alpha=0.6,
                              arrows=True, arrowsize=20, ax=ax,
                              arrowstyle='->', connectionstyle='arc3,rad=0.1')
    
    # Draw cycle edges (highlighted)
    if cycle_edge_list:
        nx.draw_networkx_edges(G, pos, edgelist=cycle_edge_list,
                              edge_color='#e63946', width=3, alpha=0.8,
                              arrows=True, arrowsize=25, ax=ax,
                              arrowstyle='->', connectionstyle='arc3,rad=0.1')
    
    # Add legend
    legend_elements = [
        mpatches.Patch(color='#ff6b6b', label='High change (>10 boxes)'),
        mpatches.Patch(color='#ffd93d', label='Medium change (5-10 boxes)'),
        mpatches.Patch(color='#a8dadc', label='Small change (<5 boxes)'),
        mpatches.Patch(color='#e0e0e0', label='No change'),
        mpatches.Patch(color='#e63946', label='Cycle edge')
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=10)
    
    # Add cycle annotation (SCC-based)
    if selected_scc:
        # Show SCC nodes in sorted order
        scc_nodes = sorted(selected_scc)
        scc_str = ', '.join(scc_nodes)
        scc_size = len(selected_scc)
        ax.text(0.5, 0.02, f"Main Cycle SCC ({scc_size} nodes): {{{scc_str}}}",
               transform=ax.transAxes, ha='center', fontsize=10,
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Network diagram saved to {output_path}")
