<script setup lang="ts">
import { computed, ref } from 'vue'

import { todayIso } from '../../members'

// Stichtag im Format JJJJ-MM-TT, so wie <input type="date"> und das Backend ihn erwarten.
const referenceDate = ref(todayIso())

// Die Liste ist ein einfacher Link: Der Browser lädt die Datei mit dem Session-Cookie herunter.
// Ein GET braucht kein CSRF-Token, deshalb geht es ohne api().
const gengUrl = computed(() => `/api/reports/members-geng?reference_date=${referenceDate.value}`)
</script>

<template>
  <div class="card">
    <div class="card-header">Reports</div>
    <div class="card-content">
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
      </ul>
    </div>
  </div>
</template>

<style scoped>
.reference-date {
  max-width: 12rem;
}

.report-list li {
  margin-bottom: 0.5rem;
}
</style>
