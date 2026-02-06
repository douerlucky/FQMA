from agents.QueryPlanningAndGeneration import QueryPlanner, SparQLGenerator
from agents.QueryAdaptive import SubQueryScheduler, SubQueryExecutor
from agents.ResultAggregation import ResultAggregation
from agents.SemanticQueryRepair import QueryChecker, QueryRepairer
from agents.DatabaseExecutor import Neo4jQueryExecutor, MySQLQueryExecutor, PostgreQueryExecutor
from config import ontology_path, model, iter_nums, Neo4j_config, MySQL_config, Postgre_config, GutMDisorder_config

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.tools import Tool
from langchain_core.prompts.prompt import PromptTemplate
from langchain.chains import LLMChain
from typing import List, Dict, Any


class DatabaseQueryTool:
    """统一的数据库查询工具类，集成了原有的多个组件"""

    def __init__(self, model):
        self.model = model
        self.query_planner = QueryPlanner(model)
        self.sparql_generator = SparQLGenerator(model, ontology_path)
        self.subquery_scheduler = SubQueryScheduler(model)
        self.subquery_executor = SubQueryExecutor(model)
        self.result_aggregation = ResultAggregation(model)

        # 修复相关组件
        self.query_checker = QueryChecker(ontology_path)
        self.query_repairer = QueryRepairer(model)

    def run(self, question: str) -> str:
        """
        执行完整的查询流程：分解 -> 生成SPARQL -> 修复 -> 调度 -> 执行 -> 聚合
        """
        try:
            print(f"\n🔍 开始处理问题: {question}")
            print("=" * 80)

            # 步骤1: 获取子查询
            subqueries = self.query_planner.get_subqueries(question)
            if not subqueries:
                return "❌ 无法分解查询，请重新表述问题"

            print(f"📋 分解出 {len(subqueries)} 个子查询:")
            for sq in subqueries:
                deps = f"依赖: {sq['dependencies']}" if sq['dependencies'] else "依赖: 无"
                print(f"   {sq['id']}. [{deps}] {sq['question']}")

            # 步骤2: 生成和修复SPARQL查询
            sparqls = []
            for subquery in subqueries:
                sub_question = subquery["question"]
                dependencies = [subqueries[i - 1] for i in subquery["dependencies"]]

                # 生成SPARQL
                sparql_query = self.sparql_generator.generate_sparql(sub_question, dependencies)

                # 修复SPARQL（如果启用）
                if iter_nums > 0:
                    for repair_iter in range(iter_nums):
                        is_compliant, details = self.query_checker.check_query(sparql_query, sub_question)
                        if not is_compliant:
                            print(f"🔧 修复子查询 {subquery['id']} (第{repair_iter + 1}次)")
                            sparql_query = self.query_repairer.repair_sparql(sub_question, details, sparql_query)
                        else:
                            break

                sparqls.append(sparql_query)
                print(f"✅ 子查询 {subquery['id']} SPARQL已生成")

            # 步骤3: 数据库调度和执行
            converted_queries = []
            query_results = {}

            for i, sparql in enumerate(sparqls):
                subquery = subqueries[i]

                # 选择数据库
                sel_db = self.subquery_scheduler.select_database(sparql, subquery["question"])
                print(f"📊 子查询 {i + 1} 选择数据库: {sel_db}")

                # 转换查询语言
                converted_query = self.subquery_executor.convert_to_target_query(sparql, sel_db)
                converted_queries.append(converted_query)

                # 替换占位符
                if self.subquery_executor.has_placeholder(converted_query):
                    converted_query = self.subquery_executor.replace_placeholders(converted_query, query_results)

                # 执行查询
                result = self.subquery_executor.execute_in_database(converted_query, sel_db)
                query_results.update({i + 1: result})
                print(f"📈 子查询 {i + 1} 执行完成，结果: {len(result)} 条记录")

            # 步骤4: 结果聚合
            print("\n📊 开始结果聚合...")
            tables, explanation = self.result_aggregation.process(question, converted_queries, query_results)

            # 格式化最终结果
            final_result = f"""
🎯 查询结果总结:

{explanation}

📋 详细数据表格:
{tables}

✅ 查询完成! 共处理了 {len(subqueries)} 个子查询，涉及 {len(set(self.subquery_scheduler.select_database(sparql, subqueries[i]["question"]) for i, sparql in enumerate(sparqls)))} 个数据库。
"""

            return final_result.strip()

        except Exception as e:
            error_msg = f"❌ 查询过程中出现错误: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return error_msg


