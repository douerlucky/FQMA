#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QueryAdaptive.py - 零硬编码版本
所有数据库选择决策完全由LLM根据TTL映射信息做出
不使用任何评分规则或硬编码逻辑！
"""

from langchain.prompts import PromptTemplate
from agents.DatabaseExecutor import Neo4jQueryExecutor, MySQLQueryExecutor, PostgreQueryExecutor
from Tools.SPARQL2MySQL import SparqlToMySQLConverter
from Tools.SPARQL2Neo4j import SparqlToCypherConverter
from Tools.SPARQL2PostgreSQL import SparqlToPostgreSQLConverter

# 导入配置
from config import (
    Neo4j_config, MySQL_config, Postgre_config, GutMDisorder_config,
    TTL_FILES, ENABLED_DATABASES, CURRENT_DATASET
)

import re
import importlib
from typing import List, Dict, Tuple, Any


# 🔥 动态导入数据库选择提示词模板（根据当前数据集）
try:
    prompts_module = importlib.import_module(f"samples_exp.{CURRENT_DATASET}.prompts_rules")
    if hasattr(prompts_module, 'SubQuerySchedulerRules'):
        DATABASE_SELECTION_PROMPT_TEMPLATE = prompts_module.SubQuerySchedulerRules
        print(f"✅ 已加载 {CURRENT_DATASET} 数据集的数据库选择规则")
    else:
        # 使用默认模板
        DATABASE_SELECTION_PROMPT_TEMPLATE = None
        print(f"⚠️ {CURRENT_DATASET} 数据集未提供SubQuerySchedulerRules，使用默认模板")
except (ImportError, AttributeError) as e:
    print(f"⚠️ 无法导入数据集特定的提示词模板: {e}，使用默认模板")
    DATABASE_SELECTION_PROMPT_TEMPLATE = None


# ============================================================
# TTL内容提取器 - 从TTL文件提取完整映射信息供LLM使用
# ============================================================
class TTLContentExtractor:
    """
    从TTL文件中提取完整的映射信息，格式化为LLM可理解的文本

    核心原则：只提取信息，不做任何决策！
    所有决策由LLM完成。
    """

    def __init__(self, ttl_files: Dict[str, str]):
        """
        初始化提取器

        Args:
            ttl_files: {数据库名: TTL文件路径}
        """
        self.ttl_files = ttl_files
        self.ttl_contents = {}  # 存储每个数据库的TTL解析结果

        # 解析所有TTL文件
        self._parse_all_ttl_files()

    def _parse_all_ttl_files(self):
        """解析所有TTL文件"""
        print("\n" + "=" * 60)
        print("📂 加载TTL映射文件（供LLM决策使用）")
        print("=" * 60)

        for db_name, ttl_path in self.ttl_files.items():
            # 处理可能是列表的情况
            if isinstance(ttl_path, list):
                combined_info = []
                for path in ttl_path:
                    info = self._parse_single_ttl(path, db_name)
                    if info:
                        combined_info.append(info)
                self.ttl_contents[db_name] = "\n\n".join(combined_info)
            else:
                self.ttl_contents[db_name] = self._parse_single_ttl(ttl_path, db_name)

        print("=" * 60 + "\n")

    def _parse_single_ttl(self, ttl_path: str, db_name: str) -> str:
        """
        解析单个TTL文件，提取结构化映射信息

        Returns:
            格式化的映射信息字符串
        """
        try:
            with open(ttl_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取所有映射块的关键信息
            mappings = []

            # 分割映射块
            mapping_sections = re.split(r'\n\s*<#', content)

            for section in mapping_sections:
                if not section.strip():
                    continue

                mapping_info = self._extract_mapping_info(section)
                if mapping_info:
                    mappings.append(mapping_info)

            print(f"  ✅ {db_name}: 加载了 {len(mappings)} 个映射")

            return self._format_mappings_for_llm(db_name, mappings)

        except Exception as e:
            print(f"  ❌ {db_name}: 解析失败 - {e}")
            return ""

    def _extract_mapping_info(self, section: str) -> Dict:
        """从映射块中提取关键信息"""
        info = {}

        # 提取映射名称
        name_match = re.match(r'(\w+)>', section)
        if name_match:
            info['name'] = name_match.group(1)

        # 提取关联的类（rr:class）
        class_match = re.search(r'rr:class\s+(\w+):(\w+)', section)
        if class_match:
            info['class'] = class_match.group(2)

        # 提取表名（rr:tableName）
        table_match = re.search(r'rr:tableName\s+"?([^"\s\]]+)"?', section)
        if table_match:
            info['table'] = table_match.group(1)

        # 提取SQL查询（rr:sqlQuery）
        sql_match = re.search(r'rr:sqlQuery\s*"""(.*?)"""', section, re.DOTALL)
        if sql_match:
            info['sql'] = sql_match.group(1).strip()

        # 提取所有谓词（rr:predicate）
        predicates = []
        predicate_blocks = re.findall(
            r'rr:predicateObjectMap\s*\[(.*?)\]',
            section,
            re.DOTALL
        )

        for block in predicate_blocks:
            pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', block)
            if pred_match:
                pred_name = pred_match.group(2)

                # 判断是数据属性还是对象属性
                is_object_prop = 'rr:termType rr:IRI' in block or 'rr:template' in block

                # 提取列名或模板
                column_match = re.search(r'rr:column\s+"?([^"\s\]]+)"?', block)
                template_match = re.search(r'rr:template\s+"([^"]+)"', block)

                pred_info = {
                    'name': pred_name,
                    'type': 'ObjectProperty' if is_object_prop else 'DatatypeProperty'
                }

                if column_match:
                    pred_info['column'] = column_match.group(1)
                if template_match:
                    pred_info['template'] = template_match.group(1)

                predicates.append(pred_info)

        if predicates:
            info['predicates'] = predicates

        return info if info else None

    def _format_mappings_for_llm(self, db_name: str, mappings: List[Dict]) -> str:
        """将映射信息格式化为LLM可理解的文本"""
        lines = []
        lines.append(f"### {db_name} 数据库映射")
        lines.append("")

        # 按类分组
        classes = {}
        relationships = []

        for mapping in mappings:
            if 'class' in mapping:
                class_name = mapping['class']
                if class_name not in classes:
                    classes[class_name] = {'tables': [], 'predicates': []}

                if 'table' in mapping:
                    classes[class_name]['tables'].append(mapping['table'])
                if 'predicates' in mapping:
                    classes[class_name]['predicates'].extend(mapping['predicates'])
            else:
                # 没有class的是纯关系映射
                if 'predicates' in mapping:
                    relationships.extend(mapping['predicates'])

        # 输出实体类
        if classes:
            lines.append("**实体类及其属性：**")
            for class_name, info in classes.items():
                tables = ', '.join(set(info['tables'])) if info['tables'] else '无'
                lines.append(f"- **{class_name}** (表: {tables})")

                # 数据属性
                data_props = [p for p in info['predicates'] if p['type'] == 'DatatypeProperty']
                if data_props:
                    prop_names = ', '.join(set(p['name'] for p in data_props))
                    lines.append(f"  - 数据属性: {prop_names}")

                # 对象属性
                obj_props = [p for p in info['predicates'] if p['type'] == 'ObjectProperty']
                if obj_props:
                    prop_names = ', '.join(set(p['name'] for p in obj_props))
                    lines.append(f"  - 关系属性: {prop_names}")

        # 输出纯关系
        if relationships:
            lines.append("")
            lines.append("**关系映射：**")
            for rel in relationships:
                lines.append(f"- {rel['name']} ({rel['type']})")

        lines.append("")
        return '\n'.join(lines)

    def get_all_ttl_info_for_llm(self) -> str:
        """
        获取所有数据库的TTL映射信息，供LLM决策使用

        这是核心方法！将所有TTL信息整合为LLM提示词的一部分
        """
        result = []
        result.append("=" * 60)
        result.append("## 数据库映射信息（来自TTL文件）")
        result.append("=" * 60)
        result.append("")

        for db_name, info in self.ttl_contents.items():
            if info:
                result.append(info)

        return '\n'.join(result)

    def get_ttl_info_for_database(self, db_name: str) -> str:
        """获取特定数据库的TTL映射信息"""
        return self.ttl_contents.get(db_name, "")


# ============================================================
# 数据库选择提示词模板 - 使用数据集特定的规则或默认规则
# ============================================================
if DATABASE_SELECTION_PROMPT_TEMPLATE:
    # 使用数据集特定的提示词模板
    DATABASE_SELECTION_PROMPT = DATABASE_SELECTION_PROMPT_TEMPLATE
else:
    # 默认模板（后备方案）
    DATABASE_SELECTION_PROMPT = """你是数据库路由专家。请根据SPARQL查询和TTL映射信息，选择最合适的数据库。

