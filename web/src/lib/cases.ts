/**
 * The two demo cases (#3). Must stay identical to examples/cases/*.json: a unit test
 * compares them. Only the crank speed differs between reference and variant.
 */

export interface DemoCase {
  key: 'reference' | 'variant'
  label: string
  caseId: string
  rpm: number
}

export const DEMO_CASES: DemoCase[] = [
  { key: 'reference', label: 'Référence', caseId: 'KIN-DEMO-REF', rpm: 2000 },
  { key: 'variant', label: 'Variante', caseId: 'KIN-DEMO-VAR', rpm: 4000 },
]

export const SHARED_GEOMETRY = {
  boreMm: 86,
  strokeMm: 86,
  rodMm: 143,
  revolutions: 2,
  samplesPerRevolution: 360,
}

const HYDRA = 'Ricardo Hydra, docs/validation/scenarios/scenario-catalog.md §2'

export function caseDocument(demo: DemoCase, rpm: number = demo.rpm): Record<string, unknown> {
  const reference = demo.key === 'reference'
  const role = reference ? 'Référence' : 'Variante (seul le régime change)'
  return {
    schema: 'vtwin.kinematic-case',
    schema_version: '1.0.0',
    case_id: demo.caseId,
    title: `${role} — cinématique bielle-manivelle à ${rpm} tr/min`,
    model: 'slider-crank-kinematics',
    synthetic: true,
    geometry: {
      bore: { value: SHARED_GEOMETRY.boreMm, unit: 'mm', source: HYDRA },
      stroke: { value: SHARED_GEOMETRY.strokeMm, unit: 'mm', source: HYDRA },
      connecting_rod_length: {
        value: SHARED_GEOMETRY.rodMm,
        unit: 'mm',
        source: 'hypothèse de démo (r/l ≈ 0.30), à remplacer par la valeur sourcée de #3',
      },
    },
    operating_point: {
      crank_speed: {
        value: rpm,
        unit: 'rpm',
        source: 'hypothèse de démo, régime à confirmer dans #3',
      },
    },
    sampling: {
      revolutions: SHARED_GEOMETRY.revolutions,
      samples_per_revolution: SHARED_GEOMETRY.samplesPerRevolution,
    },
    notes:
      'Exemple du contrat runner #8 pour la démo #51 ; les valeurs définitives des deux cas appartiennent à #3.',
  }
}
