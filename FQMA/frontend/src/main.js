import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { io } from 'socket.io-client'

import App from './App.vue'
import router from './router'

const socket = io('http://127.0.0.1:5000'); // 端口如有变动请同步

const app = createApp(App)

app.config.globalProperties.$socket = socket;
app.use(createPinia())
app.use(router)

app.mount('#app')
