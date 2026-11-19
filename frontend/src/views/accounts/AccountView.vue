<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import {
  bookingKindLabel,
  COOPERATIVE_ACCOUNT_NUMBER,
  counterAccount,
  formatEuro,
  getAccount,
  reverse,
  signedFor,
  type AccountView,
  type Booking,
} from '../../accounts'
import { errorText } from '../../api'
import { ACCOUNTING, currentUser } from '../../auth'
import { formatDate, getMember, NATURAL_PERSON, statusLabel, statusTagClass, type MemberDetail } from '../../members'
import BookingForm from './BookingForm.vue'

// Der Router übergibt :number aus dem Pfad als Prop, als Text (siehe props: true in router.ts).
const props = defineProps<{ number: string }>()

const account = ref<AccountView | null>(null)
const member = ref<MemberDetail | null>(null) // Inhaber; beim Genossenschaftskonto null
const error = ref('')
const warning = ref('') // Warnung nach einem Storno, z. B. „Geldeingang zurückgenommen“
const hideReversed = ref(false) // Filter „Stornierte ausblenden“

const isCooperative = computed(() => account.value?.number === COOPERATIVE_ACCOUNT_NUMBER)

// Die Buchungsmaske nur für die Buchhaltung, nur an Mitgliedskonten und nur mit Anteilspreis.
// Das ist Komfort; verbindlich prüft das Backend.
const canBook = computed(
  () =>
    currentUser.value?.role === ACCOUNTING &&
    account.value !== null &&
    !isCooperative.value &&
    account.value.share_price !== null,
)

// Stornieren darf die Buchhaltung auf jedem Konto, auch auf dem Genossenschaftskonto.
const canReverse = computed(() => currentUser.value?.role === ACCOUNTING)

// Zu jeder stornierten Buchung ihr Storno: Schlüssel ist die ID des Originals. Original und
// Storno stehen immer auf demselben Konto, deshalb reicht die Liste dieses Kontos.
const reversalOf = computed(() => {
  const map = new Map<string, Booking>()
  for (const booking of account.value?.bookings ?? []) {
    if (booking.reverses !== null) {
      map.set(booking.reverses, booking)
    }
  }
  return map
})

// Gehört die Buchung zu einem Paar aus Original und Storno?
function isReversedPair(booking: Booking): boolean {
  return booking.reverses !== null || reversalOf.value.has(booking.id)
}

// Die Buchungen in der Tabelle; mit Filter ohne die Paare aus Original und Storno.
const visibleBookings = computed(() => {
  const all = account.value?.bookings ?? []
  return hideReversed.value ? all.filter((b) => !isReversedPair(b)) : all
})

// Storno: Grund abfragen, buchen, Ansicht aktualisieren. Abbrechen oder leerer Grund: nichts tun.
async function onReverse(booking: Booking): Promise<void> {
  const reason = window.prompt(`Grund für das Storno von „${booking.text}“:`)
  if (reason === null || reason.trim() === '') {
    return
  }
  error.value = ''
  warning.value = ''
  try {
    const response = await reverse({ booking_id: booking.id, reason })
    warning.value = response.warning ?? ''
    if (response.account.number === account.value?.number) {
      await onBooked(response.account)
    } else {
      // Auf dem Genossenschaftskonto: Der Server antwortet mit dem Mitgliedskonto, also laden
      // wir das angezeigte Konto selbst neu.
      account.value = await getAccount(account.value!.number)
    }
  } catch (e) {
    error.value = errorText(e)
  }
}

// Die Maske meldet das Konto nach der Buchung. Den Inhaber laden wir neu, denn eine Buchung kann
// seinen Status ändern (Geldeingang, Eintritt).
async function onBooked(updated: AccountView): Promise<void> {
  account.value = updated
  if (updated.member_id !== null) {
    try {
      member.value = await getMember(updated.member_id)
    } catch (e) {
      error.value = errorText(e)
    }
  }
}

const ownerName = computed(() => {
  const m = member.value
  if (m === null) {
    return ''
  }
  return m.person_type === NATURAL_PERSON ? `${m.name.first_names} ${m.name.last_name}` : m.name.company_name
})

// Lädt Konto und Inhaber. Erst das Konto, denn erst darin steht, wem es gehört.
async function load(): Promise<void> {
  error.value = ''
  warning.value = ''
  account.value = null
  member.value = null
  try {
    const loaded = await getAccount(Number(props.number))
    if (loaded.member_id !== null) {
      member.value = await getMember(loaded.member_id)
    }
    account.value = loaded
  } catch (e) {
    error.value = errorText(e)
  }
}

// watch statt onMounted: Klickt man auf ein Gegenkonto, bleibt Vue auf derselben Seite und
// tauscht nur die Nummer aus; onMounted liefe dann nicht noch einmal. immediate: auch gleich zu Beginn.
watch(() => props.number, load, { immediate: true })
</script>

