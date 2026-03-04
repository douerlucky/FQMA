import argparse
import sys

from agents.QueryPlanningAndGeneration import QueryPlanner, SparQLGenerator
from agents.QueryAdaptive import SubQueryScheduler, SubQueryExecutor
from agents.ResultAggregation import ResultAggregation
from agents.SemanticQueryRepair import QueryChecker, QueryRepairer
from backup.SemanticQueryRepair import QueryChecker as QueryCheckerGMQA, QueryRepairer as QueryRepairerGMQA
import config

try:
    from config import LLM_CHECK_MODE
except ImportError:
    LLM_CHECK_MODE = "advisory"


def run_query(question: str):
    """对单个自然语言问题执行完整的查询流程，并输出结果。"""

    print(f"\n{'═' * 60}")
    print(f"📝 问题: {question}")
    print(f"📊 当前数据集: {config.CURRENT_DATASET}")
    print(f"{'═' * 60}\n")

    # ── 查询规划 ──────────────────────────────────────────
    query_planner = QueryPlanner(config.model)
    subqueries = query_planner.get_subqueries(question)
    print("子查询结果:", subqueries)

    # ── SPARQL 生成 ───────────────────────────────────────
    sparql_generator = SparQLGenerator(config.model, config.ontology_path)
    sparqls = []

    if subqueries:
        for subquery in subqueries:
            sub_question = subquery["question"]
            dependencies = [subqueries[i - 1] for i in subquery["dependencies"]]
            sparql_query = sparql_generator.generate_sparql(sub_question, dependencies)
            sparqls.append(sparql_query)
            print(f"生成的SPARQL查询 (子查询 {subquery['id']}): {sparql_query}")

    # ── 语义检查与修复 ────────────────────────────────────
    print(f"\n{'=' * 80}")
    print(f"📊 检查配置: LLM检查模式 = {LLM_CHECK_MODE}")
    print(f"{'=' * 80}\n")

    if config.CURRENT_DATASET == 'GMQA':
        checker = QueryCheckerGMQA(config.ontology_path, config.model, llm_check_mode=LLM_CHECK_MODE)
        repairer = QueryRepairerGMQA(config.model)
    else:
        checker = QueryChecker(config.ontology_path, config.model, llm_check_mode=LLM_CHECK_MODE)
        repairer = QueryRepairer(config.model)

    for i in range(len(sparqls)):
        print(f"\n{'=' * 80}")
        print(f"第{i + 1}个子查询正在评价")
        print(f"子查询: {subqueries[i]['question']}")
        print(f"{'=' * 80}")

        for repair_iter in range(config.iter_nums):
            is_compliant, details = checker.check_query(sparqls[i], subqueries[i]["question"])

            if not is_compliant or repair_iter == 0:
                print(f"\n--- 检查详情 ---")
                print(details)
                print(f"--- 详情结束 ---\n")

            print(f"\n📋 检查结果: {'✅ 合规' if is_compliant else '❌ 不合规'}")

            if not is_compliant:
                print(f"⚠️ 语法不合规,进行第{repair_iter + 1}次迭代修复")
                repaired_sparql = repairer.repair_sparql(subqueries[i]["question"], details, sparqls[i])
                print(f"第{i + 1}个子查询的第{repair_iter + 1}次修复的结果是：")
                print(repaired_sparql)
                sparqls[i] = repaired_sparql
            else:
                print(f"✅ 查询合规，无需修复")
                break

    # ── 数据库调度与执行 ──────────────────────────────────
    print("\n=== 数据库选择 ===")
    subqueryscheduler = SubQueryScheduler(config.model)
    converted_queries = []
    query_results = {}

    for i in range(len(sparqls)):
        sel_db = subqueryscheduler.select_database(sparqls[i], subqueries[i]["question"])
        subqueryexecutor = SubQueryExecutor(config.model)
        print(f"子查询 {i + 1} 选择数据库: {sel_db}")
        converted_query = subqueryexecutor.convert_to_target_query(sparqls[i], sel_db)
        converted_queries.append(converted_query)
        print(f"子查询 {i + 1} 转换的查询语言: {converted_query}")

        if subqueryexecutor.has_placeholder(converted_query):
            print("\n替换后的查询:")
            converted_query = subqueryexecutor.replace_placeholders(converted_query, query_results)
            print(converted_query)
        else:
            print("无需上一个查询的结果作为输入，无需替换")

        result = subqueryexecutor.execute_in_database(converted_query, sel_db)
        query_results.update({i + 1: result})
        print(f"子查询 {i + 1} 查询结果: {result}")

    # ── 结果聚合 ──────────────────────────────────────────
    print("\n=== 结果聚合 ===")
    resultAggregation = ResultAggregation(config.model)
    tables, explanation = resultAggregation.process(question, converted_queries, query_results)
    print(tables)
    print("\n整体分析和建议:\n")
    print(explanation)


