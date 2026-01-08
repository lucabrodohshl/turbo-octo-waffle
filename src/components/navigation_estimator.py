"""
NavigationEstimator component with 10-tier degradation model.

Inputs: control_error, motor_current, power_mode
Outputs: nav_position_error, nav_drift

Navigation quality degrades through 10 tiers activated by motor_current and power_mode.
Each tier progressively worsens position error and drift bounds.
"""

import pulp
from typing import Dict, List, Set
from .base import BaseComponent
from ..contracts import BehaviorSet, Box, Contract


class NavigationEstimator(BaseComponent):
    """
    Navigation estimator with 10-tier degradation model.
    
    Physics:
    - Tier k activates when: motor_current ≥ 4+2*k OR power_mode ≥ k/3
    - Each tier adds: +0.8 to pos_err bounds, +0.15 to drift bounds
    - Tier 0 (best): pos_err [0.5, 3.0], drift [0.0, 0.5]
    - Tier 9 (worst): pos_err [7.7, 10.2], drift [1.35, 1.85]
    """
    
    # Physical parameters
    NUM_TIERS = 10
    BASE_POS_ERR = (0.5, 3.0)  # Tier 0 position error bounds
    BASE_DRIFT = (0.0, 0.5)     # Tier 0 drift bounds
    POS_ERR_INCREMENT = 0.8     # Per-tier position error increase
    DRIFT_INCREMENT = 0.15      # Per-tier drift increase
    
    # Tier activation thresholds
    # Tier k: motor_current ≥ 4 + 2*k OR power_mode ≥ k/3
    CURRENT_BASE = 4.0
    CURRENT_STEP = 2.0
    MODE_DIVISOR = 3.0
    
    def __init__(self):
        inputs = {'control_error', 'motor_current', 'power_mode'}
        outputs = {'nav_position_error', 'nav_drift'}
        super().__init__('NavigationEstimator', inputs, outputs)
    
    def get_constraints(self,
                       input_vars: Dict[str, pulp.LpVariable],
                       output_vars: Dict[str, pulp.LpVariable]) -> List:
        """
        10-tier model with current and mode-based activation.
        """
        constraints = []
        M = 1000.0  # Big-M for logical constraints
        
        # === 10 quality tiers (0=best, 9=worst) ===
        tier_vars = [pulp.LpVariable(f"nav_tier_{k}", cat='Binary') for k in range(self.NUM_TIERS)]
        constraints.append(pulp.lpSum(tier_vars) == 1)
        
        # Tier level (0-9)
        tier_level = pulp.LpVariable("nav_tier_level", lowBound=0, upBound=9, cat='Integer')
        constraints.append(
            tier_level == pulp.lpSum(k * tier_vars[k] for k in range(self.NUM_TIERS))
        )
        
        # === Tier activation logic ===
        # Tier k activates when: motor_current ≥ (4 + 2*k) OR power_mode ≥ k/3
        # Must be in tier >= k if condition met
        
        for k in range(self.NUM_TIERS):
            current_threshold = self.CURRENT_BASE + self.CURRENT_STEP * k
            mode_threshold = k / self.MODE_DIVISOR
            
            # Binary: current exceeds threshold
            binary_current = pulp.LpVariable(f"nav_curr_tier_{k}", cat='Binary')
            constraints.append(
                input_vars['motor_current'] >= current_threshold - M * (1 - binary_current)
            )
            constraints.append(
                input_vars['motor_current'] <= current_threshold + M * binary_current
            )
            
            # Binary: mode exceeds threshold
            binary_mode = pulp.LpVariable(f"nav_mode_tier_{k}", cat='Binary')
            constraints.append(
                input_vars['power_mode'] >= mode_threshold - M * (1 - binary_mode)
            )
            constraints.append(
                input_vars['power_mode'] <= mode_threshold + M * binary_mode
            )
            
            # If either condition met, must be in tier >= k
            # tier_level >= k if (binary_current OR binary_mode)
            # Equivalent: tier_level >= k * max(binary_current, binary_mode)
            # Linear: tier_level >= k * (binary_current + binary_mode - binary_current * binary_mode)
            # Simplified: tier_level >= k if binary_current + binary_mode >= 1
            or_condition = pulp.LpVariable(f"nav_or_{k}", cat='Binary')
            constraints.append(or_condition >= binary_current)
            constraints.append(or_condition >= binary_mode)
            constraints.append(or_condition <= binary_current + binary_mode)
            constraints.append(
                tier_level >= k - M * (1 - or_condition)
            )
        
        # === Output bounds by tier ===
        # pos_err: [base_lower + k*increment, base_upper + k*increment]
        # drift: [base_lower + k*increment, base_upper + k*increment]
        
        for k in range(self.NUM_TIERS):
            pos_err_lower = self.BASE_POS_ERR[0] + k * self.POS_ERR_INCREMENT
            pos_err_upper = self.BASE_POS_ERR[1] + k * self.POS_ERR_INCREMENT
            drift_lower = self.BASE_DRIFT[0] + k * self.DRIFT_INCREMENT
            drift_upper = self.BASE_DRIFT[1] + k * self.DRIFT_INCREMENT
            
            # If tier k active, enforce bounds
            constraints.append(
                output_vars['nav_position_error'] >= pos_err_lower - M * (1 - tier_vars[k])
            )
            constraints.append(
                output_vars['nav_position_error'] <= pos_err_upper + M * (1 - tier_vars[k])
            )
            constraints.append(
                output_vars['nav_drift'] >= drift_lower - M * (1 - tier_vars[k])
            )
            constraints.append(
                output_vars['nav_drift'] <= drift_upper + M * (1 - tier_vars[k])
            )
        
        # Control error also influences position error (direct coupling)
        constraints.append(
            output_vars['nav_position_error'] >= 0.5 * input_vars['control_error']
        )
        
        # Global physical bounds
        constraints.append(output_vars['nav_position_error'] >= 0)
        constraints.append(output_vars['nav_position_error'] <= 50)
        constraints.append(output_vars['nav_drift'] >= 0)
        constraints.append(output_vars['nav_drift'] <= 10)
        
        return constraints
    
    @staticmethod
    def get_baseline_contract() -> Contract:
        """Baseline contract for NavigationEstimator at nominal conditions"""
        assumptions = BehaviorSet([
            Box({
                'control_error': (0.0, 15.0),
                'motor_current': (0.0, 15.0),  # Must fit Motor guarantee [0, 15]
                'power_mode': (0.0, 1.0)  # Must fit PowerManager guarantee [0, 1]
            })
        ])
        
        guarantees = BehaviorSet([
            Box({
                'nav_position_error': (0.5, 6.0),
                'nav_drift': (0.0, 1.0)
            })
        ])
        
        return Contract(assumptions, guarantees)
