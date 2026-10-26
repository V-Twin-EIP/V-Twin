# Technical Track: coverage and evidence plan

This plan connects V-Twin's two product applications to the four Epitech Technical Track objectives selected by the team. It preserves the seven product milestones and adds the work needed to demonstrate technical decisions, quality, collaboration, and performance.

The reference is the team-supplied **Technical Track guide, v1**, in `G-EIP-600_track_technical.pdf`: PDF pages 3–6 for the mandatory objectives and pages 10–12 for the selected complementary objectives. The team's mentoring notes provide additional delivery targets. Those targets are distinguished from the guide's requirements below.

## Selected objectives

| Code | Selected objective | Label |
| :--- | :--- | :--- |
| **O1** | Evaluating and Integrating New Technologies (Technology Watch) | [`track:tech-watch`](https://github.com/V-Twin-EIP/V-Twin/labels/track%3Atech-watch) |
| **O2** | Structure, Document, and Harden the Project's Technical Architecture | [`track:architecture`](https://github.com/V-Twin-EIP/V-Twin/labels/track%3Aarchitecture) |
| **C1** | Collaborate with Technical Experts | [`track:experts`](https://github.com/V-Twin-EIP/V-Twin/labels/track%3Aexperts) |
| **C2** | Measure, Test, and Optimize Technical Performance | [`track:performance`](https://github.com/V-Twin-EIP/V-Twin/labels/track%3Aperformance) |

O1 and O2 are mandatory. C1 and C2 are the team's two chosen complementary objectives; they are numbered **3 and 4** in the guide's full complementary list. An issue may support several objectives. Its labels indicate intended coverage, not academic validation.

## What changed in the roadmap

The initial 28 objectives already addressed engine modeling, data contracts, architecture, reproducibility, and physical validation. They needed more explicit work for technology-watch evidence, external expert collaboration, and software performance measurement and optimization.

The updated plan contains **47 objectives**: the 28 product objectives plus **19 supporting objectives**. Existing issues retain their product scope and gain track labels, acceptance criteria, and links to the supporting work. All seven milestones remain in use.

| Objective | Work and evidence | Main issues |
| :--- | :--- | :--- |
| **O1 · Watch and adoption** | Dated watch journal; four comparative studies; two POCs; transport and storage benchmarks; a justified integration; community exchanges; final decision synthesis. | [Journal #29](https://github.com/V-Twin-EIP/V-Twin/issues/29), [studies #30](https://github.com/V-Twin-EIP/V-Twin/issues/30), [#31](https://github.com/V-Twin-EIP/V-Twin/issues/31), [#32](https://github.com/V-Twin-EIP/V-Twin/issues/32), [#33](https://github.com/V-Twin-EIP/V-Twin/issues/33), [POCs #34](https://github.com/V-Twin-EIP/V-Twin/issues/34), [#35](https://github.com/V-Twin-EIP/V-Twin/issues/35), [benchmarks #42](https://github.com/V-Twin-EIP/V-Twin/issues/42), [#43](https://github.com/V-Twin-EIP/V-Twin/issues/43), [adoption #44](https://github.com/V-Twin-EIP/V-Twin/issues/44), [synthesis #45](https://github.com/V-Twin-EIP/V-Twin/issues/45). |
| **O2 · Architecture and quality** | Justified V1 architecture, UML and flow/deployment diagrams; documented structure and configuration; quality checks and critical-module tests; error handling, logs, initial security, and reproducible installation/deployment. | [Architecture #5](https://github.com/V-Twin-EIP/V-Twin/issues/5), [repository and CI #6](https://github.com/V-Twin-EIP/V-Twin/issues/6), [contracts #7](https://github.com/V-Twin-EIP/V-Twin/issues/7), [reliability #40](https://github.com/V-Twin-EIP/V-Twin/issues/40), [configuration and technical docs #41](https://github.com/V-Twin-EIP/V-Twin/issues/41), [delivery #28](https://github.com/V-Twin-EIP/V-Twin/issues/28). |
| **C1 · Experts** | Specific questions and relevant external profiles; documented outreach and review; advice applied and verified; a follow-up review of model validation. | [Preparation #36](https://github.com/V-Twin-EIP/V-Twin/issues/36), [first review and action #37](https://github.com/V-Twin-EIP/V-Twin/issues/37), [follow-up #38](https://github.com/V-Twin-EIP/V-Twin/issues/38). |
| **C2 · Performance** | Two to three primary KPIs; measurement protocol; baseline; load, stress and resilience scenarios; profiling; an applied optimization with comparable before/after results. | [KPIs #39](https://github.com/V-Twin-EIP/V-Twin/issues/39), [test harness #46](https://github.com/V-Twin-EIP/V-Twin/issues/46), [optimization #47](https://github.com/V-Twin-EIP/V-Twin/issues/47), [transport #42](https://github.com/V-Twin-EIP/V-Twin/issues/42), [storage #43](https://github.com/V-Twin-EIP/V-Twin/issues/43), [final evaluation #25](https://github.com/V-Twin-EIP/V-Twin/issues/25). |

## O1: evaluate, experiment, decide, integrate

### Guide requirements and team targets

| Guide requirement | V-Twin delivery target |
| :--- | :--- |
| Regular, relevant watch using varied credible sources, with analysis and team sharing. | A dated journal, source index, and a proposed weekly team review cadence. Record the question, findings, limits, and effect on a project decision. |
| Comparative analysis and one or more technical benchmarks. | Four studies and two comparative benchmarks, with reproducible methods and raw results. These quantities are team targets. |
| One to two concrete experiments. | Two POCs: acquisition and MQTT telemetry. Record successes, failures, and what each experiment establishes. |
| At least one new technology integrated with working evidence and justification. | Adopt at least one technology explored by the team in a working product path. Document why it represents new exploration for the team. |
| Active technical-community participation and documented learning. | One to two documented technical interactions, with a precise question, a shareable trace, and the lesson applied or considered. The quantity is a team target. |
| Reasoned decisions, including rejected options and impact on the project. | ADRs during development and a final synthesis linking studies, experiments, measurements, and adoption. |

### Four comparative studies

1. **Acquisition paths:** OBD-II access, direct/passive CAN access, and additional sensors. Distinguish protocol layers and access methods, then compare the signals actually accessible on the reference engine, timing, precision, equipment, and constraints.
2. **Telemetry transport:** MQTT, WebSocket, REST, and Server-Sent Events. Define direction, workload, delivery guarantees, reconnection, and consumers before comparing options.
3. **Time-series storage:** InfluxDB and TimescaleDB. Fix versions/editions, dataset, cardinality, retention, ingestion patterns, and representative queries.
4. **Wear estimation:** physical models, ML, and hybrid approaches. Compare data needs, observability, calibration, interpretability, generalization, uncertainty, and computational cost.

Each study records sources, alternatives, strengths, limitations, learning curve, maintainability, project fit, and a reasoned recommendation. MQTT and either database remain candidates until the experiments and measurements support a decision.

The acquisition POC must distinguish hardware acquisition from replay and synthetic inputs. A transport POC can use declared synthetic data to proceed while access to the real engine is being arranged. Neither a successful POC nor an installed dependency alone demonstrates production-path integration.

The watch journal starts early and continues alongside development. Its ongoing follow-up does not block the comparative studies from starting.

## O2: document and harden the foundation

The early architecture deliverable in [#5](https://github.com/V-Twin-EIP/V-Twin/issues/5) covers components, dependencies, interfaces, storage, flows, deployment, versioning, and justified choices. Include suitable UML views of structure and a critical interaction, alongside a data-flow and deployment view. Record assumptions and revisit decisions after experiments and expert feedback.

The [working V1 design and ADRs](architecture/README.md) provide those architecture views and a local API/replaceable-engine boundary. We selected Windows/macOS/Linux targets, developer installation, batch calculation followed by exploration, and dashboard-only operation. The [corrected hardware register](../benchmarks/README.md#machine-register) now records 16 GB reference profiles for Pacien (integrated graphics) and Divin (dedicated GPU), plus two M4/16 GB Macs and Adam's 32 GB workstation. Numerical acceptance and measured performance remain tied to #4/#39; the architecture does not complete those checks.

The foundation also includes:

- A documented repository/module structure, linting, formatting, and a reproducible quality-analysis report suited to the selected stack.
- Unit or validation tests for at least one critical module, with a command and recorded result in CI.
- Explicit error handling, input validation, useful correlated logs, configuration management, and initial security controls.
- A technical README covering prerequisites, installation/deployment, module layout, commands, and environment variables.
- `.env.example` and relevant development/production configuration examples containing no real secrets.
- Reproducible setup/deployment instructions or scripts, checked from a clean checkout, plus backup/restore procedures for the stored data in scope.

[Reliability #40](https://github.com/V-Twin-EIP/V-Twin/issues/40) and [configuration/docs #41](https://github.com/V-Twin-EIP/V-Twin/issues/41) make these deliverables explicit. Error handling and initial security begin with the first modules. Deeper security analysis can follow the risks and maturity of the system.

SonarQube/Cloud is a possible quality tool; the guide also accepts other appropriate analysis tools. Docker is a possible way to reproduce deployment. Select and justify tools after the stack and operational needs are known.

## C1: collaborate with technical experts

The expert work begins with concrete questions tied to V-Twin's uncertainties:

| Topic | Questions to challenge |
| :--- | :--- |
| Vehicle data and instrumentation | Which required signals can the reference engine expose? What precision, sampling, and additional instrumentation are needed? |
| Thermodynamics, tribology, and wear | Which initial degradation mechanism is observable and measurable? How should it be calibrated and independently validated? |
| Architecture, storage, and performance | Are the proposed boundaries, failure handling, storage choices, and performance protocols appropriate for the expected workloads? |

Identify relevant specialists beyond the immediate group and the EIP mentor alone. The plan targets an initial architecture/acquisition review, then a follow-up review of model-validation results. These two checkpoints are the team's collaboration plan.

For each exchange, retain the expert's relevant profile, a focused request, a shareable record of the exchange, a memo, decisions and reasons, and links to changes actually applied and verified. A prepared message or informal conversation without trace and action is not sufficient evidence. Share only material appropriate for publication.

## C2: measure software performance and improve it

Physical-model accuracy and software performance answer different questions. Preserve independent physical validation while measuring the cost and responsiveness of the implementation.

The [PF.1 measurement protocol](performance.md) selects **three primary sandbox KPIs** for the batch-first scope:

| KPI | Meaning | Measurement considerations |
| :--- | :--- | :--- |
| Submission-to-usable-result latency | Delay from one browser submission through required results and usable initial graphs. | Our target is ≤ 60 seconds per calculation; report median, p95, maximum and all failures on a fixed workload/machine. |
| Simulation real-time factor | Simulated seconds divided by elapsed wall-clock seconds. | Fix engine, scenario, simulation duration, numerical settings, and hardware. |
| Peak sampled application RSS | Maximum simultaneous RSS sum for coordinator, worker and dedicated benchmark browser. | Retain group traces and sample completeness; evaluate actual system headroom on the reported 16 GB reference profiles. |

We also set a **less-than-one-second** target for opening stored results or changing curves; this is a supporting interaction metric. Telemetry end-to-end p95 becomes the latency focus for the later twin profile, with source/consumer clock and acquisition requirements defined separately. Local transport/database benchmarks retain their workload-specific measures.

The [initial tracking register](../benchmarks/README.md) and [nominal-workload record](../benchmarks/workloads/sandbox-nominal-v1.json) expose the remaining evidence gaps. #39 stays open for the frozen nominal workload and justified budgets after baseline. #46 can use the protocol to obtain that baseline; it must not require invented budgets to begin. The environment inventory command is implemented and exercised in CI, while product timing/memory measurements are not yet available.

The test harness in [#46](https://github.com/V-Twin-EIP/V-Twin/issues/46) covers nominal operation, increasing load, stress, interruption/reconnection, unexpected inputs, and replay/recovery behavior. Record versions, hardware, configuration, workload, repetitions, raw data, and result variability. Keep functional correctness, numerical tolerances, and data integrity as guardrails.

For [#47](https://github.com/V-Twin-EIP/V-Twin/issues/47), profile a measured bottleneck, apply an optimization, and rerun the same protocol against the initial and optimized versions. Report gains and limits, including trade-offs in accuracy, complexity, resource use, and maintenance.

## Prepare the next mentoring meeting

The next mentoring meeting is **Monday, October 26, 2026**. Use the `mentoring:next` label to find its preparation work. Present available evidence, recommendations, open decisions, and remaining work; inclusion in the review does not mark an issue complete or commit the executable product for that date. The [five-person team allocation](product-scope.md#team-and-work-allocation) records all five assignable members. Since October 24, #7 and #41 are assigned to divin0i for the review; #24 is also assigned for subsequent visualization work.

Project views: [team preparation](https://github.com/orgs/V-Twin-EIP/projects/1/views/10) and [Prochain Mentorat mon travail](https://github.com/orgs/V-Twin-EIP/projects/1/views/11). The personal view combines the mentoring label with `assignee:@me`, as explained in the [team allocation](product-scope.md#team-and-work-allocation).

| Bring to the meeting | Issues and expected discussion |
| :--- | :--- |
| Product scope, reference engine, scenarios, and evidence plan. | [#1](https://github.com/V-Twin-EIP/V-Twin/issues/1), [#3](https://github.com/V-Twin-EIP/V-Twin/issues/3), [#4](https://github.com/V-Twin-EIP/V-Twin/issues/4): what is observable, what will be demonstrated, and how it will be checked. AdamTamboura leads #3/#4. |
| Architecture V1 and a justified repository/configuration plan. | [#5](https://github.com/V-Twin-EIP/V-Twin/issues/5), [#6](https://github.com/V-Twin-EIP/V-Twin/issues/6), [#41](https://github.com/V-Twin-EIP/V-Twin/issues/41): UML, flows, responsibilities, initial setup assumptions, and decisions still to test. |
| An initialized watch journal and comparative questions. | [#29](https://github.com/V-Twin-EIP/V-Twin/issues/29): sources, novelty for the team, cadence, and planned experiments. |
| Four comparative studies led by Slakkos. | [#30](https://github.com/V-Twin-EIP/V-Twin/issues/30): OBD-II/CAN/sensors; [#31](https://github.com/V-Twin-EIP/V-Twin/issues/31): MQTT/WebSocket/REST/SSE; [#32](https://github.com/V-Twin-EIP/V-Twin/issues/32): InfluxDB/TimescaleDB; [#33](https://github.com/V-Twin-EIP/V-Twin/issues/33): physical/ML/hybrid wear approaches. Bring sources, comparison criteria, V-Twin fit, recommendations, and experiments or evidence still needed. |
| Expert topics, suitable profiles, and precise questions. | [#36](https://github.com/V-Twin-EIP/V-Twin/issues/36): which decisions need external challenge and what outcome is sought. |
| Candidate KPIs and a measurement protocol. | [#39](https://github.com/V-Twin-EIP/V-Twin/issues/39): how a baseline and fair before/after comparison will be obtained. |

The README overview, license, issue-based roadmap, working architecture/UML views, and [initial development foundation](development.md) are present. The foundation provides a runnable module structure, a small configuration example, analytical numerical/adapter tests, quality reports, and CI jobs. Full physical models, persistent execution/storage, and the error/logging/security work in #40 still require their own evidence. The team's list of accepted sub-objectives is treated as agreed scope; completion requires evidence linked to the relevant issue.

## Evidence and completion rules

Use a small, reviewable evidence index. Suggested locations below are targets for future deliverables, not a claim that these artifacts already exist:

| Area | Suggested evidence location |
| :--- | :--- |
| Architecture and decisions | `docs/architecture/`: diagrams, module contracts, deployment, ADRs. |
| Watch and adoption | `docs/technology-watch/`: journal, sources, comparative briefs, decisions, community learning. |
| Expert collaboration | `docs/experts/`: questions, shareable exchange records, memos, and links to applied changes. |
| Performance | `benchmarks/` and `docs/performance/`: scripts, environment, workloads, raw results, baseline, and before/after analysis. |

Close an issue when its acceptance criteria and evidence are satisfied. P0 means a demonstrator prerequisite or essential track evidence; P1 identifies a planned extension. Preserve links between a decision, its experiment or review, the implementation change, and its verification.

The final delivery in [#28](https://github.com/V-Twin-EIP/V-Twin/issues/28) consolidates all four objectives. The mentoring review determines academic validation; labels, issue counts, and planned documents alone do not establish it.
