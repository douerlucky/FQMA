export default {
  // API配置
  API_BASE_URL: process.env.VUE_APP_API_URL || 'http://localhost:5000/api',

  // 应用配置
  APP_NAME: 'GeneTi-Maid',
  APP_VERSION: '1.0.0',

  // 查询配置
  MAX_QUERY_LENGTH: 1000,
  QUERY_TIMEOUT: 60000, // 60秒超时

  // UI配置
  THEME: {
    primaryColor: '#6b46c1',
    secondaryColor: '#f0f0f0',
    errorColor: '#dc2626',
    successColor: '#10b981'
  }
}