## 输入信息

### 自然语言问题
{question}

### SPARQL查询
```sparql
{sparql_query}
```

### 可用数据库及其映射信息
{ttl_info}

## 决策规则

1. **分析SPARQL中使用的谓词（属性/关系）**
   - 识别所有 conf:xxx 或 ont:xxx 形式的谓词
   - 注意：同一个谓词可能在多个数据库中都有映射

2. **查看TTL映射信息**
   - 每个数据库的映射告诉你它能提供什么数据
   - 数据属性(DatatypeProperty)：返回具体值（如名字、文本等）
   - 关系属性(ObjectProperty)：表示实体间的关系

3. **决策原则**
   - 如果SPARQL需要特定数据库独有的属性 → 选择该数据库
   - 如果需要详细文本内容 → 优先考虑专门存储文本的数据库
   - 如果是简单的关系遍历 → 优先考虑图数据库
   - 如果需要聚合操作（COUNT/GROUP BY）→ 优先考虑关系型数据库

## 输出格式

只输出数据库名称，不要其他内容：
Neo4j / MySQL / PostgreSQL

你的选择："""


# ============================================================
# SubQueryScheduler - 零硬编码版本，完全由LLM决策
# ============================================================
class SubQueryScheduler:
    """
    子查询数据库调度器 - 零硬编码版本

    核心原则：所有数据库选择决策完全由LLM做出！
    本类只负责：
    1. 加载TTL映射信息
    2. 构造提示词
    3. 调用LLM获取决策
    """

    def __init__(self, llm):
        self.llm = llm

        # 加载TTL映射信息
        self.ttl_extractor = TTLContentExtractor(TTL_FILES)

        # 构造提示词模板
        self.selection_prompt = PromptTemplate(
            input_variables=["question", "sparql_query", "ttl_info"],
            template=DATABASE_SELECTION_PROMPT
        )

    def select_database(self, sparql_query: str, question: str) -> str:
        """
        让LLM根据TTL映射信息选择最合适的数据库

        Args:
            sparql_query: SPARQL查询语句
            question: 原始自然语言问题

        Returns:
            数据库名称: "Neo4j" / "MySQL" / "PostgreSQL"
        """
        print(f"\n=== 数据库选择（LLM决策）===")
        print(f"子问题: {question[:80]}...")
        print(f"SPARQL: {sparql_query[:100]}...")

        # 获取所有TTL映射信息
        ttl_info = self.ttl_extractor.get_all_ttl_info_for_llm()

        # 构造提示词
        prompt = self.selection_prompt.format(
            question=question,
            sparql_query=sparql_query,
            ttl_info=ttl_info
        )

        # 调用LLM获取决策
        result = self.llm.invoke(prompt)

        # 解析LLM返回的数据库名称
        selected_db = self._parse_database_selection(result.content)

        print(f"✅ LLM选择数据库: {selected_db}")
        print(f"=== 数据库选择完成 ===\n")

        return selected_db

    def _parse_database_selection(self, llm_response: str) -> str:
        """解析LLM返回的数据库选择"""
        response = llm_response.strip().lower()

        # 标准化数据库名称
        if 'neo4j' in response:
            return 'Neo4j'
        elif 'mysql' in response:
            # 检查是否是GMQA数据集的特殊MySQL库
            if CURRENT_DATASET == "GMQA":
                if 'gutmdisorder' in response or 'disorder' in response:
                    return 'MySQL(gutmdisorder)'
                else:
                    return 'MySQL(newgutmgene)'
            return 'MySQL'
        elif 'postgre' in response or 'postgresql' in response:
            return 'PostgreSQL'
        else:
            # 默认返回第一个可用数据库
            print(f"⚠️ 无法解析LLM响应: {llm_response}")
            return ENABLED_DATABASES[0] if ENABLED_DATABASES else 'MySQL'


# ============================================================
# SubQueryExecutor - 查询执行器（保持不变）
# ============================================================
class SubQueryExecutor:
    """
    子查询执行器
    负责：
    1. 将SPARQL转换为目标数据库查询语言
    2. 执行查询
    3. 处理占位符替换
    """

    def __init__(self, llm):
        self.llm = llm
        self.placeholder_pattern = r'<<SUBQUERY_(\d+)>>'

    def convert_to_target_query(self, sparql_query: str, sel_db: str) -> str:
        """将SPARQL转换为目标数据库的查询语言"""
        print(f"\n=== 转换查询到 {sel_db} (数据集: {CURRENT_DATASET}) ===")
        sel_db = sel_db.strip()

        try:
            if sel_db == 'Neo4j':
                converter = SparqlToCypherConverter(TTL_FILES['neo4j'])
                cypher_query = converter.convert(sparql_query)
                print(f"✅ 转换成功")
                print(f"转换后的Cypher: {cypher_query}")
                return cypher_query

            elif sel_db == 'MySQL(newgutmgene)' or (sel_db == 'MySQL' and CURRENT_DATASET == "GMQA"):
                ttl_files = TTL_FILES['mysql_main'] if isinstance(TTL_FILES['mysql_main'], list) else [
                    TTL_FILES['mysql_main']]
                converter = SparqlToMySQLConverter(ttl_files)
                mysql_query = converter.convert_sparql_to_mysql(sparql_query)
                print(f"✅ 转换成功")
                print(f"转换后的MySQL: {mysql_query}")
                return mysql_query

            elif sel_db == 'MySQL(gutmdisorder)':
                ttl_files = TTL_FILES['mysql_disorder'] if isinstance(TTL_FILES['mysql_disorder'], list) else [
                    TTL_FILES['mysql_disorder']]
                converter = SparqlToMySQLConverter(ttl_files)
                mysql_query = converter.convert_sparql_to_mysql(sparql_query)
                print(f"✅ 转换成功")
                print(f"转换后的MySQL(gutmdisorder): {mysql_query}")
                return mysql_query

            elif sel_db == 'MySQL' and CURRENT_DATASET != "GMQA":
                ttl_files = TTL_FILES['mysql_main'] if isinstance(TTL_FILES['mysql_main'], list) else [
                    TTL_FILES['mysql_main']]
                converter = SparqlToMySQLConverter(ttl_files)
                mysql_query = converter.convert_sparql_to_mysql(sparql_query)
                print(f"✅ 转换成功")
                print(f"转换后的MySQL: {mysql_query}")
                return mysql_query

            elif sel_db == 'PostgreSQL':
                converter = SparqlToPostgreSQLConverter(TTL_FILES['postgresql'])
                postgresql_query = converter.convert(sparql_query)
                print(f"✅ 转换成功")
                print(f"转换后的PostgreSQL: {postgresql_query}")
                return postgresql_query

            else:
                print(f"❌ 无法识别的数据库类型: '{sel_db}'")
                print(f"当前数据集({CURRENT_DATASET})支持的数据库类型: {ENABLED_DATABASES}")
                return ""

        except Exception as e:
            print(f"❌ 转换查询时出错: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def execute_in_database(self, converted_query: str, sel_db: str) -> List:
        """在指定数据库中执行查询"""
        print(f"\n=== 执行数据库查询 (数据集: {CURRENT_DATASET}) ===")
        print(f"数据库: {sel_db}")
        print(f"查询语句: {converted_query}")

        if not converted_query or converted_query.strip() == "":
            print("转换后的查询为空，无法执行")
            return []

        try:
            if sel_db == 'Neo4j':
                executor = Neo4jQueryExecutor(
                    Neo4j_config['uri'],
                    Neo4j_config['user'],
                    Neo4j_config['password']
                )
                result = executor.execute_query(converted_query)
                print(f"Neo4j查询结果: {result}")
                return result

            elif sel_db == 'MySQL(newgutmgene)' or (sel_db == 'MySQL' and CURRENT_DATASET == "GMQA"):
                executor = MySQLQueryExecutor(
                    MySQL_config['host'],
                    MySQL_config['user'],
                    MySQL_config['password'],
                    MySQL_config['database']
                )
                result = executor.execute_query(converted_query)
                print(f"MySQL查询结果: {result}")
                return result

            elif sel_db == 'MySQL(gutmdisorder)':
                if GutMDisorder_config is None:
                    print(f"错误: 当前数据集({CURRENT_DATASET})不支持MySQL(gutmdisorder)")
                    return []
                executor = MySQLQueryExecutor(
                    GutMDisorder_config['host'],
                    GutMDisorder_config['user'],
                    GutMDisorder_config['password'],
                    GutMDisorder_config['database']
                )
                result = executor.execute_query(converted_query)
                print(f"MySQL(gutmdisorder)查询结果: {result}")
                return result

            elif sel_db == 'MySQL' and CURRENT_DATASET != "GMQA":
                executor = MySQLQueryExecutor(
                    MySQL_config['host'],
                    MySQL_config['user'],
                    MySQL_config['password'],
                    MySQL_config['database']
                )
                result = executor.execute_query(converted_query)
                print(f"MySQL查询结果: {result}")
                return result

            elif sel_db == 'PostgreSQL':
                executor = PostgreQueryExecutor(
                    Postgre_config['host'],
                    Postgre_config['user'],
                    Postgre_config['password'],
                    Postgre_config['database']
                )
                result = executor.execute_query(converted_query)
                print(f"PostgreSQL查询结果: {result}")
                return result

            else:
                print(f"无法识别的数据库类型: '{sel_db}'")
                return []

        except Exception as e:
            print(f"执行数据库查询时出错: {e}")
            import traceback
            traceback.print_exc()
            return []

    def has_placeholder(self, query: str) -> bool:
        """判断查询是否包含占位符"""
        has_placeholder = bool(re.search(self.placeholder_pattern, query))
        print(f"\n=== 占位符检查 ===")
        print(f"查询语句: {query}")
        print(f"包含占位符: {has_placeholder}")
        if has_placeholder:
            placeholders = re.findall(self.placeholder_pattern, query)
            print(f"找到的占位符: {placeholders}")
        print(f"=== 检查完成 ===\n")
        return has_placeholder

    def extract_placeholders(self, query: str) -> List[Tuple[str, int]]:
        """提取查询中的所有占位符"""
        matches = re.finditer(self.placeholder_pattern, query)
        placeholders = []

        for match in matches:
            placeholder_text = match.group(0)
            subquery_num = int(match.group(1))
            placeholders.append((placeholder_text, subquery_num))

        print(f"提取到的占位符: {placeholders}")
        return placeholders

    def format_subquery_results(self, results: List[List[Any]]) -> str:
        """将子查询结果格式化为SQL IN子句可用的格式"""
        print(f"\n=== 格式化子查询结果 ===")
        print(f"原始结果: {results}")

        values = [result[0] for result in results if result]
        print(f"提取的值: {values}")

        formatted_values = []
        for value in values:
            if isinstance(value, str):
                escaped_value = value.replace("'", "''")
                formatted_values.append(f"'{escaped_value}'")
            elif value is None:
                formatted_values.append('NULL')
            else:
                formatted_values.append(str(value))

        result = ', '.join(formatted_values)
        print(f"格式化后的结果: {result}")
        print(f"=== 格式化完成 ===\n")
        return result

    def replace_placeholders(self, query: str, subquery_results: Dict[int, List[List[Any]]]) -> str:
        """替换查询中的所有占位符为实际的子查询结果"""
        print(f"\n=== 开始替换占位符 ===")
        print(f"原始查询: {query}")
        print(f"子查询结果字典: {subquery_results}")

        if not self.has_placeholder(query):
            print("查询中没有占位符，直接返回原查询")
            return query

        result_query = query
        placeholders = self.extract_placeholders(query)

        for placeholder_text, subquery_num in placeholders:
            print(f"\n处理占位符: {placeholder_text} (子查询编号: {subquery_num})")

            if subquery_num in subquery_results:
                results = subquery_results[subquery_num]
                print(f"找到子查询 {subquery_num} 的结果: {results}")

                if len(results) == 0:
                    print("结果为空，添加空字符串")
                    results.append([""])

                formatted_results = self.format_subquery_results(results)
                print(f"格式化后的结果: {formatted_results}")

                old_query = result_query
                result_query = result_query.replace(placeholder_text, formatted_results)
                print(f"替换前: {old_query}")
                print(f"替换后: {result_query}")
            else:
                print(f"警告: 未找到子查询 {subquery_num} 的结果")

        print(f"=== 占位符替换完成 ===")
        print(f"最终查询: {result_query}")
        print(f"=== 替换结束 ===\n")
        return result_query


# ============================================================
# 测试代码
# ============================================================
if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("QueryAdaptive 零硬编码版本测试")
    print("=" * 80)

    # 测试TTL内容提取
    print("\n📂 测试TTL内容提取...")
    extractor = TTLContentExtractor(TTL_FILES)

    print("\n📝 生成的LLM提示词信息：")
    print("-" * 60)
    ttl_info = extractor.get_all_ttl_info_for_llm()
    print(ttl_info[:2000])  # 只打印前2000字符
    if len(ttl_info) > 2000:
        print(f"\n... (共 {len(ttl_info)} 字符)")
    print("-" * 60)

    print("\n✅ 零硬编码版本测试完成！")
    print("所有数据库选择将完全由LLM根据TTL映射信息决策。")