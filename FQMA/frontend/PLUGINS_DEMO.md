# GeneTi-Maid 前端插件 Demo

## 概述

本项目使用了多个现代化的前端插件，提供丰富的功能和优秀的开发体验。以下是各个插件的详细介绍和demo。

## 核心依赖插件

### 1. Vue 3 + Vue Router

**功能**: 现代化的前端框架和路由管理

**Demo**:
```vue
<!-- App.vue -->
<template>
  <div id="app">
    <router-view></router-view>
  </div>
</template>

<script>
import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'

// 路由配置
const routes = [
  { path: '/', component: Home },
  { path: '/chat', component: Chat }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const app = createApp(App)
app.use(router)
app.mount('#app')
</script>
```

### 2. Pinia (状态管理)

**功能**: Vue 3 官方推荐的状态管理库

**Demo**:
```javascript
// stores/counter.js
import { defineStore } from 'pinia'

export const useCounterStore = defineStore('counter', {
  state: () => ({
    count: 0,
    queryHistory: []
  }),
  
  getters: {
    doubleCount: (state) => state.count * 2,
    recentQueries: (state) => state.queryHistory.slice(0, 5)
  },
  
  actions: {
    increment() {
      this.count++
    },
    addQuery(query) {
      this.queryHistory.unshift(query)
    }
  }
})
```

### 3. Axios (HTTP 客户端)

**功能**: 强大的 HTTP 请求库

**Demo**:
```javascript
// api/query.js
import axios from 'axios'

// 创建实例
const api = axios.create({
  baseURL: 'http://localhost:5000/api',
  timeout: 30000
})

// 请求拦截器
api.interceptors.request.use(config => {
  console.log('发送请求:', config.url)
  return config
})

// 响应拦截器
api.interceptors.response.use(
  response => {
    console.log('收到响应:', response.status)
    return response
  },
  error => {
    console.error('请求失败:', error)
    return Promise.reject(error)
  }
)

// API 方法
export const queryAPI = {
  // 发送查询
  async sendQuery(question, sessionId, messageId) {
    const response = await api.post('/query', {
      question,
      session_id: sessionId,
      message_id: messageId
    })
    return response.data
  },
  
  // 获取历史记录
  async getHistory(sessionId) {
    const response = await api.get(`/history/${sessionId}`)
    return response.data
  },
  
  // 健康检查
  async healthCheck() {
    const response = await api.get('/health')
    return response.data
  }
}
```

### 4. Socket.IO Client (WebSocket)

**功能**: 实时双向通信

**Demo**:
```javascript
// socket/connection.js
import { io } from 'socket.io-client'

class SocketManager {
  constructor() {
    this.socket = null
    this.isConnected = false
  }
  
  connect(url = 'http://localhost:5000') {
    this.socket = io(url, {
      transports: ['websocket', 'polling'],
      timeout: 20000
    })
    
    // 连接事件
    this.socket.on('connect', () => {
      console.log('✅ WebSocket 连接成功')
      this.isConnected = true
    })
    
    this.socket.on('disconnect', () => {
      console.log('❌ WebSocket 连接断开')
      this.isConnected = false
    })
    
    this.socket.on('connect_error', (error) => {
      console.error('WebSocket 连接错误:', error)
    })
    
    return this.socket
  }
  
  // 监听思考过程
  onThinking(callback) {
    if (!this.socket) return
    
    this.socket.on('thinking', (data) => {
      console.log('收到思考数据:', data)
      callback(data)
    })
  }
  
  // 发送消息
  emit(event, data) {
    if (this.socket && this.isConnected) {
      this.socket.emit(event, data)
    }
  }
  
  disconnect() {
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }
  }
}

export const socketManager = new SocketManager()
```

### 5. Marked (Markdown 解析)

**功能**: 将 Markdown 转换为 HTML

**Demo**:
```javascript
// utils/markdown.js
import { marked } from 'marked'

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
  sanitize: false
})

// 自定义渲染器
const renderer = new marked.Renderer()

// 自定义代码块渲染
renderer.code = (code, language) => {
  return `<pre class="language-${language}"><code>${code}</code></pre>`
}

// 自定义表格渲染
renderer.table = (header, body) => {
  return `
    <div class="table-wrapper">
      <table class="result-table">
        <thead>${header}</thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `
}

marked.use({ renderer })

export const markdownUtils = {
  // 解析 Markdown
  parse(markdown) {
    return marked.parse(markdown || '')
  },
  
  // 解析表格数据
  parseTable(markdown) {
    const html = this.parse(markdown)
    return html
  },
  
  // 安全解析（移除脚本标签）
  safeParse(markdown) {
    const html = this.parse(markdown)
    return html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
  }
}
```

### 6. Highlight.js (代码高亮)

**功能**: 代码语法高亮

**Demo**:
```javascript
// utils/highlight.js
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'

export const highlightUtils = {
  // 初始化高亮
  init() {
    // 自动检测语言
    hljs.highlightAll()
  },
  
  // 手动高亮代码块
  highlight(code, language = 'javascript') {
    try {
      return hljs.highlight(code, { language }).value
    } catch (error) {
      return hljs.highlight(code, { language: 'plaintext' }).value
    }
  },
  
  // 高亮页面中的所有代码块
  highlightAll() {
    document.querySelectorAll('pre code').forEach((block) => {
      hljs.highlightElement(block)
    })
  },
  
  // 获取支持的语言列表
  getSupportedLanguages() {
    return hljs.listLanguages()
  }
}
```

### 7. UUID (唯一标识符)

