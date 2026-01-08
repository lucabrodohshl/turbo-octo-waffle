"""
Contract Network representation and graph structure.
"""

from dataclasses import dataclass
from typing import Dict, List, Set, Optional
from .interface import Interface
from ..contracts import Contract


@dataclass
class ComponentNode:
    """
    A component node in the contract network.
    """
    name: str
    inputs: Set[str]  # Input variable names
    outputs: Set[str]  # Output variable names
    baseline_contract: Contract
    
    def all_variables(self) -> Set[str]:
        """Get all variables (inputs + outputs)"""
        return self.inputs | self.outputs


class ContractNetwork:
    """
    A Contract Network (CN) is a directed graph where:
    - Nodes are components with contracts
    - Edges are interfaces (shared variables)
    
    The network maintains the graph structure and provides queries.
    """
    
    def __init__(self):
        self.components: Dict[str, ComponentNode] = {}
        self.interfaces: List[Interface] = []
    
    def add_component(self, node: ComponentNode):
        """Add a component to the network"""
        self.components[node.name] = node
    
    def add_interface(self, interface: Interface):
        """Add an interface between components"""
        # Validate that components exist
        if interface.supplier not in self.components:
            raise ValueError(f"Supplier component '{interface.supplier}' not found")
        if interface.consumer not in self.components:
            raise ValueError(f"Consumer component '{interface.consumer}' not found")
        
        self.interfaces.append(interface)
    
    def get_component(self, name: str) -> Optional[ComponentNode]:
        """Get component by name"""
        return self.components.get(name)
    
    def get_suppliers(self, component: str) -> List[str]:
        """Get list of component names that supply to this component"""
        return [iface.supplier for iface in self.interfaces if iface.consumer == component]
    
    def get_consumers(self, component: str) -> List[str]:
        """Get list of component names that consume from this component"""
        return [iface.consumer for iface in self.interfaces if iface.supplier == component]
    
    def get_interface(self, supplier: str, consumer: str) -> Optional[Interface]:
        """Get interface between two components"""
        for iface in self.interfaces:
            if iface.supplier == supplier and iface.consumer == consumer:
                return iface
        return None
    
    def get_outgoing_interfaces(self, component: str) -> List[Interface]:
        """Get all interfaces where component is the supplier"""
        return [iface for iface in self.interfaces if iface.supplier == component]
    
    def get_incoming_interfaces(self, component: str) -> List[Interface]:
        """Get all interfaces where component is the consumer"""
        return [iface for iface in self.interfaces if iface.consumer == component]
    
    def find_strongly_connected_components(self) -> List[List[str]]:
        """
        Find all strongly connected components (SCCs) using Tarjan's algorithm.
        Returns list of SCCs, where each SCC is a list of component names.
        An SCC with size >= 2 indicates a cycle.
        """
        index_counter = [0]
        stack = []
        lowlink = {}
        index = {}
        on_stack = {}
        sccs = []
        
        def strongconnect(node: str):
            index[node] = index_counter[0]
            lowlink[node] = index_counter[0]
            index_counter[0] += 1
            stack.append(node)
            on_stack[node] = True
            
            # Consider successors
            for consumer in self.get_consumers(node):
                if consumer not in index:
                    strongconnect(consumer)
                    lowlink[node] = min(lowlink[node], lowlink[consumer])
                elif on_stack.get(consumer, False):
                    lowlink[node] = min(lowlink[node], index[consumer])
            
            # If node is a root, pop the stack and create SCC
            if lowlink[node] == index[node]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.append(w)
                    if w == node:
                        break
                sccs.append(sorted(scc))  # Sort for deterministic output
        
        for component in self.components:
            if component not in index:
                strongconnect(component)
        
        # Sort SCCs by size (largest first) for consistent ordering
        sccs.sort(key=lambda x: (-len(x), x[0]))
        return sccs
    
    def find_cycles(self) -> List[List[str]]:
        """
        Find cycles by returning SCCs with size >= 2.
        Maintained for backward compatibility.
        """
        sccs = self.find_strongly_connected_components()
        return [scc for scc in sccs if len(scc) >= 2]
    
    def has_cycle(self) -> bool:
        """Check if network has any cycles (SCCs with size >= 2)"""
        return any(len(scc) >= 2 for scc in self.find_strongly_connected_components())
    
    def __str__(self) -> str:
        return f"ContractNetwork({len(self.components)} components, {len(self.interfaces)} interfaces)"
    
    def detailed_str(self) -> str:
        """Detailed string representation"""
        lines = [f"Contract Network with {len(self.components)} components:"]
        
        for name, comp in sorted(self.components.items()):
            lines.append(f"  {name}:")
            lines.append(f"    Inputs: {{{', '.join(sorted(comp.inputs))}}}")
            lines.append(f"    Outputs: {{{', '.join(sorted(comp.outputs))}}}")
            lines.append(f"    Suppliers: {self.get_suppliers(name)}")
            lines.append(f"    Consumers: {self.get_consumers(name)}")
        
        lines.append(f"\nInterfaces ({len(self.interfaces)}):")
        for iface in self.interfaces:
            lines.append(f"  {iface}")
        
        cycles = self.find_cycles()
        if cycles:
            lines.append(f"\nCycles detected ({len(cycles)}):")
            for cycle in cycles[:5]:  # Show first 5
                lines.append(f"  {' → '.join(cycle)} → {cycle[0]}")
        else:
            lines.append("\nNo cycles detected.")
        
        return "\n".join(lines)
