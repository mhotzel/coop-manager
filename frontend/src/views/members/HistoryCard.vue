<script setup lang="ts">
import { ref, watch } from 'vue'

import { errorText } from '../../api'
import { formatDate, formatDateTime, getHistory, type HistoryEntry, type MemberDetail } from '../../members'

// Das ganze Mitglied statt nur der ID: Nach jedem Speichern auf der Seite kommt ein neues Objekt,
// daran erkennt die Karte, dass der Verlauf neu geladen werden muss.
const props = defineProps<{ member: MemberDetail }>()

const open = ref(false) // zugeklappt: Geladen wird erst beim Aufklappen
const entries = ref<HistoryEntry[] | null>(null)
const error = ref('')

async function load(): Promise<void> {
  error.value = ''
  try {
    entries.value = await getHistory(props.member.id)
  } catch (e) {
    error.value = errorText(e)
  }
}

async function toggle(): Promise<void> {
  open.value = !open.value
  if (open.value) {
    await load()
  }
}

// Gültig ab: aus dem Altsystem bzw. das Antragsdatum, sonst der Tag des Speicherns.
function validFrom(entry: HistoryEntry): string {
  return entry.valid_from ? formatDate(entry.valid_from) : formatDateTime(entry.recorded_at).slice(0, 10)
}

// Ist der Verlauf offen und wurde auf der Seite etwas gespeichert, gleich neu laden.
watch(
  () => props.member,
  async () => {
    if (open.value) {
      await load()
    }
  },
)
</script>

<template>
  <div class="card">
    <div class="card-header">Verlauf</div>
    <div class="card-content">
      <p class="hint">Alle Änderungen an den Personendaten, die neueste zuerst; zuunterst der Stand beim Antrag.</p>
      <div class="button-row">
        <button type="button" class="btn btn-outline" @click="toggle">
          {{ open ? 'Verlauf ausblenden' : 'Verlauf anzeigen' }}
        </button>
      </div>

      <template v-if="open">
        <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
        <div v-else-if="entries" class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Gültig ab</th>
                <th>Gespeichert</th>
                <th>Von</th>
                <th>Was</th>
                <th>Vorher</th>
                <th>Nachher</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(entry, index) in entries" :key="index">
                <td>{{ validFrom(entry) }}</td>
                <td>{{ formatDateTime(entry.recorded_at) }}</td>
                <td>{{ entry.actor }}</td>
                <td>{{ entry.part }}</td>
                <td class="text">{{ entry.before }}</td>
                <td class="text">{{ entry.after }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.hint {
  color: var(--text-label);
}

/* Mehrzeilige Hinweise bleiben mehrzeilig. */
.text {
  white-space: pre-line;
}
</style>
