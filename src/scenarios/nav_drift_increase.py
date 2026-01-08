"""
Navigation Drift Increase Scenario - Secondary Scenario.

Engineering narrative:
The NavigationEstimator's sensors degrade, causing worse navigation performance.
This is modeled as GUARANTEE RELAXATION (ΔG_rel) - the component now provides
weaker guarantees (allows larger position errors and drift).

Physical interpretation:
- Degraded sensors → less accurate position estimates
- Sensor noise increases → higher nav_position_error
- Drift accumulation worsens → higher nav_drift  
- Guarantees are relaxed to accommodate degraded performance

Propagation pattern (FORWARD through ΔG_rel):
1. NavigationEstimator's relaxed guarantees (worse position errors) propagate forward
2. FlightController receives worse nav_position_error → ΔA_rel (must accept worse inputs)
3. FlightController relaxes assumptions → post() computes ΔG_rel (worse control_error, higher thrust)
4. Motor receives worse inputs → ΔA_rel, then ΔG_rel (higher current, worse response)
5. PowerManager receives higher current → ΔA_rel, then ΔG_rel (worse modes, lower voltage)
6. Lower voltage cycles back to Motor → further degradation through 3-node SCC
7. Cycle repeats through FC→Motor→PM→FC with progressive tier activation

The 10-tier model in NavigationEstimator responds to control_error feedback,
creating stepwise activation through ~5-10 iterations as the degradation cascades
through the SCC. Designed to achieve final well-formedness through bounded relaxation.
"""

from ..network import ContractNetwork, ComponentNode, Interface
from ..contracts import Contract, BehaviorSet, Box
from ..components import FlightController, Motor, PowerManager, Battery, NavigationEstimator
from .base_scenario import Scenario


def create_nav_drift_scenario() -> Scenario:
    """
    Create the navigation drift increase scenario.
    """
    
    # Create contract network (same structure as motor degradation)
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
    
    # Create interfaces (same as motor degradation scenario - includes 3-node cycle)
    # 3-NODE CYCLE: FlightController → Motor → PowerManager → FlightController
    network.add_interface(Interface(
        supplier='FlightController',
        consumer='Motor',
        variables={'thrust_command'}
    ))
    
    network.add_interface(Interface(
        supplier='Motor',
        consumer='FlightController',
        variables={'motor_thrust', 'motor_response_time'}
    ))
    
    network.add_interface(Interface(
        supplier='Motor',
        consumer='PowerManager',
        variables={'motor_current'}
    ))
    
    network.add_interface(Interface(
        supplier='PowerManager',
        consumer='Motor',
        variables={'voltage_available'}
    ))
    
    # COMPLETES 3-NODE CYCLE
    network.add_interface(Interface(
        supplier='PowerManager',
        consumer='FlightController',
        variables={'power_mode'}
    ))
    
    network.add_interface(Interface(
        supplier='Battery',
        consumer='PowerManager',
        variables={'battery_voltage', 'battery_current'}
    ))
    
    network.add_interface(Interface(
        supplier='PowerManager',
        consumer='Battery',
        variables={'power_mode'}
    ))
    
    network.add_interface(Interface(
        supplier='NavigationEstimator',
        consumer='FlightController',
        variables={'nav_position_error'}
    ))
    
    network.add_interface(Interface(
        supplier='FlightController',
        consumer='NavigationEstimator',
        variables={'control_error'}
    ))
    
    # NEW: Connect Motor current to NavigationEstimator for tier activation
    network.add_interface(Interface(
        supplier='Motor',
        consumer='NavigationEstimator',
        variables={'motor_current'}
    ))
    
    # NEW: Connect PowerManager mode to NavigationEstimator for tier activation
    network.add_interface(Interface(
        supplier='PowerManager',
        consumer='NavigationEstimator',
        variables={'power_mode'}
    ))
    
    # Define evolved contract for NavigationEstimator (worse performance via GUARANTEE RELAXATION)
    # KEY STRATEGY: Use ΔG_rel (guarantee relaxation) to model sensor degradation
    # Forward propagation: ΔG_rel → ΔA_rel → ΔG_rel through the network
    # 
    # Baseline guarantees: nav_position_error ∈ [0.5, 6], nav_drift ∈ [0, 1]
    # Evolved guarantees: RELAX (widen) to allow worse performance
    evolved_nav_contract = Contract(
        # Assumptions: Keep within supplier ranges for well-formedness
        assumptions=BehaviorSet([
            Box({
                'control_error': (0.0, 15.0),     # Within FC baseline guarantee
                'motor_current': (0.0, 15.0),     # Within Motor baseline guarantee
                'power_mode': (0.0, 1.0)          # Within PM baseline guarantee
            })
        ]),
        # Guarantees: RELAX to allow worse navigation performance (staged for progression)
        guarantees=BehaviorSet([
            # Stage 1: Modest degradation (tier 0-3)
            Box({
                'nav_position_error': (0.5, 8.0),   # Relaxed from [0.5, 6]
                'nav_drift': (0.0, 1.5)             # Relaxed from [0, 1]
            }),
            # Stage 2: Moderate degradation (tier 4-6)
            Box({
                'nav_position_error': (5.0, 12.0),
                'nav_drift': (0.8, 2.5)
            }),
            # Stage 3: High degradation (tier 7-9)
            Box({
                'nav_position_error': (8.0, 15.0),
                'nav_drift': (1.5, 3.5)
            })
        ])
    )
    
    # Define system-level contract
    # Should accommodate evolved navigation performance
    system_contract = Contract(
        assumptions=BehaviorSet([]),
        guarantees=BehaviorSet([
            Box({
                'nav_position_error': (0.0, 12.0),  # Allow evolved degradation
                'control_error': (0.0, 20.0),       # Allow increased control effort
                'nav_drift': (0.0, 3.0),            # Accommodate drift increase
                'motor_current': (0.0, 18.0),       # Allow higher current draws
                'power_mode': (0.0, 2.0)            # Allow mode progression
            })
        ])
    )
    
    return Scenario(
        name="NavDriftIncrease",
        description=(
            "NavigationEstimator sensors degrade, providing worse guarantees (ΔG_rel) with larger "
            "position errors and drift. Forward propagation creates a cascade: worse nav_position_error "
            "→ FC must relax assumptions → worse control_error and thrust → Motor draws more current "
            "→ PM enters worse modes → lower voltage → worse motor response → higher control_error "
            "→ feedback to Nav activates higher tiers. The 10-tier model creates stepwise propagation "
            "through the 3-node SCC (FC→Motor→PM→FC) requiring ~5-10 iterations for convergence."
        ),
        network=network,
        target_component='NavigationEstimator',
        target_contract=evolved_nav_contract,
        min_iterations_expected=5,  # Target 5-10 iterations with forward ΔG_rel propagation
        system_level_contract=system_contract
    )