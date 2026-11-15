<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import logoUrl from './assets/img/dlslogo.png'
import { currentUser, logout } from './auth'

const router = useRouter()

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

async function signOut(): Promise<void> {
  await logout()
  await router.push({ name: 'login' })
}

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
    <div class="action-left">
      <span v-if="currentUser" class="badge">{{ currentUser.full_name }}</span>
    </div>
    <div class="action-right">
      <button v-if="currentUser" type="button" class="btn btn-primary" @click="signOut">Abmelden</button>
    </div>
  </div>
  <div id="content-wrapper">
    <!-- Das Menü gibt es erst nach der Anmeldung. -->
    <nav v-if="currentUser" class="nav">
      <details class="mobile-menu" :open="menuOpen">
        <summary>☰ Menü</summary>
        <ul>
          <!-- Platzhalter ohne Ziel; die Seiten dazu entstehen in den nächsten Schritten. -->
          <li v-for="entry in menuEntries" :key="entry.title">
            <a>{{ entry.title }}</a>
          </li>
        </ul>
      </details>
    </nav>
    <main>
      <!-- Hier setzt der Router die Seite zur aktuellen Adresse ein, z. B. LoginView. -->
      <RouterView />
    </main>
  </div>
  <footer>
    <p>Backend: {{ backendStatus }}</p>
  </footer>
</template>
