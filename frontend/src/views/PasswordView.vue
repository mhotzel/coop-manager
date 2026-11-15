<script setup lang="ts">
import { ref } from 'vue'

import { errorText } from '../api'
import { changeOwnPassword } from '../auth'

const currentPassword = ref('')
const newPassword = ref('')
const repeated = ref('')
const message = ref('')
const error = ref('')
const busy = ref(false)

async function submit(): Promise<void> {
  message.value = ''
  error.value = ''
  // Nur Komfort: Tippfehler gleich hier bemerken. Die Regeln für Kennwörter prüft das Backend.
  if (newPassword.value !== repeated.value) {
    error.value = 'Die beiden neuen Kennwörter stimmen nicht überein.'
    return
  }
  busy.value = true
  try {
    await changeOwnPassword(currentPassword.value, newPassword.value)
    message.value = 'Dein Kennwort wurde geändert.'
  } catch (e) {
    error.value = errorText(e)
  } finally {
    // Kennwörter nicht im Formular stehen lassen, auch nicht nach einem Fehler.
    currentPassword.value = ''
    newPassword.value = ''
    repeated.value = ''
    busy.value = false
  }
}
</script>

<template>
  <div class="card-center">
    <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
    <div v-if="message" class="status-box info"><p>{{ message }}</p></div>

    <div class="card">
      <div class="card-header">Kennwort ändern</div>
      <div class="card-content">
        <form @submit.prevent="submit">
          <div class="form-group">
            <label for="current-password">Bisheriges Kennwort</label>
            <input
              id="current-password"
              v-model="currentPassword"
              type="password"
              autocomplete="current-password"
              required
              autofocus
            />

            <label for="new-password">Neues Kennwort</label>
            <input id="new-password" v-model="newPassword" type="password" autocomplete="new-password" required />

            <label for="repeated">Neues Kennwort wiederholen</label>
            <input id="repeated" v-model="repeated" type="password" autocomplete="new-password" required />

            <p>Mindestens 8 Zeichen mit Klein- und Großbuchstaben, einer Ziffer und einem Sonderzeichen.</p>

            <div class="button-row">
              <button type="submit" class="btn btn-primary" :disabled="busy">Kennwort ändern</button>
            </div>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
