import { createApp } from 'vue'
import App from './App.vue'

// Reihenfolge wichtig: erst die Farbvariablen, dann das CSS, das sie verwendet.
import './assets/css/colorscheme-dorfladen.css'
import './assets/css/style.css'

createApp(App).mount('#app')
