"""
Tests for well-formedness checking and network properties.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.contracts import Box, BehaviorSet, Contract
from src.network import ContractNetwork, ComponentNode, Interface, WellFormednessChecker


def test_three_node_cycle_detection():
    """Test that 3-node SCC is detected correctly using strongly connected components"""
    network = ContractNetwork()
    
    # Create simple 3-node cycle: A → B → C → A
    for name in ['A', 'B', 'C']:
        network.add_component(ComponentNode(
            name=name,
            inputs={'in'},
            outputs={'out'},
            baseline_contract=Contract(
                assumptions=BehaviorSet([Box({'in': (0.0, 10.0)})]),
                guarantees=BehaviorSet([Box({'out': (0.0, 10.0)})])
            )
        ))
    
    network.add_interface(Interface('A', 'B', {'out'}))
    network.add_interface(Interface('B', 'C', {'out'}))
    network.add_interface(Interface('C', 'A', {'out'}))
    
    # Test SCC detection
    sccs = network.find_strongly_connected_components()
    cyclic_sccs = [scc for scc in sccs if len(scc) >= 2]
    
    assert len(cyclic_sccs) > 0, "No cyclic SCCs detected!"
    
    # Should find the 3-node SCC
    three_node_sccs = [scc for scc in cyclic_sccs if len(scc) == 3]
    assert len(three_node_sccs) > 0, f"No 3-node SCC found! Got SCCs: {sccs}"
    
    # Verify it contains the expected nodes
    scc_nodes = set(three_node_sccs[0])
    assert scc_nodes == {'A', 'B', 'C'}, f"Wrong nodes in SCC: {scc_nodes}"
    
    # Backward compatibility: find_cycles should also work
    cycles = network.find_cycles()
    assert len(cycles) > 0, "find_cycles() returned empty!"
    
    print(f"✓ 3-node SCC detected: {three_node_sccs[0]}")
    print(f"✓ All SCCs: {sccs}")
    print(f"✓ Backward compatible cycles: {cycles}")


def test_well_formedness_pass():
    """Test well-formedness check passing case"""
    network = ContractNetwork()
    
    # Create A → B where A.G ⊇ B.A (compatible)
    network.add_component(ComponentNode(
        name='A',
        inputs=set(),
        outputs={'x'},
        baseline_contract=Contract(
            assumptions=BehaviorSet([]),
            guarantees=BehaviorSet([Box({'x': (0.0, 20.0)})])  # Wide guarantee
        )
    ))
    
    network.add_component(ComponentNode(
        name='B',
        inputs={'x'},
        outputs={'y'},
        baseline_contract=Contract(
            assumptions=BehaviorSet([Box({'x': (5.0, 15.0)})]),  # Narrow assumption
            guarantees=BehaviorSet([Box({'y': (0.0, 10.0)})])
        )
    ))
    
    network.add_interface(Interface('A', 'B', {'x'}))
    
    contracts = {
        'A': network.get_component('A').baseline_contract,
        'B': network.get_component('B').baseline_contract
    }
    
    checker = WellFormednessChecker(network)
    result = checker.check(contracts)
    
    # Debug output
    if not result.passed:
        print(f"DEBUG: Test failed with details: {result.details}")
        # Check manually
        a_g = contracts['A'].guarantees
        b_a = contracts['B'].assumptions
        print(f"DEBUG: A guarantees: {a_g.boxes}")
        print(f"DEBUG: B assumptions: {b_a.boxes}")
        print(f"DEBUG: B.A subset of A.G? {b_a.subset_of(a_g)}")
    
    assert result.passed, f"Should pass but failed: {result.message}\nDetails: {result.details}"
    print(f"✓ Well-formedness check passed correctly")


def test_well_formedness_fail():
    """Test well-formedness check failing case"""
    network = ContractNetwork()
    
    # Create A → B where A.G ⊄ B.A (incompatible)
    network.add_component(ComponentNode(
        name='A',
        inputs=set(),
        outputs={'x'},
        baseline_contract=Contract(
            assumptions=BehaviorSet([]),
            guarantees=BehaviorSet([Box({'x': (5.0, 15.0)})])  # Narrow guarantee
        )
    ))
    
    network.add_component(ComponentNode(
        name='B',
        inputs={'x'},
        outputs={'y'},
        baseline_contract=Contract(
            assumptions=BehaviorSet([Box({'x': (0.0, 20.0)})]),  # Wide assumption
            guarantees=BehaviorSet([Box({'y': (0.0, 10.0)})])
        )
    ))
    
    network.add_interface(Interface('A', 'B', {'x'}))
    
    contracts = {
        'A': network.get_component('A').baseline_contract,
        'B': network.get_component('B').baseline_contract
    }
    
    checker = WellFormednessChecker(network)
    result = checker.check(contracts)
    
    assert not result.passed, "Should fail but passed!"
    assert len(result.details) > 0, "Should have failure details"
    print(f"✓ Well-formedness check failed correctly: {result.details[0]}")


if __name__ == '__main__':
    print("="*80)
    print("TESTING WELL-FORMEDNESS AND NETWORK PROPERTIES")
    print("="*80)
    print()
    
    try:
        test_three_node_cycle_detection()
        test_well_formedness_pass()
        test_well_formedness_fail()
        
        print()
        print("="*80)
        print("✓ ALL NETWORK TESTS PASSED")
        print("="*80)
    except AssertionError as e:
        print()
        print("="*80)
        print("✗ TEST FAILED")
        print("="*80)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def test_specific_3node_cycle_selection():
    """Test that the specific FC→Motor→PM cycle is correctly identified"""
    print("\nTest: Specific 3-node cycle selection (FC→Motor→PM)")
    print("-" * 80)
    
    network = ContractNetwork()
    
    # Create a network with the target 3-node cycle
    network.add_component(ComponentNode(
        name='FlightController',
        inputs={'motor_thrust'},
        outputs={'thrust_command'},
        baseline_contract=Contract(
            assumptions=BehaviorSet([Box({'motor_thrust': (0.0, 20.0)})]),
            guarantees=BehaviorSet([Box({'thrust_command': (0.0, 20.0)})])
        )
    ))
    
    network.add_component(ComponentNode(
        name='Motor',
        inputs={'thrust_command'},
        outputs={'motor_thrust', 'motor_current'},
        baseline_contract=Contract(
            assumptions=BehaviorSet([Box({'thrust_command': (0.0, 20.0)})]),
            guarantees=BehaviorSet([Box({'motor_thrust': (0.0, 20.0), 'motor_current': (0.0, 10.0)})])
        )
    ))
    
    network.add_component(ComponentNode(
        name='PowerManager',
        inputs={'motor_current'},
        outputs={'power_mode'},
        baseline_contract=Contract(
            assumptions=BehaviorSet([Box({'motor_current': (0.0, 10.0)})]),
            guarantees=BehaviorSet([Box({'power_mode': (0.0, 1.0)})])
        )
    ))
    
    # Add another component to create additional cycles
    network.add_component(ComponentNode(
        name='Battery',
        inputs={'power_mode'},
        outputs={'battery_voltage'},
        baseline_contract=Contract(
            assumptions=BehaviorSet([Box({'power_mode': (0.0, 1.0)})]),
            guarantees=BehaviorSet([Box({'battery_voltage': (11.0, 12.6)})])
        )
    ))
    
    # Create interfaces forming FC→Motor→PM→FC cycle
    network.add_interface(Interface('FlightController', 'Motor', {'thrust_command'}))
    network.add_interface(Interface('Motor', 'FlightController', {'motor_thrust'}))
    network.add_interface(Interface('Motor', 'PowerManager', {'motor_current'}))
    network.add_interface(Interface('PowerManager', 'FlightController', {'power_mode'}))
    
    # Add Battery in a chain
    network.add_interface(Interface('PowerManager', 'Battery', {'power_mode'}))
    
    # Find cycles
    cycles = network.find_cycles()
    
    # Check that we have at least one cycle
    assert len(cycles) > 0, "No cycles found"
    
    # Check for 3-node cycles
    three_node_cycles = [c for c in cycles if len(c) == 3]
    assert len(three_node_cycles) > 0, f"No 3-node cycles found. All cycles: {cycles}"
    
    # Check that the target cycle is present (any rotation)
    target_nodes = {'FlightController', 'Motor', 'PowerManager'}
    found_target_cycle = any(set(cycle) == target_nodes for cycle in three_node_cycles)
    
    assert found_target_cycle, f"Target 3-node cycle not found. Found cycles: {three_node_cycles}"
    
    print(f"✓ Found {len(three_node_cycles)} 3-node cycle(s)")
    print(f"✓ Target cycle FC→Motor→PM present: {three_node_cycles}")
    print("="*80)


if __name__ == '__main__':
    try:
        test_three_node_cycle_detection()
        test_well_formedness_pass()
        test_well_formedness_fail()
        test_specific_3node_cycle_selection()
        
        print("\n" + "="*80)
        print("✓ ALL NETWORK TESTS PASSED")
        print("="*80)
    except AssertionError as e:
        print(e)
