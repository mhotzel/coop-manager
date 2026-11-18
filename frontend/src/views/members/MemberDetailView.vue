<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { errorText } from '../../api'
import { ACCOUNTING, currentUser } from '../../auth'
import * as members from '../../members'
import {
  formatDate,
  genderLabel,
  NATURAL_PERSON,
  personTypeLabel,
  showPartialNotice,
  statusLabel,
  statusTagClass,
  type Address,
  type Contact,
  type MemberDetail,
  type PersonName,
} from '../../members'
import AddressFields from './AddressFields.vue'
import ContactFields from './ContactFields.vue'
import NameFields from './NameFields.vue'
import NoticeCard from './NoticeCard.vue'

// Der Router übergibt :id aus dem Pfad als Prop (siehe props: true in router.ts).
const props = defineProps<{ id: string }>()

const member = ref<MemberDetail | null>(null)
const message = ref('')
const error = ref('')
const busy = ref(false)

// Welche Entscheidung gerade erfasst wird. Ein Union-Typ aus festen Texten: Vertippt man sich
// (z. B. 'admitt'), meldet TypeScript einen Fehler. null heißt: kein Formular offen.
type Action = 'admit' | 'reject' | 'withdraw' | 'death' | 'expel' | 'liftExpulsion'
const action = ref<Action | null>(null)
const actionDate = ref('')

const ACTION_TITLES: Record<Action, string> = {
  admit: 'Zulassung durch den Vorstand',
  reject: 'Ablehnung durch den Vorstand',
  withdraw: 'Rücknahme durch die Person',
  death: 'Tod des Mitglieds',
  expel: 'Ausschluss durch den Vorstand',
  liftExpulsion: 'Aufhebung des Ausschlusses',
}

// Nach „Tod erfassen“: Hinweis, die Adresszeilen auf die Erben umzustellen (siehe Plan).
const heirsHint = ref(false)

// Welcher Abschnitt gerade bearbeitet wird; immer nur einer, jeder mit seinem eigenen Befehl.
type Section = 'name' | 'address' | 'contact' | 'addressLines' | 'salutation' | 'notes'
const editing = ref<Section | null>(null)

// Entwürfe: Kopien der Daten, die das Formular ändert. Erst „Speichern“ schickt sie ans Backend,
// „Abbrechen“ verwirft sie einfach. Die Anzeige bleibt bis dahin unverändert.
const draftName = ref<PersonName>({ company_name: '', title: '', first_names: '', last_name: '', gender: '' })
const draftAddress = ref<Address>({ street: '', house_number: '', postal_code: '', city: '', country: '' })
const draftContact = ref<Contact>({ phone: '', email: '' })
const draftLines = ref<string[]>([])
const draftSalutation = ref('')
const draftNotes = ref('')

// Längere Zeilen passen nicht mehr ins Sichtfenster des Umschlags (siehe Plan.md).
const LINE_WARN_LENGTH = 35

// Was ist im aktuellen Zustand erlaubt? Nur damit keine sinnlosen Knöpfe erscheinen;
// verbindlich prüft das Backend (members/domain.py).
const canWrite = computed(() => currentUser.value?.role === ACCOUNTING)
const isOpen = computed(() => member.value !== null && member.value.rejection_date === null)
const canDecide = computed(() => canWrite.value && isOpen.value && member.value?.admission_date === null)
// Den Antrag zurücknehmen kann nur, wer noch nicht Mitglied ist; danach gilt die Kündigung.
const canWithdraw = computed(() => canWrite.value && isOpen.value && member.value?.entry_date === null)
// Tod erfassen bei Mitgliedern, auch gekündigten; bei Antragstellern gilt die Rücknahme.
const canRecordDeath = computed(
  () =>
    canWrite.value &&
    member.value?.date_of_death === null &&
    (member.value.status === 'member' || member.value.status === 'notice_given'),
)
// Ausschließen wie Tod: bei Mitgliedern, auch gekündigten. Aufheben, solange einer erfasst ist.
const canExpel = computed(
  () =>
    canWrite.value &&
    member.value?.expulsion_date === null &&
    (member.value.status === 'member' || member.value.status === 'notice_given'),
)
const canLiftExpulsion = computed(
  () => canWrite.value && member.value !== null && member.value.expulsion_date !== null,
)
const canRevokeDeath = computed(() => canWrite.value && member.value !== null && member.value.date_of_death !== null)
// Bearbeiten nur, solange kein anderes Formular offen ist; so geht kein Entwurf verloren.
const canEdit = computed(() => canWrite.value && editing.value === null && action.value === null)

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

