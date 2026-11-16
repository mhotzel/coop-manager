<script setup lang="ts">
// Eingabefelder für den Namen; genutzt beim Antrag und beim Bearbeiten.
import { computed } from 'vue'

import { GENDER_LABELS, NATURAL_PERSON, type PersonName } from '../../members'

// defineModel: Die Elternseite bindet mit v-model="…" ein PersonName-Objekt an. Die Felder hier
// ändern direkt dessen Eigenschaften, die Elternseite sieht die Änderungen sofort.
const name = defineModel<PersonName>({ required: true })
// Die Art der Person bestimmt, welche Felder Pflicht sind (wie validate_name im Backend).
const props = defineProps<{ personType: string }>()

const isNatural = computed(() => props.personType === NATURAL_PERSON)
</script>

<template>
  <div class="form-group">
    <template v-if="!isNatural">
      <label for="company-name">Firma</label>
      <input id="company-name" v-model="name.company_name" type="text" maxlength="100" required />
      <p class="hint">Ansprechpartner (optional):</p>
    </template>

    <div class="form-row">
      <div class="form-group">
        <label for="title">Titel</label>
        <input id="title" v-model="name.title" type="text" maxlength="30" />
      </div>
      <div class="form-group">
        <label for="gender">Geschlecht</label>
        <select id="gender" v-model="name.gender">
          <option v-for="(label, value) in GENDER_LABELS" :key="value" :value="value">{{ label }}</option>
        </select>
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label for="first-names">Vornamen</label>
        <input id="first-names" v-model="name.first_names" type="text" maxlength="100" :required="isNatural" />
      </div>
      <div class="form-group">
        <label for="last-name">Nachname</label>
        <input id="last-name" v-model="name.last_name" type="text" maxlength="100" :required="isNatural" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.hint {
  margin: 0.4rem 0 0;
  color: var(--text-label);
}
</style>
