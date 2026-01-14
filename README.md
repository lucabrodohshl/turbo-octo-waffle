# turbo-octo-waffle

Contract-based design framework with dynamic evolution and MILP-based transformers for drone system analysis.

## Fail-Fast MILP Behavior

This system implements **strict fail-fast semantics** for all MILP-based contract transformers (`post` and `pre`). This ensures mathematical correctness and preserves theoretical properties.

### Key Properties

1. **No Fallback Bounds**: If any MILP optimization cannot be solved to proven optimality, the system terminates immediately. No approximate bounds (e.g., -1000/+1000) are used.

2. **Total Functions Only on Solvable Inputs**: The `post()` and `pre()` transformers are only defined on inputs where all required optimizations can be solved optimally.

3. **Hard Failures**:
   - Model infeasibility
   - Unbounded objectives
   - Solver errors or timeouts
   - Any non-optimal status
   
   All of these conditions cause immediate termination with detailed diagnostics.

4. **Detailed Error Reporting**: When a failure occurs, the system generates:
   - `output/solver_failure_report.txt` - Human-readable report with MILP problem details
   - `output/solver_failure_report.json` - Structured JSON data
   
   Reports include:
   - Component name and transformer type (post/pre)
   - Variable being optimized and direction (min/max)
   - Solver name and status code
   - Input/output regions with bounds
   - Iteration number in fixpoint loop
   - Edge context (supplier → consumer, interface variables)
   - Complete MILP problem details:
     * All variables with bounds and types
     * All constraints with formulas
     * Objective function

5. **Contract Network Snapshots**: At each iteration, the system saves:
   - `output/CN_<ScenarioName>/iteration_<N>/` - Folder per iteration
   - One `.txt` file per component showing:
     * Component inputs/outputs
     * Deviation breakdown (ΔA_rel, ΔA_str, ΔG_rel, ΔG_str counts and magnitude)
     * Baseline contract (1 assumption box, 1 guarantee box)
     * Evolved contract (all assumption boxes, all guarantee boxes with exact bounds)
   
   This provides complete visibility into contract evolution at every step.

6. **Duplicate Box Elimination**: Union operations automatically deduplicate identical boxes
   to reduce memory usage and speed up convergence.

### Rationale

Fail-fast behavior ensures:
- **Correctness**: No degraded approximations that violate theoretical guarantees
- **Debuggability**: Clear indication of where and why the model failed
- **Soundness**: Contract operations remain sound under the assume-guarantee paradigm

If a transformer fails, it indicates either:
- The deviation scenario is not physically realizable
- Component models have errors or incompatibilities
- The system has reached an inconsistent state

### Usage

Run scenarios with:
```bash
python main.py      # Runs MotorUpgrade scenario
python main2.py     # Runs NavDriftIncrease scenario
```

**Output Structure:**
```
output/
├── solver_failure_report.txt      # MILP failure diagnostics (if any)
├── solver_failure_report.json     # Structured failure data (if any)
├── evolution_report_<Scenario>.txt
├── CN_<ScenarioName>/             # Contract network snapshots per iteration
│   ├── iteration_0/
│   │   ├── Battery.txt
│   │   ├── FlightController.txt
│   │   ├── Motor.txt
│   │   ├── NavigationEstimator.txt
│   │   └── PowerManager.txt
│   ├── iteration_1/
│   │   └── ...
│   └── ...
└── figures/
    ├── network_<Scenario>.png
    ├── iteration_analytics_<Scenario>.png
    └── delta_breakdown_<Scenario>.png
```

**If a solver fails**, the program will:
1. Print failure details to console
2. Write detailed reports to `output/` with complete MILP problem details
3. Save CN snapshots for all completed iterations
4. Terminate with a clear exception

No partial results or fallback approximations are produced.