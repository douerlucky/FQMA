import re
from langchain_core.prompts import PromptTemplate
from typing import List, Dict, Any
import config
import importlib
import samples_exp.prompt_grad

class ResultAggregation:
    def __init__(self, llm):
        self.llm = llm
        # 🔥 修复：每次__init__动态加载，不用模块级缓存变量
        try:
            prompts_module = importlib.import_module(f"samples_exp.{config.CURRENT_DATASET}.prompts_rules")
            _,_,_,_,_,cur_prompt = samples_exp.prompt_grad.get_templates()
            template = cur_prompt
        except (ImportError, AttributeError) as e:
            print(f"⚠️ 无法导入ResultAggregation_template: {e}")
            template = None
        self.aggregation_prompt = PromptTemplate(
            input_variables=["sub_question", "converted_queries", "query_results"],
            template=template
        )

    def extract_return_fields(self, query_list: List[str], results: Dict[int, List[Any]] = None) -> Dict[
        int, List[str]]:
        result = {}
        for idx, query in enumerate(query_list, 1):
            fields = []
            query = query.strip()

            if "RETURN" in query.upper():
                fields = self._extract_neo4j_fields(query)
            elif "SELECT" in query.upper():
                fields = self._extract_sql_fields(query)

            # 用实际结果校正列数
            if results and idx in results:
                actual_data = results[idx]
                if actual_data:
                    first_row = actual_data[0]
                    actual_col_count = len(first_row) if isinstance(first_row, (list, tuple)) else 1
                    # 字段数不够时补充
                    while len(fields) < actual_col_count:
                        fields.append(f"column_{len(fields) + 1}")
                    # 字段数过多时截断
                    fields = fields[:actual_col_count]

            if not fields:
                fields = ["column_1", "column_2"]

            result[idx] = fields
            print(f"查询 {idx} 提取的字段: {fields}")

        return result

    def _extract_neo4j_fields(self, query: str) -> List[str]:
        """
        提取Neo4j查询的返回字段
        """
        fields = []

        # 匹配 RETURN ... as alias 的模式
        as_pattern = r'RETURN\s+.*?\s+as\s+(\w+)'
        as_matches = re.findall(as_pattern, query, re.IGNORECASE | re.DOTALL)
        fields.extend(as_matches)

        # 如果没有找到 as 别名，尝试提取属性名
        if not fields:
            # 匹配 RETURN node.property 的模式
            prop_pattern = r'RETURN\s+[\w\.]+\.(\w+)'
            prop_matches = re.findall(prop_pattern, query, re.IGNORECASE)
            fields.extend(prop_matches)

        # 如果还是没有，尝试简单的 RETURN 模式
        if not fields:
            return_pattern = r'RETURN\s+(.*?)(?:$|\s+ORDER|\s+LIMIT)'
            return_match = re.search(return_pattern, query, re.IGNORECASE | re.DOTALL)
            if return_match:
                return_content = return_match.group(1).strip()
                # 简单分割并清理
                items = [item.strip() for item in return_content.split(',')]
                for item in items:
                    # 提取最后的单词作为字段名
                    if '.' in item:
                        field_name = item.split('.')[-1]
                    else:
                        field_name = item
                    fields.append(field_name)

        return fields

    def _extract_sql_fields(self, query: str) -> List[str]:
        """
        提取SQL查询的字段名（改进版）
        """
        fields = []

        # 改进的SELECT字段提取正则表达式
        # 匹配 SELECT [DISTINCT] ... FROM
        select_pattern = r'SELECT\s+(?:DISTINCT\s+)?(.*?)\s+FROM'
        select_match = re.search(select_pattern, query, re.IGNORECASE | re.DOTALL)

        if select_match:
            select_content = select_match.group(1).strip()
            print(f"提取的SELECT内容: {select_content}")

            # 分割字段（考虑逗号分隔）
            field_items = [item.strip() for item in select_content.split(',')]

            for item in field_items:
                item = item.strip()
                if not item:
                    continue

                # 处理 AS 别名
                if ' as ' in item.lower():
                    # 提取 AS 后面的别名
                    alias = item.lower().split(' as ')[-1].strip()
                    fields.append(alias)
                elif '.' in item:
                    # 提取表前缀后的字段名（如 hecrbm.gene_symbol -> gene_symbol）
                    field_name = item.split('.')[-1].strip()
                    fields.append(field_name)
                else:
                    # 直接使用字段名
                    fields.append(item)

        return fields

    def table_generate(self, queries: List[str], results: Dict[int, List[Any]]) -> str:
        detected_attr = self.extract_return_fields(queries, results)  # 传入results
        tables = ""
        for key, field_names in detected_attr.items():
            if not field_names:
                continue
            headers = " | ".join(field_names)
            separator = " | ".join(["---"] * len(field_names))
            result_data = results.get(key, [])
            rows = ""
            for row_data in result_data:
                if isinstance(row_data, (list, tuple)):
                    row_values = list(row_data[:len(field_names)])
                    while len(row_values) < len(field_names):
                        row_values.append("")
                    row_str = " | ".join(map(str, row_values))
                else:
                    row_str = str(row_data)
                rows += f"| {row_str} |\n"  # ← 关键修复
            markdown_table = f"### 查询 {key} 的结果\n\n| {headers} |\n| {separator} |\n{rows}\n"
            tables += markdown_table
        return tables

    def generate_explanations(self, sub_question: str, queries: List[str], results: Dict[int, List[Any]]) -> str:
        """
        生成查询结果的整体分析和解释
        """
        # 准备数据
        converted_queries = "\n".join([f"查询 {i + 1}: {query}" for i, query in enumerate(queries)])
        query_results = "\n".join([f"查询 {key} 结果: {results[key]}" for key in results])

        # 使用模板生成提示
        prompt = self.aggregation_prompt.format(
            sub_question=sub_question,
            converted_queries=converted_queries,
            query_results=query_results
        )

        # 调用模型生成解释
        result = self.llm.invoke(prompt)
        return result.content

    def process(self, sub_question: str, queries: List[str], results: Dict[int, List[Any]]) -> tuple:
        """
        主方法：生成表格并让模型生成整体的分析和建议

        返回:
            tuple: (tables, explanation)
        """
        print("=== 开始处理结果聚合 ===")
        print(f"子问题: {sub_question}")
        print(f"查询数量: {len(queries)}")
        print(f"结果数量: {len(results)}")

        # 生成所有表格
        tables = self.table_generate(queries, results)

        # 生成整体分析和建议
        explanation = self.generate_explanations(sub_question, queries, results)

        print("=== 结果聚合完成 ===")

        return tables, explanation


