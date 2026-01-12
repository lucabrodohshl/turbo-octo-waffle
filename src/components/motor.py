"""
Motor component with voltage-dependent efficiency.

Inputs: thrust_command, voltage_available
Outputs: motor_thrust, motor_current, motor_response_time

Motor efficiency varies with voltage (3 bands), current draw depends on thrust and voltage deficit.
Response time degrades with low voltage and high current.
"""

import pulp
from typing import Dict, List, Set
from .base import BaseComponent
from ..contracts import BehaviorSet, Box, Contract


class Motor(BaseComponent):
    """
    Motor with voltage-dependent efficiency (3 bands).
    
    Physics:
    - Efficiency η(V): V≥11.5 → 1.0, V∈[10.5,11.5) → 0.9, V<10.5 → 0.8
    - Current: I = (T + 2*max(0, V_nom - V)) / (V/12)
    - Response time: t = 0.05 + 0.05*(12-V) + 0.01*I
    """
    
    # Physical parameters
    V_NOM = 12.0  # Nominal voltage (V)
    T_BASE_RESPONSE = 0.05  # Base response time (s)
    K_VOLTAGE_RESPONSE = 0.05  # Response time coefficient for voltage (s/V)
    K_CURRENT_RESPONSE = 0.01  # Response time coefficient for current (s/A)
    
    # Efficiency bands (V_threshold, eta)
    EFF_BANDS = [(11.5, 1.0), (10.5, 0.9), (0.0, 0.8)]
    
    def __init__(self):
        inputs = {'thrust_command', 'voltage_available'}
        outputs = {'motor_thrust', 'motor_current', 'motor_response_time'}
        super().__init__('Motor', inputs, outputs)
    
    def get_constraints(self,
                       input_vars: Dict[str, pulp.LpVariable],
                       output_vars: Dict[str, pulp.LpVariable]) -> List:
        """
        3-band voltage-dependent efficiency with physical coupling.
        """
        constraints = []
        M = 1000.0  # Big-M for logical constraints
        
        # === 3 voltage bands with binary selection ===
        band_vars = [pulp.LpVariable(f"motor_band_{i}", cat='Binary') for i in range(3)]
        constraints.append(pulp.lpSum(band_vars) == 1)
        
        # Band 0: V >= 11.5 (eta = 1.0)
        constraints.append(
            input_vars['voltage_available'] >= 11.5 - M * (1 - band_vars[0])
        )
        
        # Band 1: 10.5 <= V < 11.5 (eta = 0.9)
        constraints.append(
            input_vars['voltage_available'] >= 10.5 - M * (1 - band_vars[1])
        )
        constraints.append(
            input_vars['voltage_available'] <= 11.5 + M * (1 - band_vars[1])
        )
        
        # Band 2: V < 10.5 (eta = 0.8)
        constraints.append(
            input_vars['voltage_available'] <= 10.5 + M * (1 - band_vars[2])
        )
        
        # === Thrust output with efficiency ===
        # motor_thrust = eta * thrust_command
        # Implement as: motor_thrust = sum(band_vars[i] * EFF_BANDS[i][1]) * thrust_command
        # But this is bilinear, so use Big-M:
        for i, (v_thresh, eta) in enumerate(self.EFF_BANDS):
            constraints.append(
                output_vars['motor_thrust'] <= eta * input_vars['thrust_command'] + M * (1 - band_vars[i])
            )
            constraints.append(
                output_vars['motor_thrust'] >= eta * input_vars['thrust_command'] - M * (1 - band_vars[i])
            )
        
        # === Voltage deficit coupling ===
        # Voltage deficit increases current draw
        voltage_deficit = pulp.LpVariable("motor_voltage_deficit", lowBound=0)
        constraints.append(
            voltage_deficit >= self.V_NOM - input_vars['voltage_available']
        )
        constraints.append(
            voltage_deficit >= 0
        )
        
        # === Current draw ===
        # I = (T + 2 * voltage_deficit) / (V / 12)
        # Linearized: I ≈ (T + 2*deficit) * (12/V) ≈ (T + 2*deficit) * (1 + (12-V)/12)
        # Approximate as: I = 0.5*T + 2*deficit + 0.02*T*(12-V)
        # Simpler: I = 0.5*motor_thrust + 2*voltage_deficit
        constraints.append(
            output_vars['motor_current'] >= 0.5 * output_vars['motor_thrust'] + 2.0 * voltage_deficit
        )
        constraints.append(
            output_vars['motor_current'] <= 0.6 * output_vars['motor_thrust'] + 2.5 * voltage_deficit + 1.0
        )
        
        # === Response time with voltage and current coupling ===
        # motor_response_time = T_base + K_V * (V_nom - V) + K_I * I
        constraints.append(
            output_vars['motor_response_time'] >= self.T_BASE_RESPONSE + 
            self.K_VOLTAGE_RESPONSE * (self.V_NOM - input_vars['voltage_available']) +
            self.K_CURRENT_RESPONSE * output_vars['motor_current']
        )
        constraints.append(
            output_vars['motor_response_time'] <= self.T_BASE_RESPONSE + 
            self.K_VOLTAGE_RESPONSE * (self.V_NOM - input_vars['voltage_available']) +
            self.K_CURRENT_RESPONSE * output_vars['motor_current'] + 0.05
        )
        
        # Physical bounds on inputs
        constraints.append(input_vars['thrust_command'] >= 0)
        constraints.append(input_vars['thrust_command'] <= 100)
        constraints.append(input_vars['voltage_available'] >= 8.0)
        constraints.append(input_vars['voltage_available'] <= 13.0)
        
        # Physical bounds on outputs
        constraints.append(output_vars['motor_thrust'] >= 0)
        constraints.append(output_vars['motor_thrust'] <= 100)
        constraints.append(output_vars['motor_current'] >= 0)
        constraints.append(output_vars['motor_current'] <= 50)
        constraints.append(output_vars['motor_response_time'] >= 0.01)
        constraints.append(output_vars['motor_response_time'] <= 3.0)
        
        return constraints
    
    @staticmethod
    def get_baseline_contract() -> Contract:
        """Baseline contract for Motor at nominal conditions"""
        assumptions = BehaviorSet([
            Box({
                'thrust_command': (0.0, 30.0),  # Match FC guarantee range
                'voltage_available': (10.5, 12.6)
            })
        ])
        
        guarantees = BehaviorSet([
            Box({
                'motor_thrust': (0.0, 25.0),
                'motor_current': (0.0, 15.0),
                'motor_response_time': (0.05, 0.5)
            })
        ])
        
        return Contract(assumptions, guarantees)
