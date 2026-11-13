import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TooltipProvider } from '@/components/ui/tooltip'

import { Dashboard } from './dashboard'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function fakeApi(options: { rejectVariant?: boolean } = {}) {
  const runs: Record<string, { rpm: number; caseId: string }> = {}
  return vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/api/v1/capabilities'))
      return json({
        api_version: '1',
        application_version: '0.1.0',
        stage: 'kinematics-demo',
        simulation_available: true,
        models: ['slider-crank-kinematics@1.0.0'],
      })
    if (url.includes('/api/v1/runs?')) return json({ runs: [], active_run: null })
    if (url.endsWith('/api/v1/runs') && init?.method === 'POST') {
      const document = JSON.parse(String(init.body))
      const rpm = document.operating_point.crank_speed.value
      if (options.rejectVariant && document.case_id === 'KIN-DEMO-VAR')
        return json(
          {
            error: {
              code: 'invalid_input',
              message: 'Case document is invalid.',
              retryable: false,
              details: [{ path: 'operating_point.crank_speed.value', message: 'Out of range.' }],
            },
          },
          422,
        )
      const id = `run-20261113T000000Z-0000000${Object.keys(runs).length}`
      runs[id] = { rpm, caseId: document.case_id }
      return json({ run: record(id, document.case_id, 'queued') }, 202)
    }
    const match = /\/api\/v1\/runs\/([^/?]+)(\/[a-z]+)?/.exec(url)
    if (match) {
      const [, id, suffix] = match
      const run = runs[id]
      if (!suffix) return json({ run: record(id, run.caseId, 'completed') })
      if (suffix === '/manifest')
        return json({
          run_id: id,
          case: { case_id: run.caseId, title: '', synthetic: true, sha256: '' },
          model: { id: 'slider-crank-kinematics', version: '1.0.0' },
          observables: [],
          resolved_inputs_si: { stroke_m: 0.086, crank_speed_rpm: run.rpm, revolutions: 2 },
        })
      const omega = (run.rpm * 2 * Math.PI) / 60
      const theta = [0, Math.PI / 2, Math.PI]
      return json({
        next_start: null,
        series: {
          time_s: { unit: 's', values: theta.map((t) => t / omega) },
          crank_angle_rad: { unit: 'rad', values: theta },
          piston_displacement_m: { unit: 'm', values: [0, 0.043, 0.086] },
          piston_velocity_m_s: { unit: 'm/s', values: [0, omega * 0.043, 0] },
        },
      })
    }
    return json({ error: { code: 'not_found', message: 'Not found' } }, 404)
  })
}

function record(id: string, caseId: string, state: string) {
  return {
    run_id: id,
    case_id: caseId,
    state,
    created_at_utc: '2026-11-13T00:00:00Z',
    finished_at_utc: null,
    attempts: 1,
    progress: { completed_samples: state === 'completed' ? 3 : 0, total_samples: 3 },
    resumable: false,
    error: null,
    kpis:
      state === 'completed'
        ? {
            simulated_duration_s: 0.06,
            engine_wall_s: 0.0002,
            simulation_rate_s_per_s: 300,
            compute_wall_s: 0.001,
            output_samples: 3,
          }
        : null,
  }
}

function renderDashboard() {
  return render(
    <TooltipProvider>
      <Dashboard />
    </TooltipProvider>,
  )
}

describe('Dashboard', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
    window.history.replaceState(null, '', '/')
  })
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('asks for the session token when the launch link was not used', async () => {
    vi.stubGlobal('fetch', fakeApi())
    renderDashboard()
    expect(await screen.findByText('Jeton de session manquant')).toBeTruthy()
    expect(
      (screen.getByRole('button', { name: /Lancer les deux calculs/ }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
  })

  it('runs both cases and reports the only changed input', async () => {
    window.history.replaceState(null, '', '/#session=test-token')
    const fetcher = fakeApi()
    vi.stubGlobal('fetch', fetcher)
    renderDashboard()
    const launch = await screen.findByRole('button', { name: /Lancer les deux calculs/ })
    await waitFor(() => expect((launch as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(launch)
    await waitFor(() => expect(screen.getAllByText('Terminé')).toHaveLength(2), { timeout: 5000 })
    expect(await screen.findByText(/Entrées différentes : régime 2\s000 → 4\s000/)).toBeTruthy()
    expect(screen.getByText(/Run B : 15,0 ms/)).toBeTruthy()
    const posted = fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')
    expect(posted).toHaveLength(2)
    expect((posted[0][1]?.headers as Headers).get('X-VTwin-Session')).toBe('test-token')
  })

  it('shows field-level diagnostics when a case is refused', async () => {
    window.history.replaceState(null, '', '/#session=test-token')
    vi.stubGlobal('fetch', fakeApi({ rejectVariant: true }))
    renderDashboard()
    const launch = await screen.findByRole('button', { name: /Lancer les deux calculs/ })
    await waitFor(() => expect((launch as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(launch)
    expect(await screen.findByText('Case document is invalid.', {}, { timeout: 5000 })).toBeTruthy()
    expect(screen.getByText('operating_point.crank_speed.value')).toBeTruthy()
    expect(screen.getByText('Refusé')).toBeTruthy()
  })
})
