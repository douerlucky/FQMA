<template>
  <div id="app">
    <!-- 侧边栏 -->
    <div class="sidebar">
      <div class="sidebar-header">
        <div class="logo">
          <div class="logo-texts">
            <span class="logo-name">{{ $config.APP_NAME }}</span>
            <div class="sidebar-link-row">
              <button class="about-link" @click="openAboutModal">About</button>
              <button class="about-link" @click="openDatasetJson">View Dataset</button>
            </div>
            <ul class="sidebar-features">
              <li v-for="(item, idx) in currentDatasetConfig.features" :key="idx">
                {{ item }}
              </li>
            </ul>
          </div>
        </div>
      </div>
      <div class="dataset-selector">
        <label class="dataset-label" for="dataset-select">Current Database</label>
        <select
          id="dataset-select"
          v-model="currentDataset"
          class="dataset-select"
          :disabled="datasetSwitching || isProcessing"
          @change="switchDataset($event.target.value)"
        >
          <option
            v-for="dataset in datasetOptions"
            :key="dataset.name"
            :value="dataset.name"
          >
            {{ dataset.displayName || dataset.name }}
          </option>
        </select>
        <div class="dataset-hint">
          {{ datasetSwitching ? 'Switching database...' : currentDatasetConfig.label }}
        </div>
      </div>
      <button class="new-query-btn" @click="startNewQuery">
        <span class="new-query-icon">➕</span>
        <span>New Query</span>
      </button>
      <div class="sidebar-section">
        <div class="section-title-wrapper">
          <div class="section-title">Queries</div>
          <button class="clear-history-btn" @click="clearAllHistory" title="Clear history">
            🗑️
          </button>
        </div>
      </div>
      <div class="query-list">
        <!-- 空状态 -->
        <div v-if="queryHistory.length === 0" class="empty-history">
          <div class="empty-icon">💬</div>
          <div class="empty-text">No query history</div>
          <div class="empty-subtitle">Start a new query.</div>
        </div>
        <!-- 历史记录列表 -->
        <div
          v-for="query in queryHistory"
          :key="query.id"
          class="query-item"
          :class="{ active: currentQueryId === query.id }"
          @click="selectQuery(query)"
        >
          <div class="query-avatar">💬</div>
          <div class="query-content">
            <div class="query-text">{{ truncateText(query.user_message || query.question, 30) }}</div>
            <div class="query-time">{{ formatTime(query.timestamp) }}</div>
          </div>
          <button class="delete-btn" @click.stop="deleteQuery(query.id)">🗑️</button>
        </div>
      </div>
    </div>
    <!-- 主内容区 -->
    <div class="main-content">
      <div class="chat-container" ref="chatContainer">
        <div class="chat-inner">
          <!-- 欢迎界面 -->
          <div v-if="messages.length === 0" class="welcome-screen">
            <div class="welcome-title">
              <span>🧬</span>
              <span>{{ $config.APP_NAME }}</span>
              <span></span>
            </div>
            <div class="welcome-subtitle">{{ currentDatasetConfig.label }}</div>
            <img
              class="welcome-ontology-image"
              src="/sys_ontology.png"
              alt="FQMA ontology and federated query workflow"
            />
            <div class="example-section">
              <div class="example-title">
                <span>💡</span>
                <span>Example queries</span>
              </div>
              <div class="example-cards">
                <div v-for="(example, index) in currentDatasetConfig.examples" :key="index" class="example-card" @click="useExample(example.text)">
                  <div class="example-icon">{{ example.icon }}</div>
                  <div class="example-text">{{ example.text }}</div>
                </div>
              </div>
            </div>
          </div>
          <!-- 消息列表 -->
          <div v-for="(message, index) in messages" :key="index" class="message-wrapper">
            <!-- 用户消息 - 显示在右侧 -->
            <div v-if="message.type === 'user'" class="message user-message">
              <div class="message-avatar user-avatar">👤</div>
              <div class="message-content user-bubble">
                {{ message.content }}
              </div>
            </div>
            <!-- AI消息 - 显示在左侧 -->
            <div v-else class="message ai-message">
              <div class="message-avatar ai-avatar">🧬</div>
              <div class="message-content-wrapper">
                <!-- 思考过程 - 可折叠设计 -->
                <div v-if="message.thinking && message.thinking.length > 0" class="thinking-section">
                  <div class="thinking-header" @click="toggleThinking(message)">
                    <div class="thinking-status">
                      <span class="thinking-icon">🧠</span>
                      {{ message.loading ? 'Thinking...' : 'Thinking complete' }}
                    </div>
                    <div class="thinking-controls">
                      <span class="thinking-toggle">{{ message.thinkingCollapsed ? 'Expand' : 'Collapse' }}</span>
                    </div>
                  </div>
                  <div
                    v-if="!message.thinkingCollapsed"
                    :ref="`thinkingContent-${message.message_id}`"
                    class="thinking-content"
                  >
                    <div class="thinking-list">
                      <div
                        v-for="(step, i) in message.thinking"
                        :key="i"
                        class="thinking-item"
                      >
                        <div v-if="step.type === 'print'" class="print-message">
                          <span class="print-icon">📄</span>
                          <span class="print-text">{{ step.content }}</span>
                        </div>
                        <div v-else class="thinking-message">
                          {{ step.content }}
                        </div>
                      </div>
                      <!-- 加载指示器 - 当还在思考时显示 -->
                      <div v-if="message.loading" class="thinking-item">
                        <div class="thinking-loading">
                          <div class="dot-pulse"></div>
                          Processing...
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- AI回复内容 -->
                <div v-if="!message.loading && (message.tables || message.explanation)" class="message-content ai-bubble">
                  <div v-if="message.mergedTable" class="merged-table-section">
                    <div class="merged-table-header">
                      <h3>Merged Summary Table</h3>
                      <button v-if="message.mergedCsv" class="download-btn" @click="downloadMergedCsv(message)">
                        Download
                      </button>
                    </div>
                    <div v-html="renderMarkdown(stripMergedTableTitle(message.mergedTable))" class="result-table merged-table-scroll"></div>
                  </div>
                  <div v-if="message.tables" v-html="renderMarkdown(message.tables)" class="result-table detail-table-section"></div>
                  <div v-if="message.explanation" v-html="renderMarkdown(message.explanation)" class="result-explanation"></div>
                </div>
                <!-- 加载动画 - 初始状态 -->
                <div v-if="message.loading && (!message.thinking || message.thinking.length === 0)" class="message-content loading-bubble">
                  <div class="loading-dots">
                    <span></span><span></span><span></span>
                  </div>
                  Processing your query...
                </div>
                <!-- 错误信息 -->
                <div v-if="message.error" class="message-content error-bubble">
                  <span>⚠️</span> {{ message.error }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <!-- 输入区域 -->
      <div class="input-area">
        <div class="input-container">
          <div class="input-wrapper">
            <textarea
              v-model="inputText"
              @keydown.enter.prevent="handleEnter"
              placeholder="Enter your question..."
              class="input-textarea"
              rows="1"
              ref="textareaRef"
              @input="adjustTextareaHeight"
              :disabled="isProcessing"
            ></textarea>
            <button
              class="send-btn"
              @click="sendQuery"
              :disabled="!inputText.trim() || isProcessing"
            >
              <span v-if="!isProcessing">Send</span>
              <span v-else>Processing</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showAboutModal" class="about-modal-mask" @click.self="closeAboutModal">
      <div class="about-modal">
        <div class="about-modal-header">
          <h2>{{ aboutProject.title }}</h2>
          <button class="about-close" @click="closeAboutModal">Close</button>
        </div>
        <div class="about-modal-body">
          <section class="about-block">
            <h3>Project Overview</h3>
            <p>{{ aboutProject.intro }}</p>
          </section>
          <section class="about-block">
            <h3>Developers</h3>
            <p>{{ aboutProject.developers }}</p>
          </section>
          <section class="about-block">
            <h3>Objectives</h3>
            <p>{{ aboutProject.problems }}</p>
          </section>
          <section class="about-block">
            <h3>Core Ideas and Contributions</h3>
            <p>{{ aboutProject.innovations }}</p>
          </section>
          <section class="about-block">
            <h3>Databases</h3>
            <p>{{ aboutProject.databases }}</p>
          </section>
          <section class="about-block">
            <h3>Dataset Construction and Sources</h3>
            <p>{{ aboutProject.datasetSources }}</p>
          </section>
          <section class="about-block">
            <h3>Question-Answer Categories</h3>
            <p>{{ aboutProject.qaCategories }}</p>
            <h4>GMQA Dataset Statistics</h4>
            <table class="stats-table">
              <thead>
                <tr>
                  <th>Query Category</th>
                  <th>Questions</th>
                  <th>Tables</th>
                  <th>Triples</th>
                  <th>Mean Rows</th>
                  <th>Row Range</th>
                  <th>Column Range</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="stat in aboutProject.qaStats" :key="stat.category">
                  <td>{{ stat.category }}</td>
                  <td>{{ stat.questions }}</td>
                  <td>{{ stat.tables }}</td>
                  <td>{{ stat.triples }}</td>
                  <td>{{ stat.meanRows }}</td>
                  <td>{{ stat.rowRange }}</td>
                  <td>{{ stat.colRange }}</td>
                </tr>
              </tbody>
            </table>
            <h4>Query Category Details</h4>
            <table class="details-table">
              <thead>
                <tr>
                  <th>Query Category</th>
                  <th>Questions</th>
                  <th>Representative Natural-Language Question</th>
                  <th>Data Sources</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="detail in aboutProject.qaDetails" :key="detail.category">
                  <td>{{ detail.category }}</td>
                  <td>{{ detail.qty }}</td>
                  <td>{{ detail.query }}</td>
                  <td>{{ detail.sources }}</td>
                </tr>
              </tbody>
            </table>
          </section>

        </div>
      </div>
    </div>

  </div>
</template>

<script>
import axios from 'axios'
import { marked } from 'marked'
import { v4 as uuidv4 } from 'uuid';
import { nextTick } from 'vue';
import appConfig from './config.js'

export default {
  name: 'App',
  beforeCreate() {
    this.$config = appConfig;
  },
  data() {
    return {
      sessionId: null,
      currentQueryId: null,
      queryHistory: [],
      messages: [],
      inputText: '',
      isProcessing: false,
      messageIdMap: {},
      currentThinkingMessage: null,
      showAboutModal: false,
      logoLoadFailed: false,
      currentDataset: appConfig.DEFAULT_DATASET || 'GMQA',
      lastSyncedDataset: appConfig.DEFAULT_DATASET || 'GMQA',
      datasetSwitching: false,
    }
  },
  computed: {
    isDevelopment() {
      return process.env.NODE_ENV === 'development' || window.location.hostname === 'localhost';
    },
    currentDatasetConfig() {
      return this.$config.DATASETS?.[this.currentDataset] || this.$config.DATASETS?.GMQA || {};
    },
    datasetOptions() {
      return Object.values(this.$config.DATASETS || {});
    },
    aboutProject() {
      return this.$config.ABOUT_PROJECT || {};
    }
  },
  mounted() {
    this.initSession();
    this.setupSocketConnection();
    this.syncDefaultDataset();
  },
  methods: {
    async syncDefaultDataset() {
      try {
        await axios.post(`${appConfig.API_BASE_URL}/switch-dataset`, { dataset: this.currentDataset });
        this.lastSyncedDataset = this.currentDataset;
      } catch (error) {
        console.warn('Failed to sync the default database. You can switch it manually after the backend starts:', error);
      }
    },
    initSession() {
      
      this.sessionId = localStorage.getItem('geneti-session-id');
      if (this.sessionId) {
        this.loadHistory();
      } else {
        this.sessionId = uuidv4();
        localStorage.setItem('geneti-session-id', this.sessionId);
        this.queryHistory = [];
      }
    },
    setupSocketConnection() {
      if (this.$socket) {
        // 实时接收思考过程 - 优化实时性
        this.$socket.on('thinking', (msg) => {
          if (!msg || !msg.message_id) return;
          const sysMsg = this.messageIdMap[msg.message_id];
          if (!sysMsg) return;

          // 确保UI及时更新
          nextTick(() => {
            // 实时添加思考步骤
            if (msg.type === 'thinking') {
              if (!String(msg.data || '').trim()) return;
              if (!sysMsg.thinking) {
                sysMsg.thinking = [];
              }
              // 添加思考步骤
              sysMsg.thinking.push({
                type: 'thinking',
                content: msg.data
              });
              this.scrollThinkingToBottom(msg.message_id);
              this.scrollToBottomIfNearBottom();
            }
            // 处理print输出
            else if (msg.type === 'print') {
              if (!String(msg.data || '').trim()) return;
              if (!sysMsg.thinking) {
                sysMsg.thinking = [];
              }
              // 添加print输出
              sysMsg.thinking.push({
                type: 'print',
                content: msg.data
              });
              this.scrollThinkingToBottom(msg.message_id);
              this.scrollToBottomIfNearBottom();
            }
            // 处理最终结果
            else if (msg.type === 'result') {
              sysMsg.loading = false;
              if (msg.data.success) {
                sysMsg.subqueries = msg.data.subqueries;
                sysMsg.tables = msg.data.tables;
                sysMsg.mergedTable = msg.data.merged_table || null;
                sysMsg.mergedCsv = msg.data.merged_csv || null;
                sysMsg.explanation = msg.data.explanation;
              } else {
                sysMsg.error = msg.data.error;
              }
              this.scrollThinkingToBottom(msg.message_id);
              this.scrollToBottom();
            }
          });
        });
      }
    },
    loadHistory() {
      // 直接从本地存储加载历史记录，不调用后端
      const cachedHistory = localStorage.getItem('geneti-history-cache');
      if (cachedHistory) {
        try {
          let history = JSON.parse(cachedHistory);
          const deletedItems = JSON.parse(localStorage.getItem('geneti-deleted-queries') || '[]');
          this.queryHistory = history.filter(item => !deletedItems.includes(item.id));
        } catch (parseError) {
          console.error('解析缓存失败:', parseError);
          this.queryHistory = [];
        }
      } else {
        this.queryHistory = [];
      }
    },
    async sendQuery() {
      if (!this.inputText.trim() || this.isProcessing) return;
      const question = this.inputText.trim();
      this.inputText = '';
      this.isProcessing = true;

      // 添加用户消息
      this.messages.push({
        type: 'user',
        content: question
      });

      // 生成唯一ID
      const message_id = uuidv4();
      const query_id = uuidv4();

      // 添加系统消息（加载中）
      const systemMessage = {
        type: 'system',
        loading: true,
        thinking: null,  // 初始化为null，收到第一个思考步骤时再创建数组
        subqueries: null,
        tables: null,
        mergedTable: null,
        mergedCsv: null,
        explanation: null,
        error: null,
        message_id,
        // 思考过程控制相关
        thinkingCollapsed: false
      };
      this.messages.push(systemMessage);
      this.messageIdMap[message_id] = systemMessage;

      this.scrollToBottom();
      this.adjustTextareaHeight();

      try {
        const response = await axios.post(`${appConfig.API_BASE_URL}/query`, {
          question,
          session_id: this.sessionId,
          message_id,
          dataset: this.currentDataset
        });

        const data = response.data;
        this.sessionId = data.session_id;
        localStorage.setItem('geneti-session-id', this.sessionId);

        // 添加到历史记录
        const newQuery = {
          id: query_id,
          user_message: question,
          dataset: this.currentDataset,
          timestamp: new Date().toISOString(),
          response: data.result
        };
        this.queryHistory.unshift(newQuery);
        this.currentQueryId = query_id;
        // 保存到本地存储，不依赖后端
        localStorage.setItem('geneti-history-cache', JSON.stringify(this.queryHistory));
      } catch (error) {
        systemMessage.loading = false;
        systemMessage.error = 'Query failed: ' + (error.response?.data?.error || error.message);
      } finally {
        this.isProcessing = false;
        this.scrollToBottom();
      }
    },
    startNewQuery() {
      this.messages = [];
      this.currentQueryId = null;
      this.messageIdMap = {};
      this.currentThinkingMessage = null;
      nextTick(() => {
        const container = this.$refs.chatContainer;
        if (container) container.scrollTop = 0;
      });
    },
    selectQuery(query) {
      this.currentQueryId = query.id;
      const record = this.queryHistory.find(q => q.id === query.id);
      if (!record) {
        alert('This conversation does not exist.');
        return;
      }

      this.messages = [];
      // 用户消息
      this.messages.push({ type: 'user', content: record.user_message || record.question });
      // AI消息
      const sysMsg = {
        type: 'system',
        loading: false,
        thinking: record.response?.thinking ? record.response.thinking.map(step => {
          if (typeof step === 'string') {
            return { type: 'thinking', content: step };
          }
          return step;
        }) : [],
        subqueries: record.response?.subqueries || null,
        tables: record.response?.tables || null,
        mergedTable: record.response?.merged_table || null,
        mergedCsv: record.response?.merged_csv || null,
        explanation: record.response?.explanation || null,
        error: record.response?.error || null,
        message_id: null,
        // 思考过程控制相关
        thinkingCollapsed: false
      };
      this.messages.push(sysMsg);
      this.scrollToBottom();
    },
    deleteQuery(queryId) {
      if (!confirm('Delete this conversation?')) return;
      this.queryHistory = this.queryHistory.filter(q => q.id !== queryId);
      if (this.currentQueryId === queryId) {
        this.startNewQuery();
      }
      // 完全在前端管理删除状态
      const deletedItems = JSON.parse(localStorage.getItem('geneti-deleted-queries') || '[]');
      deletedItems.push(queryId);
      localStorage.setItem('geneti-deleted-queries', JSON.stringify(deletedItems));
      localStorage.setItem('geneti-history-cache', JSON.stringify(this.queryHistory));
    },
    clearAllHistory() {
      if (!confirm('Clear all query history? This action cannot be undone.')) return;
      this.queryHistory = [];
      this.messages = [];
      this.currentQueryId = null;
      // 完全在前端管理清空状态
      localStorage.removeItem('geneti-history-cache');
      localStorage.setItem('geneti-deleted-queries', JSON.stringify([]));
    },
    useExample(text) {
      this.inputText = text;
      this.sendQuery();
    },
    async switchDataset(dataset) {
      if (this.isProcessing) {
        this.currentDataset = this.lastSyncedDataset;
        alert('A query is still running. Please wait until it finishes before switching databases.');
        return;
      }
      if (!this.$config.DATASETS?.[dataset] || dataset === this.lastSyncedDataset) return;

      this.datasetSwitching = true;
      try {
        await axios.post(`${appConfig.API_BASE_URL}/switch-dataset`, { dataset });
        this.lastSyncedDataset = dataset;
        this.startNewQuery();
      } catch (error) {
        this.currentDataset = this.lastSyncedDataset;
        alert('Failed to switch database: ' + (error.response?.data?.error || error.message));
      } finally {
        this.datasetSwitching = false;
      }
    },
    handleEnter(event) {
      if (!event.shiftKey) {
        this.sendQuery();
      }
    },
    adjustTextareaHeight() {
      const textarea = this.$refs.textareaRef;
      if (textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
      }
    },
    scrollToBottom() {
      nextTick(() => {
        const container = this.$refs.chatContainer;
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      });
    },
    scrollToBottomIfNearBottom() {
      nextTick(() => {
        const container = this.$refs.chatContainer;
        if (!container) return;
        const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
        if (distanceToBottom < 180) {
          container.scrollTop = container.scrollHeight;
        }
      });
    },
    scrollThinkingToBottom(messageId) {
      nextTick(() => {
        const refName = `thinkingContent-${messageId}`;
        const refValue = this.$refs[refName];
        const contentEl = Array.isArray(refValue) ? refValue[0] : refValue;
        if (!contentEl) return;
        contentEl.scrollTop = contentEl.scrollHeight;
      });
    },
    truncateText(text, maxLength) {
      if (!text) return '';
      return text.length <= maxLength ? text : text.substring(0, maxLength) + '...';
    },
    formatTime(timestamp) {
      if (!timestamp) return '';
      const date = new Date(timestamp);
      const now = new Date();
      const diff = now - date;

      if (diff < 3600000) {
        return Math.floor(diff / 60000) + ' min ago';
      } else if (diff < 86400000) {
        return Math.floor(diff / 3600000) + ' hr ago';
      } else {
        return date.toLocaleDateString();
      }
    },
    renderMarkdown(text) {
      return marked.parse(text || '');
    },
    stripMergedTableTitle(text) {
      return (text || '').replace(/^#{1,6}\s*联合汇总表\s*\n+/i, '');
    },
    openAboutModal() {
      this.showAboutModal = true;
    },
    openDatasetJson() {
      const datasetJsonPath = this.currentDatasetConfig.datasetJsonPath;
      if (!datasetJsonPath) {
        alert('No dataset JSON file is configured for the current database.');
        return;
      }
      window.open(datasetJsonPath, '_blank', 'noopener,noreferrer');
    },
    closeAboutModal() {
      this.showAboutModal = false;
    },
    onLogoError() {
      this.logoLoadFailed = true;
    },
    downloadMergedCsv(message) {
      if (!message || !message.mergedCsv) return;
      const csvContent = '\ufeff' + message.mergedCsv;
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `zhiwei_jianzhu_merged_result_${Date.now()}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    },
    // 思考过程控制方法
    toggleThinking(message) {
      message.thinkingCollapsed = !message.thinkingCollapsed;
    }
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
html, body, #app {
  width: 100vw;
  height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f7f7f8;
  overflow: hidden;
}
#app {
  display: flex;
  flex-direction: row;
}
/* 侧边栏样式 */
.sidebar {
  width: 320px;
  background: #f7f7f8;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e5e5e5;
  height: 100vh;
  overflow-y: auto;
  padding: 16px;
}
.sidebar-header {
  padding: 16px 0;
  border-bottom: 1px solid #e5e5e5;
  margin-bottom: 16px;
}
.logo {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  color: #202123;
  margin-bottom: 8px;
}
.logo-png-box {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.logo-png {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.logo-png-placeholder {
  font-size: 12px;
  color: #64748b;
  letter-spacing: 1px;
}
.logo-texts {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  margin-top: 2px;
}
.logo-name {
  font-size: 20px;
  font-weight: 700;
  color: #111827;
}
.sidebar-link-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.about-link {
  border: 1px solid #2563eb;
  background: #ffffff;
  padding: 4px 8px;
  color: #2563eb;
  font-size: 12px;
  cursor: pointer;
  border-radius: 6px;
  text-decoration: none;
  transition: all 0.15s;
}
.about-link:hover {
  background: #2563eb;
  color: #ffffff;
}
.sidebar-features {
  margin: 8px 0 0;
  padding-left: 16px;
  color: #475569;
  font-size: 12px;
  line-height: 1.55;
}
.sidebar-features li {
  margin-bottom: 4px;
}
/* 数据集选择器样式 */
.dataset-selector {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}
.dataset-label {
  font-size: 12px;
  color: #666;
  font-weight: 500;
}
.dataset-select {
  padding: 8px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  background-color: #ffffff;
  color: #202123;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.dataset-select:hover {
  border-color: #d0d0d0;
  background-color: #fafafa;
}
.dataset-select:focus {
  outline: none;
  border-color: #10a37f;
  box-shadow: 0 0 0 2px rgba(16, 163, 127, 0.1);
}
.dataset-select:disabled {
  color: #94a3b8;
  cursor: not-allowed;
  background-color: #f8fafc;
}
.dataset-hint {
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
}
.new-query-btn {
  width: 100%;
  padding: 12px 16px;
  background-color: #ffffff;
  color: #202123;
  border: 1px solid #e5e5e5;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  transition: all 0.15s;
  margin-bottom: 16px;
}
.new-query-btn:hover {
  background-color: #f0f0f0;
}
.sidebar-section {
  margin-bottom: 8px;
}
.section-title-wrapper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
}
.section-title {
  font-size: 12px;
  color: #666;
  font-weight: 500;
  margin-bottom: 8px;
}
.clear-history-btn {
  background: none;
  border: none;
  color: #bbb;
  font-size: 14px;
  cursor: pointer;
  opacity: 0.7;
  transition: all 0.15s;
  padding: 4px;
  border-radius: 4px;
  margin-bottom: 8px;
}
.clear-history-btn:hover {
  color: #d32f2f;
  background: #ffebee;
  opacity: 1;
}
.query-list {
  flex: 1;
  overflow-y: auto;
}
.empty-history {
  text-align: center;
  padding: 40px 20px;
  color: #999;
}
.empty-icon {
  font-size: 32px;
  margin-bottom: 12px;
  opacity: 0.5;
}
.empty-text {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  color: #666;
}
.empty-subtitle {
  font-size: 12px;
  color: #999;
}
.query-item {
  background: #ffffff;
  border-radius: 8px;
  margin-bottom: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid transparent;
  display: flex;
  align-items: center;
  gap: 12px;
}
.query-item:hover {
  background: #f0f0f0;
}
.query-item.active {
  background: #e3f2fd;
  border-color: #90caf9;
}
.query-avatar {
  font-size: 16px;
}
.query-content {
  flex: 1;
  overflow: hidden;
}
.query-text {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.query-time {
  font-size: 12px;
  color: #aaa;
}
.delete-btn {
  background: none;
  border: none;
  color: #bbb;
  font-size: 16px;
  cursor: pointer;
  opacity: 0.7;
  transition: all 0.15s;
  padding: 4px;
  border-radius: 4px;
}
.delete-btn:hover {
  color: #d32f2f;
  background: #ffebee;
  opacity: 1;
}
/* 主内容区样式 */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: #ffffff;
  height: 100vh;
  overflow: hidden;
}
.chat-container {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: 20px;
}
.chat-inner {
  width: 100%;
  max-width: 1000px;
  margin: 0 auto;
  flex-grow: 1;
}
/* 欢迎界面 */
.welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 20px 40px;
  text-align: center;
}
.welcome-title {
  font-size: 42px;
  font-weight: 700;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.welcome-subtitle {
  font-size: 18px;
  color: #666;
  margin-bottom: 18px;
}
.welcome-ontology-image {
  width: min(520px, 82%);
  max-height: 190px;
  object-fit: contain;
  margin: 0 0 22px;
}
.example-section {
  width: 100%;
  max-width: 600px;
}
.example-title {
  font-size: 16px;
  font-weight: 600;
  color: #202123;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.example-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
.example-card {
  background-color: #f7f7f8;
  padding: 20px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
  border: 1px solid #e0e0e0;
}
.example-card:hover {
  background-color: #ececec;
  border-color: #d9d9d9;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}
.example-icon {
  font-size: 24px;
  margin-bottom: 8px;
}
.example-text {
  font-size: 14px;
  color: #202123;
  line-height: 1.5;
}
/* 消息样式 - 确保用户消息在右侧 */
.message-wrapper {
  margin-bottom: 16px;
  width: 100%;
  display: flex;
}
.message {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  max-width: 85%;
}
/* 用户消息在右侧 */
.user-message {
  margin-left: auto;
  flex-direction: row-reverse;
}
.ai-message {
  margin-right: auto;
}
.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: bold;
  color: white;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  margin-top: 4px;
}
.user-avatar {
  background: linear-gradient(135deg, #10a37f 0%, #0d8c6d 100%);
}
.ai-avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.message-content {
  padding: 12px 18px;
  border-radius: 18px;
  line-height: 1.6;
  font-size: 15px;
  word-wrap: break-word;
  position: relative;
  max-width: 100%;
}
.message-content-wrapper {
  display: flex;
  flex-direction: column;
  max-width: 100%;
  width: 100%;
}
/* 用户消息样式 - 右侧气泡 */
.user-bubble {
  background: linear-gradient(135deg, #e3f2fd 0%, #b3e5fc 100%);
  color: #202123;
  border-bottom-right-radius: 4px;
  box-shadow: 0 2px 8px rgba(16,163,127,0.1);
}
.ai-bubble {
  background: #ffffff;
  color: #333;
  border: 1px solid #e0e0e0;
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  margin-top: 8px;
}
.loading-bubble {
  background: #f0f7ff;
  color: #0066cc;
  display: flex;
  align-items: center;
  gap: 8px;
  font-style: italic;
  border: 1px solid #e0e0e0;
}
.error-bubble {
  background: #ffeaea;
  color: #d32f2f;
  border: 1px solid #ffcdd2;
  font-weight: bold;
}
/* 思考过程样式 - 极简设计 */
.thinking-section {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  margin-bottom: 12px;
  overflow: hidden;
  animation: fadeIn 0.3s ease-out;
}
.thinking-header {
  padding: 6px 10px;
  background: #f1f5f9;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  gap: 4px;
}
.thinking-status {
  font-size: 11px;
  color: #64748b;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 3px;
}
.thinking-icon {
  font-size: 12px;
}
.thinking-content {
  padding: 8px 10px;
  background: #ffffff;
  max-height: 280px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}
.thinking-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.thinking-item {
  opacity: 1;
  animation: fadeIn 0.12s ease-out;
  padding: 2px 0;
}
.thinking-message {
  font-size: 12px;
  line-height: 1.3;
  color: #374151;
}
.print-message {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  font-size: 11px;
  line-height: 1.2;
  color: #6b7280;
  background: #f9fafb;
  padding: 4px 6px;
  border-radius: 3px;
  border-left: 2px solid #d1d5db;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}
.print-icon {
  font-size: 9px;
  opacity: 0.7;
  margin-top: 1px;
}
.print-text {
  flex: 1;
  word-break: break-word;
}
.thinking-loading {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #6b7280;
  font-style: italic;
}
.thinking-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
.thinking-count {
  font-size: 10px;
  color: #9ca3af;
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 3px;
}
.thinking-toggle {
  font-size: 10px;
  color: #6366f1;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 3px;
  transition: background-color 0.15s;
}
.thinking-toggle:hover {
  background: #f3f4f6;
}
.thinking-header {
  cursor: pointer;
  transition: background-color 0.15s;
}
.thinking-header:hover {
  background: #e5e7eb;
}

/* 思考中指示器 */
.thinking-loading {
  display: flex;
  align-items: baseline;
  gap: 8px;
  height: 24px;
}
.dot-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #6366f1;
  animation: pulse 1.4s infinite ease-in-out;
}
/* 加载动画 */
.loading-dots {
  display: inline-flex;
  gap: 4px;
}
.loading-dots span {
  width: 8px;
  height: 8px;
  background-color: #0066cc;
  border-radius: 50%;
  animation: loading 1.4s infinite ease-in-out both;
}
.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }
/* 输入区域 */
.input-area {
  padding: 24px;
  background: #f7f7f8;
  border-top: 1px solid #e0e0e0;
}
.input-container {
  max-width: 1000px;
  margin: 0 auto;
}
.input-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 24px;
  padding: 12px 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  transition: all 0.15s;
}
.input-wrapper:focus-within {
  border-color: #10a37f;
  box-shadow: 0 0 0 3px rgba(16, 163, 127, 0.1);
}
.input-textarea {
  flex: 1;
  background: none;
  border: none;
  color: #202123;
  font-size: 16px;
  resize: none;
  outline: none;
  font-family: inherit;
  line-height: 1.6;
  min-height: 24px;
  max-height: 200px;
}
.input-textarea::placeholder {
  color: #aaa;
}
.send-btn {
  background: linear-gradient(135deg, #10a37f 0%, #0d8c6d 100%);
  color: white;
  border: none;
  border-radius: 20px;
  padding: 8px 16px;
  font-size: 14px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(16, 163, 127, 0.25);
  transition: all 0.15s;
}
.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(16, 163, 127, 0.3);
}
.send-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
  box-shadow: none;
}
/* 响应式设计 */
@media (max-width: 768px) {
  #app {
    flex-direction: column;
  }
  .sidebar {
    width: 100%;
    height: auto;
    max-height: 200px;
  }
  .chat-inner {
    padding: 10px 6px;
  }
  .message {
    max-width: 90%;
  }
  .example-cards {
    grid-template-columns: 1fr;
  }
  .input-area {
    padding: 16px;
  }
}
/* 表格样式 */
.result-table table {
  width: max-content;
  min-width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 14px;
}
.result-table {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.merged-table-section {
  margin-bottom: 18px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}
.merged-table-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 8px;
}
.merged-table-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #202123;
}
.merged-table-scroll {
  max-width: 100%;
  border-radius: 10px;
}
.detail-table-section {
  margin-top: 12px;
}
.result-table th,
.result-table td {
  border: 1px solid #e0e0e0;
  padding: 8px 12px;
  text-align: left;
  white-space: nowrap;
}
.result-table th {
  background: #f5f5f5;
  font-weight: 600;
}
.result-table tr:hover {
  background: #f9f9f9;
}
.download-btn {
  border: 1px solid #d6d6d6;
  background: #ffffff;
  color: #1f2937;
  border-radius: 6px;
  padding: 4px 9px;
  font-size: 12px;
  line-height: 1.2;
  cursor: pointer;
}
.download-btn:hover {
  background: #f7f7f7;
}
.about-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}
.about-modal {
  width: min(860px, 100%);
  max-height: 88vh;
  background: #ffffff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 16px 50px rgba(2, 6, 23, 0.22);
}
.about-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid #e5e7eb;
  background: #f8fafc;
}
.about-modal-header h2 {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}
.about-close {
  border: 1px solid #d1d5db;
  background: #ffffff;
  color: #111827;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
}
.about-modal-body {
  padding: 18px;
  overflow-y: auto;
  max-height: calc(88vh - 56px);
}
.about-block {
  margin-bottom: 14px;
}
.about-block h3 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #111827;
}
.about-block p,
.about-block li {
  font-size: 13px;
  line-height: 1.7;
  color: #374151;
}
.about-block ul {
  margin: 0;
  padding-left: 18px;
}
/* Markdown样式 */
.message-content h1,
.message-content h2,
.message-content h3,
.message-content h4,
.message-content h5,
.message-content h6 {
  margin: 16px 0 8px 0;
  font-weight: 600;
}
.message-content p {
  margin-bottom: 12px;
}
.message-content ul,
.message-content ol {
  margin: 8px 0;
  padding-left: 20px;
}
.message-content li {
  margin-bottom: 4px;
}
.message-content code {
  background: #f5f5f5;
  padding: 2px 4px;
  border-radius: 3px;
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 0.9em;
}
/* 关于页面表格样式 */
.stats-table, .details-table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 12px;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  overflow: hidden;
}
.stats-table th, .stats-table td,
.details-table th, .details-table td {
  border: 1px solid #e0e0e0;
  padding: 8px 10px;
  text-align: left;
}
.stats-table th, .details-table th {
  background: #f8fafc;
  font-weight: 600;
  color: #374151;
}
.stats-table tr:hover, .details-table tr:hover {
  background: #f9fafb;
}
.stats-table tr:nth-child(even), .details-table tr:nth-child(even) {
  background: #f8fafc;
}
.about-block h4 {
  margin: 16px 0 8px 0;
  font-size: 13px;
  color: #111827;
  font-weight: 600;
}
.message-content pre {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 12px 0;
}
.message-content blockquote {
  border-left: 3px solid #e0e0e0;
  padding-left: 12px;
  margin: 12px 0;
  color: #666;
  font-style: italic;
}
/* 动画 */
@keyframes loading {
  0%, 80%, 100% {
    transform: scale(0);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}
@keyframes pulse {
  0%, 100% {
    opacity: 0.5;
    transform: scale(0.8);
  }
  50% {
    opacity: 1;
    transform: scale(1);
  }
}
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

</style>
