# Headless runner and deterministic replay

**Tracking:** [M1.4 #8](https://github.com/V-Twin-EIP/V-Twin/issues/8). **Contract revision:** case `vtwin.kinematic-case` 1.0.0, manifest 1.0.0, run status 1.0.0.

The runner validates a case, freezes it, executes the engine in checkpointed chunks, then publishes immutable artifacts. The CLI (`vtwin run`) and the HTTP API ([#40](https://github.com/V-Twin-EIP/V-Twin/issues/40)) call the same `RunService` use cases. The first engine is the closed-form single-cylinder slider-crank kinematics used for the November 13 demo. Forces, torque, friction and wear are outside it.

## Commands

```sh
uv run --locked vtwin run examples/cases/kinematics-ref-2000rpm.json --data-dir artifacts/runs-demo
uv run --locked vtwin run examples/cases/kinematics-var-4000rpm.json --data-dir artifacts/runs-demo
uv run --locked vtwin replay <run_id> --data-dir artifacts/runs-demo
uv run --locked vtwin show <run_id> --data-dir artifacts/runs-demo
uv run --locked vtwin export <run_id> --data-dir artifacts/runs-demo --output artifacts/<run_id>.json
uv run --locked vtwin resume <run_id> --data-dir artifacts/runs-demo
```

Without `--data-dir`, the workspace is `VTWIN_DATA_DIR`, otherwise a per-user directory: `~/Library/Application Support/vtwin` on macOS, `%LOCALAPPDATA%\vtwin` on Windows, `$XDG_DATA_HOME/vtwin` or `~/.local/share/vtwin` on Linux. Each command prints one JSON document on stdout.

| Exit code | Meaning |
| :--- | :--- |
| 0 | Success; replay within tolerance. |
| 1 | Run failed (numerical or internal error), or replay outside tolerance. |
| 2 | Invalid input or usage, unsupported schema/model, limit exceeded. |
| 3 | Lifecycle conflict: workspace busy, unknown run, wrong state. |
| 4 | Storage or integrity failure. |
| 130 | Interrupted; committed checkpoints are kept for `vtwin resume`. |

`vtwin export` writes the manifest and full series to one JSON file. Use it to import a CLI result into the dashboard (#51) when the protected HTTP path is not available.

## Input contract: `vtwin.kinematic-case` 1.0.0

Two example inputs are provided: [reference at 2000 rpm](../examples/cases/kinematics-ref-2000rpm.json) and [variant at 4000 rpm](../examples/cases/kinematics-var-4000rpm.json). They differ only in `case_id`, `title` and `operating_point.crank_speed.value`. Bore and stroke come from the scenario catalogue. Rod length and speeds are marked **hypothèse de démo**; the definitive values of the two cases belong to #3.

| Field | Type and unit | Bounds (software limits, not a physical domain) |
| :--- | :--- | :--- |
| `schema`, `schema_version` | `"vtwin.kinematic-case"`, `"1.0.0"` | Other versions are rejected as `unsupported_model`. |
| `case_id` | `[A-Za-z0-9][A-Za-z0-9._-]{0,63}` | Stable identifier chosen by the case author. |
| `model` | `"slider-crank-kinematics"` | Only model of this build. |
| `synthetic` | boolean | Required: declares synthetic or demo inputs. |
| `geometry.bore`, `geometry.stroke`, `geometry.connecting_rod_length` | `{value, unit: "m"\|"mm", source}` | 1 mm to 2 m; rod longer than stroke/2. |
| `operating_point.crank_speed` | `{value, unit: "rpm"\|"rad/s", source}` | 1 to 20 000 rpm. |
| `sampling.revolutions`, `sampling.samples_per_revolution` | integers | 1–1000 revolutions, 4–7200 samples/rev, at most 1 000 000 output samples. |
| `title`, `notes` | optional strings | At most 200 and 2000 characters. |

Each `source` is required: give a reference or write « hypothèse de démo ». Unknown fields, duplicate JSON keys, `NaN`/`Infinity`, booleans in numeric fields and documents over 64 KiB are rejected. All field errors are returned together with their dotted paths, for example `geometry.stroke.unit`.

## Model and conventions

Crank angle θ is measured from top dead centre in the direction of rotation and is unwrapped. At constant speed, θ = ω·t and t = 0 at TDC. With crank radius r = stroke/2 and rod length l:

- displacement from TDC, positive towards the crank: x = r(1 − cos θ) + l − √(l² − r² sin² θ);
- velocity: v = ω·r·sin θ·(1 + r cos θ / √(l² − r² sin² θ)).

Assumptions: centred slider-crank with no pin offset, rigid links, no clearance, constant crank speed. Sample `i` uses θᵢ = i·2π/N and tᵢ = i·Δt, with N samples per revolution. The grid includes both endpoints, so a case has `revolutions × N + 1` samples. Each value depends only on the case and `i`, which makes chunked, interrupted and resumed executions identical.

[`tests/test_kinematics.py`](../tests/test_kinematics.py) checks the outputs against independent references: dead centres and stroke, the period 60/rpm, the geometric rod/crank construction, a finite-difference derivative and the long-rod harmonic limit. It also checks the expected effect of the variant: same stroke and displacement-versus-angle, half the period and twice the velocity. These checks are analytical kinematic verifications, not the validation protocol of #4.

## Output contract

A published run directory contains:

| File | Content |
| :--- | :--- |
| `case.json` | Frozen case, canonical JSON (sorted keys). Its SHA-256 is recorded in the manifest. |
| `manifest.json` | Run ID, case ID/hash/provenance, SI-resolved inputs, model ID and version, numerical policy (method, binary64, time step, sample count, chunk size, seed `null` with its reason), observable definitions and units, replay tolerance, software versions and source commit. |
| `series.npz` | Authoritative binary64 arrays `time_s`, `crank_angle_rad`, `piston_displacement_m`, `piston_velocity_m_s`. NumPy format without pickles. |
| `inventory.json` | SHA-256 and size of the three artifacts above, verified before publication and before every read. |
| `status.json` | Lifecycle state, attempts, progress, error and KPIs. |
| `events.jsonl` | Lifecycle events correlated by `run_id`. |

The run KPIs feed #39/#46: `simulated_duration_s`, `engine_wall_s` (engine calls only), `simulation_rate_s_per_s`, `compute_wall_s` (engine, checkpoint and assembly I/O), `output_samples`, `compute_segments` and the computing process's peak RSS where `getrusage` exists. On Windows, peak RSS is `null` with a reason. Dashboard series reads are bounded by the API in #40. Parquet storage (ADR 0003) is deferred: NumPy archives avoid a new dependency for this first model, and the format is internal to the storage adapter.

## Lifecycle, checkpoints and resume

`queued → running → completed`, or `failed`/`interrupted`. The engine runs one revolution per chunk. Each chunk is written atomically to the staging area and counts only once `checkpoint.json` references it: the atomic checkpoint replacement is the commit point. A chunk written but not committed is recomputed and overwritten on resume, never appended twice. Before publication, the runner verifies the chunk checksums and that they cover the grid contiguously and exactly once.

`vtwin resume` continues interrupted runs and failed runs with a retryable error (storage or worker failure) from the last committed sample. A numerical failure is deterministic and not resumable. Each start reconciles the workspace: runs left `queued`/`running` by a dead process become `interrupted`, and a staged run already marked `completed` is published again. The tests check that an interrupted, then resumed run gives exactly the same arrays as an uninterrupted run.

A workspace has one owner at a time, enforced by an OS file lock released automatically on process exit. A second CLI run or a CLI run against a workspace served by `vtwin serve` fails with `workspace_busy`.

## Replay and tolerance

`vtwin replay` re-reads the frozen case, checks its hash and the model version, re-executes it and compares every observable with the stored series. It reports `identical` (bit-for-bit) and `within_tolerance`: |Δ| ≤ 10⁻¹² × max|stored values| for each observable. The same build on the same platform is expected to be bit-identical; the tolerance absorbs last-bit differences of `sin`/`cos`/`sqrt` between platforms. This is a numerical reproducibility tolerance, not a physical accuracy tolerance: those come from #4. A replay against another model version is refused as `unsupported_model`.

## Limits of this delivery

- The model is kinematics only, at constant speed; values not sourced in #3 are demo assumptions.
- Checkpoint state is the sample index, which is complete for an algebraic model. Stateful ODE models will add their state vector to the checkpoint.
- The storage is a filesystem catalogue; the SQLite catalogue and Parquet histories of ADR 0003 remain later work.
