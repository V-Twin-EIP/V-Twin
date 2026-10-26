# ADR 0001 Local application and replaceable interface

**Status:** working V1 baseline, frontend choice corrected October 26, 2026. We selected Next.js (React) with TypeScript for the UI, batch calculation followed by exploration, Windows/macOS/Linux targets, a developer installation, and a dashboard mode without 3D. Local web is the selected initial deployment baseline.

## Context

V-Twin needs an interactive sandbox without binding the numerical model to a particular interface. The [hardware register corrected on October 24](../../../benchmarks/README.md#machine-register) has 16 GB RAM as the lowest reported capacity, with Pacien's integrated-graphics profile and Divin's separate dedicated-GPU profile. A simulation can finish before the engineer explores and compares results, so numerical advancement need not track browser animation.

## Decision

Use a local web application: **Next.js (React), TypeScript and the App Router** for the selected frontend; **FastAPI** remains the loopback HTTP adapter to the application services. Plan a Next.js **static export** so the built UI can be served locally alongside `/api/v1` without adding a required Next.js server process. Browser data access, charts and the optional viewer belong in client-side components; numerical execution remains in Python. [Next.js documentation](https://nextjs.org/docs), [static export](https://nextjs.org/docs/app/guides/static-exports), [FastAPI standards](https://fastapi.tiangolo.com/features/).

**Implementation status:** the current startup screen, tooling and tests still use Vue/Vite. Porting them to Next.js, pinning compatible Next.js/React versions, configuring local development/API access and exported-asset routing, and updating CI/smoke checks remain to be done. The current `web/dist` launch instructions describe the existing scaffold, not a completed Next.js migration. Revisit the deployment topology explicitly if server-only Next.js features become necessary.

The application/domain layers contain no FastAPI routes, React/Next.js components, browser objects, or chart/3D library types. An HTTP adapter maps versioned request/response DTOs to application calls. A CLI can invoke the same use cases. The frontend accesses these contracts through a small API client; replacing the frontend requires a new presentation adapter while preserving the API semantics.

Use **Three.js** behind a viewer adapter for 3D and **Apache ECharts** behind a chart adapter for dashboard plots. Keep a shared run identifier, selected state/time, observable metadata, and comparison selection outside the renderers. Choose the ECharts Canvas or SVG renderer for the dashboard path. Three.js's WebGL renderer requires WebGL 2; ECharts documents Canvas/SVG imports. [Three.js renderer](https://threejs.org/docs/pages/WebGLRenderer), [ECharts imports](https://echarts.apache.org/handbook/en/basics/import/).

The **dashboard-only mode is a first-class path**. Lazy-load 3D assets/code only when requested; do not create a WebGL context in dashboard-only mode. A missing graphics capability or viewer initialization failure leaves configuration, run submission, graphs, comparison, and export usable. The 3D capability remains part of the MVP and is evaluated separately on supported hardware.

Use ordinary HTTP requests for configuration, run submission, status polling, and bounded result queries. The batch workflow does not require a persistent browser stream. Vehicle telemetry transport remains a separate adapter decision in [#31](https://github.com/V-Twin-EIP/V-Twin/issues/31); this local control API does not decide the MQTT/WebSocket/REST/SSE study for live telemetry.

## Alternatives

| Alternative | Assessment for the initial delivery |
| :--- | :--- |
| Desktop wrapper around the web UI | Can reuse presentation work, but adds runtime packaging, process supervision, ports, updates, and platform-specific testing. Revisit when a nontechnical installation is required. |
| Hosted application | Supports remote access, but introduces server operation, authentication, shared-resource scheduling, and deployment decisions beyond the initial single-user local workflow. |
| Vue/Vite interface | Existing startup scaffold; superseded as the frontend choice. Retain it until the Next.js migration is implemented and checked. |
| Direct UI calls into Python/C++ objects | Couples presentation to the runtime and packaging mechanism. The HTTP boundary keeps a browser UI and future alternative clients independent. |

## Verification and revision

- In #6/#41, verify installation, launch, shutdown, browser access, and persisted runs on Windows, macOS, and Linux. Record CPU architecture, supported runtime versions, and dependency lockfiles.
- In #24, verify the complete dashboard workflow with 3D disabled and with WebGL unavailable; verify the 3D/graphs selection linkage separately.
- In #39, measure the 16 GB Pacien and Divin profiles with API, worker, browser, and the operating system sharing memory. The hardware capacity is a test environment, not an invented application memory budget.
- Revisit streaming after measurements identify a requirement for live progress or continuous interaction. Revisit desktop packaging when installation expectations change.