// Führt einen Befehl aus und zeigt danach Erfolg oder Fehler an. Jeder Befehl antwortet mit der
// neuen Detailansicht, die einfach die alte ersetzt. Bei einem Fehler bleibt das Formular offen.
async function run(command: () => Promise<MemberDetail>, success: string): Promise<void> {
  message.value = ''
  error.value = ''
  busy.value = true
  try {
    member.value = await command()
    message.value = success
    action.value = null
    editing.value = null
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}

function startAction(chosen: Action): void {
  message.value = ''
  error.value = ''
  heirsHint.value = false
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
    death: members.recordDeath,
    expel: members.expel,
    liftExpulsion: members.liftExpulsion,
  }
  const chosen = action.value
  const day = actionDate.value
  await run(() => commands[chosen](props.id, day), `${ACTION_TITLES[chosen]} wurde gespeichert.`)
  // run() lässt error leer, wenn alles geklappt hat.
  heirsHint.value = chosen === 'death' && error.value === ''
}

function revokeDeath(): void {
  if (!confirm('Die Erfassung des Todes zurücknehmen? Das ist nur für Fehlerfassungen gedacht.')) {
    return
  }
  heirsHint.value = false
  void run(() => members.revokeDeath(props.id), 'Die Erfassung des Todes wurde zurückgenommen.')
}

// Vom Hinweis nach dem Tod direkt zu den Adresszeilen: Formular öffnen und hinscrollen.
function editLinesForHeirs(): void {
  startEdit('addressLines')
  document.getElementById('address-lines-card')?.scrollIntoView({ behavior: 'smooth' })
}

// Öffnet einen Abschnitt zum Bearbeiten und füllt den Entwurf mit den gespeicherten Daten.
// { ...x } und [...x] machen Kopien; sonst änderte das Formular direkt die Anzeige mit.
function startEdit(section: Section): void {
  const m = member.value
  if (m === null) {
    return
  }
  message.value = ''
  error.value = ''
  heirsHint.value = false
  draftName.value = { ...m.name }
  draftAddress.value = { ...m.address }
  draftContact.value = { ...m.contact }
  draftLines.value = [...m.address_lines]
  draftSalutation.value = m.salutation_override
  draftNotes.value = m.notes
  editing.value = section
}

const saveName = () => run(() => members.changeName(props.id, draftName.value), 'Der Name wurde geändert.')
const saveAddress = () => run(() => members.changeAddress(props.id, draftAddress.value), 'Die Anschrift wurde geändert.')
const saveContact = () => run(() => members.changeContact(props.id, draftContact.value), 'Der Kontakt wurde geändert.')
const saveLines = () =>
  run(() => members.changeAddressLines(props.id, draftLines.value), 'Die Adresszeilen wurden geändert.')
const saveSalutation = () =>
  run(() => members.changeSalutation(props.id, draftSalutation.value), 'Die Briefanrede wurde geändert.')
const saveNotes = () => run(() => members.changeNotes(props.id, draftNotes.value), 'Die Hinweise wurden geändert.')

function toggleNoMail(): void {
  const noMail = !member.value?.no_mail
  void run(
    () => members.changeMailPreference(props.id, noMail),
    noMail ? 'Das Mitglied bekommt keine Post mehr.' : 'Das Mitglied bekommt wieder Post.',
  )
}

// Übernimmt die im Backend aus Name und Anschrift erzeugten Zeilen in den Entwurf. Stehen dort
// andere Zeilen (z. B. von Hand angepasst), wird vorher gefragt. Gespeichert wird erst danach.
function generateLines(): void {
  const generated = member.value?.generated_address_lines ?? []
  const differs = draftLines.value.some((line, index) => line !== generated[index])
  if (differs && !window.confirm('Die Adresszeilen weichen von den erzeugten ab. Überschreiben?')) {
    return
  }
  draftLines.value = [...generated]
}
</script>

