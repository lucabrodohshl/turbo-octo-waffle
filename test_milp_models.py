"""Quick test of MILP models to verify they solve correctly"""

import sys
from src.components import NavigationEstimator, PowerManager
from src.contracts import Box
import pulp

print("Testing NavigationEstimator MILP model...")
nav = NavigationEstimator()

# Create test problem
prob = pulp.LpProblem("TestNav", pulp.LpMinimize)

# Input variables
control_error = pulp.LpVariable("control_error", 0, 50)
battery_soc = pulp.LpVariable("battery_soc", 0, 100)

# Output variables  
nav_pos_err = pulp.LpVariable("nav_position_error", 0, 50)
nav_drift = pulp.LpVariable("nav_drift", 0, 10)

input_vars = {'control_error': control_error, 'battery_soc': battery_soc}
output_vars = {'nav_position_error': nav_pos_err, 'nav_drift': nav_drift}

# Add constraints
constraints = nav.get_constraints(input_vars, output_vars)
for c in constraints:
    prob += c

# Set input values
prob += control_error == 5.0
prob += battery_soc == 80.0

# Objective: minimize position error
prob += nav_pos_err

# Solve
print(f"  Problem has {len(constraints)} constraints")
print(f"  Solving...")
status = prob.solve(pulp.PULP_CBC_CMD(msg=0))

if status == pulp.LpStatusOptimal:
    print(f"  ✓ SOLVED: nav_position_error={nav_pos_err.varValue:.2f}, nav_drift={nav_drift.varValue:.2f}")
else:
    print(f"  ✗ FAILED: Status={pulp.LpStatus[status]}")
    sys.exit(1)

print("\nTesting PowerManager MILP model...")
pm = PowerManager()

# Create test problem
prob2 = pulp.LpProblem("TestPM", pulp.LpMinimize)

# Input variables
motor_current = pulp.LpVariable("motor_current", 0, 15)
battery_voltage = pulp.LpVariable("battery_voltage", 8, 13)
battery_current = pulp.LpVariable("battery_current", 0, 15)

# Output variables
voltage_avail = pulp.LpVariable("voltage_available", 8, 13)
power_mode = pulp.LpVariable("power_mode", 0, 2)
voltage_margin = pulp.LpVariable("voltage_margin", -3, 2)

input_vars2 = {'motor_current': motor_current, 'battery_voltage': battery_voltage, 'battery_current': battery_current}
output_vars2 = {'voltage_available': voltage_avail, 'power_mode': power_mode, 'voltage_margin': voltage_margin}

# Add constraints
constraints2 = pm.get_constraints(input_vars2, output_vars2)
for c in constraints2:
    prob2 += c

# Set input values
prob2 += motor_current == 5.0
prob2 += battery_voltage == 12.0
prob2 += battery_current == 6.0

# Objective: minimize power mode
prob2 += power_mode

# Solve
print(f"  Problem has {len(constraints2)} constraints")
print(f"  Solving...")
status2 = prob2.solve(pulp.PULP_CBC_CMD(msg=0))

if status2 == pulp.LpStatusOptimal:
    print(f"  ✓ SOLVED: voltage_available={voltage_avail.varValue:.2f}, power_mode={power_mode.varValue:.2f}, voltage_margin={voltage_margin.varValue:.2f}")
else:
    print(f"  ✗ FAILED: Status={pulp.LpStatus[status2]}")
    sys.exit(1)

print("\n✓ All MILP models solve correctly!")
