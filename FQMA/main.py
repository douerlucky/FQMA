from agents.QueryPlanningAndGeneration import QueryPlanner, SparQLGenerator
from agents.QueryAdaptive import SubQueryScheduler, SubQueryExecutor
from agents.ResultAggregation import ResultAggregation
from agents.SemanticQueryRepair import QueryChecker, QueryRepairer
from config import ontology_path, model, iter_nums

# 导入检查配置
try:
    from config import LLM_CHECK_MODE
except ImportError:
    LLM_CHECK_MODE = "advisory"  # 默认使用advisory模式


def main():
    # 初始化查询规划器
    query_planner = QueryPlanner(model)
    test_questions = [
        "给ketogenic diet食物导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够减少这些微生物的数量？这些基因的代谢通路是什么？",
        "给\"henolic compounds from red wine and coffee\"食物导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够减少这些微生物的数量？这些基因的代谢通路是什么？",
        "使用药物Anticholinergic drug导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够增加这些微生物群的数量？这些基因的代谢通路是什么？使用药物Anticholinergic drug导致肠道微生物丰度上升的微生物有哪些？",
        "哪些微生物群关联于生猪饲养效率，在\"Fattening, Unmedicated feed formula / Antibiotics and zinc oxide\"条件下Pvalue在0.2与0.21之间？哪些基因的表达能够增加这些微生物群的数量？这些基因的代谢通路有哪些？",
        "哪些微生物群关联于生猪饲养效率且Pvalue在0.28与0.288之间？哪些基因的表达能够增加这些微生物群的数量？这些基因的代谢通路有哪些？",
        "（genera）Dorea，Eubacterium，Bacteroides中哪些微生物群对生猪饲养效率是显著相关的？哪些基因的表达能够减少这些微生物群的数量？这些基因的代谢通路有哪些？",
        "Eubacterium是否对生猪饲养效率是显著相关的？哪些基因的表达能够减少这些微生物群的数量？这些基因的代谢通路有哪些？",
        " Bacteroides是否对生猪饲养效率是显著相关的？它产生的代谢物和哪些基因的表达量有关？这些基因的代谢通路有哪些？",
        " Clostridium，Treponema中哪些微生物群对生猪饲养效率是显著相关的？哪些基因的表达能够增加这些微生物群的数量？hsa04060 Cytokine-cytokine receptor interaction，hsa04061 Viral protein interaction with cytokine and cytokine receptor，hsa04062 Chemokine signaling pathway，hsa01521 EGFR tyrosine kinase inhibitor resistance,mmu01521 EGFR tyrosine kinase inhibitor resistance，hsa04066 HIF-1 signaling pathway,hsa01524 Platinum drug resistance，mmu04152 AMPK signaling pathway,mmu04010 MAPK signaling pathway，mmu00220 Arginine biosynthesis，hsa04659 Th17 cell differentiation,mmu04714 Thermogenesis中哪些在这些基因的代谢通路里？",
        "使用药物Metformin导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够增加这些微生物群的数量？这些基因的代谢通路是什么？",
        "使用药物Metformin导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够减少这些微生物群的数量？这些基因的代谢通路是什么？",
        "查询ID为3的作者所著的前10篇论文，这些论文的摘要，之后在另一数据库他们的标题和提交的会议ID又是什么",
        "查询ID为1000的委员会的成员 ID，获取对应的邮箱地址，这些成员的名字、姓氏又是什么呢？",
        "查找ID为3的作者所著的所有论文,查询这些论文的审稿意见,查询每篇论文的作者数量",
        "查询ID=1000委员会的成员,查询这些成员的电子邮件地址,然后查询这些成员名字、姓氏",
        "查找会议ID=7的投稿论文,这些论文的所有审稿意见是是什么,每篇论文的标题和对应的会议是什么",
        "查找所有提交到会议ID=7的论文，投稿论文摘要是什么，每篇论文的作者数量",
    "找出所有既是委员会成员又是论文作者的人，再查询邮箱，然后在图数据库查找这些作者撰写的论文的ID和抬头。",
    "查询ID为7会议提交的所有论文ID和标题，查询这些论文的评审意见，Neo4j中查询每篇论文的作者信息",
    "查找所有在‘YSWC 2015 Program Committee’委员会中的成员，获取他们的邮箱地址",
    "在Neo4j中查找所有作者名为'Aberthol'的人员所撰写的论文，返回论文ID、作者姓名和论文标题。",
    "查找所有位置为Benguela举办的会议上发表论文的作者，获取这些作者的姓名。",
    "找出委员会YSWC 2015 Program Committee所有成员，并获取他们详细个人信息包括所属的所有委员会信息",
    "查询ID为62的作者所著的前10篇论文及其摘要",
    "查询ID为1658的作者所著的前10篇论文的标题和提交的会议ID",
    "查询ID为3的作者所著的前10篇论文，这些论文的摘要，再查他们的标题和提交的会议ID又是什么",
    "查找所有位置在Benguela会议上发表论文的作者，获取这些作者的姓名。",
    "Query the member IDs of the committee with ID 1000, obtain the corresponding email addresses, and what are the first and last names of these members?"]
    test_question = test_questions[-1]
    # 获取子查询
    subqueries = query_planner.get_subqueries(test_question)
    print("子查询结果:", subqueries)

    # 初始化SparQL生成器
    sparql_generator = SparQLGenerator(model, ontology_path)
    sparqls = []

    # 生成每个子查询的SPARQL
    if subqueries:
        for subquery in subqueries:
            sub_question = subquery["question"]
            dependencies = [subqueries[i - 1] for i in subquery["dependencies"]]
            sparql_query = sparql_generator.generate_sparql(sub_question, dependencies)
            sparqls.append(sparql_query)
            print(f"生成的SPARQL查询 (子查询 {subquery['id']}): {sparql_query}")

    # 评分和修复
    sparql_repair = []
    print(f"\n{'=' * 80}")
    print(f"📊 检查配置: LLM检查模式 = {LLM_CHECK_MODE}")
    print(f"{'=' * 80}\n")
    checker = QueryChecker(ontology_path, model, llm_check_mode=LLM_CHECK_MODE)  # 传入模型和检查模式
    repairer = QueryRepairer(model)  # 修复器

    for i in range(len(sparqls)):
        print(f"\n{'=' * 80}")
        print(f"第{i + 1}个子查询正在评价")
        print(f"子查询: {subqueries[i]['question']}")
        print(f"{'=' * 80}")

        for repair_iter in range(iter_nums):
            is_compliant, details = checker.check_query(sparqls[i], subqueries[i]["question"])

            # 🔥 始终输出检查详情
            if not is_compliant or repair_iter == 0:  # 第一次或不合规时输出详情
                print(f"\n--- 检查详情 ---")
                print(details)
                print(f"--- 详情结束 ---\n")

            print(f"\n📋 检查结果: {'✅ 合规' if is_compliant else '❌ 不合规'}")

            if (not is_compliant):
                print(f"⚠️ 语法不合规,进行第{repair_iter + 1}次迭代修复")
                repaired_sparql = repairer.repair_sparql(subqueries[i]["question"], details, sparqls[i])
                print(f"第{i + 1}个子查询的第{repair_iter + 1}次修复的结果是：")
                print(repaired_sparql)
                sparqls[i] = repaired_sparql
            else:
                print(f"✅ 查询合规，无需修复")
                break

    # 数据库调度
    print("\n=== 数据库选择 ===")
    subqueryscheduler = SubQueryScheduler(model)
    converted_queries = []
    query_results = {}

    for i in range(len(sparqls)):
        sel_db = subqueryscheduler.select_database(
            sparqls[i],
            subqueries[i]["question"]
        )
        subqueryexecutor = SubQueryExecutor(model)
        print(f"子查询 {i + 1} 选择数据库: {sel_db}")
        converted_query = subqueryexecutor.convert_to_target_query(sparqls[i], sel_db)
        converted_queries.append(converted_query)
        print(f"子查询 {i + 1} 转换的查询语言: {converted_query}")
        if (subqueryexecutor.has_placeholder(converted_query)):
            print("\n替换后的查询:")
            converted_query = subqueryexecutor.replace_placeholders(converted_query, query_results)
            print(converted_query)
        else:
            print("无需上一个查询的结果作为输入，无需替换")
        result = subqueryexecutor.execute_in_database(converted_query, sel_db)
        query_results.update({i + 1: result})
        print(f"子查询 {i + 1} 查询结果: {result}")

    print("\n=== 结果聚合 ===")
    resultAggregation = ResultAggregation(model)
    tables, explanation = resultAggregation.process(test_question, converted_queries, query_results)
    print(tables)
    # 显示整体分析和建议
    print("整体分析和建议:\n")
    print(explanation)


if __name__ == "__main__":
    main()