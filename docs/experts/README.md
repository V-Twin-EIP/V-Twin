# Expert collaboration (C1 · `track:experts`)

> Status: work in progress, last updated 2026-11-12. Tracked in [#36](https://github.com/V-Twin-EIP/V-Twin/issues/36).

## 1. Prioritization of external expertise needs

The three domains are prioritized according to four criteria:
- Project impact: How significantly could a technical mistake affect the V-Twin project?
- Technical uncertainty: How much is still unknown or not yet demonstrated by the team?
- Project dependency: How much does this topic block current or upcoming development steps?
- Need for external expertise: How important is an external specialist's knowledge to make or validate the technical decision?

Each criterion is scored from 1 to 3 from lowest to highest.

| Rank | Domain | Project impact | 

Technical uncertainty | Project dependency | Project dependency

Need for external expertise | Total |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Thermodynamics / tribology / wear | 3 | 3 | 3 | 3 | 12/12 |
| 2 | Vehicle data / signals acquisition | 3 | 3 | 2 | 3 | 11/12 |
| 3 | Architecture / performance | 2 | 2 | 1 | 2 | 7/12 |

### Thermodynamics / tribology / wear — Highest priority

This domain represents the core physical value of V-Twin. The team needs to identify a realistic degradation mechanism and define how it can be modelled and validated.

The main uncertainty is whether the selected physical assumptions and wear model accurately represent the behaviour of a real engine.

An external specialist is needed to challenge the physical assumptions, identify relevant parameters and recommend an independent validation method.

### Vehicle data / signal acquisition — High priority

The future digital twin will depend on data collected from a real engine. However, the available signals, their accuracy and their sampling rates are not yet fully established.

External expertise is needed to determine which signals can realistically be obtained through OBD-II/CAN and which would require additional sensors.

This topic is essential for the future measurement and acquisition POC, even if some of this work depends on access to a reference engine.

### Architecture / performance — Medium priority

The V1 software architecture and main technical choices have already been defined. This gives the team a starting point for implementation.

However, the architecture still needs to be tested against the expected simulation workloads and performance requirements.

An external review would help identify potential bottlenecks and determine whether the Python-based computation core will remain sufficient or require optimization.

## 2. Questions matrix

| Domain | Precise question | Decision it informs | Linked issue |
| :--- | :--- | :--- | :--- |
| Thermodynamics / tribology / wear | For our planned comparison of two oils in a piston ring–cylinder liner contact, which independent measurement (e.g. oil-film thickness or friction force) would be most suitable to validate our model, and under what operating conditions? | Selection of the reference measurement and validation conditions for the wear model | [#4](https://github.com/V-Twin-EIP/V-Twin/issues/4), [#33](https://github.com/V-Twin-EIP/V-Twin/issues/33) |
| Vehicle data / signals acquisition | Which engine signals can realistically be obtained through OBD-II/CAN, with sufficient accuracy and sampling frequency for our future simulation needs? | Selection of measurable signals and definition of the acquisition POC | [#2](https://github.com/V-Twin-EIP/V-Twin/issues/2), [#30](https://github.com/V-Twin-EIP/V-Twin/issues/30), [#34](https://github.com/V-Twin-EIP/V-Twin/issues/34) |
| Architecture / performance | s our current Python/NumPy/SciPy architecture suitable for the planned simulation scenarios and performance requirements? | Confirmation of the software architecture and identification of potential optimization needs | [#5](https://github.com/V-Twin-EIP/V-Twin/issues/5), [#39](https://github.com/V-Twin-EIP/V-Twin/issues/39), [#47](https://github.com/V-Twin-EIP/V-Twin/issues/47) |

## 3. Candidate profiles

| Name | Public profile | Specialty | Why this person | Domain |
| :--- | :--- | :--- | :--- | :--- |
| Prof. Rob Dwyer-Joyce | University of Sheffield | Tribology | His research directly covers piston ring–liner contacts and oil-film measurement. His expertise could help identify an independent measurement for validating our friction model. | Tribology / wear |

## 4. Prepared requests

| Target expert | Topic | Question to be sent | xpected outcome | Decision concerned | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Prof. Rob Dwyer-Joyce – University of Sheffield | Independent validation of the piston ring–cylinder liner friction model | For a piston ring–cylinder liner friction model, which independent measurement (e.g. oil-film thickness or friction force) would be the most suitable to validate our model, and under which operating conditions should it be performed? | Recommendation on the most relevant measurable parameter and the experimental conditions required for reliable validation | Definition of the model validation protocol and reference data (#4) | Prepared |

## 5. Planned reviews

| Review | Topic | Owner | Target date | Expected shareable proof |
| :--- | :--- | :--- | :--- | :--- |