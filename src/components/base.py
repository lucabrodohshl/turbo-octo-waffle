"""Base component class with optimization-based post/pre transformers."""

from abc import ABC, abstractmethod
from typing import Set, Dict, Tuple, List, Optional
import pulp
from ..contracts import BehaviorSet, Box


class BaseComponent(ABC):
    """
    Base class for components with optimization-based post/pre transformers.
    
    Each component has:
    - Input and output variables
    - A set of constraints (linear or MILP)
    - post() and pre() methods that solve real optimization problems
    """
    
    def __init__(self, name: str, inputs: Set[str], outputs: Set[str]):
        self.name = name
        self.inputs = inputs
        self.outputs = outputs
        # Use CBC with timeout
        try:
            if pulp.GUROBI_CMD().available():
                self.solver = pulp.GUROBI_CMD(msg=0, timeLimit=5)
            else:
                self.solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=5)
        except:
            self.solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=5)
    
    @abstractmethod
    def get_constraints(self, 
                       input_vars: Dict[str, pulp.LpVariable],
                       output_vars: Dict[str, pulp.LpVariable]) -> List:
        """
        Return list of constraints for this component.
        Constraints relate input and output variables.
        """
        pass
    
    def post(self, input_behaviors: BehaviorSet) -> BehaviorSet:
        """
        Post transformer: compute output behaviors from input behaviors.
        
        For each input box, solve optimization to find min/max of each output variable.
        """
        if input_behaviors.is_empty():
            return BehaviorSet([])
        
        output_boxes = []
        
        for input_box in input_behaviors.boxes:
            output_box = self._compute_output_box(input_box)
            if output_box is not None:
                output_boxes.append(output_box)
        
        return BehaviorSet(output_boxes)
    
    def _compute_output_box(self, input_box: Box) -> Optional[Box]:
        """
        Compute output box from single input box using optimization.
        For each output variable, solve min and max.
        """
        # Create optimization problem
        prob = pulp.LpProblem(f"{self.name}_post", pulp.LpMinimize)
        
        # Create variables
        input_vars = {var: pulp.LpVariable(f"in_{var}", lowBound=None, upBound=None)
                      for var in self.inputs}
        output_vars = {var: pulp.LpVariable(f"out_{var}", lowBound=None, upBound=None)
                       for var in self.outputs}
        
        # Add component constraints
        constraints = self.get_constraints(input_vars, output_vars)
        for i, constraint in enumerate(constraints):
            prob += constraint, f"constraint_{i}"
        
        # Add input box bounds
        input_dict = input_box.as_dict
        for var in self.inputs:
            if var in input_dict:
                lb, ub = input_dict[var]
                prob += input_vars[var] >= lb, f"input_{var}_lb"
                prob += input_vars[var] <= ub, f"input_{var}_ub"
        
        # Solve for each output variable bounds
        output_bounds = {}
        
        for out_var in self.outputs:
            # Minimize
            prob.sense = pulp.LpMinimize
            prob.setObjective(output_vars[out_var])
            
            try:
                prob.solve(self.solver)
                if prob.status == pulp.LpStatusOptimal:
                    min_val = pulp.value(output_vars[out_var])
                else:
                    # Infeasible or unbounded - use conservative bounds
                    min_val = -1000.0
            except:
                min_val = -1000.0
            
            # Maximize
            prob.sense = pulp.LpMaximize
            prob.setObjective(output_vars[out_var])
            
            try:
                prob.solve(self.solver)
                if prob.status == pulp.LpStatusOptimal:
                    max_val = pulp.value(output_vars[out_var])
                else:
                    max_val = 1000.0
            except:
                max_val = 1000.0
            
            output_bounds[out_var] = (min_val, max_val)
        
        if not output_bounds:
            return None
        
        return Box(output_bounds)
    
    def pre(self, output_behaviors: BehaviorSet) -> BehaviorSet:
        """
        Pre transformer: compute input behaviors that can lead to output behaviors.
        
        For each output box, solve optimization to find min/max of each input variable.
        """
        if output_behaviors.is_empty():
            return BehaviorSet([])
        
        input_boxes = []
        
        for output_box in output_behaviors.boxes:
            input_box = self._compute_input_box(output_box)
            if input_box is not None:
                input_boxes.append(input_box)
        
        return BehaviorSet(input_boxes)
    
    def _compute_input_box(self, output_box: Box) -> Optional[Box]:
        """
        Compute input box from single output box using optimization.
        For each input variable, solve min and max.
        """
        # Create optimization problem
        prob = pulp.LpProblem(f"{self.name}_pre", pulp.LpMinimize)
        
        # Create variables
        input_vars = {var: pulp.LpVariable(f"in_{var}", lowBound=None, upBound=None)
                      for var in self.inputs}
        output_vars = {var: pulp.LpVariable(f"out_{var}", lowBound=None, upBound=None)
                       for var in self.outputs}
        
        # Add component constraints
        constraints = self.get_constraints(input_vars, output_vars)
        for i, constraint in enumerate(constraints):
            prob += constraint, f"constraint_{i}"
        
        # Add output box bounds
        output_dict = output_box.as_dict
        for var in self.outputs:
            if var in output_dict:
                lb, ub = output_dict[var]
                prob += output_vars[var] >= lb, f"output_{var}_lb"
                prob += output_vars[var] <= ub, f"output_{var}_ub"
        
        # Solve for each input variable bounds
        input_bounds = {}
        
        for in_var in self.inputs:
            # Minimize
            prob.sense = pulp.LpMinimize
            prob.setObjective(input_vars[in_var])
            
            try:
                prob.solve(self.solver)
                if prob.status == pulp.LpStatusOptimal:
                    min_val = pulp.value(input_vars[in_var])
                else:
                    min_val = -1000.0
            except:
                min_val = -1000.0
            
            # Maximize
            prob.sense = pulp.LpMaximize
            prob.setObjective(input_vars[in_var])
            
            try:
                prob.solve(self.solver)
                if prob.status == pulp.LpStatusOptimal:
                    max_val = pulp.value(input_vars[in_var])
                else:
                    max_val = 1000.0
            except:
                max_val = 1000.0
            
            input_bounds[in_var] = (min_val, max_val)
        
        if not input_bounds:
            return None
        
        return Box(input_bounds)
