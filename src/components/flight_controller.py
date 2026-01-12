"""
FlightController component with mode-dependent thrust authority.

Inputs: motor_thrust, motor_response_time, nav_position_error, power_mode
Outputs: thrust_command, control_error

Flight controller with mode-dependent thrust authority limits and saturation tracking.
Control error includes nav error + response time effects + saturation slack.
"""

import pulp
from typing import Dict, List, Set
from .base import BaseComponent
from ..contracts import BehaviorSet, Box, Contract


class FlightController(BaseComponent):
    """
    Flight controller with 4-mode thrust authority limits.
    
    Physics:
    - Demanded thrust: thrust_demand = 2.0 * nav_position_error
    - Authority limits by mode: 100/85/65/45 for modes 0/1/2/3
    - Actual command: thrust_command = min(thrust_demand, authority_limit)
    - Saturation slack: slack = max(0, thrust_demand - thrust_command)
    - Control error: nav_error + 5*response_time + 0.2*slack
    """
    
    # Physical parameters
    K_NAV_TO_THRUST = 2.0  # Nav error to thrust gain
    K_RESPONSE_ERROR = 5.0  # Response time to control error gain
    K_SATURATION_ERROR = 0.2  # Saturation slack to control error gain
    K_THRUST_TRACKING_ERROR = 0.3  # Thrust tracking error gain
    
    # Mode-dependent thrust authority limits (percentage of max)
    MODE_AUTHORITY = {0: 100.0, 1: 85.0, 2: 65.0, 3: 45.0}
    
    def __init__(self):
        inputs = {'motor_thrust', 'motor_response_time', 'nav_position_error', 'power_mode'}
        outputs = {'thrust_command', 'control_error'}
        super().__init__('FlightController', inputs, outputs)
    
    def get_constraints(self,
                       input_vars: Dict[str, pulp.LpVariable],
                       output_vars: Dict[str, pulp.LpVariable]) -> List:
        """
        Mode-dependent thrust authority with saturation tracking.
        """
        constraints = []
        M = 1000.0  # Big-M for logical constraints
        
        # === Demanded thrust from navigation error ===
        thrust_demand = pulp.LpVariable("fc_thrust_demand", lowBound=0, upBound=200)
        constraints.append(
            thrust_demand == self.K_NAV_TO_THRUST * input_vars['nav_position_error']
        )
        
        # === Mode-dependent authority limits ===
        # 4 modes: 0=Normal, 1=ThrottleLimit, 2=Brownout, 3=Emergency
        mode_vars = [pulp.LpVariable(f"fc_mode_{i}", cat='Binary') for i in range(4)]
        constraints.append(pulp.lpSum(mode_vars) == 1)
        constraints.append(
            input_vars['power_mode'] == pulp.lpSum(i * mode_vars[i] for i in range(4))
        )
        
        # Apply authority limit for active mode
        for mode, authority in self.MODE_AUTHORITY.items():
            constraints.append(
                output_vars['thrust_command'] <= authority + M * (1 - mode_vars[mode])
            )
        
        # thrust_command also limited by demand
        constraints.append(
            output_vars['thrust_command'] <= thrust_demand
        )
        constraints.append(
            output_vars['thrust_command'] >= 0
        )
        
        # === Saturation slack ===
        # slack = max(0, thrust_demand - thrust_command)
        saturation_slack = pulp.LpVariable("fc_saturation_slack", lowBound=0)
        constraints.append(
            saturation_slack >= thrust_demand - output_vars['thrust_command']
        )
        constraints.append(
            saturation_slack >= 0
        )
        
        # === Thrust tracking error ===
        # Account for difference between commanded and actual motor thrust
        thrust_tracking_error = pulp.LpVariable("fc_thrust_tracking_error", lowBound=0)
        constraints.append(
            thrust_tracking_error >= output_vars['thrust_command'] - input_vars['motor_thrust']
        )
        constraints.append(
            thrust_tracking_error >= input_vars['motor_thrust'] - output_vars['thrust_command']
        )
        
        # Bounds on motor_thrust (physical limits of the motor system)
        constraints.append(input_vars['motor_thrust'] >= 0)
        constraints.append(input_vars['motor_thrust'] <= 100)
        
        # Bounds on motor_response_time (physical motor dynamics)
        constraints.append(input_vars['motor_response_time'] >= 0)
        constraints.append(input_vars['motor_response_time'] <= 2.0)
        
        # Bounds on nav_position_error (navigation system range)
        constraints.append(input_vars['nav_position_error'] >= 0)
        constraints.append(input_vars['nav_position_error'] <= 50)
        
        # === Control error composition ===
        # control_error = nav_error + K_response * response_time + K_sat * slack + K_tracking * tracking_error
        constraints.append(
            output_vars['control_error'] >= input_vars['nav_position_error'] +
            self.K_RESPONSE_ERROR * input_vars['motor_response_time'] +
            self.K_SATURATION_ERROR * saturation_slack +
            self.K_THRUST_TRACKING_ERROR * thrust_tracking_error
        )
        constraints.append(
            output_vars['control_error'] <= input_vars['nav_position_error'] +
            self.K_RESPONSE_ERROR * input_vars['motor_response_time'] +
            self.K_SATURATION_ERROR * saturation_slack +
            self.K_THRUST_TRACKING_ERROR * thrust_tracking_error + 0.5
        )
        
        # Physical bounds
        constraints.append(output_vars['thrust_command'] >= 0)
        constraints.append(output_vars['thrust_command'] <= 100)
        constraints.append(output_vars['control_error'] >= 0)
        constraints.append(output_vars['control_error'] <= 100)
        
        return constraints
    
    @staticmethod
    def get_baseline_contract() -> Contract:
        """Baseline contract for FlightController at nominal conditions"""
        assumptions = BehaviorSet([
            Box({
                'motor_thrust': (0.0, 25.0),
                'motor_response_time': (0.05, 0.5),
                'nav_position_error': (0.5, 5.0),  # Updated to match NavigationEstimator baseline
                'power_mode': (0.0, 1.0)
            })
        ])
        
        guarantees = BehaviorSet([
            Box({
                'thrust_command': (0.0, 30.0),
                'control_error': (0.0, 15.0)
            })
        ])
        
        return Contract(assumptions, guarantees)
