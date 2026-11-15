import { createRouter, createWebHistory } from 'vue-router'

import { ADMIN, currentUser } from './auth'
import HomeView from './views/HomeView.vue'
import LoginView from './views/LoginView.vue'
import PasswordView from './views/PasswordView.vue'
import UserEditView from './views/users/UserEditView.vue'
import UserListView from './views/users/UserListView.vue'
import UserNewView from './views/users/UserNewView.vue'

// Eigene Angaben je Route in `meta`; hier machen wir TypeScript mit ihren Typen bekannt.
declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean // ohne Anmeldung erreichbar
    roles?: string[] // nur für diese Rollen; fehlt die Angabe, reicht die Anmeldung
  }
}

export const router = createRouter({
  // Echte Pfade wie /login statt /#/login. Im Betrieb muss FastAPI dafür index.html ausliefern.
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    // Ohne roles: Jeder Angemeldete darf sein Kennwort ändern.
    { path: '/password', name: 'password', component: PasswordView },
    { path: '/users', name: 'users', component: UserListView, meta: { roles: [ADMIN] } },
    // Anders als in FastAPI egal, ob vor oder nach /users/:id: Feste Pfade gewinnen immer.
    { path: '/users/new', name: 'user-new', component: UserNewView, meta: { roles: [ADMIN] } },
    // props: true gibt :id als Prop an die Komponente weiter.
    { path: '/users/:id', name: 'user-edit', component: UserEditView, props: true, meta: { roles: [ADMIN] } },
  ],
})

// Navigation Guard: läuft vor jedem Seitenwechsel. Rückgabe einer Route = stattdessen dorthin.
// Das ist nur Komfort; verbindlich prüft das Backend.
router.beforeEach((to) => {
  const user = currentUser.value
  if (!to.meta.public && user === null) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.name === 'login' && user !== null) {
    return { name: 'home' }
  }
  if (to.meta.roles && user !== null && !to.meta.roles.includes(user.role)) {
    return { name: 'home' }
  }
})
