<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { COOPERATIVE_ACCOUNT_NUMBER, formatEuro, getBalances, type BalanceList } from '../../accounts'
import { errorText } from '../../api'
import { statusLabel, statusTagClass, todayIso } from '../../members'

// Stichtag im Format JJJJ-MM-TT, wie <input type="date"> und das Backend ihn erwarten.
const day = ref(todayIso())
const includeZero = ref(false)
const result = ref<BalanceList | null>(null) // null: noch nicht geladen
const error = ref('')

// Dieselbe Liste als Excel-Datei; ein einfacher Link wie auf der Seite „Reports“ (GET mit Session-Cookie).
const excelUrl = computed(
  () => `/api/reports/account-balances?reference_date=${day.value}&include_zero=${includeZero.value}`,
)

// Wie viele Konten zum Stichtag ausgeschieden sind, aber noch Anteile haben (Seite „Jahresende“).
const notBooked = computed(() => (result.value?.entries ?? []).filter((e) => e.exit_not_booked).length)

// Bei jedem neuen Stichtag oder Häkchen neu laden; `immediate` lädt auch beim Öffnen der Seite.
watch(
  [day, includeZero],
  async ([newDay, newIncludeZero]) => {
    error.value = ''
    if (!newDay) {
      return // Feld leer, z. B. während man tippt
    }
    try {
      result.value = await getBalances(newDay, newIncludeZero)
    } catch (e) {
      error.value = errorText(e)
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="card">
    <div class="card-header">Salden aller Konten</div>
    <div class="card-content">
      <div class="filters">
        <label>
          Stichtag
          <input v-model="day" type="date" />
        </label>
        <label class="checkbox">
          <input v-model="includeZero" type="checkbox" />
          auch Konten mit Saldo 0
        </label>
        <a v-if="day" :href="excelUrl" download>Als Excel herunterladen</a>
      </div>

      <div v-if="error" class="status-box error"><p>{{ error }}</p></div>

      <template v-if="result">
        <!-- Abstimmung: Was die Mitglieder zusammen gut haben, schuldet die Genossenschaft. -->
        <div v-if="result.balanced" class="status-box info">
          <p>
            Abgestimmt: Die Summe der Mitgliedskonten entspricht dem Genossenschaftskonto
            {{ COOPERATIVE_ACCOUNT_NUMBER }} ({{ formatEuro(-result.cooperative_balance) }}).
          </p>
        </div>
        <div v-else class="status-box error">
          <p>
            Nicht abgestimmt: Mitgliedskonten {{ formatEuro(result.total_balance) }}, Genossenschaftskonto
            {{ COOPERATIVE_ACCOUNT_NUMBER }} {{ formatEuro(result.cooperative_balance) }}.
          </p>
        </div>
        <div v-if="notBooked > 0" class="status-box warning">
          <p>
            {{ notBooked }} {{ notBooked === 1 ? 'Konto ist' : 'Konten sind' }} zum Stichtag ausgeschieden, aber das
            Ausscheiden ist noch nicht gebucht. Bitte auf der Seite
            <RouterLink :to="{ name: 'year-end' }">Jahresende</RouterLink> buchen.
          </p>
        </div>

        <p v-if="result.entries.length === 0">Keine Konten mit Saldo.</p>
        <div v-else class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Nr.</th>
                <th>Name</th>
                <th>Status</th>
                <th class="col-number">Anteile</th>
                <th class="col-number">Saldo</th>
                <th class="col-number">Geschäfts&shy;guthaben</th>
                <th class="col-number">Anspruch</th>
                <th>Hinweis</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in result.entries" :key="entry.account_number">
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
                <td class="col-number">{{ entry.shares }}</td>
                <td class="col-number">
                  <RouterLink :to="{ name: 'account', params: { number: entry.account_number } }">
                    {{ formatEuro(entry.balance) }}
                  </RouterLink>
                </td>
                <td class="col-number">{{ formatEuro(entry.share_capital) }}</td>
                <td class="col-number">{{ entry.claim === 0 ? '' : formatEuro(entry.claim) }}</td>
                <td>{{ entry.exit_not_booked ? 'Ausscheiden nicht gebucht' : '' }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <td></td>
                <td colspan="2"><strong>Summe</strong></td>
                <td class="col-number"><strong>{{ result.total_shares }}</strong></td>
                <td class="col-number"><strong>{{ formatEuro(result.total_balance) }}</strong></td>
                <td class="col-number"><strong>{{ formatEuro(result.total_share_capital) }}</strong></td>
                <td class="col-number"><strong>{{ formatEuro(result.total_claim) }}</strong></td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem 2rem;
  align-items: end;
  margin-bottom: 1rem;
}

.filters label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.filters label.checkbox {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}
</style>
