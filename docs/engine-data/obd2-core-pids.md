# OBD-II engine inputs

This file lists the OBD-II parameters considered for future vehicle-data acquisition in V-Twin. A PID identifies a parameter requested from the vehicle's ECU. Support varies by vehicle and must be checked before acquisition.

These signals describe operating conditions. They do not directly measure ring/liner wear or establish the inputs needed by the sandbox's contact model. The current foundation has no vehicle-acquisition adapter or physical engine model.

## Candidate signals

| Parameter | PID | Unit | Intended use |
|---|---|---|---|
| Engine speed | `0C` | RPM | Speed history and operating-point identification |
| Engine load | `04` | % | Load context alongside speed and other operating signals |
| Coolant temperature | `05` | °C | Cooling and thermal context |
| Oil temperature | `5C` | °C | Lubricant-temperature context, where supported |
| Intake air temperature | `0F` | °C | Intake and combustion context |
| Manifold absolute pressure (MAP) | `0B` | Pressure; acquisition unit to be recorded | Intake-pressure and load context |
| Throttle position | `11` | % | Demand context and operating transitions |
| Timing advance | `0E` | Crankshaft degrees | Ignition timing and combustion context |
| Mass air flow (MAF) | `10` | g/s | Intake mass-flow and load context |
| Vehicle speed | `0D` | km/h | Driving-profile context |

## Interpretation

### Engine speed — `0C`

Engine speed is the crankshaft's rotational speed. The same RPM can occur at different loads, so speed alone is insufficient to estimate mechanical stress or wear.

Over-rev detection requires a limit for the specific engine. Idle speed, the evaluated operating range, and redline remain unresolved for the selected Hydra case; generic vehicle examples cannot supply those limits.

### Engine load — `04`

Load provides operating context alongside speed. It must not be treated as a direct ring-contact force or pressure. The sandbox needs an explicit mapping from any load indicator to the contact-loading history used by the model.

### Coolant temperature — `05`

Coolant temperature describes the cooling system's thermal state. Normal and critical ranges depend on the engine. It does not directly measure lubricant or ring/liner contact temperature.

### Oil temperature — `5C`

Oil temperature can inform a viscosity–temperature model when the lubricant and measurement location are known. It is insufficient to characterize lubrication without the relevant viscosity law, loading, supply conditions, and contact properties.

PID `5C` is not supported by every vehicle. Missing oil-temperature data must remain identifiable as missing; a substituted temperature needs a documented assumption.

### Intake air temperature — `0F`

Intake temperature affects air density and provides combustion context. It is a different quantity from coolant, oil, and contact temperature.

### Manifold absolute pressure — `0B`

MAP measures intake manifold pressure. It may help interpret engine load and boost, depending on the engine. It is not a direct measurement of cylinder pressure or ring-contact loading.

### Throttle position — `11`

Throttle position describes valve opening. On an electronically controlled throttle, it can differ from accelerator-pedal position because the ECU controls the valve. It provides context for demand changes, not a direct torque measurement.

### Timing advance — `0E`

Timing advance describes ignition timing relative to piston position, usually referenced to top dead center. For example, 15° BTDC means 15 crankshaft degrees before top dead center.

Timing changes can reflect operating conditions or ECU control strategies. Timing advance alone is not a knock measurement.

### Mass air flow — `10`

MAF measures intake air mass per unit time. It complements MAP, which measures pressure, and can support operating-point analysis and consistency checks.

### Vehicle speed — `0D`

Vehicle speed helps describe the driving profile when combined with engine speed, load, and other signals. It does not measure engine wear.

## Derived indicators

Thermal Reserve, Lubrication Reserve, Detonation Reserve, Damage Rate, Accumulated Damage, Global Health, and Remaining Useful Life are not OBD-II PIDs. These names refer to proposed higher-level indicators; none is an implemented or validated output of the current foundation.

The first sandbox comparison concerns the top compression ring–liner contact. Its candidate friction and lubrication observables, evidence requirements, and limits are defined in the [scenario catalogue](../validation/scenarios/scenario-catalog.md). The detailed validation protocol is in preparation. Vehicle acquisition belongs to the later real-engine twin described in the [product scope](../product-scope.md).
