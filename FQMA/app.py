import config
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import uuid
import logging
from flask_socketio import SocketIO
import sys
import queue

# 导入您的核心模块
from agents.QueryPlanningAndGeneration import QueryPlanner, SparQLGenerator
from agents.QueryAdaptive import SubQueryScheduler, SubQueryExecutor
from agents.ResultAggregation import ResultAggregation
from agents.SemanticQueryRepair import QueryChecker, QueryRepairer

app = Flask(__name__)

# ✅ 配置 Flask
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['JSON_AS_ASCII'] = False

# ✅ 配置 CORS - 所有路由都允许跨域
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

# ✅ 配置 Socket.IO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False)


class PrintRedirector:
    def __init__(self, socketio, message_id):
        self.socketio = socketio
        self.message_id = message_id
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.output_queue = queue.Queue()
        self.is_active = True

    def write(self, text):
        if self.is_active and text.strip():
            self.socketio.emit('thinking', {
                'type': 'print',
                'message_id': self.message_id,
                'data': text.strip()
            })
            self.original_stdout.write(text)
            self.original_stdout.flush()

    def flush(self):
        self.original_stdout.flush()

    def __enter__(self):
        sys.stdout = self
        sys.stderr = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        self.is_active = False


print_redirectors = {}


def get_print_redirector(message_id):
    if message_id not in print_redirectors:
        print_redirectors[message_id] = PrintRedirector(socketio, message_id)
    return print_redirectors[message_id]


def cleanup_print_redirector(message_id):
    if message_id in print_redirectors:
        print_redirectors[message_id].is_active = False
        del print_redirectors[message_id]


