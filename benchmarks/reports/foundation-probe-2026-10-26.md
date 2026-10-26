# Analytical-core probe - October 26, 2026

**Scope:** existing mathematical decay check only. **Not a product baseline.**

| Observation | Result |
| :--- | :--- |
| Correct measured attempts | 30 / 30, after 3 warm-ups |
| Median elapsed time | 2.107 ms |
| Nearest-rank p95 elapsed time | 2.235 ms |
| Maximum observed elapsed time | 2.291 ms |
| Maximum post-attempt process RSS observation | 72.16 MiB; not an application peak |
| Environment | Darwin 27.0.0, arm64, Python 3.13.16 |
| Source revision | `c842e3099d1c270c308761e9f9fd4eef0ce9f6b4` |

The problem is `y'=-y`, `y(0)=1`, on [0, 5] seconds with 51 saved samples and RK45. Each attempt is checked against `exp(-t)` with the existing analytical acceptance tolerance. Imports and warm-ups are outside the recorded wall times.

[Raw attempts, versions, source hashes and limitations](foundation-probe-2026-10-26.json).

```sh
uv run --locked --extra api python scripts/measure_foundation.py --output artifacts/performance/foundation-probe.json
```

No physical engine model, SCN-001 execution, browser, scheduler, publication or graph rendering is measured. End-to-end product latency, simulation throughput and application memory peaks remain unmeasured. These observations do not justify the 60-second/one-second targets or a product RSS budget. The representative campaign remains #8/#40/#46 work after the required inputs and validation references are frozen.
