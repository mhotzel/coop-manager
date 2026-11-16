<script setup lang="ts">
// Eingabefelder für die Anschrift; genutzt beim Antrag und beim Bearbeiten.
import type { Address } from '../../members'

// Siehe NameFields.vue: v-model an der Elternseite, die Felder ändern das Objekt direkt.
const address = defineModel<Address>({ required: true })
</script>

<template>
  <div class="form-group">
    <div class="form-row">
      <div class="form-group street">
        <label for="street">Straße</label>
        <input id="street" v-model="address.street" type="text" maxlength="100" required />
      </div>
      <div class="form-group">
        <label for="house-number">Hausnummer</label>
        <input id="house-number" v-model="address.house_number" type="text" maxlength="20" />
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label for="postal-code">PLZ</label>
        <input id="postal-code" v-model="address.postal_code" type="text" maxlength="20" required />
      </div>
      <div class="form-group city">
        <label for="city">Ort</label>
        <input id="city" v-model="address.city" type="text" maxlength="100" required />
      </div>
    </div>
    <label for="country">Land (leer = Deutschland)</label>
    <input id="country" v-model="address.country" type="text" maxlength="50" />
  </div>
</template>

<style scoped>
/* Straße und Ort bekommen mehr Platz als Hausnummer und PLZ. */
.form-row .street,
.form-row .city {
  flex: 3;
}
</style>
