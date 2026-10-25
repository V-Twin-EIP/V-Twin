# Expert collaboration (C1 · `track:experts`)

> Status: work in progress, last updated 2026-10-24. Tracked in [#36](https://github.com/V-Twin-EIP/V-Twin/issues/36).

## 1. Priorities (by project risk)

| Rank | Domain | Why it is risky for V-Twin |
| :--- | :--- | :--- |
| 1 | Thermodynamics / tribology / wear | Core value of the project. A wear model that cannot be validated independently has no value; the first degradation mechanism must be both observable and measurable. |
| 2 | Vehicle data / signals acquisition | The signals exposed by the reference engine (precision, sampling) are not yet known. They condition calibration, validation and the later twin profile. |
| 3 | Architecture / performance | V1 architecture, ADRs and KPI protocol already exist; remaining risk is lower and better framed. |


## 2. Questions matrix

| Domain | Precise question | Decision it informs | Linked issue |
| :--- | :--- | :--- | :--- |
| Thermodynamics / tribology / wear | Which wear mechanism of the reference engine can we model first, given the signals we can actually measure, and how can we validate the model independently from the data used to calibrate it? | Choice of the initial degradation model and validation protocol | [#4](https://github.com/V-Twin-EIP/V-Twin/issues/4), [#33](https://github.com/V-Twin-EIP/V-Twin/issues/33) |
| Vehicle data / signals acquisition | To calibrate and validate a ring/liner friction and wear model, which signals must be measured on an engine, with what accuracy and sampling rate, and which can realistically be obtained through OBD-II/CAN versus requiring added instrumentation? | Signal list and plan for the acquisition POC and for the later twin profile | [#2](https://github.com/V-Twin-EIP/V-Twin/issues/2), [#30](https://github.com/V-Twin-EIP/V-Twin/issues/30), [#34](https://github.com/V-Twin-EIP/V-Twin/issues/34) |
| Architecture / performance | For a browser-submitted simulation that must return usable results in under 60 seconds on an 8 GB machine, is a Python/NumPy/SciPy solver behind a local API sufficient for the planned scenarios, and when should the compute core move to a compiled implementation? | Boundary between Python and a compiled core, and the first optimization target | [#5](https://github.com/V-Twin-EIP/V-Twin/issues/5), [#39](https://github.com/V-Twin-EIP/V-Twin/issues/39), [#47](https://github.com/V-Twin-EIP/V-Twin/issues/47) |

## 3. Candidate profiles

| Name | Public link | Specialty | Why this person | Domain |
| :--- | :--- | :--- | :--- | :--- |
| K. Tomlinson et al. | [Journal of Tribology, 2024](https://eprints.whiterose.ac.uk/id/eprint/204972) | Lubricant additives, ring-liner friction | Compares four lubricants at the oil control ring / liner contact, close to our two-oil comparison | Tribology / wear |
| R.S. Dwyer-Joyce et al. | [Oil film formation and friction in a piston ring-liner contact, 2013](https://eprints.whiterose.ac.uk/id/eprint/94619/) | Lubrication, test rigs and numerical models | Test rig plus numerical model of film thickness and friction across lubrication regimes | Tribology / modelling |
| B. Zabala, A. Igartua et al. | [Tribology International, 2017](https://doi.org/10.1016/j.triboint.2016.10.005) | Ring-liner friction and wear modelling | Wear and friction model validated against laboratory experiments | Tribology / model validation |
| T. Wopelka et al. | [Industrial Lubrication and Tribology, 2018](https://real.mtak.hu/122515) | Cylinder liner wear measurement | Continuous liner wear measurement, separating running-in from steady-state wear | Tribology / measurement |

## 4. Prepared requests


## 5. Planned reviews

| Review | Topic | Owner | Target date | Expected shareable proof |
| :--- | :--- | :--- | :--- | :--- |