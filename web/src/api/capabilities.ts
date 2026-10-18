export interface Capabilities {
  api_version: '1'
  application_version: string
  stage: string
  simulation_available: boolean
  viewer_3d_available: boolean
  models: string[]
}

export async function getCapabilities(): Promise<Capabilities> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 5000)
  try {
    const response = await fetch('/api/v1/capabilities', {
      signal: controller.signal,
    })
    if (!response.ok)
      throw new Error(`The local service returned HTTP ${response.status}.`)
    const data: unknown = await response.json()
    if (
      typeof data !== 'object' ||
      data === null ||
      !('api_version' in data) ||
      data.api_version !== '1' ||
      !('application_version' in data) ||
      typeof data.application_version !== 'string' ||
      !('stage' in data) ||
      typeof data.stage !== 'string' ||
      !('models' in data) ||
      !Array.isArray(data.models) ||
      !data.models.every((model) => typeof model === 'string') ||
      !('simulation_available' in data) ||
      typeof data.simulation_available !== 'boolean' ||
      !('viewer_3d_available' in data) ||
      typeof data.viewer_3d_available !== 'boolean'
    ) {
      throw new Error(
        'The local service returned an incompatible capability response.',
      )
    }
    return data as Capabilities
  } finally {
    clearTimeout(timeout)
  }
}
