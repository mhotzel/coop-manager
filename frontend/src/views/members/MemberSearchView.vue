<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { errorText } from '../../api'
import { ACCOUNTING, currentUser } from '../../auth'
import { lastQuery, searchMembers, SEARCH_LIMIT, statusLabel, statusTagClass, type MemberRow } from '../../members'

// null heißt: Es wurde noch nicht gesucht (anders als [] = gesucht, nichts gefunden).
const rows = ref<MemberRow[] | null>(null)
const error = ref('')
const busy = ref(false)
// Neue Anträge erfasst nur die Buchhaltung, nicht „Buchhaltung lesend“.
const canWrite = computed(() => currentUser.value?.role === ACCOUNTING)

async function search(): Promise<void> {
  error.value = ''
  busy.value = true
  try {
    rows.value = await searchMembers(lastQuery.value)
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}

// Beim Öffnen gleich suchen: mit dem letzten Begriff oder leer (dann die ersten Mitglieder).
onMounted(search)
</script>

<template>
  <div class="card">
    <div class="card-header">Mitglieder</div>
    <div class="card-content">
      <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
      <form class="search-form" @submit.prevent="search">
        <input
          v-model="lastQuery"
          type="search"
          aria-label="Suchbegriff"
          placeholder="Name, Ort, Straße, Nummer oder PLZ"
          autocomplete="off"
          autofocus
        />
        <button type="submit" class="btn btn-primary" :disabled="busy">Suchen</button>
      </form>
      <div v-if="canWrite" class="button-row">
        <RouterLink :to="{ name: 'member-new' }" class="btn btn-secondary">Neuer Antrag</RouterLink>
      </div>

      <template v-if="rows !== null">
        <div v-if="rows.length === 0" class="status-box info"><p>Keine Mitglieder gefunden.</p></div>
        <div v-else class="table-wrapper">
          <div v-if="rows.length >= SEARCH_LIMIT" class="status-box warning">
            <p>Es werden höchstens {{ SEARCH_LIMIT }} Treffer angezeigt, bitte die Suche verfeinern.</p>
          </div>
          <table>
            <thead>
              <tr>
                <th>Nr.</th>
                <th>Name</th>
                <th>Anschrift</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.id">
                <td>{{ row.member_number }}</td>
                <td>
                  <RouterLink :to="{ name: 'member-detail', params: { id: row.id } }">{{ row.list_name }}</RouterLink>
                </td>
                <td>{{ row.street }}, {{ row.postal_code }} {{ row.city }}</td>
                <td>
                  <span v-if="row.status !== null" class="status-tag" :class="statusTagClass(row.status)">
                    {{ statusLabel(row.status) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* Suchfeld und Knopf nebeneinander; das Feld nimmt den restlichen Platz. */
.search-form {
  display: flex;
  gap: 5px;
  margin-bottom: 0.8rem;
}

.search-form input {
  flex: 1;
}
</style>