class Neo4jQueryTool:
    """Neo4j专用查询工具"""

    def __init__(self):
        self.executor = Neo4jQueryExecutor(
            Neo4j_config['uri'],
            Neo4j_config['user'],
            Neo4j_config['password']
        )

    def run(self, query: str) -> str:
        """执行Neo4j Cypher查询"""
        try:
            print(f"🔵 执行Neo4j查询: {query}")
            result = self.executor.execute_query(query)

            if not result:
                return "Neo4j查询未返回结果"

            # 格式化结果
            formatted_result = "Neo4j查询结果:\n"
            for i, row in enumerate(result[:10], 1):  # 限制显示前10条
                formatted_result += f"{i}. {row}\n"

            if len(result) > 10:
                formatted_result += f"... 还有 {len(result) - 10} 条记录\n"

            formatted_result += f"\n总计: {len(result)} 条记录"
            return formatted_result

        except Exception as e:
            return f"Neo4j查询错误: {str(e)}"


class MySQLQueryTool:
    """MySQL专用查询工具"""

    def __init__(self, database='newgutmgene'):
        if database == 'gutmdisorder':
            config = GutMDisorder_config
        else:
            config = MySQL_config

        self.executor = MySQLQueryExecutor(
            config['host'],
            config['user'],
            config['password'],
            config['database']
        )
        self.database = database

    def run(self, query: str) -> str:
        """执行MySQL查询"""
        try:
            print(f"🟡 执行MySQL({self.database})查询: {query}")
            result = self.executor.execute_query(query)

            if not result:
                return f"MySQL({self.database})查询未返回结果"

            # 格式化结果
            formatted_result = f"MySQL({self.database})查询结果:\n"
            for i, row in enumerate(result[:10], 1):  # 限制显示前10条
                formatted_result += f"{i}. {row}\n"

            if len(result) > 10:
                formatted_result += f"... 还有 {len(result) - 10} 条记录\n"

            formatted_result += f"\n总计: {len(result)} 条记录"
            return formatted_result

        except Exception as e:
            return f"MySQL({self.database})查询错误: {str(e)}"


class PostgreSQLQueryTool:
    """PostgreSQL专用查询工具"""

    def __init__(self):
        self.executor = PostgreQueryExecutor(
            Postgre_config['host'],
            Postgre_config['user'],
            Postgre_config['password'],
            Postgre_config['database']
        )

    def run(self, query: str) -> str:
        """执行PostgreSQL查询"""
        try:
            print(f"🟢 执行PostgreSQL查询: {query}")
            result = self.executor.execute_query(query)

            if not result:
                return "PostgreSQL查询未返回结果"

            # 格式化结果
            formatted_result = "PostgreSQL查询结果:\n"
            for i, row in enumerate(result[:10], 1):  # 限制显示前10条
                formatted_result += f"{i}. {row}\n"

            if len(result) > 10:
                formatted_result += f"... 还有 {len(result) - 10} 条记录\n"

            formatted_result += f"\n总计: {len(result)} 条记录"
            return formatted_result

        except Exception as e:
            return f"PostgreSQL查询错误: {str(e)}"


