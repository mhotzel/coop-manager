<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { errorText } from '../../api'
import { getHandbook } from '../../help'

const html = ref('')
const error = ref('')

onMounted(async () => {
  try {
    html.value = await getHandbook()
  } catch (e) {
    error.value = errorText(e)
  }
})

// Klicks auf die Links im Inhaltsverzeichnis („#k-4-7“) selbst behandeln: zum Kapitel scrollen,
// ohne dass Vue Router die Adresse als neue Seite versteht.
function onClick(event: MouseEvent): void {
  const link = (event.target as HTMLElement).closest('a')
  const target = link?.getAttribute('href')
  if (!target?.startsWith('#')) {
    return
  }
  event.preventDefault()
  document.getElementById(target.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<template>
  <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
  <!-- v-html setzt fertiges HTML ein. Unbedenklich, weil es aus unserem eigenen Generator
       (Dokumentation/handbuch/handbuch.js) stammt und keine Eingaben von Benutzern enthält. -->
  <article v-else class="card handbook" @click="onClick" v-html="html"></article>
</template>

<style scoped>
/* :deep() — scoped-Stile gelten sonst nicht für Inhalt aus v-html. */
/* Braun aus dem Logo für Überschriften und Knöpfe im Text, Grün aus der App für Linien und Kästen. */
.handbook {
  --handbook-brown: #544741;
  padding: 1rem 1.5rem 2rem;
  line-height: 1.5;
  max-width: 60rem;
}

.handbook :deep(h1) {
  color: var(--handbook-brown);
  border-bottom: 2px solid var(--primary-color);
  padding-bottom: 0.2rem;
  margin-top: 2rem;
}

.handbook :deep(h2),
.handbook :deep(h3) {
  color: var(--handbook-brown);
  margin-top: 1.4rem;
}

.handbook :deep(h1),
.handbook :deep(h2),
.handbook :deep(h3) {
  scroll-margin-top: 1rem;
}

.handbook :deep(.ui) {
  color: var(--handbook-brown);
}

.handbook :deep(.note) {
  background: var(--primary-light-hover);
  border-left: 4px solid var(--primary-color);
  padding: 0.5rem 0.8rem;
  margin: 0.8rem 0;
}

.handbook :deep(.note > strong:first-child) {
  color: var(--handbook-brown);
}

.handbook :deep(ol.steps li::marker) {
  font-weight: 700;
  color: var(--handbook-brown);
}

.handbook :deep(table) {
  width: 100%;
  margin: 0.6rem 0 1rem;
}

.handbook :deep(.toc) {
  background: var(--bg-card-header);
  padding: 0.5rem 1rem;
  border-radius: 4px;
}

.handbook :deep(.toc ul) {
  list-style: none;
  padding-left: 0;
  columns: 2 18rem;
}

.handbook :deep(.toc .toc-1) {
  font-weight: 700;
  margin-top: 0.4rem;
}

.handbook :deep(.toc .toc-2) {
  padding-left: 1rem;
}
</style>
