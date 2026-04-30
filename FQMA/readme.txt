本文件夹作用：
用于存放作品后端服务代码、多智能体查询流程实现、配置文件及实验相关脚本。

文件说明：
1. app.py
   Flask 后端服务入口文件。
2. main.py
   命令行模式或主执行入口文件。
3. query_workflow.py
   多智能体查询工作流定义文件。
4. config.py
   系统配置文件，包含数据库连接和模型相关配置。
5. requirements.txt
   Python 依赖列表文件。
6. agents/
   智能体实现目录，包含查询规划、语义修复、查询适配、结果聚合等模块。
7. QAsets/
   后端测试问答集目录。
8. Tools/
   后端工具函数与辅助模块目录。
9. data/
   运行所需的中间数据或辅助数据目录。
10. scripts/
    后端脚本目录。
11. experiment_results/
    实验结果输出目录。
12. samples_exp/
    示例实验或测试样例目录。
13. exp_framework_modified.py
    实验框架相关脚本。
14. .env
    本地运行环境变量配置文件。
15. backend.log
    后端运行日志文件。
16. readme.txt
    本文件夹说明文件。

说明：
1. .idea/、.gitignore、.DS_Store 等属于开发环境或系统辅助文件，可忽略。
2. 如需查看数据库脚本、本体与映射文件，请进入“素材”目录。
