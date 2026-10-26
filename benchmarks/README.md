# Performance tracking

**PF.1 #39:** [KPI definitions, targets and protocol](../docs/performance.md). Initial tracking state: **October 19, 2026**. This table records missing measurements explicitly; it is not a performance baseline.

## Initial KPI register

| Metric | User expectation | Measured baseline | Adopted technical budget | Next evidence |
| :--- | :--- | :--- | :--- | :--- |
| Primary: single-run `run_ready_s` | ≤ 60 s per calculation, through usable initial graphs. | Not measured. | Stage allocations unset. | Freeze nominal case #3/#4/#7/#8; measure the full path in #46. |
| Primary: `simulation_rate` | Batch workflow; no real-time requirement. | Not measured. | Minimum unset. | Engine span and simulated interval from the same nominal case in #46. |
| Primary: `peak_sampled_app_rss_bytes` | Usable on the reported 16 GB Pacien and Divin profiles, including dashboard-only operation. | Not measured. | RSS cap/headroom unset. | Complete each machine's environment inventory, then sample application/browser groups in #46. |
| Supporting: stored-result/curve readiness | < 1 s, including required retrieval and rendering. | Not measured. | Per-stage/query budgets unset. | Fix result volume/curves and cache modes; measure in #46. |
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
