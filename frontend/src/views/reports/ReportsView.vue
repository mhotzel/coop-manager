<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { YEAR_MAX, YEAR_MIN } from '../../accounts'
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

// Geschäftsjahr für die Auswertung der Vorgänge. Vorbelegt mit dem Vorjahr, denn ausgewertet wird
// meist ein abgeschlossenes Jahr. v-model.number macht aus dem eingegebenen Text eine Zahl.
const fiscalYear = ref(new Date().getFullYear() - 1)
// Leeres Feld oder halb getipptes Jahr: kein Link, wie beim leeren Stichtag.
const isValidYear = computed(
  () => Number.isInteger(fiscalYear.value) && fiscalYear.value >= YEAR_MIN && fiscalYear.value <= YEAR_MAX,
)
const eventsUrl = computed(() => `/api/reports/fiscal-year-events?fiscal_year=${fiscalYear.value}`)

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

      <h3>Auswertung eines Geschäftsjahres</h3>
      <div class="form-group fiscal-year">
        <label for="reports-fiscal-year">Geschäftsjahr</label>
        <input id="reports-fiscal-year" v-model.number="fiscalYear" type="number" :min="YEAR_MIN" :max="YEAR_MAX" />
      </div>

      <ul class="report-list">
        <li>
          <a v-if="isValidYear" :href="eventsUrl" download>Vorgänge im Geschäftsjahr</a>
          <span v-else>Vorgänge im Geschäftsjahr</span>
          – Eintritte, Kündigungen, Todesfälle, Ausschlüsse und alle Buchungen des Jahres, zum Filtern in
          Excel (ohne Stornos)
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.reference-date,
.fiscal-year {
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
