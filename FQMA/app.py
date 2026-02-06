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
from config import ontology_path, model, iter_nums

app = Flask(__name__)
CORS(app)  # 允许跨域请求
socketio = SocketIO(app, cors_allowed_origins="*")


# 全局print重定向系统
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
            # 发送到WebSocket
            self.socketio.emit('thinking', {
                'type': 'print',
                'message_id': self.message_id,
                'data': text.strip()
            })
            # 同时写入原始stdout
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


# 全局print重定向管理器
print_redirectors = {}


def get_print_redirector(message_id):
    """获取或创建print重定向器"""
    if message_id not in print_redirectors:
        print_redirectors[message_id] = PrintRedirector(socketio, message_id)
    return print_redirectors[message_id]


def cleanup_print_redirector(message_id):
    """清理print重定向器"""
    if message_id in print_redirectors:
        print_redirectors[message_id].is_active = False
        del print_redirectors[message_id]


# 日志配置
logging.basicConfig(filename='app.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

# 存储会话历史（实际应用中应该使用数据库）
sessions = {}


class QueryProcessor:
    def __init__(self):
        self.query_planner = QueryPlanner(model)
        self.sparql_generator = SparQLGenerator(model, ontology_path)
        self.scheduler = SubQueryScheduler(model)
        self.executor = SubQueryExecutor(model)
        self.aggregator = ResultAggregation(model)
        self.scorer = QueryChecker(ontology_path)
        self.repairer = QueryRepairer(model)

    def process_query(self, question, thinking_callback=None, message_id=None):
        """
        处理用户查询的主函数，支持思考过程流式回调和print重定向
        """
        redirector = None
        try:
            # 设置print重定向
            if message_id:
                redirector = get_print_redirector(message_id)
                redirector.__enter__()

            # 1. 获取子查询
            if thinking_callback:
                thinking_callback("正在分解问题……")
            subqueries = self.query_planner.get_subqueries(question)
            if thinking_callback:
                thinking_callback(f"分解得到 {len(subqueries)} 个子查询")

            # 2. 生成SPARQL查询
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

            # 3. 评分和修复（修改为与main.py一致的逻辑）
            final_sparqls = []
            for i, sparql in enumerate(sparqls):
                current_sparql = sparql
                if thinking_callback:
                    thinking_callback(f"第{i + 1}个子查询正在评价")

                for repair_iter in range(iter_nums):
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

            # 4. 执行查询
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

            # 5. 聚合结果
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
            # 清理print重定向
            if redirector:
                redirector.__exit__(None, None, None)
                cleanup_print_redirector(message_id)


# 创建查询处理器实例
processor = QueryProcessor()


@app.route('/api/query', methods=['POST'])
def handle_query():
    """处理用户查询请求，流式推送思考过程和最终结果"""
    data = request.json
    question = data.get('question')
    session_id = data.get('session_id')
    message_id = data.get('message_id')

    if not question:
        logging.warning("收到空问题请求")
        return jsonify({"error": "问题不能为空", "code": 400}), 400

    # 创建新会话或获取现有会话
    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = []

    # 定义流式推送思考过程的函数
    def thinking_callback(msg):
        socketio.emit('thinking', {
            'type': 'thinking',
            'message_id': message_id,
            'data': msg
        })

    # 处理查询，传递thinking_callback和message_id
    result = processor.process_query(question, thinking_callback=thinking_callback, message_id=message_id)

    # 推送最终结果
    socketio.emit('thinking', {
        'type': 'result',
        'message_id': message_id,
        'data': result
    })

    # 保存到会话历史
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


@app.route('/api/history/<session_id>', methods=['GET'])
def get_history(session_id):
    """获取会话历史"""
    if session_id not in sessions:
        logging.warning(f"会话不存在: {session_id}")
        return jsonify({"error": "会话不存在", "code": 404}), 404

    return jsonify({
        "session_id": session_id,
        "history": sessions[session_id]
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    logging.info("健康检查接口被调用")
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)