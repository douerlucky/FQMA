#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPARQL到Neo4j Cypher转换器 - rdflib版本
完全基于TTL文件的R2RML映射，零硬编码
使用rdflib解析SPARQL和TTL
"""

import re
from typing import Dict, List, Optional, Set
from collections import defaultdict
from rdflib import Graph, Namespace, RDF
from rdflib.plugins.sparql.parser import parseQuery


class SparqlToCypherConverter:
    """SPARQL到Cypher转换器 - 使用rdflib解析，零硬编码"""

    def __init__(self, ttl_file_path: str):
        """
        初始化转换器

        Args:
            ttl_file_path: R2RML映射TTL文件路径
        """
        self.ttl_file_path = ttl_file_path

        # 核心映射数据结构
        self.class_to_label = {}  # RDF类 -> Neo4j标签
        self.property_to_attribute = {}  # 数据属性 -> 节点属性
        self.property_to_relation = {}  # 对象属性 -> 关系类型
        self.property_to_label = {}  # 属性 -> 标签映射

        # RDF图和命名空间
        self.graph = Graph()
        self.graph.parse(ttl_file_path, format='turtle')
        self.rr = Namespace("http://www.w3.org/ns/r2rml#")
        self.conf = Namespace("http://conference#")

        # 解析映射
        self._parse_r2rml_mapping()

        print(f"成功解析Neo4j R2RML映射:")
        print(f"  - {len(self.class_to_label)} 个节点类型映射")
        print(f"  - {len(self.property_to_attribute)} 个属性映射")
        print(f"  - {len(self.property_to_relation)} 个关系映射")

    def _parse_r2rml_mapping(self):
        """从RDF图中解析R2RML映射"""
        # Neo4j TTL没有声明rdf:type rr:TriplesMap
        # 直接查找有rr:logicalTable的节点
        triples_maps = set()
        for s in self.graph.subjects(self.rr.logicalTable, None):
            triples_maps.add(s)
        for s in self.graph.subjects(self.rr.subjectMap, None):
            triples_maps.add(s)

        for triples_map in triples_maps:
            self._parse_triples_map(triples_map)

    def _extract_label_from_cypher(self, cypher_query: str) -> Optional[str]:
        """从Cypher查询中提取节点标签"""
        match = re.search(r'MATCH\s+\(\w+:(\w+)\)', cypher_query, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _parse_triples_map(self, triples_map):
        """解析单个TriplesMap"""
        logical_table = self.graph.value(triples_map, self.rr.logicalTable)
        if not logical_table:
            return

        sql_query = self.graph.value(logical_table, self.rr.sqlQuery)
        label = None
        if sql_query:
            label = self._extract_label_from_cypher(str(sql_query))

        subject_map = self.graph.value(triples_map, self.rr.subjectMap)
        if not subject_map:
            return

        rdf_class = self.graph.value(subject_map, self.rr['class'])
        if rdf_class and label:
            class_name = str(rdf_class).split('#')[-1]
            self.class_to_label[class_name] = label

        for pom in self.graph.objects(triples_map, self.rr.predicateObjectMap):
            self._parse_predicate_object_map(pom, label)

    def _parse_predicate_object_map(self, pom, label):
        """解析predicateObjectMap"""
        predicate = self.graph.value(pom, self.rr.predicate)
        if not predicate:
            return

        pred_name = str(predicate).split('#')[-1]

        object_map = self.graph.value(pom, self.rr.objectMap)
        if not object_map:
            return

        column = self.graph.value(object_map, self.rr.column)
        template = self.graph.value(object_map, self.rr.template)

        # 数据属性：使用rr:column
        if column and label:
            self.property_to_attribute[pred_name] = str(column)
            self.property_to_label[pred_name] = label
        # 对象属性：使用rr:template
        elif template and label:
            # 从template中提取列名或关系信息
            template_str = str(template)
            col_match = re.search(r'\{([^}]+)\}', template_str)
            if col_match:
                extracted_col = col_match.group(1)
                # 如果列名包含_id，说明是属性式外键
                if '_id' in extracted_col or extracted_col.endswith('_at'):
                    self.property_to_attribute[pred_name] = extracted_col
                    self.property_to_label[pred_name] = label
                else:
                    # 否则是真正的关系
                    target_class = template_str.split('#')[-1].split('_')[0]
                    self.property_to_relation[pred_name] = {
                        'type': pred_name.upper(),
                        'target': target_class
                    }

    def convert_sparql_to_cypher(self, sparql_query: str) -> str:
        """
        将SPARQL查询转换为Neo4j Cypher

        Args:
            sparql_query: SPARQL查询字符串

        Returns:
            Cypher查询字符串
        """
        parsed = self._parse_sparql_query(sparql_query)
        cypher = self._build_cypher(parsed)
        return cypher

    def _parse_sparql_query(self, query: str) -> Dict:
        """使用rdflib解析SPARQL，回退到正则表达式"""
        has_placeholder = '<<SUBQUERY_' in query

        if has_placeholder:
            temp_query = re.sub(r'<<SUBQUERY_\d+>>', '1, 2, 3', query)
        else:
            temp_query = query

        try:
            parsed_result = parseQuery(temp_query)
            result = {
                'select_vars': [],
                'triples': [],
                'filters': [],
                'has_placeholder': has_placeholder
            }

            # 提取SELECT变量
            if hasattr(parsed_result, 'algebra'):
                algebra = parsed_result.algebra
                if hasattr(algebra, 'PV'):
                    for var in algebra.PV:
                        result['select_vars'].append(str(var).strip('?'))

            # 提取WHERE子句
            if hasattr(parsed_result, 'algebra') and hasattr(parsed_result.algebra, 'p'):
                where_clause = parsed_result.algebra.p
                self._extract_triples_and_filters(where_clause, result)

            # 如果rdflib解析成功但结果为空，回退到regex
            if not result['select_vars'] and not result['triples']:
                return self._parse_sparql_query_regex(query)

            return result

        except Exception:
            # 回退到正则表达式解析
            return self._parse_sparql_query_regex(query)

    def _extract_triples_and_filters(self, where_clause, result):
        """从rdflib WHERE子句中提取三元组和过滤器"""
        if hasattr(where_clause, 'p'):
            self._extract_triples_and_filters(where_clause.p, result)

        if hasattr(where_clause, 'p1'):
            self._extract_triples_and_filters(where_clause.p1, result)

        if hasattr(where_clause, 'p2'):
            self._extract_triples_and_filters(where_clause.p2, result)

        if hasattr(where_clause, 'part'):
            for part in where_clause.part:
                if hasattr(part, 'triples'):
                    for triple in part.triples:
                        subject = str(triple[0])
                        obj = str(triple[2])

                        predicate_path = triple[1]
                        predicate = self._extract_predicate_from_path(predicate_path)

                        result['triples'].append({
                            'subject': subject,
                            'predicate': predicate,
                            'object': obj
                        })

                if hasattr(part, 'expr'):
                    result['filters'].append('HAS_FILTER')

    def _extract_predicate_from_path(self, predicate_path) -> str:
        """从谓词路径对象中提取谓词字符串"""
        try:
            if hasattr(predicate_path, 'part'):
                for path_seq in predicate_path.part:
                    if hasattr(path_seq, 'part'):
                        for path_elt in path_seq.part:
                            if hasattr(path_elt, 'part'):
                                pname = path_elt.part
                                if hasattr(pname, 'localname'):
                                    return pname.localname
            return str(predicate_path)
        except:
            return str(predicate_path)

    def _parse_sparql_query_regex(self, query: str) -> Dict:
        """正则表达式解析SPARQL（回退方案）"""
        clean_query = re.sub(r'#.*', '', query)
        clean_query = ' '.join(clean_query.split())

        select_match = re.search(
            r'SELECT\s+(DISTINCT\s+)?(.*?)\s+WHERE',
            clean_query,
            re.IGNORECASE
        )
        if not select_match:
            raise ValueError("无法解析SELECT子句")

        select_clause = select_match.group(2).strip()
        select_vars = []
        for match in re.finditer(r'\?(\w+)', select_clause):
            var = match.group(1)
            if var not in select_vars:
                select_vars.append(var)

        where_match = re.search(
            r'WHERE\s*\{(.*?)\}\s*$',
            clean_query,
            re.DOTALL | re.IGNORECASE
        )
        if not where_match:
            raise ValueError("无法解析WHERE子句")

        where_body = where_match.group(1)

        filters = []
        filter_pattern = r'FILTER\s*\(((?:[^()]|\([^()]*\))*)\)'
        for match in re.finditer(filter_pattern, where_body, re.DOTALL):
            filters.append(match.group(1).strip())
            where_body = where_body.replace(match.group(0), '')

        triples = []
        # 先移除多余的空白，但保留语句结构
        where_body = re.sub(r'\s+', ' ', where_body).strip()
        # 按点号分割语句
        statements = [s.strip() for s in re.split(r'\s*\.\s*', where_body) if s.strip()]

        for stmt in statements:
            # 匹配三元组：?subject predicate ?object 或 ?subject predicate "literal"
            triple_match = re.match(r'(\??\w+)\s+(\S+:\S+|\S+)\s+(.+)', stmt)
            if triple_match:
                triples.append({
                    'subject': triple_match.group(1),
                    'predicate': triple_match.group(2),
                    'object': triple_match.group(3).rstrip('.')
                })

        return {
            'select_vars': select_vars,
            'triples': triples,
            'filters': filters,
            'has_placeholder': '<<SUBQUERY_' in query
        }

    def _build_cypher(self, parsed: Dict) -> str:
        """构建Neo4j Cypher查询"""
        main_label = None
        main_var = None

        # 查找主节点标签
        for triple in parsed['triples']:
            pred = triple['predicate']
            if 'type' in pred.lower() or pred == 'a':
                obj = triple['object']
                class_name = obj.split('#')[-1] if '#' in obj else obj.split(':')[-1]
                if class_name in self.class_to_label:
                    main_label = self.class_to_label[class_name]
                    main_var = triple['subject'].strip('?')
                    break

        if not main_label:
            # 从属性推断标签
            for triple in parsed['triples']:
                pred_name = triple['predicate'].split(':')[-1]
                if pred_name in self.property_to_label:
                    main_label = self.property_to_label[pred_name]
                    main_var = triple['subject'].strip('?')
                    break

        if not main_label:
            return "// 无法确定节点标签"

        # 构建MATCH子句
        match_clause = f"MATCH ({main_var[0] if main_var else 'n'}:{main_label})"

        # 构建RETURN子句
        return_items = []
        for var in parsed['select_vars']:
            if var == main_var:
                return_items.append(f"{main_var[0]}.ID")
            else:
                # 查找对应的属性
                for triple in parsed['triples']:
                    if triple['object'] == f'?{var}':
                        pred_name = triple['predicate'].split(':')[-1]
                        if pred_name in self.property_to_attribute:
                            attr = self.property_to_attribute[pred_name]
                            return_items.append(f"{main_var[0]}.{attr}")
                            break

        if not return_items:
            return_items = [f"{main_var[0] if main_var else 'n'}.*"]

        # 构建WHERE子句
        where_parts = []
        if parsed.get('has_placeholder'):
            where_parts.append(f"{main_var[0]}.ID IN <<SUBQUERY_1>>")

        cypher = match_clause
        if where_parts:
            cypher += f"\nWHERE {' AND '.join(where_parts)}"
        cypher += f"\nRETURN {', '.join(return_items)}"

        return cypher
