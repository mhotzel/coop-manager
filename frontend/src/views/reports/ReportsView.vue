<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { errorText } from '../../api'
import { todayIso } from '../../members'
import { getReportWarnings } from '../../reports'

// Stichtag im Format JJJJ-MM-TT, so wie <input type="date"> und das Backend ihn erwarten.
const referenceDate = ref(todayIso())

// Die Liste ist ein einfacher Link: Der Browser lädt die Datei mit dem Session-Cookie herunter.
// Ein GET braucht kein CSRF-Token, deshalb geht es ohne api().
const gengUrl = computed(() => `/api/reports/members-geng?reference_date=${referenceDate.value}`)
const assemblyUrl = computed(() => `/api/reports/members-assembly?reference_date=${referenceDate.value}`)
const mailingUrl = computed(() => `/api/reports/members-mailing?reference_date=${referenceDate.value}`)

const warnings = ref<string[]>([])
const error = ref('')

// Bei jedem neuen Stichtag nachsehen, ob die Listen unter Vorbehalt stehen.
watch(
  referenceDate,
  async (day) => {
    warnings.value = []
    error.value = ''
    if (!day) {
      return // Feld leer, z. B. während man tippt
    }
    try {
      warnings.value = await getReportWarnings(day)
    } catch (e) {
      error.value = errorText(e)
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="card">
    <div class="card-header">Reports</div>
    <div class="card-content">
      <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
      <div v-for="warning in warnings" :key="warning" class="status-box warning"><p>{{ warning }}</p></div>

      <div class="form-group reference-date">
        <label for="reports-reference-date">Stichtag</label>
        <input id="reports-reference-date" v-model="referenceDate" type="date" required />
      </div>

      <ul class="report-list">
        <li>
          <!-- Ohne Stichtag (leeres Feld) gibt es keinen Link. -->
          <a v-if="referenceDate" :href="gengUrl" download>Mitgliederliste nach GenG</a>
          <span v-else>Mitgliederliste nach GenG</span>
          – Nr., Name, Anschrift, Eintritt, Betrag und Anteile (Excel)
        </li>
        <li>
          <a v-if="referenceDate" :href="assemblyUrl" download>Liste zur Generalversammlung</a>
          <span v-else>Liste zur Generalversammlung</span>
          – stimmberechtigte Mitglieder nach Namen, mit Spalten für Vertretung und Unterschrift (Stichtag =
          Tag der Versammlung)
        </li>
        <li>
          <a v-if="referenceDate" :href="mailingUrl" download>Seriendruck-Liste</a>
          <span v-else>Seriendruck-Liste</span>
          – Adresszeilen und Briefanrede für die Einladung, ohne „keine Post“ (Feldnamen wie im Altsystem)
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.reference-date {
  max-width: 12rem;
}

/* Eine Liste ohne Aufzählungspunkte und ohne den Einzug, den der Browser einer <ul> gibt. */
.report-list {
  list-style: none;
  padding-left: 0;
}

.report-list li {
  margin-bottom: 0.5rem;
}
</style>
