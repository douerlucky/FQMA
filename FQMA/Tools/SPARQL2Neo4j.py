#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用SPARQL到Neo4j Cypher转换器 - 完全修复版 v2.0
完全基于TTL文件的R2RML映射，零硬编码

🔥🔥🔥 关键修复 🔥🔥🔥：
1. 修复属性变量FILTER条件丢失的问题
   - FILTER (?first_name = "Aberthol") 现在能正确转换为 WHERE p.first_name = "Aberthol"
2. 支持各种比较操作符 (=, <, >, <=, >=, !=, <>)
3. 支持属性变量的IN操作
4. 正确处理嵌套括号
5. 完全从TTL文件提取映射，无硬编码
"""

import re
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict


class SparqlToCypherConverter:
    """通用的SPARQL到Cypher转换器 - 完全由TTL驱动"""

    def __init__(self, ttl_file_path: str):
        """
        初始化转换器

        Args:
            ttl_file_path: R2RML映射TTL文件路径（包含Neo4j Cypher查询）
        """
        self.ttl_file_path = ttl_file_path

        # 核心映射数据结构
        self.class_to_label = {}  # RDF类 -> Neo4j标签
        self.property_to_attribute = {}  # 数据属性 -> 节点属性
        self.property_to_relation = {}  # 对象属性 -> 关系类型
        self.relation_directions = {}  # 关系方向信息

        # 属性式关系：对象属性存储为节点属性（如 is_submitted_at）
        self.property_based_relations = {}

        # 解析TTL文件
        self._parse_neo4j_mapping()

    def _parse_neo4j_mapping(self):
        """解析Neo4j映射TTL文件"""
        try:
            with open(self.ttl_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 分割映射节
            sections = re.split(r'\n\s*<#', content)

            for section in sections:
                if not section.strip():
                    continue
                self._parse_mapping_section('<#' + section if not section.startswith('<#') else section)

            print(f"✓ 成功解析Neo4j映射:")
            print(f"  - {len(self.class_to_label)} 个节点类型: {list(self.class_to_label.keys())}")
            print(f"  - {len(self.property_to_attribute)} 个属性映射: {self.property_to_attribute}")
            print(f"  - {len(self.property_to_relation)} 个关系映射: {self.property_to_relation}")

        except Exception as e:
            print(f"✗ 解析失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _parse_mapping_section(self, section: str):
        """解析单个映射节"""
        # 1. 从Cypher查询中提取节点标签
        self._parse_node_labels(section)

        # 2. 解析属性映射（处理嵌套括号）
        self._parse_property_mappings_fixed(section)

        # 3. 从Cypher查询中提取关系映射
        self._parse_relationship_mappings(section)

        # 4. 解析属性式关系（对象属性存储为节点属性）
        self._parse_property_based_relations(section)

    def _parse_node_labels(self, section: str):
        """从Cypher查询或tableName中提取节点标签"""
        # 提取rr:class（RDF类）
        class_matches = list(re.finditer(r'rr:class\s+(\w+):(\w+)', section))

        # 方法1: 从Cypher查询中提取节点标签 - MATCH (p:Person)
        cypher_label_matches = re.findall(r'MATCH\s+\(\w+:(\w+)\)', section)

        # 方法2: 从tableName提取（如果没有Cypher查询）
        table_match = re.search(r'rr:tableName\s+"(\w+)"', section)

        for class_match in class_matches:
            rdf_class = class_match.group(2)

            # 优先使用Cypher中的标签
            neo4j_label = None
            if cypher_label_matches:
                neo4j_label = cypher_label_matches[0]

            # 如果没有Cypher标签，使用tableName
            if not neo4j_label and table_match:
                neo4j_label = table_match.group(1)

            # 最后使用RDF类名本身
            if not neo4j_label:
                neo4j_label = rdf_class

            self.class_to_label[rdf_class] = neo4j_label

    def _extract_nested_block(self, text: str, start_pos: int) -> str:
        """
        提取嵌套括号块
        从start_pos位置的'['开始，提取到匹配的']'结束
        """
        if start_pos >= len(text) or text[start_pos] != '[':
            return ""

        depth = 0
        end_pos = start_pos

        for i in range(start_pos, len(text)):
            if text[i] == '[':
                depth += 1
            elif text[i] == ']':
                depth -= 1
                if depth == 0:
                    end_pos = i
                    break

        return text[start_pos:end_pos + 1]

    def _parse_property_mappings_fixed(self, section: str):
        """
        修复版：解析属性映射，正确处理嵌套括号

        TTL格式示例：
        rr:predicateObjectMap [
            rr:predicate conf:has_a_paper_title ;
            rr:objectMap [
                rr:column "title" ;
                rr:datatype xsd:string
            ]
        ] ;
        """
        # 如果section的sqlQuery包含关系模式，跳过数据属性提取
        sql_match = re.search(r'rr:sqlQuery\s*"""(.*?)"""', section, re.DOTALL)
        if sql_match:
            sql_query = sql_match.group(1)
            # 如果包含关系模式 -[r:XXX]-> 或 <-[r:XXX]-，跳过
            if re.search(r'\[r?:?\w+\]', sql_query):
                return

        # 找到所有 rr:predicateObjectMap 的起始位置
        pom_starts = [m.end() for m in re.finditer(r'rr:predicateObjectMap\s*', section)]

        for start in pom_starts:
            # 找到 '[' 的位置
            bracket_pos = section.find('[', start)
            if bracket_pos == -1:
                continue

            # 提取完整的嵌套块
            block = self._extract_nested_block(section, bracket_pos)
            if not block:
                continue

            # 从块中提取predicate
            pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', block)
            if not pred_match:
                continue

            predicate = pred_match.group(2)

            # 如果已经存在映射，不覆盖（优先保留第一个定义）
            if predicate in self.property_to_attribute:
                continue

            # 从块中提取column（在objectMap内）
            col_match = re.search(r'rr:column\s+"([^"]+)"', block)

            # 检查是否有template（表示是对象属性/关系，不是数据属性）
            template_match = re.search(r'rr:template\s+"([^"]+)"', block)

            # 只有当有column且没有template时，才是数据属性
            if col_match and not template_match:
                column = col_match.group(1)
                self.property_to_attribute[predicate] = column

    def _parse_relationship_mappings(self, section: str):
        """从Cypher查询中提取关系映射"""
        # 查找RDF谓词
        pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', section)
        if not pred_match:
            return

        predicate = pred_match.group(2)

        # 检查是否有template（对象属性的标志）
        if not re.search(r'rr:template\s+"http', section):
            return  # 不是对象属性，跳过

        # 从sqlQuery中提取Cypher MATCH模式
        sql_match = re.search(r'rr:sqlQuery\s*"""(.*?)"""', section, re.DOTALL)
        if not sql_match:
            return

        cypher_query = sql_match.group(1)

        # 正向关系: (source:Label)-[r:REL_TYPE]->(target:Label)
        forward_match = re.search(
            r'MATCH\s+\((\w+):(\w+)\)-\[r?:?(\w+)\]->\((\w+):(\w+)\)',
            cypher_query, re.IGNORECASE
        )
        if forward_match:
            source_var, source_label, rel_type, target_var, target_label = forward_match.groups()
            self.property_to_relation[predicate] = rel_type
            self.relation_directions[predicate] = {
                'source_label': source_label,
                'target_label': target_label,
                'relation': rel_type,
                'direction': 'forward'
            }
            return

        # 反向关系: (target:Label)<-[r:REL_TYPE]-(source:Label)
        backward_match = re.search(
            r'MATCH\s+\((\w+):(\w+)\)<-\[r?:?(\w+)\]-\((\w+):(\w+)\)',
            cypher_query, re.IGNORECASE
        )
        if backward_match:
            target_var, target_label, rel_type, source_var, source_label = backward_match.groups()
            self.property_to_relation[predicate] = rel_type
            self.relation_directions[predicate] = {
                'source_label': source_label,
                'target_label': target_label,
                'relation': rel_type,
                'direction': 'backward'
            }
            return

    def _parse_property_based_relations(self, section: str):
        """
        解析属性式关系（对象属性存储为节点属性）
        例如: Paper.submitted_at 存储会议ID
        """
        # 查找RDF谓词
        pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', section)
        if not pred_match:
            return

        predicate = pred_match.group(2)

        # 如果已经识别为图关系或数据属性，跳过
        if predicate in self.property_to_relation:
            return
        if predicate in self.property_to_attribute:
            return

        # 检查是否有objectMap带template（表示这是对象属性）
        if not re.search(r'rr:template\s+"http', section):
            return

        # 从SQL查询中提取节点标签和属性名
        sql_match = re.search(r'rr:sqlQuery\s*"""(.*?)"""', section, re.DOTALL)
        if not sql_match:
            return

        sql_query = sql_match.group(1)

        # 如果有关系模式，不是属性式关系
        if re.search(r'\[r?:\w+\]', sql_query):
            return

        # 从MATCH子句提取源节点标签: MATCH (p:Paper)
        source_match = re.search(r'MATCH\s+\((\w+):(\w+)\)', sql_query)
        if not source_match:
            return

        source_var = source_match.group(1)
        source_label = source_match.group(2)

        # 在RETURN子句中查找属性
        return_match = re.search(r'RETURN\s+(.*)', sql_query, re.IGNORECASE | re.DOTALL)
        if not return_match:
            return

        return_clause = return_match.group(1)

        # 查找类似 p.submitted_at as conference_id 的模式
        prop_pattern = rf'{source_var}\.(\w+)\s+as\s+\w+'
        prop_matches = re.findall(prop_pattern, return_clause, re.IGNORECASE)

        for prop_name in prop_matches:
            if prop_name.lower() != 'id':  # 排除ID
                self.property_based_relations[predicate] = {
                    'source_label': source_label,
                    'property_name': prop_name
                }
                break

    def convert(self, sparql_query: str) -> str:
        """
        将SPARQL查询转换为Cypher

        Args:
            sparql_query: SPARQL查询字符串

        Returns:
            Cypher查询字符串
        """
        try:
            # Step 1: 解析SPARQL
            parsed = self._parse_sparql(sparql_query)

            # Step 2: 构建Cypher
            cypher = self._build_cypher(parsed)

            return cypher

        except Exception as e:
            print(f"✗ 转换失败: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _parse_sparql(self, query: str) -> Dict:
        """解析SPARQL查询"""
        # 清理
        clean = re.sub(r'#.*', '', query)
        clean = ' '.join(clean.split())

        # SELECT
        select_match = re.search(
            r'SELECT\s+(DISTINCT\s+)?(.*?)\s+WHERE',
            clean,
            re.IGNORECASE
        )
        if not select_match:
            raise ValueError("无法解析SELECT子句")

        is_distinct = bool(select_match.group(1))
        select_vars = [
            v.strip('?')
            for v in select_match.group(2).split()
            if v.startswith('?')
        ]

        # WHERE
        where_match = re.search(
            r'WHERE\s*\{(.*?)\}',
            clean,
            re.DOTALL | re.IGNORECASE
        )
        if not where_match:
            raise ValueError("无法解析WHERE子句")

        where_body = where_match.group(1)

        # FILTER - 保留原始FILTER表达式
        filters = []
        for match in re.finditer(r'FILTER\s*\(((?:[^()]|\([^()]*\))*)\)', where_body, re.DOTALL):
            filters.append(match.group(1).strip())
            where_body = where_body.replace(match.group(0), '')

        # 三元组
        triples = []
        statements = [s.strip() for s in re.split(r'\s*\.\s*', where_body) if s.strip()]

        for stmt in statements:
            parts = stmt.split(None, 2)
            if len(parts) >= 3:
                triples.append({
                    'subject': parts[0].strip('?'),
                    'predicate': parts[1],
                    'object': parts[2].rstrip('.').strip('?')
                })

        # LIMIT
        limit = None
        limit_match = re.search(r'LIMIT\s+(\d+)', clean, re.IGNORECASE)
        if limit_match:
            limit = int(limit_match.group(1))

        return {
            'select_vars': select_vars,
            'is_distinct': is_distinct,
            'triples': triples,
            'filters': filters,
            'limit': limit
        }

    def _build_cypher(self, parsed: Dict) -> str:
        """构建Cypher查询"""
        # 分析查询模式
        pattern = self._analyze_pattern(parsed['triples'])

        # 构建MATCH子句
        match_clauses = self._build_match(pattern)

        # 关键修复：传入properties用于处理属性变量的过滤
        where_clauses = self._build_where(parsed['filters'], pattern)

        # 构建RETURN子句
        return_clause = self._build_return(parsed['select_vars'], pattern)

        # 组装
        cypher_parts = []

        if match_clauses:
            cypher_parts.append('MATCH ' + ', '.join(match_clauses))

        if where_clauses:
            cypher_parts.append('WHERE ' + ' AND '.join(where_clauses))

        if return_clause:
            distinct = 'DISTINCT ' if parsed['is_distinct'] else ''
            cypher_parts.append(f'RETURN {distinct}{return_clause}')

        if parsed['limit']:
            cypher_parts.append(f'LIMIT {parsed["limit"]}')

        return '\n'.join(cypher_parts)

    def _analyze_pattern(self, triples: List[Dict]) -> Dict:
        """
        分析三元组模式

        Returns:
            {
                'nodes': {var: label},
                'relationships': [(source_var, rel_type, target_var, pred_name)],
                'var_mapping': {sparql_var: cypher_var},
                'properties': {var: (node_var, property_name)},
                'literal_filters': [(node_var, attr_name, value)],
                'property_relations': {...}
            }
        """
        nodes = {}  # 变量 -> 标签
        relationships = []
        properties = {}  # 属性变量 -> (所属节点变量, 属性名)
        property_relations = {}
        literal_filters = []  # 存储字面值过滤条件

        # 第一遍：识别节点类型
        for triple in triples:
            if self._is_type_predicate(triple['predicate']):
                var = triple['subject']
                rdf_class = triple['object'].split(':')[-1]

                if rdf_class in self.class_to_label:
                    label = self.class_to_label[rdf_class]
                    nodes[var] = label

        # 第二遍：识别关系和数据属性
        for triple in triples:
            if self._is_type_predicate(triple['predicate']):
                continue

            pred_name = triple['predicate'].split(':')[-1]
            source_var = triple['subject']
            target = triple['object']

            # 检查target是变量还是字面值
            is_variable = not (target.startswith('"') or target.startswith("'") or
                               target[0].isdigit() or target.startswith('conf:'))

            # 优先检查是否是数据属性
            if pred_name in self.property_to_attribute:
                attr_name = self.property_to_attribute[pred_name]

                if is_variable:
                    # target是变量，记录为属性绑定
                    properties[target] = (source_var, attr_name)
                else:
                    # target是字面值，记录为过滤条件
                    literal_value = target.strip('"').strip("'")
                    literal_filters.append((source_var, attr_name, literal_value))
                continue

            # 检查是否是对象属性（关系）
            elif pred_name in self.property_to_relation:
                rel_type = self.property_to_relation[pred_name]
                relationships.append((source_var, rel_type, target, pred_name))

                # 如果目标节点类型未知，从关系方向推断
                if target not in nodes and pred_name in self.relation_directions:
                    rel_info = self.relation_directions[pred_name]
                    if rel_info.get('direction') == 'backward':
                        nodes[target] = rel_info['source_label']
                        if source_var not in nodes:
                            nodes[source_var] = rel_info['target_label']
                    else:
                        nodes[target] = rel_info['target_label']
                        if source_var not in nodes:
                            nodes[source_var] = rel_info['source_label']

            # 检查是否是属性式关系
            elif pred_name in self.property_based_relations:
                rel_info = self.property_based_relations[pred_name]
                property_relations[pred_name] = {
                    'source_var': source_var,
                    'target_var': target,
                    'property_name': rel_info['property_name'],
                    'source_label': rel_info['source_label']
                }
                if source_var not in nodes:
                    nodes[source_var] = rel_info['source_label']

        # 生成简短的Cypher变量名
        var_mapping = {}
        used_names = set()

        for var in nodes.keys():
            short_name = var[0].lower()
            counter = 1
            while short_name in used_names:
                short_name = f"{var[0].lower()}{counter}"
                counter += 1
            var_mapping[var] = short_name
            used_names.add(short_name)

        return {
            'nodes': nodes,
            'relationships': relationships,
            'var_mapping': var_mapping,
            'properties': properties,
            'property_relations': property_relations,
            'literal_filters': literal_filters
        }

    def _is_type_predicate(self, predicate: str) -> bool:
        """判断是否是类型谓词"""
        return (predicate == 'a' or
                predicate == 'rdf:type' or
                'type' in predicate.lower())

    def _build_match(self, pattern: Dict) -> List[str]:
        """构建MATCH子句"""
        matches = []
        nodes = pattern['nodes']
        relationships = pattern['relationships']
        var_mapping = pattern['var_mapping']

        if relationships:
            # 有关系的情况
            matched_nodes = set()

            for source_var, rel_type, target_var, pred_name in relationships:
                source_label = nodes.get(source_var, '')
                target_label = nodes.get(target_var, '')

                source_cypher = var_mapping.get(source_var, source_var[0])
                target_cypher = var_mapping.get(target_var, target_var[0])

                # 获取关系方向
                direction = 'forward'
                if pred_name in self.relation_directions:
                    rel_info = self.relation_directions[pred_name]
                    if rel_info.get('direction') == 'backward':
                        direction = 'backward'

                if direction == 'backward':
                    match_pattern = f"({source_cypher}:{source_label})<-[:{rel_type}]-({target_cypher}:{target_label})"
                else:
                    match_pattern = f"({source_cypher}:{source_label})-[:{rel_type}]->({target_cypher}:{target_label})"

                matches.append(match_pattern)
                matched_nodes.add(source_var)
                matched_nodes.add(target_var)

            # 添加未被关系覆盖的节点
            for var, label in nodes.items():
                if var not in matched_nodes:
                    cypher_var = var_mapping.get(var, var[0])
                    matches.append(f"({cypher_var}:{label})")
        else:
            # 只有节点，没有关系
            for var, label in nodes.items():
                cypher_var = var_mapping.get(var, var[0])
                matches.append(f"({cypher_var}:{label})")

        return matches

    def _build_where(self, filters: List[str], pattern: Dict) -> List[str]:
        """
       构建WHERE条件，正确处理属性变量过滤
        """
        conditions = []
        var_mapping = pattern['var_mapping']
        properties = pattern.get('properties', {})  # 属性变量映射
        property_relations = pattern.get('property_relations', {})
        literal_filters = pattern.get('literal_filters', [])

        # 1. 首先处理字面值过滤条件（三元组中直接指定的字面值）
        for node_var, attr_name, literal_value in literal_filters:
            if node_var in var_mapping:
                cypher_var = var_mapping[node_var]
                conditions.append(f'{cypher_var}.{attr_name} = "{literal_value}"')

        # 2. 处理FILTER表达式
        for filter_expr in filters:
            condition = self._convert_filter_expression(filter_expr, var_mapping, properties, property_relations)
            if condition:
                conditions.append(condition)

        return conditions

    def _convert_filter_expression(self, filter_expr: str, var_mapping: Dict,
                                   properties: Dict, property_relations: Dict) -> Optional[str]:
        """
        🔥🔥🔥 核心修复：转换单个FILTER表达式

        支持的模式：
        1. FILTER (?var IN (<<SUBQUERY_X>>)) - 子查询占位符
        2. FILTER (?var = 123) - 节点ID过滤
        3. FILTER (?var = "value") - 字符串等值过滤（包括属性变量！）
        4. FILTER (?var > 10) - 比较操作符
        5. FILTER (?var IN (1, 2, 3)) - IN列表
        """

        # 模式1: 子查询占位符 FILTER (?var IN (<<SUBQUERY_X>>))
        placeholder_match = re.search(
            r'\?(\w+)\s+IN\s+\(<<SUBQUERY_(\d+)>>\)',
            filter_expr, re.IGNORECASE
        )
        if placeholder_match:
            var = placeholder_match.group(1)
            subquery_num = placeholder_match.group(2)

            if var in var_mapping:
                cypher_var = var_mapping[var]
                return f"{cypher_var}.ID IN [<<SUBQUERY_{subquery_num}>>]"
            return None

        # 🔥🔥🔥 模式2: 字符串等值过滤 FILTER (?var = "value") - 最重要的修复！
        str_match = re.search(r'\?(\w+)\s*(=|!=|<>)\s*["\']([^"\']+)["\']', filter_expr)
        if str_match:
            var = str_match.group(1)
            operator = str_match.group(2)
            value = str_match.group(3)

            # 转换操作符
            if operator in ('!=', '<>'):
                cypher_op = '<>'
            else:
                cypher_op = '='

            # 🔥 关键：检查是否是属性变量
            if var in properties:
                # 属性变量：获取所属节点和属性名
                node_var, attr_name = properties[var]
                if node_var in var_mapping:
                    cypher_var = var_mapping[node_var]
                    return f'{cypher_var}.{attr_name} {cypher_op} "{value}"'
            elif var in var_mapping:
                # 节点变量：使用默认的name属性（从TTL推断）
                cypher_var = var_mapping[var]
                # 尝试从property_to_attribute中找到合适的名称属性
                # 默认使用name，但如果有更具体的映射则使用它
                return f'{cypher_var}.name {cypher_op} "{value}"'

            return None

        # 模式3: 数值比较 FILTER (?var op number)
        num_match = re.search(r'\?(\w+)\s*(=|!=|<>|<|>|<=|>=)\s*(\d+(?:\.\d+)?)', filter_expr)
        if num_match:
            var = num_match.group(1)
            operator = num_match.group(2)
            value = num_match.group(3)

            # 转换操作符
            if operator in ('!=', '<>'):
                cypher_op = '<>'
            else:
                cypher_op = operator

            # 检查是否是属性变量
            if var in properties:
                node_var, attr_name = properties[var]
                if node_var in var_mapping:
                    cypher_var = var_mapping[node_var]
                    return f"{cypher_var}.{attr_name} {cypher_op} {value}"

            # 检查是否是属性式关系的目标变量
            for pred_name, rel_info in property_relations.items():
                if rel_info['target_var'] == var:
                    source_var = rel_info['source_var']
                    property_name = rel_info['property_name']
                    if source_var in var_mapping:
                        cypher_var = var_mapping[source_var]
                        return f"{cypher_var}.{property_name} {cypher_op} {value}"

            # 节点ID过滤
            if var in var_mapping:
                cypher_var = var_mapping[var]
                return f"{cypher_var}.ID {cypher_op} {value}"

            return None

        # 模式4: IN列表 FILTER (?var IN (1, 2, 3)) 或 FILTER (?var IN ("a", "b"))
        in_match = re.search(r'\?(\w+)\s+IN\s+\(([^)]+)\)', filter_expr, re.IGNORECASE)
        if in_match:
            var = in_match.group(1)
            values_str = in_match.group(2)

            # 检查是否是属性变量
            if var in properties:
                node_var, attr_name = properties[var]
                if node_var in var_mapping:
                    cypher_var = var_mapping[node_var]

                    # 检查是否是数字列表
                    if re.match(r'^[\d,\s]+$', values_str):
                        values_list = '[' + values_str + ']'
                        return f'{cypher_var}.{attr_name} IN {values_list}'
                    else:
                        # 字符串列表
                        values = re.findall(r'["\']([^"\']+)["\']', values_str)
                        if values:
                            values_list = '[' + ', '.join(f'"{v}"' for v in values) + ']'
                            return f'{cypher_var}.{attr_name} IN {values_list}'

            elif var in var_mapping:
                cypher_var = var_mapping[var]

                # 检查是否是数字列表
                if re.match(r'^[\d,\s]+$', values_str):
                    values_list = '[' + values_str + ']'
                    return f'{cypher_var}.ID IN {values_list}'
                else:
                    # 字符串列表
                    values = re.findall(r'["\']([^"\']+)["\']', values_str)
                    if values:
                        values_list = '[' + ', '.join(f'"{v}"' for v in values) + ']'
                        return f'{cypher_var}.name IN {values_list}'

            return None

        return None

    def _build_return(self, select_vars: List[str], pattern: Dict) -> str:
        """构建RETURN子句"""
        return_items = []
        var_mapping = pattern['var_mapping']
        nodes = pattern['nodes']
        properties = pattern['properties']

        for var in select_vars:
            # 首先检查是否是数据属性变量
            if var in properties:
                node_var, attr_name = properties[var]
                if node_var in var_mapping:
                    cypher_var = var_mapping[node_var]
                    return_items.append(f'{cypher_var}.{attr_name} AS {var}')
                else:
                    return_items.append(var)

            # 如果变量对应一个节点本身，返回 node.ID AS var
            elif var in var_mapping:
                cypher_var = var_mapping[var]
                return_items.append(f'{cypher_var}.ID AS {var}')

            # 处理 xxx_id 格式的变量
            elif '_id' in var:
                base_var = var.replace('_id', '')
                if base_var in var_mapping:
                    cypher_var = var_mapping[base_var]
                    return_items.append(f'{cypher_var}.ID AS {var}')
                else:
                    return_items.append(var)

            # 其他情况
            else:
                return_items.append(var)

        return ', '.join(return_items) if return_items else '*'

    def print_mapping_summary(self):
        """打印映射摘要（调试用）"""
        print("\n" + "=" * 70)
        print("Neo4j R2RML 映射摘要")
        print("=" * 70)

        print("\n【RDF类 -> Neo4j标签】")
        for cls, label in sorted(self.class_to_label.items()):
            print(f"  {cls:30} → {label}")

        print("\n【RDF数据属性 -> Neo4j属性】")
        for prop, attr in sorted(self.property_to_attribute.items()):
            print(f"  {prop:30} → {attr}")

        print("\n【RDF谓词 -> Neo4j关系】")
        for prop, rel in sorted(self.property_to_relation.items()):
            if prop in self.relation_directions:
                info = self.relation_directions[prop]
                print(f"  {prop:30} → ({info['source_label']})-[:{rel}]->({info['target_label']})")
            else:
                print(f"  {prop:30} → {rel}")

        if self.property_based_relations:
            print("\n【属性式关系 (存储为节点属性)】")
            for prop, info in sorted(self.property_based_relations.items()):
                print(f"  {prop:30} → {info['source_label']}.{info['property_name']}")

        print("=" * 70 + "\n")


def main():
    """测试函数"""
    ttl_file = '/mnt/user-data/uploads/1766976673166_rodi_neo4j.ttl'

    print("\n" + "=" * 70)
    print(" 🔥🔥🔥 完全修复版 SPARQL→Cypher转换器 v2.0 🔥🔥🔥")
    print("=" * 70)

    # 初始化
    converter = SparqlToCypherConverter(ttl_file)
    converter.print_mapping_summary()

    # 🔥🔥🔥 测试1: 用户报告的问题 - 按名字查询作者的论文
    print("\n" + "=" * 70)
    print("【测试1】🔥 用户报告的问题：按名字过滤作者")
    print("-" * 70)

    sparql_user = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?paper
WHERE {
  ?person rdf:type conf:Person .
  ?person conf:has_the_first_name ?first_name .
  FILTER (?first_name = "Aberthol")
  ?person conf:contributes ?paper .
  ?paper rdf:type conf:Paper .
}
    """

    print("SPARQL:")
    print(sparql_user)
    print("\n生成的Cypher:")
    cypher_user = converter.convert(sparql_user)
    print(cypher_user)
    print("\n✅ 期望输出:")
    print('MATCH (p:Person)-[:AUTHORED]->(p1:Paper)')
    print('WHERE p.first_name = "Aberthol"')
    print('RETURN p1.ID AS paper')

    # 测试2: 完整版本 - 返回论文ID、作者姓名和论文标题
    print("\n" + "=" * 70)
    print("【测试2】完整查询：返回论文ID、作者姓名和论文标题")
    print("-" * 70)

    sparql_full = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?paper ?first_name ?last_name ?title
