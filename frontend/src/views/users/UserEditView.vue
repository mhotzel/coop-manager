<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { errorText } from '../../api'
import { currentUser, type User } from '../../auth'
import * as users from '../../users'

// Der Router übergibt :id aus dem Pfad als Prop (siehe props: true in router.ts).
const props = defineProps<{ id: string }>()
const router = useRouter()

const user = ref<User | null>(null)
const roles = ref<users.Role[]>([])
const fullName = ref('')
const role = ref('')
const password = ref('')
const message = ref('')
const error = ref('')
const busy = ref(false)

// computed: wird automatisch neu berechnet, wenn sich user oder currentUser ändern.
const isSelf = computed(() => user.value?.id === currentUser.value?.id)

function show(loaded: User): void {
  user.value = loaded
  fullName.value = loaded.full_name
  role.value = loaded.role
}

onMounted(async () => {
  try {
    const [loaded, loadedRoles] = await Promise.all([users.getUser(props.id), users.listRoles()])
    roles.value = loadedRoles
    show(loaded)
  } catch (e) {
    error.value = errorText(e)
  }
})

// Führt einen Befehl aus und zeigt danach Erfolg oder Fehler an. So steht das nur einmal hier.
async function run(command: () => Promise<User>, success: string): Promise<void> {
  message.value = ''
  error.value = ''
  busy.value = true
  try {
    show(await command())
    message.value = success
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = false
  }
}

// Die Befehle dieser Seite; die Vorlage ruft nur diese Funktionen auf.
const saveFullName = () => run(() => users.changeFullName(props.id, fullName.value), 'Der Name wurde geändert.')
const saveRole = () => run(() => users.changeRole(props.id, role.value), 'Die Rolle wurde geändert.')
const deactivate = () => run(() => users.deactivate(props.id), 'Der Benutzer wurde deaktiviert.')
const reactivate = () => run(() => users.reactivate(props.id), 'Der Benutzer wurde reaktiviert.')

async function savePassword(): Promise<void> {
  await run(() => users.changePassword(props.id, password.value), 'Das Kennwort wurde neu gesetzt.')
  password.value = ''
}

async function terminate(): Promise<void> {
  if (!user.value || !confirm(`Benutzer „${user.value.username}“ endgültig löschen?`)) {
    return
  }
  try {
    await users.terminate(props.id)
    await router.push({ name: 'users' })
  } catch (e) {
    error.value = errorText(e)
  }
}
</script>

<template>
  <!-- card-center: Die ganze Seite steht mittig, Meldungen und Buttons eingeschlossen. -->
  <div class="card-center">
    <div v-if="error" class="status-box error"><p>{{ error }}</p></div>
    <div v-if="message" class="status-box info"><p>{{ message }}</p></div>

    <template v-if="user">
      <div class="card">
        <div class="card-header">
          Benutzer „{{ user.username }}“
          <span v-if="!user.active" class="status-tag warning">deaktiviert</span>
        </div>
        <div class="card-content">
          <form @submit.prevent="saveFullName">
            <div class="form-group">
              <label for="full-name">Name</label>
              <input id="full-name" v-model="fullName" type="text" required />
              <div class="button-row">
                <button type="submit" class="btn btn-primary" :disabled="busy">Name ändern</button>
              </div>
            </div>
          </form>

          <form @submit.prevent="saveRole">
            <div class="form-group">
              <label for="role">Rolle</label>
              <select id="role" v-model="role">
                <option v-for="r in roles" :key="r.value" :value="r.value">{{ r.label }}</option>
              </select>
              <div class="button-row">
                <button type="submit" class="btn btn-primary" :disabled="busy || role === user.role">Rolle ändern</button>
              </div>
            </div>
          </form>

          <form @submit.prevent="savePassword">
            <div class="form-group">
              <label for="password">Neues Kennwort</label>
              <input id="password" v-model="password" type="password" autocomplete="new-password" required />
              <div class="button-row">
                <button type="submit" class="btn btn-primary" :disabled="busy">Kennwort setzen</button>
              </div>
            </div>
          </form>
        </div>
      </div>

      <!-- Wie in purchase-prices: sich selbst kann man nicht deaktivieren oder löschen. -->
      <div v-if="!isSelf" class="card">
        <div class="card-header">Status</div>
        <div class="card-content">
          <div class="button-row">
            <button v-if="user.active" type="button" class="btn btn-secondary" :disabled="busy" @click="deactivate">
              Deaktivieren
            </button>
            <template v-else>
              <button type="button" class="btn btn-secondary" :disabled="busy" @click="reactivate">Reaktivieren</button>
              <button type="button" class="btn btn-secondary" :disabled="busy" @click="terminate">Löschen</button>
            </template>
          </div>
        </div>
      </div>
    </template>

    <div class="button-row">
      <RouterLink :to="{ name: 'users' }" class="btn btn-secondary">Zurück zur Liste</RouterLink>
    </div>
  </div>
</template>
