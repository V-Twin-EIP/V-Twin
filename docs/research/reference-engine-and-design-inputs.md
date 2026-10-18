# Reference engine and design input recommendation

**Context:** [M0.1 product scope](../product-scope.md). The owner prioritizes the design sandbox, has no physical engine available, and selected wear associated with friction or lubrication as the first reliability topic. The owner delegated the reference-engine search and requested a recommendation on parameter-based input versus complete CAD import.

**Review date:** 2026-10-18.

## Working selection

Use a **single-cylinder gasoline Ricardo Hydra** as the engine context. Freeze the initial engine specification to the **86 mm bore, 86 mm stroke, 10.5:1 compression-ratio variant** described in Table 1 of Dyson, Priest, and Lee's 2023 study. The paper identifies its configuration and laboratory lubrication arrangements. These values establish a reference specification, not a complete wear-validation dataset. [Engine specification, Table 1](https://d-nb.info/1312319852/34).

Focus the first component-level study on the **top compression ring–cylinder liner contact**, with **liner sliding wear** as the initial degradation quantity to investigate. Ring wear, the entire ring pack, bearings, and other failure mechanisms can be added after the first contact model is established. This component choice is a proposed technical scope, based on the owner's confirmed friction/lubrication direction.

Use **explicit engine/contact parameters**, entered through a form or a versioned file, as the proposed MVP design input. The exact file format is an architecture decision. Complete CAD import is a later capability.

## Candidate comparison

