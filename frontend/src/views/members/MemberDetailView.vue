<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { errorText } from '../../api'
import { ACCOUNTING, currentUser } from '../../auth'
import * as members from '../../members'
import { formatDate, genderLabel, NATURAL_PERSON, personTypeLabel, statusLabel, type MemberDetail } from '../../members'

// Der Router übergibt :id aus dem Pfad als Prop (siehe props: true in router.ts).
const props = defineProps<{ id: string }>()

const member = ref<MemberDetail | null>(null)
const message = ref('')
const error = ref('')
const busy = ref(false)

// Welche Entscheidung gerade erfasst wird. Ein Union-Typ aus festen Texten: Vertippt man sich
// (z. B. 'admitt'), meldet TypeScript einen Fehler. null heißt: kein Formular offen.
type Action = 'admit' | 'reject' | 'withdraw'
const action = ref<Action | null>(null)
const actionDate = ref('')

const ACTION_TITLES: Record<Action, string> = {
  admit: 'Zulassung durch den Vorstand',
  reject: 'Ablehnung durch den Vorstand',
  withdraw: 'Rücknahme durch die Person',
}

// Was ist im aktuellen Zustand erlaubt? Nur damit keine sinnlosen Knöpfe erscheinen;
// verbindlich prüft das Backend (members/domain.py).
const canWrite = computed(() => currentUser.value?.role === ACCOUNTING)
const isOpen = computed(() => member.value !== null && member.value.rejection_date === null)
const canDecide = computed(() => canWrite.value && isOpen.value && member.value?.admission_date === null)
const canWithdraw = computed(() => canWrite.value && isOpen.value)

const isNaturalPerson = computed(() => member.value?.person_type === NATURAL_PERSON)

// Die Adresszeilen ohne leere Zeilen am Ende, so wie sie auf dem Umschlag stehen.
const visibleAddressLines = computed(() => {
  const lines = [...(member.value?.address_lines ?? [])]
  while (lines.length > 0 && lines[lines.length - 1] === '') {
    lines.pop()
  }
  return lines
})

onMounted(async () => {
  try {
    member.value = await members.getMember(props.id)
  } catch (e) {
    error.value = errorText(e)
  }
})

function startAction(chosen: Action): void {
  message.value = ''
  error.value = ''
  action.value = chosen
  actionDate.value = members.todayIso()
}

