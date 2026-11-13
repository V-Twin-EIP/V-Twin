import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it, vi } from 'vitest'

import { ApiError, readSessionToken, VTwinClient } from './api'
import { caseDocument, DEMO_CASES } from './cases'
import { changedInputs, chartRows, parseExport, type RunResult, summarize } from './results'

const examples = (name: string) =>
  JSON.parse(readFileSync(resolve(process.cwd(), '../examples/cases', name), 'utf-8'))

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function result(rpm: number, samples = 721): RunResult {
  const perRev = 360
  const omega = (rpm * 2 * Math.PI) / 60
  const r = 0.043
  const index = Array.from({ length: samples }, (_, i) => i)
  const theta = index.map((i) => (i * 2 * Math.PI) / perRev)
  return {
    runId: `run-${rpm}`,
    origin: 'api',
    record: { kpis: { engine_wall_s: 0.0002 } } as RunResult['record'],
    manifest: {
      run_id: `run-${rpm}`,
      case: { case_id: 'X', title: '', synthetic: true, sha256: '' },
      model: { id: 'slider-crank-kinematics', version: '1.0.0' },
      observables: [],
      resolved_inputs_si: {
        bore_m: 0.086,
        stroke_m: 0.086,
        connecting_rod_length_m: 0.143,
        crank_speed_rpm: rpm,
        revolutions: 2,
        samples_per_revolution: perRev,
      },
    },
    series: {
      time_s: theta.map((t) => t / omega),
      crank_angle_rad: theta,
      piston_displacement_m: theta.map((t) => r * (1 - Math.cos(t))),
      piston_velocity_m_s: theta.map((t) => omega * r * Math.sin(t)),
    },
  }
}

describe('demo cases', () => {
  it('match the versioned example files exactly', () => {
    expect(caseDocument(DEMO_CASES[0])).toEqual(examples('kinematics-ref-2000rpm.json'))
    expect(caseDocument(DEMO_CASES[1])).toEqual(examples('kinematics-var-4000rpm.json'))
  })
})

describe('session token', () => {
  it('moves the token from the fragment to sessionStorage and clears the URL', () => {
    window.history.replaceState(null, '', '/?x=1#session=abc%2Fdef')
    expect(readSessionToken()).toBe('abc/def')
    expect(window.location.hash).toBe('')
    expect(window.location.search).toBe('?x=1')
    expect(readSessionToken()).toBe('abc/def')
  })
})

describe('VTwinClient', () => {
  it('sends the session header and reports structured errors', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      json(
        {
          error: {
            code: 'invalid_input',
            message: 'Case document is invalid.',
            retryable: false,
            details: [{ path: 'sampling.revolutions', message: 'Must be an integer.' }],
          },
        },
        422,
      ),
    )
    const client = new VTwinClient('token-123', fetcher, '')
    const error = await client.submit({}).catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).details[0].path).toBe('sampling.revolutions')
    const headers = fetcher.mock.calls[0][1]?.headers as Headers
    expect(headers.get('X-VTwin-Session')).toBe('token-123')
  })

  it('waits while the coordinator is busy, then submits', async () => {
    const busy = {
      error: { code: 'workspace_busy', message: 'busy', retryable: true, details: [] },
    }
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(json(busy, 409))
      .mockResolvedValueOnce(json({ run: { run_id: 'run-1', state: 'queued' } }, 202))
    const run = await new VTwinClient('t', fetcher, '').submit({})
    expect(run.run_id).toBe('run-1')
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('reads every series page', async () => {
    const page = (start: number, next: number | null, values: number[]) =>
      json({
        start,
        next_start: next,
        series: { time_s: { unit: 's', values } },
      })
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(page(0, 2, [0, 1]))
      .mockResolvedValueOnce(page(2, null, [2]))
    const series = await new VTwinClient('t', fetcher, '').series('run-1')
    expect(series.time_s).toEqual([0, 1, 2])
    expect(String(fetcher.mock.calls[1][0])).toContain('start=2')
  })

  it('maps a network failure to an explicit error', async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('failed'))
    await expect(new VTwinClient('t', fetcher, '').capabilities()).rejects.toMatchObject({
      code: 'unreachable',
    })
  })
})

describe('results', () => {
  it('summarizes stroke, speed and period', () => {
    const summary = summarize(result(2000))
    expect(summary.strokeMm).toBeCloseTo(86, 6)
    expect(summary.periodMs).toBeCloseTo(30, 9)
    expect(summary.engineMs).toBeCloseTo(0.2, 9)
  })

  it('reports only the inputs that really changed', () => {
    expect(changedInputs(result(2000), result(4000))).toEqual([
      { name: 'Régime', a: 2000, b: 4000 },
    ])
  })

  it('aligns both runs on the angle axis and keeps both on the time axis', () => {
    const byAngle = chartRows(result(2000), result(4000), 'angle', 'velocity')
    expect(byAngle).toHaveLength(721)
    expect(byAngle[90].b! / byAngle[90].a!).toBeCloseTo(2, 9)
    const byTime = chartRows(result(2000), result(4000), 'time', 'displacement')
    expect(byTime.at(-1)!.x).toBeCloseTo(60, 6)
    expect(byTime.filter((row) => row.b !== undefined).at(-1)!.x).toBeCloseTo(30, 6)
  })

  it('reduces very long series for display only', () => {
    const big = result(2000, 20_001)
    expect(chartRows(big, null, 'angle', 'displacement').length).toBeLessThanOrEqual(4_001)
    expect(big.series.time_s).toHaveLength(20_001)
  })

  it('reads a vtwin export file and rejects anything else', () => {
    const exported = {
      record_type: 'run_export',
      run_id: 'run-x',
      status: { run_id: 'run-x' },
      manifest: result(2000).manifest,
      series: Object.fromEntries(
        Object.entries(result(2000).series).map(([name, values]) => [name, { unit: '', values }]),
      ),
    }
    const parsed = parseExport(JSON.stringify(exported))
    expect(parsed.origin).toBe('import')
    expect(parsed.series.time_s).toHaveLength(721)
    expect(() => parseExport('{"record_type": "other"}')).toThrow(/vtwin export/)
    expect(() => parseExport('not json')).toThrow(/JSON/)
  })
})
