# Performance tracking

**PF.1 #39:** [KPI definitions, targets and protocol](../docs/performance.md). Initial tracking state: **October 19, 2026**. This table records missing measurements explicitly; it is not a performance baseline.

## Initial KPI register

| Metric | User expectation | Measured baseline | Adopted technical budget | Next evidence |
| :--- | :--- | :--- | :--- | :--- |
| Primary: single-run `run_ready_s` | ≤ 60 s per calculation, through usable initial graphs. | Not measured. | Stage allocations unset. | Freeze nominal case #3/#4/#7/#8; measure the full path in #46. |
| Primary: `simulation_rate` | Batch workflow; no real-time requirement. | Not measured. | Minimum unset. | Engine span and simulated interval from the same nominal case in #46. |
| Primary: `peak_sampled_app_rss_bytes` | Usable on the reported 8 GB machine, dashboard-only. | Not measured. | RSS cap/headroom unset. | Inventory the actual machine, then sample application/browser groups in #46. |
| Supporting: stored-result/curve readiness | < 1 s, including required retrieval and rendering. | Not measured. | Per-stage/query budgets unset. | Fix result volume/curves and cache modes; measure in #46. |
| Future twin: telemetry p95 | To define for the acquisition/consumer workflow. | Not measured. | Unset. | Signals/clock/payload/workload from #2/#35/#42. |

The user confirmed **one minute per calculation** and **less than one second for result exploration**. Neither target is a measurement. There is no published engine timing, memory qualification or adopted regression threshold yet.

## Machine register

| Profile | Reported information | Inventory/qualification status |
| :--- | :--- | :--- |
| `reference-8gb` | Divin's computer: 8 GB RAM and integrated graphics. | CPU, OS, browser and remaining context unknown. Run the inventory on that computer; performance qualification pending. |
| `mac-m4-a`, `mac-m4-b` | Two developer Macs reported as M4. | Collect each exact configuration separately. Neither substitutes for the low-memory reference. |
| `workstation-a`, `workstation-b` | Two other developer workstations. | Exact hardware/software inventory pending. |
| `ci-<os>` | Hosted Windows/macOS/Linux runner from a specific workflow run. | Inventory command exercised in CI; runner metadata is not a product baseline or a reference-PC qualification. |

## Collect an inventory

From a developer installation on the machine being recorded:

```sh
uv run --locked --extra api python scripts/performance_inventory.py --label reference-8gb --output artifacts/performance/reference-8gb.json
```

Complete the browser, power/display, graphics, background-load, BLAS/thread and storage context before benchmarking. Automatic unknowns remain `null`; hardware labels do not invent missing specifications. Generated local reports are ignored under `artifacts/` and CI inventories accompany that run's artifacts.

The [nominal-workload record](workloads/sandbox-nominal-v1.json) lists the prerequisites for product measurements. It remains explicitly **not ready for execution** until its references and correctness criteria are frozen. #46 will add the real measurement command, raw records and baseline report. No engine benchmark command is advertised before it exists.
