<script setup lang="ts">
import { computed, ref } from 'vue'

import { errorText } from '../../api'
import { ACCOUNTING, currentUser } from '../../auth'
import {
  formatDate,
  revokeAdditionalShares,
  subscribeAdditionalShares,
  todayIso,
  type AdditionalSubscription,
  type MemberDetail,
} from '../../members'

// Wie NoticeCard: Das Mitglied kommt von der Detailseite herein, nach jeder Änderung melden wir
// die neue Detailansicht mit @changed zurück.
const props = defineProps<{ member: MemberDetail }>()
const emit = defineEmits<{ changed: [member: MemberDetail] }>()

const formOpen = ref(false)
const sharesText = ref('')
const decisionDate = ref('')

const busy = ref(false)
const error = ref('')
const message = ref('')

// Zeichnen kann nur, wer heute Mitglied ist (nicht gekündigt). Verbindlich prüft das Backend am
// Tag der Zulassung.
const canWrite = computed(() => currentUser.value?.role === ACCOUNTING)
const canSubscribe = computed(() => canWrite.value && props.member.status === 'member' && !formOpen.value)

function start(): void {
  error.value = ''
  message.value = ''
  sharesText.value = ''
  decisionDate.value = todayIso()
  formOpen.value = true
}

// Gemeinsamer Ablauf: ausführen, neue Ansicht melden, Erfolg oder Fehler zeigen.
async function run(command: () => Promise<MemberDetail>, success: string): Promise<void> {
  error.value = ''
  message.value = ''
  busy.value = true
  try {
    emit('changed', await command())
    message.value = success
    formOpen.value = false
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}

function submit(): void {
  const shares = Number(sharesText.value)
  void run(
    () => subscribeAdditionalShares(props.member.id, shares, decisionDate.value),
    `${shares} weitere Anteile gezeichnet. Eingezahlt wird in der Buchungsmaske des Kontos („Weitere Anteile“).`,
  )
}

function revoke(subscription: AdditionalSubscription): void {
  const question = `Zeichnung über ${subscription.shares} Anteile vom ${formatDate(subscription.decision_date)} zurücknehmen?`
  if (!confirm(question)) {
    return
  }
  void run(() => revokeAdditionalShares(props.member.id, subscription.id), 'Die Zeichnung wurde zurückgenommen.')
}
</script>

<template>
  <div class="card">
    <div class="card-header">Weitere Anteile</div>
    <div class="card-content">
      <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
      <div v-if="message" class="status-box info"><p>{{ message }}</p></div>

      <p v-if="member.additional_subscriptions.length === 0">Keine weiteren Anteile gezeichnet.</p>
      <template v-else>
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Zulassung</th>
                <th class="col-number">Anteile</th>
                <th v-if="canWrite"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="subscription in member.additional_subscriptions" :key="subscription.id">
                <td>{{ formatDate(subscription.decision_date) }}</td>
                <td class="col-number">{{ subscription.shares }}</td>
                <td v-if="canWrite">
                  <button type="button" class="btn btn-outline" :disabled="busy" @click="revoke(subscription)">
                    Zurücknehmen
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="member.additional_shares_open > 0">Noch nicht eingezahlt: {{ member.additional_shares_open }} Anteile.</p>
        <p v-else>Alle weiteren Anteile sind eingezahlt.</p>
      </template>

      <div v-if="canSubscribe" class="button-row">
        <button type="button" class="btn btn-secondary" @click="start">Weitere Anteile zeichnen</button>
      </div>

      <form v-if="formOpen" @submit.prevent="submit">
        <div class="form-row">
          <div class="form-group">
            <label for="additional-shares">Anteile</label>
            <input id="additional-shares" v-model="sharesText" type="number" min="1" step="1" required />
          </div>
          <div class="form-group">
            <!-- max: keine Zulassung in der Zukunft; verbindlich prüft das Backend. -->
            <label for="additional-decision-date">Zulassung durch den Vorstand</label>
            <input id="additional-decision-date" v-model="decisionDate" type="date" :max="todayIso()" required />
          </div>
        </div>
        <div class="button-row">
          <button type="submit" class="btn btn-primary" :disabled="busy">Zeichnung speichern</button>
          <button type="button" class="btn btn-secondary" @click="formOpen = false">Abbrechen</button>
        </div>
      </form>
    </div>
  </div>
</template>