async function confirmAction(): Promise<void> {
  if (action.value === null) {
    return
  }
  // Je Aktion die passende Funktion aus members.ts; alle haben dieselbe Form (id, Datum).
  const commands: Record<Action, (id: string, day: string) => Promise<MemberDetail>> = {
    admit: members.admit,
    reject: members.reject,
    withdraw: members.withdraw,
  }
  const title = ACTION_TITLES[action.value]
  error.value = ''
  busy.value = true
  try {
    member.value = await commands[action.value](props.id, actionDate.value)
    message.value = `${title} wurde gespeichert.`
    action.value = null
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="button-row">
    <RouterLink :to="{ name: 'members' }" class="btn btn-secondary">Zur Suche</RouterLink>
  </div>

  <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
  <div v-if="message" class="status-box info"><p>{{ message }}</p></div>

  <template v-if="member">
    <div class="card">
      <div class="card-header">
        Nr. {{ member.member_number }}:
        {{ isNaturalPerson ? `${member.name.first_names} ${member.name.last_name}` : member.name.company_name }}
        <span v-if="member.status !== null" class="status-tag" :class="member.status === 'rejected' ? 'warning' : 'info'">
          {{ statusLabel(member.status) }}
        </span>
      </div>
      <div class="card-content">
        <dl>
          <dt>Art der Person</dt>
          <dd>{{ personTypeLabel(member.person_type) }}</dd>
          <dt>Antrag vom</dt>
          <dd>{{ formatDate(member.application_date) }}</dd>
          <dt>Gezeichnete Anteile</dt>
          <dd>{{ member.shares_subscribed }}</dd>
          <dt>Zugelassen am</dt>
          <dd>{{ formatDate(member.admission_date) }}</dd>
          <template v-if="member.rejection_date !== null">
            <dt>{{ member.withdrawn ? 'Zurückgenommen am' : 'Abgelehnt am' }}</dt>
            <dd>{{ formatDate(member.rejection_date) }}</dd>
          </template>
        </dl>

        <div v-if="action === null && (canDecide || canWithdraw)" class="button-row">
          <button v-if="canDecide" type="button" class="btn btn-primary" @click="startAction('admit')">Zulassen</button>
          <button v-if="canDecide" type="button" class="btn btn-secondary" @click="startAction('reject')">Ablehnen</button>
          <button v-if="canWithdraw" type="button" class="btn btn-secondary" @click="startAction('withdraw')">
            Rücknahme
          </button>
        </div>

        <form v-if="action !== null" @submit.prevent="confirmAction">
          <div class="form-group">
            <label for="action-date">{{ ACTION_TITLES[action] }} am</label>
            <input id="action-date" v-model="actionDate" type="date" required />
            <div class="button-row">
              <button type="submit" class="btn btn-primary" :disabled="busy">Bestätigen</button>
              <button type="button" class="btn btn-secondary" @click="action = null">Abbrechen</button>
            </div>
          </div>
        </form>
      </div>
    </div>

    <div class="card">
      <div class="card-header">{{ isNaturalPerson ? 'Name' : 'Firma und Ansprechpartner' }}</div>
      <div class="card-content">
        <dl>
          <template v-if="!isNaturalPerson">
            <dt>Firma</dt>
            <dd>{{ member.name.company_name }}</dd>
          </template>
          <dt>Titel</dt>
          <dd>{{ member.name.title || '–' }}</dd>
          <dt>Vornamen</dt>
          <dd>{{ member.name.first_names || '–' }}</dd>
          <dt>Nachname</dt>
          <dd>{{ member.name.last_name || '–' }}</dd>
          <dt>Geschlecht</dt>
          <dd>{{ genderLabel(member.name.gender) }}</dd>
        </dl>
      </div>
    </div>

    <div class="card">
      <div class="card-header">Anschrift</div>
      <div class="card-content">
        <dl>
          <dt>Straße</dt>
          <dd>{{ member.address.street }} {{ member.address.house_number }}</dd>
          <dt>Ort</dt>
          <dd>{{ member.address.postal_code }} {{ member.address.city }}</dd>
          <dt>Land</dt>
          <dd>{{ member.address.country || 'Deutschland' }}</dd>
        </dl>
      </div>
    </div>

    <div class="card">
      <div class="card-header">Kontakt</div>
      <div class="card-content">
        <dl>
          <dt>Telefon</dt>
          <dd>{{ member.contact.phone || '–' }}</dd>
          <dt>E-Mail</dt>
          <dd>{{ member.contact.email || '–' }}</dd>
        </dl>
      </div>
    </div>

    <div class="card">
      <div class="card-header">Post</div>
      <div class="card-content">
        <div v-if="member.warnings.length > 0" class="status-box warning">
          <p v-for="warning in member.warnings" :key="warning">{{ warning }}</p>
        </div>
        <dl>
          <dt>Adresszeilen</dt>
          <dd>
            <!-- Leere Zeilen mittendrin als geschütztes Leerzeichen, sonst fielen sie weg. -->
            <div v-for="(line, index) in visibleAddressLines" :key="index">{{ line || ' ' }}</div>
          </dd>
          <dt>Briefanrede</dt>
          <dd>
            {{ member.salutation }}
            <span v-if="member.salutation_override" class="status-tag info">abweichend</span>
          </dd>
          <dt>Keine Post</dt>
          <dd>{{ member.no_mail ? 'ja' : 'nein' }}</dd>
        </dl>
      </div>
    </div>

    <div class="card">
      <div class="card-header">Hinweise</div>
      <div class="card-content">
        <!-- pre-line: Zeilenumbrüche aus dem Text bleiben erhalten. -->
        <p class="notes">{{ member.notes || 'keine' }}</p>
      </div>
    </div>
  </template>
</template>

<style scoped>
/* Bezeichnung links, Wert rechts; auf schmalen Bildschirmen untereinander. */
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

.notes {
  white-space: pre-line;
}
</style>
