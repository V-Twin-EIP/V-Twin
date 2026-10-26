# Technical KPIs and measurement protocol

**Tracking:** [PF.1 #39](https://github.com/V-Twin-EIP/V-Twin/issues/39). **Protocol revision:** 1.0.0, October 19, 2026. **Status:** KPI definitions and collection plan established; representative workload, reference-machine qualification, product baseline and technical budgets pending.

The first application is a local, single-user **batch sandbox**, with one numerical worker and optional 3D. Performance work must follow that scope. The real-engine twin has a later telemetry profile. The [initial tracking table](../benchmarks/README.md) records what is known and what has not been measured.

**October 26 update:** the nominal workload now references Adam's SCN-001/CONF-A and records the remaining input owners. An [executed analytical-core probe](../benchmarks/reports/foundation-probe-2026-10-26.json) exercises 30 repetitions with correctness checks, raw timings and source hashes. It is explicitly separate from the still-unmeasured product KPI/baseline and cannot set the application's latency or memory budgets. [ADR 0004](architecture/adr/0004-study-review-and-v1-boundary.md) records the review of Slakkos's studies.

## Confirmed user expectations

The owner confirmed these targets on October 19, 2026:

- **At most 60 seconds per calculation**, from browser submission until the required results and initial graphs are usable. This is a target for one calculation, not for two calculations plus comparison.
- **Less than one second** to open an already calculated result or change its displayed curve under the defined nominal result workload. Include any necessary retrieval, decoding and chart update.
- The [hardware register](../benchmarks/README.md#machine-register) was corrected by the owner on **October 24, 2026**: four machines have **16 GB RAM**, Adam's has **32 GB**. Pacien's i5-1135G7/Iris Xe supplies the integrated-graphics profile; Divin's i5-7300HQ/GTX 1050 Ti supplies a separate CPU/dedicated-GPU profile. OS/browser versions and measured behavior remain to be collected. System RAM is shared with the OS and browser, not allocated entirely to the engine.

These are user expectations, not observed performance, automatic execution timeouts, or measured resource budgets. First measure the workload, then decide whether the implementation meets the expectations and which changes are justified.

## Three primary sandbox KPIs

| Identifier | Definition and unit | Measurement boundary | Interpretation and initial budget |
| :--- | :--- | :--- | :--- |
| `run_ready_s` | Seconds from submission to usable results. Lower is better. | Start immediately before the browser submits one valid nominal case. Stop after all required results are retrieved, decoded and the required initial plots have completed their render/update callbacks. | User target: **each successful, correct nominal repetition ≤ 60 s**. Report median, p95, maximum and failures. Component allocations remain unset until baseline. |
| `simulation_rate` | Simulated seconds advanced divided by engine wall-clock seconds, in `s_sim/s_wall`. Higher is better. | Engine entry after frozen inputs are handed over, through numerical execution and emission of required outputs to its sink. Record the simulated interval actually completed. | No minimum fixed yet. This is throughput, not a requirement for a real-time simulator. Do not include queue waiting or browser work in its denominator. |
| `peak_sampled_app_rss_bytes` | Maximum of simultaneous sums of resident memory over the owned application process set, in bytes; display may use MiB. Lower is better for an equivalent workload. | API/coordinator, worker and a dedicated benchmark browser process tree, from idle-before-submit through usable results. Retain each group's trace and the idle baseline. | No cap fixed yet. The headroom required on the reported 16 GB reference profiles needs measurement. A core-only RSS observation is not this application KPI. |

All three are evaluated on the **same frozen workload and environment**. Keep failed, cancelled, interrupted, invalid and correctness-failing runs in the report with their counts/reasons. Successful latency summaries do not establish success when attempts failed. A fast, incorrect or incomplete result cannot pass.

For the 60-second target, a favorable p95 does not excuse a slower observed nominal repetition. Passing a finite measurement campaign is not a guarantee about every possible future execution.

### Supporting measurements

- `stored_result_ready_s`: opening one persisted result until its required charts are usable. User target **< 1 s**. Start with an empty client data cache; record backend/OS cache conditions without claiming unverified cold-disk reads.
- `curve_change_ready_s`: user selection of another required curve until it is usable, including a fetch when needed. User target **< 1 s**. Distinguish cached and fetched paths.
- Record validation, queue wait, engine wall time, publication, retrieval/decoding and initial rendering spans, plus output samples/bytes, solver evaluations and process-group RSS. These explain the primary KPIs; they are not additional primary product KPIs.
- Measure two-run comparison separately. Do not reinterpret the 60-second target as a total comparison budget. Compare only compatible, correct result sets and record the changed inputs.
- Startup, an occupied queue and optional 3D have separate scenarios. Record frame-time distribution and interaction failures for 3D when it exists; no FPS budget or graphics compatibility is claimed today.

## Clocks and event boundaries

Measure browser end-to-end and interaction durations with `performance.now()` in one document/time origin. Wait for the chart library's actual completion callback and a subsequent animation frame, with the required series available and controls enabled. An HTTP 200, completed job status or placeholder paint is not enough. Keep the page foreground and visible; mark visibility changes or automation failures explicitly. [Browser clock semantics](https://www.w3.org/TR/hr-time-3/).

Measure Python spans with `time.perf_counter_ns()` and convert differences to seconds. Record clock implementation/resolution and use UTC timestamps only for identifying/correlating records. Do not subtract browser and Python clock readings or wall clocks on separate machines to invent a duration. Keep concurrent spans separate rather than summing overlapping work. [Python performance counter](https://docs.python.org/3.13/library/time.html#time.perf_counter_ns).

The coordinator measures queue wait from persisted acceptance to dispatch, on its own clock. The engine reports its own wall span. Correlate these with the same campaign, attempt and run IDs. Boundaries for the future runner must implement these semantics in #8/#40/#46; this protocol does not claim that instrumentation is already present.

## Memory collection

The collector in #46 will sample `psutil.Process.memory_info().rss` for an explicitly owned process set. Start with a **50 ms sampling interval** as a collection setting, not a resource budget. Retain actual timestamps, missed samples, process identity `(PID, creation time)` and permission/process-exit errors. Count each process once, include spawned children and keep browser/application groups separate. A disappearing unobserved worker makes the trace incomplete, not zero memory. [psutil's memory API](https://github.com/giampaolo/psutil/blob/release-7.2.2/docs/index.rst#memory_info).

At each sampling tick, sum the current group RSS values, then take the maximum of those sums. Record collection timestamps/skew: reading several processes is not an atomic snapshot. **Do not sum independent per-process maxima.** Sample before submission and at completion as well. A sampled peak can miss short spikes; it is not a guaranteed high-water mark. RSS sums can count shared pages more than once, so they are a reproducible accounting measure, not exact unique physical usage. Do not compare OS-specific RSS semantics as if they were identical.

Run the browser with a dedicated profile/process tree to avoid attributing unrelated tabs. Record available system memory and swapping/paging indicators alongside RSS. Record monitor overhead by comparing instrumented and uninstrumented timing campaigns and a changed sampling interval. If the monitor materially changes conclusions or samples are incomplete, investigate before accepting the baseline. No arbitrary overhead threshold is introduced here.

## Workload and environment freeze

The [nominal-workload record](../benchmarks/workloads/sandbox-nominal-v1.json) is deliberately **not executable yet**. #3/#4/#7/#8 must provide the real case and correctness references. A five-second analytical decay test, health request or invented viscosity fixture cannot be called the product's nominal wear workload.

Before a product baseline, freeze and version:

| Group | Required record |
| :--- | :--- |
| Physical case | Engine/contact design, lubricant variant, calibration and initial state; source/evidence categories and content hashes. |
| Scenario | Simulated interval, speed/load/temperature history and its source, discontinuities, units and validity domain. |
| Numerical policy | Model/backend versions, binary64 policy, method, relative/per-state absolute tolerances, maximum steps, convergence/failure conditions and any seed. |
| Outputs and UI | Observable definitions, saved sample grid/count, authoritative bytes, selected initial curves, display-reduction method and bounded query parameters. Fix viewport, pixel ratio and dashboard-only mode. |
| Hardware/OS | Exact CPU/architecture, reported and measured RAM, OS/build, storage/free space, power mode, background load and graphics device when used. |
| Software | Source commit, dirty state/patch, Python/Node/npm/browser versions, dependency-lock hashes, BLAS/backend/thread settings, collector and protocol revision. |
| Execution | One worker, single user, empty queue for nominal runs; foreground browser, fixed cache conditions and local data storage. Record each deviation. |

Use the inventory command before measurement:

```sh
uv sync --locked --extra api
uv run --locked --extra api python scripts/performance_inventory.py --label pacien-16gb-igpu --output artifacts/performance/pacien-16gb-igpu.json
```

Run it on the **actual target computer**. It collects OS/CPU/RAM, runtime versions, lock hashes and clock metadata; remaining browser, graphics, power, display, background-load, BLAS and storage fields stay explicit until completed. It does not collect hostnames, account names, network addresses or serial numbers, and does not measure performance. Optional `--browser-name`, `--browser-version` and `--graphics` preserve reported information; they do not test graphics support. Keep the original inventory and annotate the campaign's manual context separately.

First qualify Pacien's integrated-graphics profile and Divin's separate CPU/dedicated-GPU profile, both with 16 GB reported RAM. Use the appropriate profile ID from the register when running the command on each actual machine. Raphael's and Mathieu's M4/16 GB Macs and Adam's i7-13620H/32 GB/RTX 5060 Laptop GPU are separate profiles; improvements on one do not qualify another. CI runner inventories establish the collection command's portability, not the performance of a team computer.

## Repetitions and statistics

1. Verify functional/numerical correctness and a complete workload/environment record before collecting product timing.
2. For a warm-application campaign, perform **3 declared warm-up attempts**, then **30 measured sequential attempts**, with an empty queue before each. These are initial protocol choices for practical repeated local testing, not statistically guaranteed tail coverage. Retain warm-up records separately.
3. Exercise opening stored results and changing curves with the same repetition plan. Keep empty-client-cache and warm-client-cache paths separate; declare backend/OS cache conditions. Do not silently drop a slow first read.
4. Measure startup separately with **10 fresh process launches**. This includes startup cost under declared cache conditions, without pretending that the OS disk cache was flushed. Do not mix these with warm-run statistics.
5. Retain every attempted run and its outcome. Report count, median, minimum, maximum and nearest-rank p95 of successful correct durations: sort `n` values and select one-based index `ceil(0.95 × n)`. With 30 values, index 29 is a coarse estimate; show raw values. Do not claim a production p95 SLA from this sample.
6. Aggregate simulation rates per attempt; also report total simulated duration / total engine wall time. Never substitute a mean of rates for that aggregate. Report duration-weighting and incomplete-run exclusions explicitly.
7. For optimization comparisons, run baseline and candidate in alternating blocks on the same machine/workload/settings, with **3 blocks of 10 measured attempts per version** after their warm-ups. Preserve versions and all raw records, report variation and correctness alongside gains. Do not pool different machines, workloads or cache modes.

Increasing load, stress, cancellation, interruption, reconnect and invalid-data campaigns belong to #46. They must record rejection/failure behavior and resource limits separately from the nominal user targets. Stress the bounded queue deliberately; do not require an occupied queue to satisfy an empty-queue latency claim.

## Budget adoption after baseline

| Item | State now | Adoption rule |
| :--- | :--- | :--- |
| Nominal single-run latency | User target **≤ 60 s**; unmeasured. | Evaluate the complete path on the frozen reference case/machine; retain component spans and all failures. |
| Stored-result/curve interaction | User target **< 1 s**; unmeasured. | Evaluate the fixed query/output/plot workload, including retrieval and rendering. |
| Minimum simulation rate | **Unset.** | Derive a requirement from simulated duration and measured non-engine costs within the run target, then verify it on the reference profile. If the remaining time is nonpositive, address the path rather than inventing a rate. |
| Application RSS cap and headroom | **Unset.** | Measure application groups, idle/OS/browser needs, available memory and paging on the reference machine; propose and verify a cap that preserves usability under the declared conditions. |
| Queue length, run/output limits and stage allocations | **Unset.** | Choose from representative size/load/resilience results, document the trade-off, then validate enforcement and failure behavior. |
| CI timing-regression threshold | **Unset.** | Assess runner variability and baseline stability first. Ordinary shared-runner timing does not justify a hard wall-time gate. |

For every proposed budget, retain its value/unit, workload revision, machine profile, raw baseline/report links, variability, rationale, correctness guardrails, owner/reviewer and adoption date. The technical owner `rchrp` reviews the measured proposal with the team. A changed model, output volume, machine or numerical tolerance triggers a recorded reevaluation rather than silent budget drift.

#46 can start from this versioned protocol while **#39's workload/budget criteria remain open**. It returns baseline evidence and proposed budgets to #39; it does not need #39 to falsely claim measured budgets before the first measurement. Telemetry-specific #35 prerequisites apply to the later twin campaign, not to an independent sandbox baseline.

## Correctness guardrails

- Run the numerical, contract and adapter checks before accepting a timing campaign. Preserve [the analytical references](development.md#quality-and-tests), but do not treat them as physical engine validation.
- The product workload needs #4's independent evaluation data, justified per-observable tolerances/domain and calibration/evaluation separation. Until available, tag outputs as unvalidated/synthetic and keep the physical claim pending.
- Reject incomplete trajectories, nonfinite outputs, mismatched definitions/units and missing provenance. Compare supported outputs with the same numerical/physical tolerances before and after an optimization.
- A changed tolerance, sampling grid, downsampling rule, precision, physical law or output set changes the workload or correctness contract. Report that trade-off; do not call it an equivalent speedup automatically.
- Preserve errors/timeouts/cancellations. Neither 60 s nor 1 s automatically stops a correct calculation; execution limits and cancellation have their own policy in #40.

## Logs, reports and development cycle

The future collector writes one structured attempt record and referenced memory/event traces per attempt. Include `protocol_version`, `campaign_id`, `attempt_id`, `run_id`, workload/environment hashes, code/lock/model versions, scenario, warm-up flag, cache/3D mode, outcome, correctness result, duration spans, completed simulated duration, output samples/bytes, process groups and sample-completeness status. Unavailable measurements are `null` with a reason, never zero. Errors retain their run/attempt correlation without launch tokens or input secrets.

Store raw JSON/JSONL and summary tables together with the exact command and inventories. Keep large traces in identified CI/release artifacts; retain stable links and hashes in the small versioned report. The [tracking table](../benchmarks/README.md) starts with **no product baseline**. The implemented inventory command produces metadata only.

- **Every PR:** existing correctness/quality checks and inventory-command integration test. CI uploads its own environment metadata without comparing performance across runners.
- **In #46:** implement instrumentation, collectors, reports and the reduced repeatable performance scenario. Keep timing informational until its environment and variability justify a regression gate.
- **Before a performance claim/release:** execute the full reference-machine protocol, check numerical/physical guardrails and record budget adoption.
- **In #47:** profile a measured bottleneck, change the implementation and publish the same-workload before/after evidence and trade-offs.

## Later real-engine twin

For the telemetry profile, replace the sandbox latency focus with **source-to-consumer telemetry latency (p95)**; keep replay/simulation rate and scoped application memory as relevant. Source-event, transport, processing/persistence and consumer-availability boundaries, payload/rate, ordering/duplicates/loss and session coverage must be frozen in #2/#35/#42/#46.

One source/consumer machine can use a verified common clock; different machines need measured clock synchronization error or another method that does not subtract unrelated clocks. Record that uncertainty with one-way latency; an RTT/echo is a different measurement and must retain that name. No telemetry latency budget or successful live acquisition is claimed for this sandbox-first protocol.
