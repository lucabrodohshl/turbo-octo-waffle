"""
Tests for MILP transformer failure handling.

Validates that the system fails fast when MILP solvers cannot find optimal solutions.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import pulp
from src.contracts import Box, BehaviorSet
from src.components.base import BaseComponent
from src.exceptions import MILPTransformFailure


class InfeasibleComponent(BaseComponent):
    """A component with intentionally infeasible constraints for testing."""
    
    def __init__(self):
        super().__init__(
            name="InfeasibleComp",
            inputs={'x'},
            outputs={'y'}
        )
    
    def get_constraints(self, input_vars, output_vars):
        """Return conflicting constraints that make the problem infeasible."""
        return [
            output_vars['y'] >= input_vars['x'] + 10,  # y >= x + 10
            output_vars['y'] <= input_vars['x'] - 10,  # y <= x - 10 (conflict!)
        ]


class UnboundedComponent(BaseComponent):
    """A component with unbounded optimization for testing."""
    
    def __init__(self):
        super().__init__(
            name="UnboundedComp",
            inputs={'x'},
            outputs={'y'}
        )
    
    def get_constraints(self, input_vars, output_vars):
        """Return no meaningful constraints, allowing unbounded solutions."""
        # No constraint relating y to x, so y can grow without bound
        return []


def test_infeasible_post_transformer():
    """Test that post transformer fails fast on infeasible problem."""
    comp = InfeasibleComponent()
    
    # Create an input box
    input_box = Box({'x': (0.0, 10.0)})
    input_behavior = BehaviorSet([input_box])
    
    # post() should raise MILPTransformFailure
    with pytest.raises(MILPTransformFailure) as exc_info:
        comp.post(input_behavior)
    
    # Check exception attributes
    exception = exc_info.value
    assert exception.component_name == "InfeasibleComp"
    assert exception.transformer_type == "post"
    assert exception.variable_being_optimized == "y"
    assert exception.solver_status_name in ["Infeasible", "Not Solved"]
    assert exception.input_region == {'x': (0.0, 10.0)}
    
    # Check that exception message is informative
    msg = str(exception)
    assert "InfeasibleComp" in msg
    assert "post" in msg
    assert "y" in msg


def test_infeasible_pre_transformer():
    """Test that pre transformer fails fast on infeasible problem."""
    comp = InfeasibleComponent()
    
    # Create an output box that's impossible to achieve
    output_box = Box({'y': (5.0, 15.0)})
    output_behavior = BehaviorSet([output_box])
    
    # pre() should raise MILPTransformFailure
    with pytest.raises(MILPTransformFailure) as exc_info:
        comp.pre(output_behavior)
    
    # Check exception attributes
    exception = exc_info.value
    assert exception.component_name == "InfeasibleComp"
    assert exception.transformer_type == "pre"
    assert exception.variable_being_optimized == "x"
    assert exception.output_region == {'y': (5.0, 15.0)}


def test_exception_to_dict():
    """Test that MILPTransformFailure can be serialized to dict."""
    exception = MILPTransformFailure(
        component_name="TestComponent",
        transformer_type="post",
        variable_being_optimized="output_var",
        optimization_direction="minimize",
        solver_status=pulp.LpStatusInfeasible,
        solver_status_name="Infeasible",
        input_region={'x': (0.0, 10.0), 'y': (5.0, 15.0)},
        iteration_number=3,
        edge_context=("Supplier", "Consumer", {"iface_var"}),
        solver_name="PULP_CBC_CMD",
    )
    
    data = exception.to_dict()
    
    # Verify all important fields are present
    assert data["component_name"] == "TestComponent"
    assert data["transformer_type"] == "post"
    assert data["variable_being_optimized"] == "output_var"
    assert data["optimization_direction"] == "minimize"
    assert data["solver_status_name"] == "Infeasible"
    assert data["iteration_number"] == 3
    assert data["solver_name"] == "PULP_CBC_CMD"
    
    # Check edge context
    assert "edge_context" in data
    assert data["edge_context"]["supplier"] == "Supplier"
    assert data["edge_context"]["consumer"] == "Consumer"
    assert "iface_var" in data["edge_context"]["interface_variables"]
    
    # Check input region
    assert "input_region" in data
    assert data["input_region"]["x"] == [0.0, 10.0]
    assert data["input_region"]["y"] == [5.0, 15.0]


def test_no_fallback_bounds():
    """Verify that no fallback bounds like -1000/1000 are used."""
    comp = InfeasibleComponent()
    
    input_box = Box({'x': (0.0, 10.0)})
    input_behavior = BehaviorSet([input_box])
    
    # Should raise exception, not return a box with fallback bounds
    try:
        result = comp.post(input_behavior)
        # If we got here, check that no fallback bounds are used
        # (but we expect an exception, so this should not be reached)
        for output_box in result.boxes:
            for var, (lb, ub) in output_box.as_dict.items():
                assert lb != -1000.0, "Fallback lower bound detected!"
                assert ub != 1000.0, "Fallback upper bound detected!"
                assert lb != -1000, "Fallback lower bound detected!"
                assert ub != 1000, "Fallback upper bound detected!"
    except MILPTransformFailure:
        # Expected behavior - test passes
        pass


class SimpleComponent(BaseComponent):
    """A simple feasible component for testing normal operation."""
    
    def __init__(self):
        super().__init__(
            name="SimpleComp",
            inputs={'x'},
            outputs={'y'}
        )
    
    def get_constraints(self, input_vars, output_vars):
        """Simple linear relationship: y = 2*x"""
        return [
            output_vars['y'] == 2 * input_vars['x']
        ]


def test_feasible_case_still_works():
    """Test that feasible problems still work correctly."""
    comp = SimpleComponent()
    
    input_box = Box({'x': (1.0, 5.0)})
    input_behavior = BehaviorSet([input_box])
    
    # This should work without raising an exception
    result = comp.post(input_behavior)
    
    # Check that output is correct
    assert not result.is_empty()
    assert len(result.boxes) == 1
    output_box = result.boxes[0]
    
    # y = 2*x, so y should be in [2, 10]
    y_bounds = output_box.as_dict['y']
    assert abs(y_bounds[0] - 2.0) < 0.01
    assert abs(y_bounds[1] - 10.0) < 0.01


if __name__ == '__main__':
    # Run tests
    print("Running MILP failure tests...")
    
    print("\n1. Testing infeasible post transformer...")
    try:
        test_infeasible_post_transformer()
        print("   ✓ Passed")
    except AssertionError as e:
        print(f"   ✗ Failed: {e}")
    
    print("\n2. Testing infeasible pre transformer...")
    try:
        test_infeasible_pre_transformer()
        print("   ✓ Passed")
    except AssertionError as e:
        print(f"   ✗ Failed: {e}")
    
    print("\n3. Testing exception serialization...")
    try:
        test_exception_to_dict()
        print("   ✓ Passed")
    except AssertionError as e:
        print(f"   ✗ Failed: {e}")
    
    print("\n4. Testing no fallback bounds...")
    try:
        test_no_fallback_bounds()
        print("   ✓ Passed")
    except AssertionError as e:
        print(f"   ✗ Failed: {e}")
    
    print("\n5. Testing feasible case...")
    try:
        test_feasible_case_still_works()
        print("   ✓ Passed")
    except AssertionError as e:
        print(f"   ✗ Failed: {e}")
    
    print("\nAll tests completed!")