**功能**: 生成唯一标识符

**Demo**:
```javascript
// utils/uuid.js
import { v4 as uuidv4 } from 'uuid'

export const uuidUtils = {
  // 生成 UUID
  generate() {
    return uuidv4()
  },
  
  // 生成短 UUID
  generateShort() {
    return uuidv4().split('-')[0]
  },
  
  // 验证 UUID 格式
  isValid(uuid) {
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    return uuidRegex.test(uuid)
  },
  
  // 批量生成
  generateMultiple(count) {
    return Array.from({ length: count }, () => uuidv4())
  }
}
```

## 开发工具插件

### 8. Vite (构建工具)

**功能**: 现代化的前端构建工具

**Demo**:
```javascript
// vite.config.js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { devtools } from 'vite-plugin-vue-devtools'

export default defineConfig({
  plugins: [
    vue(),
    devtools()
  ],
  
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  },
  
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          utils: ['axios', 'marked', 'highlight.js']
        }
      }
    }
  }
})
```

### 9. ESLint (代码检查)

**功能**: 代码质量检查和格式化

**Demo**:
```javascript
// eslint.config.js
import js from '@eslint/js'
import globals from 'globals'
import vue from 'eslint-plugin-vue'

export default [
  js.configs.recommended,
  {
    files: ['**/*.vue'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.es2021
      }
    },
    plugins: {
      vue
    },
    rules: {
      ...vue.configs.recommended.rules,
      'vue/no-unused-vars': 'error',
      'vue/component-name-in-template-casing': ['error', 'PascalCase'],
      'vue/component-definition-name-casing': ['error', 'PascalCase']
    }
  }
]
```

### 10. Prettier (代码格式化)

**功能**: 代码自动格式化

**Demo**:
```json
// .prettierrc
{
  "semi": false,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 80,
  "bracketSpacing": true,
  "arrowParens": "avoid",
  "vueIndentScriptAndStyle": true
}
```

## 综合使用示例

### 完整的消息处理组件

```vue
<!-- components/MessageHandler.vue -->
<template>
  <div class="message-handler">
    <!-- 消息列表 -->
    <div class="messages">
      <div
        v-for="message in messages"
        :key="message.id"
        class="message"
        :class="message.type"
      >
        <!-- 用户消息 -->
        <div v-if="message.type === 'user'" class="user-message">
          {{ message.content }}
        </div>
        
        <!-- AI 消息 -->
        <div v-else class="ai-message">
          <!-- 思考过程 -->
          <ThinkingProcess 
            v-if="message.thinking"
            :thinking="message.thinking"
            :loading="message.loading"
          />
          
          <!-- 结果内容 -->
          <div v-if="message.tables" class="result-content">
            <div v-html="parseMarkdown(message.tables)" class="tables"></div>
          </div>
          
          <div v-if="message.explanation" class="explanation">
            <div v-html="parseMarkdown(message.explanation)"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, nextTick } from 'vue'
import { useCounterStore } from '@/stores/counter'
import { socketManager } from '@/socket/connection'
import { markdownUtils } from '@/utils/markdown'
import { highlightUtils } from '@/utils/highlight'
import { uuidUtils } from '@/utils/uuid'
import ThinkingProcess from './ThinkingProcess.vue'

export default {
  name: 'MessageHandler',
  components: {
    ThinkingProcess
  },
  
  setup() {
    const store = useCounterStore()
    const messages = ref([])
    
    // 解析 Markdown
    const parseMarkdown = (text) => {
      return markdownUtils.safeParse(text)
    }
    
    // 处理新消息
    const handleNewMessage = (message) => {
      const messageId = uuidUtils.generate()
      const newMessage = {
        id: messageId,
        type: 'system',
        content: message.content,
        timestamp: new Date().toISOString()
      }
      
      messages.value.push(newMessage)
      store.addQuery(newMessage)
      
      // 高亮代码块
      nextTick(() => {
        highlightUtils.highlightAll()
      })
    }
    
    // 初始化 WebSocket
    onMounted(() => {
      const socket = socketManager.connect()
      
      socket.on('thinking', (data) => {
        console.log('收到思考数据:', data)
        // 处理思考过程数据
      })
    })
    
    return {
      messages,
      parseMarkdown,
      handleNewMessage
    }
  }
}
</script>

<style scoped>
.message-handler {
  height: 100%;
  overflow-y: auto;
}

.messages {
  padding: 20px;
}

.message {
  margin-bottom: 16px;
}

.user-message {
  text-align: right;
  color: #333;
}

.ai-message {
  text-align: left;
  color: #666;
}

.result-content {
  margin-top: 12px;
}

.explanation {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.6;
}
</style>
```

## 插件使用建议

### 1. 性能优化
- 使用 Vite 的代码分割功能
- 合理使用 Pinia 的状态管理
- 避免不必要的 WebSocket 重连

### 2. 代码质量
- 启用 ESLint 的严格模式
- 使用 Prettier 保持代码风格一致
- 定期运行代码检查

### 3. 开发体验
- 使用 Vue DevTools 调试
- 利用 Vite 的热重载功能
- 合理组织代码结构

## 总结

这些插件为 GeneTi-Maid 项目提供了：

1. **现代化框架**: Vue 3 + Vue Router + Pinia
2. **网络通信**: Axios + Socket.IO
3. **内容处理**: Marked + Highlight.js
4. **工具函数**: UUID 生成
5. **开发工具**: Vite + ESLint + Prettier

通过这些插件的组合使用，我们构建了一个功能完整、性能优秀、开发体验良好的前端应用。 