<template>
  <div class="button-row">
    <RouterLink v-if="member" :to="{ name: 'member-detail', params: { id: member.id } }" class="btn btn-secondary">
      Zum Mitglied
    </RouterLink>
    <RouterLink :to="{ name: 'members' }" class="btn btn-secondary">Zur Suche</RouterLink>
  </div>

  <div v-if="error" class="status-box error"><p>{{ error }}</p></div>

  <template v-if="account">
    <div class="card">
      <div class="card-header">
        Konto {{ account.number }}:
        <template v-if="isCooperative">Genossenschaftskonto</template>
        <template v-else-if="member">
          {{ ownerName }}
          <span v-if="member.status !== null" class="status-tag" :class="statusTagClass(member.status)">
            {{ statusLabel(member.status) }}
          </span>
        </template>
      </div>
      <div class="card-content">
        <dl>
          <dt>Saldo</dt>
          <dd>{{ formatEuro(account.balance) }}</dd>
          <dt>Anteile</dt>
          <dd>{{ account.shares }}</dd>
          <!-- Erst nach dem Ausscheiden: was die Genossenschaft noch auszahlen muss. -->
          <template v-if="account.claim > 0">
            <dt>Offener Anspruch</dt>
            <dd>{{ formatEuro(account.claim) }}</dd>
          </template>
          <template v-if="member">
            <dt>Gezeichnete Anteile</dt>
            <dd>{{ member.shares_subscribed }}</dd>
            <dt>Geldeingang am</dt>
            <dd>{{ formatDate(member.payment_date) }}</dd>
            <dt>Eintritt am</dt>
            <dd>{{ formatDate(member.entry_date) }}</dd>
          </template>
          <dt>Anteilspreis</dt>
          <dd>{{ account.share_price === null ? 'noch nicht festgelegt' : formatEuro(account.share_price) }}</dd>
        </dl>
      </div>
    </div>

    <!-- share_price! : canBook hat schon geprüft, dass er nicht null ist; TypeScript weiß das hier nicht. -->
    <BookingForm
      v-if="canBook"
      :account-number="account.number"
      :share-price="account.share_price!"
      :claim="account.claim"
      :shares="account.shares"
      :balance="account.balance"
      @booked="onBooked"
    />

    <div class="card">
      <div class="card-header bookings-header">
        Buchungen
        <label class="filter"><input v-model="hideReversed" type="checkbox" /> Stornierte ausblenden</label>
      </div>
      <div class="card-content">
        <div v-if="warning" class="status-box warning"><p>{{ warning }}</p></div>
        <p v-if="account.bookings.length === 0">Noch keine Buchungen.</p>
        <div v-else class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Wertstellung</th>
                <th>Gebucht am</th>
                <th>Art</th>
                <th>Text</th>
                <th>Gegenkonto</th>
                <th class="col-number">Anteile</th>
                <th class="col-number">Betrag</th>
                <th v-if="canReverse"></th>
              </tr>
            </thead>
            <tbody>
              <!-- Original und Storno grau, damit das Paar als erledigt erkennbar ist. -->
              <tr v-for="booking in visibleBookings" :key="booking.id" :class="{ reversed: isReversedPair(booking) }">
                <td>{{ formatDate(booking.value_date) }}</td>
                <td>{{ formatDate(booking.booking_date) }}</td>
                <td>{{ bookingKindLabel(booking.kind) }}</td>
                <td>
                  {{ booking.text }}
                  <small v-if="reversalOf.has(booking.id)" class="reversal-note">
                    storniert am {{ formatDate(reversalOf.get(booking.id)!.booking_date) }}
                  </small>
                </td>
                <td>
                  <RouterLink
                    :to="{ name: 'account', params: { number: counterAccount(account.number, booking) } }"
                  >
                    {{ counterAccount(account.number, booking) }}
                  </RouterLink>
                </td>
                <!-- Aus Sicht dieses Kontos: Haben positiv, Soll negativ. -->
                <td class="col-number">
                  <span>{{ signedFor(account.number, booking).shares }}</span>
                </td>
                <td class="col-number">
                  <span>{{ formatEuro(signedFor(account.number, booking).amount) }}</span>
                </td>
                <!-- Nur Buchungen, die weder Storno sind noch schon storniert; verbindlich prüft das Backend. -->
                <td v-if="canReverse">
                  <button
                    v-if="!isReversedPair(booking)"
                    type="button"
                    class="btn btn-outline"
                    @click="onReverse(booking)"
                  >
                    Stornieren
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </template>
</template>

<style scoped>
.bookings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter {
  font-weight: normal;
}

tr.reversed td {
  color: var(--text-muted);
}

.reversal-note {
  display: block;
}

/* Wie auf der Detailseite: Bezeichnung links, Wert rechts; auf schmalen Bildschirmen untereinander. */
dl {
  display: grid;
  grid-template-columns: 12rem 1fr;
  gap: 0.4rem 1rem;
  margin: 0 0 0.8rem;
}

dt {
  font-weight: 600;
  color: var(--text-label);
}

dd {
  margin: 0;
}

@media (max-width: 768px) {
  dl {
    grid-template-columns: 1fr;
  }

  dd {
    margin-bottom: 0.4rem;
  }
}
</style>
