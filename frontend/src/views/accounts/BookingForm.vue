<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import {
  deductLoss,
  donate,
  formatEuro,
  parseEuro,
  payout,
  refund,
  sharesForAmount,
  subscribe,
  writeOff,
  type AccountView,
  type BookingResponse,
} from '../../accounts'
import { errorText } from '../../api'
import { todayIso } from '../../members'

// Props: kommen von der Elternseite (AccountView.vue) herein und werden hier nur gelesen.
// claim: offener Auseinandersetzungsanspruch; erst damit gibt es Auszahlung usw.
// shares und balance: für die Spende, die immer das ganze Guthaben umfasst.
const props = defineProps<{ accountNumber: number; sharePrice: number; claim: number; shares: number; balance: number }>()

// Emits: Ereignisse, die diese Komponente nach außen meldet. Die Elternseite hört mit
// @booked="..." zu und bekommt das Konto nach der Buchung, um die Anzeige zu aktualisieren.
const emit = defineEmits<{ booked: [account: AccountView] }>()

// Die Buchungsarten der Maske. Zwei Gruppen: mit Anteilen (Betrag = Anteile × Preis) und mit
// freiem Betrag ohne Anteile, die den Anspruch mindern (siehe Plan: Buchungsarten). Dazu die Spende,
// die immer das ganze Guthaben bucht und deshalb keine Eingabe braucht.
type Kind = 'subscribe' | 'refund' | 'payout' | 'deductLoss' | 'writeOff' | 'donate'
const KIND_LABELS: Record<Kind, string> = {
  subscribe: 'Eintritt',
  refund: 'Rückzahlung',
  payout: 'Auszahlung',
  deductLoss: 'Kürzung Verlustvortrag',
  writeOff: 'Ausbuchung Verjährung',
  donate: 'Spende Anteil',
}
const SHARE_KINDS: Kind[] = ['subscribe', 'refund']
const CLAIM_KINDS: Kind[] = ['payout', 'deductLoss', 'writeOff']

// Die Arten, die gerade passen: die mindernden nur, solange es einen Anspruch gibt, die Spende nur,
// solange es Anteile gibt. Ob die Person spenden darf (Status), prüft das Backend.
const kinds = computed<Kind[]>(() => {
  const result: Kind[] = props.claim > 0 ? [...CLAIM_KINDS, ...SHARE_KINDS] : [...SHARE_KINDS]
  if (props.shares > 0) {
    result.push('donate')
  }
  return result
})
const kind = ref<Kind>(props.claim > 0 ? 'payout' : 'subscribe')
const isShareKind = computed(() => SHARE_KINDS.includes(kind.value))

// Fällt der Anspruch weg (z. B. nach der Auszahlung des Rests), passt die gewählte Art nicht mehr.
watch(kinds, (available) => {
  if (!available.includes(kind.value)) {
    kind.value = available[0] ?? 'subscribe'
  }
})

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

// Der freie Betrag in Cent (Auszahlung, Verlustvortrag) oder null, solange die Eingabe nicht passt.
const amount = computed<number | null>(() => {
  const cents = parseEuro(amountText.value)
  return cents !== null && cents > 0 ? cents : null
})

// Kann gebucht werden? Die Ausbuchung braucht keine Eingabe, sie nimmt den ganzen Rest.
const ready = computed(() => {
  if (isShareKind.value) {
    return shares.value !== null
  }
  return kind.value === 'writeOff' || kind.value === 'donate' || amount.value !== null
})

// Hinweis unter dem Betragsfeld, wenn der Betrag nicht zu ganzen Anteilen passt.
const amountHint = ref('')

// Anteile eingetippt → Betrag ausrechnen.
function onSharesInput(): void {
  amountHint.value = ''
  amountText.value = shares.value === null ? '' : formatEuro(shares.value * props.sharePrice)
}

