# Product scope and first demonstrator

**Status:** working draft; product decisions are being established with the project owner.

**Tracking:** [M0.1 — Define the scope and user journeys](https://github.com/V-Twin-EIP/V-Twin/issues/1).

## Product intent

V-Twin has two intended applications, with the **design sandbox prioritized for the first demonstrator**:

1. **A design sandbox before production:** help an engineer test an engine design and investigate potential reliability problems before construction.
2. **A digital twin of a real engine:** help a private vehicle owner track engine wear, with the software intended to follow the vehicle from its initial new-engine condition.

The existing roadmap proposes a shared simulation foundation. The first sandbox case, engine description method, and reliability mechanism are being selected. The initial wear mechanism to support the broader product must also be scoped against the observations available.

## Confirmed constraints

- The team currently has **no accessible physical engine or vehicle** for this work.
- No acquired engine measurements or wear observations have been established in this discussion.
- A reference engine or documented case is still to be selected. Published specifications, reference datasets, analytical cases, and expert feedback are potential evidence sources to investigate in the validation work.
- The first product demonstration prioritizes the sandbox. Vehicle acquisition and twin-related technology experiments can continue as supporting roadmap work, without making a live vehicle connection a prerequisite for this demonstration.
- The future twin is intended to start with a new vehicle. Its deployment mechanism, available signals, and initialization/calibration procedure remain to be defined.

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
| Select a reference engine and establish available evidence. | Awaiting engine preference and reference research | No hardware access established. |
| Select how an engineer describes a design and the first reliability problem to explain. | Awaiting owner input | Second discussion round. |
| Select the first component and wear mechanism. | Pending engine and reliability-case selection | Must match accessible evidence and validation opportunities. |
| Set the role of visualization and audio in the MVP. | Pending scope discussion | Explicit acceptance criterion of M0.1. |

## Application framing

| Question | Digital twin | Design sandbox |
| :--- | :--- | :--- |
| Intended purpose | Follow the condition and wear of a particular real engine over time. | Examine potential design weaknesses under defined simulated conditions. |
| Priority user | A private owner with the software intended to follow a vehicle from its new condition. | An engineer testing an engine design before construction. |
| User's goal | Track the evolution of engine wear from the initial reference condition. | Investigate potential reliability problems and decide which aspects of the design need revision. |
| Delivery priority | Subsequent product delivery; exact monitoring actions remain to be scoped. | First demonstrator. |
| Inputs to specify | Engine identity/description, initial condition record, accessible observations, and operating history. | Design description, configurable parameters, operating scenarios, and comparison criteria; input method remains under discussion. |
| Outputs to specify | Selected wear estimates and their history, provenance, coverage, and uncertainty. | Results explaining the selected reliability problem and comparison of design variants; quantities follow problem selection. |

User roles and delivery priority are confirmed. Concrete input fields, output quantities, and demonstration claims remain to be selected.

## User journeys

### First delivery: design sandbox

This proposed journey translates the confirmed user goal into a workflow to refine with the owner:

1. The engineer describes an engine design using the selected input method.
2. The engineer selects a supported operating scenario and the reliability question to investigate.
3. V-Twin runs the configured model and records its inputs, assumptions, and results.
4. The engineer examines the quantities relevant to the modeled problem, together with their interpretation and model coverage.
5. The engineer changes a supported design parameter and reruns the same scenario.
6. The engineer compares the variants and identifies a candidate design revision to investigate further.

The initial demonstration will need one concrete instance of this journey. Its engine, parameter set, scenario, component, and observable result are still being chosen.

### Subsequent delivery: real-engine twin

The owner has defined the intended starting condition and purpose. The proposed workflow is:

1. Associate the software with a vehicle and record its initial new-engine reference condition and available metadata.
2. Acquire the selected observations over the vehicle's operating history through a deployment/integration method to be specified.
3. Maintain the modeled state and a traceable history of the selected wear estimates.
4. Let the owner review wear evolution and the quality/coverage of the observations supporting it.

The meaning of the initial reference state, calibration, supported owner decisions, and handling of missing history require further specification. The new-vehicle starting point is an intended operating condition, not a measurement of the engine's internal state.

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

## Decisions needed to define the MVP

- Reference engine family/model and the specifications or datasets available for a first sandbox case.
- Design description method, supported parameters, first reliability question, and targeted component/mechanism.
- Concrete sandbox scenario, comparison, observable completion criteria, and the boundary of the first demonstration.
- Included capabilities and deferred capabilities, including the role of audio and visualization.
- Initial wear mechanism for the broader product and supported owner actions in the subsequent twin delivery.
- Assumptions and unanswered questions to discuss with the EIP mentor and technical experts.

These decisions establish product scope. Signal inventories and acquisition protocols are developed in [#2](https://github.com/V-Twin-EIP/V-Twin/issues/2); sandbox test scenarios in [#3](https://github.com/V-Twin-EIP/V-Twin/issues/3); validation protocols in [#4](https://github.com/V-Twin-EIP/V-Twin/issues/4); architecture choices in [#5](https://github.com/V-Twin-EIP/V-Twin/issues/5).

## Mentoring evidence

The [Technical Track coverage plan](technical-track.md) maps the four selected objectives to deliverables, evidence, and issue links. The confirmed sandbox-first direction and lack of hardware access create the following product-specific topics for the next review:

| Objective | Product-specific evidence and arbitration topic |
| :--- | :--- |
| **O1: technology watch** | Evaluate model approaches and reference-data availability for the selected sandbox case. Keep transport/acquisition POCs distinct from proof of a live engine twin. |
| **O2: architecture** | Document the sandbox design/run/compare journey, supported inputs and outputs, shared model boundaries, and assumptions about the later twin. |
| **C1: expert collaboration** | Seek an external view on reference-engine selection, the first reliability mechanism, and a validation approach possible with the accessible evidence. |
| **C2: performance** | Define a repeatable sandbox workload and software KPIs after the engine/scenario are chosen; keep computational performance separate from physical-model accuracy. |

| M0.1 acceptance criterion | Current evidence |
| :--- | :--- |
| Describe users, inputs, decisions, and outputs for each application. | Users and goals confirmed; journeys drafted; concrete inputs/outputs under discussion. |
| Select a reference engine and initial component/wear mechanism. | No hardware access; reference engine and mechanism selection pending. |
| Define included/deferred MVP capabilities and the place of audio/visualization. | Sandbox priority confirmed; capability boundaries and audio/visualization pending. |
| Distinguish measurements, estimated states, load indicators, physical wear, and predictions. | Definitions recorded above; concrete quantities follow mechanism selection. |
| Prepare the four-objective mentoring matrix and topics to arbitrate. | Track matrix linked and sandbox-specific arbitration topics recorded above; refine with engine/problem selection. |