def interactive_mode():
    """交互式命令行查询循环：循环接收用户输入的问题并执行查询，直到用户退出。"""

    print(f"\n{'═' * 60}")
    print(f"  🔬 FQMA 交互式查询模式")
    print(f"  数据集: {config.CURRENT_DATASET}  |  模型: {config.model}")
    print(f"{'═' * 60}")
    print("  输入自然语言问题后按回车执行查询。")
    print("  输入 exit 或直接回车退出。\n")

    while True:
        try:
            question = input("❓ 请输入问题: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 已退出交互模式。")
            break

        if not question or question.lower() in ("exit", "quit", "q", "退出"):
            print("👋 已退出交互模式。")
            break

        try:
            run_query(question)
        except Exception as e:
            print(f"\n❌ 查询执行出错: {e}")
            print("  请检查问题或配置后重试。\n")


def main():
    parser = argparse.ArgumentParser(
        description="FQMA 查询系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 交互式模式（通过 start.sh / start.bat 选项 2 进入）
  python main.py --interactive

  # 直接传入单个问题
  python main.py --question "查找所有位置在Benguela会议上发表论文的作者，获取这些作者的姓名。"

  # 不带参数：运行内置测试问题集的最后一条
  python main.py
        """
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="进入交互式命令行查询模式，循环接收问题输入"
    )
    parser.add_argument(
        "--question", "-q",
        type=str,
        default=None,
        help="直接传入一个自然语言问题并执行查询后退出"
    )

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()

    elif args.question:
        run_query(args.question)

    else:
        # 原始行为：运行内置测试问题集的最后一条
        print("当前数据库: " + config.CURRENT_DATASET)
        test_questions = [
            "给ketogenic diet食物导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够减少这些微生物的数量？这些基因的代谢通路是什么？",
            "给\"henolic compounds from red wine and coffee\"食物导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够减少这些微生物的数量？这些基因的代谢通路是什么？",
            "使用药物Anticholinergic drug导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够增加这些微生物群的数量？这些基因的代谢通路是什么？使用药物Anticholinergic drug导致肠道微生物丰度上升的微生物有哪些？",
            "哪些微生物群关联于生猪饲养效率，在\"Fattening, Unmedicated feed formula / Antibiotics and zinc oxide\"条件下Pvalue在0.2与0.21之间？哪些基因的表达能够增加这些微生物群的数量？这些基因的代谢通路有哪些？",
            "哪些微生物群关联于生猪饲养效率且Pvalue在0.28与0.288之间？哪些基因的表达能够增加这些微生物群的数量？这些基因的代谢通路有哪些？",
            "（genera）Dorea，Eubacterium，Bacteroides中哪些微生物群对生猪饲养效率是显著相关的？哪些基因的表达能够减少这些微生物群的数量？这些基因的代谢通路有哪些？",
            "Eubacterium是否对生猪饲养效率是显著相关的？哪些基因的表达能够减少这些微生物群的数量？这些基因的代谢通路有哪些？",
            "Bacteroides是否对生猪饲养效率是显著相关的？它产生的代谢物和哪些基因的表达量有关？这些基因的代谢通路有哪些？",
            "Clostridium，Treponema中哪些微生物群对生猪饲养效率是显著相关的？哪些基因的表达能够增加这些微生物群的数量？hsa04060 Cytokine-cytokine receptor interaction，hsa04061 Viral protein interaction with cytokine and cytokine receptor，hsa04062 Chemokine signaling pathway，hsa01521 EGFR tyrosine kinase inhibitor resistance,mmu01521 EGFR tyrosine kinase inhibitor resistance，hsa04066 HIF-1 signaling pathway,hsa01524 Platinum drug resistance，mmu04152 AMPK signaling pathway,mmu04010 MAPK signaling pathway，mmu00220 Arginine biosynthesis，hsa04659 Th17 cell differentiation,mmu04714 Thermogenesis中哪些在这些基因的代谢通路里？",
            "使用药物Metformin导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够增加这些微生物群的数量？这些基因的代谢通路是什么？",
            "使用药物Metformin导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够减少这些微生物群的数量？这些基因的代谢通路是什么？",
        ]
        run_query(test_questions[-1])


if __name__ == "__main__":
    main()