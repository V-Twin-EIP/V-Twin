/** Display-side derivations: unit conversion, summaries, comparison and reduction. */

import type { Manifest, RunRecord, Series } from './api'

export type ResultOrigin = 'api' | 'import'

export interface RunResult {
  runId: string
  origin: ResultOrigin
  record: RunRecord
  manifest: Manifest
  series: Series
}

export interface Summary {
  strokeMm: number
  maxSpeedMs: number
  periodMs: number
  rpm: number
  samples: number
  engineMs: number | null
}

export function summarize(result: RunResult): Summary {
  const { series, manifest, record } = result
  const displacement = series.piston_displacement_m
  const rpm = manifest.resolved_inputs_si.crank_speed_rpm
  const engine = record.kpis?.engine_wall_s
  return {
    strokeMm: Math.max(...displacement) * 1e3,
    maxSpeedMs: Math.max(...series.piston_velocity_m_s.map(Math.abs)),
    periodMs: (60 / rpm) * 1e3,
    rpm,
    samples: displacement.length,
    engineMs: engine === undefined ? null : engine * 1e3,
  }
}

export type Axis = 'angle' | 'time'
export type Quantity = 'displacement' | 'velocity'

export interface ChartRow {
  x: number
  a?: number
  b?: number
}

export const MAX_DISPLAY_POINTS = 4_000

function points(result: RunResult, axis: Axis, quantity: Quantity): [number, number][] {
  const { series } = result
  const xs =
    axis === 'angle'
      ? series.crank_angle_rad.map((value) => (value * 180) / Math.PI)
      : series.time_s.map((value) => value * 1e3)
  const ys =
    quantity === 'displacement'
      ? series.piston_displacement_m.map((value) => value * 1e3)
      : series.piston_velocity_m_s
  const stride = Math.max(1, Math.ceil(xs.length / MAX_DISPLAY_POINTS))
  const out: [number, number][] = []
  for (let index = 0; index < xs.length; index += stride) out.push([xs[index], ys[index]])
  const last = xs.length - 1
  if (last % stride !== 0) out.push([xs[last], ys[last]])
  return out
}

/** True when a series is decimated for display; the stored result is never altered. */
export function isReduced(result: RunResult): boolean {
  return result.series.time_s.length > MAX_DISPLAY_POINTS
}

/** Merge two runs on a shared x coordinate; gaps are bridged by the chart. */
export function chartRows(
  a: RunResult | null,
  b: RunResult | null,
  axis: Axis,
  quantity: Quantity,
): ChartRow[] {
  const rows = new Map<number, ChartRow>()
  for (const [key, result] of [
    ['a', a],
    ['b', b],
  ] as const) {
    if (!result) continue
    for (const [x, y] of points(result, axis, quantity)) {
      const rounded = Math.round(x * 1e9) / 1e9
      const row = rows.get(rounded) ?? { x: rounded }
      row[key] = y
      rows.set(rounded, row)
    }
  }
  return [...rows.values()].sort((left, right) => left.x - right.x)
}

export interface InputChange {
  name: string
  a: number
  b: number
}

const LABELS: Record<string, string> = {
  bore_m: 'Alésage',
  stroke_m: 'Course',
  connecting_rod_length_m: 'Longueur de bielle',
  crank_speed_rpm: 'Régime',
  revolutions: 'Tours simulés',
  samples_per_revolution: 'Échantillons par tour',
}

/** Inputs that actually differ, from the frozen manifests (not from the intent). */
export function changedInputs(a: RunResult, b: RunResult): InputChange[] {
  const left = a.manifest.resolved_inputs_si
  const right = b.manifest.resolved_inputs_si
  return Object.keys(LABELS)
    .filter(
      (key) => Math.abs((left[key] ?? NaN) - (right[key] ?? NaN)) > 1e-12 * Math.abs(left[key]),
    )
    .map((key) => ({ name: LABELS[key], a: left[key], b: right[key] }))
}

interface ExportDocument {
  record_type: string
  run_id: string
  status: RunRecord
  manifest: Manifest
  series: Record<string, { unit: string; values: number[] }>
}

/** Read a `vtwin export` file: the fallback path when the HTTP API is unavailable. */
export function parseExport(text: string): RunResult {
  let document: ExportDocument
  try {
    document = JSON.parse(text) as ExportDocument
  } catch {
    throw new Error('Le fichier n’est pas un JSON valide.')
  }
  if (document?.record_type !== 'run_export' || !document.series || !document.manifest)
    throw new Error('Ce fichier n’est pas un export de vtwin export.')
  const series = Object.fromEntries(
    Object.entries(document.series).map(([name, item]) => [name, item.values]),
  ) as Series
  for (const name of [
    'time_s',
    'crank_angle_rad',
    'piston_displacement_m',
    'piston_velocity_m_s',
  ] as const) {
    if (!Array.isArray(series[name])) throw new Error(`Série ${name} absente de l’export.`)
  }
  return {
    runId: document.run_id,
    origin: 'import',
    record: document.status,
    manifest: document.manifest,
    series,
  }
}

export function formatNumber(value: number, digits = 1): string {
  return new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)
}
