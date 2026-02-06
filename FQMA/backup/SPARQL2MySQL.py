#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真正零硬编码的数据驱动SPARQL转换器 - 修复版
核心原则：
1. 零if-else硬编码逻辑
2. 完全基于TTL映射的动态推断
3. 智能的SQL解析和映射提取
4. 通用算法，适应任何TTL配置
5. 正确处理变量完整性和FILTER条件
"""

import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, URIRef, Literal
import re
from typing import Dict, List, Tuple, Optional, Set, Union
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class ColumnMapping:
    """列映射信息"""
    select_expression: str  # SELECT中的完整表达式 (如: hecrbm.relationship AS metabolite_name)
    where_expression: str  # WHERE中使用的表达式 (如: hecrbm.relationship)
    variable_name: str  # SPARQL变量名 (如: metabolite_name)


@dataclass
class SQLMapping:
    """SQL映射信息"""
    predicate_uri: str
    sql_query: str
    column_mappings: Dict[str, ColumnMapping]  # variable_name -> ColumnMapping
    complexity_score: int  # 复杂度评分（JOIN数量等）
    covered_predicates: Set[str]  # 覆盖的谓词集合
    mapping_id: str  # 映射标识符


class ZeroHardcodeParser:
    """零硬编码的TTL解析器"""

    def __init__(self, graph: Graph):
        self.graph = graph
        self.rr = Namespace("http://www.w3.org/ns/r2rml#")
        self.onto = Namespace("http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#")

    def extract_all_sql_mappings(self) -> List[SQLMapping]:
        """从TTL中提取所有SQL映射，完全数据驱动"""
        mappings = []

        for mapping_uri in self.graph.subjects(self.rr.logicalTable, None):
            mapping = self._extract_single_mapping(mapping_uri)
            if mapping:
                mappings.append(mapping)

        # 按复杂度和变量覆盖度排序，优先选择变量完整的映射
        mappings.sort(key=lambda x: (len(x.column_mappings), x.complexity_score), reverse=True)

        print(f"提取到 {len(mappings)} 个SQL映射")
        for i, mapping in enumerate(mappings[:5]):
            print(f"{i + 1}. {mapping.mapping_id}")
            print(f"   复杂度: {mapping.complexity_score}")
            print(f"   列映射: {list(mapping.column_mappings.keys())}")
            print(f"   覆盖谓词: {len(mapping.covered_predicates)}")

        return mappings

    def _extract_single_mapping(self, mapping_uri: URIRef) -> Optional[SQLMapping]:
        """提取单个映射，完全基于TTL内容"""
        # 获取SQL查询
        logical_table = self.graph.value(mapping_uri, self.rr.logicalTable)
        if not logical_table:
            return None

        sql_query = self.graph.value(logical_table, self.rr.sqlQuery)
        if not sql_query:
            return None

        sql_str = str(sql_query).strip()

        # 提取所有谓词（不只是主要谓词）
        covered_predicates = self._extract_all_predicates(mapping_uri)
        main_predicate = self._extract_main_predicate(mapping_uri)

        if not main_predicate:
            return None

        # 智能解析SQL中的列映射
        column_mappings = self._parse_sql_column_mappings(sql_str)

        # 计算复杂度评分
        complexity_score = self._calculate_complexity_score(sql_str)

        # 获取映射ID
        mapping_id = str(mapping_uri).split('#')[-1] if '#' in str(mapping_uri) else str(mapping_uri)

        return SQLMapping(
            predicate_uri=main_predicate,
            sql_query=sql_str,
            column_mappings=column_mappings,
            complexity_score=complexity_score,
            covered_predicates=covered_predicates,
            mapping_id=mapping_id
        )

    def _extract_all_predicates(self, mapping_uri: URIRef) -> Set[str]:
        """提取映射覆盖的所有谓词"""
        predicates = set()

        for pred_obj_map in self.graph.objects(mapping_uri, self.rr.predicateObjectMap):
            predicate = self.graph.value(pred_obj_map, self.rr.predicate)
            if predicate:
                predicates.add(str(predicate))

        return predicates

    def _extract_main_predicate(self, mapping_uri: URIRef) -> Optional[str]:
        """提取主要谓词，优先选择非属性谓词"""
        predicates = []

        for pred_obj_map in self.graph.objects(mapping_uri, self.rr.predicateObjectMap):
            predicate = self.graph.value(pred_obj_map, self.rr.predicate)
            if predicate:
                pred_str = str(predicate)
                predicates.append(pred_str)

        if not predicates:
            return None

        # 智能选择主要谓词：优先选择关系谓词
        relation_predicates = []
        attribute_predicates = []

        for pred in predicates:
            pred_name = pred.split('#')[-1] if '#' in pred else pred.split('/')[-1]

            # 判断是否为关系谓词
            relation_indicators = ['changes', 'generates', 'regulates', 'increases', 'decreases', 'has_']
            if any(indicator in pred_name.lower() for indicator in relation_indicators):
                relation_predicates.append(pred)
            else:
                attribute_predicates.append(pred)

        # 优先返回关系谓词
        return relation_predicates[0] if relation_predicates else predicates[0]

    def _parse_sql_column_mappings(self, sql_query: str) -> Dict[str, ColumnMapping]:
        """智能解析SQL查询中的列映射，完全数据驱动"""
        column_mappings = {}

        # 解析SELECT子句
        select_match = re.search(r'SELECT\s+(DISTINCT\s+)?(.*?)\s+FROM', sql_query, re.IGNORECASE | re.DOTALL)
        if not select_match:
            return column_mappings

        select_clause = select_match.group(2)

        # 解析每个SELECT列
        for col_expr in select_clause.split(','):
            col_expr = col_expr.strip()

            # 解析 "column AS alias" 格式
            as_match = re.match(r'(.+?)\s+as\s+(\w+)', col_expr, re.IGNORECASE)
            if as_match:
                actual_column = as_match.group(1).strip()
                alias = as_match.group(2).strip()

                column_mappings[alias] = ColumnMapping(
                    select_expression=col_expr,
                    where_expression=actual_column,
                    variable_name=alias
                )
            else:
                # 没有AS别名的列
                column_name = col_expr.strip()
                # 提取列名（去掉表前缀）
                actual_name = column_name.split('.')[-1] if '.' in column_name else column_name

                column_mappings[actual_name] = ColumnMapping(
                    select_expression=col_expr,
                    where_expression=col_expr,
                    variable_name=actual_name
                )

        return column_mappings

    def _calculate_complexity_score(self, sql_query: str) -> int:
        """计算SQL查询的复杂度评分"""
        score = 0
        sql_lower = sql_query.lower()

        # JOIN增加复杂度
        score += sql_lower.count('join') * 10

        # DISTINCT增加复杂度
        if 'distinct' in sql_lower:
            score += 5

        # WHERE子句增加复杂度
        if 'where' in sql_lower:
            score += 3

        # 表数量增加复杂度
        from_tables = re.findall(r'from\s+\w+\.\w+', sql_lower)
        join_tables = re.findall(r'join\s+\w+\.\w+', sql_lower)
        score += (len(from_tables) + len(join_tables)) * 2

        return score


class SparqlToMySQLConverter:
    """真正零硬编码的SPARQL转换器"""

    def __init__(self, ttl_file_paths: List[str]):
        self.ttl_file_paths = ttl_file_paths
        self.graph = Graph()
        self.sql_mappings = []

        self._load_and_parse()

    def _load_and_parse(self):
        """加载TTL文件并解析"""
        # 加载TTL文件
        for ttl_file_path in self.ttl_file_paths:
            try:
                self.graph.parse(ttl_file_path, format='turtle')
                print(f"成功加载TTL文件: {ttl_file_path}")
            except Exception as e:
                print(f"加载TTL文件失败 {ttl_file_path}: {e}")

        # 解析SQL映射
        parser = ZeroHardcodeParser(self.graph)
        self.sql_mappings = parser.extract_all_sql_mappings()

    def convert_sparql_to_mysql(self, sparql_query: str) -> str:
        """转换SPARQL查询为MySQL查询，零硬编码"""
        try:
            print(f"\n{'=' * 60}")
            print("开始真正数据驱动的SPARQL转换")
            print(f"{'=' * 60}")

            # 解析SPARQL查询
            query_info = self._parse_sparql_query(sparql_query)

            # 智能选择最佳的SQL映射 - 改进版
            best_mapping = self._select_best_mapping_improved(query_info)
            if not best_mapping:
                return "-- ERROR: 未找到匹配的SQL映射"

            print(f"选择的SQL映射: {best_mapping.mapping_id}")
            print(f"复杂度评分: {best_mapping.complexity_score}")
            print(f"覆盖变量: {list(best_mapping.column_mappings.keys())}")

            # 基于映射构建SQL查询
            final_sql = self._build_sql_from_mapping(query_info, best_mapping)

            print(f"\n生成的SQL查询:")
            print(final_sql)

            return final_sql

        except Exception as e:
            print(f"转换过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
            return f"-- ERROR: 转换失败 - {str(e)}"

    def _parse_sparql_query(self, sparql_query: str) -> Dict:
        print(f"\n🔍 接收到的原始SPARQL查询:\n{sparql_query}\n")
        """解析SPARQL查询"""
        query_info = {
            'prefixes': {},
            'select_vars': [],
            'triple_patterns': [],
            'filters': [],
            'distinct': False,
            'required_predicates': set(),
            'required_variables': set(),
            'var_to_predicates': {}  # 变量映射到其使用的谓词
        }

        # 提取前缀
        prefix_pattern = r'PREFIX\s+(\w+):\s*<([^>]+)>'
        for match in re.finditer(prefix_pattern, sparql_query, re.IGNORECASE):
            query_info['prefixes'][match.group(1)] = match.group(2)

        # 提取SELECT变量
        select_match = re.search(r'SELECT\s+(DISTINCT\s+)?(.*?)\s+WHERE', sparql_query, re.IGNORECASE | re.DOTALL)
        if select_match:
            if select_match.group(1):
                query_info['distinct'] = True
            vars_str = select_match.group(2).strip()
            select_vars = [v.strip()[1:] for v in vars_str.split() if v.strip().startswith('?')]
            query_info['select_vars'] = select_vars
            query_info['required_variables'].update(select_vars)

        # 提取WHERE子句
        where_match = re.search(r'WHERE\s*\{(.*?)\}', sparql_query, re.DOTALL | re.IGNORECASE)
        if where_match:
            where_content = where_match.group(1)

            # 提取FILTER条件
            where_content = self._extract_filters(where_content, query_info)

            # 解析三元组模式
            self._parse_triple_patterns(where_content, query_info)

        print(f"解析后的SELECT变量: {query_info['select_vars']}")
        print(f"解析后的变量到谓词映射: {query_info['var_to_predicates']}")

        return query_info

    def _extract_filters(self, content: str, query_info: Dict) -> str:
        """提取FILTER条件，保留占位符"""
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
            query_info['required_variables'].add(match.group(1))
            result_content = result_content.replace(match.group(0), '')

        # 处理IN条件（包括占位符） - 修复版本
        in_pattern = r'FILTER\s*\(\s*\?(\w+)\s+IN\s*\(([^)]+)\)\s*\)'
        for match in re.finditer(in_pattern, result_content, re.IGNORECASE):
            variable = match.group(1)
            value = match.group(2).strip()

            filter_info = {
                'variable': variable,
                'operator': 'IN',
                'value': value,
                'is_placeholder': '<<SUBQUERY_' in value and '>>' in value
            }
            query_info['filters'].append(filter_info)
            query_info['required_variables'].add(variable)
            result_content = result_content.replace(match.group(0), '')

        return result_content

    def _parse_triple_patterns(self, content: str, query_info: Dict):
        """解析三元组模式"""
        # 按句号分割三元组
        patterns = re.split(r'\.\s*(?=\?|\w+:)', content)

        for pattern in patterns:
            pattern = pattern.strip().rstrip('.')
            if not pattern or 'FILTER' in pattern.upper():
                continue

            triple = self._parse_single_triple(pattern, query_info['prefixes'])
            if triple:
                query_info['triple_patterns'].append(triple)
                # 收集需要的谓词
                predicate = triple['predicate']
                if not predicate.endswith('22-rdf-syntax-ns#type'):
                    query_info['required_predicates'].add(predicate)

                # 收集变量并记录变量与谓词的关系
                obj = triple['object'].strip()
                if obj.startswith('?'):
                    var_name = obj[1:]
                    query_info['required_variables'].add(var_name)
                    if var_name not in query_info['var_to_predicates']:
                        query_info['var_to_predicates'][var_name] = []
                    query_info['var_to_predicates'][var_name].append(predicate)

    def _parse_single_triple(self, pattern: str, prefixes: Dict) -> Dict:
        """解析单个三元组"""
        parts = pattern.split(None, 2)
        if len(parts) < 3:
            return None

        subject, predicate, obj = parts[0], parts[1], ' '.join(parts[2:])

        # 展开前缀
        predicate = self._expand_prefix(predicate, prefixes)

        return {
            'subject': subject,
            'predicate': predicate,
            'object': obj,
            'raw': pattern
        }

    def _expand_prefix(self, term: str, prefixes: Dict) -> str:
        """展开前缀"""
        if ':' in term and not term.startswith('http'):
            prefix, local = term.split(':', 1)
            if prefix in prefixes:
                return prefixes[prefix] + local
        return term

    def _select_best_mapping_improved(self, query_info: Dict) -> Optional[SQLMapping]:
        """改进的映射选择算法，零硬编码"""
        if not self.sql_mappings:
            return None

        required_vars = query_info['required_variables']
        required_predicates = query_info['required_predicates']

        print(f"查询需要的变量: {required_vars}")
        print(f"查询需要的谓词: {required_predicates}")

        # 评分系统
        mapping_scores = []

        for mapping in self.sql_mappings:
            score = 0

            # 1. 变量覆盖度评分（最重要）
            mapping_vars = set(mapping.column_mappings.keys())
            var_coverage = len(required_vars & mapping_vars) / len(required_vars) if required_vars else 0
            score += var_coverage * 100

            # 2. 谓词匹配评分
            pred_matches = 0
            for pred in required_predicates:
                if pred in mapping.covered_predicates:
                    pred_matches += 1
                elif pred == mapping.predicate_uri:
                    pred_matches += 1
                else:
                    # 关键词匹配
                    pred_keywords = pred.split('#')[-1].split('_') if '#' in pred else pred.split('/')[-1].split('_')
                    mapping_keywords = mapping.predicate_uri.split('#')[-1].split(
                        '_') if '#' in mapping.predicate_uri else mapping.predicate_uri.split('/')[-1].split('_')
                    overlap = len(set(pred_keywords) & set(mapping_keywords))
                    if overlap >= 2:
                        pred_matches += 0.5

            pred_score = pred_matches / len(required_predicates) if required_predicates else 0
            score += pred_score * 50

            # 3. 复杂度奖励（复杂查询优先）
            score += mapping.complexity_score * 0.1

            mapping_scores.append((mapping, score, var_coverage, pred_score))
            print(
                f"映射 {mapping.mapping_id}: 总分={score:.2f}, 变量覆盖={var_coverage:.2f}, 谓词匹配={pred_score:.2f}")

        # 按总分排序
        mapping_scores.sort(key=lambda x: x[1], reverse=True)

        # 选择最佳映射
        if mapping_scores:
            best_mapping = mapping_scores[0][0]
            print(f"选择最佳映射: {best_mapping.mapping_id}")
            return best_mapping

        return None

    def _build_sql_from_mapping(self, query_info: Dict, mapping: SQLMapping) -> str:
        """基于映射构建SQL查询，零硬编码"""
        base_sql = mapping.sql_query

        # 建立SPARQL变量到SQL列的映射
        var_to_column = self._map_sparql_vars_to_columns(query_info, mapping)

        print(f"\n变量到列映射: {var_to_column}")

        # 应用过滤条件
        sql_with_filters = self._apply_all_filters_data_driven(base_sql, query_info, mapping, var_to_column)

        # 构建SELECT子句
        final_sql = self._build_select_data_driven(sql_with_filters, query_info, mapping, var_to_column)

        return final_sql

    def _map_sparql_vars_to_columns(self, query_info: Dict, mapping: SQLMapping) -> Dict[str, str]:
        """
        将SPARQL变量映射到SQL列名 - 完全修复版

        正确处理：
        1. 对象属性（关系）：?abstract is_the_1th_part_of ?paper
        2. 数据属性：?abstract has_text ?text
        3. 主语实体变量
        """
        var_to_column = {}

        print(f"\n🔍 开始变量到列映射")
        print(f"SELECT变量: {query_info['select_vars']}")
        print(f"所有变量: {query_info['required_variables']}")

        # 第一步：处理对象属性（关系三元组）
        print(f"\n--- 第一步：处理对象属性（关系） ---")
        for triple in query_info['triple_patterns']:
            pred = triple['predicate']

            # 跳过type声明
            if 'type' in pred.lower():
                continue

            subj = triple['subject'].strip('?')
            obj = triple['object'].strip('?')

            # 判断：如果宾语是变量，这是对象属性
            if obj in query_info['required_variables']:
                # 获取谓词的本地名称
                pred_local = pred.split('#')[-1] if '#' in pred else pred.split('/')[-1]

                # 关键映射：宾语变量 -> 谓词名称（作为列名）
                var_to_column[obj] = pred_local
                print(f"✓ 对象属性: {subj} --[{pred_local}]--> {obj}")
                print(f"  映射: {obj} -> 列名 {pred_local}")

        # 第二步：处理数据属性（谓词->列映射）
        print(f"\n--- 第二步：处理数据属性 ---")
        for var, predicates in query_info.get('var_to_predicates', {}).items():
            if var in var_to_column:
                continue  # 已经映射过了

            for pred in predicates:
                pred_local = pred.split('#')[-1] if '#' in pred else pred.split('/')[-1]

                # 在mapping中查找匹配的列
                for col_name in mapping.column_mappings.keys():
                    if pred_local.lower() in col_name.lower() or col_name.lower() in pred_local.lower():
                        var_to_column[var] = col_name
                        print(f"✓ 数据属性: 变量 {var} -> 列 {col_name}")
                        break

        # 第三步：处理SELECT变量的直接映射
        print(f"\n--- 第三步：处理SELECT变量 ---")
        for var in query_info['select_vars']:
            if var not in var_to_column:
                # 尝试直接匹配列名
                for col_name in mapping.column_mappings.keys():
                    if var.lower() == col_name.lower() or var in col_name.lower():
                        var_to_column[var] = col_name
                        print(f"✓ 直接映射: 变量 {var} -> 列 {col_name}")
                        break

        print(f"\n📊 最终映射结果: {var_to_column}")
        return var_to_column
    def _extract_subject_key_from_mapping(self, mapping: SQLMapping) -> str:
        """
        从SQL映射中提取主键列

        解析pattern：
        - SQL: SELECT Person as person_id, ...
        - Template: http://conference#person_{person_id}

        返回: "person_id"
        """
        sql = mapping.sql_query

        # 方法1: 从SELECT子句中找第一个列（通常是主键）
        select_match = re.search(r'SELECT\s+(?:DISTINCT\s+)?(\w+)\s+as\s+(\w+)', sql, re.IGNORECASE)
        if select_match:
            first_column_alias = select_match.group(2)
            print(f"从SELECT提取主键: {first_column_alias}")
            return first_column_alias

        # 方法2: 查找包含"id"的列
        for col_name in mapping.column_mappings.keys():
            if 'id' in col_name.lower():
                print(f"从列名推断主键: {col_name}")
                return col_name

        # 方法3: 返回第一个列
        if mapping.column_mappings:
            first_col = list(mapping.column_mappings.keys())[0]
            print(f"使用第一个列作为主键: {first_col}")
            return first_col

        return None

    def _identify_subject_variables(self, query_info: Dict) -> Set[str]:
        """
        识别SPARQL中的主语变量

        规则：
        1. 出现在 rdf:type 三元组的主语
        2. 出现在其他三元组的主语且不是宾语
        """
        subject_vars = set()

        for triple in query_info['triple_patterns']:
            subject = triple['subject'].strip('?')
            predicate = triple['predicate']

            # 如果是类型声明，主语就是实体变量
            if predicate == 'a' or 'type' in predicate.lower():
                subject_vars.add(subject)
                continue

            # 如果主语出现在数据属性中，也是实体变量
            pred_name = predicate.split('#')[-1] if '#' in predicate else predicate
            # 检查是否是数据属性（而非关系）
            obj = triple['object'].strip('?')
            if obj in query_info['select_vars'] or obj.startswith('"'):
                subject_vars.add(subject)

        return subject_vars

    def _apply_all_filters_data_driven(self, sql: str, query_info: Dict, mapping: SQLMapping,
                                       var_to_column: Dict[str, str]) -> str:
        """
        数据驱动的所有过滤条件应用 - 改进版

        关键改进：正确处理主语变量的过滤条件
        """
        conditions = []

        # 处理FILTER条件
        for filter_info in query_info['filters']:
            var_name = filter_info['variable']
            operator = filter_info['operator']
            value = filter_info['value']

            # 🔥 改进：检查变量是否在映射中
            if var_name not in var_to_column:
                print(f"⚠️ 警告: FILTER变量 {var_name} 未找到列映射，尝试智能推断...")
                # 尝试从列名中推断（例如：person -> person_id）
                potential_col = f"{var_name}_id"
                if potential_col in mapping.column_mappings:
                    var_to_column[var_name] = potential_col
                    print(f"✓ 推断映射: {var_name} -> {potential_col}")
                else:
                    print(f"✗ 无法推断，跳过此FILTER")
                    continue

            col_name = var_to_column[var_name]

            # 🔥 改进：获取WHERE表达式
            if col_name in mapping.column_mappings:
                where_expr = mapping.column_mappings[col_name].where_expression
            else:
                # 如果列不在映射中，直接使用列名
                where_expr = col_name

            print(f"FILTER映射: {var_name} -> {col_name} -> {where_expr}")

            if operator == 'IN':
                # 保留占位符或值列表
                conditions.append(f"{where_expr} IN ({value})")
                print(f"✓ 添加IN条件: {where_expr} IN ({value})")
            elif operator == '=':
                conditions.append(f"{where_expr} = '{value}'")
                print(f"✓ 添加等值条件: {where_expr} = '{value}'")

        # 处理三元组中的字面值过滤条件（原有逻辑保持不变）
        for tp in query_info['triple_patterns']:
            obj = tp['object'].strip()
            predicate = tp['predicate']

            if obj.startswith('"') and obj.endswith('"'):
                literal_value = obj[1:-1]
                pred_name = predicate.split('#')[-1] if '#' in predicate else predicate.split('/')[-1]

                found = False
                for col_name, col_mapping in mapping.column_mappings.items():
                    if pred_name.lower() in col_name.lower() or col_name.lower() in pred_name.lower():
                        where_expr = col_mapping.where_expression
                        conditions.append(f"{where_expr} = '{literal_value}'")
                        print(f"✓ 三元组过滤: {pred_name} -> {where_expr} = '{literal_value}'")
                        found = True
                        break

        # 应用所有条件
        if conditions:
            if 'WHERE' in sql.upper():
                sql += f" AND {' AND '.join(conditions)}"
            else:
                sql += f" WHERE {' AND '.join(conditions)}"
            print(f"\n✓ 最终SQL: {sql}")

        return sql

    def _build_select_data_driven(self, sql: str, query_info: Dict, mapping: SQLMapping,
                                  var_to_column: Dict[str, str]) -> str:
        """数据驱动的SELECT子句构建，零硬编码"""
        if not query_info['select_vars']:
            return sql

        select_expressions = []

        for var in query_info['select_vars']:
            col_name = var_to_column.get(var, var)

            if col_name in mapping.column_mappings:
                column_mapping = mapping.column_mappings[col_name]
                select_expressions.append(column_mapping.select_expression)
                print(f"SELECT映射: {var} -> {col_name} -> {column_mapping.select_expression}")
            else:
                # 使用列名作为后备
                select_expressions.append(col_name)
                print(f"警告: 未找到变量 {var} 的完整SELECT映射，使用列名 {col_name}")

        # 构建新的SELECT子句
        distinct_clause = "DISTINCT " if query_info['distinct'] else ""
        new_select = f"SELECT {distinct_clause}{', '.join(select_expressions)}"

        # 替换原SQL的SELECT部分
        sql = re.sub(r'SELECT\s+(DISTINCT\s+)?.*?\s+FROM', f'{new_select} FROM', sql,
                     flags=re.IGNORECASE | re.DOTALL)

        return sql


def main():
    """测试真正零硬编码的转换器"""
    print("初始化真正零硬编码的SPARQL到MySQL转换器")

    ttl_files = ["data/RODI/rodi_mysql.ttl"]
    converter = SparqlToMySQLConverter(ttl_files)

    test_query = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT DISTINCT ?paper_id ?abstract_text
WHERE {
  ?abstract rdf:type conf:Abstract .
  ?abstract conf:is_the_1th_part_of ?paper_id .
  ?abstract conf:has_text ?abstract_text .
  FILTER (?paper_id IN (0, 600))
}
    """

    result = converter.convert_sparql_to_mysql(test_query)


if __name__ == "__main__":
    main()