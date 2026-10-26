# ADR 0004 Study review and V1 boundary

**Status:** V1 architecture arbitration recorded on October 26, 2026 for #5. Experimental recommendations remain subject to their stated evidence gates; no new transport, database or neural model is declared implemented.

## Inputs reviewed

- Slakkos's four studies, [PR #49](https://github.com/V-Twin-EIP/V-Twin/pull/49), immutable revision [6b5079c](https://github.com/V-Twin-EIP/V-Twin/tree/6b5079c8f369702686199c0f5707fff447abe506/docs/research/etudes-comparaison). The PR is not merged at this review.
- Adam's merged [scenario catalogue](../../validation/scenarios/scenario-catalog.md), introduced by [600b2ae](https://github.com/V-Twin-EIP/V-Twin/commit/600b2ae591cb188d62dd2ee7d3272f7baa3d8c77). SCN-001/CONF-A is the nominal-case identity; operating values and matched contact inputs remain TBD. The validation protocol and datasets remain in preparation.
- The owner's batch-first sandbox, optional 3D, CPU calculation, one-minute-per-run expectation and [reported team hardware](../../../benchmarks/README.md#machine-register).

## Decision by study

| Study and recommendation | V1 decision | Evidence gate for revision |
| :--- | :--- | :--- |
| #30: dual CAN/OBD ingestion and neural interpolation. | Keep acquisition outside the numerical model. The initial sandbox consumes explicit parameters/scenarios; a CAN representation is not mandatory. OBD/CAN remain candidates for the later twin. Neural reconstruction is not selected as a substitute for unobserved measurements. | #2/#30/#34: actual signal inventory, timestamp/quality/coverage and acquisition POC; independently validate any estimated missing signal. |
| #31: MQTT v5/Protobuf ingestion and WebSocket UI. | Retain local HTTP requests/polling for batch control and bounded result reads. Browser playback is independent of solver stepping. MQTT/Protobuf and WebSocket remain options for a demonstrated telemetry/streaming need. | #35/#42: explicit payload/rate/delivery semantics, reconnect behavior and comparable measured transport results. A 60 FPS statement is not a measured latency or solver requirement. |
| #32: TimescaleDB as the single persistence store. | Retain SQLite catalogue + immutable JSON/Parquet for the local sandbox. TimescaleDB is a candidate for later telemetry/history, rather than a replacement adopted without that workload. | #32/#43: exact product versions/editions/licenses, query/ingestion/retention workload, operational cost and reproducible benchmark. Generic compression percentages do not define a V-Twin budget. |
| #33: PINN as the wear-model implementation. | Retain an independently verifiable physical reference implementation in Python/NumPy/SciPy. PINN/other surrogates are deferred candidates; no learning framework or wear law is selected by this study review. | #4/#13/#33: equations, matched parameters, calibration/evaluation separation, applicability and independent accuracy/convergence evidence; measure training/inference cost before adoption. The study's sub-20-ms figure and physical guarantees are not V-Twin test results. |

These decisions retain [ADR 0001](0001-local-application-and-ui-boundary.md), [ADR 0002](0002-reference-engine-and-numerical-policy.md) and [ADR 0003](0003-local-execution-and-storage.md). They distinguish proposals from accepted V1 decisions without changing the studies on their author's branch.

## Numerical choice and its limits

Python/NumPy/SciPy is the selected V1 implementation. Binary64 and the replaceable SciPy ODE adapter are supported by analytical decay/oscillator checks, input/failure tests and CI on Windows/macOS/Linux. RK45 is a starting candidate for a supported non-stiff ODE; the existing Radau/BDF/DOP853 paths do not establish the correct solver for an unformulated contact or thermal problem.

The selected libraries provide a reproducible reference and a route to measurement on the reported CPU machines. C++ or a learned surrogate requires evidence of need and equivalent accepted outputs. No library/language choice alone establishes physical accuracy, the 60-second target or compatibility with every team machine.

## Follow-up and completion boundary

- #5 now has a concrete study-to-decision trace and a justified V1 baseline. Its final evidence review remains open for #4's physical/numerical acceptance and the relevant POC/benchmark results; the ticket is not closed on the strength of prose alone.
- #39 maps the nominal workload to SCN-001/CONF-A and records missing inputs. A separate analytical-core timing probe can test collection/reporting, but cannot supply the sandbox's end-to-end latency or application memory budget.
- #3/#4/#7 must freeze the actual inputs, domain, observable definitions and tolerances. #8/#40/#46 provide execution, supervision and the representative measurement campaign.
- Revisit only the affected ADR when an evidence gate is satisfied. Retain the version, source data, numerical settings, machine and correctness result for each revision.
