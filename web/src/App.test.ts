import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App.vue'

const capabilities = {
  api_version: '1',
  application_version: '0.1.0',
  stage: 'foundation',
  simulation_available: false,
  viewer_3d_available: false,
  models: [],
}

afterEach(() => vi.unstubAllGlobals())

describe('local workspace connection', () => {
  it('reads the API response and keeps unavailable simulations explicit', async () => {
    const request = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(capabilities)))
    vi.stubGlobal('fetch', request)
    const wrapper = mount(App)
    await flushPromises()
    expect(request.mock.calls[0]?.[0]).toBe('/api/v1/capabilities')
    expect(wrapper.get('[role="status"]').text()).toContain(
      'Connected · version 0.1.0',
    )
    expect(wrapper.text()).toContain(
      'No engine simulation model is available yet.',
    )
    expect(wrapper.find('canvas').exists()).toBe(false)
    wrapper.unmount()
  })

  it('recovers after a failed connection without reloading the page', async () => {
    const request = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Offline'))
      .mockResolvedValueOnce(new Response(JSON.stringify(capabilities)))
    vi.stubGlobal('fetch', request)
    const wrapper = mount(App)
    await flushPromises()
    expect(wrapper.get('button').text()).toBe('Retry connection')
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toContain('Connected')
    wrapper.unmount()
  })

  it.each(['{"api_version":"future"}', 'not-json'])(
    'explains incompatible response %s without asking to start a running service',
    async (body) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body)))
      const wrapper = mount(App)
      await flushPromises()
      const status = wrapper.get('[role="status"]').text()
      expect(status).toContain('matching frontend/backend versions')
      expect(status).not.toContain('Start it')
      wrapper.unmount()
    },
  )

  it('reports an HTTP error with a relevant recovery action', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('', { status: 503 })),
    )
    const wrapper = mount(App)
    await flushPromises()
    const status = wrapper.get('[role="status"]').text()
    expect(status).toContain('HTTP 503')
    expect(status).toContain('Check its output')
    expect(status).not.toContain('Start it')
    wrapper.unmount()
  })

  it('accepts new capability values without tying the client to the foundation stage', async () => {
    const future = {
      ...capabilities,
      stage: 'prototype',
      simulation_available: true,
      models: ['example-model'],
      additional_capability: true,
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify(future))),
    )
    const wrapper = mount(App)
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toContain('Connected')
    expect(wrapper.text()).toContain(
      'The local service reports simulation support.',
    )
    wrapper.unmount()
  })
})
