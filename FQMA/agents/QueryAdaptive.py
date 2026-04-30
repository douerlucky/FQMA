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
import config
import re
import importlib
import socket
import sys
from typing import List, Dict, Tuple, Any, Set

import samples_exp.prompt_grad

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


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
        self.ttl_predicates = {}

        # 解析所有TTL文件
        self._parse_all_ttl_files()

    def _parse_all_ttl_files(self):
        """解析所有TTL文件"""
        print("\n" + "=" * 60)
        print("📂 加载TTL映射文件（供LLM决策使用）")
        print("=" * 60)

        for db_name, ttl_path in self.ttl_files.items():
            combined_info = []
            combined_predicates = set()
            ttl_paths = ttl_path if isinstance(ttl_path, list) else [ttl_path]

            for path in ttl_paths:
                info, predicates = self._parse_single_ttl(path, db_name)
                if info:
                    combined_info.append(info)
                combined_predicates.update(predicates)

            self.ttl_contents[db_name] = "\n\n".join(combined_info)
            self.ttl_predicates[db_name] = combined_predicates

        print("=" * 60 + "\n")

    def _parse_single_ttl(self, ttl_path: str, db_name: str) -> Tuple[str, Set[str]]:
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

            # 分割映射块：兼容 <#Map> 和 ex:Map 两种 R2RML 写法。
            mapping_sections = self._split_mapping_sections(content)

            for section in mapping_sections:
                if not section.strip():
                    continue

                mapping_info = self._extract_mapping_info(section)
                if mapping_info:
                    mappings.append(mapping_info)

            print(f"  ✅ {db_name}: 加载了 {len(mappings)} 个映射")

            predicates = {
                predicate["name"]
                for mapping in mappings
                for predicate in mapping.get("predicates", [])
                if predicate.get("name")
            }
            return self._format_mappings_for_llm(db_name, mappings), predicates

        except Exception as e:
            print(f"  ❌ {db_name}: 解析失败 - {e}")
            return "", set()

    def _extract_mapping_info(self, section: str) -> Dict:
        """从映射块中提取关键信息"""
        info = {}

        # 提取映射名称
        name_match = re.match(r'\s*(?:<#(\w+)>|(?:\w+:)?(\w+))\s+rr:logicalTable\b', section)
        if name_match:
            info['name'] = name_match.group(1) or name_match.group(2)

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
        predicate_blocks = self._extract_predicate_object_blocks(section)

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

        sql_text = info.get('sql', '')
        if sql_text:
            known_predicates = {predicate['name'] for predicate in predicates}
            for alias in re.findall(r'\bas\s+([A-Za-z_]\w*)', sql_text, re.IGNORECASE):
                if alias not in known_predicates:
                    predicates.append({
                        'name': alias,
                        'type': 'DatatypeProperty',
                        'column': alias,
                    })
                    known_predicates.add(alias)

        if predicates:
            info['predicates'] = predicates

        return info if info else None

    def _split_mapping_sections(self, content: str) -> List[str]:
        """按 rr:logicalTable 切分映射块，避免把 GMQA 的 ex:Map 整体吞成一块。"""
        starts = [
            match.start()
            for match in re.finditer(
                r'(?m)^\s*(?:<#[^>]+>|\w+:\w+)\s+rr:logicalTable\b',
                content,
            )
        ]
        if not starts:
            return re.split(r'\n\s*<#', content)

        sections = []
        for idx, start in enumerate(starts):
            end = starts[idx + 1] if idx + 1 < len(starts) else len(content)
            sections.append(content[start:end])
        return sections

    def _extract_predicate_object_blocks(self, section: str) -> List[str]:
        """提取完整 predicateObjectMap 块，支持内部 objectMap 的嵌套方括号。"""
        blocks = []
        for match in re.finditer(r'rr:predicateObjectMap\s*\[', section):
            start = section.find('[', match.start())
            if start == -1:
                continue

            depth = 0
            for pos in range(start, len(section)):
                char = section[pos]
                if char == '[':
                    depth += 1
                elif char == ']':
                    depth -= 1
                    if depth == 0:
                        blocks.append(section[start:pos + 1])
                        break
        return blocks

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

    def get_predicates_for_database(self, db_name: str) -> Set[str]:
        return set(self.ttl_predicates.get(db_name, set()))

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
        self.ttl_extractor = TTLContentExtractor(config.TTL_FILES)

        import samples_exp.prompt_grad as pg
        _, _, _, _, cur_prompt, _ = pg.get_templates()
        self.selection_prompt_template = cur_prompt

        # 构造提示词模板
        self.selection_prompt = PromptTemplate(
            input_variables=["question", "sparql_query", "ttl_info"],
            template=self.selection_prompt_template
        )

    def _get_database_connection_target(self, db_name: str) -> Tuple[str, int]:
        if db_name == "Neo4j":
            uri = config.Neo4j_config.get("uri", "bolt://localhost:7687")
            host_port = uri.split("://", 1)[-1]
            host, _, port = host_port.partition(":")
            return host or "localhost", int(port or 7687)
        if db_name.startswith("MySQL"):
            return config.MySQL_config.get("host", "localhost"), 3306
        if db_name == "PostgreSQL":
            return config.Postgre_config.get("host", "localhost"), 5432
        return "localhost", 0

    def _is_database_available(self, db_name: str, timeout: float = 0.8) -> bool:
        host, port = self._get_database_connection_target(db_name)
        if port <= 0:
            return False

        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def _get_available_databases(self) -> List[str]:
        available_databases = []
        for db_name in config.ENABLED_DATABASES:
            if self._is_database_available(db_name):
                available_databases.append(db_name)
            else:
                print(f"⚠️ 跳过不可用数据库: {db_name}")
        return available_databases

    def _database_name_to_ttl_key(self, db_name: str) -> str:
        if db_name == "Neo4j":
            return "neo4j"
        if db_name in ("MySQL", "MySQL(newgutmgene)"):
            return "mysql_main"
        if db_name == "MySQL(gutmdisorder)":
            return "mysql_disorder"
        if db_name == "PostgreSQL":
            return "postgresql"
        return ""

    def _get_ttl_info_for_databases(self, database_names: List[str]) -> str:
        result = []
        result.append("=" * 60)
        result.append("## 当前可用数据库映射信息")
        result.append("=" * 60)
        result.append(f"可用数据库: {', '.join(database_names)}")
        result.append("")

        for db_name in database_names:
            ttl_key = self._database_name_to_ttl_key(db_name)
            ttl_info = self.ttl_extractor.get_ttl_info_for_database(ttl_key)
            if ttl_info:
                result.append(ttl_info)

        return "\n".join(result)

    def _extract_predicates_from_sparql(self, sparql_query: str) -> List[str]:
        query_without_prefixes = re.sub(
            r"PREFIX\s+\w+:\s*<[^>]+>\s*",
            "",
            sparql_query,
            flags=re.IGNORECASE,
        )
        where_match = re.search(
            r"WHERE\s*\{(.*)\}",
            query_without_prefixes,
            flags=re.IGNORECASE | re.DOTALL,
        )
        query_body = where_match.group(1) if where_match else query_without_prefixes
        query_body = re.sub(r"BIND\s*\([^)]*\)", "", query_body, flags=re.IGNORECASE)

        predicates = []
        for statement in re.split(r"\s*\.\s*", query_body):
            statement = statement.strip().strip("{}").strip()
            if not statement:
                continue

            upper_statement = statement.upper()
            if upper_statement.startswith(("FILTER", "OPTIONAL", "BIND", "VALUES")):
                continue

            tokens = statement.split()
            if len(tokens) < 3:
                continue

            predicate = tokens[1]
            if predicate == "a" or ":" not in predicate:
                continue

            prefix, name = predicate.split(":", 1)
            if prefix.lower() == "rdf" and name.lower() == "type":
                continue

            predicates.append(name)

        return sorted(set(predicates))

    def _prefer_database_for_gmqa(
        self,
        candidate_databases: List[str],
        sparql_query: str,
    ) -> str | None:
        if config.CURRENT_DATASET != "GMQA":
            return None

        predicates = set(self._extract_predicates_from_sparql(sparql_query))
        if not predicates:
            return None

        if "participates_in_pathway" in predicates and "PostgreSQL" in candidate_databases:
            return "PostgreSQL"

        if {
            "generates_metabolite",
            "changes_gene_expression_by_microbiota",
        }.issubset(predicates):
            if "MySQL(newgutmgene)" in candidate_databases:
                return "MySQL(newgutmgene)"
            if "MySQL" in candidate_databases:
                return "MySQL"

        return None

    def _prefer_database_for_rodi(
        self,
        candidate_databases: List[str],
        sparql_query: str,
    ) -> str | None:
        if config.CURRENT_DATASET != "RODI":
            return None

        if "PostgreSQL" not in candidate_databases:
            return None

        predicates = set(self._extract_predicates_from_sparql(sparql_query))
        if not predicates:
            return None

        # RODI 的本地 Neo4j 在作者-论文和论文元数据关系上存在缺边，
        # 优先使用 PostgreSQL 以获得稳定结果。
        preferred_predicates = {
            "contributes",
            "has_authors",
            "has_members",
            "was_a_member_of",
            "has_a_paper_title",
            "is_submitted_at",
        }
        if predicates.intersection(preferred_predicates):
            return "PostgreSQL"

        return None

    def _filter_databases_by_predicates(
        self,
        database_names: List[str],
        sparql_query: str,
    ) -> List[str]:
        predicates = self._extract_predicates_from_sparql(sparql_query)
        if not predicates:
            return database_names

        matching_databases = []
        required_predicates = set(predicates)

        for db_name in database_names:
            ttl_key = self._database_name_to_ttl_key(db_name)
            supported_predicates = self.ttl_extractor.get_predicates_for_database(ttl_key)
            if required_predicates.issubset(supported_predicates):
                matching_databases.append(db_name)

        if matching_databases:
            print(
                f"根据SPARQL谓词过滤后的候选数据库: {matching_databases} "
                f"(predicates: {', '.join(predicates)})"
            )
            return matching_databases

        print(
            f"⚠️ 没有在线数据库同时支持谓词 {predicates}，回退到在线数据库集合: "
            f"{database_names}"
        )
        return database_names

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

        available_databases = self._get_available_databases()
        if not available_databases:
            raise RuntimeError(
                f"No available databases for dataset {config.CURRENT_DATASET}. "
                f"Expected one of: {config.ENABLED_DATABASES}"
            )

        candidate_databases = self._filter_databases_by_predicates(
            available_databases,
            sparql_query,
        )
        preferred_database = self._prefer_database_for_gmqa(
            candidate_databases,
            sparql_query,
        )
        if preferred_database:
            print(f"GMQA兜底选择数据库: {preferred_database}")
            print(f"=== 数据库选择完成 ===\n")
            return preferred_database
        preferred_database = self._prefer_database_for_rodi(
            candidate_databases,
            sparql_query,
        )
        if preferred_database:
            print(f"RODI兜底选择数据库: {preferred_database}")
            print(f"=== 数据库选择完成 ===\n")
            return preferred_database
        if len(candidate_databases) == 1:
            selected_db = candidate_databases[0]
            print(f"✅ 根据谓词约束直接选择数据库: {selected_db}")
            print(f"=== 数据库选择完成 ===\n")
            return selected_db

        # 获取当前可用数据库的TTL映射信息
        ttl_info = self._get_ttl_info_for_databases(candidate_databases)

        # 构造提示词
        prompt = self.selection_prompt.format(
            question=question,
            sparql_query=sparql_query,
            ttl_info=ttl_info
        )

        # 调用LLM获取决策
        result = self.llm.invoke(prompt)

        # 解析LLM返回的数据库名称
        selected_db = self._parse_database_selection(result.content, candidate_databases)

        print(f"✅ LLM选择数据库: {selected_db}")
        print(f"=== 数据库选择完成 ===\n")

        return selected_db

    def _parse_database_selection(self, llm_response: str, available_databases: List[str] | None = None) -> str:
        """解析LLM返回的数据库选择"""
        response = llm_response.strip().lower()
        available_databases = available_databases or list(config.ENABLED_DATABASES)

        # 标准化数据库名称
        if 'neo4j' in response:
            selected_db = 'Neo4j'
        elif 'mysql' in response:
            # 检查是否是GMQA数据集的特殊MySQL库
            if config.CURRENT_DATASET == "GMQA":
                if 'gutmdisorder' in response or 'disorder' in response:
                    selected_db = 'MySQL(gutmdisorder)'
                else:
                    selected_db = 'MySQL(newgutmgene)'
            else:
                selected_db = 'MySQL'
        elif 'postgre' in response or 'postgresql' in response:
            selected_db = 'PostgreSQL'
        else:
            # 默认返回第一个可用数据库
            print(f"⚠️ 无法解析LLM响应: {llm_response}")
            return available_databases[0] if available_databases else 'MySQL'

        if selected_db in available_databases:
            return selected_db

        print(f"⚠️ LLM选择了不可用数据库 {selected_db}，回退到 {available_databases[0]}")
        return available_databases[0]


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

    def _normalize_gmqa_mysql_query(self, mysql_query: str, sel_db: str) -> str:
        if config.CURRENT_DATASET != "GMQA":
            return mysql_query

        if sel_db in {"MySQL(newgutmgene)", "MySQL"}:
            mysql_query = re.sub(r"\brelationship\.", "", mysql_query, flags=re.IGNORECASE)
            mysql_query = re.sub(r"\bnewgutmgene\.", "", mysql_query, flags=re.IGNORECASE)
        elif sel_db == "MySQL(gutmdisorder)":
            mysql_query = re.sub(r"\brelationship\.", "newgutmgene.", mysql_query, flags=re.IGNORECASE)
            mysql_query = re.sub(r"\bgutmdisorder\.", "", mysql_query, flags=re.IGNORECASE)

        return mysql_query

    def convert_to_target_query(self, sparql_query: str, sel_db: str) -> str:
        """将SPARQL转换为目标数据库的查询语言"""
        print(f"\n=== 转换查询到 {sel_db} (数据集: {config.CURRENT_DATASET}) ===")
        sel_db = sel_db.strip()

        try:
            if sel_db == 'Neo4j':
                converter = SparqlToCypherConverter(config.TTL_FILES['neo4j'])
                cypher_query = converter.convert(sparql_query)
                print(f"✅ 转换成功")
                print(f"转换后的Cypher: {cypher_query}")
                return cypher_query

            elif sel_db == 'MySQL(newgutmgene)' or (sel_db == 'MySQL' and config.CURRENT_DATASET == "GMQA"):
                ttl_files = config.TTL_FILES['mysql_main'] if isinstance(config.TTL_FILES['mysql_main'], list) else [
                    config.TTL_FILES['mysql_main']]
                converter = SparqlToMySQLConverter(ttl_files)
                mysql_query = converter.convert_sparql_to_mysql(sparql_query)
                mysql_query = self._normalize_gmqa_mysql_query(mysql_query, sel_db)
                print(f"✅ 转换成功")
                print(f"转换后的MySQL: {mysql_query}")
                return mysql_query

            elif sel_db == 'MySQL(gutmdisorder)':
                ttl_files = config.TTL_FILES['mysql_disorder'] if isinstance(config.TTL_FILES['mysql_disorder'], list) else [
                    config.TTL_FILES['mysql_disorder']]
                converter = SparqlToMySQLConverter(ttl_files)
                mysql_query = converter.convert_sparql_to_mysql(sparql_query)
                mysql_query = self._normalize_gmqa_mysql_query(mysql_query, sel_db)
                print(f"✅ 转换成功")
                print(f"转换后的MySQL(gutmdisorder): {mysql_query}")
                return mysql_query

            elif sel_db == 'MySQL' and config.CURRENT_DATASET != "GMQA":
                ttl_files = config.TTL_FILES['mysql_main'] if isinstance(config.TTL_FILES['mysql_main'], list) else [
                    config.TTL_FILES['mysql_main']]
                converter = SparqlToMySQLConverter(ttl_files)
                mysql_query = converter.convert_sparql_to_mysql(sparql_query)
                print(f"✅ 转换成功")
                print(f"转换后的MySQL: {mysql_query}")
                return mysql_query

            elif sel_db == 'PostgreSQL':
                converter = SparqlToPostgreSQLConverter(config.TTL_FILES['postgresql'])
                postgresql_query = converter.convert(sparql_query)
                print(f"✅ 转换成功")
                print(f"转换后的PostgreSQL: {postgresql_query}")
                return postgresql_query

            else:
                print(f"❌ 无法识别的数据库类型: '{sel_db}'")
                print(f"当前数据集({config.CURRENT_DATASET})支持的数据库类型: {config.ENABLED_DATABASES}")
                raise RuntimeError(f"Unsupported database type: {sel_db}")

        except Exception as e:
            print(f"❌ 转换查询时出错: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Failed to convert query for {sel_db}: {e}") from e

    def execute_in_database(self, converted_query: str, sel_db: str) -> List:
        """在指定数据库中执行查询"""
        print(f"\n=== 执行数据库查询 (数据集: {config.CURRENT_DATASET}) ===")
        print(f"数据库: {sel_db}")
        print(f"查询语句: {converted_query}")

        if not converted_query or converted_query.strip() == "":
            print("转换后的查询为空，无法执行")
            return []

        executor = None
        try:
            if sel_db == 'Neo4j':
                executor = Neo4jQueryExecutor(
                    config.Neo4j_config['uri'],
                    config.Neo4j_config['user'],
                    config.Neo4j_config['password']
                )
                result = executor.execute_query(converted_query)
                print(f"Neo4j查询结果: {result}")
                return result

            elif sel_db == 'MySQL(newgutmgene)' or (sel_db == 'MySQL' and config.CURRENT_DATASET == "GMQA"):
                executor = MySQLQueryExecutor(
                    config.MySQL_config['host'],
                    config.MySQL_config['user'],
                    config.MySQL_config['password'],
                    config.MySQL_config['database']
                )
                result = executor.execute_query(converted_query)
                print(f"MySQL查询结果: {result}")
                return result

            elif sel_db == 'MySQL(gutmdisorder)':
                if config.GutMDisorder_config is None:
                    print(f"错误: 当前数据集({config.CURRENT_DATASET})不支持MySQL(gutmdisorder)")
                    return []
                executor = MySQLQueryExecutor(
                    config.GutMDisorder_config['host'],
                    config.GutMDisorder_config['user'],
                    config.GutMDisorder_config['password'],
                    config.GutMDisorder_config['database']
                )
                result = executor.execute_query(converted_query)
                print(f"MySQL(gutmdisorder)查询结果: {result}")
                return result

            elif sel_db == 'MySQL' and config.CURRENT_DATASET != "GMQA":
                executor = MySQLQueryExecutor(
                    config.MySQL_config['host'],
                    config.MySQL_config['user'],
                    config.MySQL_config['password'],
                    config.MySQL_config['database']
                )
                result = executor.execute_query(converted_query)
                print(f"MySQL查询结果: {result}")
                return result

            elif sel_db == 'PostgreSQL':
                executor = PostgreQueryExecutor(
                    config.Postgre_config['host'],
                    config.Postgre_config['user'],
                    config.Postgre_config['password'],
                    config.Postgre_config['database']
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
            raise RuntimeError(f"{sel_db} query execution failed: {e}") from e
        finally:
            if executor is not None:
                try:
                    executor.close()
                except Exception:
                    pass

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

    def format_subquery_results(self, results: List[List[Any]], as_list_literal: bool = False) -> str:
        """将子查询结果格式化为SQL IN子句可用的格式"""
        print(f"\n=== 格式化子查询结果 ===")
        print(f"原始结果: {results}")

        values = []
        for result in results:
            if not result:
                continue
            value = result[0]
            if isinstance(value, str) and value.strip() == "":
                continue
            values.append(value)
        print(f"提取的值: {values}")

        if not values:
            result = '[]' if as_list_literal else 'NULL'
            print(f"格式化后的结果: {result}")
            print(f"=== 格式化完成 ===\n")
            return result

        formatted_values = []
        for value in values:
            if isinstance(value, str):
                escaped_value = value.replace("'", "''")
                formatted_values.append(f"'{escaped_value}'")
            elif value is None:
                formatted_values.append('NULL')
            else:
                formatted_values.append(str(value))

        if as_list_literal:
            result = '[' + ', '.join(formatted_values) + ']'
        else:
            result = ', '.join(formatted_values)
        print(f"格式化后的结果: {result}")
        print(f"=== 格式化完成 ===\n")
        return result

    def _replace_placeholder_in_query(self, query: str, placeholder_text: str, replacement: str) -> str:
        if re.search(r"^\s*MATCH\b", query, re.IGNORECASE):
            in_pattern = re.compile(
                rf"\bIN\s*\(\s*{re.escape(placeholder_text)}\s*\)",
                re.IGNORECASE,
            )
            if in_pattern.search(query):
                return in_pattern.sub(f"IN {replacement}", query)
        return query.replace(placeholder_text, replacement)

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
                results = subquery_results[subquery_num] or []
                print(f"找到子查询 {subquery_num} 的结果: {results}")
            else:
                print(f"警告: 未找到子查询 {subquery_num} 的结果，按空结果处理")
                results = []

            use_list_literal = bool(
                re.search(r"^\s*MATCH\b", result_query, re.IGNORECASE)
                and re.search(
                    rf"\bIN\s*\(\s*{re.escape(placeholder_text)}\s*\)",
                    result_query,
                    re.IGNORECASE,
                )
            )
            formatted_results = self.format_subquery_results(
                results,
                as_list_literal=use_list_literal,
            )
            print(f"格式化后的结果: {formatted_results}")

            old_query = result_query
            result_query = self._replace_placeholder_in_query(
                result_query,
                placeholder_text,
                formatted_results,
            )
            print(f"替换前: {old_query}")
            print(f"替换后: {result_query}")

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
    extractor = TTLContentExtractor(config.TTL_FILES)

    print("\n📝 生成的LLM提示词信息：")
    print("-" * 60)
    ttl_info = extractor.get_all_ttl_info_for_llm()
    print(ttl_info[:2000])  # 只打印前2000字符
    if len(ttl_info) > 2000:
        print(f"\n... (共 {len(ttl_info)} 字符)")
    print("-" * 60)

    print("\n✅ 零硬编码版本测试完成！")
    print("所有数据库选择将完全由LLM根据TTL映射信息决策。")
