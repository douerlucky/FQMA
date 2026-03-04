import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { io } from 'socket.io-client'

import App from './App.vue'
import router from './router'

const socket = io('http://localhost:5000', {
  transports: ['websocket', 'polling'],
  withCredentials: false
});

const app = createApp(App)

app.config.globalProperties.$socket = socket;
app.use(createPinia())
app.use(router)

app.mount('#app')