<template>
  <!-- card-center: die ganze Seite schmal (max. 600 px) und mittig, wie die Antragsmaske. -->
  <div class="card-center">
    <div class="button-row">
      <RouterLink :to="{ name: 'members' }" class="btn btn-secondary">Zur Suche</RouterLink>
    </div>

    <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
    <div v-if="message" class="status-box info"><p>{{ message }}</p></div>

    <template v-if="member">
      <!-- Oben, damit man die Warnungen direkt nach dem Speichern sieht. Speichern geht trotzdem. -->
      <div v-if="member.warnings.length > 0" class="status-box warning">
        <p v-for="warning in member.warnings" :key="warning">{{ warning }}</p>
      </div>

      <div class="card">
        <div class="card-header">
          Nr. {{ member.member_number }}:
          {{ isNaturalPerson ? `${member.name.first_names} ${member.name.last_name}` : member.name.company_name }}
          <span v-if="member.status !== null" class="status-tag" :class="statusTagClass(member.status)">
            {{ statusLabel(member.status) }}
          </span>
          <span v-if="showPartialNotice(member.status, member.partial_notice)" class="status-tag warning">
            teilgekündigt
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
            <dt>Geldeingang am</dt>
            <dd>{{ formatDate(member.payment_date) }}</dd>
            <dt>Eintritt am</dt>
            <dd>{{ formatDate(member.entry_date) }}</dd>
            <template v-if="member.notice_date !== null">
              <dt>Kündigung eingegangen</dt>
              <dd>{{ formatDate(member.notice_date) }}</dd>
            </template>
            <template v-if="member.expulsion_date !== null">
              <dt>Ausgeschlossen am</dt>
              <dd>{{ formatDate(member.expulsion_date) }}</dd>
            </template>
            <template v-if="member.date_of_death !== null">
              <dt>Verstorben am</dt>
              <dd>{{ formatDate(member.date_of_death) }}</dd>
            </template>
            <!-- Wirksames Ausscheiden: nach einem Tod der 31.12. des Todesjahres. -->
            <template v-if="member.exit_date !== null">
              <dt>Ausscheiden zum</dt>
              <dd>{{ formatDate(member.exit_date) }}</dd>
            </template>
          </dl>

          <div class="button-row">
            <!-- Mitglieds- und Kontonummer sind gleich (siehe Plan). -->
            <RouterLink :to="{ name: 'account', params: { number: member.member_number } }" class="btn btn-outline">
              Konto anzeigen
            </RouterLink>
          </div>

          <div v-if="heirsHint" class="status-box warning">
            <p>
              Bitte die Adresszeilen auf die Erben umstellen, z. B. „An die Erben von …“ mit deren
              Anschrift. Die Briefanrede lautet jetzt immer „Sehr geehrte Damen und Herren“.
            </p>
            <div class="button-row">
              <button type="button" class="btn btn-primary" @click="editLinesForHeirs">Adresszeilen bearbeiten</button>
            </div>
          </div>

          <div
            v-if="
              editing === null &&
              action === null &&
              (canDecide || canWithdraw || canRecordDeath || canRevokeDeath || canExpel || canLiftExpulsion)
            "
            class="button-row"
          >
            <button v-if="canDecide" type="button" class="btn btn-primary" @click="startAction('admit')">Zulassen</button>
            <button v-if="canDecide" type="button" class="btn btn-secondary" @click="startAction('reject')">Ablehnen</button>
            <button v-if="canWithdraw" type="button" class="btn btn-secondary" @click="startAction('withdraw')">
              Rücknahme
            </button>
            <button v-if="canRecordDeath" type="button" class="btn btn-secondary" @click="startAction('death')">
              Tod erfassen
            </button>
            <button v-if="canExpel" type="button" class="btn btn-secondary" @click="startAction('expel')">
              Ausschließen
            </button>
            <button v-if="canLiftExpulsion" type="button" class="btn btn-outline" @click="startAction('liftExpulsion')">
              Ausschluss aufheben
            </button>
            <button v-if="canRevokeDeath" type="button" class="btn btn-outline" :disabled="busy" @click="revokeDeath">
              Erfassung des Todes zurücknehmen
            </button>
          </div>

          <form v-if="action !== null" @submit.prevent="confirmAction">
            <div class="form-group">
              <label for="action-date">{{ ACTION_TITLES[action] }} am</label>
              <!-- min/max: Der Browser bietet nur Tage zwischen Antrag und heute an (geprüft wird im Backend). -->
              <input
                id="action-date"
                v-model="actionDate"
                type="date"
                :min="member.application_date"
                :max="members.todayIso()"
                required
              />
              <small v-if="action === 'expel'" class="hint">
                Ausscheiden zum 31.12. des Beschlussjahres. Widerspruch beim Aufsichtsrat binnen sechs
                Wochen; gibt er ihm statt, den Ausschluss hier wieder aufheben.
              </small>
              <small v-if="action === 'liftExpulsion'" class="hint">
                Datum des Aufsichtsratsbeschlusses; auch für eine Fehlerfassung. Der Ausschluss gilt
                danach als nie geschehen.
              </small>
              <div class="button-row">
                <button type="submit" class="btn btn-primary" :disabled="busy">Bestätigen</button>
                <button type="button" class="btn btn-secondary" @click="action = null">Abbrechen</button>
              </div>
            </div>
          </form>
        </div>
      </div>

      <!-- Erst ab dem Eintritt sinnvoll; laufende Kündigungen bleiben sichtbar. -->
      <NoticeCard
        v-if="member.entry_date !== null || member.notices.length > 0"
        :member="member"
        @changed="(updated) => (member = updated)"
      />

      <div class="card">
        <div class="card-header">{{ isNaturalPerson ? 'Name' : 'Firma und Ansprechpartner' }}</div>
        <div class="card-content">
          <form v-if="editing === 'name'" @submit.prevent="saveName">
            <NameFields v-model="draftName" :person-type="member.person_type" />
            <p class="hint">Die Adresszeilen ändern sich nicht von selbst, bitte danach prüfen.</p>
            <div class="button-row">
              <button type="submit" class="btn btn-primary" :disabled="busy">Speichern</button>
              <button type="button" class="btn btn-secondary" @click="editing = null">Abbrechen</button>
            </div>
          </form>
          <template v-else>
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
            <div v-if="canEdit" class="button-row">
              <button type="button" class="btn btn-outline" @click="startEdit('name')">Bearbeiten</button>
            </div>
          </template>
        </div>
      </div>

      <div class="card">
        <div class="card-header">Anschrift</div>
        <div class="card-content">
          <form v-if="editing === 'address'" @submit.prevent="saveAddress">
            <AddressFields v-model="draftAddress" />
            <p class="hint">Die Adresszeilen ändern sich nicht von selbst, bitte danach prüfen.</p>
            <div class="button-row">
              <button type="submit" class="btn btn-primary" :disabled="busy">Speichern</button>
              <button type="button" class="btn btn-secondary" @click="editing = null">Abbrechen</button>
            </div>
          </form>
          <template v-else>
            <dl>
              <dt>Straße</dt>
              <dd>{{ member.address.street }} {{ member.address.house_number }}</dd>
              <dt>Ort</dt>
              <dd>{{ member.address.postal_code }} {{ member.address.city }}</dd>
              <dt>Land</dt>
              <dd>{{ member.address.country || 'Deutschland' }}</dd>
            </dl>
            <div v-if="canEdit" class="button-row">
              <button type="button" class="btn btn-outline" @click="startEdit('address')">Bearbeiten</button>
            </div>
          </template>
        </div>
      </div>

      <div class="card">
        <div class="card-header">Kontakt</div>
        <div class="card-content">
          <form v-if="editing === 'contact'" @submit.prevent="saveContact">
            <ContactFields v-model="draftContact" />
            <div class="button-row">
              <button type="submit" class="btn btn-primary" :disabled="busy">Speichern</button>
              <button type="button" class="btn btn-secondary" @click="editing = null">Abbrechen</button>
            </div>
          </form>
          <template v-else>
            <dl>
              <dt>Telefon</dt>
              <dd>{{ member.contact.phone || '–' }}</dd>
              <dt>E-Mail</dt>
              <dd>{{ member.contact.email || '–' }}</dd>
            </dl>
            <div v-if="canEdit" class="button-row">
              <button type="button" class="btn btn-outline" @click="startEdit('contact')">Bearbeiten</button>
            </div>
          </template>
        </div>
      </div>

      <div id="address-lines-card" class="card">
        <div class="card-header">Adresszeilen</div>
        <div class="card-content">
          <form v-if="editing === 'addressLines'" @submit.prevent="saveLines">
            <div class="form-group">
              <!-- v-model auf ein Element der Liste: draftLines[index] wird direkt geändert. -->
              <template v-for="(line, index) in draftLines" :key="index">
                <label :for="`line-${index}`">
                  Zeile {{ index + 1 }}
                  <span v-if="line.length > LINE_WARN_LENGTH" class="too-long">
                    ({{ line.length }} Zeichen, höchstens {{ LINE_WARN_LENGTH }} passen)
                  </span>
                </label>
                <input :id="`line-${index}`" v-model="draftLines[index]" type="text" maxlength="100" />
              </template>
            </div>
            <div class="button-row">
              <button type="submit" class="btn btn-primary" :disabled="busy">Speichern</button>
              <button type="button" class="btn btn-outline" @click="generateLines">Adresszeilen erzeugen</button>
              <button type="button" class="btn btn-secondary" @click="editing = null">Abbrechen</button>
            </div>
          </form>
          <template v-else>
            <!-- Leere Zeilen mittendrin als geschütztes Leerzeichen, sonst fielen sie weg. -->
            <div class="address-lines">
              <div v-for="(line, index) in visibleAddressLines" :key="index">{{ line || ' ' }}</div>
            </div>
            <div v-if="canEdit" class="button-row">
              <button type="button" class="btn btn-outline" @click="startEdit('addressLines')">Bearbeiten</button>
            </div>
          </template>
        </div>
      </div>

      <div class="card">
        <div class="card-header">Briefanrede und Post</div>
        <div class="card-content">
          <form v-if="editing === 'salutation'" @submit.prevent="saveSalutation">
            <div class="form-group">
              <label for="salutation">Abweichende Briefanrede</label>
              <input id="salutation" v-model="draftSalutation" type="text" maxlength="100" />
              <p class="hint">Leer lassen, dann wird die Anrede aus Name und Geschlecht erzeugt.</p>
            </div>
            <div class="button-row">
              <button type="submit" class="btn btn-primary" :disabled="busy">Speichern</button>
              <button type="button" class="btn btn-secondary" @click="editing = null">Abbrechen</button>
            </div>
          </form>
          <dl v-else>
            <dt>Briefanrede</dt>
            <dd>
              {{ member.salutation }}
              <span v-if="member.salutation_override" class="status-tag info">abweichend</span>
              <button v-if="canEdit" type="button" class="btn btn-outline btn-inline" @click="startEdit('salutation')">
                Bearbeiten
              </button>
            </dd>
            <dt>Keine Post</dt>
            <dd>
              {{ member.no_mail ? 'ja, keine Einladungen per Seriendruck' : 'nein' }}
              <button v-if="canEdit" type="button" class="btn btn-outline btn-inline" :disabled="busy" @click="toggleNoMail">
                {{ member.no_mail ? 'Aufheben' : 'Setzen' }}
              </button>
            </dd>
          </dl>
        </div>
      </div>

      <div class="card">
        <div class="card-header">Hinweise</div>
        <div class="card-content">
          <form v-if="editing === 'notes'" @submit.prevent="saveNotes">
            <div class="form-group">
              <label for="notes">Hinweise</label>
              <textarea id="notes" v-model="draftNotes" rows="6" maxlength="5000"></textarea>
            </div>
            <div class="button-row">
              <button type="submit" class="btn btn-primary" :disabled="busy">Speichern</button>
              <button type="button" class="btn btn-secondary" @click="editing = null">Abbrechen</button>
            </div>
          </form>
          <template v-else>
            <!-- pre-line: Zeilenumbrüche aus dem Text bleiben erhalten. -->
            <p class="notes">{{ member.notes || 'keine' }}</p>
            <div v-if="canEdit" class="button-row">
              <button type="button" class="btn btn-outline" @click="startEdit('notes')">Bearbeiten</button>
            </div>
          </template>
        </div>
      </div>
    </template>
  </div>
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

.address-lines {
  margin-bottom: 0.8rem;
}

.hint {
  color: var(--text-label);
}

.too-long {
  color: var(--error-color);
  font-weight: normal;
}

/* Kleiner Knopf hinter einem Wert in derselben Zeile. */
.btn-inline {
  margin-left: 0.8rem;
  padding: 2px 8px;
  font-size: 0.85rem;
}
</style>
