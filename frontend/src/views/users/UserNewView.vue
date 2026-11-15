<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { errorText } from '../../api'
import { ACCOUNTING } from '../../auth'
import { listRoles, registerUser, type Role } from '../../users'

const router = useRouter()

const roles = ref<Role[]>([])
const username = ref('')
const fullName = ref('')
const password = ref('')
const role = ref(ACCOUNTING)
const error = ref('')
const busy = ref(false)

onMounted(async () => {
  try {
    roles.value = await listRoles()
  } catch (e) {
    error.value = errorText(e)
  }
})

async function submit(): Promise<void> {
  error.value = ''
  busy.value = true
  try {
    const user = await registerUser(username.value, fullName.value, password.value, role.value)
    await router.push({ name: 'user-edit', params: { id: user.id } })
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="card card-center">
    <div class="card-header">Neuer Benutzer</div>
    <div class="card-content">
      <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
      <form @submit.prevent="submit">
        <div class="form-group">
          <label for="username">Benutzername</label>
          <input id="username" v-model="username" type="text" autocomplete="off" required autofocus />

          <label for="full-name">Name</label>
          <input id="full-name" v-model="fullName" type="text" autocomplete="off" required />

          <label for="password">Kennwort</label>
          <input id="password" v-model="password" type="password" autocomplete="new-password" required />

          <label for="role">Rolle</label>
          <select id="role" v-model="role">
            <option v-for="r in roles" :key="r.value" :value="r.value">{{ r.label }}</option>
          </select>

          <div class="button-row">
            <button type="submit" class="btn btn-primary" :disabled="busy">Anlegen</button>
            <RouterLink :to="{ name: 'users' }" class="btn btn-secondary">Abbrechen</RouterLink>
          </div>
        </div>
      </form>
    </div>
  </div>
</template>
