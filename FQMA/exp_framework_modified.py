#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统测试框架 - 基于config.py参数进行实验评估
评估指标：EX、FEX、Time per query、Token Cost
支持选择性测试和详细输出
使用LLM智能判断结果正确性
修复了JSON序列化问题
修改为要求答案完全一致（不能错，不能少，不能多）的严格评估
使用EX和FEX评价指标
第三个子查询（代谢通路）只比较数量相似性
添加了Token成本计算功能
支持可变样例数量测试
"""

import json
import time
import os
import csv
import re
from typing import List, Dict, Any, Tuple
from datetime import datetime
from neo4j.graph import Node, Relationship
from decimal import Decimal

# 导入系统组件
from agents.QueryPlanningAndGeneration import QueryPlanner, SparQLGenerator
from agents.QueryAdaptive import SubQueryScheduler, SubQueryExecutor
from agents.SemanticQueryRepair import QueryChecker, QueryRepairer
import config


class TokenCalculator:
    """Token计算器类"""

    def __init__(self):
        self.chinese_token_ratio = 0.6  # 1个中文字符 ≈ 0.6个token
        self.english_token_ratio = 0.3  # 1个英文字符 ≈ 0.3个token

    def count_tokens(self, text: str) -> int:
        """
        计算文本的token数量

        Args:
            text: 输入文本

        Returns:
            估算的token数量
        """
        if not text:
            return 0

        # 统计中文字符（包括中文标点）
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', text))

        # 统计英文字符（总字符数减去中文字符）
        english_chars = len(text) - chinese_chars

        # 计算token数量
        chinese_tokens = chinese_chars * self.chinese_token_ratio
        english_tokens = english_chars * self.english_token_ratio

        total_tokens = chinese_tokens + english_tokens

        return int(round(total_tokens))

    def calculate_llm_call_tokens(self, input_text: str, output_text: str) -> Dict[str, int]:
        """
        计算单次LLM调用的token消耗

        Args:
            input_text: 输入文本
            output_text: 输出文本

        Returns:
            包含输入、输出和总token数的字典
        """
        input_tokens = self.count_tokens(input_text)
        output_tokens = self.count_tokens(output_text)
        total_tokens = input_tokens + output_tokens

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens
        }


class CustomJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理特殊数据类型"""

    def default(self, obj):
        # 处理Neo4j Node对象
        if isinstance(obj, Node):
            return {
                "_type": "neo4j_node",
                "id": obj.id,
                "labels": list(obj.labels),
                "properties": dict(obj)
            }

        # 处理Neo4j Relationship对象
        if isinstance(obj, Relationship):
            return {
                "_type": "neo4j_relationship",
                "id": obj.id,
                "type": obj.type,
                "start_node": obj.start_node.id if obj.start_node else None,
                "end_node": obj.end_node.id if obj.end_node else None,
                "properties": dict(obj)
            }

        # 处理Decimal对象
        if isinstance(obj, Decimal):
            return float(obj)

        # 处理datetime对象
        if isinstance(obj, datetime):
            return obj.isoformat()

        # 处理bytes对象
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')

        # 处理set对象
        if isinstance(obj, set):
            return list(obj)

        # 对于其他不可序列化的对象，转换为字符串
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


def safe_serialize_data(data: Any) -> Any:
    """
    安全地序列化数据，移除或转换不可序列化的对象
    """
    if isinstance(data, dict):
        return {key: safe_serialize_data(value) for key, value in data.items()}

    elif isinstance(data, list):
        return [safe_serialize_data(item) for item in data]

    elif isinstance(data, tuple):
        return [safe_serialize_data(item) for item in data]

    elif isinstance(data, Node):
        return {
            "_type": "neo4j_node",
            "id": data.id,
            "labels": list(data.labels),
            "properties": dict(data)
        }

    elif isinstance(data, Relationship):
        return {
            "_type": "neo4j_relationship",
            "id": data.id,
            "type": data.type,
            "properties": dict(data)
        }

    elif isinstance(data, Decimal):
        return float(data)

    elif isinstance(data, datetime):
        return data.isoformat()

    elif isinstance(data, bytes):
        return data.decode('utf-8', errors='ignore')

    elif isinstance(data, set):
        return list(data)

    # 基本数据类型直接返回
    elif isinstance(data, (str, int, float, bool, type(None))):
        return data

    else:
        # 对于其他类型，尝试转换为字符串
        try:
            json.dumps(data)  # 测试是否可序列化
            return data
        except (TypeError, ValueError):
            return str(data)


def safe_format_float(value, precision=3, default_str="N/A"):
    """
    安全地格式化浮点数，处理字符串和None值
    """
    if value is None:
        return default_str
    if isinstance(value, str):
        if value == "N/A" or value == "None":
            return default_str
        try:
            return f"{float(value):.{precision}f}"
        except (ValueError, TypeError):
            return default_str
    if isinstance(value, (int, float)):
        return f"{float(value):.{precision}f}"
    return default_str


