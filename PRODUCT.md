# Product

<!-- impeccable:product-schema 1 -->

## Platform

Web, running locally in the user's browser.

## Stack

Python, NumPy and SciPy provide the numerical foundation. Vue 3, TypeScript and
Vite provide the client. A local FastAPI adapter keeps the interface independent
of the numerical implementation. See [the architecture](docs/architecture/README.md).

## Users and purpose

The first sandbox helps engineers compare engine designs and investigate
reliability before manufacture. A later virtual twin will help owners follow
engine wear from a new vehicle. The project has five members. See
[the product scope](docs/product-scope.md).

## Current capabilities and constraints

The foundation checks the local connection and an analytical numerical reference.
There is no engine wear model, job execution workflow, dashboard or 3D viewer yet.
The target is Windows, macOS and Linux with a developer installation. The reported
team machines have 16 or 32 GB RAM; Pacien supplies the integrated-graphics profile
and Divin a separate CPU/dedicated-GPU profile. See the
[hardware inventory](benchmarks/README.md#machine-register). The planned workflow is batch
simulation followed by result exploration, with optional 3D and a dashboard-only
mode. Audio is outside the first demonstration. See
[the development guide](docs/development.md).

## Evidence on hand

The repository contains source code, dependency locks, automated tests, CI and
research notes. The team has no acquired real-engine measurements or validated
wear model yet. Analytical checks establish numerical plumbing, not physical
accuracy or engine reliability predictions.
