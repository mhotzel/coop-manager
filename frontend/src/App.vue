<script setup lang="ts">
import { onMounted, ref } from 'vue'

// Antwort von GET /healthz; die Form muss zu dem passen, was das Backend liefert.
interface Health {
  status: string
}

// ref() macht den Wert reaktiv: Ändert er sich, zeichnet Vue die Anzeige neu.
const backendStatus = ref<string>('wird geprüft …')

onMounted(async () => {
  try {
    const response = await fetch('/healthz')
    const health: Health = await response.json()
    backendStatus.value = health.status
  } catch {
    backendStatus.value = 'nicht erreichbar'
  }
})
</script>

<template>
  <h1>coop-manager</h1>
  <p>Backend: {{ backendStatus }}</p>
</template>
