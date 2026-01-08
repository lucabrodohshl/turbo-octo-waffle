"""
Motor Degradation Scenario - Primary Multi-Iteration Scenario.

Engineering narrative:
The Motor component's performance degrades, causing:
1. Worse response time (relaxed guarantee)
2. Higher current draw at same thrust (relaxed guarantee)

This triggers a complex propagation through the 3-node cycle:
FlightController → Motor → PowerManager → (Battery) → (back to PowerManager) → (back to Motor via voltage) → FlightController

The propagation requires multiple iterations because:
- Motor's degraded response time forces FlightController to strengthen assumptions
- FlightController's strengthened assumptions cause it to relax guarantees (worse control)
- Worse control error propagates to NavigationEstimator
- Higher motor current propagates to PowerManager
- PowerManager changes mode (enters ThrottleLimit), affecting voltage_available
- Reduced voltage feeds back to Motor, further degrading performance
- This creates a feedback loop requiring several iterations to stabilize

The scenario is parameterized to ensure ≥5 iterations by using piecewise boxes
that reveal constraints gradually through the iteration process.
"""

from ..network import ContractNetwork, ComponentNode, Interface
from ..contracts import Contract, BehaviorSet, Box
from ..components import FlightController, Motor, PowerManager, Battery, NavigationEstimator
from .base_scenario import Scenario


def create_motor_degradation_scenario() -> Scenario:
    """
    Create the motor degradation scenario with multi-iteration requirement.
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
    
    # Create interfaces forming the required 3-node cycle and additional connections
    # The main 3-NODE CYCLE: FlightController → Motor → PowerManager → FlightController
    # This is achieved by:
    # 1. FC commands Motor (thrust_command)
    # 2. Motor demands current from PM (motor_current)
    # 3. PM provides power mode/status back to FC (power_mode for FC awareness)
    
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
    
    # PowerManager → FlightController (power_mode for awareness)
    # THIS COMPLETES THE 3-NODE CYCLE: FC → Motor → PM → FC
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
    
    # Battery → NavigationEstimator (battery_soc)
    network.add_interface(Interface(
        supplier='Battery',
        consumer='NavigationEstimator',
        variables={'battery_soc'}
    ))
    
    # Define evolved contract for Motor (degraded performance)
    # The key is to use multiple boxes that represent piecewise degradation
    # This forces gradual revelation through iterations
    
    evolved_motor_contract = Contract(
        # Assumptions: same as baseline but we'll add some relaxation
        assumptions=BehaviorSet([
            Box({
                'thrust_command': (0.0, 20.0),
                'voltage_available': (10.0, 12.6)
            }),
            # Additional box for low voltage scenarios (revealed through iteration)
            Box({
                'thrust_command': (0.0, 15.0),
                'voltage_available': (9.5, 10.5)
            })
        ]),
        # Guarantees: degraded performance (relaxed)
        guarantees=BehaviorSet([
            # Normal operating region - slightly worse
            Box({
                'motor_thrust': (0.0, 18.0),  # Reduced from 20.0
                'motor_current': (0.0, 12.0),  # Increased from 10.0
                'motor_response_time': (0.08, 0.6)  # Worse from (0.05, 0.4)
            }),
            # High current region (new, revealed through iterations)
            Box({
                'motor_thrust': (10.0, 18.0),
                'motor_current': (8.0, 15.0),  # Higher current draw
                'motor_response_time': (0.3, 0.8)  # Much worse response
            }),
            # Low voltage operating region (new)
            Box({
                'motor_thrust': (0.0, 12.0),
                'motor_current': (0.0, 8.0),
                'motor_response_time': (0.2, 1.0)  # Degraded
            })
        ])
    )
    
    # Define system-level contract (this will NOT be satisfied)
    system_contract = Contract(
        assumptions=BehaviorSet([]),
        guarantees=BehaviorSet([
            Box({
                'control_error': (0.0, 10.0),  # Require good control
                'nav_position_error': (0.0, 8.0),  # Require good navigation
                'motor_response_time': (0.0, 0.5)  # Require good motor response
            })
        ])
    )
    
    return Scenario(
        name="MotorDegradation",
        description=(
            "Motor component degrades, causing worse response time and higher current draw. "
            "This triggers multi-iteration propagation through the FC→Motor→PM→Battery cycle. "
            "The degradation is modeled with piecewise boxes to ensure gradual convergence."
        ),
        network=network,
        target_component='Motor',
        target_contract=evolved_motor_contract,
        min_iterations_expected=5,
        system_level_contract=system_contract
    )
