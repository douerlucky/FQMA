import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { io } from 'socket.io-client'

import App from './App.vue'
import router from './router'

const runtimeHost = window.location.hostname || 'localhost'
const runtimeProtocol = window.location.protocol === 'https:' ? 'https' : 'http'
const socketBaseUrl = import.meta.env.VITE_SOCKET_BASE_URL || `${runtimeProtocol}://${runtimeHost}:5001`

const socket = io(socketBaseUrl, {
  transports: ['websocket', 'polling'],
  withCredentials: false
});

const app = createApp(App)

app.config.globalProperties.$socket = socket;
app.use(createPinia())
app.use(router)

app.mount('#app')
