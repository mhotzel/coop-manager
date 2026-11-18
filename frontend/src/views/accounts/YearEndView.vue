<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import {
  exitReasonsLabel,
  formatEuro,
  getExits,
  postExits,
  YEAR_MAX,
  YEAR_MIN,
  type ExitEntry,
} from '../../accounts'
import { errorText } from '../../api'
import { ACCOUNTING, currentUser } from '../../auth'

// Vorbelegt mit dem Vorjahr: Gebucht wird nach dem 31.12., also im Januar für das alte Jahr.
const currentYear = new Date().getFullYear()
const year = ref(currentYear - 1)

const entries = ref<ExitEntry[] | null>(null) // null: noch nicht geladen
const error = ref('')
const message = ref('')
const busy = ref(false)

const isValidYear = computed(() => Number.isInteger(year.value) && year.value >= YEAR_MIN && year.value <= YEAR_MAX)
const openCount = computed(() => entries.value?.filter((e) => !e.booked).length ?? 0)
// Buchen nur für abgeschlossene Jahre (siehe Plan); verbindlich prüft das Backend.
const isCompleted = computed(() => year.value < currentYear)
const canPost = computed(
  () => currentUser.value?.role === ACCOUNTING && isCompleted.value && openCount.value > 0 && !busy.value,
)

async function load(): Promise<void> {
  error.value = ''
  entries.value = null
  if (!isValidYear.value) {
    return // z. B. während man das Jahr eintippt
  }
  try {
    entries.value = await getExits(year.value)
  } catch (e) {
    error.value = errorText(e)
  }
}

// Beim Öffnen und bei jeder Änderung des Jahres neu laden. Die Meldung gehört zum alten Jahr.
watch(year, () => {
  message.value = ''
  void load()
}, { immediate: true })

async function post(): Promise<void> {
  const count = openCount.value
  if (!confirm(`${count} Ausscheiden zum 31.12.${year.value} buchen?`)) {
    return
  }
  error.value = ''
  message.value = ''
  busy.value = true
  try {
    entries.value = await postExits(year.value)
    message.value = `${count} Ausscheiden zum 31.12.${year.value} gebucht.`
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="card">
    <div class="card-header">Ausscheiden zum Jahresende</div>
    <div class="card-content">
      <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
      <div v-if="message" class="status-box info"><p>{{ message }}</p></div>

      <div class="form-group year">
        <label for="year-end-year">Ausscheiden zum 31.12.</label>
        <input id="year-end-year" v-model.number="year" type="number" :min="YEAR_MIN" :max="YEAR_MAX" />
      </div>

      <template v-if="entries">
        <p v-if="entries.length === 0">Zum 31.12.{{ year }} scheidet niemand aus.</p>
        <div v-else class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Nr.</th>
                <th>Name</th>
                <th>Grund</th>
                <th class="col-number">Anteile</th>
                <th class="col-number">Anspruch</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in entries" :key="entry.account_number">
                <td>
                  <RouterLink :to="{ name: 'member-detail', params: { id: entry.member_id } }">
                    {{ entry.member_number }}
                  </RouterLink>
                </td>
                <td>{{ entry.name }}</td>
                <td>{{ exitReasonsLabel(entry.reasons) }}</td>
                <!-- Volles Ausscheiden: alle Anteile des Kontos. -->
                <td class="col-number">{{ entry.full ? `alle (${entry.shares})` : entry.shares }}</td>
                <!-- Zum Konto, z. B. um eine falsche Buchung zu stornieren. -->
                <td class="col-number">
                  <RouterLink :to="{ name: 'account', params: { number: entry.account_number } }">
                    {{ formatEuro(entry.balance) }}
                  </RouterLink>
                </td>
                <td>
                  <span class="status-tag" :class="entry.booked ? 'success' : 'warning'">
                    {{ entry.booked ? 'gebucht' : 'offen' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-if="!isCompleted && entries.length > 0" class="hint">
          Vorschau: Gebucht werden kann erst nach dem 31.12.{{ year }}.
        </p>
        <div v-if="canPost" class="button-row">
          <button type="button" class="btn btn-primary" @click="post">Ausscheiden buchen ({{ openCount }})</button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.year {
  max-width: 12rem;
}

.hint {
  color: var(--text-label);
}
</style>