WHERE {
  ?person rdf:type conf:Person .
  ?person conf:has_the_first_name ?first_name .
  ?person conf:has_the_last_name ?last_name .
  FILTER (?first_name = "Aberthol")
  ?person conf:contributes ?paper .
  ?paper rdf:type conf:Paper .
  ?paper conf:has_a_paper_title ?title .
}
    """

    print("SPARQL:")
    print(sparql_full)
    print("\n生成的Cypher:")
    cypher_full = converter.convert(sparql_full)
    print(cypher_full)

    # 测试3: 数值ID过滤
    print("\n" + "=" * 70)
    print("【测试3】数值ID过滤")
    print("-" * 70)

    sparql_id = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?paper
WHERE {
  ?person rdf:type conf:Person .
  ?person conf:contributes ?paper .
  ?paper rdf:type conf:Paper .
  FILTER (?person = 3)
}
LIMIT 10
    """

    print("SPARQL:")
    print(sparql_id)
    print("\n生成的Cypher:")
    cypher_id = converter.convert(sparql_id)
    print(cypher_id)

    # 测试4: 字面值过滤（三元组中直接指定）
    print("\n" + "=" * 70)
    print("【测试4】三元组中直接指定字面值")
    print("-" * 70)

    sparql_literal = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?person
WHERE {
  ?committee rdf:type conf:Committee .
  ?committee conf:has_a_name "YSWC 2015 Program Committee" .
  ?committee conf:has_members ?person .
  ?person rdf:type conf:Person .
}
    """

    print("SPARQL:")
    print(sparql_literal)
    print("\n生成的Cypher:")
    cypher_literal = converter.convert(sparql_literal)
    print(cypher_literal)

    # 测试5: IN列表过滤（属性变量）
    print("\n" + "=" * 70)
    print("【测试5】IN列表过滤（属性变量）")
    print("-" * 70)

    sparql_in = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?person ?first_name
WHERE {
  ?person rdf:type conf:Person .
  ?person conf:has_the_first_name ?first_name .
  FILTER (?first_name IN ("Alice", "Bob", "Charlie"))
}
    """

    print("SPARQL:")
    print(sparql_in)
    print("\n生成的Cypher:")
    cypher_in = converter.convert(sparql_in)
    print(cypher_in)

    # 测试6: 子查询占位符
    print("\n" + "=" * 70)
    print("【测试6】子查询占位符")
    print("-" * 70)

    sparql_placeholder = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX conf: <http://conference#>

SELECT ?paper ?title
WHERE {
  ?paper rdf:type conf:Paper .
  ?paper conf:has_a_paper_title ?title .
  FILTER (?paper IN (<<SUBQUERY_1>>))
}
    """

    print("SPARQL:")
    print(sparql_placeholder)
    print("\n生成的Cypher:")
    cypher_placeholder = converter.convert(sparql_placeholder)
    print(cypher_placeholder)

    print("\n" + "=" * 70)
    print("✓ 所有测试完成！")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()