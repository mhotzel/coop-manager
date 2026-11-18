<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import {
  bookingKindLabel,
  COOPERATIVE_ACCOUNT_NUMBER,
  counterAccount,
  formatEuro,
  getAccount,
  signedFor,
  type AccountView,
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
      @booked="onBooked"
    />

    <div class="card">
      <div class="card-header">Buchungen</div>
      <div class="card-content">
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
              </tr>
            </thead>
            <tbody>
              <tr v-for="booking in account.bookings" :key="booking.id">
                <td>{{ formatDate(booking.value_date) }}</td>
                <td>{{ formatDate(booking.booking_date) }}</td>
                <td>{{ bookingKindLabel(booking.kind) }}</td>
                <td>{{ booking.text }}</td>
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
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </template>
</template>

<style scoped>
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
