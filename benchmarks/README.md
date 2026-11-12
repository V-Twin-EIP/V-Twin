# Performance tracking

**PF.1 #39:** [KPI definitions, targets and protocol](../docs/performance.md). Initial tracking state: **October 19, 2026**. This table records missing measurements explicitly; it is not a performance baseline.

## Initial KPI register

| Metric | User expectation | Measured baseline | Adopted technical budget | Next evidence |
| :--- | :--- | :--- | :--- | :--- |
| Primary: single-run `run_ready_s` | ≤ 60 s per calculation, through usable initial graphs. | Browser path not measured. API part on the kinematic demo, Raphael's M4: median 306 ms, p95 447 ms, max 457 ms (30 runs, [Nov 12](reports/runner-api-baseline-2026-11-12.md)). | Stage allocations unset. | Measure the browser path with #51; freeze the SCN-001 case #3/#4. |
| Primary: `simulation_rate` | Batch workflow; no real-time requirement. | Kinematic demo only: 312 s_sim/s_wall aggregate (closed-form model; not indicative of the tribology model). | Minimum unset. | Re-measure with the first ODE/contact model. |
| Primary: `peak_sampled_app_rss_bytes` | Usable on the reported 16 GB Pacien and Divin profiles, including dashboard-only operation. | Without browser, M4: idle coordinator 96 MiB; nominal coordinator + worker 170 MiB; 347 MiB at 1 M output samples. | RSS cap/headroom unset. | Add the browser group with #51; run on Pacien's and Divin's machines. |
| Supporting: stored-result/curve readiness | < 1 s, including required retrieval and rendering. | API retrieval and decoding only: 1.4 ms median for 721 samples; 1.45 s for 1 M samples (50 pages). Rendering not measured. | Per-stage/query budgets unset. | Measure chart rendering with #51. |
| Future twin: telemetry p95 | To define for the acquisition/consumer workflow. | Not measured. | Unset. | Signals/clock/payload/workload from #2/#35/#42. |

We set targets of **one minute per calculation** and **less than one second for result exploration**. Neither target is a measurement. There is no published engine timing, memory qualification or adopted regression threshold yet.

## Machine register

We recorded our team hardware on **October 24, 2026**. The [machine-readable inventory](hardware-inventory.json) preserves the reported values and unknown fields.

| Member / profile | CPU as reported | RAM | Graphics as reported |
| :--- | :--- | :--- | :--- |
| Pacien / `pacien-16gb-igpu` | 11th Gen Intel Core i5-1135G7 (x8 reported) | 16 GB | Intel Iris Xe Graphics (TGL GT2), integrated. |
| Divin / `divin-16gb-gtx1050ti` | Intel Core i5-7300HQ (x4 reported) | 16 GB | NVIDIA GeForce GTX 1050 Ti. |
| Raphael / `raphael-m4-16gb` | MacBook Pro, Apple M4 | 16 GB | Exact graphics configuration not supplied. |
| Mathieu / `mathieu-m4-16gb` | MacBook Pro, Apple M4 | 16 GB | Exact graphics configuration not supplied. |
| Adam / `adam-32gb-rtx5060` | 13th Gen Intel Core i7-13620H (2.40 GHz reported) | 32 GB | NVIDIA GeForce RTX 5060 Laptop GPU, 8 GB VRAM reported. |

The lowest reported system RAM is now **16 GB**. Divin's previous hardware description is superseded. Use **Pacien** for the integrated-graphics profile and **Divin** for a separate CPU/dedicated-GPU profile; their relative performance is not established. Keep dashboard-only operation available on every profile. The `x8`/`x4` multipliers are retained as reported and are not assertions about physical core counts.

These are reported specifications, not automatic inventories or benchmark results. Exact OS/browser versions, power/display settings, storage, BLAS/thread configuration and measured behavior still need collection on each machine. The two Macs remain distinct profiles even though the supplied specifications match. Hosted `ci-<os>` inventories establish collector portability, not qualification of any team computer.

## Collect an inventory

From a developer installation on the machine being recorded:

```sh
uv run --locked --extra api python scripts/performance_inventory.py --label pacien-16gb-igpu --output artifacts/performance/pacien-16gb-igpu.json
uv run --locked --extra api python scripts/performance_inventory.py --label divin-16gb-gtx1050ti --output artifacts/performance/divin-16gb-gtx1050ti.json
```

Run each command on the corresponding machine. Complete the browser, power/display, graphics, background-load, BLAS/thread and storage context before benchmarking. Automatic unknowns remain `null`; hardware labels do not invent missing specifications. Generated local reports are ignored under `artifacts/` and CI inventories accompany that run's artifacts.

