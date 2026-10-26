# Technology watch (O1 · `track:tech-watch`)

Evidence index for the technology-watch objective. Journal tracked in [#29](https://github.com/V-Twin-EIP/V-Twin/issues/29).
Rule: an entry is added only if it feeds a study, POC, benchmark or decision.

> Status: work in progress, last updated 2026-10-23.

**Cadence:** 15 min at the end of the weekly team meeting. Each week one person adds 1 to 3 lines to the journal before the meeting
**Follow-up period:** 26/10/2026 → <to be confirmed>.

## 1. Starting point

| Technology | Team level | Status |
| :--- | :--- | :--- |
| Python, NumPy, SciPy | <mastered> | not new |
| Vue / TypeScript | <mastered> | not new |
| uv, GitHub Actions CI | <mastered> | not new |
| MQTT | <never used> | **new exploration** (POC + study #31) |
| InfluxDB| <never used> | **new exploration** (study #32, benchmark #43) |
| OBD-II / CAN acquisition | <never used> | **new exploration** (study #30, POC) |

Technology that will be integrated into the product (#44): **<to be decided: e.g. MQTT or the chosen DB>**.
It counts as new exploration because no team member had used MQTT before this project.

## 2. Sources followed

| Source | Type | Link | Why credible |
| :--- | :--- | :--- | :--- |
| <MQTT / Mosquitto official docs> | Official docs | https://mqtt.org/ | Reference spec |
| <InfluxDB / TimescaleDB docs and GitHub issues> | Docs + GitHub | https://docs.influxdata.com/ | Maintainers answer |
Screenshots of RSS feeds, newsletters and bookmarks: `docs/technology-watch/assets/`.

## 3. Journal

| Date | Source | Question | Critical analysis | Expected impact | Linked to |
| :--- | :--- | :--- | :--- | :--- | :--- |

## 4. Work produced from the watch

| Item | Issue | Document / evidence | Status |
| :--- | :--- | :--- | :--- |
| Study: acquisition (OBD-II / CAN / sensors) | [#30](https://github.com/V-Twin-EIP/V-Twin/issues/30) | [01_telemetrie_obd2_vs_can.md](../research/etudes-comparaison/01_telemetrie_obd2_vs_can.md) | Done |
| Study: telemetry transport (MQTT / WebSocket / REST / SSE) | [#31](https://github.com/V-Twin-EIP/V-Twin/issues/31) | [02_protocoles_reseau_mqtt_vs_websocket.md](../research/etudes-comparaison/02_protocoles_reseau_mqtt_vs_websocket.md) | Done |
| Study: time-series storage (InfluxDB / TimescaleDB) | [#32](https://github.com/V-Twin-EIP/V-Twin/issues/32) | [03_stockage_series_temporelles_timescaledb_vs_influxdb.md](../research/etudes-comparaison/03_stockage_series_temporelles_timescaledb_vs_influxdb.md) | Done |
| Study: wear estimation (physical / ML / hybrid) | [#33](https://github.com/V-Twin-EIP/V-Twin/issues/33) | [04_prediction_usure_moteur_pinn_vs_ml.md](../research/etudes-comparaison/04_prediction_usure_moteur_pinn_vs_ml.md) | Done |
| POC: acquisition | [#34](https://github.com/V-Twin-EIP/V-Twin/issues/34) | — | Not started |
| POC: MQTT telemetry | [#35](https://github.com/V-Twin-EIP/V-Twin/issues/35) | — | Not started |
| Benchmark: transport | [#42](https://github.com/V-Twin-EIP/V-Twin/issues/42) | — | Not started |
| Benchmark: storage | [#43](https://github.com/V-Twin-EIP/V-Twin/issues/43) | — | Not started |
| Integration of a new technology | [#44](https://github.com/V-Twin-EIP/V-Twin/issues/44) | — | Not started |
| Final synthesis | [#45](https://github.com/V-Twin-EIP/V-Twin/issues/45) | — | Not started |

## 5. Community interactions (target: 1 to 2, active)

| Date | Where | Precise question | Link / trace | Answer | What we learned / applied |
| :--- | :--- | :--- | :--- | :--- | :--- |
| | | | | | |

## 6. Team sharing notes

| Date | Presented | Decision or action |
| :--- | :--- | :--- |
| | | |

## 7. Decisions (adopted or rejected)

| Decision | Status | Why | Evidence (study / POC / benchmark / ADR) |
| :--- | :--- | :--- | :--- |
| Ingestion duale CAN / OBD-II | Adopted | CAN haute fréquence (100–500 Hz) pour simulateur, OBD-II pour véhicules série | [Study #30](../research/etudes-comparaison/01_telemetrie_obd2_vs_can.md) |
| Transport hybride MQTT v5 + WebSocket | Adopted | MQTT v5/Protobuf pour ingestion télémétrique résiliente, WebSocket pour flux temps réel 3D, REST pour services CRUD | [Study #31](../research/etudes-comparaison/02_protocoles_reseau_mqtt_vs_websocket.md) |
| TimescaleDB pour séries temporelles | Adopted | SQL ANSI unifié, Hypertables, jointures natives avec nomenclatures/pièces et intégrité ACID | [Study #32](../research/etudes-comparaison/03_stockage_series_temporelles_timescaledb_vs_influxdb.md) |
| Approche hybride PINN pour usure | Adopted | Inférence temps réel (<20 ms) tout en garantissant le respect strict des lois physiques (fatigue, lubrification) | [Study #33](../research/etudes-comparaison/04_prediction_usure_moteur_pinn_vs_ml.md) |

## 8. Mentoring summary

Updated before each review (next: 2026-10-26).
- What the watch changed in decisions:
- New technologies explored and level reached:
- Community learnings:
- Questions for the mentor: