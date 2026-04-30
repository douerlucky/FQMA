import logging
import os
import queue
import sys
import uuid
from datetime import datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR in sys.path:
    sys.path.remove(CURRENT_DIR)
sys.path.insert(0, CURRENT_DIR)

import config
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO

from query_workflow import QueryWorkflow

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

app = Flask(__name__)
app.config["CORS_HEADERS"] = "Content-Type"
app.config["JSON_AS_ASCII"] = False

CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=False,
    engineio_logger=False,
)


class PrintRedirector:
    def __init__(self, socketio_instance, message_id):
        self.socketio = socketio_instance
        self.message_id = message_id
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.output_queue = queue.Queue()
        self.is_active = True

    def write(self, text):
        if self.is_active and text.strip():
            self.socketio.emit(
                "thinking",
                {
                    "type": "print",
                    "message_id": self.message_id,
                    "data": text.strip(),
                },
            )
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
sessions = {}
processor = None

logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def get_print_redirector(message_id):
    if message_id not in print_redirectors:
        print_redirectors[message_id] = PrintRedirector(socketio, message_id)
    return print_redirectors[message_id]


def cleanup_print_redirector(message_id):
    if message_id in print_redirectors:
        print_redirectors[message_id].is_active = False
        del print_redirectors[message_id]


def get_processor():
    global processor
    if processor is None:
        processor = QueryProcessor()
    return processor


class QueryProcessor:
    def __init__(self):
        self.workflow = QueryWorkflow()

    def process_query(self, question, thinking_callback=None, message_id=None):
        redirector = None
        try:
            print("当前数据集: " + config.CURRENT_DATASET)

            if message_id:
                redirector = get_print_redirector(message_id)
                redirector.__enter__()

            return self.workflow.run(question, thinking_callback=thinking_callback)
        except Exception as exc:
            import traceback

            err_msg = str(exc)
            stack = traceback.format_exc()
            logging.error(f"处理查询异常: {err_msg}\n{stack}")
            if thinking_callback:
                thinking_callback(f"处理过程中出现异常: {err_msg}")
            return {
                "success": False,
                "code": 500,
                "error": err_msg,
            }
        finally:
            if redirector:
                redirector.__exit__(None, None, None)
                cleanup_print_redirector(message_id)


@app.route("/api/query", methods=["POST", "OPTIONS"])
def handle_query():
    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json(silent=True) or {}
    question = data.get("question")
    session_id = data.get("session_id")
    message_id = data.get("message_id")

    if not question:
        logging.warning("收到空问题请求")
        return jsonify({"error": "问题不能为空", "code": 400}), 400

    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = []

    def thinking_callback(msg):
        socketio.emit(
            "thinking",
            {
                "type": "thinking",
                "message_id": message_id,
                "data": msg,
            },
        )

    current_processor = get_processor()
    result = current_processor.process_query(
        question,
        thinking_callback=thinking_callback,
        message_id=message_id,
    )

    socketio.emit(
        "thinking",
        {
            "type": "result",
            "message_id": message_id,
            "data": result,
        },
    )

    query_record = {
        "id": str(uuid.uuid4()),
        "question": question,
        "response": result,
        "timestamp": datetime.now().isoformat(),
    }
    sessions[session_id].append(query_record)

    return jsonify(
        {
            "session_id": session_id,
            "query_id": query_record["id"],
            "result": result,
        }
    )


@app.route("/api/history/<session_id>", methods=["GET", "OPTIONS"])
def get_history(session_id):
    if request.method == "OPTIONS":
        return "", 204

    if session_id not in sessions:
        logging.warning(f"会话不存在: {session_id}")
        return jsonify({"error": "会话不存在", "code": 404}), 404

    return jsonify(
        {
            "session_id": session_id,
            "history": sessions[session_id],
        }
    )


@app.route("/api/health", methods=["GET", "OPTIONS"])
def health_check():
    if request.method == "OPTIONS":
        return "", 204

    logging.info("健康检查接口被调用")
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


@app.route("/api/switch-dataset", methods=["POST", "OPTIONS"])
def switch_dataset():
    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json(silent=True) or {}
    dataset = data.get("dataset")

    if dataset not in ["GMQA", "RODI"]:
        return jsonify({"error": "不支持的数据集"}), 400

    config.CURRENT_DATASET = dataset
    config.DATASET_CONFIG = config.DATASETS[dataset]
    config.ontology_path = config.DATASET_CONFIG["ontology_file"]
    config.TTL_FILES = config.DATASET_CONFIG["ttl_files"]
    config.ENABLED_DATABASES = config.DATASET_CONFIG["enabled_databases"]

    config.Neo4j_config["database"] = config.DATASET_CONFIG["databases"]["neo4j"]["database"]
    config.MySQL_config["database"] = config.DATASET_CONFIG["databases"]["mysql_main"]["database"]
    config.Postgre_config["database"] = config.DATASET_CONFIG["databases"]["postgresql"]["database"]

    if "mysql_disorder" in config.DATASET_CONFIG["databases"]:
        config.GutMDisorder_config = {
            "host": "localhost",
            "user": config.MySQL_user,
            "password": config.MySQL_pwd,
            "database": config.DATASET_CONFIG["databases"]["mysql_disorder"]["database"],
        }
    else:
        config.GutMDisorder_config = None

    print(f"Dataset switched to: {dataset}")

    global processor
    processor = None

    print(f"QueryProcessor reset. Current ontology path: {config.ontology_path}")
    return jsonify({"success": True, "current_dataset": dataset})


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=5001,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