The [nominal-workload record](workloads/sandbox-nominal-v1.json) lists the prerequisites for product measurements. It remains explicitly **not ready for execution** until its references and correctness criteria are frozen. #46 will add the real measurement command, raw records and baseline report. No engine benchmark command is advertised before it exists.

## October 26 progress

The nominal case is now explicitly linked to Adam's **SCN-001 / CONF-A** and its source revision. The workload record lists the remaining input owners; unresolved physical values are not replaced with arbitrary numbers.

An [analytical-core timing probe](reports/foundation-probe-2026-10-26.json) has been executed locally with 3 warm-ups and 30 measured, correctness-checked attempts. It measures the existing `y'=-y` check in one Python process. Raw attempts, timing statistics, runtime information and source hashes are retained. Its RSS observations are taken after each attempt and are **not application memory peaks**.

Reproduce that component-only observation with:

```sh
uv run --locked --extra api python scripts/measure_foundation.py --output artifacts/performance/foundation-probe.json
```

This is not the product baseline: no physical model, browser, queue, result publication or graphs are exercised. The three product KPI measurements and their technical budgets remain open.

## November 12 runner API baseline (#46)

[Report](reports/runner-api-baseline-2026-11-12.md) and [raw attempts](reports/runner-api-baseline-2026-11-12.json), recorded on `raphael-m4-16gb` at commit `e5c8ad3`. The worktree was flagged dirty only because of two untracked local folders outside the source tree (`.blame/`, `output/`). Workload: [kinematic-demo-v1](workloads/kinematic-demo-v1.json). Reproduce with:

```sh
uv run --locked --extra api python scripts/benchmark_runner.py --label raphael-m4-16gb --output benchmarks/reports/runner-api-baseline-<date>.json
```

**Path measured: HTTP API, no browser.** A Python client on loopback submits the case to `vtwin serve`; one worker is spawned, results are published, then every series page is fetched and decoded. The browser `run_ready_s` stays `null`: chart rendering and the first readable graph belong to #51.

| Result | Value | Reading |
| :--- | :--- | :--- |
| Nominal API run ready, 30 correct attempts | median 306 ms, p95 447 ms, max 457 ms | 98 % of it is spent between acceptance and the terminal state, while the engine itself takes 0.18 ms: starting a fresh `spawn` worker (Python + NumPy import) dominates. |
| Series retrieval and decoding, 721 samples | median 2.0 ms | Negligible at the demo size. |
| Stored result read | median 1.4 ms, max 5.0 ms | API part only of the < 1 s target. |
| Output ramp up to 997 201 samples | run ready 2.05 s, of which retrieval 1.45 s for 73.5 MB of JSON; peak RSS 347 MiB | Each 20 000-sample page re-verifies and reloads the whole series file. Fine for the demo; the first candidate for #47 at large volumes. |
| 8 simultaneous submissions × 3 rounds | 1 accepted, 7 `workspace_busy` each round; `/health` p95 ≤ 8.6 ms during the run | Single execution is enforced, and the coordinator stays responsive while the worker computes. |
| Resilience, 6 scenarios / 37 checks | all PASS | Invalid, foreign and oversize requests; out-of-order requests; duplicates; worker crash; coordinator killed mid-run (1440/7201 samples committed), restarted and resumed; hung worker stopped by the timeout. Resumed series are bit-identical to an uninterrupted run, with exact sample counts. |

All faults are **software** faults, injected with `VTWIN_FAULT_INJECTION`. No physical defect is simulated: SCN-004/005 need the tribology model.

### Proposals returned to #39

These are proposals from one machine and a demo workload, not adopted budgets.

- `run_ready_s`: the API part uses about 0.5 % of the 60 s target. The budget question moves to the browser part (#51) and the future physical model. Measure those before allocating stages.
- Worker start-up (≈ 0.3 s per run) is the dominant fixed cost. A persistent worker would remove most of it; justify it in #47 once a real model makes the cost visible, as it would weaken isolation.
- Result reads: keep pages at 20 000 samples, and cache the verified series per run or move to a column format before raising output limits. The < 1 s exploration target holds up to about 360 000 samples on this path (354 ms).
- Memory: the measured application group stays below 0.4 GiB without browser at the 1 M-sample limit, so the current output limit is compatible with a 16 GB machine. Confirm on Pacien's and Divin's machines before setting a cap.
- CI: `tests/test_benchmark_runner.py` runs the reduced `--quick` campaign on every OS and checks behaviour and correctness only. No timing threshold is set, because shared runners vary.
