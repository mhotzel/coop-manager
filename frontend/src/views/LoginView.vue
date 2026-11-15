<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '../api'
import { login } from '../auth'

const route = useRoute()
const router = useRouter()

// v-model im Formular hält diese Werte und die Eingabefelder gegenseitig aktuell.
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit(): Promise<void> {
  error.value = ''
  busy.value = true
  try {
    await login(username.value, password.value)
    await router.push(safeNext(route.query.next))
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Der Server ist nicht erreichbar.'
    password.value = ''
  } finally {
    busy.value = false
  }
}

// Nach dem Login nur zu Pfaden dieser Seite weiterleiten, nie zu fremden Adressen
// (wie safe_next_url in purchase-prices). "//boese.example" wäre sonst eine fremde Seite.
function safeNext(next: unknown): string {
  if (typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') && !next.includes('\\')) {
    return next
  }
  return '/'
}
</script>

<template>
  <div class="card card-center">
    <div class="card-header"><p>Anmelden</p></div>
    <div class="card-content">
      <div v-if="error" class="status-box error">
        <p>{{ error }}</p>
      </div>
      <!-- .prevent: Der Browser schickt das Formular nicht selbst ab, das macht submit(). -->
      <form @submit.prevent="submit">
        <div class="form-group">
          <label for="username">Benutzername</label>
          <input id="username" v-model="username" type="text" autocomplete="username" required autofocus />

          <label for="password">Kennwort</label>
          <input id="password" v-model="password" type="password" autocomplete="current-password" required />

          <div class="button-row">
            <button type="submit" class="btn btn-primary" :disabled="busy">Anmelden</button>
          </div>
        </div>
      </form>
    </div>
  </div>
</template>
