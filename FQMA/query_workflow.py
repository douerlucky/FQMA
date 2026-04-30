from __future__ import annotations

import os
import sys
import json
import re
from typing import Any, Callable, Dict, List, Optional, TypedDict

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph

# Ensure local project modules are resolved before similarly named third-party packages.
# before similarly named third-party packages from site-packages.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR in sys.path:
    sys.path.remove(CURRENT_DIR)
sys.path.insert(0, CURRENT_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import config
from agents.QueryAdaptive import SubQueryExecutor, SubQueryScheduler
from agents.QueryPlanningAndGeneration import QueryPlanner, SparQLGenerator
from agents.ResultAggregation import ResultAggregation
from agents.SemanticQueryRepair import QueryChecker, QueryRepairer

try:
    from config import LLM_CHECK_MODE
except ImportError:
    LLM_CHECK_MODE = "advisory"


class QueryWorkflowState(TypedDict, total=False):
    question: str
    thinking_callback: Optional[Callable[[str], None]]
    subqueries: List[Dict[str, Any]]
    current_index: int
    current_subquery: Optional[Dict[str, Any]]
    current_sparql: str
    current_check_details: str
    current_check_passed: bool
    selected_database: str
    current_converted_query: str
    repair_iteration: int
    max_repair_iterations: int
    final_sparqls: List[str]
    converted_queries: List[str]
    query_results: Dict[int, List[Any]]
    tables: str
    merged_table: str
    merged_csv: str
    explanation: str


class QueryWorkflow:
    def __init__(self):
        self.query_planner = QueryPlanner(config.model)
        self.sparql_generator = SparQLGenerator(config.model, config.ontology_path)
        self.scheduler = SubQueryScheduler(config.model)
        self.executor = SubQueryExecutor(config.model)
        self.aggregator = ResultAggregation(config.model)
        self.checker, self.repairer = self._build_repair_pipeline()
        self.graph = self._build_graph()

    def _build_repair_pipeline(self):
        return (
            QueryChecker(config.ontology_path, config.model, llm_check_mode=LLM_CHECK_MODE),
            QueryRepairer(config.model),
        )

    def _build_graph(self):
        graph_builder = StateGraph(QueryWorkflowState)

        graph_builder.add_node("plan_subqueries", self._plan_subqueries)
        graph_builder.add_node("prepare_subquery", self._prepare_subquery)
        graph_builder.add_node("generate_sparql", self._generate_sparql)
        graph_builder.add_node("check_sparql", self._check_sparql)
        graph_builder.add_node("repair_sparql", self._repair_sparql)
        graph_builder.add_node("finalize_subquery", self._finalize_subquery)
        graph_builder.add_node("schedule_database", self._schedule_database)
        graph_builder.add_node("convert_query", self._convert_query)
        graph_builder.add_node("resolve_placeholders", self._resolve_placeholders)
        graph_builder.add_node("execute_query", self._execute_query)
        graph_builder.add_node("aggregate_results", self._aggregate_results)

        graph_builder.add_edge(START, "plan_subqueries")
        graph_builder.add_conditional_edges(
            "plan_subqueries",
            self._route_after_planning,
            {
                "prepare_subquery": "prepare_subquery",
                "aggregate_results": "aggregate_results",
            },
        )
        graph_builder.add_edge("prepare_subquery", "generate_sparql")
        graph_builder.add_edge("generate_sparql", "check_sparql")
        graph_builder.add_conditional_edges(
            "check_sparql",
            self._route_after_check,
            {
                "repair_sparql": "repair_sparql",
                "finalize_subquery": "finalize_subquery",
            },
        )
        graph_builder.add_conditional_edges(
            "repair_sparql",
            self._route_after_repair,
            {
                "check_sparql": "check_sparql",
                "finalize_subquery": "finalize_subquery",
            },
        )
        graph_builder.add_edge("finalize_subquery", "schedule_database")
        graph_builder.add_edge("schedule_database", "convert_query")
        graph_builder.add_edge("convert_query", "resolve_placeholders")
        graph_builder.add_edge("resolve_placeholders", "execute_query")
        graph_builder.add_conditional_edges(
            "execute_query",
            self._route_after_execute,
            {
                "prepare_subquery": "prepare_subquery",
                "aggregate_results": "aggregate_results",
            },
        )
        graph_builder.add_edge("aggregate_results", END)

        return graph_builder.compile()

    def run(
        self,
        question: str,
        thinking_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        try:
            print("当前数据集: " + config.CURRENT_DATASET)
            final_state = self.graph.invoke(
                {
                    "question": question,
                    "thinking_callback": thinking_callback,
                    "subqueries": [],
                    "current_index": 0,
                    "current_subquery": None,
                    "current_sparql": "",
                    "current_check_details": "",
                    "current_check_passed": False,
                    "selected_database": "",
                    "current_converted_query": "",
                    "repair_iteration": 0,
                    "max_repair_iterations": max(config.iter_nums, 0),
                    "final_sparqls": [],
                    "converted_queries": [],
                    "query_results": {},
                    "tables": "",
                    "merged_table": "",
                    "merged_csv": "",
                    "explanation": "",
                },
                config={"recursion_limit": getattr(config, "GRAPH_RECURSION_LIMIT", 200)},
            )
            return {
                "success": True,
                "code": 200,
                "subqueries": final_state.get("subqueries", []),
                "results": final_state.get("query_results", {}),
                "tables": final_state.get("tables", ""),
                "merged_table": final_state.get("merged_table", ""),
                "merged_csv": final_state.get("merged_csv", ""),
                "explanation": final_state.get("explanation", ""),
            }
        except GraphRecursionError as exc:
            recursion_limit = getattr(config, "GRAPH_RECURSION_LIMIT", 200)
            self._emit(
                {"thinking_callback": thinking_callback},
                f"工作流步数超过上限 {recursion_limit}，请提高 FQMA_GRAPH_RECURSION_LIMIT 或检查图路由是否形成循环",
            )
            return {
                "success": False,
                "code": 500,
                "error": str(exc),
            }
        except Exception as exc:
            self._emit({"thinking_callback": thinking_callback}, f"处理过程中出现异常: {exc}")
            return {
                "success": False,
                "code": 500,
                "error": str(exc),
            }

    def _emit(self, state: QueryWorkflowState, message: str):
        callback = state.get("thinking_callback")
        if callback:
            callback(message)

    def _resolve_dependencies(self, state: QueryWorkflowState) -> List[Dict[str, Any]]:
        current_subquery = state.get("current_subquery") or {}
        subqueries = state.get("subqueries", [])
        dependencies: List[Dict[str, Any]] = []

        for dependency_id in current_subquery.get("dependencies", []):
            dependency_index = dependency_id - 1
            if 0 <= dependency_index < len(subqueries):
                dependencies.append(subqueries[dependency_index])

        return dependencies

    def _plan_subqueries(self, state: QueryWorkflowState) -> QueryWorkflowState:
        self._emit(state, "正在分解问题...")
        subqueries = self.query_planner.get_subqueries(state["question"])
        self._emit(state, f"分解得到 {len(subqueries)} 个子查询")
        return {
            "subqueries": subqueries,
            "current_index": 0,
            "final_sparqls": [],
            "converted_queries": [],
            "query_results": {},
            "tables": "",
            "merged_table": "",
            "merged_csv": "",
            "explanation": "",
        }

    def _route_after_planning(self, state: QueryWorkflowState) -> str:
        if state.get("subqueries"):
            return "prepare_subquery"
        return "aggregate_results"

    def _prepare_subquery(self, state: QueryWorkflowState) -> QueryWorkflowState:
        current_index = state["current_index"]
        current_subquery = state["subqueries"][current_index]
        self._emit(state, f"正在处理第 {current_index + 1} 个子查询")
        return {
            "current_subquery": current_subquery,
            "current_sparql": "",
            "current_check_details": "",
            "current_check_passed": False,
            "selected_database": "",
            "current_converted_query": "",
            "repair_iteration": 0,
        }

    def _generate_sparql(self, state: QueryWorkflowState) -> QueryWorkflowState:
        current_index = state["current_index"]
        current_subquery = state["current_subquery"] or {}
        self._emit(state, f"正在生成第 {current_index + 1} 个 SPARQL 查询...")
        dependencies = self._resolve_dependencies(state)
        sparql_query = self.sparql_generator.generate_sparql(
            current_subquery.get("question", ""),
            dependencies,
        )
        sparql_query = self._ensure_dependency_placeholders(sparql_query, dependencies)
        self._emit(state, f"第 {current_index + 1} 个 SPARQL 查询生成完成")
        return {"current_sparql": sparql_query}

    def _ensure_dependency_placeholders(
        self,
        sparql_query: str,
        dependencies: List[Dict[str, Any]],
    ) -> str:
        """
        Keep dependency constraints when the LLM forgets the placeholder filter.

        The check is schema-agnostic: if an upstream subquery SELECTs ?x and the
        current SPARQL also uses ?x, the current query must constrain ?x with
        <<SUBQUERY_n>> unless it already did so. This prevents a dependent query
        from accidentally widening to the whole database.
        """
        if not dependencies:
            return sparql_query

        query = sparql_query
        current_vars = self._extract_sparql_variables(query)
        filter_lines: List[str] = []

        for dependency in dependencies:
            upstream_id = dependency.get("id")
            if not upstream_id:
                continue

            placeholder = f"<<SUBQUERY_{upstream_id}>>"
            if placeholder in query:
                continue

            upstream_vars = self._extract_select_variables(dependency.get("generated_sparql", ""))
            shared_vars = [var for var in upstream_vars if var in current_vars]
            if not shared_vars:
                continue

            filter_var = shared_vars[0]
            filter_lines.append(f"  FILTER (?{filter_var} IN ({placeholder}))")

        if not filter_lines:
            return query

        closing_brace = query.rfind("}")
        if closing_brace == -1:
            return query.rstrip() + "\n" + "\n".join(filter_lines)

        return query[:closing_brace].rstrip() + "\n" + "\n".join(filter_lines) + "\n" + query[closing_brace:]

    def _extract_select_variables(self, sparql_query: str) -> List[str]:
        match = re.search(r"\bSELECT\b\s+(?:DISTINCT\s+)?(?P<select>.*?)\bWHERE\b", sparql_query, re.IGNORECASE | re.DOTALL)
        if not match:
            return []
        return re.findall(r"\?([A-Za-z_][A-Za-z0-9_]*)", match.group("select"))

    def _extract_sparql_variables(self, sparql_query: str) -> set[str]:
        return set(re.findall(r"\?([A-Za-z_][A-Za-z0-9_]*)", sparql_query))

    def _check_sparql(self, state: QueryWorkflowState) -> QueryWorkflowState:
        current_index = state["current_index"]
        current_subquery = state["current_subquery"] or {}
        self._emit(state, f"第 {current_index + 1} 个子查询正在评估")
        is_compliant, details = self.checker.check_query(
            state["current_sparql"],
            current_subquery.get("question"),
        )
        self._emit(state, f"检查结果: {'合规' if is_compliant else '不合规'}")
        return {
            "current_check_passed": is_compliant,
            "current_check_details": details,
        }

    def _route_after_check(self, state: QueryWorkflowState) -> str:
        if state.get("current_check_passed"):
            return "finalize_subquery"
        if state["repair_iteration"] >= state["max_repair_iterations"]:
            return "finalize_subquery"
        return "repair_sparql"

    def _repair_sparql(self, state: QueryWorkflowState) -> QueryWorkflowState:
        current_index = state["current_index"]
        current_subquery = state["current_subquery"] or {}
        next_iteration = state["repair_iteration"] + 1
        self._emit(state, f"语义不合规，进行第 {next_iteration} 次迭代修复")
        repaired_sparql = self.repairer.repair_sparql(
            current_subquery.get("question", ""),
            state.get("current_check_details", ""),
            state["current_sparql"],
        )
        self._emit(state, f"第 {current_index + 1} 个子查询的第 {next_iteration} 次修复完成")
        return {
            "current_sparql": repaired_sparql,
            "repair_iteration": next_iteration,
        }

    def _route_after_repair(self, state: QueryWorkflowState) -> str:
        if state["repair_iteration"] >= state["max_repair_iterations"]:
            return "finalize_subquery"
        return "check_sparql"

    def _finalize_subquery(self, state: QueryWorkflowState) -> QueryWorkflowState:
        final_sparqls = list(state.get("final_sparqls", []))
        final_sparqls.append(state["current_sparql"])
        subqueries = list(state.get("subqueries", []))
        current_index = state.get("current_index", 0)
        if 0 <= current_index < len(subqueries):
            updated = dict(subqueries[current_index])
            updated["generated_sparql"] = state.get("current_sparql", "")
            subqueries[current_index] = updated
        return {"final_sparqls": final_sparqls, "subqueries": subqueries}

    def _schedule_database(self, state: QueryWorkflowState) -> QueryWorkflowState:
        current_index = state["current_index"]
        current_subquery = state["current_subquery"] or {}
        self._emit(state, f"子查询 {current_index + 1} 正在选择数据库...")
        selected_db = self.scheduler.select_database(
            state["current_sparql"],
            current_subquery.get("question", ""),
        )
        self._emit(state, f"子查询 {current_index + 1} 选择数据库: {selected_db}")
        return {"selected_database": selected_db}

    def _convert_query(self, state: QueryWorkflowState) -> QueryWorkflowState:
        current_index = state["current_index"]
        converted_query = self.executor.convert_to_target_query(
            state["current_sparql"],
            state["selected_database"],
        )
        self._emit(state, f"子查询 {current_index + 1} 转换后的查询语言: {converted_query}")
        return {"current_converted_query": converted_query}

    def _resolve_placeholders(self, state: QueryWorkflowState) -> QueryWorkflowState:
        converted_query = state["current_converted_query"]
        if self.executor.has_placeholder(converted_query):
            self._emit(state, "检测到占位符，正在替换上游子查询结果")
            converted_query = self.executor.replace_placeholders(
                converted_query,
                state.get("query_results", {}),
            )
            self._emit(state, converted_query)
        else:
            self._emit(state, "无需使用上一个查询的结果作为输入")
        return {"current_converted_query": converted_query}

    def _execute_query(self, state: QueryWorkflowState) -> QueryWorkflowState:
        current_index = state["current_index"]
        self._emit(state, f"正在执行第 {current_index + 1} 个查询...")
        result = self.executor.execute_in_database(
            state["current_converted_query"],
            state["selected_database"],
        )

        query_results = dict(state.get("query_results", {}))
        query_results[current_index + 1] = result

        converted_queries = list(state.get("converted_queries", []))
        converted_queries.append(state["current_converted_query"])

        self._emit(state, f"子查询 {current_index + 1} 查询结果: {result}")
        return {
            "query_results": query_results,
            "converted_queries": converted_queries,
            "current_index": current_index + 1,
        }

    def _route_after_execute(self, state: QueryWorkflowState) -> str:
        if state["current_index"] < len(state.get("subqueries", [])):
            return "prepare_subquery"
        return "aggregate_results"

    def _aggregate_results(self, state: QueryWorkflowState) -> QueryWorkflowState:
        self._emit(state, "=== 结果聚合 ===")
        tables, explanation, merged_table, merged_csv = self.aggregator.process(
            state["question"],
            state.get("converted_queries", []),
            state.get("query_results", {}),
        )
        self._emit(state, "结果聚合完成")
        return {
            "tables": tables,
            "merged_table": merged_table,
            "merged_csv": merged_csv,
            "explanation": explanation,
        }


def _console_log(message: str):
    print(f"[workflow] {message}")


def main():
    question = "请识别在人类宿主中，在ketogenic diet饮食干预下丰度显著上升的肠道微生物群。"
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:]).strip() or question

    print("启动 QueryWorkflow 单文件调试模式")
    print(f"当前数据集: {config.CURRENT_DATASET}")
    print(f"问题: {question}")

    workflow = QueryWorkflow()
    result = workflow.run(question, thinking_callback=_console_log)
    print("\n最终结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success", False):
        sys.exit(1)


if __name__ == "__main__":
    main()
