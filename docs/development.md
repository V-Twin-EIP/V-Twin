# Development foundation

V-Twin's foundation contains an installable numerical package, a read-only local API, and a Vue startup screen. The numerical check uses analytical ODEs; no Hydra physics, calibrated wear model, job runner, result store, dashboards, or 3D viewer is implemented yet. Those capabilities keep their own roadmap issues.

## Supported toolchain

| Tool | Version and source of truth |
| :--- | :--- |
| CPython | **3.13.16**, selected by `.python-version`; package supports the 3.13 series. |
| uv | **0.13.1**, enforced in `pyproject.toml`. |
| Node.js | **24.18.1**, selected by `.node-version` and `.nvmrc`. |
| npm | **11.16.0**, recorded in `web/package.json` and pinned in CI. |
| Python dependencies | Exact distributions/hashes in `uv.lock`, including platform-specific wheels. |
| Frontend dependencies | Exact resolution/integrity in `web/package-lock.json`; use `npm ci`. |

Install uv using its [platform instructions](https://docs.astral.sh/uv/getting-started/installation/) and use the versions above. uv can obtain the Python runtime specified by the project. Install the pinned Node/npm toolchain before frontend commands. [uv project locking](https://docs.astral.sh/uv/guides/projects/).

Windows, macOS, and Linux are CI targets. CI records the Python/platform/CPU architecture in its quality report; it does not establish compatibility with every OS/browser/CPU version or the resource limits of the reported 8 GB machine. That hardware evaluation belongs to #39. The foundation has no GPU dependency and loads no 3D library.

## Install and run

Run the same commands from the repository root in PowerShell, zsh, or bash:

```sh
uv sync --locked --extra api
npm --prefix web ci
npm --prefix web run build
uv run --locked --extra api vtwin serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The startup screen checks the API connection and reports that simulation models are not available. Stop the local process with Ctrl+C. The default launch expects `web/dist/index.html`; a missing build produces an actionable CLI error.

For frontend development, start the API in one terminal:

```sh
uv run --locked --extra api vtwin serve --no-web
```

In another terminal, start Vite:

```sh
npm --prefix web run dev
```

Use the URL printed by Vite. Its `/api` and `/health` proxy targets the API on port 8000, keeping browser requests relative to their origin. Restart the Python process after backend changes; frontend edits use Vite's development reload.

### Configuration

`vtwin serve --help` documents the supported flags. `VTWIN_HOST` and `VTWIN_PORT` have CLI equivalents `--host` and `--port`; command-line values take precedence. The host is restricted to `127.0.0.1` or `localhost`, including when it comes from the environment. Ports must be between 1 and 65535. The normal examples use IPv4 loopback.

The optional `.env.example` contains these two settings without secrets. Copy it to `.env` if needed, then load it explicitly:

```sh
uv run --env-file .env --locked --extra api vtwin serve
```

An `.env` file is not loaded implicitly. If the API port changes during frontend development, update the local Vite proxy target accordingly. Runtime data-directory, queue, storage, acquisition, and session-token settings will be added when their modules exist; they are not inert example settings today.

### Current API surface

| Route | Meaning |
| :--- | :--- |
| `GET /health` | Process liveness and package version. |
| `GET /api/v1/capabilities` | Foundation stage, version, empty model list, simulation/3D availability both false. |
| `GET /api/v1/openapi.json` | Machine-readable API schema. |
| `/` and built frontend assets | Served when a UI build is selected. |

This scaffold exposes only local, read-only metadata. It validates allowed hosts and enables no wildcard CORS. It has no run-submission or result-reading endpoints. #40 must implement the local session-token/error/logging controls before such endpoints are exposed; full storage recovery/backup remains #41 work. The architecture describes those future controls separately.

## Quality and tests

```sh
uv run --locked --extra api python scripts/check_quality.py
uv run --locked --extra api pytest --cov=vtwin --cov-report=term-missing --cov-report=xml:artifacts/coverage.xml --junitxml=artifacts/pytest.xml
uv run --locked --extra api vtwin check-numerics
npm --prefix web run check
uv build --no-sources
uv run --locked --extra api python scripts/smoke_http.py
```

The Python quality command runs Ruff lint/format checks, strict mypy for `src`, and two Import Linter contracts. The core cannot import HTTP/entrypoint adapters; application services cannot import numerical implementations. The composition root selects the implementation.

The numerical tests compare decay and a coupled oscillator against analytical solutions, check output sampling and binary64 values, and reject invalid policies, states, grids, derivatives, and a singular problem. These verify the integration module's software/numerical contract. Their tolerances are explicitly for those analytical references and are not physical-model or wear-validation tolerances.

HTTP tests use [HTTPX's ASGI transport](https://fastapi.tiangolo.com/advanced/async-tests/). CLI tests exercise invalid input and environment configuration through real subprocesses. The smoke command launches the built UI/API together on an available local port, checks their routes, then stops the process. Vue tests cover connection, failure/retry, and incompatible responses.

Reports are generated under the ignored `artifacts/` directory: `python-quality.json`, `pytest.xml`, `coverage.xml`, and CI's `eslint.json`/`vitest.xml`. Python distributions are in `dist/`; the frontend build is in `web/dist/`. Generated reports are CI artifacts rather than committed snapshots.

To apply formatting deliberately:

```sh
uv run --locked --extra api ruff check . --fix
uv run --locked --extra api ruff format .
npm --prefix web run format
```

### CI

[Foundation CI](https://github.com/V-Twin-EIP/V-Twin/actions/workflows/ci.yml) runs on pushes, pull requests, and manual dispatch. Each Windows/macOS/Linux job installs locked dependencies, checks Python quality/import boundaries, runs numerical/CLI/HTTP tests, builds distributions, checks/tests/builds the frontend, and launches the real local server. Reports and builds are uploaded per platform even when a prior step fails.

A separate core-only job installs a **non-editable wheel** without API or development dependencies, verifies that FastAPI is absent, and runs `vtwin check-numerics`. GitHub Actions are pinned to commit SHAs. Workflow permissions are limited to repository read access; no repository secrets are required.

### Performance inventory

The [performance protocol](performance.md) defines the three sandbox KPIs and the evidence needed before adopting budgets. Collect metadata on each actual target computer with:

```sh
uv run --locked --extra api python scripts/performance_inventory.py --label reference-8gb --output artifacts/performance/reference-8gb.json
```

The command uses the pinned development-only psutil dependency and leaves unavailable/manual context explicit. It collects environment metadata, not a performance baseline. Complete browser, graphics, power/display, background-load, BLAS/thread and storage information before running a benchmark. CI records its own inventory under `artifacts/performance/`; its integration test exercises the command on all three OS targets without introducing a wall-time performance gate.

## Module responsibilities

| Path | Implemented responsibility |
| :--- | :--- |
| `src/vtwin/domain/` | Framework-independent numerical policy, trajectory and error records. |
| `src/vtwin/ports/` | Replaceable integrator protocol. The full run/engine contracts remain #7/#8 work. |
| `src/vtwin/engine/` | SciPy ODE adapter with finite/shape/completeness checks. |
| `src/vtwin/application/` | Analytical foundation check using the integrator port. |
| `src/vtwin/bootstrap/` | Explicit selection of the SciPy implementation. |
| `src/vtwin/adapters/` | CLI and optional FastAPI entrypoints. |
| `web/src/api/` | Versioned capability request and response validation. |
| `web/src/App.vue` | Minimal connection/empty-state screen, without 3D. |
| `tests/`, `web/src/*.test.ts` | Numerical, adapter and frontend checks. |
| `scripts/`, `.github/workflows/` | Quality reports, real-server smoke check, cross-platform CI. |

The [V1 architecture](architecture/README.md) retains the target module layout. Storage, acquisition, physical/wear models, persistent workers, and full visualization are subsequent implementation work. Review a related ADR when changing an architectural boundary.