def create_react_agent_system():
    """创建基于ReAct Agent的肠道微生物查询系统"""

    # 初始化工具
    db_query_tool = DatabaseQueryTool(model)
    neo4j_tool = Neo4jQueryTool()
    mysql_newgut_tool = MySQLQueryTool('newgutmgene')
    mysql_disorder_tool = MySQLQueryTool('gutmdisorder')
    postgresql_tool = PostgreSQLQueryTool()

    # 逻辑推理工具
    llm_prompt = PromptTemplate(
        input_variables=["input"],
        template='''
        你是一个专业的肠道微生物研究助手，擅长分析生物学问题并提供科学解释。
        对于输入的问题，你可以进行逻辑推理和科学分析。
        如果问题涉及数据查询，建议使用相应的数据库工具。

        问题: {input}

        请提供你的分析和回答：
        '''
    )
    llm_chain = LLMChain(llm=model, prompt=llm_prompt)

    # 定义Agent提示模板
    prompt = PromptTemplate(
        input_variables=['agent_scratchpad', 'input', 'chat_history', 'tool_names', 'tools'],
        template="""
你是一个专业的肠道微生物研究助手，擅长处理复杂的生物信息学查询。你可以：

1. **智能查询分解**: 自动将复杂问题分解为子问题，跨多个数据库进行查询
2. **多数据库整合**: 整合Neo4j图数据库、MySQL关系数据库和PostgreSQL数据库的查询结果
3. **科学分析**: 对查询结果进行生物学意义的解释和分析

**可用工具说明**:
- **智能数据库查询**: 自动分解复杂问题，跨库查询并整合结果
- **Neo4j查询**: 专门查询微生物-饲料效率关系、关联分析
- **MySQL(newgutmgene)**: 基因表达、微生物-基因交互数据
- **MySQL(gutmdisorder)**: 食物、药物对微生物影响数据  
- **PostgreSQL**: KEGG代谢通路、基因功能注释数据
- **逻辑推理**: 科学分析和解释

**处理策略**:
- 对于复杂的生物学问题，优先使用"智能数据库查询"工具
- 对于特定数据库的简单查询，可直接使用对应的数据库工具
- 对于需要科学解释的问题，使用逻辑推理工具
- 查询失败超过3次时，停止重试并报告结果
- 生成最终答案时，列出所有相关结果，不使用"等"、"多个"等省略词汇

你可以使用如下工具：
{tools}

回答问题时使用以下格式：

Question: 现在要回答的问题

Thought: 我需要思考如何解决这个问题，应该使用哪个工具。

Action: 所采取的行动，需要是下面其中之一[{tool_names}]

Action Input: 行动的输入

Observation: 行动的输出

(... 以上 Thought/Action/Action Input/Observation 的过程将重复执行N遍)

Thought: 我已经获得了足够的信息来回答这个问题。

Final Answer: 对原始问题的最终完整答案

开始！

{chat_history}

Question: {input}

Thought: {agent_scratchpad}
"""
    )

    # 创建工具列表
    tools = [
        Tool(
            name='智能数据库查询',
            func=db_query_tool.run,
            description='''
            智能数据库查询工具：适用于复杂的肠道微生物相关问题。能够：
            - 自动分解复杂问题为子查询
            - 跨Neo4j、MySQL、PostgreSQL多数据库查询
            - 智能选择最适合的数据库
            - 整合查询结果并生成分析报告

            适用于：微生物与饲料效率关系、基因调控、代谢通路、食物药物影响等复合查询
            '''
        ),
        Tool(
            name='逻辑推理工具',
            func=llm_chain.run,
            description='用于科学分析、逻辑推理、生物学解释，以及普通对话。不用于数据库查询。'
        ),
        Tool(
            name="Neo4j数据库查询",
            func=neo4j_tool.run,
            description='''
            Neo4j图数据库查询工具：
            - 微生物与饲料效率的关联关系
            - 显著性分析(pvalue、log2_ratio)
            - 微生物间的相互作用网络

            节点类型：MicrobiotaName, FE, GeneName, MetabolitesName
            关系类型：significantly_associated, increase, upregulate, downregulate, produce
            '''
        ),
        Tool(
            name="MySQL(newgutmgene)查询",
            func=mysql_newgut_tool.run,
            description='''
            MySQL(newgutmgene)数据库查询工具：
            - 基因表达数据
            - 微生物对基因表达的调控
            - 代谢物生成关系

            主要表：gene, metabolite, gut_microbiota_gene_change_results, metabolite_gene_change_results
            '''
        ),
        Tool(
            name="MySQL(gutmdisorder)查询",
            func=mysql_disorder_tool.run,
            description='''
            MySQL(gutmdisorder)数据库查询工具：
            - 食物对微生物影响数据
            - 药物对微生物影响数据
            - 疾病与微生物关系

            主要表：food_gut_microbiota_change_results, drug_gut_microbiota_change_results
            '''
        ),
        Tool(
            name="PostgreSQL查询",
            func=postgresql_tool.run,
            description='''
            PostgreSQL数据库查询工具：
            - KEGG代谢通路信息
            - 基因功能注释
            - 基因与通路映射关系

            主要表：kegg (包含gene_symbol, pathway, network, brite字段)
            '''
        )
    ]

    # 创建agent
    agent = create_react_agent(model, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10  # 限制最大迭代次数
    )

    return agent_executor


def run_react_agent(input_item: str, chat_history: List[str]) -> str:
    """运行ReAct Agent"""
    agent_executor = create_react_agent_system()

    # 格式化聊天历史
    formatted_history = "\n".join(chat_history) if chat_history else ""

    try:
        response = agent_executor.invoke({
            "input": input_item,
            "chat_history": formatted_history
        })

        # 更新聊天历史
        chat_history.append(f"人类：{input_item}")
        chat_history.append(f"助手：{response['output']}")

        return response['output']

    except Exception as e:
        error_msg = f"系统错误：{str(e)}"
        print(f"Error executing agent: {e}")
        chat_history.append(f"人类：{input_item}")
        chat_history.append(f"助手：{error_msg}")
        return error_msg


def main():
    """主函数 - 测试ReAct Agent系统"""
    print("🧬 肠道微生物智能查询系统")
    print("基于ReAct Agent的多数据库整合查询")
    print("=" * 60)

    # 测试问题
    test_questions = [
        "（genera）Dorea，Eubacterium，Bacteroides中哪些微生物群对生猪饲养效率是显著相关的？哪些基因的表达能够减少这些微生物群的数量？这些基因的代谢通路有哪些？",
        "使用药物Metformin导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够增加这些微生物群的数量？这些基因的代谢通路是什么？",
        "给\"sea buckthorn protein\"食物导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够减少这些微生物的数量？",
    ]

    chat_history = []

    # 测试第一个问题
    question = test_questions[0]
    print(f"\n🔍 测试问题: {question}")
    print("-" * 60)

    answer = run_react_agent(question, chat_history)
    print(f"\n📋 最终答案:\n{answer}")



if __name__ == "__main__":
    main()