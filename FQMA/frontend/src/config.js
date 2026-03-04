export default {
  // API配置 - 直接指定地址
  API_BASE_URL: 'http://localhost:5000/api',

  // 应用配置
  APP_NAME: 'FQMA',  // 改成你的项目名
  APP_VERSION: '1.0.0',

  // 默认数据集
  DEFAULT_DATASET: 'GMQA',

  // 数据集配置
  DATASETS: {
    GMQA: {
      label: 'GMQA',
      icon: '🐷',
      examples: [
        {
          text: '给ketogenic diet食物导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够减少这些微生物的数量？这些基因的代谢通路是什么？',
          icon: '🐷'
        },
        {
          text: '使用药物Anticholinergic drug导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够增加这些微生物群的数量？这些基因的代谢通路是什么？使用药物Anticholinergic drug导致肠道微生物丰度上升的微生物有哪些？',
          icon: '🦠'
        },
        {
          text: 'Bacteroides是否对生猪饲养效率是显著相关的？它产生的代谢物和哪些基因的表达量有关？这些基因的代谢通路有哪些？',
          icon: '🧬'
        },
        {
          text: '使用药物Metformin导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够增加这些微生物群的数量？这些基因的代谢通路是什么？',
          icon: '🌾'
        }
      ]
    },
    RODI: {
      label: 'RODI-Conference',
      icon: '📄',
      examples: [
        {
          text: '查找所有位置在Benguela会议上发表论文的作者，获取这些作者的姓名。',
          icon: '📍'
        },
        {
          text: '查询ID为3的作者所著的前10篇论文，这些论文的摘要，再查他们的标题和提交的会议ID又是什么',
          icon: '✍️'
        },
        {
          text: '找出委员会YSWC 2015 Program Committee所有成员，并获取他们详细个人信息包括所属的所有委员会信息',
          icon: '🔍'
        },
        {
          text: '查询ID为1000的委员会的成员ID，获取对应的邮箱地址，这些成员的名字、姓氏又是什么？',
          icon: '👥'
        }
      ]
    }
  },

  // 查询配置
  MAX_QUERY_LENGTH: 1000,
  QUERY_TIMEOUT: 60000,

  // UI配置
  THEME: {
    primaryColor: '#6b46c1',
    secondaryColor: '#f0f0f0',
    errorColor: '#dc2626',
    successColor: '#10b981'
  }
}