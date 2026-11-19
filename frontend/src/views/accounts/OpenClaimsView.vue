<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { formatEuro, getClaims, type ClaimEntry } from '../../accounts'
import { errorText } from '../../api'
import { formatDate, statusLabel, statusTagClass } from '../../members'

const entries = ref<ClaimEntry[] | null>(null) // null: noch nicht geladen
const error = ref('')

// Was die Genossenschaft insgesamt noch schuldet. reduce: addiert alle Ansprüche, beginnend bei 0.
const total = computed(() => (entries.value ?? []).reduce((sum, entry) => sum + entry.claim, 0))

onMounted(async () => {
  try {
    entries.value = await getClaims()
  } catch (e) {
    error.value = errorText(e)
  }
})
</script>

<template>
  <div class="card">
    <div class="card-header">Offene Ansprüche</div>
    <div class="card-content">
      <div v-if="error" class="status-box error"><p>{{ error }}</p></div>

      <template v-if="entries">
        <p v-if="entries.length === 0">Keine offenen Ansprüche.</p>
        <template v-else>
          <!-- Die Verjährung (Satzung 2.7) überwacht die App nicht; die ältesten stehen oben. -->
          <p class="hint">Sortiert nach Ausscheiden, das älteste zuerst. Auszahlen über das Konto.</p>
          <div class="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Nr.</th>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Ausgeschieden zum</th>
                  <th class="col-number">Offener Anspruch</th>
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
                  <td>
                    <span v-if="entry.status !== null" class="status-tag" :class="statusTagClass(entry.status)">
                      {{ statusLabel(entry.status) }}
                    </span>
                  </td>
                  <td>{{ formatDate(entry.exit_date) }}</td>
                  <td class="col-number">
                    <RouterLink :to="{ name: 'account', params: { number: entry.account_number } }">
                      {{ formatEuro(entry.claim) }}
                    </RouterLink>
                  </td>
                </tr>
              </tbody>
              <tfoot>
                <tr>
                  <td></td>
                  <td colspan="3"><strong>Summe</strong></td>
                  <td class="col-number"><strong>{{ formatEuro(total) }}</strong></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<style scoped>
.hint {
  color: var(--text-label);
}
</style>
