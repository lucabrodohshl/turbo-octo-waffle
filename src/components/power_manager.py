"""
PowerManager component with 4 discrete protection modes.

Inputs: motor_current, battery_voltage, battery_current
Outputs: voltage_available, power_mode, voltage_margin

PowerManager regulates voltage delivery based on voltage margin thresholds.
4 modes: Normal (0), ThrottleLimit (1), Brownout (2), Emergency (3).
"""

import pulp
from typing import Dict, List, Set
from .base import BaseComponent
from ..contracts import BehaviorSet, Box, Contract


class PowerManager(BaseComponent):
    """
    Power management with 4 discrete protection modes based on voltage margin.
    
    Physics:
    - voltage_available = battery_voltage - 0.08*motor_current
    - voltage_margin = voltage_available - V_min (V_min = 10.2V)
    - Mode selection: ≥0.6 → 0, [0.3,0.6) → 1, [0.1,0.3) → 2, <0.1 → 3
    - Battery current coupling: battery_current ≥ motor_current + I_base
    """
    
    # Physical parameters
    R_MOTOR = 0.08  # Motor path resistance (ohms)
    I_BASE = 2.0   # Base avionics current (A)
    V_MIN = 10.2   # Minimum safe voltage (V)
    
    # Mode thresholds (voltage margin in volts)
    MODE_THRESHOLDS = [(0.6, float('inf')), (0.3, 0.6), (0.1, 0.3), (float('-inf'), 0.1)]
    
    def __init__(self):
        inputs = {'motor_current', 'battery_voltage', 'battery_current'}
        outputs = {'voltage_available', 'power_mode', 'voltage_margin'}
        super().__init__('PowerManager', inputs, outputs)
    
    def get_constraints(self,
                       input_vars: Dict[str, pulp.LpVariable],
                       output_vars: Dict[str, pulp.LpVariable]) -> List:
        """
        4 discrete modes with binary encoding and voltage margin thresholds.
        """
        constraints = []
        M = 1000.0  # Big-M for logical constraints
        
        # === Voltage delivery ===
        # voltage_available = battery_voltage - R_motor * motor_current
        constraints.append(
            output_vars['voltage_available'] == input_vars['battery_voltage'] - 
            self.R_MOTOR * input_vars['motor_current']
        )
        
        # === Battery current coupling ===
        # battery_current must supply motor_current plus base avionics load
        constraints.append(
            input_vars['battery_current'] >= input_vars['motor_current'] + self.I_BASE
        )
        
        # === Voltage margin ===
        # voltage_margin = voltage_available - V_min
        constraints.append(
            output_vars['voltage_margin'] == output_vars['voltage_available'] - self.V_MIN
        )
        
        # === 4 discrete modes based on voltage margin ===
        # Modes: 0=Normal, 1=ThrottleLimit, 2=Brownout, 3=Emergency
        mode_vars = [pulp.LpVariable(f"pm_mode_{i}", cat='Binary') for i in range(4)]
        constraints.append(pulp.lpSum(mode_vars) == 1)
        constraints.append(
            output_vars['power_mode'] == pulp.lpSum(i * mode_vars[i] for i in range(4))
        )
        
        # Apply mode threshold constraints
        # Mode 0: margin >= 0.6
        constraints.append(
            output_vars['voltage_margin'] >= 0.6 - M * (1 - mode_vars[0])
        )
        
        # Mode 1: 0.3 <= margin < 0.6
        constraints.append(
            output_vars['voltage_margin'] >= 0.3 - M * (1 - mode_vars[1])
        )
        constraints.append(
            output_vars['voltage_margin'] <= 0.6 + M * (1 - mode_vars[1])
        )
        
        # Mode 2: 0.1 <= margin < 0.3
        constraints.append(
            output_vars['voltage_margin'] >= 0.1 - M * (1 - mode_vars[2])
        )
        constraints.append(
            output_vars['voltage_margin'] <= 0.3 + M * (1 - mode_vars[2])
        )
        
        # Mode 3: margin < 0.1
        constraints.append(
            output_vars['voltage_margin'] <= 0.1 + M * (1 - mode_vars[3])
        )
        
        # Physical bounds
        constraints.append(output_vars['voltage_available'] >= 9.0)
        constraints.append(output_vars['voltage_available'] <= 12.6)
        constraints.append(output_vars['voltage_margin'] >= -1.2)
        constraints.append(output_vars['voltage_margin'] <= 2.4)
        constraints.append(output_vars['power_mode'] >= 0)
        constraints.append(output_vars['power_mode'] <= 3)
        
        return constraints
    
    @staticmethod
    def get_baseline_contract() -> Contract:
        """Baseline contract for PowerManager at nominal conditions"""
        assumptions = BehaviorSet([
            Box({
                'motor_current': (0.0, 15.0),  # Match Motor guarantee range
                'battery_voltage': (11.5, 12.6),
                'battery_current': (0.0, 30.0)
            })
        ])
        
        guarantees = BehaviorSet([
            Box({
                'voltage_available': (10.5, 12.6),
                'power_mode': (0.0, 1.0),
                'voltage_margin': (0.3, 2.4)
            })
        ])
        
        return Contract(assumptions, guarantees)
