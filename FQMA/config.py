import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import random

# =====================================================================
# 核心配置：选择使用哪个数据集
# =====================================================================
CURRENT_DATASET = "RODI"  # 修改这里来切换数据集：GMQA, RODI

# =====================================================================
# 数据集配置 - 灵活支持不同的数据库结构
# =====================================================================
DATASETS = {
    "GMQA": {
        # 文件路径配置
        "ontology_file": "data/GMQA/ontology.owl",
        "ttl_files": {
            "neo4j": "data/GMQA/pgmkg.ttl",
            "mysql_main": ["data/GMQA/newgutmgene.ttl", "data/GMQA/relationship.ttl"],
            "mysql_disorder": ["data/GMQA/gutmdisorder.ttl", "data/GMQA/relationship.ttl"],
            "postgresql": "data/GMQA/kegg.ttl"
        },
        # 数据库类型配置（定义该数据集实际使用的数据库）
        "enabled_databases": [
            "Neo4j",
            "MySQL(newgutmgene)",
            "MySQL(gutmdisorder)",
            "PostgreSQL"
        ],
        # 数据库连接配置
        "databases": {
            "neo4j": {
                "database": "neo4j",
                "display_name": "Neo4j"
            },
            "mysql_main": {
                "database": "newgutmgene",
                "display_name": "MySQL(newgutmgene)"
            },
            "mysql_disorder": {
                "database": "gutmdisorder",
                "display_name": "MySQL(gutmdisorder)"
            },
            "postgresql": {
                "database": "kegg",
                "display_name": "PostgreSQL"
            }
        }
    },

    "RODI": {
        "ontology_file": "data/RODI/rodi_ontology.owl",
        "ttl_files": {
            "neo4j": "data/RODI/rodi_neo4j.ttl",
            "mysql_main": "data/RODI/rodi_mysql.ttl",  # RODI只有一个MySQL库
            "postgresql": "data/RODI/rodi_postgre.ttl"
        },
        # RODI只使用3个数据库
        "enabled_databases": [
            "Neo4j",
            "MySQL",  # 注意：RODI只有一个MySQL，不需要区分
            "PostgreSQL"
        ],
        "databases": {
            "neo4j": {
                "database": "rodineo4j",
                "display_name": "Neo4j"
            },
            "mysql_main": {
                "database": "rodiConference",
                "display_name": "MySQL"
            },
            "postgresql": {
                "database": "rodiConference",
                "display_name": "PostgreSQL"
            }
        }
    },

   
}


# =====================================================================
# 获取当前数据集配置
# =====================================================================
def get_current_dataset_config():
    """获取当前选择的数据集配置"""
    if CURRENT_DATASET not in DATASETS:
        raise ValueError(f"数据集 '{CURRENT_DATASET}' 未定义！请检查DATASETS配置。")
    return DATASETS[CURRENT_DATASET]


# 当前数据集配置（快捷访问）
DATASET_CONFIG = get_current_dataset_config()

# =====================================================================
# 文件路径配置（从数据集配置中获取）
# =====================================================================
ontology_path = DATASET_CONFIG["ontology_file"]

# TTL文件路径
TTL_FILES = DATASET_CONFIG["ttl_files"]

# 启用的数据库列表
ENABLED_DATABASES = DATASET_CONFIG["enabled_databases"]

# =====================================================================
# 数据库连接配置（通用部分 + 数据集特定部分）
# =====================================================================
# MySQL通用配置（用户名密码保持不变）
MySQL_user = 'root'
MySQL_pwd = 'xfy911922'

# Neo4j配置
Neo4j_config = {
    'uri': "bolt://localhost:7687",
    'user': "neo4j",
    'password': "akie0126",
    'database': DATASET_CONFIG["databases"]["neo4j"]["database"]
}

# MySQL主数据库配置
MySQL_config = {
    'host': "localhost",
    'user': MySQL_user,
    'password': MySQL_pwd,
    'database': DATASET_CONFIG["databases"]["mysql_main"]["database"]
}

# MySQL疾病数据库配置（仅GMQA使用）
GutMDisorder_config = None
if "mysql_disorder" in DATASET_CONFIG["databases"]:
    GutMDisorder_config = {
        'host': "localhost",
        'user': MySQL_user,
        'password': MySQL_pwd,
        'database': DATASET_CONFIG["databases"]["mysql_disorder"]["database"]
    }

# PostgreSQL配置
Postgre_config = {
    'host': "localhost",
    'user': "postgres",
    'password': "1234",
    'database': DATASET_CONFIG["databases"]["postgresql"]["database"]
}

# =====================================================================
# 辅助函数：获取数据库显示名称
# =====================================================================
def get_database_display_name(db_key: str) -> str:
    """根据数据库key获取显示名称"""
    if db_key in DATASET_CONFIG["databases"]:
        return DATASET_CONFIG["databases"][db_key]["display_name"]
    return db_key

def is_database_enabled(db_name: str) -> bool:
    """检查数据库是否在当前数据集中启用"""
    return db_name in ENABLED_DATABASES

# =====================================================================
# 测试配置
# =====================================================================
TEST_MODE = "selected"  # "all" 或 "selected"
SELECTED_QUESTION_IDS = [str(i) for i in range(106,116)]

# =====================================================================
# LLM配置
# =====================================================================
MODEL_TYPE = "deepseek"  # 可选: "deepseek", "qwen", "gpt", "llama", "zhipu", "ollama"
llm_temperature = 0.15