// Betrag eingetippt → bei Arten mit Anteilen die Anteile ausrechnen, falls er glatt aufgeht.
function onAmountInput(): void {
  amountHint.value = ''
  if (amountText.value.trim() === '') {
    sharesText.value = ''
    return
  }
  const cents = parseEuro(amountText.value)
  if (cents === null) {
    sharesText.value = ''
    amountHint.value = 'Kein gültiger Betrag (z. B. 1.500,00).'
    return
  }
  if (!isShareKind.value) {
    return // freier Betrag: keine Anteile
  }
  const result = sharesForAmount(cents, props.sharePrice)
  if (result === null || result === 0) {
    sharesText.value = ''
    amountHint.value = `Der Betrag muss ein Vielfaches von ${formatEuro(props.sharePrice)} sein.`
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

// Beim Wechsel der Art passen die bisherigen Eingaben oft nicht mehr; lieber leeren.
watch(kind, () => {
  sharesText.value = ''
  amountText.value = ''
  amountHint.value = ''
})

// Schickt den passenden Befehl und liefert die Antwort samt einer Erfolgsmeldung.
async function send(): Promise<[BookingResponse, string]> {
  const base = {
    account_number: props.accountNumber,
    value_date: valueDate.value,
    text: text.value.trim() === '' ? null : text.value.trim(),
  }
  const label = KIND_LABELS[kind.value]
  switch (kind.value) {
    case 'subscribe':
    case 'refund': {
      const command = { ...base, shares: shares.value! } // ready hat geprüft, dass es nicht null ist
      const response = kind.value === 'subscribe' ? await subscribe(command) : await refund(command)
      return [response, `${label} über ${command.shares} Anteile gebucht.`]
    }
    case 'payout':
    case 'deductLoss': {
      const command = { ...base, amount: amount.value! }
      const response = kind.value === 'payout' ? await payout(command) : await deductLoss(command)
      return [response, `${label} über ${formatEuro(command.amount)} gebucht.`]
    }
    case 'writeOff':
      return [await writeOff(base), `${label} über ${formatEuro(props.claim)} gebucht.`]
    case 'donate':
      return [await donate(base), `${label} über ${props.shares} Anteile (${formatEuro(props.balance)}) gebucht.`]
  }
}

async function book(): Promise<void> {
  if (!ready.value) {
    return
  }
  if (kind.value === 'writeOff' && !confirm(`Den ganzen Restanspruch von ${formatEuro(props.claim)} ausbuchen?`)) {
    return
  }
  if (
    kind.value === 'donate' &&
    !confirm(
      `Alle ${props.shares} Anteile und den ganzen Saldo von ${formatEuro(props.balance)} der Genossenschaft spenden? ` +
        'Das Mitglied scheidet damit aus.',
    )
  ) {
    return
  }
  error.value = ''
  warning.value = ''
  message.value = ''
  busy.value = true
  try {
    const [response, success] = await send()
    message.value = success
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
              <option v-for="key in kinds" :key="key" :value="key">{{ KIND_LABELS[key] }}</option>
            </select>
          </div>
          <div class="form-group">
            <!-- max: kein Datum nach heute; verbindlich prüft das Backend. -->
            <label for="booking-value-date">Wertstellung</label>
            <input id="booking-value-date" v-model="valueDate" type="date" :max="todayIso()" required />
          </div>
        </div>

        <!-- Arten mit Anteilen: Anteile und Betrag rechnen sich gegenseitig aus. -->
        <div v-if="isShareKind" class="form-row">
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

        <!-- Auszahlung und Verlustvortrag: freier Betrag, höchstens der offene Anspruch. -->
        <div v-else-if="kind === 'payout' || kind === 'deductLoss'" class="form-group">
          <label for="booking-claim-amount">Betrag (offener Anspruch {{ formatEuro(claim) }})</label>
          <input
            id="booking-claim-amount"
            v-model="amountText"
            type="text"
            inputmode="decimal"
            @input="onAmountInput"
          />
          <small v-if="amountHint" class="hint">{{ amountHint }}</small>
        </div>

        <p v-else-if="kind === 'writeOff'" class="info-text">
          Ausgebucht wird der ganze Restanspruch von {{ formatEuro(claim) }}.
        </p>

        <p v-else class="info-text">
          Gespendet werden alle {{ shares }} Anteile, Saldo {{ formatEuro(balance) }}, an die Genossenschaft. Das
          Mitglied scheidet damit am Tag nach der Wertstellung aus.
        </p>

        <div class="form-group">
          <label for="booking-text">Buchungstext (leer = „{{ KIND_LABELS[kind] }}“)</label>
          <input id="booking-text" v-model="text" type="text" maxlength="200" />
        </div>

        <div class="button-row">
          <button type="submit" class="btn btn-primary" :disabled="busy || !ready">Buchen</button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.hint {
  color: var(--warning-color);
}

.info-text {
  margin: 0 0 0.8rem;
}
</style>
