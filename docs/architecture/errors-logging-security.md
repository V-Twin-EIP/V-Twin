# Errors, logs, security and backup

**Tracking:** [AR.1 #40](https://github.com/V-Twin-EIP/V-Twin/issues/40). **Status:** implemented for the first perimeter on November 12, 2026: kinematic runs through the CLI and the local HTTP API. This page applies the [architecture's trust boundaries](README.md#errors-and-trust-boundaries) and [ADR 0003](adr/0003-local-execution-and-storage.md). The runner itself is described in the [runner guide](../runner.md).

## Error policy

Expected failures are classes of `vtwin.domain.errors`. Each has a stable `code`, a safe message, optional field-level `details` and a `retryable` flag. Adapters map them; the domain never imports an adapter. HTTP errors share one body: `{"error": {code, message, retryable, details[, run_id]}, "request_id": ...}`.

| Code | Raised when | HTTP | CLI exit | Recovery and safe stop |
| :--- | :--- | :--- | :--- | :--- |
| `invalid_input` | Schema, unit, bound, type, unknown field, malformed or non-finite JSON. | 422 | 2 | Fix the listed paths. No run is created. |
| `limit_exceeded` | Output samples above 1 000 000, or other declared limits. | 422 | 2 | Reduce sampling. No run is created. |
| `payload_too_large` | Request body above 64 KiB (declared or streamed). | 413 | — | Rejected before parsing. |
| `unsupported_model` | Unknown schema version or model; replay against another model version. | 422 | 2 | Use a supported version. |
| `unauthorized` | Missing or wrong `X-VTwin-Session` token on a run route. | 401 | — | Use the launch URL's token. |
| `forbidden_origin` | Browser `Origin` not in the allow-list. | 403 | — | Use the served UI or start with `--allow-origin`. |
| `run_not_found` | Unknown or malformed run ID (pattern-checked before any path is built). | 404 | 3 | — |
| `run_state_conflict` | Series of a non-completed run, resume of a completed or non-retryable run. | 409 | 3 | Wait for completion or start a new run. |
| `workspace_busy` | One run already executing, or another process owns the workspace. | 409 + `Retry-After: 1` | 3 | Retry later; no hidden queue. |
| `numerical_failure` | Non-finite or misshaped engine output. | in run status | 1 | Terminal, not resumable: the model is deterministic. |
| `storage_failure` | Disk/OS error while writing. | 503 / run status | 4 | Retryable: `resume` continues from the last checkpoint. |
| `integrity_failure` | Missing file, checksum mismatch, chunk gap/overlap, case hash mismatch. | 500 | 4 | The run is not published or read. Restore from backup. |
| `worker_failure` | Worker exited abnormally (crash, kill). | in run status | — | Retryable: `POST …/resume`. |
| `run_timeout` | Worker exceeded `--run-timeout-s` (default 120 s); it is terminated, then killed. | in run status | — | Retryable from the last checkpoint. |
| `run_interrupted` | Ctrl+C / SIGINT during computation, or a run left active by a dead process. | in run status | 130 | `vtwin resume` or `POST …/resume`. |
| `internal_error` | Unexpected exception. | 500 | 1 | Logged with traceback; the client gets no internal detail. |

Propagation: the engine raises only domain errors; the run service records the terminal state, the error and the committed sample count before re-raising. The coordinator turns abnormal worker exits and timeouts into `worker_failure`/`run_timeout`. A failed or incomplete run is never published, so its series cannot be read or compared. Publication is the last step, after checksum and length verification.

Safe stop: a checkpoint is committed by an atomic file replacement after each revolution, so an interruption at any instant leaves either the previous or the new checkpoint. At startup, the workspace owner (CLI or server) reconciles runs left `queued`/`running` as `interrupted`, and republishes a run whose publication was cut short.

## Input validation

The [case contract](../runner.md#input-contract-vtwinkinematic-case-100) checks schema and version, required provenance per value, units (converted to SI at the boundary), finite numbers, bounds, the rod/crank closure condition and output volume. JSON is decoded strictly: no `NaN`/`Infinity`, duplicate keys or non-object documents. All field errors are returned together. Series reads are paginated (at most 20 000 samples per response, `next_start` cursor) and the observable list is checked against the manifest. Run IDs match `run-YYYYMMDDTHHMMSSZ-<8 hex>` before any filesystem access; the API never accepts a host path.

## Logs

Logs are JSON lines on stderr (`--log-format text` for humans), configured by `--log-level`/`VTWIN_LOG_LEVEL`. Every record carries `ts_utc`, `level`, `logger`, `message`, `pid` and `session_id`, a random identifier per server launch shared with its workers. Request records add `request_id` (also returned as `X-Request-ID`), method, path, status and duration. Run records add `run_id`, the lifecycle `event` and error codes. Each run also keeps its own `events.jsonl` next to its artifacts.

Never logged: request bodies, case contents, headers, query strings, the session token. Keys such as `token`, `authorization` or `cookie` are replaced by `[REDACTED]`, and the session token value is masked in every rendered line as a second barrier. The token is printed once to the terminal, in the launch URL, and never written to the workspace. Tests check these properties on the captured log output.

Example record:

```json
{"ts_utc": "2026-11-12T12:24:01.890132Z", "level": "INFO", "logger": "vtwin.execution", "message": "worker_finished", "session_id": "eae9b2b4e9dc", "pid": 45921, "run_id": "run-20261112T122401Z-5e0a2dfe", "event": "worker_finished", "exit_code": 0, "state": "completed"}
```

## Access boundaries and secrets

| Boundary | Control |
| :--- | :--- |
| Network exposure | `vtwin serve` binds only `127.0.0.1` or `localhost`, including from the environment. No remote deployment is supported in V1. |
| DNS rebinding | `Host` must be `127.0.0.1` or `localhost` (400 otherwise). |
| Cross-site requests | On `/api/v1/runs*`, a browser `Origin` must be the server's own loopback origin or an explicit `--allow-origin http://localhost:<port>` dev origin. CORS is enabled only for those dev origins, never with a wildcard. |
| Local callers | A per-launch token (`secrets.token_urlsafe(32)`) is required in `X-VTwin-Session` on every run route and compared in constant time. Automation can supply `VTWIN_SESSION_TOKEN` (32+ characters) through the environment; never store it in `.env` or Git. |
| Public routes | `/health`, `/api/v1/capabilities` and `/api/v1/openapi.json` expose metadata only. |
| Resources | One worker at a time, a wall-clock timeout per run, bounded bodies, output volume and result pages. |
| Files | Workspace directories are created with owner-only permissions (`0700`) in a per-user location outside Git. The data directory is never served as static files. Backup archives contain only run artifacts. |
| Response headers | `Cache-Control: no-store` on run routes, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, no `Server` header. |

Frontend integration (#50/#51): the served UI receives the token in the URL fragment `#session=…`, which browsers do not send to the server. The dashboard reads it from `location.hash`, keeps it in `sessionStorage`, removes it from the address bar with `history.replaceState`, and sends it as `X-VTwin-Session` (`web/src/lib/api.ts`). With the Next.js dev server on another port, start the API with `--allow-origin http://127.0.0.1:3000`.

Acquisition data does not exist yet. When #30/#35 add it, recorded sessions go to the same owner-only workspace, credentials stay in the environment or OS keychain and are registered with the log masking, and acquired private datasets stay out of Git as `CONTRIBUTING.md` requires.

## Backup and restore

Scope: published runs, meaning their frozen case, manifest, series, inventory, status and events. Unfinished staged runs are listed in the backup manifest but not archived; resume them first.

```sh
uv run --locked vtwin backup create ~/vtwin-backup-2026-11-12.tar.gz
uv run --locked vtwin backup restore ~/vtwin-backup-2026-11-12.tar.gz --data-dir <new or existing workspace>
uv run --locked vtwin replay <run_id> --data-dir <new or existing workspace>
```

1. Stop `vtwin serve` or wait for CLI runs: both commands require exclusive ownership of the workspace and fail with `workspace_busy` otherwise. No run can be published during the backup.
2. `create` verifies every run's inventory before archiving, and writes `backup-manifest.json` with the SHA-256 of every file. The archive is written next to its target, then renamed. It is refused inside the workspace.
3. `restore` reads only expected members (`runs/<valid run id>/<known file>`), never extracts paths, and checks every file against the backup manifest and the run's own inventory before moving anything. An identical existing run is skipped; a different run with the same ID is reported as a conflict (exit 3) and left untouched.
4. Check a restored run with `vtwin replay`: it re-executes the frozen case and compares with the restored series.

The tests exercise a backup, a restore into an empty workspace, a replay of the restored run, an idempotent second restore, and the refusal of corrupted or path-traversal archives without any partial restore.

## Evidence

| Criterion of #40 | Evidence |
| :--- | :--- |
| Expected errors, propagation, recovery, safe stop; inputs, bounds, units, schemas | Table above; [`tests/test_cases.py`](../../tests/test_cases.py), [`tests/test_runner.py`](../../tests/test_runner.py) |
| Run/session-correlated logs without secrets | [`tests/test_http_runs.py`](../../tests/test_http_runs.py) `test_logs_are_correlated_and_never_contain_the_token` |
| Critical module: invalid configuration, unavailable dependency, interruption and resume | Invalid cases and CLI flags ([`tests/test_cli.py`](../../tests/test_cli.py)); disk failure during commit, workspace owned by another process, worker crash and hung worker; interruption then identical resume (runner and HTTP tests) |
| Access boundaries, secrets, authentication, data protection | Token, origin, host, body size and run-ID tests in [`tests/test_http_runs.py`](../../tests/test_http_runs.py) and [`tests/test_http.py`](../../tests/test_http.py) |
| Backup/restore with documented procedure | [`tests/test_backup.py`](../../tests/test_backup.py) and the procedure above |
| Real server path | [`scripts/smoke_http.py`](../../scripts/smoke_http.py), run in CI on Windows, macOS and Linux |

Remaining risks to deepen: no cancellation endpoint yet (timeout and Ctrl+C only); the filesystem catalogue replaces SQLite until ADR 0003's catalogue lands; the token protects against other local web pages and casual local clients, not against malware running as the same user; Windows peak RSS is not reported without psutil.
