#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的系统评估测试框架
支持多种实验配置和评估指标
"""

import json
import time
import os
import re
from typing import Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# 导入系统组件
from agents.QueryPlanningAndGeneration import QueryPlanner, SparQLGenerator
from agents.QueryAdaptive import SubQueryScheduler, SubQueryExecutor
from agents.ResultAggregation import ResultAggregation
from agents.SemanticQueryRepair import QueryScorer, QueryRepairer
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatTongyi


class ExperimentType(Enum):
    """实验类型枚举"""
    PARAMETER_TUNING = "parameter_tuning"  # 参数调优
    ONTOLOGY_COMPARISON = "ontology_comparison"  # 本体对比
    REPAIR_COMPARISON = "repair_comparison"  # 修复器对比
    LLM_COMPARISON = "llm_comparison"  # LLM对比
    PROMPT_COMPARISON = "prompt_comparison"  # Prompt对比


@dataclass
class ExperimentConfig:
    """实验配置类"""
    # 基本配置
    experiment_name: str = "default_experiment"
    experiment_type: ExperimentType = ExperimentType.PARAMETER_TUNING

    # LLM配置
    llm_type: str = "deepseek"  # deepseek, qwen, openai
    temperature: float = 0.15

    # 系统组件开关
    use_ontology: bool = True
    use_repair: bool = True

    # 评分权重
    ontology_consistency_weight: float = 0.5
    syntax_compliance_weight: float = 0.3
    complexity_metric_weight: float = 0.2

    # 修复器配置
    min_score: int = 90
    max_attempts: int = 5

    # Prompt配置
    prompt_type: str = "full"  # full, zero_shot, few_shot, many_shot

    # 其他配置
    timeout: int = 300  # 每个查询的超时时间（秒）
    max_queries: int = None  # 最大查询数量，None表示所有


@dataclass
class QueryResult:
    """查询结果类"""
    query_id: int
    question: str
    expected_answer: str
    actual_answer: str
    execution_time: float
    success: bool
    error_message: str = ""

    # 详细信息
    subqueries: List[Dict] = field(default_factory=list)
    sparql_queries: List[str] = field(default_factory=list)
    repair_attempts: int = 0
    final_scores: List[int] = field(default_factory=list)


@dataclass
class ExperimentResult:
    """实验结果类"""
    config: ExperimentConfig
    query_results: List[QueryResult]
    start_time: datetime
    end_time: datetime

    # 统计指标
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    avg_time_per_query: float = 0.0
    success_rate: float = 0.0

    # 修复器统计
    repair_success_rate: float = 0.0
    avg_repair_attempts: float = 0.0


class AnswerEvaluator:
    """答案评估器"""

    def __init__(self):
        self.entity_patterns = {
            'microbiota': r'([A-Z][a-z]*(?:bacterium|bacter|coccus|ella|ium|aceae|vibrio)?\b|Dorea|Eubacterium|Bacteroides|Clostridium|Lactobacillus|Oscillibacter|Desulfovibrionaceae)',
            'gene': r'([A-Z][A-Z0-9]+\b|[A-Z][a-z0-9]+\b|BCL2|BAX|CASP3|IL22|MAPK14|Tjp1|Arg1|Prkaa[12]|Gcg|Nr1h4|Fgf15|Fgfr4|Cyp7a1|Sirpa|Cpt1b|Fas)',
            'pathway': r'([hm]sa\d+|[hm]mu\d+|[\w\-]+\s+signaling\s+pathway|[\w\-]+\s+metabolism|[\w\-]+\s+biosynthesis)',
        }

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """从文本中提取实体"""
        entities = {}
        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            # 清理和去重
            clean_matches = []
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1] if len(match) > 1 else ''
                if match and len(match) > 1:  # 过滤太短的匹配
                    clean_matches.append(match)
            entities[entity_type] = list(set(clean_matches))
        return entities

    def compare_answers(self, expected: str, actual: str) -> Dict[str, Any]:
        """比较期望答案和实际答案"""
        print(f"🔍 评估答案:")
        print(f"期望答案: {expected[:200]}...")
        print(f"实际答案: {actual[:200]}...")

        expected_entities = self.extract_entities(expected)
        actual_entities = self.extract_entities(actual)

        print(f"期望实体: {expected_entities}")
        print(f"实际实体: {actual_entities}")

        results = {}
        overall_tp = overall_fp = overall_fn = 0

        for entity_type in self.entity_patterns.keys():
            expected_set = set(expected_entities.get(entity_type, []))
            actual_set = set(actual_entities.get(entity_type, []))

            tp = len(expected_set & actual_set)  # 正确识别的
            fp = len(actual_set - expected_set)  # 多识别的
            fn = len(expected_set - actual_set)  # 漏识别的

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

            results[entity_type] = {
                'tp': tp, 'fp': fp, 'fn': fn,
                'precision': precision, 'recall': recall, 'f1': f1,
                'expected': list(expected_set),
                'actual': list(actual_set),
                'missing': list(expected_set - actual_set),
                'extra': list(actual_set - expected_set)
            }

            overall_tp += tp
            overall_fp += fp
            overall_fn += fn

            print(f"{entity_type}: TP={tp}, FP={fp}, FN={fn}, F1={f1:.3f}")

        # 计算总体指标
        overall_precision = overall_tp / (overall_tp + overall_fp) if (overall_tp + overall_fp) > 0 else 0
        overall_recall = overall_tp / (overall_tp + overall_fn) if (overall_tp + overall_fn) > 0 else 0
        overall_f1 = 2 * overall_precision * overall_recall / (overall_precision + overall_recall) if (
                                                                                                                  overall_precision + overall_recall) > 0 else 0

        results['overall'] = {
            'tp': overall_tp, 'fp': overall_fp, 'fn': overall_fn,
            'precision': overall_precision, 'recall': overall_recall, 'f1': overall_f1,
            'accuracy': overall_tp / (overall_tp + overall_fp + overall_fn) if (
                                                                                           overall_tp + overall_fp + overall_fn) > 0 else 0
        }

        print(f"总体: TP={overall_tp}, FP={overall_fp}, FN={overall_fn}, F1={overall_f1:.3f}")

        return results


class LLMFactory:
    """LLM工厂类"""

    @staticmethod
    def create_llm(llm_type: str, temperature: float = 0.15):
        """创建LLM实例"""
        if llm_type == "deepseek":
            return ChatOpenAI(
                temperature=temperature,
                model="deepseek-chat",
                api_key=os.environ.get('DEEPSEEK_API_KEY', 'sk-2eeb2c0f09794d5d9ca9346cc6f85c27'),
                base_url="https://api.deepseek.com/v1"
            )
        elif llm_type == "qwen":
            return ChatTongyi(
                temperature=temperature,
                model_name="qwen-plus",
                dashscope_api_key=os.environ.get('DASHSCOPE_API_KEY', 'sk-1e6a1b5f2671486380b3553c82f42199')
            )
        elif llm_type == "openai":
            return ChatOpenAI(
                temperature=temperature,
                model="gpt-3.5-turbo",
                api_key=os.environ.get('OPENAI_API_KEY')
            )
        else:
            raise ValueError(f"不支持的LLM类型: {llm_type}")


class PromptManager:
    """Prompt管理器"""

    def __init__(self):
        self.prompt_templates = {
            "zero_shot": self._get_zero_shot_templates(),
            "few_shot": self._get_few_shot_templates(),
            "many_shot": self._get_many_shot_templates(),
            "full": self._get_full_templates()
        }

    def _get_zero_shot_templates(self):
        """零样本模板"""
        return {
            "QueryPlanner": """
