<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { errorText } from '../../api'
import { ACCOUNTING, currentUser } from '../../auth'
import {
  defaultExitYear,
  formatDate,
  giveNotice,
  givePartialNotice,
  NOTICE,
  todayIso,
  withdrawNotice,
  type MemberDetail,
  type Notice,
} from '../../members'

// Das Mitglied kommt von der Detailseite herein; nach jeder Änderung melden wir die neue
// Detailansicht mit @changed zurück, die Seite tauscht sie dann aus.
const props = defineProps<{ member: MemberDetail }>()
const emit = defineEmits<{ changed: [member: MemberDetail] }>()

// Welches Formular offen ist; null = keines.
type Kind = 'notice' | 'partial'
const kind = ref<Kind | null>(null)
const noticeDate = ref('')
const exitYear = ref(0)
const sharesText = ref('')

const busy = ref(false)
const error = ref('')
const message = ref('')

// Kündigen kann nur, wer heute Mitglied ist (nicht Antragsteller, nicht schon gekündigt).
// Das ist Komfort; verbindlich prüft das Backend am Tag des Eingangs.
const canWrite = computed(() => currentUser.value?.role === ACCOUNTING)
const canGiveNotice = computed(() => canWrite.value && props.member.status === 'member' && kind.value === null)

// Ändert man den Eingang, rechnet das Jahr des Ausscheidens mit (Vorschlag nach der Frist).
watch(noticeDate, (day) => {
  if (day !== '') {
    exitYear.value = defaultExitYear(day)
  }
})

// Tod oder Ausschluss beenden die Mitgliedschaft zum 31.12. ihres Jahres. Kündigungen mit späterem
// Termin bleiben als Geschichte stehen, sind aber gegenstandslos (siehe Plan). Leer = gilt noch.
function mootReason(notice: Notice): string {
  const { date_of_death, expulsion_date, exit_date } = props.member
  if (date_of_death === null && expulsion_date === null) {
    return '' // ohne Tod oder Ausschluss ist keine Kündigung gegenstandslos
  }
  if (exit_date === null || notice.exit_date <= exit_date) {
    return ''
  }
  return date_of_death !== null ? 'Tod' : 'Ausschluss'
}

function kindLabel(notice: Notice): string {
  return notice.kind === NOTICE ? 'Mitgliedschaft' : 'Teilkündigung'
}

function start(chosen: Kind): void {
  error.value = ''
  message.value = ''
  kind.value = chosen
  noticeDate.value = todayIso() // setzt über watch auch das Jahr
  sharesText.value = ''
}

// Gemeinsamer Ablauf für alle Befehle: ausführen, neue Ansicht melden, Erfolg oder Fehler zeigen.
async function run(command: () => Promise<MemberDetail>, success: string): Promise<void> {
  error.value = ''
  message.value = ''
  busy.value = true
  try {
    emit('changed', await command())
    message.value = success
    kind.value = null
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}

function submit(): void {
  const id = props.member.id
  const day = noticeDate.value
  const exitDate = `${exitYear.value}-12-31`
  if (kind.value === 'notice') {
    void run(() => giveNotice(id, day, exitDate), 'Die Kündigung der Mitgliedschaft wurde gespeichert.')
  } else if (kind.value === 'partial') {
    const shares = Number(sharesText.value)
    void run(() => givePartialNotice(id, shares, day, exitDate), 'Die Teilkündigung wurde gespeichert.')
  }
}

function withdraw(notice: Notice): void {
  if (!confirm(`${kindLabel(notice)} vom ${formatDate(notice.notice_date)} zurücknehmen?`)) {
    return
  }
  void run(() => withdrawNotice(props.member.id, notice.id), 'Die Kündigung wurde zurückgenommen.')
}
</script>

<template>
  <div class="card">
    <div class="card-header">Kündigungen</div>
    <div class="card-content">
      <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
      <div v-if="message" class="status-box info"><p>{{ message }}</p></div>

      <p v-if="member.notices.length === 0">Keine Kündigung.</p>
      <div v-else class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Art</th>
              <th>Eingang</th>
              <th>Ausscheiden</th>
              <th class="col-number">Anteile</th>
              <th v-if="canWrite"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="notice in member.notices" :key="notice.id">
              <td>{{ kindLabel(notice) }}</td>
              <td>{{ formatDate(notice.notice_date) }}</td>
              <td>
                {{ formatDate(notice.exit_date) }}
                <small v-if="mootReason(notice)" class="moot">gegenstandslos ({{ mootReason(notice) }})</small>
              </td>
              <!-- Die Kündigung der Mitgliedschaft umfasst alle Anteile. -->
              <td class="col-number">{{ notice.shares ?? 'alle' }}</td>
              <td v-if="canWrite">
                <button type="button" class="btn btn-outline" :disabled="busy" @click="withdraw(notice)">
                  Zurücknehmen
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="canGiveNotice" class="button-row">
        <button type="button" class="btn btn-secondary" @click="start('notice')">Mitgliedschaft kündigen</button>
        <button type="button" class="btn btn-secondary" @click="start('partial')">Teilkündigung</button>
      </div>

      <form v-if="kind !== null" @submit.prevent="submit">
        <h3>{{ kind === 'notice' ? 'Kündigung der Mitgliedschaft' : 'Teilkündigung einzelner Anteile' }}</h3>
        <div class="form-row">
          <div class="form-group">
            <!-- max: kein Eingang in der Zukunft; verbindlich prüft das Backend. -->
            <label for="notice-date">Eingang der Kündigung</label>
            <input id="notice-date" v-model="noticeDate" type="date" :max="todayIso()" required />
          </div>
          <div class="form-group">
            <!-- Nur das Jahr: Ausgeschieden wird immer zum 31.12. (Satzung 6.1). -->
            <label for="notice-exit-year">Ausscheiden zum 31.12.</label>
            <input id="notice-exit-year" v-model.number="exitYear" type="number" min="2000" max="2200" required />
          </div>
        </div>
        <div v-if="kind === 'partial'" class="form-group">
          <label for="notice-shares">Gekündigte Anteile (mindestens einer muss bleiben)</label>
          <input id="notice-shares" v-model="sharesText" type="number" min="1" step="1" required />
        </div>
        <div class="button-row">
          <button type="submit" class="btn btn-primary" :disabled="busy">Kündigung speichern</button>
          <button type="button" class="btn btn-secondary" @click="kind = null">Abbrechen</button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.moot {
  display: block;
  color: var(--text-muted);
}

h3 {
  margin: 0.8rem 0 0.4rem;
  font-size: 1rem;
}
</style>
