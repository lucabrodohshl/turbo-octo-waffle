"""
Battery component with realistic 3S LiPo physics.

Inputs: power_mode
Outputs: battery_voltage, battery_current, battery_soc

Models SOC-dependent open-circuit voltage with internal resistance sag.
"""

import pulp
from typing import Dict, List, Set
from .base import BaseComponent
from ..contracts import BehaviorSet, Box, Contract


class Battery(BaseComponent):
    """
    3S LiPo battery with SOC-dependent voltage and mode-dependent current limits.
    
    Physics:
    - Open-circuit voltage V_oc varies with SOC (piecewise linear)
    - Loaded voltage = V_oc - R_int * I
    - Current limits depend on protection mode
    """
    
    # Physical parameters (3S LiPo)
    R_INT = 0.06  # Internal resistance (ohms)
    I_BASE = 2.0  # Base avionics current draw (A)
    
    # V_oc(SOC) piecewise linear breakpoints
    VOC_BREAKPOINTS = [(20, 10.8), (40, 11.1), (60, 11.4), (80, 12.0), (100, 12.6)]
    
    # Mode-dependent current caps (A)
    MODE_CURRENT_CAPS = {0: 40.0, 1: 30.0, 2: 22.0, 3: 15.0}
    
    def __init__(self):
        inputs = {'power_mode'}
        outputs = {'battery_voltage', 'battery_current', 'battery_soc'}
        super().__init__('Battery', inputs, outputs)
    
    def get_constraints(self,
                       input_vars: Dict[str, pulp.LpVariable],
                       output_vars: Dict[str, pulp.LpVariable]) -> List:
        """
        Constraints implementing 3S LiPo physics with mode-dependent protection.
        """
        constraints = []
        M = 1000.0  # Big-M for logical constraints
        
        # SOC bounds
        constraints.append(output_vars['battery_soc'] >= 20)
        constraints.append(output_vars['battery_soc'] <= 100)
        
        # Current bounds (mode-dependent, implemented below)
        constraints.append(output_vars['battery_current'] >= 0)
        constraints.append(output_vars['battery_current'] <= 40)  # Global max
        
        # === V_oc(SOC) piecewise linear implementation ===
        # Use 5 binary variables for 5 segments
        num_segments = len(self.VOC_BREAKPOINTS) - 1
        segment_vars = [pulp.LpVariable(f"voc_seg_{i}", cat='Binary') for i in range(num_segments)]
        lambda_vars = [pulp.LpVariable(f"voc_lambda_{i}", lowBound=0, upBound=1) for i in range(len(self.VOC_BREAKPOINTS))]
        
        # SOS2 constraint: at most 2 adjacent lambdas can be nonzero
        constraints.append(pulp.lpSum(lambda_vars) == 1)
        
        # Link lambdas to segments
        for i in range(num_segments):
            constraints.append(lambda_vars[i] + lambda_vars[i+1] >= segment_vars[i])
        constraints.append(pulp.lpSum(segment_vars) == 1)
        
        # SOC from breakpoints
        constraints.append(
            output_vars['battery_soc'] == pulp.lpSum(
                lambda_vars[i] * self.VOC_BREAKPOINTS[i][0] for i in range(len(self.VOC_BREAKPOINTS))
            )
        )
        
        # V_oc from breakpoints
        V_oc = pulp.LpVariable("battery_V_oc", lowBound=10.8, upBound=12.6)
        constraints.append(
            V_oc == pulp.lpSum(
                lambda_vars[i] * self.VOC_BREAKPOINTS[i][1] for i in range(len(self.VOC_BREAKPOINTS))
            )
        )
        
        # === Loaded voltage with internal resistance ===
        # battery_voltage = V_oc - R_int * battery_current
        constraints.append(
            output_vars['battery_voltage'] == V_oc - self.R_INT * output_vars['battery_current']
        )
        
        # === Mode-dependent current limits ===
        # 4 modes: 0=Normal, 1=ThrottleLimit, 2=Brownout, 3=Emergency
        mode_vars = [pulp.LpVariable(f"bat_mode_{i}", cat='Binary') for i in range(4)]
        constraints.append(pulp.lpSum(mode_vars) == 1)
        constraints.append(
            input_vars['power_mode'] == pulp.lpSum(i * mode_vars[i] for i in range(4))
        )
        
        # Apply current cap for active mode
        for mode, cap in self.MODE_CURRENT_CAPS.items():
            constraints.append(
                output_vars['battery_current'] <= cap + M * (1 - mode_vars[mode])
            )
        
        # Physical bounds on inputs
        constraints.append(input_vars['power_mode'] >= 0)
        constraints.append(input_vars['power_mode'] <= 3)
        
        # Physical bounds on outputs
        constraints.append(output_vars['battery_voltage'] >= 9.5)
        constraints.append(output_vars['battery_voltage'] <= 12.6)
        
        return constraints
    
    @staticmethod
    def get_baseline_contract() -> Contract:
        """Baseline contract for Battery at nominal conditions"""
        assumptions = BehaviorSet([
            Box({'power_mode': (0.0, 1.0)})  # Normal to ThrottleLimit
        ])
        
        guarantees = BehaviorSet([
            Box({
                'battery_voltage': (11.5, 12.6),
                'battery_current': (0.0, 30.0),
                'battery_soc': (60.0, 100.0)
            })
        ])
        
        return Contract(assumptions, guarantees)
