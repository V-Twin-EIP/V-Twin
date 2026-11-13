/**
 * Client of the local V-Twin API (`/api/v1`, same origin as the served UI).
 *
 * The per-launch session token arrives in the URL fragment `#session=…` printed by
 * `vtwin serve`. It is moved to sessionStorage, removed from the address bar and sent
 * as `X-VTwin-Session` on run routes. It is never logged or persisted elsewhere.
 */

export const SESSION_HEADER = 'X-VTwin-Session'
const STORAGE_KEY = 'vtwin.session'
const API_BASE = process.env.NEXT_PUBLIC_VTWIN_API ?? ''
const PAGE_LIMIT = 20_000

export type RunState = 'queued' | 'running' | 'completed' | 'failed' | 'interrupted'

export interface FieldIssue {
  path: string
  message: string
}

export interface RunErrorBody {
  code: string
  message: string
  retryable: boolean
  details: FieldIssue[]
  run_id?: string
}

export interface RunKpis {
  simulated_duration_s: number
  engine_wall_s: number
  simulation_rate_s_per_s: number | null
  compute_wall_s: number
  output_samples: number
}

export interface RunRecord {
  run_id: string
  case_id: string
  state: RunState
  created_at_utc: string
  finished_at_utc: string | null
  attempts: number
  progress: { completed_samples: number; total_samples: number }
  resumable: boolean
  error: RunErrorBody | null
  kpis: RunKpis | null
}

export interface Manifest {
  run_id: string
  case: { case_id: string; title: string; synthetic: boolean; sha256: string }
  resolved_inputs_si: Record<string, number>
  model: { id: string; version: string }
  observables: { id: string; unit: string; definition: string }[]
}

export type ObservableId =
  'time_s' | 'crank_angle_rad' | 'piston_displacement_m' | 'piston_velocity_m_s'

export type Series = Record<ObservableId, number[]>

export interface Capabilities {
  api_version: string
  application_version: string
  stage: string
  simulation_available: boolean
  models: string[]
  session_header?: string | null
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly retryable: boolean
  readonly details: FieldIssue[]

  constructor(status: number, body: Partial<RunErrorBody> | undefined, fallback: string) {
    super(body?.message ?? fallback)
    this.name = 'ApiError'
    this.status = status
    this.code = body?.code ?? 'http_error'
    this.retryable = body?.retryable ?? false
    this.details = body?.details ?? []
  }
}

/** Read the token from the launch URL fragment once, then from sessionStorage. */
export function readSessionToken(win: Window = window): string | null {
  const match = /(?:^#|&)session=([^&]+)/.exec(win.location.hash)
  if (match) {
    const token = decodeURIComponent(match[1])
    try {
      win.sessionStorage.setItem(STORAGE_KEY, token)
    } catch {
      // Private mode: the token still works for this page.
    }
    const { pathname, search } = win.location
    win.history.replaceState(null, '', pathname + search)
    return token
  }
  try {
    return win.sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function storeSessionToken(token: string, win: Window = window): void {
  try {
    win.sessionStorage.setItem(STORAGE_KEY, token)
  } catch {
    // Ignored: kept in memory by the caller.
  }
}

export class VTwinClient {
  constructor(
    private readonly token: string | null,
    private readonly fetcher: typeof fetch = (...args) => fetch(...args),
    private readonly base: string = API_BASE,
  ) {}

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers)
    if (this.token) headers.set(SESSION_HEADER, this.token)
    if (init.body) headers.set('Content-Type', 'application/json')
    let response: Response
    try {
      response = await this.fetcher(this.base + path, { ...init, headers })
    } catch {
      throw new ApiError(0, { code: 'unreachable' }, 'Le service local ne répond pas.')
    }
    let body: unknown = null
    try {
      body = await response.json()
    } catch {
      body = null
    }
    if (!response.ok) {
      const error = (body as { error?: RunErrorBody } | null)?.error
      throw new ApiError(response.status, error, `Réponse HTTP ${response.status}.`)
    }
    return body as T
  }

  capabilities(): Promise<Capabilities> {
    return this.request('/api/v1/capabilities')
  }

  async submit(document: object, signal?: AbortSignal): Promise<RunRecord> {
    // One run at a time on the coordinator: wait politely while it is busy.
    for (let attempt = 0; ; attempt++) {
      try {
        const body = await this.request<{ run: RunRecord }>('/api/v1/runs', {
          method: 'POST',
          body: JSON.stringify(document),
          signal,
        })
        return body.run
      } catch (error) {
        if (!(error instanceof ApiError) || error.code !== 'workspace_busy' || attempt >= 60)
          throw error
        await sleep(250, signal)
      }
    }
  }

  async run(id: string): Promise<RunRecord> {
    return (await this.request<{ run: RunRecord }>(`/api/v1/runs/${id}`)).run
  }

  async runs(limit = 50): Promise<RunRecord[]> {
    return (await this.request<{ runs: RunRecord[] }>(`/api/v1/runs?limit=${limit}`)).runs
  }

  manifest(id: string): Promise<Manifest> {
    return this.request(`/api/v1/runs/${id}/manifest`)
  }

  async series(id: string): Promise<Series> {
    const values: Partial<Record<ObservableId, number[]>> = {}
    let start: number | null = 0
    while (start !== null) {
      const page: {
        next_start: number | null
        series: Record<ObservableId, { unit: string; values: number[] }>
      } = await this.request(`/api/v1/runs/${id}/series?start=${start}&limit=${PAGE_LIMIT}`)
      for (const [name, item] of Object.entries(page.series) as [
        ObservableId,
        { values: number[] },
      ][]) {
        values[name] = (values[name] ?? []).concat(item.values)
      }
      start = page.next_start
    }
    return values as Series
  }

  async waitFor(
    id: string,
    onUpdate: (run: RunRecord) => void,
    signal?: AbortSignal,
  ): Promise<RunRecord> {
    for (;;) {
      const run = await this.run(id)
      onUpdate(run)
      if (run.state === 'completed' || run.state === 'failed' || run.state === 'interrupted')
        return run
      await sleep(100, signal)
    }
  }
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    })
  })
}