logging.basicConfig(filename='app.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

sessions = {}

# 1. 定义一个全局变量来保存当前的处理器
processor = None

def get_processor():
    global processor
    if processor is None:
        processor = QueryProcessor()
    return processor


class QueryProcessor:
    def __init__(self):
        self.query_planner = QueryPlanner(config.model)
        self.sparql_generator = SparQLGenerator(config.model, config.ontology_path)
        self.scheduler = SubQueryScheduler(config.model)
        self.executor = SubQueryExecutor(config.model)
        self.aggregator = ResultAggregation(config.model)
        self.scorer = QueryChecker(config.ontology_path)
        self.repairer = QueryRepairer(config.model)

    def process_query(self, question, thinking_callback=None, message_id=None):
        redirector = None
        try:
            print("当前数据库" + config.CURRENT_DATASET)

            if message_id:
                redirector = get_print_redirector(message_id)
                redirector.__enter__()

            if thinking_callback:
                thinking_callback("正在分解问题……")
            subqueries = self.query_planner.get_subqueries(question)
            if thinking_callback:
                thinking_callback(f"分解得到 {len(subqueries)} 个子查询")

            sparqls = []
            for i, subquery in enumerate(subqueries):
                if thinking_callback:
                    thinking_callback(f"正在生成第 {i + 1} 个SPARQL查询...")
                sub_question = subquery["question"]
                dependencies = [subqueries[j - 1] for j in subquery["dependencies"]]
                sparql_query = self.sparql_generator.generate_sparql(sub_question, dependencies)
                sparqls.append(sparql_query)
                if thinking_callback:
                    thinking_callback(f"第 {i + 1} 个SPARQL查询生成完成")

            final_sparqls = []
            for i, sparql in enumerate(sparqls):
                current_sparql = sparql
                if thinking_callback:
                    thinking_callback(f"第{i + 1}个子查询正在评价")

                for repair_iter in range(config.iter_nums):
                    is_compliant, details = self.scorer.check_query(current_sparql, subqueries[i]["question"])
                    if thinking_callback:
                        thinking_callback(f"📋 检查结果: {'✅ 合规' if is_compliant else '❌ 不合规'}")

                    if not is_compliant:
                        if thinking_callback:
                            thinking_callback(f"语法不合规,进行第{repair_iter + 1}次迭代修复")
                        repaired_sparql = self.repairer.repair_sparql(
                            subqueries[i]["question"],
                            details,
                            current_sparql
                        )
                        current_sparql = repaired_sparql
                        if thinking_callback:
                            thinking_callback(f"第{i + 1}个子查询的第{repair_iter + 1}次修复完成")
                    else:
                        if thinking_callback:
                            thinking_callback(f"第{i + 1}个子查询检查合规")
                        break

                final_sparqls.append(current_sparql)

            query_results = {}
            converted_queries = []
            for i, sparql in enumerate(final_sparqls):
                if thinking_callback:
                    thinking_callback(f"子查询 {i + 1} 正在选择数据库...")
                selected_db = self.scheduler.select_database(
                    sparql,
                    subqueries[i]["question"]
                )
                if thinking_callback:
                    thinking_callback(f"子查询 {i + 1} 选择数据库: {selected_db}")
                converted_query = self.executor.convert_to_target_query(sparql, selected_db)
                converted_queries.append(converted_query)
                if thinking_callback:
                    thinking_callback(f"子查询 {i + 1} 转换的查询语言: {converted_query}")

                if self.executor.has_placeholder(converted_query):
                    if thinking_callback:
                        thinking_callback("替换后的查询:")
                    converted_query = self.executor.replace_placeholders(converted_query, query_results)
                    if thinking_callback:
                        thinking_callback(converted_query)
                else:
                    if thinking_callback:
                        thinking_callback("无需上一个查询的结果作为输入，无需替换")

                if thinking_callback:
                    thinking_callback(f"正在执行第 {i + 1} 个查询...")
                result = self.executor.execute_in_database(converted_query, selected_db)
                query_results[i + 1] = result
                if thinking_callback:
                    thinking_callback(f"子查询 {i + 1} 查询结果: {result}")

            if thinking_callback:
                thinking_callback("=== 结果聚合 ===")
            tables, explanation = self.aggregator.process(
                question, converted_queries, query_results
            )
            if thinking_callback:
                thinking_callback("结果聚合完成")

            return {
                "success": True,
                "code": 200,
                "subqueries": subqueries,
                "results": query_results,
                "tables": tables,
                "explanation": explanation
            }
        except Exception as e:
            import traceback
            err_msg = str(e)
            stack = traceback.format_exc()
            logging.error(f"处理查询异常: {err_msg}\n{stack}")
            if thinking_callback:
                thinking_callback(f"处理过程中出现异常: {err_msg}")
            return {
                "success": False,
                "code": 500,
                "error": err_msg
            }
        finally:
            if redirector:
                redirector.__exit__(None, None, None)
                cleanup_print_redirector(message_id)

@app.route('/api/query', methods=['POST', 'OPTIONS'])
def handle_query():
    if request.method == 'OPTIONS':
        return '', 204


    data = request.json
    question = data.get('question')
    session_id = data.get('session_id')
    message_id = data.get('message_id')


    if not question:
        logging.warning("收到空问题请求")
        return jsonify({"error": "问题不能为空", "code": 400}), 400

    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = []

    def thinking_callback(msg):
        socketio.emit('thinking', {
            'type': 'thinking',
            'message_id': message_id,
            'data': msg
        })

    current_processor = get_processor()

    result = current_processor.process_query(question, thinking_callback=thinking_callback, message_id=message_id)

    socketio.emit('thinking', {
        'type': 'result',
        'message_id': message_id,
        'data': result
    })

    query_record = {
        "id": str(uuid.uuid4()),
        "question": question,
        "response": result,
        "timestamp": datetime.now().isoformat()
    }
    sessions[session_id].append(query_record)

    return jsonify({
        "session_id": session_id,
        "query_id": query_record["id"],
        "result": result
    })


@app.route('/api/history/<session_id>', methods=['GET', 'OPTIONS'])
def get_history(session_id):
    if request.method == 'OPTIONS':
        return '', 204

    if session_id not in sessions:
        logging.warning(f"会话不存在: {session_id}")
        return jsonify({"error": "会话不存在", "code": 404}), 404

    return jsonify({
        "session_id": session_id,
        "history": sessions[session_id]
    })


@app.route('/api/health', methods=['GET', 'OPTIONS'])
def health_check():
    if request.method == 'OPTIONS':
        return '', 204

    logging.info("健康检查接口被调用")
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


@app.route('/api/switch-dataset', methods=['POST', 'OPTIONS'])
def switch_dataset():
    if request.method == 'OPTIONS':
        return '', 204
    data = request.json
    dataset = data.get('dataset')

    if dataset not in ['GMQA', 'RODI']:
        return jsonify({'error': '不支持的数据集'}), 400

    # 动态修改config模块的变量
    config.CURRENT_DATASET = dataset
    config.DATASET_CONFIG = config.DATASETS[dataset]
    config.ontology_path = config.DATASET_CONFIG["ontology_file"]
    config.TTL_FILES = config.DATASET_CONFIG["ttl_files"]
    config.ENABLED_DATABASES = config.DATASET_CONFIG["enabled_databases"]

    # 更新数据库配置
    config.Neo4j_config['database'] = config.DATASET_CONFIG["databases"]["neo4j"]["database"]
    config.MySQL_config['database'] = config.DATASET_CONFIG["databases"]["mysql_main"]["database"]
    config.Postgre_config['database'] = config.DATASET_CONFIG["databases"]["postgresql"]["database"]

    # 更新GutMDisorder配置
    if "mysql_disorder" in config.DATASET_CONFIG["databases"]:
        config.GutMDisorder_config = {
            'host': "localhost",
            'user': config.MySQL_user,
            'password': config.MySQL_pwd,
            'database': config.DATASET_CONFIG["databases"]["mysql_disorder"]["database"]
        }
    else:
        config.GutMDisorder_config = None

    print(f"✅ 数据集已切换为: {dataset}")
    global processor
    processor = None

    print(f"🚀 已重置 QueryProcessor，当前本体路径: {config.ontology_path}")
    return jsonify({'success': True, 'current_dataset': dataset})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)