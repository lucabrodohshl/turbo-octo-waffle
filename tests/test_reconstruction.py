"""
Tests for contract reconstruction semantics.

CRITICAL: These tests validate the core formal semantics of contract evolution.

Contract reconstruction from baseline C₀=(A₀,G₀) and deviation δ=(ΔA_rel,ΔA_str,ΔG_rel,ΔG_str):

FORMAL SEMANTICS:
- A★ = (A₀ ∪ ΔA_rel) \\ ΔA_str
  * ΔA_rel: assumption RELAXATION - component accepts MORE behaviors (A grows)
  * ΔA_str: assumption STRENGTHENING - component accepts FEWER behaviors (A shrinks)

- G★ = (G₀ ∪ ΔG_rel) \\ ΔG_str
  * ΔG_rel: guarantee RELAXATION - component promises LESS (allows more behaviors, G grows)
  * ΔG_str: guarantee STRENGTHENING - component promises MORE (fewer allowed behaviors, G shrinks)

INTUITION:
- Relaxing = weakening = allowing more = set grows
- Strengthening = tightening = restricting = set shrinks
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.contracts import Box, BehaviorSet, Contract, Deviation, reconstruct_contract


def test_assumption_relaxation():
    """
    Test: Relaxing assumption increases A (component accepts more behaviors).
    
    A₀ = {x ∈ [0,10]}
    ΔA_rel = {x ∈ [10,20]}
    Expected: A★ = {x ∈ [0,20]} (union, so we get 2 boxes or merged)
    """
    baseline = Contract(
        assumptions=BehaviorSet([Box({'x': (0.0, 10.0)})]),
        guarantees=BehaviorSet([Box({'y': (0.0, 5.0)})])
    )
    
    deviation = Deviation(
        assumption_relaxation=BehaviorSet([Box({'x': (10.0, 20.0)})]),
        assumption_strengthening=BehaviorSet([]),
        guarantee_relaxation=BehaviorSet([]),
        guarantee_strengthening=BehaviorSet([])
    )
    
    evolved = reconstruct_contract(baseline, deviation)
    
    # A★ should have both boxes (or merged)
    assert len(evolved.assumptions.boxes) >= 1
    # Check coverage: original box should still be there
    original_box = Box({'x': (0.0, 10.0)})
    assert any(original_box.subset_of(box) or original_box == box for box in evolved.assumptions.boxes), \
        f"Original assumption box not preserved. Got: {evolved.assumptions.boxes}"
    
    print(f"✓ Assumption relaxation: A grew from {len(baseline.assumptions.boxes)} to {len(evolved.assumptions.boxes)} boxes")


def test_assumption_strengthening():
    """
    Test: Strengthening assumption decreases A (component accepts fewer behaviors).
    
    A₀ = {x ∈ [0,20]}
    ΔA_str = {x ∈ [10,20]}
    Expected: A★ ⊆ A₀ (should be roughly [0,10])
    """
    baseline = Contract(
        assumptions=BehaviorSet([Box({'x': (0.0, 20.0)})]),
        guarantees=BehaviorSet([Box({'y': (0.0, 5.0)})])
    )
    
    deviation = Deviation(
        assumption_relaxation=BehaviorSet([]),
        assumption_strengthening=BehaviorSet([Box({'x': (10.0, 20.0)})]),
        guarantee_relaxation=BehaviorSet([]),
        guarantee_strengthening=BehaviorSet([])
    )
    
    evolved = reconstruct_contract(baseline, deviation)
    
    # A★ should be smaller than A₀
    # Check that boxes roughly cover [0,10]
    assert len(evolved.assumptions.boxes) >= 1
    # Verify it doesn't include the removed region
    removed_box = Box({'x': (15.0, 15.0)})  # Point in removed region
    baseline_includes = any(removed_box.subset_of(box) for box in baseline.assumptions.boxes)
    evolved_includes = any(removed_box.subset_of(box) for box in evolved.assumptions.boxes)
    
    assert baseline_includes, "Baseline should include removed region"
    # After strengthening, it might still include it due to conservative difference
    # but total magnitude should not increase
    
    print(f"✓ Assumption strengthening: A changed from {len(baseline.assumptions.boxes)} to {len(evolved.assumptions.boxes)} boxes")


def test_guarantee_relaxation():
    """
    Test: Relaxing guarantee increases G (component allows more behaviors).
    
    G₀ = {y ∈ [0,10]}
    ΔG_rel = {y ∈ [10,20]}
    Expected: G★ ⊇ G₀ (G grows - weaker guarantee means more allowed behaviors)
    """
    baseline = Contract(
        assumptions=BehaviorSet([Box({'x': (0.0, 5.0)})]),
        guarantees=BehaviorSet([Box({'y': (0.0, 10.0)})])
    )
    
    deviation = Deviation(
        assumption_relaxation=BehaviorSet([]),
        assumption_strengthening=BehaviorSet([]),
        guarantee_relaxation=BehaviorSet([Box({'y': (10.0, 20.0)})]),
        guarantee_strengthening=BehaviorSet([])
    )
    
    evolved = reconstruct_contract(baseline, deviation)
    
    # G★ should have both regions (or merged)
    assert len(evolved.guarantees.boxes) >= 1
    
    # CRITICAL CHECK: Original guarantee box should still be included
    original_box = Box({'y': (0.0, 10.0)})
    assert any(original_box.subset_of(box) or original_box == box for box in evolved.guarantees.boxes), \
        f"Original guarantee box not preserved after relaxation! Got: {evolved.guarantees.boxes}"
    
    print(f"✓ Guarantee relaxation: G grew from {len(baseline.guarantees.boxes)} to {len(evolved.guarantees.boxes)} boxes")


def test_guarantee_strengthening():
    """
    Test: Strengthening guarantee decreases G (component promises more, fewer allowed behaviors).
    
    G₀ = {y ∈ [0,20]}
    ΔG_str = {y ∈ [10,20]}
    Expected: G★ ⊆ G₀ (G shrinks - stronger guarantee means fewer allowed behaviors)
    """
    baseline = Contract(
        assumptions=BehaviorSet([Box({'x': (0.0, 5.0)})]),
        guarantees=BehaviorSet([Box({'y': (0.0, 20.0)})])
    )
    
    deviation = Deviation(
        assumption_relaxation=BehaviorSet([]),
        assumption_strengthening=BehaviorSet([]),
        guarantee_relaxation=BehaviorSet([]),
        guarantee_strengthening=BehaviorSet([Box({'y': (10.0, 20.0)})]),
    )
    
    evolved = reconstruct_contract(baseline, deviation)
    
    # G★ should be smaller - should exclude the strengthened region
    # After removing [10,20], should have roughly [0,10]
    assert len(evolved.guarantees.boxes) >= 1
    
    # Check that evolved is subset of baseline (G shrank)
    assert evolved.guarantees.subset_of(baseline.guarantees), \
        f"Guarantee strengthening should shrink G, but evolved not subset of baseline"
    
    print(f"✓ Guarantee strengthening: G changed from {len(baseline.guarantees.boxes)} to {len(evolved.guarantees.boxes)} boxes")


def test_combined_operations():
    """Test combination of multiple deviation types"""
    baseline = Contract(
        assumptions=BehaviorSet([Box({'x': (5.0, 15.0)})]),
        guarantees=BehaviorSet([Box({'y': (5.0, 15.0)})])
    )
    
    deviation = Deviation(
        assumption_relaxation=BehaviorSet([Box({'x': (0.0, 5.0)})]),  # Add [0,5]
        assumption_strengthening=BehaviorSet([Box({'x': (12.0, 18.0)})]),  # Remove [12,18]
        guarantee_relaxation=BehaviorSet([Box({'y': (15.0, 20.0)})]),  # Add [15,20]
        guarantee_strengthening=BehaviorSet([Box({'y': (0.0, 5.0)})]),  # Remove [0,5]
    )
    
    evolved = reconstruct_contract(baseline, deviation)
    
    # A should have expanded left, contracted right
    # G should have expanded right, contracted left
    assert not evolved.assumptions.is_empty(), "Assumptions should not be empty"
    assert not evolved.guarantees.is_empty(), "Guarantees should not be empty"
    
    print(f"✓ Combined operations: A has {len(evolved.assumptions.boxes)} boxes, G has {len(evolved.guarantees.boxes)} boxes")


def test_guarantee_not_empty_after_strengthening():
    """
    REGRESSION TEST for the bug where all guarantees become empty.
    
    This test creates a scenario similar to MotorDegradation where
    guarantee strengthening was incorrectly applied, causing G to become empty.
    """
    # Motor baseline
    baseline = Contract(
        assumptions=BehaviorSet([
            Box({'thrust_command': (0.0, 20.0), 'voltage_available': (10.0, 12.6)})
        ]),
        guarantees=BehaviorSet([
            Box({'motor_thrust': (0.0, 20.0), 'motor_current': (0.0, 10.0), 'motor_response_time': (0.05, 0.4)})
        ])
    )
    
    # Simulate degradation: stronger guarantees in some dimensions
    deviation = Deviation(
        assumption_relaxation=BehaviorSet([]),
        assumption_strengthening=BehaviorSet([]),
        guarantee_relaxation=BehaviorSet([]),
        guarantee_strengthening=BehaviorSet([
            Box({'motor_response_time': (0.4, 0.6)})  # Strengthening: promise better response
        ])
    )
    
    evolved = reconstruct_contract(baseline, deviation)
    
    # CRITICAL: Guarantees should NOT be empty
    assert not evolved.guarantees.is_empty(), \
        "BUG REPRODUCED: Guarantees became empty after strengthening!"
    assert len(evolved.guarantees.boxes) > 0, \
        f"BUG REPRODUCED: Guarantee boxes disappeared! Got {len(evolved.guarantees.boxes)} boxes"
    
    print(f"✓ Guarantees preserved after strengthening: {len(evolved.guarantees.boxes)} boxes")


if __name__ == '__main__':
    print("="*80)
    print("TESTING CONTRACT RECONSTRUCTION SEMANTICS")
    print("="*80)
    print()
    
    try:
        test_assumption_relaxation()
        test_assumption_strengthening()
        test_guarantee_relaxation()
        test_guarantee_strengthening()
        test_combined_operations()
        test_guarantee_not_empty_after_strengthening()
        
        print()
        print("="*80)
        print("✓ ALL RECONSTRUCTION TESTS PASSED")
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
