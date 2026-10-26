# ADR 0002 Python reference engine and numerical policy

**Status:** Python/NumPy/SciPy selected by the owner for V1 on October 18, 2026, with C++ introduced according to measured needs. Numerical acceptance depends on #3/#4/#33; no performance winner has been measured.

**October 26 review:** [ADR 0004](0004-study-review-and-v1-boundary.md) records the study-to-decision trace, retains the physical reference baseline and defers PINN adoption until independent correctness and measured-cost evidence exists.

## Decision

Start with a **Python reference engine using NumPy and SciPy**, independently importable and callable without the web server. Use explicit typed domain records/arrays inside the engine and serialized, versioned run contracts at its boundary. Keep validation of HTTP payloads in the adapter. Model modules must not import FastAPI, database clients, or presentation code.

The application selects an `EnginePort` implementation through the composition root. Its operation consumes a frozen run specification, emits diagnostics and result artifacts through defined callbacks/sinks, and returns a terminal outcome. Numerical callbacks execute inside the selected engine. A future C++ implementation can implement the same semantic contract; neither UI routes nor run schemas need to expose its internal data structures.

This choice uses the team's Python experience and the available numerical tools while establishing the physical model and evaluation data. **No CUDA or GPU compute dependency is required for V1.** Python execution time and memory still need measurement on the reference workload.

## Alternatives

| Candidate | Fit and cost | V1 outcome |
| :--- | :--- | :--- |
| Python with NumPy/SciPy | Supports a reference implementation, analysis, and calibration in one runtime; callback overhead and array allocation can matter. | Initial implementation baseline; profile actual model workloads. |
| C++ numerical engine | Team has relevant skills; gives control over data layout and allocation, with additional build, binding, and distribution work. Boost.Odeint provides C++ integration steppers. | Alternative for a measured need or a justified model/library requirement. [Boost.Odeint](https://www.boost.org/doc/libs/latest/libs/numeric/odeint/doc/html/boost_numeric_odeint/odeint_in_detail/steppers.html). |
| Python orchestration with C++ kernels | Retains the application/runtime contract while moving a measured hotspot; adds native build and boundary costs. pybind11 supports NumPy-array bindings. | Extension path after profiling and equivalence checks. [pybind11 arrays](https://pybind11.readthedocs.io/en/stable/advanced/pycpp/numpy.html). |

If C++ is introduced, cross the language boundary with complete operations or array batches rather than one call per rendered sample. Check representation, ownership, copies, cancellation, and numerical agreement. Neither language alone establishes physical accuracy or a speed advantage for the selected workload.

## Numerical policy

- Use **binary64** as the initial physical-state and stored-numerical-result baseline; identify missing/invalid outputs explicitly instead of publishing nonfinite JSON values. A different precision requires convergence/error evidence.
- Use SciPy `solve_ivp` as the candidate adapter for supported ODE subproblems. RK45 is the starting candidate for non-stiff ODEs; Radau/BDF are candidates when stiffness is established. The method, per-state absolute tolerances, relative tolerance, maximum step, events, and output grid belong to the frozen run specification. [SciPy solver documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html).
- Separate the solver's integration steps from saved output sampling and the browser's playback frame rate. Represent scenario discontinuities explicitly when scheduling integration intervals.
- A Reynolds/contact-field formulation may require spatial discretization, algebraic/linear/nonlinear solves, or coupled iteration. `solve_ivp` is not a selected solution for every lubrication equation. #33 and the physical-model work establish that formulation and its convergence policy.
- #4 specifies justified physical tolerances, calibration/evaluation separation, domain coverage, and failure conditions. Solver-local error controls do not establish agreement with experimental wear.

## Numerical and performance evaluation

The owner requested a **maximum one-minute wait for a nominal sandbox case**. Treat **60 seconds** as a user target to evaluate in #39: measure from the browser's run submission to the first complete required result set being usable in the dashboard. Include validation, scheduling, calculation, publication, result retrieval, and initial chart availability; report queue wait separately within that total. The nominal workload and environment must be fixed in #3/#39. Startup/installation and a queue already occupied by other jobs are separate scenarios with separately reported waits. This target is not a demonstrated result or an automatic solver timeout.

On October 19, 2026, the owner clarified that the minute applies **per calculation** and added a **less-than-one-second** target for opening stored results or changing curves. The [PF.1 protocol](../../performance.md) defines the KPI boundaries, repetitions, inventory, initial tracking and budget-adoption process. These expectations remain unmeasured; technical budgets are pending a representative baseline.

Use the actual #3 reference workload and the #4 accuracy guardrails. Record input/model versions, duration, integration/output policy, runtime/BLAS configuration, hardware, repeated wall times, peak memory, solver diagnostics, and observable errors. Count the API/worker/browser cost separately where useful; retain total application measurements on the [reported 16 GB Pacien and Divin profiles](../../../benchmarks/README.md#machine-register).

If this baseline misses the budgets defined in #39, profile it first. Compare an optimized Python implementation and a C++ candidate only when the identified cost justifies the latter. Both must satisfy the same accuracy and result-contract checks. Any solver/backend revision gets a new implementation version in the run manifest; old results remain attached to their original implementation.
