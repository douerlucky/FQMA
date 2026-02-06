#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消融实验：三种修复策略对比
1. 无检查和修复 (No Repair)
2. 仅语法检查和修复 (Syntax Only)
3. 仅语义检查和修复 (Semantic Only)

评估指标：
- FEX (Full Exact Match): 所有子查询都正确的问题比例
- SEX (Sub-query Exact Match): 子查询正确率平均值
- Time: 平均执行时间
- Token Cost: Token消耗
"""

import json
import time
import random
import os
from typing import Dict, List, Any, Tuple
from datetime import datetime
from enum import Enum

# 导入系统组件
from agents.QueryPlanningAndGeneration import QueryPlanner, SparQLGenerator
from agents.QueryAdaptive import SubQueryScheduler, SubQueryExecutor
from agents.SemanticQueryRepair import QueryChecker, QueryRepairer
import config


class RepairStrategy(Enum):
    """修复策略枚举"""
    NO_REPAIR = "no_repair"  # 无检查和修复
    SYNTAX_ONLY = "syntax_only"  # 仅语法检查和修复
    SEMANTIC_ONLY = "semantic_only"  # 仅语义检查和修复


class TokenCalculator:
    """Token计算器"""

    def __init__(self):
        self.chinese_token_ratio = 0.6
        self.english_token_ratio = 0.3

    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        if not text:
            return 0

        import re
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', text))
        english_chars = len(text) - chinese_chars

        chinese_tokens = chinese_chars * self.chinese_token_ratio
        english_tokens = english_chars * self.english_token_ratio

        return int(round(chinese_tokens + english_tokens))

    def calculate_llm_call_tokens(self, input_text: str, output_text: str) -> Dict[str, int]:
        """计算单次LLM调用的token消耗"""
        input_tokens = self.count_tokens(input_text)
        output_tokens = self.count_tokens(output_text)

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        }


class SyntaxOnlyChecker:
    """仅语法检查器（跳过语义检查）"""

    def __init__(self, model):
        self.model = model
        self.forbidden_functions = ['CONTAINS', 'REGEX', 'STRSTARTS']

    def check_query(self, sparql_query: str, natural_language_query: str = None) -> Tuple[bool, str]:
        """只进行语法检查，跳过所有语义检查"""
        import re
        from rdflib.plugins.sparql import prepareQuery

        is_compliant = True
        details = []

        print(f"\n{'=' * 60}")
        print(f"🔍 语法检查模式（跳过语义检查）")
        print(f"{'=' * 60}")

        # 检查占位符
        has_placeholder = '<<SUBQUERY_' in sparql_query
        if has_placeholder:
            placeholders = re.findall(r'<<SUBQUERY_\d+>>', sparql_query)
            details.append(f"✓ 检测到 {len(placeholders)} 个子查询占位符: {', '.join(placeholders)}")
            temp_query = sparql_query
            for i, placeholder in enumerate(placeholders):
                temp_query = temp_query.replace(placeholder, f'?placeholder_{i}')
        else:
            temp_query = sparql_query

        # 1. 语法合规性检查
        print(f"\n【步骤1】语法合规性检查")
        errors = []
        try:
            prepareQuery(temp_query)
            details.append("✅ 语法解析成功")
            print(f"✅ 语法检查通过")

            # 基本语法检查
            if temp_query.count('(') != temp_query.count(')'):
                errors.append("括号不匹配")
                is_compliant = False

            if temp_query.count('{') != temp_query.count('}'):
                errors.append("大括号不匹配")
                is_compliant = False

            query_upper = temp_query.upper()
            if not any(kw in query_upper for kw in ['SELECT', 'CONSTRUCT', 'ASK', 'DESCRIBE']):
                errors.append("缺少查询类型关键字")
                is_compliant = False

            if 'WHERE' not in query_upper and 'SELECT' in query_upper:
                errors.append("缺少WHERE子句")
                is_compliant = False

        except Exception as e:
            errors.append(f"语法解析错误: {str(e)[:200]}")
            is_compliant = False
            print(f"❌ 语法检查失败")

        if errors:
            for error in errors:
                details.append(f"❌ 错误: {error}")
        else:
            details.append("✅ 未发现语法错误")

        # 2. 禁止函数检查
        print(f"\n【步骤2】禁止函数检查")
        query_upper = sparql_query.upper()
        found_functions = []
        for func in self.forbidden_functions:
            pattern = rf'\b{func}\s*\('
            if re.search(pattern, query_upper):
                found_functions.append(func)
                is_compliant = False

        if found_functions:
            details.append(f"❌ 发现禁止使用的函数: {', '.join(found_functions)}")
            print(f"❌ 禁止函数检查失败")
        else:
            details.append("✅ 未发现禁止使用的函数")
            print(f"✅ 禁止函数检查通过")

        # 跳过语义检查
        print(f"\n【跳过】语义合规性检查（本实验仅进行语法检查）")
        details.append("\n=== 语义合规性检查 ===")
        details.append("🚫 跳过语义检查（本实验配置）")

        print(f"\n{'=' * 60}")
        details.append("\n=== 检查总结 ===")
        if is_compliant:
            print(f"✅ 查询语法合规")
            details.append("✅ 查询语法合规")
        else:
            print(f"❌ 查询语法不合规")
            details.append("❌ 查询语法不合规")

        print(f"{'=' * 60}\n")
        return is_compliant, "\n".join(details)


class SemanticOnlyChecker:
    """仅语义检查器（跳过语法检查）"""

    def __init__(self, ontology_path: str, model):
        self.ontology_path = ontology_path
        self.model = model
        # 使用完整的QueryChecker，但只看语义部分
        self.full_checker = QueryChecker(ontology_path, model, llm_check_mode="advisory")

    def check_query(self, sparql_query: str, natural_language_query: str = None) -> Tuple[bool, str]:
        """只进行语义检查，跳过语法检查"""
        import re

        is_compliant = True
        details = []

        print(f"\n{'=' * 60}")
        print(f"🔍 语义检查模式（跳过语法检查）")
        print(f"{'=' * 60}")

        # 检查占位符
        has_placeholder = '<<SUBQUERY_' in sparql_query
        if has_placeholder:
            placeholders = re.findall(r'<<SUBQUERY_\d+>>', sparql_query)
            details.append(f"✓ 检测到 {len(placeholders)} 个子查询占位符: {', '.join(placeholders)}")
            temp_query = sparql_query
            for i, placeholder in enumerate(placeholders):
                temp_query = temp_query.replace(placeholder, f'?placeholder_{i}')
        else:
            temp_query = sparql_query

        # 跳过语法检查
        print(f"\n【跳过】语法合规性检查（本实验仅进行语义检查）")
        details.append("=== 语法合规性检查 ===")
        details.append("🚫 跳过语法检查（本实验配置）")

        # 进行语义检查
        if self.full_checker.has_ontology:
            print(f"\n【步骤1】语义合规性检查（基于本体）")
            semantic_ok, semantic_details = self.full_checker._check_semantic_compliance(
                sparql_query, has_placeholder
            )
            if not semantic_ok:
                is_compliant = False
                print(f"❌ 本体语义检查失败")
            else:
                print(f"✅ 本体语义检查通过")
            details.append("\n=== 语义合规性检查 ===")
            details.extend(semantic_details)
        else:
            print(f"\n【步骤1】无本体，跳过语义检查")
            details.append("\n=== 语义合规性检查 ===")
            details.append("⚠️ 无本体模式，跳过语义检查")

        # LLM语义一致性检查
        if natural_language_query and self.full_checker.semantic_checker:
            print(f"\n【步骤2】LLM语义一致性检查")
            try:
                consistency_ok, consistency_details = self.full_checker.semantic_checker.check_consistency(
                    natural_language_query, sparql_query
                )

                print(f"\n--- LLM检查详情 ---")
                print(consistency_details)
                print(f"--- LLM检查结束 ---\n")

                if not consistency_ok:
                    is_compliant = False
                    print(f"❌ LLM语义检查失败")
                else:
                    print(f"✅ LLM语义检查通过")

                details.append("\n=== LLM语义一致性检查 ===")
                details.append(consistency_details)

            except Exception as e:
                print(f"⚠️ LLM检查出错: {e}")
                details.append("\n=== LLM语义一致性检查 ===")
                details.append(f"⚠️ LLM检查失败: {str(e)}")

        print(f"\n{'=' * 60}")
        details.append("\n=== 检查总结 ===")
        if is_compliant:
            print(f"✅ 查询语义合规")
            details.append("✅ 查询语义合规")
        else:
            print(f"❌ 查询语义不合规")
            details.append("❌ 查询语义不合规")

        print(f"{'=' * 60}\n")
        return is_compliant, "\n".join(details)


class AblationExperiment:
    """消融实验类"""

    def __init__(self, test_questions: List[Dict], num_samples: int = 11,
                 strategy: RepairStrategy = RepairStrategy.NO_REPAIR):
        """
        初始化消融实验

        Args:
            test_questions: 测试问题列表
            num_samples: 随机抽取的样本数量（默认11个）
            strategy: 修复策略
        """
        self.model = config.model
        self.ontology_path = config.ontology_path
        self.num_samples = num_samples
        self.strategy = strategy
        self.iter_nums = config.iter_nums if strategy != RepairStrategy.NO_REPAIR else 0

        # 随机抽取样本
        if len(test_questions) > num_samples:
            self.test_samples = random.sample(test_questions, num_samples)
        else:
            self.test_samples = test_questions

        print(f"✓ 已随机抽取 {len(self.test_samples)} 个测试样本")
        print(f"  样本ID: {[q['id'] for q in self.test_samples]}")
        print(f"  修复策略: {strategy.value}")

        # Token计算器
        self.token_calculator = TokenCalculator()

        # 结果存储
        self.results = []

    def run_query(self, question: str, expected_answer: Dict, question_id: int) -> Dict:
        """
        运行查询，根据策略选择不同的检查和修复方式

        Args:
            question: 自然语言问题
            expected_answer: 预期答案
            question_id: 问题ID

        Returns:
            结果字典
        """
        start_time = time.time()

        # Token统计
        token_stats = {
            "query_planner": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "sparql_generator": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "checker": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "repairer": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "subquery_scheduler": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "total_tokens": 0,
            "steps_count": {
                "query_planner_calls": 0,
                "sparql_generator_calls": 0,
                "checker_calls": 0,
                "repairer_calls": 0,
                "subquery_scheduler_calls": 0
            }
        }

        try:
            print(f"\n{'=' * 80}")
            print(f"测试问题 {question_id}: {question[:80]}...")
            print(f"策略: {self.strategy.value}")
            print(f"{'=' * 80}")

            # ============================================================
            # 步骤1: 查询规划
            # ============================================================
            print(f"\n[步骤1] 查询规划...")
            query_planner = QueryPlanner(self.model)

            planning_input = question
            subqueries = query_planner.get_subqueries(question)
            planning_output = str(subqueries)

            # 计算Token
            planning_tokens = self.token_calculator.calculate_llm_call_tokens(
                planning_input, planning_output
            )
            token_stats["query_planner"] = planning_tokens
            token_stats["steps_count"]["query_planner_calls"] = 1

            if not subqueries:
                print("  ✗ 查询规划失败")
                return self._create_error_result(
                    time.time() - start_time,
                    "查询规划失败",
                    token_stats,
                    question_id
                )

            print(f"  ✓ 分解为 {len(subqueries)} 个子查询")

            # ============================================================
            # 步骤2: SPARQL生成
            # ============================================================
            print(f"\n[步骤2] SPARQL生成...")
            sparql_generator = SparQLGenerator(self.model, self.ontology_path)
            sparqls = []
            sparql_generation_tokens = {
                "input_tokens": 0, "output_tokens": 0, "total_tokens": 0
            }

            for i, subquery in enumerate(subqueries):
                dependencies = [subqueries[j - 1] for j in subquery["dependencies"]]

                sparql_input = f"{subquery['question']} {dependencies}"
                sparql_query = sparql_generator.generate_sparql(
                    subquery["question"], dependencies
                )
                sparql_output = sparql_query

                # 计算Token
                sparql_tokens = self.token_calculator.calculate_llm_call_tokens(
                    sparql_input, sparql_output
                )
                sparql_generation_tokens["input_tokens"] += sparql_tokens["input_tokens"]
                sparql_generation_tokens["output_tokens"] += sparql_tokens["output_tokens"]
                sparql_generation_tokens["total_tokens"] += sparql_tokens["total_tokens"]

                sparqls.append(sparql_query)
                print(f"  ✓ 子查询 {i + 1} SPARQL生成完成")

            token_stats["sparql_generator"] = sparql_generation_tokens
            token_stats["steps_count"]["sparql_generator_calls"] = len(subqueries)

            # ============================================================
            # 步骤3: 检查和修复（根据策略）
            # ============================================================
            final_sparqls = []

            if self.strategy == RepairStrategy.NO_REPAIR:
                # 策略1: 无检查和修复
                print(f"\n[步骤3] 🚫 跳过检查和修复（策略: {self.strategy.value}）")
                final_sparqls = sparqls

            elif self.strategy == RepairStrategy.SYNTAX_ONLY:
                # 策略2: 仅语法检查和修复
                print(f"\n[步骤3] 语法检查和修复（策略: {self.strategy.value}）")
                checker = SyntaxOnlyChecker(self.model)
                repairer = QueryRepairer(self.model)

                checker_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                repairer_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

                for i, sparql in enumerate(sparqls):
                    current_sparql = sparql
                    print(f"\n第{i + 1}个子查询正在评价")

                    for repair_iter in range(self.iter_nums):
                        # 检查
                        checker_input = f"{current_sparql} {subqueries[i]['question']}"
                        is_compliant, details = checker.check_query(
                            current_sparql, subqueries[i]["question"]
                        )
                        checker_output = details

                        checker_call_tokens = self.token_calculator.calculate_llm_call_tokens(
                            checker_input, checker_output
                        )
                        checker_tokens["input_tokens"] += checker_call_tokens["input_tokens"]
                        checker_tokens["output_tokens"] += checker_call_tokens["output_tokens"]
                        checker_tokens["total_tokens"] += checker_call_tokens["total_tokens"]

                        print(f"📋 检查结果: {'✅ 合规' if is_compliant else '❌ 不合规'}")

                        if not is_compliant:
                            print(f"语法不合规,进行第{repair_iter + 1}次迭代修复")

                            # 修复
                            repairer_input = f"{subqueries[i]['question']} {details} {current_sparql}"
                            repaired_sparql = repairer.repair_sparql(
                                subqueries[i]["question"],
                                details,
                                current_sparql
                            )
                            repairer_output = repaired_sparql

                            repairer_call_tokens = self.token_calculator.calculate_llm_call_tokens(
                                repairer_input, repairer_output
                            )
                            repairer_tokens["input_tokens"] += repairer_call_tokens["input_tokens"]
                            repairer_tokens["output_tokens"] += repairer_call_tokens["output_tokens"]
                            repairer_tokens["total_tokens"] += repairer_call_tokens["total_tokens"]

                            current_sparql = repaired_sparql
                            print(f"第{i + 1}个子查询的第{repair_iter + 1}次修复完成")
                        else:
                            print(f"第{i + 1}个子查询检查合规")
                            break

                    final_sparqls.append(current_sparql)

                token_stats["checker"] = checker_tokens
                token_stats["repairer"] = repairer_tokens
                token_stats["steps_count"]["checker_calls"] = len(sparqls) * self.iter_nums
                token_stats["steps_count"]["repairer_calls"] = len(
                    [s for s in final_sparqls if s != sparqls[final_sparqls.index(s)]])

            elif self.strategy == RepairStrategy.SEMANTIC_ONLY:
                # 策略3: 仅语义检查和修复
                print(f"\n[步骤3] 语义检查和修复（策略: {self.strategy.value}）")
                checker = SemanticOnlyChecker(self.ontology_path, self.model)
                repairer = QueryRepairer(self.model)

                checker_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                repairer_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

                for i, sparql in enumerate(sparqls):
                    current_sparql = sparql
                    print(f"\n第{i + 1}个子查询正在评价")

                    for repair_iter in range(self.iter_nums):
                        # 检查
                        checker_input = f"{current_sparql} {subqueries[i]['question']}"
                        is_compliant, details = checker.check_query(
                            current_sparql, subqueries[i]["question"]
                        )
                        checker_output = details

                        checker_call_tokens = self.token_calculator.calculate_llm_call_tokens(
                            checker_input, checker_output
                        )
                        checker_tokens["input_tokens"] += checker_call_tokens["input_tokens"]
                        checker_tokens["output_tokens"] += checker_call_tokens["output_tokens"]
                        checker_tokens["total_tokens"] += checker_call_tokens["total_tokens"]

                        print(f"📋 检查结果: {'✅ 合规' if is_compliant else '❌ 不合规'}")

                        if not is_compliant:
                            print(f"语义不合规,进行第{repair_iter + 1}次迭代修复")

                            # 修复
                            repairer_input = f"{subqueries[i]['question']} {details} {current_sparql}"
                            repaired_sparql = repairer.repair_sparql(
                                subqueries[i]["question"],
                                details,
                                current_sparql
                            )
                            repairer_output = repaired_sparql

                            repairer_call_tokens = self.token_calculator.calculate_llm_call_tokens(
                                repairer_input, repairer_output
                            )
                            repairer_tokens["input_tokens"] += repairer_call_tokens["input_tokens"]
                            repairer_tokens["output_tokens"] += repairer_call_tokens["output_tokens"]
                            repairer_tokens["total_tokens"] += repairer_call_tokens["total_tokens"]

                            current_sparql = repaired_sparql
                            print(f"第{i + 1}个子查询的第{repair_iter + 1}次修复完成")
                        else:
                            print(f"第{i + 1}个子查询检查合规")
                            break

                    final_sparqls.append(current_sparql)

                token_stats["checker"] = checker_tokens
                token_stats["repairer"] = repairer_tokens
                token_stats["steps_count"]["checker_calls"] = len(sparqls) * self.iter_nums
                token_stats["steps_count"]["repairer_calls"] = len(
                    [s for s in final_sparqls if s != sparqls[final_sparqls.index(s)]])

            # ============================================================
            # 步骤4: 数据库调度和执行
            # ============================================================
            print(f"\n[步骤4] 数据库调度和执行...")
            scheduler = SubQueryScheduler(self.model)
            executor = SubQueryExecutor(self.model)
            query_results = {}

            scheduler_tokens = {
                "input_tokens": 0, "output_tokens": 0, "total_tokens": 0
            }

            for i in range(len(final_sparqls)):
                # 数据库选择
                scheduler_input = f"{final_sparqls[i]} {subqueries[i]['question']}"
                sel_db = scheduler.select_database(final_sparqls[i], subqueries[i]["question"])
                scheduler_output = sel_db

                scheduler_call_tokens = self.token_calculator.calculate_llm_call_tokens(
                    scheduler_input, scheduler_output
                )
                scheduler_tokens["input_tokens"] += scheduler_call_tokens["input_tokens"]
                scheduler_tokens["output_tokens"] += scheduler_call_tokens["output_tokens"]
                scheduler_tokens["total_tokens"] += scheduler_call_tokens["total_tokens"]

                # 查询转换和执行
                converted_query = executor.convert_to_target_query(final_sparqls[i], sel_db)

                if executor.has_placeholder(converted_query):
                    converted_query = executor.replace_placeholders(converted_query, query_results)

                result = executor.execute_in_database(converted_query, sel_db)
                query_results[i + 1] = result

                print(f"  ✓ 子查询 {i + 1} 执行完成 -> {sel_db} ({len(result)} 条结果)")

            token_stats["subquery_scheduler"] = scheduler_tokens
            token_stats["steps_count"]["subquery_scheduler_calls"] = len(final_sparqls)

            # 计算总Token
            token_stats["total_tokens"] = (
                    token_stats["query_planner"]["total_tokens"] +
                    token_stats["sparql_generator"]["total_tokens"] +
                    token_stats["checker"]["total_tokens"] +
                    token_stats["repairer"]["total_tokens"] +
                    token_stats["subquery_scheduler"]["total_tokens"]
            )

            # 计算执行时间
            execution_time = time.time() - start_time

            # 评估结果
            fex, sex = self._evaluate_results(query_results, expected_answer)

            print(f"\n{'=' * 60}")
            print(f"✓ 问题 {question_id} 完成")
            print(f"  FEX: {fex}, SEX: {sex:.3f}")
            print(f"  时间: {execution_time:.2f}s")
            print(f"  Token: {token_stats['total_tokens']}")
            print(f"{'=' * 60}")

            return {
                'success': True,
                'question_id': question_id,
                'fex': fex,
                'sex': sex,
                'time': execution_time,
                'token_stats': token_stats,
                'subqueries': subqueries,
                'sparqls': final_sparqls,
                'results': query_results
            }

        except Exception as e:
            import traceback
            err_msg = str(e)
            stack = traceback.format_exc()
            print(f"\n❌ 处理问题 {question_id} 时出错: {err_msg}")
            print(stack)
            return self._create_error_result(
                time.time() - start_time,
                err_msg,
                token_stats,
                question_id
            )

    def _evaluate_results(self, actual_results: Dict, expected_answer: Dict) -> Tuple[int, float]:
        """
        评估结果（参考exp_framework_modified.py的逻辑）

        评估规则：
        - 第1、2子查询：标准化比较，匹配度≥80%视为正确
        - 第3子查询：行数相似度比较，相似度≥80%视为正确
        """
        subquery_scores = []

        # 获取子查询数量（实际结果和期望结果中的最大值）
        max_queries = max(len(actual_results), len(expected_answer))

        for query_idx in range(1, max_queries + 1):
            # 从expected_answer中正确提取数据
            query_key = f"query_{query_idx}"
            expected = expected_answer.get(query_key, {}).get("results", [])

            # 从actual_results中获取数据
            actual = actual_results.get(query_idx, [])

            # 打印调试信息
            if self.strategy != RepairStrategy.NO_REPAIR or query_idx == 1:  # 只在第一个查询或非NO_REPAIR时打印
                print(f"    评估子查询 {query_idx}: 期望 {len(expected)} 个结果, 实际 {len(actual)} 个结果")

            # 计算EX值
            if query_idx == 3:
                # 第三个子查询：只比较行数
                ex_value = self._evaluate_third_query_by_count(expected, actual)
            else:
                # 前两个子查询：标准化比较
                ex_value = self._evaluate_by_content_similarity(expected, actual)

            subquery_scores.append(ex_value)

            if self.strategy != RepairStrategy.NO_REPAIR or query_idx == 1:  # 只在第一个查询或非NO_REPAIR时打印
                print(f"    子查询 {query_idx} EX = {ex_value} {'✓' if ex_value == 1 else '✗'}")

        # SEX (EX): 子查询平均正确率
        sex = sum(subquery_scores) / len(subquery_scores) if subquery_scores else 0.0

        # FEX: 所有子查询都正确才为1
        fex = 1 if all(score == 1 for score in subquery_scores) else 0

        return fex, sex

    def _evaluate_third_query_by_count(self, expected: List, actual: List) -> int:
        """
        第三个子查询（代谢通路）的评判逻辑
        只比较返回的行数，相似度≥80%视为正确
        """
        expected_rows = len(expected)
        actual_rows = len(actual)

        if expected_rows == 0:
            # 如果期望行数为0，实际行数也应该为0或很少
            return 1 if actual_rows <= 2 else 0

        # 计算相似度，允许20%的误差范围
        row_diff = abs(expected_rows - actual_rows)
        similarity_ratio = 1 - (row_diff / expected_rows)

        # 如果相似度>=0.8（即误差<=20%），认为正确
        is_correct = 1 if similarity_ratio >= 0.8 else 0

        return is_correct

    def _evaluate_by_content_similarity(self, expected: List, actual: List) -> int:
        """
        使用标准化比较（fallback逻辑，当LLM不可用时）
        匹配度≥80%视为正确
        """
        if not expected:
            # 如果没有期望结果，默认认为正确
            return 1

        if not actual:
            # 如果实际结果为空但期望不为空，认为不正确
            return 0

        # 标准化结果
        expected_normalized = {self._normalize_item(item) for item in expected}
        actual_normalized = {self._normalize_item(item) for item in actual}

        # 使用包含性判断
        matched = expected_normalized.intersection(actual_normalized)

        # 如果匹配度超过80%认为正确
        match_ratio = len(matched) / len(expected_normalized) if expected_normalized else 1.0
        is_correct = 1 if match_ratio >= 0.8 else 0

        return is_correct

    def _normalize_item(self, item) -> str:
        """标准化结果项（忽略大小写和空格）"""
        if isinstance(item, (list, tuple)):
            return " ".join(str(x).strip().lower() for x in item)
        return str(item).strip().lower()

    def _create_error_result(self, execution_time: float, error_msg: str,
                             token_stats: Dict, question_id: int) -> Dict:
        """创建错误结果"""
        return {
            'success': False,
            'question_id': question_id,
            'fex': 0,
            'sex': 0.0,
            'time': execution_time,
            'token_stats': token_stats,
            'error': error_msg
        }

    def run_experiments(self) -> Dict:
        """运行消融实验"""
        print("\n" + "=" * 80)
        print(f"消融实验：{self.strategy.value}")
        print("=" * 80)
        print(f"测试样本数: {len(self.test_samples)}")
        print(f"当前数据集: {config.CURRENT_DATASET}")
        print(f"模型类型: {config.MODEL_TYPE}")
        print(f"评估指标: FEX, SEX, Time, Token Cost")
        print("=" * 80)

        for i, test_case in enumerate(self.test_samples, 1):
            question = test_case['question']
            expected = test_case.get('answer', {})
            question_id = test_case.get('id', i)

            print(f"\n{'=' * 80}")
            print(f"[{i}/{len(self.test_samples)}] 问题 {question_id}")
            print(f"{'=' * 80}")

            result = self.run_query(question, expected, question_id)
            self.results.append(result)

        # 计算汇总统计
        summary = self._calculate_summary()

        return {
            'experiment': self.strategy.value,
            'results': self.results,
            'summary': summary,
            'config': {
                'dataset': config.CURRENT_DATASET,
                'model': config.MODEL_TYPE,
                'num_samples': len(self.test_samples),
                'sample_ids': [r.get('question_id') for r in self.results if r.get('success')],
                'strategy': self.strategy.value,
                'timestamp': datetime.now().isoformat()
            }
        }

    def _calculate_summary(self) -> Dict:
        """计算汇总统计"""
        successful = [r for r in self.results if r.get('success', False)]

        if not successful:
            return {
                'fex': 0.0,
                'sex': 0.0,
                'avg_time': 0.0,
                'avg_tokens': 0.0,
                'success_rate': 0.0,
                'total_questions': len(self.results),
                'successful_questions': 0
            }

        return {
            'fex': sum(r['fex'] for r in successful) / len(successful),
            'sex': sum(r['sex'] for r in successful) / len(successful),
            'avg_time': sum(r['time'] for r in successful) / len(successful),
            'avg_tokens': sum(r['token_stats']['total_tokens'] for r in successful) / len(successful),
            'total_tokens': sum(r['token_stats']['total_tokens'] for r in successful),
            'success_rate': len(successful) / len(self.results),
            'total_questions': len(self.results),
            'successful_questions': len(successful)
        }

    def print_summary(self, summary: Dict):
        """打印汇总结果"""
        print("\n" + "=" * 80)
        print("实验结果汇总")
        print("=" * 80)

        print(f"\n实验配置: {self.strategy.value}")
        print(f"测试问题数: {summary['total_questions']}")
        print(f"成功执行: {summary['successful_questions']}")
        print(f"成功率: {summary['success_rate'] * 100:.1f}%")

        print(f"\n性能指标:")
        print(f"  FEX (Full Exact Match):     {summary['fex']:.3f}")
        print(f"  SEX (Sub-query Exact Match): {summary['sex']:.3f}")
        print(f"  平均执行时间:                {summary['avg_time']:.2f}s")
        print(f"  平均Token消耗:               {summary['avg_tokens']:.0f}")
        print(f"  总Token消耗:                 {summary['total_tokens']}")

        print(f"\n各问题详细结果:")
        print(f"{'ID':<6} {'FEX':<6} {'SEX':<8} {'Time(s)':<10} {'Tokens':<10} {'Status':<10}")
        print("-" * 60)

        for r in self.results:
            if r.get('success'):
                qid = r['question_id']
                fex = r['fex']
                sex = r['sex']
                time_val = r['time']
                tokens = r['token_stats']['total_tokens']
                status = "✓ 成功"

                print(f"{qid:<6} {fex:<6} {sex:<8.3f} {time_val:<10.2f} {tokens:<10} {status}")
            else:
                qid = r.get('question_id', 'N/A')
                error = r.get('error', 'Unknown')[:20]
                print(f"{qid:<6} {'N/A':<6} {'N/A':<8} {'N/A':<10} {'N/A':<10} ✗ {error}")

        print("=" * 80)

    def save_results(self, results: Dict, output_dir: str = 'ablation_results'):
        """保存实验结果"""
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.strategy.value}_{config.CURRENT_DATASET}_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        # 安全序列化
        def safe_serialize(obj):
            if isinstance(obj, (list, tuple)):
                return [safe_serialize(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: safe_serialize(v) for k, v in obj.items()}
            elif isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            else:
                return str(obj)

        safe_results = safe_serialize(results)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(safe_results, f, indent=2, ensure_ascii=False)

        print(f"\n✓ 结果已保存到: {filepath}")


def run_all_experiments(test_data: List[Dict], num_samples: int = 11):
    """运行所有三种策略的实验"""
    strategies = [
        RepairStrategy.NO_REPAIR,
        RepairStrategy.SYNTAX_ONLY,
        RepairStrategy.SEMANTIC_ONLY
    ]

    all_results = {}

    for strategy in strategies:
        print("\n\n" + "=" * 100)
        print(f"开始实验：{strategy.value}")
        print("=" * 100)

        experiment = AblationExperiment(test_data, num_samples, strategy)
        results = experiment.run_experiments()
        experiment.print_summary(results['summary'])
        experiment.save_results(results)

        all_results[strategy.value] = results['summary']

    # 打印对比表格
    print_comparison_table(all_results)

    return all_results


def print_comparison_table(all_results: Dict):
    """打印对比表格"""
    print("\n\n" + "=" * 100)
    print("三种策略对比结果")
    print("=" * 100)

    print(f"\n{'策略':<20} {'FEX':<10} {'SEX':<10} {'Avg Time(s)':<15} {'Avg Tokens':<15} {'Total Tokens':<15}")
    print("-" * 100)

    for strategy_name, summary in all_results.items():
        print(f"{strategy_name:<20} {summary['fex']:<10.3f} {summary['sex']:<10.3f} "
              f"{summary['avg_time']:<15.2f} {summary['avg_tokens']:<15.0f} {summary['total_tokens']:<15}")

    print("=" * 100)

    # 保存对比表格到文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    comparison_file = f"ablation_results/comparison_{config.CURRENT_DATASET}_{timestamp}.json"
    with open(comparison_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n✓ 对比结果已保存到: {comparison_file}")


def main():
    """主函数"""
    print("=" * 100)
    print("消融实验：三种修复策略对比")
    print("=" * 100)

    # 加载测试数据
    test_data_file = config.TEST_DATA_FILE

    try:
        with open(test_data_file, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        print(f"✓ 已加载测试数据: {test_data_file}")
        print(f"  总问题数: {len(test_data)}")
    except Exception as e:
        print(f"✗ 加载测试数据失败: {e}")
        return

    # 运行所有实验
    all_results = run_all_experiments(test_data, num_samples=19)

    print("\n" + "=" * 100)
    print("所有消融实验完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()