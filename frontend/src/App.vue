<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import logoUrl from './assets/img/dlslogo.png'
import { ACCOUNTING, ACCOUNTING_READONLY, ADMIN, currentUser, logout } from './auth'

const router = useRouter()

// Antwort von GET /healthz; die Form muss zu dem passen, was das Backend liefert.
interface Health {
  status: string
}

// Ein Eintrag im Menü: Ziel (Name der Route) und die Rollen, die ihn sehen.
// Einträge ohne Ziel sind Platzhalter für Seiten, die erst noch entstehen.
interface MenuEntry {
  title: string
  to?: string
  roles: string[]
}

const FACHLICH = [ACCOUNTING, ACCOUNTING_READONLY]

const menuEntries: MenuEntry[] = [
  { title: 'Mitglieder', roles: FACHLICH },
  { title: 'Konten', roles: FACHLICH },
  { title: 'Reports', roles: FACHLICH },
  { title: 'Benutzer', to: 'users', roles: [ADMIN] },
]

// Nur die Einträge, die zur Rolle des angemeldeten Benutzers passen.
const visibleEntries = computed(() => {
  const role = currentUser.value?.role
  return menuEntries.filter((entry) => role !== undefined && entry.roles.includes(role))
})

// ref() macht den Wert reaktiv: Ändert er sich, zeichnet Vue die Anzeige neu.
const backendStatus = ref<string>('wird geprüft …')

// Menü auf breiten Bildschirmen immer offen (Seitenleiste), auf dem Handy zu (Hamburger).
// Ersetzt layout.js aus purchase-prices. Die Grenze 769px passt zur Media-Query in style.css.
const wideScreen = window.matchMedia('(min-width: 769px)')
const menuOpen = ref<boolean>(wideScreen.matches)

function syncMenu(): void {
  menuOpen.value = wideScreen.matches
}

// Auf dem Handy das Menü nach jedem Seitenwechsel wieder zuklappen.
router.afterEach(syncMenu)

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
      <template v-if="currentUser">
        <RouterLink :to="{ name: 'password' }" class="btn btn-secondary">Kennwort ändern</RouterLink>
        <button type="button" class="btn btn-primary" @click="signOut">Abmelden</button>
      </template>
    </div>
  </div>
  <div id="content-wrapper">
    <!-- Das Menü gibt es erst nach der Anmeldung. -->
    <nav v-if="currentUser" class="nav">
      <!-- @toggle: Klappt man das Menü per Klick auf, merkt sich menuOpen das ebenfalls. -->
      <details
        class="mobile-menu"
        :open="menuOpen"
        @toggle="menuOpen = ($event.target as HTMLDetailsElement).open"
      >
        <summary>☰ Menü</summary>
        <ul>
          <li v-for="entry in visibleEntries" :key="entry.title">
            <!-- active-class: style.css markiert den aktiven Eintrag mit der Klasse „active“. -->
            <RouterLink v-if="entry.to" :to="{ name: entry.to }" active-class="active">{{ entry.title }}</RouterLink>
            <a v-else>{{ entry.title }}</a>
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
