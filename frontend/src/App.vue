<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

import logoUrl from './assets/img/dlslogo.png'

// Antwort von GET /healthz; die Form muss zu dem passen, was das Backend liefert.
interface Health {
  status: string
}

// Ein Eintrag im Menü. Ein Ziel (Route) kommt dazu, sobald es Seiten gibt.
interface MenuEntry {
  title: string
}

const menuEntries: MenuEntry[] = [
  { title: 'Mitglieder' },
  { title: 'Konten' },
  { title: 'Reports' },
  { title: 'Benutzer' },
]

// ref() macht den Wert reaktiv: Ändert er sich, zeichnet Vue die Anzeige neu.
const backendStatus = ref<string>('wird geprüft …')

// Menü auf breiten Bildschirmen immer offen (Seitenleiste), auf dem Handy zu (Hamburger).
// Ersetzt layout.js aus purchase-prices. Die Grenze 769px passt zur Media-Query in style.css.
const wideScreen = window.matchMedia('(min-width: 769px)')
const menuOpen = ref<boolean>(wideScreen.matches)

function syncMenu(): void {
  menuOpen.value = wideScreen.matches
}

onMounted(async () => {
  wideScreen.addEventListener('change', syncMenu)
  try {
    const response = await fetch('/healthz')
    const health: Health = await response.json()
    backendStatus.value = health.status
  } catch {
    backendStatus.value = 'nicht erreichbar'
  }
})

// Aufräumen, wenn die Komponente verschwindet, sonst bliebe der Listener hängen.
onUnmounted(() => {
  wideScreen.removeEventListener('change', syncMenu)
})
</script>

<template>
  <header>
    <div class="logo-container">
      <img :src="logoUrl" alt="Unser Dorfladen Schlichten" />
    </div>
    <div class="header-title">
      <p>Mitgliederverwaltung</p>
    </div>
  </header>
  <div class="action-bar">
    <div class="action-left"></div>
    <div class="action-right"></div>
  </div>
  <div id="content-wrapper">
    <nav class="nav">
      <details class="mobile-menu" :open="menuOpen">
        <summary>☰ Menü</summary>
        <ul>
          <!-- Platzhalter ohne Ziel; der Vue Router kommt mit der ersten Seite (Schritt 3). -->
          <li v-for="entry in menuEntries" :key="entry.title">
            <a>{{ entry.title }}</a>
          </li>
        </ul>
      </details>
    </nav>
    <main>
      <div class="card">
        <div class="card-header">Willkommen</div>
        <div class="card-content">
          <p>Hier entsteht die Mitgliederverwaltung der Unser Dorfladen Schlichten eG.</p>
        </div>
      </div>
    </main>
  </div>
  <footer>
    <p>Backend: {{ backendStatus }}</p>
  </footer>
</template>
