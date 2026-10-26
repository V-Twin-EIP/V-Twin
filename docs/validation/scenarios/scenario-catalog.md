# V-Twin Sandbox Scenario Catalogue

**Status:** initial specification, October 21, 2026. The six scenarios have not yet been executed or physically validated.

**Issue:** [#3 — Sandbox scenarios](https://github.com/V-Twin-EIP/V-Twin/issues/3).

## 1. Purpose

The first sandbox campaign studies friction and lubrication at the top compression ring–cylinder liner contact. Liner sliding wear is the later quantitative target.

The campaign covers nominal operation, high load, load transients, cooling degradation, a viscosity-related lubrication weakness, and a corrective configuration. Each comparison needs reproducible inputs and a measurable criterion for distinguishing the configurations. Friction and lubrication indicators alone do not establish wear or Remaining Useful Life.

The reference choices come from the [product scope](../../product-scope.md), [reference-engine review](../../research/reference-engine-and-design-inputs.md), and [numerical ADR](../../architecture/adr/0002-reference-engine-and-numerical-policy.md). The validation protocol and reference-source inventory are in preparation under #4.

## 2. Reference Configuration

The engine context is the source-specific Ricardo Hydra variant selected in the reference review. The current code provides a Python/NumPy/SciPy numerical foundation, without a physical engine model.

| Parameter | Value / status |
|---|---|
| Reference engine | Ricardo Hydra gasoline research engine; selected 2023 source variant |
| Architecture | Single-cylinder gasoline engine |
| Cylinder count | 1 |
| Bore × stroke | 86 × 86 mm |
| Displacement | Approximately 499.6 cm³, calculated as π/4 × bore² × stroke |
| Compression ratio | 10.5:1 |
| Idle RPM | TBD |
| Maximum operating RPM | TBD; evaluated range still to be sourced |
| Redline | TBD; a test speed does not establish the mechanical limit |
| Studied component | Top compression ring–liner contact |
| Friction model | Not implemented; formulation and parameters pending #13/#33 |
| Lubrication model | Not implemented; viscosity–temperature law and boundary conditions unresolved |
| Cooling / thermal model | Not implemented; coupling and boundary conditions unresolved |
| Wear model | Not implemented or calibrated |

### Configuration inventory

These IDs identify planned configurations. They do not yet correspond to runnable files or schema fields.

| ID | Configuration | Difference from the reference |
|---|---|---|
| CONF-A | Nominal reference | Matched geometry, contact properties, viscosity law, and boundary conditions; values TBD |
| CONF-B | Lubrication weakness | Change only the viscosity–temperature configuration from CONF-A, using a supported case expected to reduce film separation |
| CONF-C | Corrective variant | Replace CONF-B's viscosity configuration with a justified alternative within the evaluated domain; keep other inputs unchanged |
| CONF-D | Cooling degradation | Reduce one heat-removal parameter from CONF-A; parameter and magnitude TBD |

The first comparison concerns lubricant viscosity behavior. CONF-C may restore CONF-A's lubricant configuration. In that case, the result is a restoration of the reference rather than a new optimized design.

## 3. Simulation Domain

The domain is a component-level ring/liner calculation. No physical operating envelope has been qualified, and the following bounds must be established before physical acceptance.

| Variable | Minimum | Maximum | Unit | Definition needed |
|---|---|---|---|---|
| Crankshaft speed | TBD | TBD | RPM | Sourced range and speed profile |
| Contact loading | TBD | TBD | Pa or N | Pressure/load history and mapping to the ring contact |
| Engine load, if used | TBD | TBD | % of a defined reference | Conversion from the indicator to contact loading |
| Lubricant/contact temperature | TBD | TBD | °C at input/display boundary | Measurement location; prescribed input or computed state |
| Coolant temperature, if represented | TBD | TBD | °C at input/display boundary | Thermal/cooling model and boundary conditions |
| Dynamic viscosity | TBD | TBD | Pa·s | Sourced μ(T) law and valid temperature range |
| Heat-removal parameter | TBD | TBD | Depends on the model | Physical definition and bounds for CONF-D |
| Simulation duration | TBD | TBD | s | Settling period, evaluation window, and cycle count |
| Load-transition duration | TBD | TBD | s | Ramp duration and interpolation for SCN-003 |

Geometry, materials, roughness, lubricant supply, initial conditions, and boundary conditions also need a matched parameter set. Internal calculations follow the ADR's SI conventions, including kelvin and radians, with explicit conversions at input and display boundaries.

The input profiles, domain bounds, model version, solver settings, output grid, and comparison windows are fixed before execution. Physical acceptance also requires independent evidence, uncertainty estimates, and tolerances for the tested conditions. Results outside the supported domain remain outside the validation claim.

### Out of scope

- Lubricant ageing, contamination, and oil chemistry.
- Manufacturing defects, fatigue cracking, bearings, and other unmodelled contacts.
- Whole-engine wear, vehicle lifetime, and Remaining Useful Life.
- Combustion, coolant-circuit behavior, and temperature dynamics beyond implemented and evaluated models.
- Tribological regimes outside the selected model and reference coverage.
- Real-vehicle telemetry validation: the project has no established access to an engine or acquired engine measurements.

## 4. Scenario Summary

| ID | Scenario | Configuration / profile | Effect to evaluate | Dependency |
|---|---|---|---|---|
| SCN-001 | Nominal Operation | CONF-A, steady moderate operating point | Bounded, repeatable cycle behavior and nominal lubrication margin | Contact model and fixed inputs |
| SCN-002 | Sustained High Load | CONF-A, increased contact loading at fixed speed | Response to load within the supported lubrication regime | Load/contact mapping |
| SCN-003 | Transient Load | CONF-A, moderate → high → moderate load | Response during loading and recovery | Profile support and contact model |
| SCN-004 | Cooling Degradation | CONF-A versus CONF-D, identical profile | Higher computed temperature or reduced thermal margin | Coupled thermal/cooling model |
| SCN-005 | Friction / Lubrication Weakness | CONF-A versus CONF-B, identical profile | Reduced film separation in the selected adverse viscosity case | Viscosity/contact model and reference evidence |
| SCN-006 | Corrective Configuration | CONF-B versus CONF-C, SCN-005 profile | Recovery of the metric selected for SCN-005 | SCN-005 and corrective configuration |

### Shared evidence and decision rules

Each run must retain:

- Scenario and configuration versions, complete inputs, changed parameters, sources, and any synthetic assumptions.
- Initial conditions and forcing, identical for paired configurations except for the declared change; profile differences identified for load comparisons.
- Model version, numerical policy, saved-output sampling, evaluation window, execution environment, logs, and terminal status.
- Raw time series with quantity definitions, units, and input/output classification; plots and a quantitative comparison table derived from those series.
- Reference evidence or justified physical expectation, uncertainty, tolerance, and acceptance criterion for each metric.

Candidate observables are friction force (N), dissipated friction power (W), friction energy over a fixed window (J), minimum film thickness (m), and the film-thickness-to-composite-roughness ratio λ (dimensionless). Their definitions and aggregation will be specified in the validation protocol. None is a current physical-model or API output. A component calculation does not establish engine-wide friction torque, damage scores, or health indicators.

Metric direction, evaluation window, resolution requirements, uncertainty treatment, and thresholds are fixed before comparing variants. Curve separation alone is insufficient. An unresolved difference is inconclusive; a resolved violation of a criterion is a failure. Missing outputs, thresholds, or model support block acceptance. Detailed PASS/FAIL/INCONCLUSIVE/BLOCKED rules will be documented in the validation protocol, which is in preparation. No detector is implemented yet.

Independent physical validation and detection of a controlled configuration change are separate evaluations. Numerical convergence and repeatability support the former but cannot establish physical accuracy on their own.

## 5. SCN-001 — Nominal Operation

### Objective and inputs

Establish CONF-A at fixed nominal speed and moderate contact loading. Speed, pressure/load history, viscosity law, temperatures, supply conditions, initial state, duration, and settling/evaluation windows remain TBD.

### Expected behavior

After settling, the contact solution should show bounded, repeatable cycles consistent with the forcing. Friction and film thickness can vary within each cycle. The selected lubrication metrics should meet the nominal bounds for this case. A prescribed temperature provides no evidence of thermal stability.

### Evidence and acceptance

Retain the shared evidence, speed/load curves, cycle-resolved contact outputs, and temperatures identified as prescribed or computed. Acceptance requires complete, numerically resolved outputs within the supported domain and the predefined nominal and cycle-to-cycle variation bounds. This case supplies the comparison baseline.

## 6. SCN-002 — Sustained High Load

### Objective and inputs

Increase CONF-A's contact loading relative to SCN-001 while keeping speed, other boundary conditions, and initial conditions unchanged. The load history, its physical meaning, and duration remain TBD.

### Expected behavior

The response depends on the lubrication regime. Friction, film thickness, and dissipated energy need reference-based criteria; there is no general requirement that every friction metric increase or that every lubrication metric worsen.

Temperature rise is an output only if a supported thermal model computes it. Otherwise, the comparison concerns dissipation under the imposed temperature boundary.

### Evidence and acceptance

Retain the shared evidence, the comparison with SCN-001, load histories, contact outputs, and cycle/window statistics. Each selected metric needs an expected direction or reference interval justified before execution. Acceptance requires a resolved response meeting those criteria.

## 7. SCN-003 — Transient Load

### Objective and input profile

Run CONF-A at fixed speed through:

1. Moderate loading and initial settling.
2. A finite ramp to the supported high-load condition.
3. A sustained high-load interval.
4. A finite ramp back to moderate loading and a recovery interval.

Load levels, ramp durations, interpolation, saved-output sampling, and interval lengths remain TBD. The viscosity configuration stays unchanged.

### Expected behavior

The response should follow the imposed loading according to the represented states. A thermal model would need to reproduce its represented inertia. A quasi-static contact calculation may respond immediately and cannot establish thermal lag or omitted transient behavior.

### Evidence and acceptance

Retain the shared evidence, timestamped load profile, contact response, and computed thermal response where available. Compare predefined transition and recovery metrics with their references. Integration and output-resolution studies must distinguish the response from sampling artifacts. Unexplained numerical discontinuities prevent acceptance.

## 8. SCN-004 — Cooling Degradation

### Objective and inputs

Compare CONF-A and CONF-D under the same loading, speed, initial state, ambient conditions, and duration. Reduce cooling through one parameter represented by the thermal model. Its definition, unit, nominal/degraded values, and applicable range remain TBD.

### Expected behavior

For the selected positive-heat-input case, lower heat removal should increase the relevant computed temperature over the evaluation window or reduce a defined thermal margin. Secondary lubrication effects require temperature–viscosity coupling.

### Evidence and acceptance

Retain the shared evidence, changed parameter, thermal initial/boundary conditions, heat-input/removal quantities, temperature curves, and any coupled lubrication outputs. Acceptance requires the predefined temperature or thermal-margin response to exceed its justified threshold. A thermal margin also needs a sourced temperature limit.

This scenario is blocked until a thermal/cooling model exists. Prescribing a higher oil temperature would be a boundary-temperature sensitivity study, not an execution of SCN-004.

## 9. SCN-005 — Friction / Lubrication Weakness

### Objective and hypothesis

Test whether CONF-B's viscosity–temperature configuration reduces lubricant film separation at a selected loading/temperature condition. The adverse direction must be supported by an independent benchmark or justified contact analysis before the comparison. The weakness has not yet been demonstrated.

Changing a global friction coefficient to force higher losses would not test this viscosity hypothesis.

### Inputs and comparison

Compare CONF-A and CONF-B with identical operating profile, geometry, materials, roughness, lubricant supply, initial state, numerical policy, output grid, and evaluation window. Only the viscosity configuration changes. The law, values, source, and profile selected from SCN-001–003 remain TBD. Both configurations must remain within model applicability.

### Expected behavior

The selected film-separation metric, such as minimum film thickness or λ, should decrease relative to CONF-A. Its definition and aggregation are fixed before evaluation. Friction and energy trade-offs must also be reported: lower viscous losses do not by themselves indicate better lubrication. Temperature or wear consequences require their own models and evidence.

### Evidence and acceptance

Retain the shared evidence, viscosity curves over the tested temperature range, exact input difference, film-separation curves, supported friction outputs, and absolute/relative differences with uncertainty and thresholds.

Detection requires a reduction beyond the predefined threshold, with independent evidence supporting its interpretation. An insufficiency claim additionally requires an applicable adequacy limit; without one, the result is limited to a relative reduction in lubrication margin. An absent or unresolved effect is reported under the protocol's failure or inconclusive rules. The primary metric cannot be changed after evaluation to obtain a pass.

## 10. SCN-006 — Corrective Configuration

### Objective and inputs

Compare CONF-C with CONF-B using SCN-005's metric, profile, initial conditions, geometry, model, numerical policy, output grid, and evaluation window. Only the viscosity configuration changes; CONF-A remains the reference anchor.

### Expected behavior

The film-separation metric should recover toward the nominal range. The comparison must also report friction/energy trade-offs and any supported thermal consequences. Lower losses do not establish a correction if lubrication adequacy worsens.

### Evidence and acceptance

Retain the shared evidence, CONF-B/CONF-C input difference, and the three-configuration comparison. Improvement and non-regression thresholds are fixed before evaluation.

Acceptance requires a resolved improvement beyond the selected threshold, compliance with other required metric limits, and operation within the supported domain. Partial recovery is distinct from restoration of an adequacy limit. If CONF-C equals CONF-A, the result must reproduce CONF-A within the numerical tolerance and be described as restoration. No engine-lifetime improvement follows from this comparison.

## 11. Expected Demonstrator Outcome

The demonstration compares CONF-A's baseline with CONF-B's viscosity weakness, then evaluates whether CONF-C recovers the selected lubrication metric. The report must show the resolved differences and their uncertainty, together with friction and any supported thermal trade-offs.

Completion requires fixed inputs/domain/thresholds, nominal/load/transient results, and the weakness/correction comparison. If the cooling model is unavailable, SCN-004 remains blocked and the demonstration is partial. An imposed temperature change cannot substitute for it.

The planned application workflow is to load a configuration, run it, inspect graphs, change a supported parameter, rerun, compare, and save. Interactive 3D and dashboard-only operation remain product requirements. Rendering is not physical validation evidence.

The [nominal performance workload](../../../benchmarks/workloads/sandbox-nominal-v1.json) is awaiting a reference case. Its inputs must match the eventual SCN-001 configuration. The one-minute calculation target is unmeasured and assessed separately from physical accuracy.

## 12. Current Limitations

The implemented numerical checks use analytical ODEs. They execute none of these scenarios and provide no Hydra physics validation. The foundation has no scenario runner, physical configuration files, result store, detector, comparison dashboard, or 3D viewer.

The matched contact parameters, operating envelope, viscosity configurations, thermal formulation, and initial conditions are unresolved. No qualified independent evaluation dataset or scenario-specific physical tolerances have been established. The validation protocol and reference-source inventory are in preparation; they will cover the evaluation method and data requirements.

Before a campaign, #3/#4/#7 must establish scenario inputs and contracts; #13/#33 must establish the physical model and its evidence requirements. Until then, the weakness, correction, and wear remain hypotheses or targets, with no detected fault, measured improvement, validated wear, or lifetime result.