| Candidate | Evidence verified in this review | Fit for the first wear-focused sandbox |
| :--- | :--- | :--- |
| **Ricardo Hydra, gasoline research engine** | A published engine specification, a separate experimental study of ring-pack lubricant-film thickness, and further work on lubricant behavior in the piston assembly. | Selected for its directly relevant tribology literature. A matched contact-parameter and wear-calibration dataset still needs to be assembled. |
| **Honda GX160** | Honda publishes engine specifications and manuals, including the 68 × 45 mm bore/stroke and single-cylinder four-stroke configuration. [Manufacturer specification](https://www.honda-engines.eu/files/files/technical-sheet-gx160.pdf). | A documented production-engine alternative. This review did not establish a matching open ring/liner wear dataset, so manufacturer specifications alone do not make it the preferred wear benchmark. |
| **University of Michigan TCC-III** | The research group's collection describes measured flow/flame data and geometry for 1-D and CFD engine simulations. [University source](https://volker-sick.engin.umich.edu/home/downloads). | Useful evidence that academic engine geometry/data can be published. Its stated flow/combustion scope is less directly aligned with the selected wear question. A validated wear benchmark was not established here. |

The selection follows evidence relevant to the first component, rather than brand familiarity. It does not imply that every study using a Hydra shares the same hardware or test conditions.

## What the literature supports

- The 2023 Hydra publication supplies a named engine configuration and basic specifications. Its reported experiment concerns lubricant droplets; those measurements are not direct observations of liner wear. [Dyson et al., 2023](https://d-nb.info/1312319852/34).
- An experimental Hydra study measures lubricant-film thickness at the piston ring pack under different lubricant conditions. It is relevant to identifying observable quantities and validation approaches. Availability of a complete machine-readable dataset has not been verified in this review. [Ring-pack film study, 2019](https://www.sciencedirect.com/science/article/pii/S0301679X1830330X).
- Separate ring/liner tribometer work reports wear measurements while varying load, temperature, and sliding frequency. This provides a candidate component-level comparison source, rather than whole-engine Hydra validation. The specimen/material/test conditions must remain attached to those results. [TU Wien research record, 2023](https://repositum.tuwien.at/handle/20.500.12708/193542).

The engineering inference is that the component can be studied through an explicit contact/lubrication model and a reproducible parameter set. The exact law, material pair, coefficient calibration, and independently evaluated operating range remain work for [#13](https://github.com/V-Twin-EIP/V-Twin/issues/13), [#33](https://github.com/V-Twin-EIP/V-Twin/issues/33), and [#4](https://github.com/V-Twin-EIP/V-Twin/issues/4).

## Parameter input versus CAD import

| Approach | What it contributes | Work still needed for wear simulation | MVP decision |
| :--- | :--- | :--- | :--- |
| **Parameter form/file** | Explicit dimensions, properties, operating conditions, and model settings that map to the solver. | Source and validate the parameters; implement and evaluate the physical model. | Proposed first implementation. It enables a controlled reference case and one-parameter comparisons. |
| **Complete CAD import** | Detailed shapes, part placement, and potentially assembly relationships, depending on the file. | Resolve format/dependencies, identify relevant parts and contacts, prepare the geometry, supply missing physical properties and conditions, and connect it to an appropriate solver. | Defer until the numerical model and its required inputs are established. |

This is an architectural assessment for V-Twin's selected contact problem. Geometric detail does not by itself specify roughness, lubricant behavior, applied loading, or a validated wear law. A rendered assembly, a kinematic animation, a CFD geometry, and a wear-capable simulation model represent different capabilities.

### CAD availability checked

- **Downloadable assembly example:** an author-maintained inline-four project contains `FullEngineAssemby.SLDASM`, subassemblies, and part files. Its README describes personal/educational use. The repository's file listing was checked; the assembly was not opened or qualified as a working engineering model, and permission to redistribute it in V-Twin has not been established. [Author's CAD project](https://github.com/safwanikbal/Inline-4-Internal-Combustion-Engine-Solidworks).
- **Academic geometry example:** the TCC-III collection is advertised by its research group as including geometry for 1-D/CFD setup alongside measurements. This does not establish that it supplies a manufacturing-complete mechanical assembly or a wear model. [Research-group downloads](https://volker-sick.engin.umich.edu/home/downloads).

These sources establish that engine-related CAD/geometry is available in some forms. This review did not identify a manufacturer-qualified, complete production-engine CAD assembly with all tribological properties, operating data, and a verified reuse license ready for V-Twin. No external CAD asset is copied into this repository by this decision.

A later 2D/3D viewer can generate a simplified representation from V-Twin's parameters. Choosing a 3D view does not require making arbitrary CAD import part of the MVP.

## Initial parameter and evidence inventory

| Group | Planned inputs | Current evidence/state |
| :--- | :--- | :--- |
| Engine context | Bore, stroke, compression ratio, reference-case identifier. | Basic values identified in the selected 2023 Hydra specification. Freeze that source/version in the configuration. |
| Motion and loading | Connecting-rod geometry, speed history, pressure/load history, duration. | A consistent set for the selected case remains to be sourced or explicitly defined as an experimental scenario. |
| Ring/liner contact | Ring face geometry and loading, liner geometry, material properties, hardness, surface finish/roughness. | Requires a matched specification or documented component-level benchmark. Do not fill gaps with values from an unrelated Hydra variant. |
| Lubrication | Viscosity model and its temperature dependence, operating temperatures, supply assumptions and boundary conditions. | Requires sources and a model supported by the chosen benchmark. |
| Wear | Wear quantity, law, coefficients, initial condition, calibration and evaluation observations. | Model selection and quantitative calibration remain open. |

Each supplied value will need a unit, provenance, applicability, and uncertainty or an explicit assumption. A configurable input is not automatically a validated design range.

## Proposed first comparison

1. Load the frozen reference configuration and one documented operating/contact case.
2. Run the selected ring/liner model and record the relevant lubrication, friction, and wear outputs.
3. Change one supported parameter, such as a lubricant property or a ring/contact design property, within the evaluated range.
4. Repeat the same scenario and compare the outputs, their interpretation, and evidence coverage.
5. Preserve the configuration, source references, model version, and results for reproduction.

The target is a physically evaluated component-level wear estimate. If the available evidence supports only friction or lubrication indicators at an intermediate stage, label those outputs accordingly and keep the quantitative-wear validation criterion open. Whole-engine wear, lifetime in kilometres, and a complete catalogue of reliability failures require additional models and evidence.

## Follow-up work

- **M0.1:** record the reference selection, component proposal, input approach, visualization/audio decisions, and first-demonstration boundaries.
- **#3 / #4:** choose a concrete comparison and identify the observations, supported domain, and tolerances that can evaluate it.
- **#13 / #33:** select and justify the contact/wear formulation and its calibration requirements.
- **#36 / #37:** seek an expert view on the component scope and the transfer limits between a tribometer and a complete engine.
- **#5 / #7:** turn the required inputs into explicit contracts after the model requirements are understood.
