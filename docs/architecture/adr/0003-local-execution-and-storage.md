# ADR 0003 Local execution and result storage

**Status:** working V1 baseline, October 18, 2026. Scoped to local single-user batch runs; future live telemetry storage remains subject to #32/#43.

## Decision

Use one local coordinator/API process and **at most one numerical worker at a time** initially. A bounded queue holds accepted requests. Persist accepted jobs before acknowledging them, and execute the numerical engine in a child process so the API can continue serving status and completed results.

Use the Python standard library's process facilities with an explicit compatible context such as `spawn`; keep the execution adapter replaceable. Python documents process-based execution on POSIX and Windows. FastAPI cautions that heavy computation needs a different execution arrangement from small in-process background tasks. These sources motivate process isolation; they do not benchmark V-Twin or require a distributed queue. [Python processes](https://docs.python.org/3.13/library/multiprocessing.html), [FastAPI background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/).

Keep child-process messages small: run IDs, manifest references, progress/diagnostic envelopes, and artifact references. Do not send the full result history through a process queue or poll it into every HTTP response. Cancellation requests are tracked separately from completed cancellation; finalize a terminal state after the worker stops. On restart, reconcile active jobs as interrupted; automatic numerical resume is a later capability requiring compatible checkpoints.

### Storage roles

| Store | Contents | Ownership |
| :--- | :--- | :--- |
| **SQLite catalogue** | Run IDs, lifecycle state, immutable manifest references, comparison relationships, artifact inventory, and schema revisions. | Coordinator is the sole catalogue writer in V1. No direct access from browser or worker. |
| **JSON snapshots/manifests** | Resolved design, calibration/scenario references, units, provenance, model/code/numerical settings, and observable definitions. | Frozen within the run's artifact directory. |
| **Parquet result files through PyArrow** | Numerical time-series columns and quality/status fields where applicable; binary64 numerical columns for the initial engine. | Worker writes only its assigned staging area; coordinator publishes verified artifacts. |

SQLite documents local application storage as an appropriate use. Parquet/PyArrow provide column selection and filtered reads; these capabilities fit bounded observable/time queries, without establishing a V-Twin-specific speed result. [SQLite use cases](https://www.sqlite.org/whentouse.html), [PyArrow Parquet reads](https://arrow.apache.org/docs/python/parquet/parquet.html).

The result-read adapter selects the requested columns/time interval and caps response size. Dashboard summaries or display downsampling identify their derivation; quantitative validation/export uses the authoritative stored result. Keep storage layout and Parquet-specific types behind the adapter so a new store does not change numerical models or the UI API.

## Publication and recovery

The worker writes to a run-specific staging directory on the application data filesystem. On completion, the coordinator checks the result contract, inventory and checksums, publishes immutable files within that filesystem, then commits the completed catalogue state. A filesystem rename and a SQLite transaction are **not one transaction**: startup reconciliation must detect staged leftovers, orphaned artifacts, and catalogue entries missing artifacts. Publish failure/incomplete state instead of presenting a partial run as successful.

A backup pauses submissions and settles/stops active work, snapshots the catalogue with a supported SQLite backup operation, and copies the referenced immutable artifacts and manifests. Restore verifies catalogue/artifact consistency and checksums before opening runs. The same retention policy removes catalogue references and artifacts deliberately. [SQLite backup API](https://www.sqlite.org/backup.html). Implementation and a restore exercise belong to #41.

## Alternatives and study boundaries

| Alternative | Reason to defer or revisit |
| :--- | :--- |
| All results in JSON/CSV | Convenient interchange/debugging, but not the selected authoritative format for typed numerical histories. Keep explicit export adapters. |
| All samples in SQLite | Possible alternative; compare if the workload shows simpler querying or operational benefits over the split catalogue/artifact approach. |
| InfluxDB or TimescaleDB service | Evaluate for live telemetry/history workloads in #32/#43. The first local sandbox needs immutable run artifacts and a local catalogue; this decision does not select a winner for the later twin. |
| Broker and distributed worker system | Revisit for multiple users/machines or measured scheduling needs. The local one-worker policy does not require Redis/Celery or a network broker. |

Verify queue limits, child failure, cancellation, interrupted-run reconciliation, bounded result reads, artifact integrity, and backup/restore in the relevant implementation issues. Measure memory and disk use on the [reported 16 GB Pacien and Divin reference profiles](../../../benchmarks/README.md#machine-register) before expanding concurrency.
