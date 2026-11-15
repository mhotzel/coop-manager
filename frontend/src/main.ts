import { createApp } from 'vue'

import App from './App.vue'
import { onUnauthorized } from './api'
import { currentUser, forget, loadMe } from './auth'
import { router } from './router'

// Reihenfolge wichtig: erst die Farbvariablen, dann das CSS, das sie verwendet.
import './assets/css/colorscheme-dorfladen.css'
import './assets/css/style.css'

// Meldet das Backend 401, obwohl jemand angemeldet war, ist die Session abgelaufen: zur Anmeldung.
onUnauthorized(() => {
  if (currentUser.value !== null) {
    forget()
    void router.push({ name: 'login', query: { next: router.currentRoute.value.fullPath } })
  }
})

// Erst fragen, ob noch eine Session besteht, dann die App einhängen. So entscheidet der Router
// gleich richtig und die Anmeldeseite blitzt nicht kurz auf.
try {
  await loadMe()
} catch (error) {
  console.error('Backend nicht erreichbar', error)
}
createApp(App).use(router).mount('#app')
