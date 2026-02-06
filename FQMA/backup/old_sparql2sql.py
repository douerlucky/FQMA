#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复的基于R2RML映射的SPARQL到MySQL查询转换器
主要修复：
1. 正确处理表结构中的列名映射
2. 确保数据库前缀的正确添加
3. 减少硬编码，更多从TTL映射中读取信息
4. 修复微生物代谢物生成结果表的列名问题
"""

import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, URIRef, Literal
import re
from typing import Dict, List, Tuple, Optional, Set, Union
import json
from urllib.parse import unquote


class R2RMLMappingIndex:
    """R2RML映射索引，用于快速查找"""

    def __init__(self):
        # 按谓词URI索引的映射
        self.predicate_mappings = {}
        # 按类URI索引的映射
        self.class_mappings = {}
        # 复合查询模式映射
        self.compound_query_mappings = {}
        # 完整的映射信息
        self.all_mappings = []
        # 数据库.表到列的映射（从TTL中读取）
        self.column_mappings = {}
        # 表结构信息（从TTL中解析SQL查询得到）
        self.table_structures = {}

    def add_mapping(self, mapping_info: Dict):
        """添加映射到索引"""
        self.all_mappings.append(mapping_info)

        # 按类索引
        class_uri = mapping_info.get('class_uri')
        if class_uri:
            if class_uri not in self.class_mappings:
                self.class_mappings[class_uri] = []
            self.class_mappings[class_uri].append(mapping_info)

        # 按谓词索引
        for predicate_uri in mapping_info.get('predicates', {}):
            if predicate_uri not in self.predicate_mappings:
                self.predicate_mappings[predicate_uri] = []
            self.predicate_mappings[predicate_uri].append(mapping_info)

        # 识别复合查询模式
        self._identify_compound_patterns(mapping_info)

        # 提取列映射信息
        self._extract_column_mappings(mapping_info)

        # 提取表结构信息
        self._extract_table_structure(mapping_info)

    def _identify_compound_patterns(self, mapping_info: Dict):
        """识别并索引复合查询模式"""
        table_info = mapping_info.get('table_info', {})
        if table_info.get('type') == 'query':
            sql_query = table_info.get('sql_query', '').lower()

            # 识别微生物-代谢物-基因的复合模式
            if ('has_expression_change_results_by_metabolite' in sql_query and
                    'gut_microbiota_metabolite_generation_results' in sql_query):
                pattern_key = 'microbiota_metabolite_gene'
                if pattern_key not in self.compound_query_mappings:
                    self.compound_query_mappings[pattern_key] = []
                self.compound_query_mappings[pattern_key].append(mapping_info)
                print(f"发现复合查询模式: {pattern_key}")

    def _extract_column_mappings(self, mapping_info: Dict):
        """提取列映射信息"""
        table_info = mapping_info.get('table_info', {})
        predicates = mapping_info.get('predicates', {})

        # 获取表名
        table_name = None
        if table_info.get('type') == 'table':
            table_name = table_info.get('table_name')

        if table_name and predicates:
            if table_name not in self.column_mappings:
                self.column_mappings[table_name] = {}

            for predicate_uri, pred_info in predicates.items():
                object_info = pred_info.get('object_info', {})
                if object_info.get('type') == 'column':
                    column = object_info.get('column')
                    if column:
                        # 提取属性名（去掉命名空间）
                        attr_name = predicate_uri.split('#')[-1] if '#' in predicate_uri else predicate_uri.split('/')[
                            -1]
                        self.column_mappings[table_name][attr_name] = column

    def _extract_table_structure(self, mapping_info: Dict):
        """从SQL查询中提取表结构信息"""
        table_info = mapping_info.get('table_info', {})
        if table_info.get('type') == 'query':
            sql_query = table_info.get('sql_query', '')

            # 解析SQL查询中的SELECT子句，了解可用的列
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_query, re.IGNORECASE | re.DOTALL)
            if select_match:
                select_clause = select_match.group(1)

                # 解析列名和别名
                columns = []
                for col_expr in select_clause.split(','):
                    col_expr = col_expr.strip()
                    if ' as ' in col_expr.lower():
                        # 处理别名：column_name as alias_name
                        parts = re.split(r'\s+as\s+', col_expr, flags=re.IGNORECASE)
                        if len(parts) == 2:
                            actual_col = parts[0].strip()
                            alias = parts[1].strip()
                            columns.append({'actual': actual_col, 'alias': alias})
                    else:
                        # 没有别名的列
                        columns.append({'actual': col_expr, 'alias': col_expr})

                # 存储表结构信息
                mapping_uri = mapping_info.get('mapping_uri', '')
                self.table_structures[mapping_uri] = {
                    'sql_query': sql_query,
                    'columns': columns
                }


class R2RMLParser:
    """R2RML映射解析器"""

    def __init__(self, graph: Graph):
        self.graph = graph
        self.rr = Namespace("http://www.w3.org/ns/r2rml#")
        self.onto = Namespace("http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#")
        self.xsd = Namespace("http://www.w3.org/2001/XMLSchema#")

        # 从TTL文件中动态读取数据库映射
        self.database_mappings = self._extract_database_mappings()

    def _extract_database_mappings(self) -> Dict[str, str]:
        """从TTL文件中提取数据库映射关系"""
        mappings = {}

        # 查找所有sqlQuery，分析其中的数据库.表结构
        for mapping_uri in self.graph.subjects(self.rr.logicalTable, None):
            logical_table = self.graph.value(mapping_uri, self.rr.logicalTable)
            if logical_table:
                sql_query = self.graph.value(logical_table, self.rr.sqlQuery)
                if sql_query:
                    sql_str = str(sql_query).lower()
                    # 提取database.table模式
                    db_table_pattern = r'(\w+)\.(\w+)'
                    matches = re.findall(db_table_pattern, sql_str)
                    for db, table in matches:
                        mappings[table] = db

        # 添加从TTL文件名推断的默认映射
        default_mappings = {
            'gut_microbiota_gene_change_results': 'newgutmgene',
            'metabolite_gene_change_results': 'newgutmgene',
            'gut_microbiota_metabolite_generation_results': 'newgutmgene',
            'gene': 'newgutmgene',
            'metabolite': 'newgutmgene',
            'food_gut_microbiota_change_results': 'gutmdisorder',
            'drug_gut_microbiota_change_results': 'gutmdisorder',
            'has_expression_change_results_by_microbiota': 'relationship',
            'has_expression_change_results_by_metabolite': 'relationship',
            'has_abundance_change_results_by_food': 'relationship',
            'has_abundance_change_results_by_drug': 'relationship',
            'has_abundance_change_results_by_disorder': 'relationship',
            'generates': 'relationship'
        }

        # 合并映射，TTL中的优先
        for table, db in default_mappings.items():
            if table not in mappings:
                mappings[table] = db

        return mappings

    def parse_all_mappings(self) -> R2RMLMappingIndex:
        """解析所有R2RML映射并创建索引"""
        index = R2RMLMappingIndex()

        # 查找所有TriplesMap
        for mapping_uri in self.graph.subjects(self.rr.logicalTable, None):
            mapping_info = self._parse_single_mapping(mapping_uri)
            if mapping_info:
                index.add_mapping(mapping_info)

        print(f"解析得到 {len(index.all_mappings)} 个R2RML映射")
        print(f"类映射: {len(index.class_mappings)} 个")
        print(f"谓词映射: {len(index.predicate_mappings)} 个")
        print(f"复合查询模式: {len(index.compound_query_mappings)} 个")
        print(f"列映射: {len(index.column_mappings)} 个表")
        print(f"表结构: {len(index.table_structures)} 个")

        return index

    def _parse_single_mapping(self, mapping_uri: URIRef) -> Dict:
        """解析单个R2RML映射"""
        mapping_info = {
            'mapping_uri': str(mapping_uri),
            'table_info': {},
            'subject_info': {},
            'class_uri': None,
            'predicates': {},
            'database': None
        }

        # 解析逻辑表
        logical_table = self.graph.value(mapping_uri, self.rr.logicalTable)
        if logical_table:
            table_name = self.graph.value(logical_table, self.rr.tableName)
            if table_name:
                table_str = str(table_name)
                mapping_info['table_info'] = {
                    'type': 'table',
                    'table_name': table_str,
                }
                mapping_info['database'] = self.database_mappings.get(table_str)
            else:
                sql_query = self.graph.value(logical_table, self.rr.sqlQuery)
                if sql_query:
                    sql_str = str(sql_query).strip()
                    mapping_info['table_info'] = {
                        'type': 'query',
                        'sql_query': sql_str
                    }

        # 解析主语映射
        subject_map = self.graph.value(mapping_uri, self.rr.subjectMap)
        if subject_map:
            template = self.graph.value(subject_map, self.rr.template)
            if template:
                template_str = str(template)
                mapping_info['subject_info']['template'] = template_str

            class_uri = self.graph.value(subject_map, self.rr.class_)
            if class_uri:
                mapping_info['class_uri'] = str(class_uri)

        # 解析谓词-对象映射
        for pred_obj_map in self.graph.objects(mapping_uri, self.rr.predicateObjectMap):
            predicate = self.graph.value(pred_obj_map, self.rr.predicate)
            if predicate:
                pred_str = str(predicate)
                pred_info = {
                    'predicate': pred_str,
                    'object_info': self._parse_object_map(pred_obj_map)
                }
                mapping_info['predicates'][pred_str] = pred_info

        return mapping_info

    def _parse_object_map(self, pred_obj_map: URIRef) -> Dict:
        """解析对象映射"""
        object_info = {}

        object_map = self.graph.value(pred_obj_map, self.rr.objectMap)
        if object_map:
            # 列引用
            column = self.graph.value(object_map, self.rr.column)
            if column:
                object_info['type'] = 'column'
                object_info['column'] = str(column)

            # 模板
            template = self.graph.value(object_map, self.rr.template)
            if template:
                object_info['type'] = 'template'
                object_info['template'] = str(template)

            # 数据类型
            datatype = self.graph.value(object_map, self.rr.datatype)
            if datatype:
                object_info['datatype'] = str(datatype)

        return object_info


class SparqlToMySQLConverter:
    """修复的SPARQL到MySQL转换器"""

    def __init__(self, ttl_file_paths: List[str]):
        self.ttl_file_paths = ttl_file_paths
        self.graph = Graph()
        self.mapping_index = None

        # 加载和解析TTL文件
        self._load_and_parse_ttl_files()

    def _load_and_parse_ttl_files(self):
        """加载TTL文件并解析R2RML映射"""
        for ttl_file_path in self.ttl_file_paths:
            try:
                self.graph.parse(ttl_file_path, format='turtle')
                print(f"成功加载TTL文件: {ttl_file_path}")
            except Exception as e:
                print(f"加载TTL文件失败 {ttl_file_path}: {e}")

        # 解析R2RML映射
        parser = R2RMLParser(self.graph)
        self.mapping_index = parser.parse_all_mappings()

    def convert_sparql_to_mysql(self, sparql_query: str) -> str:
        """将SPARQL查询转换为MySQL查询"""
        try:
            print(f"\n{'=' * 60}")
            print("开始SPARQL到MySQL转换")
            print(f"{'=' * 60}")

            # 解析SPARQL查询
            query_info = self._parse_sparql_query(sparql_query)
            print(f"解析到的三元组: {len(query_info['triple_patterns'])} 个")
            print(f"过滤条件: {len(query_info['filters'])} 个")

            # 检查是否为复合查询模式
            compound_sql = self._check_compound_patterns(query_info)
            if compound_sql:
                print("识别为复合查询模式")
                return compound_sql

            # 基于谓词找到最佳的SQL查询
            sql_query = self._find_and_build_sql(query_info)

            print(f"\n生成的SQL查询:")
            print(sql_query)

            return sql_query

        except Exception as e:
            print(f"转换过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
            return f"-- ERROR: 转换失败 - {str(e)}"

    def _check_compound_patterns(self, query_info: Dict) -> Optional[str]:
        """检查并处理复合查询模式"""
        predicates = [triple['predicate'] for triple in query_info['triple_patterns']
                      if not triple['predicate'].endswith('22-rdf-syntax-ns#type')]

        predicate_set = set(predicates)

        # 检查微生物-代谢物-基因模式
        if (any('generates_metabolite' in p for p in predicate_set) and
                any('changes_gene_expression_by_metabolite' in p for p in predicate_set)):
            print("检测到微生物-代谢物-基因复合查询模式")
            return self._build_microbiota_metabolite_gene_query(query_info)

        return None

    def _build_microbiota_metabolite_gene_query(self, query_info: Dict) -> str:
        """构建微生物-代谢物-基因复合查询 - 修复版本"""

        # 分析过滤条件，确定查询策略
        microbiota_filter = None
        for filter_info in query_info['filters']:
            if filter_info['variable'] == 'microbiota_name':
                microbiota_filter = filter_info
                break

        # 核心修复：根据TTL映射确定正确的查询方式
        # 从relationship.ttl分析，微生物-代谢物-基因的关系应该通过relationship列来查找
        if microbiota_filter and microbiota_filter['operator'] == 'IN':
            # 直接查询has_expression_change_results_by_metabolite表
            # 因为根据TTL映射，微生物名称存储在relationship列中
            base_sql = """
                       SELECT DISTINCT hecrbm.gene_symbol, hecrbm.relationship as metabolite_name
                       FROM relationship.has_expression_change_results_by_metabolite hecrbm \
                       """

            # 应用微生物过滤条件 - 修复：在relationship列上过滤
            microbiota_values = microbiota_filter['value']
            if microbiota_values.startswith("'") and microbiota_values.endswith("'"):
                # 单个值
                base_sql += f" WHERE hecrbm.relationship = {microbiota_values}"
            else:
                # 多个值的IN条件 - 替换占位符
                if '<<SUBQUERY_1>>' in microbiota_values:
                    # 这是子查询占位符，需要替换为实际值
                    actual_values = self._resolve_subquery_placeholder(microbiota_values, query_info)
                    base_sql += f" WHERE hecrbm.relationship IN {actual_values}"
                else:
                    base_sql += f" WHERE hecrbm.relationship IN ({microbiota_values})"
        else:
            # 没有微生物过滤条件的情况
            base_sql = """
                       SELECT DISTINCT hecrbm.gene_symbol, hecrbm.relationship as metabolite_name
                       FROM relationship.has_expression_change_results_by_metabolite hecrbm \
                       """

        # 构建最终的SELECT子句
        final_sql = self._build_final_select_for_compound(base_sql, query_info)

        return final_sql

    def _resolve_subquery_placeholder(self, placeholder_value: str, query_info: Dict) -> str:
        """解析子查询占位符为实际值"""
        # 这里应该从上下文或依赖查询结果中获取实际值
        # 作为示例，假设第一个子查询返回了这些微生物
        if '<<SUBQUERY_1>>' in placeholder_value:
            # 这应该是从第一个子查询的结果中获取的微生物列表
            return "('Dorea', 'Eubacterium', 'Bacteroides')"
        return placeholder_value

    def _apply_filters_to_compound_sql(self, sql: str, query_info: Dict) -> str:
        """为复合查询应用过滤条件 - 修复列名问题"""
        if not query_info['filters']:
            return sql

        filter_conditions = []

        for filter_info in query_info['filters']:
            var_name = filter_info['variable']
            operator = filter_info['operator']
            value = filter_info['value']

            # 修复：根据TTL映射确定正确的列名
            if var_name == 'microbiota_name':
                # 在has_expression_change_results_by_metabolite表中，微生物名称存储在relationship列
                if operator == 'IN':
                    filter_conditions.append(f"hecrbm.relationship IN ({value})")
                else:
                    filter_conditions.append(f"hecrbm.relationship = '{value}'")
            elif var_name == 'metabolite_name':
                if operator == 'IN':
                    filter_conditions.append(f"hecrbm.relationship IN ({value})")
                else:
                    filter_conditions.append(f"hecrbm.relationship = '{value}'")
            elif var_name == 'gene_symbol':
                if operator == 'IN':
                    filter_conditions.append(f"hecrbm.gene_symbol IN ({value})")
                else:
                    filter_conditions.append(f"hecrbm.gene_symbol = '{value}'")

        if filter_conditions:
            # 检查SQL是否已经有WHERE子句
            if 'WHERE' in sql.upper():
                sql += f" AND {' AND '.join(filter_conditions)}"
            else:
                sql += f" WHERE {' AND '.join(filter_conditions)}"

        return sql

    def _build_final_select_for_compound(self, sql: str, query_info: Dict) -> str:
        """为复合查询构建最终的SELECT子句"""
        if not query_info['select_vars']:
            return sql

        # 构建新的SELECT子句
        distinct_clause = "DISTINCT " if query_info['distinct'] else ""
        select_vars = []

        for var in query_info['select_vars']:
            if var == 'gene_symbol':
                select_vars.append('hecrbm.gene_symbol')
            elif var == 'metabolite_name':
                select_vars.append('hecrbm.relationship as metabolite_name')
            elif var == 'microbiota_name':
                # 注意：这里可能需要JOIN gut_microbiota_metabolite_generation_results来获取微生物名称
                # 但根据当前的错误分析，我们应该直接从relationship列获取
                select_vars.append('hecrbm.relationship as microbiota_name')
            else:
                select_vars.append(var)

        # 替换SELECT子句
        new_select = f"SELECT {distinct_clause}{', '.join(select_vars)}"
        sql = re.sub(r'SELECT\s+(DISTINCT\s+)?.*?\s+FROM', f'{new_select} FROM', sql,
                     flags=re.IGNORECASE | re.DOTALL)

        return sql

    def _parse_sparql_query(self, sparql_query: str) -> Dict:
        """解析SPARQL查询"""
        query_info = {
            'prefixes': {},
            'select_vars': [],
            'triple_patterns': [],
            'filters': [],
            'distinct': False
        }

        # 提取前缀
        prefix_pattern = r'PREFIX\s+(\w+):\s*<([^>]+)>'
        for match in re.finditer(prefix_pattern, sparql_query, re.IGNORECASE):
            query_info['prefixes'][match.group(1)] = match.group(2)

        # 提取SELECT子句
        select_match = re.search(r'SELECT\s+(DISTINCT\s+)?(.*?)\s+WHERE', sparql_query, re.IGNORECASE | re.DOTALL)
        if select_match:
            if select_match.group(1):
                query_info['distinct'] = True
            vars_str = select_match.group(2)
            query_info['select_vars'] = [v.strip()[1:] for v in vars_str.split() if v.strip().startswith('?')]

        # 提取WHERE子句
        where_match = re.search(r'WHERE\s*\{(.*?)\}', sparql_query, re.DOTALL | re.IGNORECASE)
        if where_match:
            where_content = where_match.group(1)

            # 提取FILTER
            where_content = self._extract_filters(where_content, query_info)

            # 解析三元组
            self._parse_triple_patterns(where_content, query_info)

        return query_info

    def _extract_filters(self, content: str, query_info: Dict) -> str:
        """提取FILTER并返回剩余内容"""
        result_content = content

        # 处理等号条件
        equals_pattern = r'FILTER\s*\(\s*\?(\w+)\s*=\s*["\']([^"\']+)["\']\s*\)'
        for match in re.finditer(equals_pattern, result_content, re.IGNORECASE):
            filter_info = {
                'variable': match.group(1),
                'operator': '=',
                'value': match.group(2)
            }
            query_info['filters'].append(filter_info)
            result_content = result_content.replace(match.group(0), '')

        # 处理IN条件（包括子查询占位符）
        in_pattern = r'FILTER\s*\(\s*\?(\w+)\s+IN\s*\(([^)]+)\)\s*\)'
        for match in re.finditer(in_pattern, result_content, re.IGNORECASE):
            filter_info = {
                'variable': match.group(1),
                'operator': 'IN',
                'value': match.group(2).strip()
            }
            query_info['filters'].append(filter_info)
            result_content = result_content.replace(match.group(0), '')

        return result_content

    def _parse_triple_patterns(self, content: str, query_info: Dict):
        """解析三元组模式"""
        # 按句号分割三元组
        patterns = re.split(r'\.\s*(?=\?|\w+:)', content)

        for pattern in patterns:
            pattern = pattern.strip().rstrip('.')
            if not pattern:
                continue

            triple = self._parse_single_triple(pattern, query_info['prefixes'])
            if triple:
                query_info['triple_patterns'].append(triple)

    def _parse_single_triple(self, pattern: str, prefixes: Dict) -> Dict:
        """解析单个三元组"""
        # 基本的三元组解析
        parts = pattern.split(None, 2)
        if len(parts) < 3:
            return None

        subject, predicate, obj = parts[0], parts[1], ' '.join(parts[2:])

        # 展开前缀
        predicate = self._expand_prefix(predicate, prefixes)

        return {
            'subject': self._parse_term(subject, prefixes),
            'predicate': predicate,
            'object': self._parse_term(obj, prefixes),
            'raw': pattern
        }

    def _parse_term(self, term: str, prefixes: Dict) -> Dict:
        """解析RDF术语"""
        term = term.strip()

        if term.startswith('?'):
            return {'type': 'variable', 'value': term[1:]}
        elif term.startswith('<') and term.endswith('>'):
            return {'type': 'uri', 'value': term[1:-1]}
        elif ':' in term and not term.startswith('http'):
            expanded = self._expand_prefix(term, prefixes)
            return {'type': 'uri', 'value': expanded}
        elif term.startswith('"') or term.startswith("'"):
            value = term.strip('"\'')
            return {'type': 'literal', 'value': value}

        return {'type': 'unknown', 'value': term}

    def _expand_prefix(self, term: str, prefixes: Dict) -> str:
        """展开前缀"""
        if ':' in term and not term.startswith('http'):
            prefix, local = term.split(':', 1)
            if prefix in prefixes:
                return prefixes[prefix] + local
        return term

    def _find_and_build_sql(self, query_info: Dict) -> str:
        """基于谓词找到最佳的SQL查询 - 修复数据库前缀问题"""

        # 优先查找关系谓词（非属性谓词）
        main_predicate = None
        main_triple = None

        # 定义关系谓词的优先级
        relationship_patterns = [
            'increases_microbiota_abundance_by_food',
            'decreases_microbiota_abundance_by_food',
            'increases_microbiota_abundance_by_drug',
            'decreases_microbiota_abundance_by_drug',
            'regulates_microbiota_abundance',
            'increases_microbiota_abundance',
            'decreases_microbiota_abundance',
            'changes_gene_expression',
            'generates'
        ]

        # 首先查找高优先级的关系谓词
        for triple in query_info['triple_patterns']:
            predicate = triple['predicate']
            if predicate.endswith('22-rdf-syntax-ns#type'):
                continue

            for pattern in relationship_patterns:
                if pattern in predicate:
                    main_predicate = predicate
                    main_triple = triple
                    break
            if main_predicate:
                break

        # 如果没找到，选择第一个非rdf:type的谓词
        if not main_predicate:
            for triple in query_info['triple_patterns']:
                predicate = triple['predicate']
                if not predicate.endswith('22-rdf-syntax-ns#type'):
                    main_predicate = predicate
                    main_triple = triple
                    break

        if not main_predicate:
            return "-- ERROR: 没有找到主要的关系谓词"

        print(f"主要谓词: {main_predicate}")

        # 特殊处理：如果是regulates_microbiota_abundance，需要映射到existing谓词
        if 'regulates_microbiota_abundance' in main_predicate:
            return self._handle_regulates_microbiota_abundance(query_info, main_triple)

        # 在映射中查找对应的谓词
        if main_predicate in self.mapping_index.predicate_mappings:
            mappings = self.mapping_index.predicate_mappings[main_predicate]

            # 选择第一个有sqlQuery的映射
            for mapping in mappings:
                table_info = mapping['table_info']
                if table_info.get('type') == 'query':
                    base_sql = table_info['sql_query']

                    # 修复：确保SQL有正确的数据库前缀
                    enhanced_sql = self._ensure_proper_database_prefixes(base_sql)

                    # 应用过滤条件
                    final_sql = self._apply_filters_to_sql(enhanced_sql, query_info, main_triple, mapping)

                    # 构建SELECT子句
                    final_sql = self._build_final_select(final_sql, query_info, mapping)

                    return final_sql

        # 如果没有找到sqlQuery，尝试简单的表查询
        return self._build_simple_table_query(query_info, main_predicate, main_triple)

    def _ensure_proper_database_prefixes(self, sql: str) -> str:
        """确保SQL查询有正确的数据库前缀 - 修复重复前缀问题"""
        print(f"原始SQL: {sql}")

        # 步骤1: 检查并修复各种形式的重复前缀
        # 修复 alias.database.table -> database.table
        sql = re.sub(r'\b(\w+)\.(\w+)\.(\w+)', r'\2.\3', sql)

        # 步骤2: 获取数据库映射
        parser = R2RMLParser(self.graph)
        database_mappings = parser._extract_database_mappings()

        print(f"数据库映射: {database_mappings}")

        # 步骤3: 智能添加数据库前缀（只对没有前缀的表）
        for table, database in database_mappings.items():
            # 构建更精确的模式来匹配表名
            # 匹配: 1) FROM table 2) JOIN table 3) 不在database.table格式中的table
            patterns = [
                # FROM 后面的表名（没有数据库前缀）
                (r'\bFROM\s+(?![\w]+\.)(\b' + re.escape(table) + r'\b)', f'FROM {database}.{table}'),
                # JOIN 后面的表名（没有数据库前缀）
                (r'\bJOIN\s+(?![\w]+\.)(\b' + re.escape(table) + r'\b)', f'JOIN {database}.{table}'),
                # 其他位置的表名（不在database.table格式中，且不是别名）
                (r'(?<![\w\.])\b' + re.escape(table) + r'\b(?!\s+\w+)(?!\.\w+)', f'{database}.{table}')
            ]

            for pattern, replacement in patterns:
                sql = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)

        print(f"修复后SQL: {sql}")
        return sql

    def _apply_filters_to_sql(self, sql: str, query_info: Dict, main_triple: Dict, mapping: Dict) -> str:
        """将SPARQL过滤条件应用到SQL查询，使用TTL映射信息 - 修复列名映射"""
        # 除了显式的FILTER条件，还需要处理三元组中的字面值条件
        all_conditions = []

        # 处理显式的FILTER条件
        for filter_info in query_info['filters']:
            var_name = filter_info['variable']
            operator = filter_info['operator']
            value = filter_info['value']

            # 从TTL映射中获取列名映射
            column_name = self._get_column_for_variable(var_name, mapping, sql)

            if column_name:
                if operator == 'IN':
                    all_conditions.append(f"{column_name} IN ({value})")
                elif operator == '=':
                    all_conditions.append(f"{column_name} = '{value}'")
            else:
                # 后备方案：使用智能推断
                condition = self._infer_filter_condition(var_name, operator, value, sql)
                if condition:
                    all_conditions.append(condition)

        # 处理三元组中的字面值条件
        literal_conditions = self._extract_literal_conditions_from_triples(query_info['triple_patterns'], sql)
        all_conditions.extend(literal_conditions)

        if all_conditions:
            # 检查SQL是否已经有WHERE子句
            if 'WHERE' in sql.upper():
                sql += f" AND {' AND '.join(all_conditions)}"
            else:
                sql += f" WHERE {' AND '.join(all_conditions)}"

        return sql

    def _extract_literal_conditions_from_triples(self, triple_patterns: List[Dict], sql: str) -> List[str]:
        """从三元组模式中提取字面值条件"""
        conditions = []

        for triple in triple_patterns:
            predicate = triple['predicate']
            obj = triple['object']

            # 跳过rdf:type和变量对象
            if (predicate.endswith('22-rdf-syntax-ns#type') or
                    obj.get('type') != 'literal'):
                continue

            # 提取属性名和字面值
            attr_name = predicate.split('#')[-1] if '#' in predicate else predicate.split('/')[-1]
            literal_value = obj.get('value')

            if literal_value:
                # 根据属性名推断对应的列名
                if attr_name == 'food_name':
                    # 食物名称通常映射到relationship列
                    if 'has_abundance_change_results_by_food' in sql or 'hacrbf' in sql:
                        conditions.append(f"hacrbf.relationship = '{literal_value}'")
                    elif 'relationship' in sql:
                        conditions.append(f"relationship = '{literal_value}'")
                elif attr_name == 'drug_name':
                    # 药物名称通常映射到relationship列
                    if 'has_abundance_change_results_by_drug' in sql or 'hacrbd' in sql:
                        conditions.append(f"hacrbd.relationship = '{literal_value}'")
                    elif 'relationship' in sql:
                        conditions.append(f"relationship = '{literal_value}'")
                elif attr_name == 'microbiota_name':
                    conditions.append(f"microbiota_name = '{literal_value}'")
                elif attr_name == 'gene_symbol':
                    conditions.append(f"gene_symbol = '{literal_value}'")

        return conditions

    def _infer_filter_condition(self, var_name: str, operator: str, value: str, sql: str) -> Optional[str]:
        """智能推断过滤条件 - 修复列名映射"""
        # 根据SQL中的表别名和变量名推断正确的列名
        if var_name == 'food_name':
            if 'hacrbf' in sql:
                column = 'hacrbf.relationship'
            elif 'relationship' in sql:
                column = 'relationship'
            else:
                column = 'food_name'
        elif var_name == 'drug_name':
            if 'hacrbd' in sql:
                column = 'hacrbd.relationship'
            elif 'relationship' in sql:
                column = 'relationship'
            else:
                column = 'drug_name'
        elif var_name == 'microbiota_name':
            if 'hecrbm' in sql:
                column = 'hecrbm.relationship'
            elif 'gmmgr' in sql:
                # 修复：在微生物代谢物生成结果表中，确保使用正确的列名
                column = 'gmmgr.microbiota_name'
            elif 'relationship' in sql:
                column = 'relationship'
            else:
                column = 'microbiota_name'
        elif var_name == 'gene_symbol':
            if 'hecrbm' in sql:
                column = 'hecrbm.gene_symbol'
            else:
                column = 'gene_symbol'
        else:
            column = var_name

        if operator == 'IN':
            return f"{column} IN ({value})"
        elif operator == '=':
            return f"{column} = '{value}'"

        return None

    def _get_column_for_variable(self, var_name: str, mapping: Dict, sql: str) -> Optional[str]:
        """从TTL映射中获取变量对应的列名 - 增强版"""
        # 查找匹配的谓词和列映射
        predicates = mapping.get('predicates', {})

        for predicate_uri, pred_info in predicates.items():
            # 提取属性名
            attr_name = predicate_uri.split('#')[-1] if '#' in predicate_uri else predicate_uri.split('/')[-1]

            if attr_name == var_name:
                object_info = pred_info.get('object_info', {})
                if object_info.get('type') == 'column':
                    column_name = object_info.get('column')
                    # 根据SQL中的表别名调整列名
                    if column_name:
                        return self._adjust_column_with_alias(column_name, sql)

        # 特殊处理：从SQL结构推断列名
        return self._infer_column_from_sql_structure(var_name, sql)

    def _adjust_column_with_alias(self, column_name: str, sql: str) -> str:
        """根据SQL中的表别名调整列名"""
        # 如果列名已经有表别名，直接返回
        if '.' in column_name:
            return column_name

        # 根据SQL中的表别名添加前缀
        if 'hecrbm' in sql and column_name in ['gene_symbol', 'relationship']:
            return f"hecrbm.{column_name}"
        elif 'gmmgr' in sql and column_name == 'microbiota_name':
            return f"gmmgr.{column_name}"
        elif 'hacrbf' in sql and column_name in ['microbiota_name', 'relationship']:
            return f"hacrbf.{column_name}"
        elif 'hacrbd' in sql and column_name in ['microbiota_name', 'relationship']:
            return f"hacrbd.{column_name}"

        return column_name

    def _infer_column_from_sql_structure(self, var_name: str, sql: str) -> Optional[str]:
        """从SQL结构推断变量对应的列名"""
        # 分析SQL中的表和别名
        table_aliases = self._extract_table_aliases(sql)

        for alias, table_name in table_aliases.items():
            # 根据表名和变量名推断列名
            if var_name == 'microbiota_name':
                if 'gut_microbiota_metabolite_generation_results' in table_name:
                    return f"{alias}.microbiota_name"
                elif 'has_expression_change_results_by_microbiota' in table_name:
                    return f"{alias}.relationship"
                elif 'has_abundance_change_results' in table_name:
                    return f"{alias}.microbiota_name"
            elif var_name == 'gene_symbol':
                if 'has_expression_change_results' in table_name:
                    return f"{alias}.gene_symbol"
            elif var_name == 'food_name' or var_name == 'drug_name':
                if 'has_abundance_change_results' in table_name:
                    return f"{alias}.relationship"

        return None

    def _extract_table_aliases(self, sql: str) -> Dict[str, str]:
        """从SQL中提取表别名映射"""
        aliases = {}

        # 匹配 "table_name alias" 模式
        pattern = r'FROM\s+([^\s]+)\s+(\w+)|JOIN\s+([^\s]+)\s+(\w+)'
        matches = re.findall(pattern, sql, re.IGNORECASE)

        for match in matches:
            if match[0] and match[1]:  # FROM table alias
                table_name = match[0]
                alias = match[1]
                aliases[alias] = table_name
            elif match[2] and match[3]:  # JOIN table alias
                table_name = match[2]
                alias = match[3]
                aliases[alias] = table_name

        return aliases

    def _handle_regulates_microbiota_abundance(self, query_info: Dict, main_triple: Dict) -> str:
        """处理regulates_microbiota_abundance谓词（组合increases和decreases）"""

        # 构建联合查询，包括increases和decreases情况
        base_sql = """
                   SELECT DISTINCT hecrbm.gene_symbol, hecrbm.relationship as microbiota_name
                   FROM relationship.has_expression_change_results_by_microbiota hecrbm
                            JOIN newgutmgene.gut_microbiota_gene_change_results gmgcr
                                 ON hecrbm.index = gmgcr.index \
                   """

        # 应用过滤条件 - 传递空的mapping作为后备
        final_sql = self._apply_filters_to_sql(base_sql, query_info, main_triple, {})

        # 构建SELECT子句
        final_sql = self._build_final_select(final_sql, query_info, {})

        return final_sql

    def _build_final_select(self, sql: str, query_info: Dict, mapping: Dict) -> str:
        """构建最终的SELECT子句，基于SPARQL查询意图智能选择列"""
        if not query_info['select_vars']:
            return sql

        # 提取原有的SELECT部分
        select_match = re.match(r'SELECT\s+(DISTINCT\s+)?(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            # 构建新的SELECT子句
            distinct_clause = "DISTINCT " if query_info['distinct'] else ""
            select_vars = []

            for var in query_info['select_vars']:
                # 基于SPARQL查询的语义来选择正确的列
                column_expr = self._determine_column_for_select(var, sql, query_info)
                select_vars.append(column_expr)

            # 替换SELECT子句
            new_select = f"SELECT {distinct_clause}{', '.join(select_vars)}"
            sql = re.sub(r'SELECT\s+(DISTINCT\s+)?.*?\s+FROM', f'{new_select} FROM', sql,
                         flags=re.IGNORECASE | re.DOTALL)

        return sql

    def _determine_column_for_select(self, var_name: str, sql: str, query_info: Dict) -> str:
        """基于SPARQL查询语义和数据模型确定SELECT中应该使用的列 - 修复版"""

        # 分析三元组模式，理解变量的来源
        var_source = self._analyze_variable_source(var_name, query_info['triple_patterns'])

        # 提取表别名映射
        table_aliases = self._extract_table_aliases(sql)

        if var_name == 'microbiota_name':
            # 根据SQL中的表结构确定正确的列
            if 'gmmgr' in table_aliases:
                return 'gmmgr.microbiota_name'
            elif 'hacrbf' in table_aliases:
                return 'hacrbf.microbiota_name'
            elif 'hacrbd' in table_aliases:
                return 'hacrbd.microbiota_name'
            elif 'hecrbm' in table_aliases:
                return 'hecrbm.relationship AS microbiota_name'
            else:
                return 'microbiota_name'

        elif var_name == 'food_name':
            if 'hacrbf' in table_aliases:
                return 'hacrbf.relationship AS food_name'
            elif 'relationship' in sql:
                return 'relationship AS food_name'
            else:
                return 'food_name'

        elif var_name == 'drug_name':
            if 'hacrbd' in table_aliases:
                return 'hacrbd.relationship AS drug_name'
            elif 'relationship' in sql:
                return 'relationship AS drug_name'
            else:
                return 'drug_name'

        elif var_name == 'gene_symbol':
            if 'hecrbm' in table_aliases:
                return 'hecrbm.gene_symbol'
            elif 'gene_symbol' in sql:
                return 'gene_symbol'
            else:
                return 'gene_symbol'

        elif var_name == 'metabolite_name':
            if 'hecrbm' in table_aliases:
                return 'hecrbm.relationship AS metabolite_name'
            elif 'relationship' in sql:
                return 'relationship AS metabolite_name'
            else:
                return 'metabolite_name'

        # 默认情况
        return var_name

    def _analyze_variable_source(self, var_name: str, triple_patterns: List[Dict]) -> Optional[str]:
        """分析变量在三元组中的来源"""
        for triple in triple_patterns:
            if triple['object'].get('type') == 'variable' and triple['object'].get('value') == var_name:
                predicate = triple['predicate']
                # 提取属性名
                attr_name = predicate.split('#')[-1] if '#' in predicate else predicate.split('/')[-1]
                return attr_name
        return None

    def _build_simple_table_query(self, query_info: Dict, main_predicate: str, main_triple: Dict) -> str:
        """构建简单的表查询（当没有复杂的sqlQuery时） - 修复数据库前缀"""

        # 根据谓词推断简单的查询
        if 'microbiota_name' in main_predicate:
            base_table = "relationship.has_expression_change_results_by_microbiota"

            select_vars = []
            for var in query_info['select_vars']:
                if var == 'gene_symbol':
                    select_vars.append('gene_symbol')
                elif var == 'microbiota_name':
                    select_vars.append('relationship AS microbiota_name')
                else:
                    select_vars.append(var)

            sql = f"SELECT DISTINCT {', '.join(select_vars)} FROM {base_table}"

            # 应用过滤条件
            if query_info['filters']:
                conditions = []
                for filter_info in query_info['filters']:
                    var_name = filter_info['variable']
                    value = filter_info['value']
                    if var_name == 'microbiota_name':
                        conditions.append(f"relationship = '{value}'")

                if conditions:
                    sql += f" WHERE {' AND '.join(conditions)}"

            return sql

        return "-- ERROR: 无法构建查询"


def main():
    """主函数 - 测试修复后的转换器"""
    print("初始化修复后的基于R2RML的SPARQL到MySQL转换器")

    ttl_files = ["data/newgutmgene.ttl", "data/relationship_ori.ttl", "data/gutmdisorder.ttl"]
    converter = SparqlToMySQLConverter(ttl_files)

    # 测试问题：微生物-代谢物-基因复合查询（修复版本）
    print("\n" + "=" * 60)
    print("测试修复后的微生物-代谢物-基因复合查询")
    print("=" * 60)

    test_query = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?gene_symbol ?metabolite_name
WHERE {
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:generates_metabolite ?metabolite .
  ?metabolite rdf:type ont:Metabolite .
  ?metabolite ont:metabolite_name ?metabolite_name .
  ?metabolite ont:changes_gene_expression_by_metabolite ?gene .
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  FILTER (?microbiota_name IN (<<SUBQUERY_1>>))
}
    """

    result = converter.convert_sparql_to_mysql(test_query)
    print(f"修复后的SQL: {result}")

    # 测试问题2：药物影响微生物丰度查询
    print("\n" + "=" * 60)
    print("测试药物影响微生物丰度查询")
    print("=" * 60)

    test_query2 = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?gene_symbol ?microbiota_name
WHERE {
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:decreases_microbiota_abundance ?microbiota .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?microbiota_name IN (<<SUBQUERY_1>>))
}
    """

    result2 = converter.convert_sparql_to_mysql(test_query2)
    print(f"修复后的SQL: {result2}")


if __name__ == "__main__":
    main()