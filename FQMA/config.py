import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import random

#选择使用哪个数据集
CURRENT_DATASET = "RODI" # 修改这里来切换数据集：GMQA, RODI

# 其他配置
is_ontology = True #是否启用本体
is_use_repair = True #是否使用语义修复
iter_nums = 2 #语义修迭代次数
example_use = 5 #样例使用数

# MySQL通用配置
MySQL_user = 'root'
MySQL_pwd = 'pwd'

Postgre_user = 'postgres'
Postgre_pwd = 'pwd'

Neo4j_user = 'neo4j'
Neo4j_pwd = "pwd"

# LLM配置
MODEL_TYPE = "deepseek"  # 可选: "deepseek", "qwen", "gpt", "llama", "zhipu", "ollama"
llm_temperature = 0.15

load_dotenv()

# 模型初始化（保持原有逻辑）
if MODEL_TYPE == "qwen":
    from langchain_community.chat_models import ChatTongyi

    os.environ['DASHSCOPE_API_KEY'] = 'sk-XXXXXX'
    model = ChatTongyi(
        temperature=llm_temperature,
        model_name="qwen-plus",
        dashscope_api_key=os.environ.get('DASHSCOPE_API_KEY')
    )
elif MODEL_TYPE == "deepseek":
    from langchain_openai import ChatOpenAI

    os.environ['DEEPSEEK_API_KEY'] = 'sk-XXXXXX'
    os.environ['OPENAI_API_BASE'] = 'https://api.deepseek.com'
    model = ChatOpenAI(
        temperature=llm_temperature,
        model="deepseek-chat",
        api_key=os.environ.get('DEEPSEEK_API_KEY'),
        base_url="https://api.deepseek.com/v1"
    )
elif MODEL_TYPE == "gpt":
    from langchain_openai import ChatOpenAI

    os.environ['OPENAI_API_KEY'] = 'sk-XXXXXX'
    os.environ['OPENAI_API_BASE'] = 'https://jeniya.top/v1'
    model = ChatOpenAI(
        temperature=llm_temperature,
        model="gpt-4o-mini",
        api_key=os.environ.get('OPENAI_API_KEY'),
        base_url="https://jeniya.top/v1"
    )
elif MODEL_TYPE == "llama":
    from langchain_openai import ChatOpenAI

    os.environ['LLAMA_API_KEY'] = 'sk-XXXXXX'
    os.environ['LLAMA_API_BASE'] = 'https://api.aigc.bar'
    model = ChatOpenAI(
        temperature=llm_temperature,
        model="llama-3.1-405b",
        api_key=os.environ.get('LLAMA_API_KEY'),
        base_url="https://api.aigc.bar/v1"
    )
elif MODEL_TYPE == "zhipu":
    from langchain_openai import ChatOpenAI

    os.environ['ZHIPU_API_KEY'] = 'XXXXXX.XXXXXX'
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

# 数据集配置 - 灵活支持不同的数据库结构
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
        # 数据库类型配置
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
        "ontology_file": "data/RODI/ontology.owl",
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
                "database": "rodiclean",
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


# 获取当前数据集配置
def get_current_dataset_config():
    """获取当前选择的数据集配置"""
    if CURRENT_DATASET not in DATASETS:
        raise ValueError(f"数据集 '{CURRENT_DATASET}' 未定义！请检查DATASETS配置。")
    return DATASETS[CURRENT_DATASET]


# 当前数据集配置（快捷访问）
DATASET_CONFIG = get_current_dataset_config()

# 文件路径配置（从数据集配置中获取）
ontology_path = DATASET_CONFIG["ontology_file"]

# TTL文件路径
TTL_FILES = DATASET_CONFIG["ttl_files"]

# 启用的数据库列表
ENABLED_DATABASES = DATASET_CONFIG["enabled_databases"]



# Neo4j配置
Neo4j_config = {
    'uri': "bolt://localhost:7687",
    'user': Neo4j_user,
    'password': Neo4j_pwd,
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
    'user': Postgre_user,
    'password': Postgre_pwd,
    'database': DATASET_CONFIG["databases"]["postgresql"]["database"]
}

# 获取数据库显示名称
def get_database_display_name(db_key: str) -> str:
    """根据数据库key获取显示名称"""
    if db_key in DATASET_CONFIG["databases"]:
        return DATASET_CONFIG["databases"][db_key]["display_name"]
    return db_key

def is_database_enabled(db_name: str) -> bool:
    """检查数据库是否在当前数据集中启用"""
    return db_name in ENABLED_DATABASES


TEST_MODE = "selected"  # "all" 或 "selected"
SELECTED_QUESTION_IDS = [str(i) for i in range(106,116)]


# 实验结果配置
# 根据当前数据集自动选择测试数据文件
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


# 打印当前配置信息
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
LLM_CHECK_MODE = "advisory"  # 推荐使用advisory模式

# 是否启用详细的检查日志
VERBOSE_CHECKING = True