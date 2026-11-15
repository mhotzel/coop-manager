import { createRouter, createWebHistory } from 'vue-router'

import { currentUser } from './auth'
import HomeView from './views/HomeView.vue'
import LoginView from './views/LoginView.vue'

export const router = createRouter({
  // Echte Pfade wie /login statt /#/login. Im Betrieb muss FastAPI dafür index.html ausliefern.
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
  ],
})

// Navigation Guard: läuft vor jedem Seitenwechsel. Rückgabe einer Route = stattdessen dorthin.
router.beforeEach((to) => {
  if (!to.meta.public && currentUser.value === null) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.name === 'login' && currentUser.value !== null) {
    return { name: 'home' }
  }
})