def main():
    """测试修复后的结果聚合器"""

    # 测试数据
    test_queries = [
        """SELECT DISTINCT hecrbm.gene_symbol, hecrbm.relationship
FROM relationship.has_expression_change_results_by_microbiota hecrbm
JOIN newgutmgene.gut_microbiota_gene_change_results gmgcr 
ON hecrbm.`index` = gmgcr.`index`
WHERE gmgcr.Alteration = 'increase' AND hecrbm.relationship IN ('Cellulosilyticum', 'Leeia', 'Subdoligranulu', 'Rothia', 'Methanobrevibacter', 'Bacteroides', 'Lactobacillus', 'Oscillibacter', 'Ruminococcaceae')""",

        """SELECT gene_symbol, pathway
FROM kegg
WHERE gene_symbol IN ('IL22', 'MAPK14', 'Tjp1', 'Arg1')""",

        """MATCH (microbiota:MicrobiotaName)-[:increase]->(feed_efficiency:FE)
RETURN microbiota.name as microbiota_name"""
    ]

    test_results = {
        1: [
            ['IL22', 'Lactobacillus'],
            ['MAPK14', 'Lactobacillus'],
            ['BAX', 'Bacteroides'],
            ['CASP3', 'Bacteroides'],
            ['Tjp1', 'Lactobacillus'],
            ['Nr1h4', 'Bacteroides'],
            ['Fgf15', 'Bacteroides'],
            ['Fgfr4', 'Bacteroides'],
            ['Fas', 'Bacteroides'],
            ['Arg1', 'Lactobacillus']
        ],
        2: [
            ['IL22', 'hsa04060 Cytokine-cytokine receptor interaction'],
            ['MAPK14', 'hsa04010 MAPK signaling pathway'],
            ['Tjp1', 'mmu04530 Tight junction'],
            ['Arg1', 'mmu00330 Arginine and proline metabolism']
        ],
        3: [
            ['Lactobacillus'],
            ['Bacteroides'],
            ['Bifidobacterium']
        ]
    }

    # 创建修复后的聚合器
    aggregator = ResultAggregation(config.model)

    # 测试字段提取
    print("=== 测试字段提取 ===")
    extracted_fields = aggregator.extract_return_fields(test_queries)
    for query_id, fields in extracted_fields.items():
        print(f"查询 {query_id} 的字段: {fields}")

    print("\n=== 测试表格生成 ===")

    # 处理结果
    sub_question = "哪些基因的表达能够增加特定微生物的数量，这些基因参与哪些通路？"
    tables, explanation = aggregator.process(sub_question, test_queries, test_results)

    print("\n生成的表格:")
    print(tables)

    print("\n生成的解释:")
    print(explanation)


if __name__ == '__main__':
    main()