你是一个查询规划助手，将复杂问题分解为子查询。

问题：{question}

子查询列表：
""",
            "SparQLGenerator": """
根据问题生成SPARQL查询。

问题：{sub_question}

SPARQL查询：
""",
            "QueryRepairer": """
修复SPARQL查询错误。

查询：{sparql_query}
错误：{details}

修复后的查询：
"""
        }

    def _get_few_shot_templates(self):
        """少样本模板（包含1-2个示例）"""
        return {
            "QueryPlanner": """
你是一个查询规划助手，将复杂问题分解为子查询。

示例：
问题：哪些基因与肥胖相关，这些基因参与哪些通路？
子查询：
1. [依赖: 无] 哪些基因与肥胖相关？
2. [依赖: 1] 这些基因参与哪些通路？

问题：{question}

子查询列表：
""",
            "SparQLGenerator": """
根据问题生成SPARQL查询。

示例：
问题：哪些微生物能提高饲养效率？
SPARQL：
SELECT ?microbiota_name WHERE {
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:increases_feed_efficiency ?efficiency .
}

问题：{sub_question}

SPARQL查询：
""",
            "QueryRepairer": """
修复SPARQL查询错误。

示例：
错误查询：SELECT ?gene WHERE { ?gene ont:symbol ?name }
修复后：SELECT ?gene WHERE { ?gene rdf:type ont:Gene . ?gene ont:gene_symbol ?name }

