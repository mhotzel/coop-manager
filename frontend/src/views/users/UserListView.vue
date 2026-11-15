<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { errorText } from '../../api'
import type { User } from '../../auth'
import { listRoles, listUsers, roleLabel, type Role } from '../../users'

const users = ref<User[]>([])
const roles = ref<Role[]>([])
const error = ref('')

onMounted(async () => {
  try {
    // Promise.all: beide Anfragen gleichzeitig abschicken und auf beide warten.
    const [loadedUsers, loadedRoles] = await Promise.all([listUsers(), listRoles()])
    users.value = loadedUsers
    roles.value = loadedRoles
  } catch (e) {
    error.value = errorText(e)
  }
})
</script>

<template>
  <div class="card">
    <div class="card-header">Benutzer</div>
    <div class="card-content">
      <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
      <div class="button-row">
        <RouterLink :to="{ name: 'user-new' }" class="btn btn-primary">Neuer Benutzer</RouterLink>
      </div>
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Benutzername</th>
              <th>Name</th>
              <th>Rolle</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td>
                <RouterLink :to="{ name: 'user-edit', params: { id: user.id } }">{{ user.username }}</RouterLink>
              </td>
              <td>{{ user.full_name }}</td>
              <td>{{ roleLabel(roles, user.role) }}</td>
              <td>
                <span v-if="user.active" class="status-tag info">aktiv</span>
                <span v-else class="status-tag warning">deaktiviert</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