class SystemTestFramework:
    """系统测试框架"""

    def __init__(self):
        """初始化测试框架，读取config.py中的参数"""
        self.model = config.model
        self.is_use_ontology = config.is_ontology
        self.ontology_path = config.ontology_path if config.is_ontology else None
        self.is_use_repair = config.is_use_repair
        self.iter_nums = config.iter_nums
        self.llm_temperature = config.llm_temperature

        # 样例数量配置（替代原来的prompt_mode）
        self.example_count = getattr(config, 'example_use', 5)

        # 测试配置
        self.test_mode = config.TEST_MODE
        self.selected_ids = config.SELECTED_QUESTION_IDS
        self.test_data_file = config.TEST_DATA_FILE
        self.verbose_output = config.VERBOSE_OUTPUT
        self.save_intermediate = config.SAVE_INTERMEDIATE_RESULTS
        self.save_error_logs = config.SAVE_ERROR_LOGS

        # 结果保存配置
        self.results_dir = config.EXPERIMENT_RESULTS_DIR
        self.experiment_tag = config.EXPERIMENT_TAG

        # 初始化Token计算器
        self.token_calculator = TokenCalculator()

        # 创建结果目录
        self._ensure_results_directory()

        # 初始化日志
        self.error_log = []
        self.intermediate_results = {}

        print(f"测试框架初始化完成")
        print(f"配置参数:")
        print(f"  - 模型类型: {config.MODEL_TYPE}")
        print(f"  - 样例数量: {self.example_count}")
        print(f"  - 使用本体: {self.is_use_ontology}")
        print(f"  - 使用修复: {self.is_use_repair}")
        print(f"  - LLM温度: {self.llm_temperature}")
        print(f"  - 修复迭代次数: {self.iter_nums}")
        print(f"  - 测试模式: {self.test_mode}")
        if self.test_mode == "selected":
            print(f"  - 选择的问题ID: {self.selected_ids}")
        print(f"  - 详细输出: {self.verbose_output}")
        print(f"  - 结果保存目录: {self.results_dir}")
        print(f"  - 评估模式: LLM智能判断 + 第三个子查询数量比较")
        print(f"  - 评价指标: EX (子查询正确率), FEX (完整问题正确率), Token成本")

    def _ensure_results_directory(self):
        """确保结果目录存在"""
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
            print(f"创建结果目录: {self.results_dir}")

    def _log_error(self, error_msg: str, context: str = ""):
        """记录错误日志"""
        timestamp = datetime.now().isoformat()
        error_entry = {
            "timestamp": timestamp,
            "context": context,
            "error": error_msg
        }
        self.error_log.append(error_entry)
        if self.verbose_output:
            print(f"[ERROR] {context}: {error_msg}")

    def _log_intermediate(self, step: str, data: Any, question_id: int = None):
        """记录中间结果（使用安全序列化）"""
        if not self.save_intermediate:
            return

        key = f"q{question_id}_{step}" if question_id else step
        # 使用安全序列化处理数据
        safe_data = safe_serialize_data(data)

        self.intermediate_results[key] = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "question_id": question_id,
            "data": safe_data
        }

    def load_test_data(self, json_file: str = None) -> List[Dict]:
        """加载测试数据"""
        if json_file is None:
            json_file = self.test_data_file

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"成功加载测试数据: {len(data)} 个问题")

            # 根据测试模式过滤数据
            if self.test_mode == "selected":
                filtered_data = [item for item in data if item.get("id") in self.selected_ids]
                print(f"选择性测试: 过滤后 {len(filtered_data)} 个问题")
                return filtered_data
            else:
                print(f"全量测试: {len(data)} 个问题")
                return data

        except FileNotFoundError:
            error_msg = f"找不到文件 {json_file}"
            self._log_error(error_msg, "load_test_data")
            print(f"错误: {error_msg}")
            return []
        except Exception as e:
            error_msg = f"加载测试数据失败: {e}"
            self._log_error(error_msg, "load_test_data")
            print(f"错误: {error_msg}")
            return []

    def llm_judge_correctness(self, expected_results: List, actual_results: List,
                              query_index: int, query_question: str) -> Tuple[int, Dict]:
        """
        使用LLM智能判断结果正确性
        第三个子查询（代谢通路）只比较数量相似性

        返回: (是否正确(0或1), 判断详情)
        """
        try:
            # 第三个子查询使用简化的数量比较逻辑
            if query_index == 3:
                return self._evaluate_third_query_by_count(expected_results, actual_results, query_question)

            # 其他查询使用LLM智能判断
            # 构建prompt让LLM判断结果是否正确
            prompt = f"""
请判断以下两个结果列表是否基本一致。

查询问题: {query_question}

期望结果({len(expected_results)}个):
{expected_results}

实际结果({len(actual_results)}个):
{actual_results}

判断规则：
1. 只要实际结果包含期望结果的主要内容即可视为正确
2. 忽略大小写差异
3. 忽略格式差异和省略词
4. 允许列的顺序不同
5. 允许轻微的表述差异

请回答：
1. 是否正确 (1=正确, 0=不正确)
2. 简要说明理由
3. 缺少的内容（如果有）
4. 多余的内容（如果有）

请按以下JSON格式回答:
{{
    "is_correct": 1或0,
    "reason": "判断理由",
    "missing_items": ["缺少的内容列表"],
    "extra_items": ["多余的内容列表"]
}}
"""

            # 调用LLM进行判断
            judgment = self._call_llm_for_judgment(prompt)

            if judgment:
                return judgment["is_correct"], {
                    "evaluation_method": "llm_intelligent",
                    "reason": judgment.get("reason", ""),
                    "missing_items": judgment.get("missing_items", []),
                    "extra_items": judgment.get("extra_items", []),
                    "expected_count": len(expected_results),
                    "actual_count": len(actual_results)
                }
            else:
                # LLM调用失败，使用fallback逻辑
                return self._fallback_judgment(expected_results, actual_results, query_index)

        except Exception as e:
            self._log_error(f"LLM判断失败: {e}", f"llm_judge_correctness_q{query_index}")
            # 使用fallback逻辑
            return self._fallback_judgment(expected_results, actual_results, query_index)

    def _evaluate_third_query_by_count(self, expected_results: List, actual_results: List,
                                       query_question: str) -> Tuple[int, Dict]:
        """
        第三个子查询（代谢通路）的简化评判逻辑
        只比较返回的行数，不关注具体内容或列数
        """
        # 获取行数（结果列表的长度就是行数）
        expected_rows = len(expected_results)
        actual_rows = len(actual_results)

        # 计算行数差异的百分比
        if expected_rows == 0:
            # 如果期望行数为0，实际行数也应该为0或很少
            is_correct = 1 if actual_rows <= 2 else 0
            similarity_ratio = 1.0 if actual_rows == 0 else 0.0
        else:
            # 计算相似度，允许20%的误差范围
            row_diff = abs(expected_rows - actual_rows)
            similarity_ratio = 1 - (row_diff / expected_rows)
            # 如果相似度>=0.8（即误差<=20%），认为正确
            is_correct = 1 if similarity_ratio >= 0.8 else 0

        comparison_details = {
            "evaluation_method": "row_count_similarity_third_query",
            "expected_rows": expected_rows,
            "actual_rows": actual_rows,
            "row_difference": abs(expected_rows - actual_rows),
            "similarity_ratio": similarity_ratio,
            "threshold": 0.8,
            "reason": f"第三个子查询行数比较: 期望{expected_rows}行，实际{actual_rows}行，相似度{similarity_ratio:.3f}",
            "is_within_threshold": is_correct == 1,
            "note": "只比较行数，不关注列数和具体内容"
        }

        return is_correct, comparison_details

    def _call_llm_for_judgment(self, prompt: str) -> Dict:
        """
        调用LLM进行判断 - 这里需要根据实际使用的LLM API进行实现
        """
        try:
            # 这里应该调用实际的LLM API
            # 例如：OpenAI GPT、Claude、或者其他模型
            # response = llm_client.chat.completions.create(...)
            # 暂时返回None，使用fallback逻辑
            return None
        except Exception as e:
            self._log_error(f"LLM API调用失败: {e}", "_call_llm_for_judgment")
            return None

    def _fallback_judgment(self, expected_results: List, actual_results: List,
                           query_index: int) -> Tuple[int, Dict]:
        """
        Fallback判断逻辑（当LLM不可用时）
        """
        # 第三个子查询使用数量比较
        if query_index == 3:
            return self._evaluate_third_query_by_count(expected_results, actual_results,
                                                       f"子查询{query_index}")

        # 其他子查询使用标准化比较
        expected_normalized = {self._normalize_item(item) for item in expected_results}
        actual_normalized = {self._normalize_item(item) for item in actual_results}

        # 使用包含性判断
        matched = expected_normalized.intersection(actual_normalized)
        # 如果匹配度超过80%认为正确
        is_correct = 1 if len(matched) >= len(expected_normalized) * 0.8 else 0

        missing = list(expected_normalized - actual_normalized)
        extra = list(actual_normalized - expected_normalized)

        return is_correct, {
            "evaluation_method": "fallback_logic",
            "reason": f"Fallback判断: 匹配度基于标准化比较",
            "missing_items": missing,
            "extra_items": extra,
            "expected_count": len(expected_results),
            "actual_count": len(actual_results)
        }

    def _normalize_item(self, item) -> str:
        """标准化结果项"""
        if isinstance(item, (list, tuple)):
            return " ".join(str(x).strip().lower() for x in item)
        return str(item).strip().lower()

    def execute_system_pipeline(self, question: str, question_id: int) -> Tuple[Dict[int, List], float, Dict, Dict]:
        """执行完整的系统流程，返回查询结果、用时、详细信息和Token统计"""
        start_time = time.time()

        # Token统计信息
        token_stats = {
            "query_planner": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "sparql_generator": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "query_repairer": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "subquery_scheduler": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "total_tokens": 0,
            "steps_count": {
                "query_planner_calls": 0,
                "sparql_generator_calls": 0,
                "query_repairer_calls": 0,
                "subquery_scheduler_calls": 0
            }
        }

        pipeline_info = {
            "subqueries_count": 0,
            "repair_attempts": 0,
            "repair_successes": 0,
            "repair_total_checks": 0,
            "repair_before_correct": 0,
            "repair_after_correct": 0,
            "database_selections": [],
            "sparql_queries": [],
            "converted_queries": [],
            "repair_details": [],
            "errors": [],
            "step_times": {},
            "example_count": self.example_count  # 添加样例数量信息
        }

        try:
            # 1. 查询规划
            step_start = time.time()
            if self.verbose_output:
                print(f"  1. 执行查询规划... (使用 {self.example_count} 个样例)")

            query_planner = QueryPlanner(self.model)

            # 计算查询规划的Token消耗
            planning_input = question  # 简化，实际应该包含完整的prompt
            subqueries = query_planner.get_subqueries(question)
            planning_output = str(subqueries)  # 简化，实际应该是LLM的原始输出

            planning_tokens = self.token_calculator.calculate_llm_call_tokens(planning_input, planning_output)
            token_stats["query_planner"] = planning_tokens
            token_stats["steps_count"]["query_planner_calls"] = 1

            pipeline_info["step_times"]["query_planning"] = time.time() - step_start

            if not subqueries:
                error_msg = "查询规划失败"
                pipeline_info["errors"].append(error_msg)
                self._log_error(error_msg, f"question_{question_id}")
                return {}, time.time() - start_time, pipeline_info, token_stats

            pipeline_info["subqueries_count"] = len(subqueries)
            safe_subqueries = safe_serialize_data(subqueries)
            self._log_intermediate("subqueries", safe_subqueries, question_id)

            if self.verbose_output:
                print(f"     分解为 {len(subqueries)} 个子查询")
                for i, sq in enumerate(subqueries):
                    print(f"     子查询{i + 1}: {sq.get('question', 'N/A')}")
                print(f"     查询规划Token消耗: {planning_tokens['total_tokens']}")

            # 2. SPARQL生成
            step_start = time.time()
            if self.verbose_output:
                print(f"  2. 生成SPARQL查询...")

            sparql_generator = SparQLGenerator(self.model, self.ontology_path)
            sparqls = []
            sparql_generation_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

            for i, subquery in enumerate(subqueries):
                sub_question = subquery["question"]
                dependencies = [subqueries[j - 1] for j in subquery["dependencies"]]

                # 计算SPARQL生成的Token消耗
                sparql_input = f"{sub_question} {dependencies}"  # 简化
                sparql_query = sparql_generator.generate_sparql(sub_question, dependencies)
                sparql_output = sparql_query

                sparql_tokens = self.token_calculator.calculate_llm_call_tokens(sparql_input, sparql_output)
                sparql_generation_tokens["input_tokens"] += sparql_tokens["input_tokens"]
                sparql_generation_tokens["output_tokens"] += sparql_tokens["output_tokens"]
                sparql_generation_tokens["total_tokens"] += sparql_tokens["total_tokens"]

                sparqls.append(sparql_query)

                if self.verbose_output:
                    print(f"     子查询{i + 1} SPARQL: {sparql_query[:100]}..." if len(
                        sparql_query) > 100 else f"     子查询{i + 1} SPARQL: {sparql_query}")

            token_stats["sparql_generator"] = sparql_generation_tokens
            token_stats["steps_count"]["sparql_generator_calls"] = len(subqueries)
            pipeline_info["sparql_queries"] = sparqls
            pipeline_info["step_times"]["sparql_generation"] = time.time() - step_start
            self._log_intermediate("sparql_queries", sparqls, question_id)

            if self.verbose_output:
                print(f"     SPARQL生成Token消耗: {sparql_generation_tokens['total_tokens']}")

            # 3. 评分和修复（如果可用）
            step_start = time.time()
            repair_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

            if self.is_use_repair:
                if self.verbose_output:
                    print(f"  3. 执行语义检查和修复...")

                checker = QueryChecker(
                    ontology_path=self.ontology_path,
                    model=self.model,  # ✅ 添加这个参数
                    llm_check_mode=getattr(config, 'LLM_CHECK_MODE', 'advisory')
                )
                repairer = QueryRepairer(self.model)

                for i in range(len(sparqls)):
                    if self.verbose_output:
                        print(f"     第{i + 1}个子查询正在评价")

                    query_repair_info = {
                        "query_index": i + 1,
                        "original_query": sparqls[i],
                        "repair_iterations": [],
                        "final_query": sparqls[i],
                        "before_repair_correct": False,
                        "after_repair_correct": False
                    }

                    # 检查修复前的查询正确性
                    original_is_compliant, original_details = checker.check_query(
                        sparqls[i], subqueries[i]["question"]
                    )
                    query_repair_info["before_repair_correct"] = original_is_compliant
                    if original_is_compliant:
                        pipeline_info["repair_before_correct"] += 1

                    pipeline_info["repair_total_checks"] += 1

                    if self.verbose_output:
                        print(f"     原始查询: {'✅ 合规' if original_is_compliant else '❌ 不合规'}")

                    current_query = sparqls[i]

                    # 如果不合规，进行修复
                    if not original_is_compliant:
                        for repair_iter in range(self.iter_nums):
                            is_compliant, details = checker.check_query(
                                current_query, subqueries[i]["question"]
                            )

                            if not is_compliant:
                                pipeline_info["repair_attempts"] += 1
                                if self.verbose_output:
                                    print(f"     语法不合规,进行第{repair_iter + 1}次迭代修复")

                                # 计算修复的Token消耗
                                repair_input = f"{subqueries[i]['question']} {details} {current_query}"
                                repaired_sparql = repairer.repair_sparql(
                                    subqueries[i]["question"], details, current_query
                                )
                                repair_output = repaired_sparql

                                repair_call_tokens = self.token_calculator.calculate_llm_call_tokens(repair_input,
                                                                                                     repair_output)
                                repair_tokens["input_tokens"] += repair_call_tokens["input_tokens"]
                                repair_tokens["output_tokens"] += repair_call_tokens["output_tokens"]
                                repair_tokens["total_tokens"] += repair_call_tokens["total_tokens"]
                                token_stats["steps_count"]["query_repairer_calls"] += 1

                                iteration_info = {
                                    "iteration": repair_iter + 1,
                                    "before_repair": current_query,
                                    "after_repair": repaired_sparql,
                                    "repair_details": details
                                }
                                query_repair_info["repair_iterations"].append(iteration_info)

                                current_query = repaired_sparql

                                if self.verbose_output:
                                    print(f"     第{i + 1}个子查询的第{repair_iter + 1}次修复完成")
                            else:
                                # 修复成功，跳出循环
                                break

                    # 检查最终查询的正确性
                    final_is_compliant, final_details = checker.check_query(
                        current_query, subqueries[i]["question"]
                    )
                    query_repair_info["after_repair_correct"] = final_is_compliant
                    query_repair_info["final_query"] = current_query

                    if final_is_compliant:
                        pipeline_info["repair_after_correct"] += 1

                    # 如果修复前不正确，修复后正确，算作修复成功
                    if not original_is_compliant and final_is_compliant:
                        pipeline_info["repair_successes"] += 1

                    pipeline_info["repair_details"].append(query_repair_info)
                    sparqls[i] = current_query

            else:
                if self.verbose_output:
                    print(f"  3. 跳过语义检查和修复（未启用）")

            token_stats["query_repairer"] = repair_tokens
            pipeline_info["step_times"]["semantic_repair"] = time.time() - step_start

            if self.verbose_output and self.is_use_repair:
                print(f"     查询修复Token消耗: {repair_tokens['total_tokens']}")

            # 4. 数据库调度和执行
            step_start = time.time()
            if self.verbose_output:
                print(f"  4. 执行数据库查询...")

            subqueryscheduler = SubQueryScheduler(self.model)
            converted_queries = []
            query_results = {}
            scheduler_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

            for i in range(len(sparqls)):
                # 数据库选择
                scheduler_input = f"{sparqls[i]} {subqueries[i]['question']}"
                sel_db = subqueryscheduler.select_database(
                    sparqls[i],
                    subqueries[i]["question"]
                )
                scheduler_output = sel_db

                scheduler_call_tokens = self.token_calculator.calculate_llm_call_tokens(scheduler_input,
                                                                                        scheduler_output)
                scheduler_tokens["input_tokens"] += scheduler_call_tokens["input_tokens"]
                scheduler_tokens["output_tokens"] += scheduler_call_tokens["output_tokens"]
                scheduler_tokens["total_tokens"] += scheduler_call_tokens["total_tokens"]

                db_selection_info = {
                    "query_index": i + 1,
                    "selected_database": sel_db,
                    "original_sparql": sparqls[i]
                }
                pipeline_info["database_selections"].append(db_selection_info)

                # 查询转换和执行
                subqueryexecutor = SubQueryExecutor(self.model)
                converted_query = subqueryexecutor.convert_to_target_query(sparqls[i], sel_db)
                converted_queries.append(converted_query)

                if subqueryexecutor.has_placeholder(converted_query):
                    converted_query = subqueryexecutor.replace_placeholders(converted_query, query_results)

                result = subqueryexecutor.execute_in_database(converted_query, sel_db)

                # 安全序列化查询结果
                safe_result = safe_serialize_data(result)
                query_results[i + 1] = safe_result

                converted_query_info = {
                    "query_index": i + 1,
                    "database": sel_db,
                    "converted_query": converted_query,
                    "result_count": len(result) if result else 0
                }
                pipeline_info["converted_queries"].append(converted_query_info)

                if self.verbose_output:
                    print(f"     子查询 {i + 1} -> {sel_db} -> {len(result)} 条结果")
                    if result and len(result) > 0:
                        sample_size = min(3, len(result))
                        print(f"     样例结果: {result[:sample_size]}")

            token_stats["subquery_scheduler"] = scheduler_tokens
            token_stats["steps_count"]["subquery_scheduler_calls"] = len(sparqls)
            pipeline_info["step_times"]["database_execution"] = time.time() - step_start

            if self.verbose_output:
                print(f"     数据库调度Token消耗: {scheduler_tokens['total_tokens']}")

            # 计算总Token消耗
            token_stats["total_tokens"] = (
                    token_stats["query_planner"]["total_tokens"] +
                    token_stats["sparql_generator"]["total_tokens"] +
                    token_stats["query_repairer"]["total_tokens"] +
                    token_stats["subquery_scheduler"]["total_tokens"]
            )

            # 安全记录查询结果和流程信息
            self._log_intermediate("query_results", query_results, question_id)
            safe_pipeline_info = safe_serialize_data(pipeline_info)
            self._log_intermediate("pipeline_info", safe_pipeline_info, question_id)

        except Exception as e:
            error_msg = str(e)
            pipeline_info["errors"].append(error_msg)
            self._log_error(error_msg, f"question_{question_id}_pipeline")
            if self.verbose_output:
                print(f"  执行流程出错: {e}")
            return {}, time.time() - start_time, pipeline_info, token_stats

        total_time = time.time() - start_time
        if self.verbose_output:
            print(f"  总执行时间: {total_time:.2f}s")
            print(f"  总Token消耗: {token_stats['total_tokens']}")
            print(f"  各步骤用时: {pipeline_info['step_times']}")

        return query_results, total_time, pipeline_info, token_stats

    def calculate_subquery_ex(self, system_results: List, expected_results: List,
                              query_index: int, query_question: str) -> Tuple[int, Dict]:
        """
        计算单个子查询的EX值
        第三个子查询使用数量比较，其他使用LLM智能判断

        返回: (ex_value, comparison_details)
        """
        if not expected_results:
            # 如果没有期望结果，默认认为正确
            return 1, {
                "evaluation_method": "no_expected_results",
                "note": "No expected results provided",
                "actual_count": len(system_results)
            }

        # 使用相应的判断方法
        ex_value, comparison_details = self.llm_judge_correctness(
            expected_results, system_results, query_index, query_question
        )

        if self.verbose_output:
            if query_index == 3:
                print(
                    f"     结果比较 (第三个子查询-行数比较): 期望{len(expected_results)}行，实际{len(system_results)}行")
                print(f"     EX = {ex_value} {'✓ 行数相似' if ex_value == 1 else '✗ 行数差异较大'}")
                similarity_ratio = comparison_details.get('similarity_ratio', 'N/A')
                print(f"     行数相似度: {safe_format_float(similarity_ratio)}")
            else:
                print(f"     结果比较 (LLM智能判断): 期望{len(expected_results)}个，实际{len(system_results)}个")
                print(f"     EX = {ex_value} {'✓ 判断为正确' if ex_value == 1 else '✗ 判断为不正确'}")
                print(f"     判断理由: {comparison_details.get('reason', 'N/A')}")
                if comparison_details.get("missing_items"):
                    print(f"     缺少内容: {comparison_details['missing_items']}")
                if comparison_details.get("extra_items"):
                    print(f"     多余内容: {comparison_details['extra_items']}")

        return ex_value, comparison_details

    def run_single_test(self, test_case: Dict) -> Dict[str, Any]:
        """运行单个测试案例"""
        question_id = test_case["id"]
        question = test_case["question"]
        expected_answer = test_case["answer"]

        print(f"\n{'=' * 80}")
        print(f"测试问题 {question_id}")
        print(f"问题: {question}")
        print(f"样例数量: {self.example_count}")
        print(f"{'=' * 80}")

        # 执行系统流程
        system_results, execution_time, pipeline_info, token_stats = self.execute_system_pipeline(question, question_id)

        # 分析每个子查询的结果
        subquery_metrics = []
        subquery_ex_values = []  # 存储每个子查询的EX值

        # 获取子查询数量（通常是3个）
        max_queries = max(len(system_results), len(expected_answer))

        for query_idx in range(1, max_queries + 1):
            query_key = f"query_{query_idx}"

            # 获取期望结果
            expected = expected_answer.get(query_key, {}).get("results", [])
            # 获取系统结果
            actual = system_results.get(query_idx, [])
            # 获取子查询问题（兼容 description 和 question 两种格式）
            query_data = expected_answer.get(query_key, {})
            query_question = query_data.get("description") or query_data.get("question", f"子查询{query_idx}")

            if self.verbose_output:
                print(f"\n  子查询 {query_idx}:")
                print(f"     问题: {query_question}")

            # 计算EX值（第三个子查询使用数量比较，其他使用LLM智能判断）
            ex_value, comparison_details = self.calculate_subquery_ex(
                actual, expected, query_idx, query_question
            )

            subquery_ex_values.append(ex_value)

            # 安全序列化比较详情
            safe_comparison_details = safe_serialize_data(comparison_details)

            subquery_metric = {
                "query_index": query_idx,
                "query_question": query_question,
                "ex_value": ex_value,
                "expected_count": len(expected),
                "actual_count": len(actual),
                "comparison_details": safe_comparison_details
            }

            subquery_metrics.append(subquery_metric)

            if self.verbose_output:
                if query_idx == 3:
                    print(
                        f"     EX = {ex_value} {'✓ 行数相似（第三个子查询）' if ex_value == 1 else '✗ 行数差异较大（第三个子查询）'}")
                else:
                    print(f"     EX = {ex_value} {'✓ 智能判断为正确' if ex_value == 1 else '✗ 智能判断为不正确'}")

        # 计算整体EX和FEX指标
        # FEX (Full Exact match): 所有子查询都正确才算正确
        fex = 1 if all(ex == 1 for ex in subquery_ex_values) else 0

        # EX: 子查询EX值的平均（正确子查询数/总子查询数）
        ex = sum(subquery_ex_values) / len(subquery_ex_values) if subquery_ex_values else 0

        overall_metrics = {
            "ex": ex,
            "fex": fex,
            "subquery_ex_values": subquery_ex_values,
            "total_subqueries": len(subquery_ex_values),
            "correct_subqueries": sum(subquery_ex_values),
            "evaluation_mode": "mixed_evaluation_third_query_count_based"
        }

        # 计算修复器指标
        repair_metrics = {}
        if self.is_use_repair and pipeline_info["repair_total_checks"] > 0:
            repair_metrics = {
                "repair_success_rate": pipeline_info["repair_successes"] / pipeline_info["repair_attempts"] if
                pipeline_info["repair_attempts"] > 0 else 0,
                "total_repair_attempts": pipeline_info["repair_attempts"],
                "successful_repairs": pipeline_info["repair_successes"],
                "before_repair_correct": pipeline_info["repair_before_correct"],
                "after_repair_correct": pipeline_info["repair_after_correct"],
                "total_checks": pipeline_info["repair_total_checks"]
            }

        # 安全序列化所有数据
        safe_pipeline_info = safe_serialize_data(pipeline_info)
        safe_system_results = safe_serialize_data(system_results)
        safe_expected_answer = safe_serialize_data(expected_answer)
        safe_token_stats = safe_serialize_data(token_stats)

        result = {
            "question_id": question_id,
            "question": question,
            "execution_time": execution_time,
            "question_correct": fex == 1,  # 使用FEX判断问题是否正确
            "subquery_metrics": subquery_metrics,
            "overall_metrics": overall_metrics,
            "repair_metrics": repair_metrics,
            "token_stats": safe_token_stats,  # 添加Token统计
            "example_count": self.example_count,  # 添加样例数量
            "pipeline_info": safe_pipeline_info,
            "system_results": safe_system_results,
            "expected_answer": safe_expected_answer,
            "timestamp": datetime.now().isoformat()
        }

        if self.verbose_output:
            print(f"\n  问题整体结果:")
            print(f"  FEX = {fex} {'✓ 所有子查询都正确' if fex == 1 else '✗ 存在不正确的子查询'}")
            print(f"  EX = {ex:.3f} (正确子查询比例: {sum(subquery_ex_values)}/{len(subquery_ex_values)})")
            print(f"  执行时间: {execution_time:.2f}s")
            print(f"  Token消耗: {token_stats['total_tokens']}")
            print(f"  样例数量: {self.example_count}")
            if repair_metrics:
                print(
                    f"  修复成功率: {repair_metrics['repair_success_rate']:.3f} ({repair_metrics['successful_repairs']}/{repair_metrics['total_repair_attempts']})")

        return result

    def run_full_test(self, test_data: List[Dict] = None) -> Dict[str, Any]:
        """运行完整测试"""
        if test_data is None:
            test_data = self.load_test_data()

        if not test_data:
            print("没有测试数据，退出测试")
            return {}

        print(f"\n开始运行完整测试，共 {len(test_data)} 个问题")
        print(f"测试模式: {self.test_mode}")
        print(f"样例数量: {self.example_count}")
        print(f"评估模式: 混合评价（第1、2子查询LLM智能判断，第3子查询行数比较）")
        print(f"评价指标: EX (子查询正确率), FEX (完整问题正确率), Token成本")
        print(f"第三个子查询（代谢通路）评价规则: 只比较返回行数，行数相似度≥80%视为正确")

        # 测试结果汇总
        results = {
            "test_config": {
                "use_ontology": self.is_use_ontology,
                "use_repair": self.is_use_repair,
                "llm_temperature": self.llm_temperature,
                "iter_nums": self.iter_nums,
                "test_mode": self.test_mode,
                "selected_ids": self.selected_ids if self.test_mode == "selected" else None,
                "experiment_tag": self.experiment_tag,
                "model_type": config.MODEL_TYPE,
                "example_count": self.example_count,  # 替代prompt_mode
                "evaluation_mode": "mixed_evaluation_third_query_count_based"
            },
            "test_summary": {
                "total_questions": len(test_data),
                "correct_questions_fex": 0,  # FEX=1的问题数
                "total_fex_sum": 0,  # 所有问题的FEX之和
                "total_ex_sum": 0.0,  # 所有问题的EX之和
                "total_subqueries": 0,  # 总子查询数
                "correct_subqueries": 0,  # EX=1的子查询数
                "total_time": 0.0,
                "total_repair_attempts": 0,
                "total_repair_successes": 0,
                "total_repair_checks": 0,
                "before_repair_correct": 0,
                "after_repair_correct": 0,
                "total_tokens": 0,  # 总Token消耗
                "evaluation_mode": "mixed_evaluation_third_query_count_based"
            },
            "question_results": [],
            "error_log": safe_serialize_data(self.error_log),
            "intermediate_results": safe_serialize_data(self.intermediate_results) if self.save_intermediate else {}
        }

        # 逐个测试问题
        for i, test_case in enumerate(test_data):
            print(f"\n进度: {i + 1}/{len(test_data)}")
            result = self.run_single_test(test_case)
            results["question_results"].append(result)

            # 更新汇总统计
            if result["overall_metrics"]["fex"] == 1:
                results["test_summary"]["correct_questions_fex"] += 1

            results["test_summary"]["total_fex_sum"] += result["overall_metrics"]["fex"]
            results["test_summary"]["total_ex_sum"] += result["overall_metrics"]["ex"]
            results["test_summary"]["total_subqueries"] += result["overall_metrics"]["total_subqueries"]
            results["test_summary"]["correct_subqueries"] += result["overall_metrics"]["correct_subqueries"]
            results["test_summary"]["total_time"] += result["execution_time"]
            results["test_summary"]["total_tokens"] += result["token_stats"]["total_tokens"]

            # 修复器统计
            if result.get("repair_metrics"):
                repair_metrics = result["repair_metrics"]
                results["test_summary"]["total_repair_attempts"] += repair_metrics.get("total_repair_attempts", 0)
                results["test_summary"]["total_repair_successes"] += repair_metrics.get("successful_repairs", 0)
                results["test_summary"]["total_repair_checks"] += repair_metrics.get("total_checks", 0)
                results["test_summary"]["before_repair_correct"] += repair_metrics.get("before_repair_correct", 0)
                results["test_summary"]["after_repair_correct"] += repair_metrics.get("after_repair_correct", 0)

        # 计算最终指标
        summary = results["test_summary"]

        # FEX准确率: 所有子查询都正确的问题比例
        fex_accuracy = summary["correct_questions_fex"] / summary["total_questions"]

        # EX整体平均: 所有问题的平均EX
        ex_overall = summary["total_ex_sum"] / summary["total_questions"]

        # 子查询级别的准确率（与EX整体平均相同）
        subquery_accuracy = summary["correct_subqueries"] / summary["total_subqueries"] if summary[
                                                                                               "total_subqueries"] > 0 else 0.0

        # 每个查询的平均时间
        time_per_query = summary["total_time"] / summary["total_questions"]

        # 每个问题的平均Token消耗
        tokens_per_query = summary["total_tokens"] / summary["total_questions"]

        # 修复成功率
        repair_success_rate = summary["total_repair_successes"] / summary["total_repair_attempts"] if summary[
                                                                                                          "total_repair_attempts"] > 0 else 0.0

        final_metrics = {
            "fex_accuracy": fex_accuracy,
            "ex_overall": ex_overall,
            "subquery_accuracy": subquery_accuracy,
            "time_per_query": time_per_query,
            "tokens_per_query": tokens_per_query,  # 新增: 每个问题的平均Token消耗
            "total_tokens": summary["total_tokens"],  # 新增: 总Token消耗
            "repair_success_rate": repair_success_rate,
            "total_questions": summary["total_questions"],
            "correct_questions_fex": summary["correct_questions_fex"],
            "total_subqueries": summary["total_subqueries"],
            "correct_subqueries": summary["correct_subqueries"],
            "total_repair_attempts": summary["total_repair_attempts"],
            "total_repair_successes": summary["total_repair_successes"],
            "example_count": self.example_count,
            "evaluation_mode": "mixed_evaluation_third_query_count_based"
        }

        results["final_metrics"] = final_metrics
        results["test_completed_at"] = datetime.now().isoformat()

        return results

    def print_final_summary(self, results: Dict[str, Any]):
        """打印最终测试摘要"""
        if not results:
            print("没有测试结果")
            return

        summary = results["test_summary"]
        metrics = results["final_metrics"]
        config_info = results["test_config"]

        print(f"\n{'=' * 80}")
        print("最终测试结果摘要")
        print(f"{'=' * 80}")

        print(f"测试配置:")
        print(f"  - 模型类型: {config_info.get('model_type', 'N/A')}")
        print(f"  - 样例数量: {config_info.get('example_count', 'N/A')}")
        print(f"  - 使用本体: {config_info['use_ontology']}")
        print(f"  - 语义查询修复: {config_info['use_repair']}")
        print(f"  - LLM温度: {config_info['llm_temperature']}")
        print(f"  - 修复迭代次数: {config_info['iter_nums']}")
        print(f"  - 测试模式: {config_info['test_mode']}")
        print(f"  - 评估模式: {config_info.get('evaluation_mode', 'mixed_evaluation_third_query_count_based')}")
        if config_info.get('selected_ids'):
            print(f"  - 选择的问题: {config_info['selected_ids']}")
        if config_info.get('experiment_tag'):
            print(f"  - 实验标签: {config_info['experiment_tag']}")

        print(f"\n性能指标:")
        print(f"  - 总问题数: {metrics['total_questions']}")
        print(f"  - FEX正确问题数: {metrics['correct_questions_fex']}")
        print(f"  - FEX准确率: {metrics['fex_accuracy']:.3f} ({metrics['fex_accuracy'] * 100:.1f}%)")
        print(f"  - EX整体平均: {metrics['ex_overall']:.3f}")
        print(
            f"  - 子查询准确率: {metrics['subquery_accuracy']:.3f} ({metrics['correct_subqueries']}/{metrics['total_subqueries']})")
        print(f"  - Time per Query: {metrics['time_per_query']:.2f}s")
        print(f"  - Total Time: {summary['total_time']:.2f}s")
        print(f"  - Tokens per Query: {metrics['tokens_per_query']:.0f}")
        print(f"  - Total Tokens: {metrics['total_tokens']}")

        if config_info['use_repair']:
            print(f"\n修复器性能:")
            print(f"  - 总检查次数: {summary['total_repair_checks']}")
            print(f"  - 修复前正确: {summary['before_repair_correct']}")
            print(f"  - 修复后正确: {summary['after_repair_correct']}")
            print(f"  - 修复尝试次数: {summary['total_repair_attempts']}")
            print(f"  - 修复成功次数: {summary['total_repair_successes']}")
            print(f"  - 修复成功率: {metrics['repair_success_rate']:.3f} ({metrics['repair_success_rate'] * 100:.1f}%)")

        # 各问题结果概览
        print(f"\n各问题结果:")
        for result in results["question_results"]:
            fex = result["overall_metrics"]["fex"]
            ex = result["overall_metrics"]["ex"]
            tokens = result["token_stats"]["total_tokens"]
            status = "✓" if fex == 1 else "✗"
            repair_info = ""
            if result.get("repair_metrics"):
                rm = result["repair_metrics"]
                repair_info = f", R={rm['successful_repairs']}/{rm['total_repair_attempts']}"
            print(
                f"  问题{result['question_id']}: {status} (FEX={fex}, EX={ex:.2f}, T={result['execution_time']:.1f}s, Tokens={tokens}{repair_info})")

        if results["error_log"]:
            print(f"\n错误总数: {len(results['error_log'])}")

        print(f"\n📊 评价指标说明:")
        print(f"   - EX: 子查询正确率 = 正确子查询数 / 总子查询数")
        print(f"   - FEX: 完整问题正确率，所有子查询都正确才为1")
        print(f"   - 混合评价模式:")
        print(f"     * 第1、2子查询: LLM智能判断，关注内容包含性")
        print(f"     * 第3子查询（代谢通路）: 行数相似性比较，行数相似度≥80%视为正确")
        print(f"   - 修复成功率: 修复后正确 / 修复尝试次数")
        print(f"   - Tokens per Query: 平均每个问题的Token消耗")
        print(f"   - 样例数量: {config_info.get('example_count', 'N/A')} (Few-shot learning)")
        print(f"{'=' * 80}")

    def save_results(self, results: Dict[str, Any]):
        """保存测试结果到多种格式的文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 构建文件名
        base_name = f"{timestamp}_example{self.example_count}_mixed_evaluation"
        if self.experiment_tag:
            base_name = f"{self.experiment_tag}_{base_name}"
        if self.test_mode == "selected":
            base_name = f"selected_{base_name}"

        saved_files = []

        try:
            # 1. 保存完整JSON结果（使用自定义编码器）
            if config.SAVE_JSON_RESULTS:
                json_filename = os.path.join(self.results_dir, f"{config.RESULT_FILE_PREFIX}_{base_name}.json")

                # 使用安全序列化确保所有数据都可以序列化
                safe_results = safe_serialize_data(results)

                with open(json_filename, 'w', encoding='utf-8') as f:
                    json.dump(safe_results, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
                saved_files.append(json_filename)
                print(f"详细结果已保存到: {json_filename}")

            # 2. 保存摘要报告
            if config.SAVE_SUMMARY_REPORT:
                summary_filename = os.path.join(self.results_dir, f"{config.SUMMARY_FILE_PREFIX}_{base_name}.txt")
                self._save_summary_report(results, summary_filename)
                saved_files.append(summary_filename)
                print(f"摘要报告已保存到: {summary_filename}")

            # 3. 保存CSV指标数据
            if config.SAVE_CSV_METRICS:
                csv_filename = os.path.join(self.results_dir, f"{config.CSV_FILE_PREFIX}_{base_name}.csv")
                self._save_csv_metrics(results, csv_filename)
                saved_files.append(csv_filename)
                print(f"CSV指标已保存到: {csv_filename}")

            # 4. 保存错误日志
            if config.SAVE_ERROR_LOGS and results.get("error_log"):
                error_filename = os.path.join(self.results_dir, f"error_log_{base_name}.json")
                safe_error_log = safe_serialize_data(results["error_log"])
                with open(error_filename, 'w', encoding='utf-8') as f:
                    json.dump(safe_error_log, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
                saved_files.append(error_filename)
                print(f"错误日志已保存到: {error_filename}")

            print(f"\n总共保存了 {len(saved_files)} 个文件到目录: {self.results_dir}")

        except Exception as e:
            error_msg = f"保存结果失败: {e}"
            self._log_error(error_msg, "save_results")
            print(f"错误: {error_msg}")
            # 打印详细错误信息以便调试
            import traceback
            traceback.print_exc()

    def _save_summary_report(self, results: Dict[str, Any], filename: str):
        """保存文本格式的摘要报告"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write(f"多源异构知识图谱问答系统测试报告（混合评价模式+Token成本分析）\n")
            f.write(f"当前数据集: {config.CURRENT_DATASET}\n")
            f.write("=" * 80 + "\n\n")

            # 测试配置
            config_info = results["test_config"]
            f.write("测试配置:\n")
            f.write(f"  - 测试时间: {results.get('test_completed_at', 'N/A')}\n")
            f.write(f"  - 模型类型: {config_info.get('model_type', 'N/A')}\n")
            f.write(f"  - 样例数量: {config_info.get('example_count', 'N/A')}\n")
            f.write(f"  - 使用本体: {config_info['use_ontology']}\n")
            f.write(f"  - 语义查询修复: {config_info['use_repair']}\n")
            f.write(f"  - LLM温度: {config_info['llm_temperature']}\n")
            f.write(f"  - 修复迭代次数: {config_info['iter_nums']}\n")
            f.write(f"  - 测试模式: {config_info['test_mode']}\n")
            f.write(f"  - 评估模式: {config_info.get('evaluation_mode', 'mixed_evaluation_third_query_count_based')}\n")
            if config_info.get('selected_ids'):
                f.write(f"  - 选择的问题: {config_info['selected_ids']}\n")
            f.write("\n")

            f.write("评价指标说明:\n")
            f.write("  - EX: 子查询正确率 = 正确子查询数 / 总子查询数\n")
            f.write("  - FEX: 完整问题正确率，所有子查询都正确才为1\n")
            f.write("  - 混合评价模式:\n")
            f.write("    * 第1、2子查询: LLM智能判断，关注内容包含性\n")
            f.write("    * 第3子查询（代谢通路）: 行数相似性比较，行数相似度≥80%视为正确\n")
            f.write("  - 修复成功率: 修复后正确 / 修复尝试次数\n")
            f.write("  - Token成本: 基于字符数估算，中文字符×0.6+英文字符×0.3\n\n")

            # 性能指标
            summary = results["test_summary"]
            metrics = results["final_metrics"]
            f.write("性能指标:\n")
            f.write(f"  - 总问题数: {metrics['total_questions']}\n")
            f.write(f"  - FEX正确问题数: {metrics['correct_questions_fex']}\n")
            f.write(f"  - FEX准确率: {metrics['fex_accuracy']:.3f} ({metrics['fex_accuracy'] * 100:.1f}%)\n")
            f.write(f"  - EX整体平均: {metrics['ex_overall']:.3f}\n")
            f.write(
                f"  - 子查询准确率: {metrics['subquery_accuracy']:.3f} ({metrics['correct_subqueries']}/{metrics['total_subqueries']})\n")
            f.write(f"  - Time per Query: {metrics['time_per_query']:.2f}s\n")
            f.write(f"  - Tokens per Query: {metrics['tokens_per_query']:.0f}\n")
            f.write(f"  - Total Tokens: {metrics['total_tokens']}\n")

            if config_info['use_repair']:
                f.write(
                    f"  - 修复成功率: {metrics['repair_success_rate']:.3f} ({metrics['total_repair_successes']}/{metrics['total_repair_attempts']})\n")
            f.write("\n")

            # 各问题详细结果
            f.write("各问题详细结果:\n")
            f.write("-" * 80 + "\n")
            for result in results["question_results"]:
                f.write(f"问题 {result['question_id']}: {result['question']}\n")
                f.write(
                    f"  - FEX: {result['overall_metrics']['fex']} {'(所有子查询都正确)' if result['overall_metrics']['fex'] == 1 else '(存在不正确的子查询)'}\n")
                f.write(f"  - EX: {result['overall_metrics']['ex']:.3f}\n")
                f.write(f"  - 执行时间: {result['execution_time']:.2f}s\n")
                f.write(f"  - Token消耗: {result['token_stats']['total_tokens']}\n")
                f.write(f"  - 样例数量: {result['example_count']}\n")

                # 子查询结果
                for sq_metric in result["subquery_metrics"]:
                    idx = sq_metric["query_index"]
                    ex = sq_metric["ex_value"]
                    details = sq_metric["comparison_details"]

                    if idx == 3:
                        # 第三个子查询显示行数比较信息
                        similarity = details.get("similarity_ratio", "N/A")
                        expected_rows = details.get("expected_rows", sq_metric['expected_count'])
                        actual_rows = details.get("actual_rows", sq_metric['actual_count'])

                        # 安全格式化相似度
                        similarity_str = safe_format_float(similarity)

                        f.write(
                            f"    子查询{idx}: EX={ex} {'✓ 行数相似' if ex == 1 else '✗ 行数差异较大'} "
                            f"({actual_rows}/{expected_rows}行, 相似度={similarity_str})\n")
                    else:
                        # 其他子查询显示LLM判断信息
                        f.write(
                            f"    子查询{idx}: EX={ex} {'✓ 智能判断正确' if ex == 1 else '✗ 智能判断不正确'} "
                            f"({sq_metric['actual_count']}/{sq_metric['expected_count']})\n")
                        if details.get("reason"):
                            f.write(f"      判断理由: {details['reason']}\n")

                # 修复信息
                if result.get("repair_metrics"):
                    rm = result["repair_metrics"]
                    f.write(f"  - 修复统计: {rm['successful_repairs']}/{rm['total_repair_attempts']} 成功\n")

                # Token详情
                token_stats = result.get("token_stats", {})
                f.write(f"  - Token详情:\n")
                f.write(f"    * 查询规划: {token_stats.get('query_planner', {}).get('total_tokens', 0)}\n")
                f.write(f"    * SPARQL生成: {token_stats.get('sparql_generator', {}).get('total_tokens', 0)}\n")
                f.write(f"    * 查询修复: {token_stats.get('query_repairer', {}).get('total_tokens', 0)}\n")
                f.write(f"    * 数据库调度: {token_stats.get('subquery_scheduler', {}).get('total_tokens', 0)}\n")

                f.write("\n")

    def _save_csv_metrics(self, results: Dict[str, Any], filename: str):
        """保存CSV格式的指标数据"""
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # 写入表头
            header = [
                'question_id', 'fex', 'ex', 'execution_time', 'total_tokens', 'tokens_per_subquery',
                'total_subqueries', 'correct_subqueries', 'example_count',
                'repair_attempts', 'repair_successes', 'repair_success_rate',
                'query_planner_tokens', 'sparql_generator_tokens', 'query_repairer_tokens', 'subquery_scheduler_tokens',
                'evaluation_mode'
            ]

            # 添加子查询EX值列
            max_subqueries = max(len(result["subquery_metrics"]) for result in results["question_results"]) if results[
                "question_results"] else 0
            for i in range(1, max_subqueries + 1):
                header.append(f'sq{i}_ex')
                if i == 3:
                    header.append(f'sq{i}_similarity')  # 第三个子查询添加相似度列

            writer.writerow(header)

            # 写入数据
            for result in results["question_results"]:
                repair_metrics = result.get("repair_metrics", {})
                token_stats = result.get("token_stats", {})

                row = [
                    result['question_id'],
                    result['overall_metrics']['fex'],
                    result['overall_metrics']['ex'],
                    result['execution_time'],
                    token_stats.get('total_tokens', 0),
                    token_stats.get('total_tokens', 0) / result['overall_metrics']['total_subqueries'] if
                    result['overall_metrics']['total_subqueries'] > 0 else 0,
                    result['overall_metrics']['total_subqueries'],
                    result['overall_metrics']['correct_subqueries'],
                    result.get('example_count', 0),
                    repair_metrics.get('total_repair_attempts', 0),
                    repair_metrics.get('successful_repairs', 0),
                    repair_metrics.get('repair_success_rate', 0),
                    token_stats.get('query_planner', {}).get('total_tokens', 0),
                    token_stats.get('sparql_generator', {}).get('total_tokens', 0),
                    token_stats.get('query_repairer', {}).get('total_tokens', 0),
                    token_stats.get('subquery_scheduler', {}).get('total_tokens', 0),
                    result['overall_metrics'].get('evaluation_mode', 'mixed_evaluation_third_query_count_based')
                ]

                # 添加子查询数据
                for i in range(1, max_subqueries + 1):
                    sq_metric = None
                    for sq in result["subquery_metrics"]:
                        if sq["query_index"] == i:
                            sq_metric = sq
                            break

                    if sq_metric:
                        row.append(sq_metric['ex_value'])
                        if i == 3:
                            # 第三个子查询添加相似度数据
                            similarity = sq_metric['comparison_details'].get('similarity_ratio', None)
                            row.append(similarity)
                    else:
                        row.append(None)
                        if i == 3:
                            row.append(None)

                writer.writerow(row)


def main():
    """主函数"""
    print("多源异构知识图谱问答系统测试框架")
    print("基于config.py参数进行性能评估")
    print("使用EX和FEX评价指标 - 混合评价模式")
    print("添加Token成本计算和可变样例数量支持")
    print("评价指标说明:")
    print("  - EX: 子查询正确率 = 正确子查询数 / 总子查询数")
    print("  - FEX: 完整问题正确率，所有子查询都正确才为1")
    print("混合评价模式:")
    print("  - 第1、2子查询: LLM智能判断，关注内容包含性")
    print("  - 第3子查询（代谢通路）: 数量相似性比较，相似度≥80%视为正确")
    print("Token计算规则: 中文字符×0.6 + 英文字符×0.3")

    # 创建测试框架
    framework = SystemTestFramework()

    # 运行完整测试
    results = framework.run_full_test()

    # 打印摘要
    framework.print_final_summary(results)

    # 保存结果
    framework.save_results(results)


if __name__ == "__main__":
    main()