查询：{sparql_query}
错误：{details}

修复后的查询：
"""
        }

    def _get_many_shot_templates(self):
        """多样本模板（包含3-5个示例）"""
        # 这里使用原有的完整模板
        from prompt import QueryPlanner_template, SparQLGenerator_template, QueryRepairer_template
        return {
            "QueryPlanner": QueryPlanner_template,
            "SparQLGenerator": SparQLGenerator_template,
            "QueryRepairer": QueryRepairer_template
        }

    def _get_full_templates(self):
        """完整模板（原始模板）"""
        from prompt import QueryPlanner_template, SparQLGenerator_template, QueryRepairer_template
        return {
            "QueryPlanner": QueryPlanner_template,
            "SparQLGenerator": SparQLGenerator_template,
            "QueryRepairer": QueryRepairer_template
        }

    def get_templates(self, prompt_type: str):
        """获取指定类型的模板"""
        return self.prompt_templates.get(prompt_type, self.prompt_templates["full"])


class SystemUnderTest:
    """被测试系统"""

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.llm = LLMFactory.create_llm(config.llm_type, config.temperature)
        self.prompt_manager = PromptManager()
        self.evaluator = AnswerEvaluator()

        # 初始化系统组件
        self._initialize_components()

    def _initialize_components(self):
        """初始化系统组件"""
        # 更新Prompt模板
        if self.config.prompt_type != "full":
            self._update_prompt_templates()

        # 初始化组件
        self.query_planner = QueryPlanner(self.llm)

        # 修复：正确处理本体路径
        ontology_path = "ontology.owl" if self.config.use_ontology else None
        if self.config.use_ontology:
            self.sparql_generator = SparQLGenerator(self.llm, ontology_path)
            if self.config.use_repair:
                self.query_scorer = QueryScorer(ontology_path)
                self.query_repairer = QueryRepairer(self.llm)
            else:
                self.query_scorer = None
                self.query_repairer = None
        else:
            # 无本体模式：创建一个不加载本体的生成器
            self.sparql_generator = self._create_no_ontology_generator()
            self.query_scorer = None
            self.query_repairer = None

        self.subquery_scheduler = SubQueryScheduler(self.llm)
        self.subquery_executor = SubQueryExecutor(self.llm)
        self.result_aggregator = ResultAggregation(self.llm)

    def _create_no_ontology_generator(self):
        """创建无本体的SPARQL生成器"""

        # 创建一个修改版的SparQLGenerator，不加载本体
        class NoOntologySparQLGenerator:
            def __init__(self, llm):
                self.llm = llm
                self.ontology = None
                from prompt import SparQLGenerator_template
                from langchain.prompts import PromptTemplate
                self.sparql_prompt = PromptTemplate(
                    input_variables=["sub_question", "ontology", "dependencies"],
                    template=SparQLGenerator_template
                )

            def _extract_ontology_info(self):
                """返回空的本体信息"""
                return {
                    "classes": [],
                    "properties": [],
                    "example_triples": []
                }

            def generate_sparql(self, sub_question, dependencies=None):
                """生成SPARQL查询，不使用本体"""
                ontology_info = self._extract_ontology_info()
                dependencies_str = self._format_dependencies(dependencies)

                sparql_query = self.sparql_prompt.format(
                    sub_question=sub_question,
                    ontology=ontology_info,
                    dependencies=dependencies_str
                )
                result = self.llm.invoke(sparql_query)
                return result.content

            def _format_dependencies(self, dependencies):
                if not dependencies:
                    return "无"
                formatted = []
                for dep in dependencies:
                    placeholder = f"<<SUBQUERY_{dep['id']}>>"
                    formatted.append(f"依赖子查询 {dep['id']}: {dep['question']} (占位符: {placeholder})")
                return "\n".join(formatted)

        return NoOntologySparQLGenerator(self.llm)

    def _update_prompt_templates(self):
        """更新Prompt模板"""
        templates = self.prompt_manager.get_templates(self.config.prompt_type)

        # 这里需要动态更新prompt模块中的模板
        # 由于原始设计中模板是硬编码的，这里提供一个示例实现
        import prompt
        if "QueryPlanner" in templates:
            prompt.QueryPlanner_template = templates["QueryPlanner"]
        if "SparQLGenerator" in templates:
            prompt.SparQLGenerator_template = templates["SparQLGenerator"]
        if "QueryRepairer" in templates:
            prompt.QueryRepairer_template = templates["QueryRepairer"]

    def process_query(self, query_id: int, question: str) -> QueryResult:
        """处理单个查询"""
        start_time = time.time()

        try:
            print(f"📝 处理查询 {query_id}: {question[:50]}...")

            # 1. 查询规划
            subqueries = self.query_planner.get_subqueries(question)
            print(f"   规划得到 {len(subqueries)} 个子查询")

            # 2. 生成SPARQL查询
            sparql_queries = []
            for i, subquery in enumerate(subqueries):
                sub_question = subquery["question"]
                dependencies = [subqueries[j - 1] for j in subquery["dependencies"]]
                sparql_query = self.sparql_generator.generate_sparql(sub_question, dependencies)
                sparql_queries.append(sparql_query)
                print(f"   子查询 {i + 1} SPARQL生成完成")

            # 3. 查询修复（如果启用）
            repair_attempts = 0
            final_scores = []

            if self.config.use_repair and self.query_scorer and self.query_repairer:
                print("   🔧 开始查询修复...")
                for i, sparql_query in enumerate(sparql_queries):
                    score, details = self.query_scorer.score_query(sparql_query)
                    final_scores.append(score)

                    if score < self.config.min_score:
                        for attempt in range(self.config.max_attempts):
                            repair_attempts += 1
                            dependencies = [subqueries[k - 1] for k in subqueries[i]["dependencies"]]
                            repaired_query = self.query_repairer.repair_sparql(
                                subqueries[i]["question"], details, sparql_query, dependencies
                            )

                            new_score, _ = self.query_scorer.score_query(repaired_query)
                            if new_score > score:
                                sparql_queries[i] = repaired_query
                                final_scores[i] = new_score
                                score = new_score
                                print(f"     修复成功，分数提升到 {score}")

                            if score >= self.config.min_score:
                                break

            # 4. 查询执行
            print("   💾 开始数据库查询...")
            query_results = {}
            converted_queries = []

            for i, sparql_query in enumerate(sparql_queries):
                try:
                    sel_db = self.subquery_scheduler.select_database(sparql_query, subqueries[i]["question"])
                    converted_query = self.subquery_executor.convert_to_target_query(sparql_query, sel_db)
                    converted_queries.append(converted_query)

                    if self.subquery_executor.has_placeholder(converted_query):
                        converted_query = self.subquery_executor.replace_placeholders(converted_query, query_results)

                    result = self.subquery_executor.execute_in_database(converted_query, sel_db)
                    query_results[i + 1] = result
                    print(f"     子查询 {i + 1} 执行完成，得到 {len(result)} 条结果")

                except Exception as e:
                    print(f"     子查询 {i + 1} 执行失败: {e}")
                    query_results[i + 1] = []

            # 5. 结果聚合
            print("   📊 结果聚合...")
            try:
                tables, explanation = self.result_aggregator.process(question, converted_queries, query_results)
                actual_answer = f"查询结果表格:\n{tables}\n\n分析说明:\n{explanation}"
            except Exception as e:
                print(f"     结果聚合失败: {e}")
                # 如果聚合失败，直接使用查询结果
                actual_answer = f"查询结果: {query_results}"

            execution_time = time.time() - start_time
            print(f"   ✅ 查询完成，耗时 {execution_time:.2f}秒")

            return QueryResult(
                query_id=query_id,
                question=question,
                expected_answer="",  # 将在外部设置
                actual_answer=actual_answer,
                execution_time=execution_time,
                success=True,
                subqueries=subqueries,
                sparql_queries=sparql_queries,
                repair_attempts=repair_attempts,
                final_scores=final_scores
            )

        except Exception as e:
            execution_time = time.time() - start_time
            print(f"   ❌ 查询失败: {e}")
            return QueryResult(
                query_id=query_id,
                question=question,
                expected_answer="",
                actual_answer="",
                execution_time=execution_time,
                success=False,
                error_message=str(e)
            )


class ExperimentRunner:
    """实验运行器"""

    def __init__(self):
        self.evaluator = AnswerEvaluator()

    def load_test_data(self, file_path: str = "pig_microbiota_qa.json") -> List[Dict]:
        """加载测试数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"测试数据文件 {file_path} 不存在")
            return []

    def run_experiment(self, config: ExperimentConfig) -> ExperimentResult:
        """运行实验"""
        print(f"开始运行实验: {config.experiment_name}")

        # 加载测试数据
        test_data = self.load_test_data()
        if not test_data:
            raise ValueError("无法加载测试数据")

        # 限制查询数量
        if config.max_queries:
            test_data = test_data[:config.max_queries]

        # 初始化系统
        system = SystemUnderTest(config)

        # 运行测试
        start_time = datetime.now()
        query_results = []

        for test_case in test_data:
            query_id = test_case["id"]
            question = test_case["question"]
            expected_answer = test_case["real_answer"]

            print(f"处理查询 {query_id}: {question[:50]}...")

            # 处理查询
            result = system.process_query(query_id, question)
            result.expected_answer = expected_answer

            query_results.append(result)

            # 显示进度
            if query_id % 5 == 0:
                print(f"已完成 {query_id}/{len(test_data)} 个查询")

        end_time = datetime.now()

        # 计算统计指标
        experiment_result = ExperimentResult(
            config=config,
            query_results=query_results,
            start_time=start_time,
            end_time=end_time
        )

        self._calculate_metrics(experiment_result)

        return experiment_result

    def _calculate_metrics(self, result: ExperimentResult):
        """计算评估指标"""
        successful_queries = [r for r in result.query_results if r.success]
        total_queries = len(result.query_results)

        if not successful_queries:
            return

        # 基本统计
        result.success_rate = len(successful_queries) / total_queries
        result.avg_time_per_query = sum(r.execution_time for r in result.query_results) / total_queries

        # 修复器统计
        if result.config.use_repair:
            repair_queries = [r for r in successful_queries if r.repair_attempts > 0]
            result.repair_success_rate = len(repair_queries) / len(successful_queries) if successful_queries else 0
            result.avg_repair_attempts = sum(r.repair_attempts for r in successful_queries) / len(successful_queries)

        # 答案质量评估
        overall_metrics = {'tp': 0, 'fp': 0, 'fn': 0}

        for query_result in successful_queries:
            if query_result.actual_answer:
                comparison = self.evaluator.compare_answers(
                    query_result.expected_answer,
                    query_result.actual_answer
                )

                overall_metrics['tp'] += comparison['overall']['tp']
                overall_metrics['fp'] += comparison['overall']['fp']
                overall_metrics['fn'] += comparison['overall']['fn']

        # 计算总体指标
        tp, fp, fn = overall_metrics['tp'], overall_metrics['fp'], overall_metrics['fn']

        result.precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        result.recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        result.f1_score = 2 * result.precision * result.recall / (result.precision + result.recall) if (
                                                                                                                   result.precision + result.recall) > 0 else 0
        result.accuracy = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0

    def generate_report(self, results: List[ExperimentResult]) -> Dict[str, Any]:
        """生成实验报告（JSON格式）"""
        report = {
            "meta": {
                "generation_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_experiments": len(results),
                "framework_version": "1.0"
            },
            "experiments": [],
            "summary": {
                "best_experiment": None,
                "performance_comparison": {}
            }
        }

        best_f1 = -1
        best_exp_name = None

        for i, result in enumerate(results, 1):
            # 基本信息
            exp_data = {
                "experiment_id": i,
                "name": result.config.experiment_name,
                "type": result.config.experiment_type.value,
                "config": {
                    "llm_type": result.config.llm_type,
                    "temperature": result.config.temperature,
                    "use_ontology": result.config.use_ontology,
                    "use_repair": result.config.use_repair,
                    "prompt_type": result.config.prompt_type,
                    "max_queries": result.config.max_queries,
                    "min_score": result.config.min_score,
                    "max_attempts": result.config.max_attempts
                },
                "execution": {
                    "start_time": result.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "end_time": result.end_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "duration_seconds": (result.end_time - result.start_time).total_seconds()
                },
                "statistics": {
                    "total_queries": len(result.query_results),
                    "successful_queries": len([r for r in result.query_results if r.success]),
                    "success_rate": result.success_rate,
                    "avg_time_per_query": result.avg_time_per_query
                },
                "metrics": {
                    "accuracy": result.accuracy,
                    "precision": result.precision,
                    "recall": result.recall,
                    "f1_score": result.f1_score
                },
                "repair_stats": {
                    "repair_success_rate": result.repair_success_rate,
                    "avg_repair_attempts": result.avg_repair_attempts
                } if result.config.use_repair else None,
                "detailed_results": []
            }

            # 跟踪最佳实验
            if result.f1_score > best_f1:
                best_f1 = result.f1_score
                best_exp_name = result.config.experiment_name

            # 详细结果分析
            for query_result in result.query_results:
                query_detail = {
                    "query_id": query_result.query_id,
                    "question": query_result.question,
                    "success": query_result.success,
                    "execution_time": query_result.execution_time,
                    "error_message": query_result.error_message if not query_result.success else None
                }

                if query_result.success and query_result.actual_answer:
                    # 答案比较分析
                    comparison = self.evaluator.compare_answers(
                        query_result.expected_answer,
                        query_result.actual_answer
                    )

                    query_detail["answer_analysis"] = {
                        "overall_metrics": comparison['overall'],
                        "entity_analysis": {
                            entity_type: {
                                "precision": metrics['precision'],
                                "recall": metrics['recall'],
                                "f1": metrics['f1'],
                                "missing_entities": metrics['missing'],
                                "extra_entities": metrics['extra'],
                                "correct_entities": list(set(metrics['expected']) & set(metrics['actual']))
                            }
                            for entity_type, metrics in comparison.items()
                            if entity_type != 'overall'
                        }
                    }

                if result.config.use_repair and query_result.repair_attempts > 0:
                    query_detail["repair_info"] = {
                        "attempts": query_result.repair_attempts,
                        "final_scores": query_result.final_scores
                    }

                exp_data["detailed_results"].append(query_detail)

            report["experiments"].append(exp_data)

        # 汇总分析
        report["summary"]["best_experiment"] = best_exp_name

        # 性能对比
        if len(results) > 1:
            comparison_data = {}
            for result in results:
                comparison_data[result.config.experiment_name] = {
                    "f1_score": result.f1_score,
                    "accuracy": result.accuracy,
                    "success_rate": result.success_rate,
                    "avg_time": result.avg_time_per_query
                }
            report["summary"]["performance_comparison"] = comparison_data

        return report

    def save_report(self, report: Dict[str, Any], experiment_type: str = "mixed") -> str:
        """保存报告到JSON文件"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"experiment_report_{experiment_type}_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return filename


def main():
    """主函数 - 运行实验"""
    runner = ExperimentRunner()

    # 实验配置列表
    experiments = [
        # 1. 参数调优实验
        ExperimentConfig(
            experiment_name="baseline",
            experiment_type=ExperimentType.PARAMETER_TUNING,
            llm_type="deepseek",
            temperature=0.15,
            max_queries=2  # 限制查询数量以便测试
        ),
        #
        # ExperimentConfig(
        #     experiment_name="high_temperature",
        #     experiment_type=ExperimentType.PARAMETER_TUNING,
        #     llm_type="deepseek",
        #     temperature=0.7,
        #     max_queries=5
        # ),
        #
        # # 2. 本体对比实验
        # ExperimentConfig(
        #     experiment_name="without_ontology",
        #     experiment_type=ExperimentType.ONTOLOGY_COMPARISON,
        #     use_ontology=False,
        #     max_queries=5
        # ),
        #
        # # 3. 修复器对比实验
        # ExperimentConfig(
        #     experiment_name="without_repair",
        #     experiment_type=ExperimentType.REPAIR_COMPARISON,
        #     use_repair=False,
        #     max_queries=5
        # ),
        #
        # # 4. Prompt对比实验
        # ExperimentConfig(
        #     experiment_name="zero_shot_prompt",
        #     experiment_type=ExperimentType.PROMPT_COMPARISON,
        #     prompt_type="zero_shot",
        #     max_queries=5
        # ),
        #
        # ExperimentConfig(
        #     experiment_name="few_shot_prompt",
        #     experiment_type=ExperimentType.PROMPT_COMPARISON,
        #     prompt_type="few_shot",
        #     max_queries=5
        # ),
    ]

    # 运行实验
    results = []
    for config in experiments:
        try:
            result = runner.run_experiment(config)
            results.append(result)
            print(f"实验 {config.experiment_name} 完成")
        except Exception as e:
            print(f"实验 {config.experiment_name} 失败: {e}")

    # 生成报告
    if results:
        report = runner.generate_report(results)
        print("\n" + report)

        # 保存报告
        with open(f"experiment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", 'w', encoding='utf-8') as f:
            f.write(report)

        print("\n报告已保存到文件")


if __name__ == "__main__":
    main()