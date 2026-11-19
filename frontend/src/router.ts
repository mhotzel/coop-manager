import { createRouter, createWebHistory } from 'vue-router'

import { ACCOUNTING, ACCOUNTING_READONLY, ADMIN, currentUser } from './auth'
import AccountView from './views/accounts/AccountView.vue'
import OpenClaimsView from './views/accounts/OpenClaimsView.vue'
import YearEndView from './views/accounts/YearEndView.vue'
import HomeView from './views/HomeView.vue'
import LoginView from './views/LoginView.vue'
import MemberApplyView from './views/members/MemberApplyView.vue'
import MemberDetailView from './views/members/MemberDetailView.vue'
import MemberSearchView from './views/members/MemberSearchView.vue'
import PasswordView from './views/PasswordView.vue'
import ReportsView from './views/reports/ReportsView.vue'
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
    {
      path: '/members',
      name: 'members',
      component: MemberSearchView,
      meta: { roles: [ACCOUNTING, ACCOUNTING_READONLY] },
    },
    // Fester Pfad: gewinnt gegen /members/:id, egal in welcher Reihenfolge.
    { path: '/members/new', name: 'member-new', component: MemberApplyView, meta: { roles: [ACCOUNTING] } },
    {
      path: '/members/:id',
      name: 'member-detail',
      component: MemberDetailView,
      props: true,
      meta: { roles: [ACCOUNTING, ACCOUNTING_READONLY] },
    },
    {
      path: '/accounts/:number',
      name: 'account',
      component: AccountView,
      props: true,
      meta: { roles: [ACCOUNTING, ACCOUNTING_READONLY] },
    },
    { path: '/year-end', name: 'year-end', component: YearEndView, meta: { roles: [ACCOUNTING, ACCOUNTING_READONLY] } },
    { path: '/claims', name: 'claims', component: OpenClaimsView, meta: { roles: [ACCOUNTING, ACCOUNTING_READONLY] } },
    { path: '/reports', name: 'reports', component: ReportsView, meta: { roles: [ACCOUNTING, ACCOUNTING_READONLY] } },
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
