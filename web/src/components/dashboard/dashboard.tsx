'use client'

import { CircleAlert, FileUp, LoaderCircle, Play, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import {
  ApiError,
  type Capabilities,
  type RunRecord,
  readSessionToken,
  storeSessionToken,
  VTwinClient,
} from '@/lib/api'
import { caseDocument, DEMO_CASES, type DemoCase, SHARED_GEOMETRY } from '@/lib/cases'
import {
  type Axis,
  changedInputs,
  chartRows,
  formatNumber,
  isReduced,
  parseExport,
  type RunResult,
  summarize,
} from '@/lib/results'

import { ComparisonChart } from './comparison-chart'

type Phase = 'idle' | 'submitting' | 'running' | 'loading' | 'done' | 'error'

interface Job {
  phase: Phase
  run?: RunRecord
  error?: ApiError | Error
}

type Connection =
  | { status: 'checking' }
  | { status: 'ok'; capabilities: Capabilities }
  | { status: 'error'; message: string }

declare global {
  interface Window {
    __vtwinTimings?: { firstChartMs: number; comparisonMs: number | null }[]
  }
}

const STATE_LABELS: Record<string, string> = {
  queued: 'En attente',
  running: 'En cours',
  completed: 'Terminé',
  failed: 'Échec',
  interrupted: 'Interrompu',
}

function runLabel(result: RunResult): string {
  const rpm = result.manifest.resolved_inputs_si.crank_speed_rpm
  return `${result.manifest.case.case_id} · ${formatNumber(rpm, 0)} tr/min`
}

function shortId(runId: string): string {
  return runId.slice(-8)
}

export function Dashboard() {
  const [token, setToken] = useState<string | null>(null)
  const [tokenReady, setTokenReady] = useState(false)
  const [draftToken, setDraftToken] = useState('')
  const [connection, setConnection] = useState<Connection>({
    status: 'checking',
  })
  const [rpms, setRpms] = useState<Record<DemoCase['key'], string>>({
    reference: '2000',
    variant: '4000',
  })
  const [jobs, setJobs] = useState<Record<DemoCase['key'], Job>>({
    reference: { phase: 'idle' },
    variant: { phase: 'idle' },
  })
  const [results, setResults] = useState<Record<string, RunResult>>({})
  const [selection, setSelection] = useState<{
    a: string | null
    b: string | null
  }>({
    a: null,
    b: null,
  })
  const [history, setHistory] = useState<RunRecord[]>([])
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [axis, setAxis] = useState<Axis>('angle')
  const [importError, setImportError] = useState<string | null>(null)
  const [timing, setTiming] = useState<{
    firstChartMs: number
    comparisonMs: number | null
  }>()
  const clickedAt = useRef<number | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    // The fragment and sessionStorage only exist in the browser; a pasted launch
    // URL on an open tab only changes the fragment, so listen for it too.
    const read = () => {
      setToken(readSessionToken())
      setTokenReady(true)
    }
    read()
    window.addEventListener('hashchange', read)
    return () => window.removeEventListener('hashchange', read)
  }, [])

  const client = useMemo(() => new VTwinClient(token), [token])

  useEffect(() => {
    let cancelled = false
    client
      .capabilities()
      .then((capabilities) => !cancelled && setConnection({ status: 'ok', capabilities }))
      .catch(
        (error: Error) => !cancelled && setConnection({ status: 'error', message: error.message }),
      )
    return () => {
      cancelled = true
    }
  }, [client])

  const refreshHistory = useCallback(async () => {
    if (!token) return
    try {
      setHistory(await client.runs(50))
      setHistoryError(null)
    } catch (error) {
      setHistoryError((error as Error).message)
    }
  }, [client, token])

  useEffect(() => {
    // Initial load of the run history once a session token is known.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshHistory()
  }, [refreshHistory])

  const loadResult = useCallback(
    async (run: RunRecord): Promise<RunResult> => {
      const cached = results[run.run_id]
      if (cached) return cached
      const [manifest, series] = await Promise.all([
        client.manifest(run.run_id),
        client.series(run.run_id),
      ])
      const result: RunResult = {
        runId: run.run_id,
        origin: 'api',
        record: run,
        manifest,
        series,
      }
      setResults((current) => ({ ...current, [run.run_id]: result }))
      return result
    },
    [client, results],
  )

  const launch = useCallback(async () => {
    clickedAt.current = performance.now()
    setTiming(undefined)
    setSelection({ a: null, b: null })
    setJobs({ reference: { phase: 'idle' }, variant: { phase: 'idle' } })
    for (const demo of DEMO_CASES) {
      const update = (job: Job) => setJobs((current) => ({ ...current, [demo.key]: job }))
      const rpm = Number(rpms[demo.key])
      try {
        update({ phase: 'submitting' })
        const accepted = await client.submit(caseDocument(demo, rpm))
        update({ phase: 'running', run: accepted })
        const run = await client.waitFor(accepted.run_id, (latest) =>
          update({ phase: 'running', run: latest }),
        )
        if (run.state !== 'completed') {
          update({
            phase: 'error',
            run,
            error: new Error(run.error?.message ?? `Calcul ${STATE_LABELS[run.state]}.`),
          })
          continue
        }
        update({ phase: 'loading', run })
        const result = await loadResult(run)
        update({ phase: 'done', run })
        setSelection((current) =>
          demo.key === 'reference'
            ? { ...current, a: result.runId }
            : { ...current, b: result.runId },
        )
      } catch (error) {
        update({ phase: 'error', error: error as Error })
      }
    }
    void refreshHistory()
  }, [client, loadResult, refreshHistory, rpms])

  const resultA = selection.a ? (results[selection.a] ?? null) : null
  const resultB = selection.b ? (results[selection.b] ?? null) : null
  const displacementRows = useMemo(
    () => chartRows(resultA, resultB, axis, 'displacement'),
    [resultA, resultB, axis],
  )
  const velocityRows = useMemo(
    () => chartRows(resultA, resultB, axis, 'velocity'),
    [resultA, resultB, axis],
  )

  // Repère #46 : du clic au premier graphique lisible, puis à la comparaison complète.
  useEffect(() => {
    const start = clickedAt.current
    if (start === null || !resultA) return
    const frame = requestAnimationFrame(() => {
      const elapsed = performance.now() - start
      setTiming((current) => {
        const next = current
          ? {
              ...current,
              comparisonMs: resultB ? elapsed : current.comparisonMs,
            }
          : { firstChartMs: elapsed, comparisonMs: resultB ? elapsed : null }
        if (next.comparisonMs !== null) {
          clickedAt.current = null
          window.__vtwinTimings = [...(window.__vtwinTimings ?? []), next]
        }
        return next
      })
    })
    return () => cancelAnimationFrame(frame)
  }, [resultA, resultB])

  const choose = useCallback(
    async (slot: 'a' | 'b', runId: string | null) => {
      if (!runId) return
      const run = history.find((item) => item.run_id === runId)
      if (run && !results[runId]) await loadResult(run)
      setSelection((current) => ({ ...current, [slot]: runId }))
    },
    [history, loadResult, results],
  )

  const importFile = useCallback(async (file: File) => {
    try {
      const result = parseExport(await file.text())
      setResults((current) => ({ ...current, [result.runId]: result }))
      setSelection((current) =>
        current.a && current.a !== result.runId
          ? { ...current, b: result.runId }
          : { ...current, a: result.runId },
      )
      setImportError(null)
    } catch (error) {
      setImportError((error as Error).message)
    }
  }, [])

  const busy = Object.values(jobs).some((job) =>
    ['submitting', 'running', 'loading'].includes(job.phase),
  )
  const completedRuns = history.filter((run) => run.state === 'completed')
  const selectable = [
    ...new Set([...Object.keys(results), ...completedRuns.map((run) => run.run_id)]),
  ]
  const selectItems = Object.fromEntries(
    selectable.map((runId) => {
      const result = results[runId]
      const run = history.find((item) => item.run_id === runId)
      const name = result ? runLabel(result) : (run?.case_id ?? runId)
      return [runId, `${name} · ${shortId(runId)}${result?.origin === 'import' ? ' · import' : ''}`]
    }),
  )
  const changes = resultA && resultB ? changedInputs(resultA, resultB) : []
  const summaryA = resultA ? summarize(resultA) : null
  const summaryB = resultB ? summarize(resultB) : null

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold">V-Twin</span>
          <span className="text-sm text-muted-foreground">Sandbox cinématique</span>
        </div>
        <ConnectionBadge connection={connection} hasToken={Boolean(token)} />
      </header>

      {tokenReady && !token && (
        <Alert>
          <CircleAlert />
          <AlertTitle>Jeton de session manquant</AlertTitle>
          <AlertDescription>
            <p>
              Ouvrez le lien affiché par <span className="font-medium">vtwin serve</span> dans le
              terminal, ou collez le jeton ci-dessous.
            </p>
            <form
              className="mt-2 flex max-w-xl gap-2"
              onSubmit={(event) => {
                event.preventDefault()
                if (!draftToken.trim()) return
                storeSessionToken(draftToken.trim())
                setToken(draftToken.trim())
              }}
            >
              <Label htmlFor="session-token" className="sr-only">
                Jeton de session
              </Label>
              <Input
                id="session-token"
                type="password"
                autoComplete="off"
                placeholder="Jeton de session"
                value={draftToken}
                onChange={(event) => setDraftToken(event.target.value)}
              />
              <Button type="submit" variant="secondary">
                Utiliser
              </Button>
            </form>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Calculs</CardTitle>
            <CardDescription>
              Même géométrie, seul le régime change. Alésage {SHARED_GEOMETRY.boreMm} mm, course{' '}
              {SHARED_GEOMETRY.strokeMm} mm, bielle {SHARED_GEOMETRY.rodMm} mm,{' '}
              {SHARED_GEOMETRY.revolutions} tours de {SHARED_GEOMETRY.samplesPerRevolution}{' '}
              échantillons.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Button className="self-start" onClick={() => void launch()} disabled={busy || !token}>
              {busy ? <LoaderCircle className="animate-spin" /> : <Play />}
              Lancer les deux calculs
            </Button>
            {DEMO_CASES.map((demo) => (
              <CaseRow
                key={demo.key}
                demo={demo}
                rpm={rpms[demo.key]}
                onRpm={(value) => setRpms((current) => ({ ...current, [demo.key]: value }))}
                job={jobs[demo.key]}
                disabled={busy}
              />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sans l’API</CardTitle>
            <CardDescription>
              Importez un fichier produit par <span className="font-medium">vtwin export</span>. Il
              est affiché comme un import, pas comme un calcul de cette session.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <input
              ref={fileInput}
              type="file"
              accept="application/json,.json"
              className="sr-only"
              aria-label="Fichier d’export"
              onChange={(event) => {
                const file = event.target.files?.[0]
                if (file) void importFile(file)
                event.target.value = ''
              }}
            />
            <Button variant="outline" onClick={() => fileInput.current?.click()}>
              <FileUp />
              Importer un export CLI
            </Button>
            {importError && (
              <p className="text-sm text-muted-foreground" role="alert">
                {importError}
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Course"
          unit="mm"
          a={summaryA?.strokeMm}
          b={summaryB?.strokeMm}
          digits={2}
          hint="Maximum du déplacement depuis le point mort haut"
        />
        <Metric
          label="Vitesse maximale du piston"
          unit="m/s"
          a={summaryA?.maxSpeedMs}
          b={summaryB?.maxSpeedMs}
          digits={2}
          hint="Valeur absolue maximale sur la série"
        />
        <Metric
          label="Durée d’un tour"
          unit="ms"
          a={summaryA?.periodMs}
          b={summaryB?.periodMs}
          digits={1}
          hint="60 / régime"
        />
        <Card size="sm">
          <CardHeader>
            <CardDescription>Clic → premier graphique lisible</CardDescription>
            <p className="tabular text-2xl font-semibold text-foreground">
              {timing ? `${formatNumber(timing.firstChartMs, 0)} ms` : '—'}
            </p>
          </CardHeader>
          <CardContent className="tabular text-sm text-muted-foreground">
            {timing?.comparisonMs != null
              ? `Comparaison complète : ${formatNumber(timing.comparisonMs, 0)} ms`
              : 'Mesuré dans le navigateur à chaque lancement'}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Comparaison</CardTitle>
          <CardDescription>
            {changes.length
              ? `Entrées différentes : ${changes
                  .map(
                    (change) =>
                      `${change.name.toLowerCase()} ${formatNumber(change.a, 0)} → ${formatNumber(change.b, 0)}`,
                  )
                  .join(', ')}`
              : resultA && resultB
                ? 'Aucune entrée différente entre les deux runs.'
                : 'Lancez les calculs ou choisissez deux runs terminés.'}
            {(resultA && isReduced(resultA)) || (resultB && isReduced(resultB))
              ? ' Courbes réduites pour l’affichage, données complètes conservées.'
              : ''}
          </CardDescription>
          <CardAction>
            <ToggleGroup
              variant="outline"
              size="sm"
              value={[axis]}
              onValueChange={(value) => value[0] && setAxis(value[0] as Axis)}
              aria-label="Axe horizontal"
            >
              <ToggleGroupItem value="angle">Angle</ToggleGroupItem>
              <ToggleGroupItem value="time">Temps</ToggleGroupItem>
            </ToggleGroup>
          </CardAction>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <div className="grid gap-3 sm:grid-cols-2">
            <RunPicker
              label="Run A"
              value={selection.a}
              items={selectItems}
              onChange={(runId) => void choose('a', runId)}
            />
            <RunPicker
              label="Run B"
              value={selection.b}
              items={selectItems}
              onChange={(runId) => void choose('b', runId)}
            />
          </div>
          {resultA || resultB ? (
            <div className="grid gap-6 xl:grid-cols-2">
              <div className="flex flex-col gap-2">
                <p className="text-sm font-medium">Déplacement du piston, mm</p>
                <ComparisonChart
                  rows={displacementRows}
                  axis={axis}
                  unit="mm"
                  labelA={resultA && runLabel(resultA)}
                  labelB={resultB && runLabel(resultB)}
                  digits={0}
                />
              </div>
              <div className="flex flex-col gap-2">
                <p className="text-sm font-medium">Vitesse du piston, m/s</p>
                <ComparisonChart
                  rows={velocityRows}
                  axis={axis}
                  unit="m/s"
                  labelA={resultA && runLabel(resultA)}
                  labelB={resultB && runLabel(resultB)}
                  digits={0}
                />
              </div>
            </div>
          ) : (
            <div className="grid gap-6 xl:grid-cols-2">
              <Skeleton className="h-72 w-full" />
              <Skeleton className="h-72 w-full" />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Historique</CardTitle>
          <CardDescription>Runs enregistrés dans l’espace de travail local.</CardDescription>
          <CardAction>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void refreshHistory()}
              disabled={!token}
            >
              <RefreshCw />
              Actualiser
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          {historyError ? (
            <p className="text-sm text-muted-foreground">{historyError}</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run</TableHead>
                  <TableHead>Cas</TableHead>
                  <TableHead>État</TableHead>
                  <TableHead className="text-right">Échantillons</TableHead>
                  <TableHead className="text-right">Calcul moteur</TableHead>
                  <TableHead>Créé le</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-muted-foreground">
                      Aucun run pour l’instant.
                    </TableCell>
                  </TableRow>
                )}
                {history.slice(0, 12).map((run) => (
                  <TableRow key={run.run_id}>
                    <TableCell className="tabular">{shortId(run.run_id)}</TableCell>
                    <TableCell>{run.case_id}</TableCell>
                    <TableCell>
                      <StateBadge run={run} />
                    </TableCell>
                    <TableCell className="tabular text-right">
                      {run.progress.total_samples.toLocaleString('fr-FR')}
                    </TableCell>
                    <TableCell className="tabular text-right">
                      {run.kpis ? `${formatNumber(run.kpis.engine_wall_s * 1e3, 2)} ms` : '—'}
                    </TableCell>
                    <TableCell className="tabular text-muted-foreground">
                      {new Date(run.created_at_utc).toLocaleString('fr-FR')}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        Données synthétiques de démonstration : la longueur de bielle et les régimes sont des
        hypothèses. Modèle cinématique seul, sans efforts ni usure.
      </p>
    </div>
  )
}

function ConnectionBadge({ connection, hasToken }: { connection: Connection; hasToken: boolean }) {
  if (connection.status === 'checking')
    return <Badge variant="outline">Connexion au service local…</Badge>
  if (connection.status === 'error')
    return (
      <Badge variant="outline">
        <CircleAlert />
        Service local injoignable
      </Badge>
    )
  const { capabilities } = connection
  return (
    <div className="flex items-center gap-2">
      <Badge variant="secondary">API v{capabilities.application_version}</Badge>
      <Badge variant="outline">
        {capabilities.simulation_available ? capabilities.models.join(', ') : 'Lecture seule'}
      </Badge>
      {!hasToken && <Badge variant="outline">Sans jeton</Badge>}
    </div>
  )
}

function CaseRow({
  demo,
  rpm,
  onRpm,
  job,
  disabled,
}: {
  demo: DemoCase
  rpm: string
  onRpm: (value: string) => void
  job: Job
  disabled: boolean
}) {
  const run = job.run
  const progress = run ? (run.progress.completed_samples / run.progress.total_samples) * 100 : 0
  const inputId = `rpm-${demo.key}`
  return (
    <div className="flex flex-col gap-3 rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex min-w-40 flex-col">
          <span className="text-sm font-medium">{demo.label}</span>
          <span className="text-xs text-muted-foreground">{demo.caseId}</span>
        </div>
        <div className="flex items-center gap-2">
          <Label htmlFor={inputId} className="text-muted-foreground">
            Régime
          </Label>
          <Input
            id={inputId}
            className="tabular h-8 w-24"
            inputMode="numeric"
            value={rpm}
            disabled={disabled}
            onChange={(event) => onRpm(event.target.value)}
          />
          <span className="text-sm text-muted-foreground">tr/min</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          {run?.kpis && (
            <span className="tabular text-sm text-muted-foreground">
              {formatNumber(run.kpis.engine_wall_s * 1e3, 2)} ms de calcul
            </span>
          )}
          <JobBadge job={job} />
        </div>
      </div>
      {(job.phase === 'running' || job.phase === 'submitting') && (
        <Progress value={progress} aria-label={`Progression ${demo.label}`} />
      )}
      {job.phase === 'error' && job.error && <JobError error={job.error} />}
    </div>
  )
}

function JobBadge({ job }: { job: Job }) {
  switch (job.phase) {
    case 'idle':
      return <Badge variant="outline">Prêt</Badge>
    case 'submitting':
      return <Badge variant="outline">Envoi…</Badge>
    case 'running':
      return (
        <Badge variant="secondary">
          <LoaderCircle className="animate-spin" />
          {job.run ? STATE_LABELS[job.run.state] : 'En cours'}
        </Badge>
      )
    case 'loading':
      return <Badge variant="secondary">Lecture des résultats…</Badge>
    case 'done':
      return <Badge>Terminé</Badge>
    case 'error':
      return (
        <Badge variant="outline">
          <CircleAlert />
          {job.run ? STATE_LABELS[job.run.state] : 'Refusé'}
        </Badge>
      )
  }
}

function JobError({ error }: { error: ApiError | Error }) {
  const details = error instanceof ApiError ? error.details : []
  return (
    <Alert>
      <CircleAlert />
      <AlertTitle>{error.message}</AlertTitle>
      {details.length > 0 && (
        <AlertDescription>
          <ul className="list-disc pl-4">
            {details.map((issue) => (
              <li key={issue.path}>
                <span className="font-medium">{issue.path}</span> : {issue.message}
              </li>
            ))}
          </ul>
        </AlertDescription>
      )}
    </Alert>
  )
}

function StateBadge({ run }: { run: RunRecord }) {
  const label = STATE_LABELS[run.state] ?? run.state
  if (run.state === 'completed') return <Badge variant="secondary">{label}</Badge>
  if (run.state === 'failed' || run.state === 'interrupted')
    return (
      <Badge variant="outline" title={run.error?.message}>
        <CircleAlert />
        {label}
      </Badge>
    )
  return <Badge variant="outline">{label}</Badge>
}

function Metric({
  label,
  unit,
  a,
  b,
  digits,
  hint,
}: {
  label: string
  unit: string
  a?: number
  b?: number
  digits: number
  hint: string
}) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <p className="tabular text-2xl font-semibold text-foreground">
          {a === undefined ? '—' : `${formatNumber(a, digits)} ${unit}`}
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-1 text-sm text-muted-foreground">
        <span className="tabular">
          {b === undefined
            ? 'Run B : —'
            : `Run B : ${formatNumber(b, digits)} ${unit}${
                a ? ` (${b >= a ? '+' : ''}${formatNumber(((b - a) / a) * 100, 0)} %)` : ''
              }`}
        </span>
        <Separator />
        <span>{hint}</span>
      </CardContent>
    </Card>
  )
}

function RunPicker({
  label,
  value,
  items,
  onChange,
}: {
  label: string
  value: string | null
  items: Record<string, string>
  onChange: (runId: string | null) => void
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label className="text-muted-foreground">{label}</Label>
      <Select items={items} value={value} onValueChange={(next) => onChange(next as string | null)}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Choisir un run terminé" />
        </SelectTrigger>
        <SelectContent>
          {Object.entries(items).map(([runId, name]) => (
            <SelectItem key={runId} value={runId}>
              {name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
