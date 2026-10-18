<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getCapabilities, type Capabilities } from './api/capabilities'

const capabilities = ref<Capabilities | null>(null)
const connecting = ref(false)
const error = ref('')

async function connect() {
  connecting.value = true
  error.value = ''
  capabilities.value = null
  try {
    capabilities.value = await getCapabilities()
  } catch {
    error.value =
      'Cannot connect to the local service. Start it, then retry the connection.'
  } finally {
    connecting.value = false
  }
}

onMounted(() => void connect())
</script>

<template>
  <main>
    <h1>V-Twin</h1>
    <p>Engine simulation workspace</p>

    <section aria-labelledby="connection-heading">
      <h2 id="connection-heading">Local service</h2>
      <div role="status" aria-live="polite">
        <p v-if="connecting">Connecting…</p>
        <p v-else-if="error">{{ error }}</p>
        <p v-else-if="capabilities">
          Connected · version {{ capabilities.application_version }}
        </p>
      </div>
      <button :disabled="connecting" type="button" @click="connect">
        {{ error ? 'Retry connection' : 'Check connection' }}
      </button>
    </section>

    <section aria-labelledby="workspace-heading">
      <h2 id="workspace-heading">A foundation for the first model</h2>
      <p v-if="capabilities?.simulation_available">
        The local service reports simulation support. This startup screen checks
        only the connection.
      </p>
      <p v-else>
        No engine simulation model is available yet. This development workspace
        checks the local connection; simulation controls, graphs and the
        optional 3D view will follow.
      </p>
    </section>
  </main>
</template>

<style>
html {
  color-scheme: light;
  font-family: system-ui, sans-serif;
  line-height: 1.6;
  color: #172328;
  background: #f7f8f6;
}

body {
  margin: 0;
}

main {
  max-width: 68ch;
  padding: 2rem 1.25rem;
  margin: 0 auto;
}

section {
  margin-block-start: 2rem;
}

button {
  font: inherit;
  padding: 0.45rem 0.8rem;
  cursor: pointer;
}

button:disabled {
  cursor: wait;
}

:focus-visible {
  outline: 3px solid #19694c;
  outline-offset: 3px;
}

::selection {
  background: #c4dfd1;
}
</style>
