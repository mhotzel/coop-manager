<script setup lang="ts">
// Eingabefelder für Telefon und E-Mail; genutzt beim Antrag und beim Bearbeiten.
import type { Contact } from '../../members'

// Siehe NameFields.vue: v-model an der Elternseite, die Felder ändern das Objekt direkt.
const contact = defineModel<Contact>({ required: true })
</script>

<template>
  <div class="form-row">
    <div class="form-group">
      <label for="phone">Telefon</label>
      <input id="phone" v-model="contact.phone" type="tel" maxlength="30" />
    </div>
    <div class="form-group">
      <label for="email">E-Mail</label>
      <input id="email" v-model="contact.email" type="email" maxlength="100" />
    </div>
  </div>
</template>
