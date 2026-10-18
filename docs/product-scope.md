# Product scope and first demonstrator

**Status:** M0.1 product-scope baseline, version 1. This document defines planned capabilities; their implementation and physical validation are tracked in the follow-up issues.

**Tracking:** [M0.1 — Define the scope and user journeys](https://github.com/V-Twin-EIP/V-Twin/issues/1).

## Product intent

V-Twin has two intended applications, with the **design sandbox prioritized for the first demonstrator**:

1. **A design sandbox before production:** help an engineer test an engine design and investigate potential reliability problems before construction.
2. **A digital twin of a real engine:** help a private vehicle owner track engine wear, with the software intended to follow the vehicle from its initial new-engine condition.

The existing roadmap proposes a shared simulation foundation. The owner selected **wear associated with friction or lubrication** as the first reliability topic, with an **interactive 3D view, graphs, and result comparisons**. Audio is excluded. The scoped technical baseline uses a Ricardo Hydra gasoline case, explicit parameter input, and a first ring–liner contact model.

## Confirmed constraints

- The team currently has **no accessible physical engine or vehicle** for this work.
- No acquired engine measurements or wear observations have been established in this discussion.
- A documented **Ricardo Hydra gasoline 86 × 86 mm case** is selected as the reference-engine context. It has published specifications and relevant tribology literature; a complete matched parameter and wear-validation dataset has not yet been established. See the [reference-engine and input review](research/reference-engine-and-design-inputs.md).
- The first product demonstration prioritizes the sandbox. Vehicle acquisition and twin-related technology experiments can continue as supporting roadmap work, without making a live vehicle connection a prerequisite for this demonstration.
- The future twin is intended to start with a new vehicle. Its deployment mechanism, available signals, and initialization/calibration procedure remain to be defined.
- The project has **four team members**. The next Epitech mentoring meeting is **Monday, October 26, 2026**. Individual responsibilities, availability, and the first executable-demonstration date have not been established in this discussion.

## Decision record

| Decision | Status | Basis |
| :--- | :--- | :--- |
| Support both the real-engine twin and the design sandbox as product goals. | Confirmed | Project owner's stated vision. |
| Build the new project in `V-Twin-EIP/V-Twin`. | Confirmed | Project owner's selected repository and fresh-start direction. |
| Use a common simulation foundation. | Roadmap basis | Existing product roadmap; architectural details belong to M1. |
| Prioritize an engineer evaluating an engine design before construction for the sandbox. | Confirmed | Owner's first-round answer. |
| Target a private owner following engine wear from the vehicle's new condition for the twin. | Confirmed | Owner's first-round answer. |
| Prioritize the sandbox for the first demonstrator. | Confirmed | Owner's first-round answer. |
| Record current access to a physical engine or vehicle as unavailable. | Confirmed constraint | Owner's first-round answer. |
| Use a Ricardo Hydra gasoline 86 × 86 mm case as reference context. | Working selection from delegated research | Source-specific variant and evidence gaps recorded in the reference review. |
| Target wear associated with friction or lubrication first. | Confirmed | Owner's second-round answer. |
| Use explicit parameters in a form/file as the MVP design input. | Adopted working baseline | Owner's preference, delegated technical advice, and the reference review; exact format belongs to the architecture/data-contract work. |
| Study the top compression ring–liner contact, initially targeting liner sliding wear. | Adopted working baseline | Scoped from the confirmed wear direction and relevant literature; formulation, parameters, and calibration remain follow-up work. |
| Include interactive 3D, graphs, and result comparison in the MVP. | Confirmed | Owner's third-round answer. |
| Exclude engine audio. | Confirmed | Owner stated that sound is not wanted. |
| Plan with a four-person team. | Confirmed | Owner's third-round answer; no allocation or delivery date inferred. |
| Prepare for the next Epitech mentoring meeting on October 26, 2026. | Planning date | Owner supplied “Monday, October 26” after the distinction between mentoring and an executable demonstration; no executable-delivery deadline inferred. |

## Application framing

| Question | Digital twin | Design sandbox |
| :--- | :--- | :--- |
| Intended purpose | Follow the condition and wear of a particular real engine over time. | Examine potential design weaknesses under defined simulated conditions. |
| Priority user | A private owner with the software intended to follow a vehicle from its new condition. | An engineer testing an engine design before construction. |
| User's goal | Track the evolution of engine wear from the initial reference condition. | Investigate potential reliability problems and decide which aspects of the design need revision. |
| Delivery priority | Subsequent product delivery; initial user capability is wear-history review. | First demonstrator. |
| Scoped inputs | Vehicle/engine identity, initial new-engine condition record, timestamped operating observations, units, provenance, and history coverage. | Parameter form/file with reference-engine geometry, ring/liner properties, lubricant behavior, operating/loading scenario, and provenance. |
| Scoped outputs | Estimated wear history for the supported component, its relation to the initial reference, uncertainty, and observation coverage. | Interactive 3D reference/contact view, graphs of the supported friction/lubrication/wear quantities, and baseline-versus-variant comparison. |
| Supported decision | Understand how the supported wear estimate evolves over recorded use and identify changes needing further examination. | Decide whether a supported configuration change improves or worsens the modeled contact's behavior in the selected scenario. |

These categories define the product boundary. Exact signal names, file schemas, units for the selected wear quantity, operating ranges, and validation tolerances are established in the data-contract, model, and validation issues.

## User journeys

### First delivery: design sandbox

The first sandbox journey is:

1. The engineer loads the reference engine and contact configuration through a form or file.
2. The engineer selects the supported operating scenario and inspects the configuration in an interactive 3D view.
3. V-Twin runs the configured model and records its inputs, assumptions, model version, and results.
4. The engineer selects the ring/liner contact and examines its supported friction, lubrication, and wear results in graphs linked to the same run.
5. The engineer duplicates the configuration, changes one supported parameter, and reruns the same scenario.
6. The engineer compares the baseline and variant in the viewer and graphs, then saves the configurations and results for reproduction.

The baseline first comparison is **two lubricant configurations differing in viscosity behavior**, applied to the same Hydra-context geometry and operating/contact scenario. Hold the remaining inputs constant and compare the supported friction/lubrication/wear quantities. The exact viscosity curves, values, test case, and evaluated range must come from the scenario and validation work; no numerical values or outcome are assumed here. Ring geometry, surface finish, and other design parameters can be opened for editing as their model support and evidence are established. The [reference review](research/reference-engine-and-design-inputs.md#proposed-first-comparison) records the evidence requirements.

### MVP boundaries

| Included in the scoped engineering MVP | Subsequent capability |
| :--- | :--- |
| One frozen reference-engine context and one ring/liner contact model. | Multiple engine families, complete ring packs, and additional components. |
| Explicit parameter input and a controlled comparison of two configurations. | General-purpose complete CAD import and automatic contact/model extraction. |
| Interactive 3D inspection of a simplified engine/contact representation, linked to graphs and comparison. | Manufacturer-qualified detailed assemblies and more advanced geometry workflows. |
| Reproducible scenario, result provenance, and interpretation tied to evaluated conditions. | Complete-engine reliability or remaining-life predictions across arbitrary use. |
| Component-level wear evaluation using suitable calibration and independent observations. | Longitudinal monitoring of a real vehicle from new. |

**Audio is excluded.** There is no audio requirement or automatic audio follow-up in this scope.

### 3D, graphs, and comparison requirements

- Support camera rotation and zoom, component selection, and a way to inspect the ring/liner contact without the outer geometry obstructing it.
- Build the simplified representation from the documented configuration. Identify illustrative geometry or assumed dimensions; visual detail must not imply additional physical-model coverage.
- Provide play/pause and time or cycle selection where animation is supported. The selected run and state must correspond to the values shown in the graphs.
- Display model-supported quantities with units, provenance, and the evaluated domain. Candidate graph quantities are minimum oil-film thickness, friction force, and accumulated liner wear; their model contracts and validation determine the final definitions.
- Compare baseline and variant under the same operating scenario, showing changed inputs and comparable output curves.
- If a thin film, deformation, or wear amount is visually exaggerated for inspection, identify the display scale or schematic representation.
- Preserve model execution independently of rendering so numerical results can be reproduced without the viewer.

These are requirements for [the sandbox visualization/comparison work in #24](https://github.com/V-Twin-EIP/V-Twin/issues/24). They do not select a frontend framework, asset format, or rendering library.

### First executable demonstration

The functional demonstration target is a complete path: **load a reference configuration → inspect it in 3D → run a supported case → inspect graphs → change one supported parameter → rerun → compare and save results**.

An early integration prototype may use declared fixtures to exercise the interface. It must identify them as example data. Satisfying the engineering MVP's wear claim requires the physical model and evaluation evidence tracked in the model/validation issues; interface functionality alone does not establish that claim.

### Mentoring meeting and software demonstration

| Event | Expected material | Date |
| :--- | :--- | :--- |
| Next Epitech mentoring meeting | Product scope, reference-engine rationale, user journeys, MVP boundaries, track evidence matrix, and questions to arbitrate. Architecture and experiment results can be added as their own issues progress. | Monday, October 26, 2026. |
| First executable software demonstration | The end-to-end configuration/run/3D/graphs/comparison path described above, with the provenance and evaluation status of displayed results explicit. | To be defined. |

The mentoring meeting and executable demonstration are separate planning events. No delivery deadline or four-person task allocation has been committed by this scope document.

### Subsequent delivery: real-engine twin

The owner has defined the intended starting condition and purpose. The proposed workflow is:

1. Associate the software with a vehicle and record its initial new-engine reference condition and available metadata.
2. Acquire the selected observations over the vehicle's operating history through a deployment/integration method to be specified.
3. Maintain the modeled state and a traceable history of the selected wear estimates.
4. Let the owner review wear evolution and the quality/coverage of the observations supporting it.

Deployment, initial-state estimation/calibration, signal acquisition, and handling of missing history require technical follow-up. The new-vehicle starting point is an intended operating condition, not a measurement of the engine's internal state.

## Information categories

| Category | Meaning in V-Twin | Evidence to retain |
| :--- | :--- | :--- |
| **Measurement** | An observation obtained from an identified physical source. | Source, unit, timestamp, acquisition method, and known quality. |
| **Estimated state** | A model-derived estimate of the engine's current condition. | Inputs, model and parameter versions, assumptions, and uncertainty. |
| **Load indicator** | A quantity describing operating exposure or stress relevant to a degradation mechanism. | Definition, units, model coverage, and the relationship being investigated. |
| **Physical wear** | The actual degradation of the selected component that the project seeks to characterize. | A defined physical quantity and a way to observe or evaluate it. |
| **Wear estimate** | A model output representing that degradation after calibration against suitable observations. | Calibration data, evaluation protocol, error, and domain of validity. |
| **Prediction** | A conditional estimate of future behavior under stated assumptions. | Future operating scenario, model limits, uncertainty, and independent evaluation. |

The selected mechanism will determine the concrete physical quantities and how they can be validated. A load indicator and an estimate of physical wear must retain distinct names and interpretations.

## Follow-up work after M0.1

| Work | Tracking |
| :--- | :--- |
| Assemble a consistent reference parameter set and select the exact scenario/viscosity comparison. | [#3: sandbox scenarios](https://github.com/V-Twin-EIP/V-Twin/issues/3). |
| Establish calibration/evaluation observations, supported operating range, and justified tolerances. | [#4: validation protocol](https://github.com/V-Twin-EIP/V-Twin/issues/4), [#13: wear mechanism/model](https://github.com/V-Twin-EIP/V-Twin/issues/13), [#33: model comparison](https://github.com/V-Twin-EIP/V-Twin/issues/33). |
| Define the architecture, parameter/result contracts, and the boundary between solver and 3D rendering. | [#5: architecture](https://github.com/V-Twin-EIP/V-Twin/issues/5), [#7: data contracts](https://github.com/V-Twin-EIP/V-Twin/issues/7). |
| Implement reproducible runs, the interactive 3D view, graphs, and comparisons. | [#21: sandbox runner](https://github.com/V-Twin-EIP/V-Twin/issues/21), [#24: visualization/comparison](https://github.com/V-Twin-EIP/V-Twin/issues/24). |
| Obtain an external expert view on the contact model, evidence gaps, and transfer from bench data to engine claims. | [#36: expert preparation](https://github.com/V-Twin-EIP/V-Twin/issues/36), [#37: expert review](https://github.com/V-Twin-EIP/V-Twin/issues/37). |
| Research the later twin's real signals, initial-state procedure, acquisition, and physical access. | [#2: real-engine data](https://github.com/V-Twin-EIP/V-Twin/issues/2), [#17: telemetry ingestion](https://github.com/V-Twin-EIP/V-Twin/issues/17). |

The product boundary is established here. These follow-ups establish feasibility details, implementation, and evidence. Changes to the reference case, supported claims, or feature scope should update this baseline explicitly. The October 26 mentoring meeting is a planning checkpoint; the executable-demonstration date remains open.

## Mentoring evidence

The [Technical Track coverage plan](technical-track.md) maps the four selected objectives to deliverables, evidence, and issue links. The confirmed sandbox-first direction and lack of hardware access create the following product-specific topics for the next review:

| Objective | Product-specific evidence and arbitration topic |
| :--- | :--- |
| **O1: technology watch** | Reference-engine/input review recorded. Evaluate ring/liner model approaches and calibration-data availability; keep transport/acquisition POCs distinct from proof of a live engine twin. |
| **O2: architecture** | Document the sandbox design/run/3D/graphs/compare journey, supported inputs and outputs, solver/rendering boundary, and assumptions about the later twin. |
| **C1: expert collaboration** | Seek an external view on reference-engine selection, the first reliability mechanism, and a validation approach possible with the accessible evidence. |
| **C2: performance** | Define a repeatable sandbox workload and software KPIs after the engine/scenario are chosen; keep computational performance separate from physical-model accuracy. |

| M0.1 acceptance criterion | Current evidence |
| :--- | :--- |
| Describe users, inputs, decisions, and outputs for each application. | Scope defined in application framing and the two user journeys. Detailed signal/schema work is assigned to follow-ups. |
| Select a reference engine and initial component/wear mechanism. | Source-specific Hydra reference, top-ring/liner contact, and liner sliding-wear target selected as the working baseline; evidence gaps assigned to follow-ups. |
| Define included/deferred MVP capabilities and the place of audio/visualization. | Boundaries defined; interactive 3D/graphs/comparison included; complete CAD import deferred; audio excluded. |
| Distinguish measurements, estimated states, load indicators, physical wear, and predictions. | Definitions recorded above and evidence categories retained in the demonstration requirements. |
| Prepare the four-objective mentoring matrix and topics to arbitrate. | Track matrix linked and product-specific evidence/arbitration topics recorded above. |
