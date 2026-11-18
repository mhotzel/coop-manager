<script setup lang="ts">
import { computed, ref } from 'vue'

import {
  formatEuro,
  parseEuro,
  refund,
  sharesForAmount,
  subscribe,
  type AccountView,
  type ShareBooking,
} from '../../accounts'
import { errorText } from '../../api'
import { todayIso } from '../../members'

// Props: kommen von der Elternseite (AccountView.vue) herein und werden hier nur gelesen.
const props = defineProps<{ accountNumber: number; sharePrice: number }>()

// Emits: Ereignisse, die diese Komponente nach außen meldet. Die Elternseite hört mit
// @booked="..." zu und bekommt das Konto nach der Buchung, um die Anzeige zu aktualisieren.
const emit = defineEmits<{ booked: [account: AccountView] }>()

// Welche Buchungsart; vorerst nur diese beiden (Plan.md, Schritt 5d).
type Kind = 'subscribe' | 'refund'
const KIND_LABELS: Record<Kind, string> = { subscribe: 'Eintritt', refund: 'Rückzahlung' }

const kind = ref<Kind>('subscribe')
// Beide Felder als Text, so wie sie im Eingabefeld stehen. Wer gerade tippt, bestimmt das andere.
const sharesText = ref('')
const amountText = ref('')
const valueDate = ref(todayIso())
const text = ref('')

const busy = ref(false)
const error = ref('')
const warning = ref('')
const message = ref('')

// Die Anteile, die gebucht würden, oder null, solange die Eingabe nicht passt.
// computed: rechnet sich automatisch neu, sobald sich sharesText ändert.
const shares = computed<number | null>(() => {
  const value = Number(sharesText.value)
  return Number.isInteger(value) && value > 0 ? value : null
})

// Hinweis unter dem Betragsfeld, wenn der Betrag nicht zu ganzen Anteilen passt.
const amountHint = ref('')

// Anteile eingetippt → Betrag ausrechnen.
function onSharesInput(): void {
  amountHint.value = ''
  amountText.value = shares.value === null ? '' : formatEuro(shares.value * props.sharePrice)
}

// Betrag eingetippt → Anteile ausrechnen, falls er glatt im Anteilspreis aufgeht.
function onAmountInput(): void {
  amountHint.value = ''
  if (amountText.value.trim() === '') {
    sharesText.value = ''
    return
  }
  const cents = parseEuro(amountText.value)
  const result = cents === null ? null : sharesForAmount(cents, props.sharePrice)
  if (result === null || result === 0) {
    sharesText.value = ''
    amountHint.value =
      cents === null
        ? 'Kein gültiger Betrag (z. B. 1.500,00).'
        : `Der Betrag muss ein Vielfaches von ${formatEuro(props.sharePrice)} sein.`
    return
  }
  sharesText.value = String(result)
}

function reset(): void {
  sharesText.value = ''
  amountText.value = ''
  amountHint.value = ''
  valueDate.value = todayIso()
  text.value = ''
}

async function book(): Promise<void> {
  if (shares.value === null) {
    return
  }
  error.value = ''
  warning.value = ''
  message.value = ''
  busy.value = true
  const command: ShareBooking = {
    account_number: props.accountNumber,
    shares: shares.value,
    value_date: valueDate.value,
    text: text.value.trim() === '' ? null : text.value.trim(),
  }
  try {
    const response = kind.value === 'subscribe' ? await subscribe(command) : await refund(command)
    message.value = `${KIND_LABELS[kind.value]} über ${command.shares} Anteile gebucht.`
    warning.value = response.warning ?? ''
    reset()
    emit('booked', response.account)
  } catch (e) {
    error.value = errorText(e)
  } finally {
    // finally läuft immer, auch nach einem Fehler: Der Knopf wird wieder frei.
    busy.value = false
  }
}
</script>

<template>
  <!-- card-center: schmal (max. 600 px) und mittig; die Buchungstabelle darunter bleibt breit. -->
  <div class="card card-center">
    <div class="card-header">Neue Buchung</div>
    <div class="card-content">
      <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
      <div v-if="warning" class="status-box warning"><p>{{ warning }}</p></div>
      <div v-if="message" class="status-box info"><p>{{ message }}</p></div>

      <form @submit.prevent="book">
        <div class="form-row">
          <div class="form-group">
            <label for="booking-kind">Buchungsart</label>
            <select id="booking-kind" v-model="kind">
              <option v-for="(label, key) in KIND_LABELS" :key="key" :value="key">{{ label }}</option>
            </select>
          </div>
          <div class="form-group">
            <!-- max: kein Datum nach heute; verbindlich prüft das Backend. -->
            <label for="booking-value-date">Wertstellung</label>
            <input id="booking-value-date" v-model="valueDate" type="date" :max="todayIso()" required />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="booking-shares">Anteile</label>
            <input id="booking-shares" v-model="sharesText" type="number" min="1" step="1" @input="onSharesInput" />
          </div>
          <div class="form-group">
            <label for="booking-amount">Betrag (Anteilspreis {{ formatEuro(sharePrice) }})</label>
            <input id="booking-amount" v-model="amountText" type="text" inputmode="decimal" @input="onAmountInput" />
            <small v-if="amountHint" class="hint">{{ amountHint }}</small>
          </div>
        </div>

        <div class="form-group">
          <label for="booking-text">Buchungstext (leer = „{{ KIND_LABELS[kind] }}“)</label>
          <input id="booking-text" v-model="text" type="text" maxlength="200" />
        </div>

        <div class="button-row">
          <button type="submit" class="btn btn-primary" :disabled="busy || shares === null">Buchen</button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.hint {
  color: var(--warning-color);
}
</style>
