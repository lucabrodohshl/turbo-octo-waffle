"""
Motor Upgrade Scenario - Pure Backward Propagation Demonstration.

Engineering narrative:
The motor is UPGRADED to a better model with improved performance characteristics.
The new motor has:
  - STRICTER ASSUMPTIONS (ΔA_str): Requires more precise inputs (narrower ranges)
  - STRICTER GUARANTEES (ΔG_str): Provides better performance (tighter bounds)

Physical interpretation:
- High-quality motor with tighter tolerances
- Requires cleaner power supply (narrower voltage range)
- Requires more precise control commands (narrower thrust range)
- Delivers better response time and more predictable current draw

Propagation pattern (BACKWARD through ΔA_str):
1. Upgraded Motor has stricter assumptions (ΔA_str) - demands better inputs
2. PowerManager must strengthen guarantees (ΔG_str) to meet motor's needs
3. PowerManager's pre() computes ΔA_str (needs better battery inputs)
4. Battery must strengthen guarantees (ΔG_str) to meet PM's needs
5. Backward propagation continues until all upstream components adapted

This scenario demonstrates PURE BACKWARD PROPAGATION:
  - Only ΔA_str and ΔG_str (no relaxation)
  - Only backward propagation (no forward)
  - Well-formedness restored through upstream strengthening
  - Target 3-5 iterations through backward cascade
"""

from ..network import ContractNetwork, ComponentNode, Interface
from ..contracts import Contract, BehaviorSet, Box
from ..components import FlightController, Motor, PowerManager, Battery, NavigationEstimator
from .base_scenario import Scenario