load_dotenv()

# 模型初始化（保持原有逻辑）
if MODEL_TYPE == "qwen":
    from langchain_community.chat_models import ChatTongyi

    os.environ['DASHSCOPE_API_KEY'] = 'sk-1e6a1b5f2671486380b3553c82f42199'
    model = ChatTongyi(
        temperature=llm_temperature,
        model_name="qwen-plus",
        dashscope_api_key=os.environ.get('DASHSCOPE_API_KEY')
    )
elif MODEL_TYPE == "deepseek":
    from langchain_openai import ChatOpenAI

    os.environ['DEEPSEEK_API_KEY'] = 'sk-2eeb2c0f09794d5d9ca9346cc6f85c27'
    os.environ['OPENAI_API_BASE'] = 'https://api.deepseek.com'
    model = ChatOpenAI(
        temperature=llm_temperature,
        model="deepseek-chat",
        api_key=os.environ.get('DEEPSEEK_API_KEY'),
        base_url="https://api.deepseek.com/v1"
    )
elif MODEL_TYPE == "gpt":
    from langchain_openai import ChatOpenAI

    os.environ['OPENAI_API_KEY'] = 'sk-5RkJwvBlwQ00hWfgUMK8ryzuxTu4dolAaFIupekAPOguyG8V'
    os.environ['OPENAI_API_BASE'] = 'https://jeniya.top/v1'
    model = ChatOpenAI(
        temperature=llm_temperature,
        model="gpt-4o-mini",
        api_key=os.environ.get('OPENAI_API_KEY'),
        base_url="https://jeniya.top/v1"
    )
elif MODEL_TYPE == "llama":
    from langchain_openai import ChatOpenAI

    os.environ['LLAMA_API_KEY'] = 'sk-J9zUDQ9hPaT2PWutvVS41vHf6XUotMjdP8c7QMCfZxvW5gyL'
    os.environ['LLAMA_API_BASE'] = 'https://api.aigc.bar'
    model = ChatOpenAI(
        temperature=llm_temperature,
        model="llama-3.1-405b",
        api_key=os.environ.get('LLAMA_API_KEY'),
        base_url="https://api.aigc.bar/v1"
    )
elif MODEL_TYPE == "zhipu":
    from langchain_openai import ChatOpenAI

    os.environ['ZHIPU_API_KEY'] = 'e78612ed227e4a8296f55279b3421ad3.5lKoq9FVqea0ttBe'
    model = ChatOpenAI(
        temperature=llm_temperature,
        model="glm-4",
        api_key=os.environ.get('ZHIPU_API_KEY'),
        base_url="https://open.bigmodel.cn/api/paas/v4"
    )
elif MODEL_TYPE == "ollama":
    from langchain_community.llms import Ollama

    model = Ollama(
        model="llama2:7b",
        temperature=llm_temperature
    )

# =====================================================================
# 其他配置（保持不变）
# =====================================================================
is_ontology = True
is_use_repair = True
iter_nums = 2
example_use = 5

# 实验结果配置
# 根据当前数据集自动选择测试数据文件
if CURRENT_DATASET == "RODI":
    TEST_DATA_FILE = 'QAsets/TOWrodi_query.json'  # RODI数据集测试文件
else:
    TEST_DATA_FILE = 'QAsets/pig_microbiota_query_backup2.json'  # GMQA数据集测试文件
VERBOSE_OUTPUT = True
SAVE_INTERMEDIATE_RESULTS = True
SAVE_ERROR_LOGS = True
EXPERIMENT_RESULTS_DIR = 'experiment_results'
SAVE_JSON_RESULTS = True
SAVE_SUMMARY_REPORT = True
SAVE_CSV_METRICS = True
RESULT_FILE_PREFIX = "test_results"
SUMMARY_FILE_PREFIX = "summary_report"
CSV_FILE_PREFIX = "metrics_data"
EXPERIMENT_TAG = "debug_mode"


# =====================================================================
# 打印当前配置信息
# =====================================================================
def print_current_config():
    """打印当前使用的数据集配置信息"""
    print("\n" + "=" * 60)
    print(f"当前使用数据集: {CURRENT_DATASET}")
    print("=" * 60)
    print(f"本体文件: {ontology_path}")
    print(f"\n启用的数据库:")
    for db_name in ENABLED_DATABASES:
        print(f"  ✓ {db_name}")
    print(f"\n数据库连接信息:")
    print(f"  Neo4j: {Neo4j_config['database']}")
    print(f"  MySQL主库: {MySQL_config['database']}")
    if GutMDisorder_config:
        print(f"  MySQL疾病库: {GutMDisorder_config['database']}")
    print(f"  PostgreSQL: {Postgre_config['database']}")
    print("=" * 60 + "\n")


# 程序启动时打印配置
if __name__ == "__main__":
    print_current_config()
# =====================================================================
# 查询检查配置
# =====================================================================
# LLM检查模式：
# - "strict": LLM检查结果影响最终判定（可能过于严格）
# - "advisory": LLM检查仅作为建议，不影响最终判定（推荐）
# - "disabled": 完全禁用LLM检查
LLM_CHECK_MODE = "advisory"  # 推荐使用advisory模式

# 是否启用详细的检查日志
VERBOSE_CHECKING = True