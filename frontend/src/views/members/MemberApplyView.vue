<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { errorText } from '../../api'
import * as members from '../../members'
import { NATURAL_PERSON, PERSON_TYPE_LABELS, type Address, type Contact, type PersonName } from '../../members'
import AddressFields from './AddressFields.vue'
import ContactFields from './ContactFields.vue'
import NameFields from './NameFields.vue'

const router = useRouter()

const personType = ref(NATURAL_PERSON)
const name = ref<PersonName>({ company_name: '', title: '', first_names: '', last_name: '', gender: '' })
const address = ref<Address>({ street: '', house_number: '', postal_code: '', city: '', country: '' })
const contact = ref<Contact>({ phone: '', email: '' })
const applicationDate = ref(members.todayIso())
const sharesSubscribed = ref(1)
const error = ref('')
const busy = ref(false)

async function submit(): Promise<void> {
  error.value = ''
  busy.value = true
  try {
    // Wer erst „juristisch“ gewählt und eine Firma eingetragen hat, dann „natürlich“: Das
    // Firmenfeld ist dann ausgeblendet, sein Inhalt darf aber nicht mitgeschickt werden.
    const companyName = personType.value === NATURAL_PERSON ? '' : name.value.company_name
    const member = await members.applyForMembership({
      person_type: personType.value,
      name: { ...name.value, company_name: companyName },
      address: address.value,
      contact: contact.value,
      application_date: applicationDate.value,
      shares_subscribed: sharesSubscribed.value,
    })
    // replace statt push: „Zurück“ im Browser soll nicht wieder im ausgefüllten Formular landen.
    await router.replace({ name: 'member-detail', params: { id: member.id } })
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="card card-center">
    <div class="card-header">Neuer Antrag</div>
    <div class="card-content">
      <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
      <form @submit.prevent="submit">
        <fieldset>
          <legend>Art der Person</legend>
          <label v-for="(label, value) in PERSON_TYPE_LABELS" :key="value" class="radio">
            <input v-model="personType" type="radio" name="person-type" :value="value" />
            {{ label }}
          </label>
        </fieldset>

        <fieldset>
          <legend>{{ personType === NATURAL_PERSON ? 'Name' : 'Firma und Ansprechpartner' }}</legend>
          <NameFields v-model="name" :person-type="personType" />
        </fieldset>

        <fieldset>
          <legend>Anschrift</legend>
          <AddressFields v-model="address" />
        </fieldset>

        <fieldset>
          <legend>Kontakt</legend>
          <ContactFields v-model="contact" />
        </fieldset>

        <fieldset>
          <legend>Antrag</legend>
          <div class="form-row">
            <div class="form-group">
              <label for="application-date">Antrag vom</label>
              <input id="application-date" v-model="applicationDate" type="date" required />
            </div>
            <div class="form-group">
              <label for="shares">Gezeichnete Anteile</label>
              <!-- v-model.number: Der Wert kommt als Zahl an, nicht als Text "1". -->
              <input id="shares" v-model.number="sharesSubscribed" type="number" min="1" step="1" required />
            </div>
          </div>
        </fieldset>

        <p class="hint">Die Mitgliedsnummer vergibt das System beim Speichern.</p>
        <div class="button-row">
          <button type="submit" class="btn btn-primary" :disabled="busy">Antrag speichern</button>
          <RouterLink :to="{ name: 'members' }" class="btn btn-secondary">Abbrechen</RouterLink>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
fieldset {
  border: none;
  margin: 0 0 1rem;
  padding: 0;
}

legend {
  font-weight: 600;
  margin-bottom: 0.4rem;
}

.radio {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  margin-right: 1.5rem;
  font-weight: normal;
}

.hint {
  color: var(--text-label);
}
</style>