def create_motor_upgrade_scenario() -> Scenario:
    """
    Create the motor upgrade scenario (pure backward propagation).
    """
    
    # Create contract network
    network = ContractNetwork()
    
    # Create components with baseline contracts
    fc = FlightController()
    motor = Motor()
    pm = PowerManager()
    battery = Battery()
    nav = NavigationEstimator()
    
    # Add components to network
    network.add_component(ComponentNode(
        name='FlightController',
        inputs=fc.inputs,
        outputs=fc.outputs,
        baseline_contract=FlightController.get_baseline_contract()
    ))
    
    network.add_component(ComponentNode(
        name='Motor',
        inputs=motor.inputs,
        outputs=motor.outputs,
        baseline_contract=Motor.get_baseline_contract()
    ))
    
    network.add_component(ComponentNode(
        name='PowerManager',
        inputs=pm.inputs,
        outputs=pm.outputs,
        baseline_contract=PowerManager.get_baseline_contract()
    ))
    
    network.add_component(ComponentNode(
        name='Battery',
        inputs=battery.inputs,
        outputs=battery.outputs,
        baseline_contract=Battery.get_baseline_contract()
    ))
    
    network.add_component(ComponentNode(
        name='NavigationEstimator',
        inputs=nav.inputs,
        outputs=nav.outputs,
        baseline_contract=NavigationEstimator.get_baseline_contract()
    ))
    
    # Create interfaces forming the network
    # Main data flow: Nav → FC → Motor → PM → Battery
    
    # FlightController → Motor (thrust_command)
    network.add_interface(Interface(
        supplier='FlightController',
        consumer='Motor',
        variables={'thrust_command'}
    ))
    
    # Motor → FlightController (motor_thrust, motor_response_time)
    network.add_interface(Interface(
        supplier='Motor',
        consumer='FlightController',
        variables={'motor_thrust', 'motor_response_time'}
    ))
    
    # Motor → PowerManager (motor_current)
    network.add_interface(Interface(
        supplier='Motor',
        consumer='PowerManager',
        variables={'motor_current'}
    ))
    
    # PowerManager → Motor (voltage_available)
    network.add_interface(Interface(
        supplier='PowerManager',
        consumer='Motor',
        variables={'voltage_available'}
    ))
    
    # PowerManager → FlightController (power_mode)
    network.add_interface(Interface(
        supplier='PowerManager',
        consumer='FlightController',
        variables={'power_mode'}
    ))
    
    # Battery → PowerManager (battery_voltage, battery_current)
    network.add_interface(Interface(
        supplier='Battery',
        consumer='PowerManager',
        variables={'battery_voltage', 'battery_current'}
    ))
    
    # PowerManager → Battery (power_mode)
    network.add_interface(Interface(
        supplier='PowerManager',
        consumer='Battery',
        variables={'power_mode'}
    ))
    
    # NavigationEstimator → FlightController (nav_position_error)
    network.add_interface(Interface(
        supplier='NavigationEstimator',
        consumer='FlightController',
        variables={'nav_position_error'}
    ))
    
    # FlightController → NavigationEstimator (control_error)
    network.add_interface(Interface(
        supplier='FlightController',
        consumer='NavigationEstimator',
        variables={'control_error'}
    ))
    
    # Motor → NavigationEstimator (motor_current)
    network.add_interface(Interface(
        supplier='Motor',
        consumer='NavigationEstimator',
        variables={'motor_current'}
    ))
    
    # PowerManager → NavigationEstimator (power_mode)
    network.add_interface(Interface(
        supplier='PowerManager',
        consumer='NavigationEstimator',
        variables={'power_mode'}
    ))
    
    # Define UPGRADED contract for Motor
    # KEY: Both assumptions AND guarantees are STRENGTHENED (narrower ranges)
    # 
    # Baseline Motor assumptions: thrust_command ∈ [0, 30], voltage_available ∈ [10.5, 12.6]
    # Baseline Motor guarantees: motor_thrust ∈ [0, 25], motor_current ∈ [0, 15], response_time ∈ [0.05, 0.5]
    #
    # Upgraded Motor:
    # - ΔA_str: Removes acceptance of extreme values (stricter requirements)
    # - ΔG_str: Removes allowance of poor performance (better guarantees)
    
    upgraded_motor_contract = Contract(
        # STRICTER ASSUMPTIONS (ΔA_str): Upgraded motor is more demanding
        # Requires narrower voltage range (high quality power)
        # Requires narrower thrust command range (precise control)
        assumptions=BehaviorSet([
            Box({
                'thrust_command': (5.0, 25.0),      # Stricter: was [0, 30], now narrower
                'voltage_available': (11.5, 12.6)   # Stricter: was [10.5, 12.6], now only high voltage
            })
        ]),
        # STRICTER GUARANTEES (ΔG_str): Upgraded motor performs better
        # Tighter current draw bounds (more efficient)
        # Tighter response time bounds (more responsive)
        # Tighter thrust output bounds (more predictable)
        guarantees=BehaviorSet([
            Box({
                'motor_thrust': (5.0, 25.0),          # Stricter: was [0, 25], no zero-thrust region
                'motor_current': (2.0, 12.0),         # Stricter: was [0, 15], narrower range
                'motor_response_time': (0.08, 0.35)   # Stricter: was [0.05, 0.5], tighter bounds
            })
        ])
    )
    
    # Define system-level contract (should be satisfied after upgrade)
    system_contract = Contract(
        assumptions=BehaviorSet([]),
        guarantees=BehaviorSet([
            Box({
                'control_error': (0.0, 15.0),
                'nav_position_error': (0.0, 8.0),
                'motor_response_time': (0.0, 0.4),    # Achievable with upgrade
                'battery_voltage': (11.0, 12.6)       # Requires good battery
            })
        ])
    )
    
    return Scenario(
        name="MotorUpgrade",
        description=(
            "Motor is UPGRADED to a better model with stricter assumptions (ΔA_str) and "
            "stricter guarantees (ΔG_str). The upgraded motor requires higher quality inputs "
            "(narrower voltage and thrust ranges) but delivers better performance (tighter "
            "response time and current bounds). This triggers BACKWARD PROPAGATION: Motor's "
            "ΔA_str forces PowerManager to strengthen guarantees (ΔG_str), which forces Battery "
            "to strengthen guarantees, propagating upstream to restore well-formedness. "
            "Demonstrates pure backward cascade through ΔA_str → ΔG_str propagation."
        ),
        network=network,
        target_component='Motor',
        target_contract=upgraded_motor_contract,
        min_iterations_expected=3,  # Target 3-5 iterations for backward propagation
        system_level_contract=system_contract
    )
