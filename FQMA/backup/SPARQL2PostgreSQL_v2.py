#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPARQL到PostgreSQL查询转换器 - rdflib重构版
完全基于TTL文件的R2RML映射，使用rdflib解析SPARQL，零硬编码
"""

import re
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
from rdflib import Graph, Namespace, RDF, URIRef, Literal
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.namespace import XSD


class SparqlToPostgreSQLConverter:
    """SPARQL到PostgreSQL转换器 - 使用rdflib解析，完全由TTL驱动"""

    def __init__(self, ttl_file_path: str):
        """
        初始化转换器

        Args:
            ttl_file_path: R2RML映射TTL文件路径
        """
        self.ttl_file_path = ttl_file_path

        # RDF图和命名空间
        self.graph = Graph()
        self.graph.parse(ttl_file_path, format='turtle')

        # R2RML命名空间
        self.rr = Namespace("http://www.w3.org/ns/r2rml#")
        self.conf = Namespace("http://conference#")

        # 核心映射数据结构
        self.class_to_table = {}
        self.property_to_column = {}
        self.property_to_table = {}
        self.object_properties = []
        self.table_columns = defaultdict(set)
        self.complex_relation_mappings = {}

        # 解析R2RML映射
        self._parse_r2rml_mapping()

        # 打印解析统计
        print(f"成功解析R2RML映射:")
        print(f"  - {len(self.class_to_table)} 个类映射")
        print(f"  - {len(self.property_to_column)} 个属性映射")
        print(f"  - {len(self.object_properties)} 个关系映射")
        print(f"  - {len(self.complex_relation_mappings)} 个复杂关系映射")

    def _parse_r2rml_mapping(self):
        """从RDF图中解析R2RML映射"""
        # 遍历所有TriplesMap
        for triples_map in self.graph.subjects(RDF.type, self.rr.TriplesMap):
            self._parse_triples_map(triples_map)

    def _parse_triples_map(self, triples_map):
        """解析单个TriplesMap"""
        # 获取逻辑表
        logical_table = self.graph.value(triples_map, self.rr.logicalTable)
        if not logical_table:
            return

        # 获取表名或SQL查询
        table_name = self.graph.value(logical_table, self.rr.tableName)
        sql_query = self.graph.value(logical_table, self.rr.sqlQuery)

        # 获取subjectMap
        subject_map = self.graph.value(triples_map, self.rr.subjectMap)
        if not subject_map:
            return

        # 获取类映射
        rdf_class = self.graph.value(subject_map, self.rr['class'])
        if rdf_class and table_name:
            class_name = str(rdf_class).split('#')[-1]
            self.class_to_table[class_name] = str(table_name)

        # 获取predicateObjectMap
        for pom in self.graph.objects(triples_map, self.rr.predicateObjectMap):
            self._parse_predicate_object_map(pom, table_name, sql_query)

    def _parse_predicate_object_map(self, pom, table_name, sql_query):
        """解析predicateObjectMap"""
        # 获取谓词
        predicate = self.graph.value(pom, self.rr.predicate)
        if not predicate:
            return

        pred_name = str(predicate).split('#')[-1]

        # 获取objectMap
        object_map = self.graph.value(pom, self.rr.objectMap)
        if not object_map:
            return

        # 检查是数据属性还是对象属性
        column = self.graph.value(object_map, self.rr.column)
        template = self.graph.value(object_map, self.rr.template)

        if column and not template:
            # 数据属性
            if table_name:
                self.property_to_column[pred_name] = str(column)
                self.property_to_table[pred_name] = str(table_name)
                self.table_columns[str(table_name)].add(str(column))

        elif template:
            # 对象属性
            if table_name:
                # 从template提取外键列和目标类
                template_str = str(template)
                match = re.search(r'#(\w+)_\{(\w+)\}', template_str)
                if match:
                    target_class = match.group(1)
                    fk_column = match.group(2)

                    self.object_properties.append({
                        'predicate': pred_name,
                        'source_table': str(table_name),
                        'target_class': target_class,
                        'foreign_key': fk_column
                    })

            # 如果有SQL查询，这是复杂映射
            if sql_query:
                self._parse_complex_mapping(pred_name, str(sql_query), template_str if template else None)

    def _parse_complex_mapping(self, predicate, sql_query, template):
        """解析复杂映射（带JOIN的SQL查询）"""
        if not template:
            return

        # 从SQL中提取JOIN信息
        join_match = re.search(
            r'(?:LEFT\s+|RIGHT\s+|INNER\s+)?JOIN\s+"?(\w+)"?\s+\w*\s*ON\s+"?(\w+)"?\."?(\w+)"?\s*=\s*"?(\w+)"?\."?(\w+)"?',
            sql_query, re.IGNORECASE
        )

        if join_match:
            join_table = join_match.group(1)
            from_table = join_match.group(2)
            left_col = join_match.group(3)
            right_col = join_match.group(5)

            # 从template提取目标列
            template_match = re.search(r'\{(\w+)\}', template)
            target_col = template_match.group(1) if template_match else None

            self.complex_relation_mappings[predicate] = {
                'join_table': join_table,
                'main_table': from_table,
                'left_col': left_col,
                'right_col': right_col,
                'target_column': target_col
            }

    def convert(self, sparql_query: str) -> str:
        """
        将SPARQL查询转换为PostgreSQL SQL

        Args:
            sparql_query: SPARQL查询字符串

        Returns:
            PostgreSQL SQL查询字符串
        """
        try:
            # 处理占位符
            has_placeholder = '<<SUBQUERY_' in sparql_query
            if has_placeholder:
                # 临时替换占位符为标准SPARQL
                temp_query = re.sub(r'<<SUBQUERY_(\d+)>>', r'1, 2, 3', sparql_query)
            else:
                temp_query = sparql_query

            # 使用rdflib解析SPARQL
            parsed = parseQuery(temp_query)

            # 提取查询组件
            query_info = self._extract_query_components(parsed)

            # 构建SQL
            sql = self._build_sql(query_info, has_placeholder, sparql_query)

            return sql

        except Exception as e:
            print(f"转换失败: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _extract_query_components(self, parsed) -> Dict:
        """从rdflib解析结果中提取查询组件"""
        components = {
            'select_vars': [],
            'triples': [],
            'filters': [],
            'prefixes': {}
        }

        # 提取前缀
        if hasattr(parsed, '__iter__'):
            for item in parsed:
                if hasattr(item, '__iter__'):
                    for sub_item in item:
                        if hasattr(sub_item, 'prefix'):
                            components['prefixes'][sub_item.prefix] = str(sub_item.iri)

        # 提取SELECT变量
        select_query = None
        for item in parsed:
            if hasattr(item, 'projection'):
                select_query = item
                break

        if select_query:
            for var_item in select_query.projection:
                if hasattr(var_item, 'var'):
                    components['select_vars'].append(str(var_item.var))

            # 提取WHERE子句中的三元组
            if hasattr(select_query, 'where'):
                self._extract_triples_from_where(select_query.where, components)

        return components

    def _extract_triples_from_where(self, where_clause, components):
        """从WHERE子句中提取三元组和FILTER"""
        if hasattr(where_clause, 'part'):
            for part in where_clause.part:
                # 三元组块
                if hasattr(part, 'triples'):
                    for triple in part.triples:
                        if len(triple) >= 3:
                            subject = str(triple[0])
                            predicate_path = triple[1]
                            obj = str(triple[2])

                            # 提取谓词名称
                            predicate = self._extract_predicate_name(predicate_path)

                            components['triples'].append({
                                'subject': subject,
                                'predicate': predicate,
                                'object': obj
                            })

                # FILTER子句
                if hasattr(part, 'expr'):
                    filter_expr = self._extract_filter_expression(part)
                    if filter_expr:
                        components['filters'].append(filter_expr)

    def _extract_predicate_name(self, predicate_path) -> str:
        """从谓词路径中提取谓词名称"""
        if hasattr(predicate_path, 'part'):
            for path_seq in predicate_path.part:
                if hasattr(path_seq, 'part'):
                    for path_elt in path_seq.part:
                        if hasattr(path_elt, 'part'):
                            pname = path_elt.part
                            if hasattr(pname, 'localname'):
                                return f"{pname.prefix}:{pname.localname}"
        return str(predicate_path)

    def _extract_filter_expression(self, filter_part) -> Optional[Dict]:
        """提取FILTER表达式"""
        # 简化处理：提取变量和值
        return {'raw': str(filter_part)}

    def _build_sql(self, query_info: Dict, has_placeholder: bool, original_sparql: str) -> str:
        """构建PostgreSQL SQL查询"""
        # 确定主表
        main_table = None
        main_variable = None

        for triple in query_info['triples']:
            pred = triple['predicate']
            if 'type' in pred.lower() or pred == 'rdf:type' or pred == 'a':
                obj = triple['object']
                class_name = obj.split('#')[-1] if '#' in obj else obj.split(':')[-1]
                if class_name in self.class_to_table:
                    main_table = self.class_to_table[class_name]
                    main_variable = triple['subject'].strip('?')
                    break

        if not main_table:
            return "SELECT * FROM unknown_table"

        # 构建SELECT子句
        select_cols = []
        for var in query_info['select_vars']:
            # 根据TTL映射变量到列
            col_found = False

            # 检查是否是主变量
            if var == main_variable:
                select_cols.append(f'"{main_table}"."ID"')
                col_found = True

            # 检查数据属性
            for triple in query_info['triples']:
                if triple['object'] == f'?{var}' or triple['subject'] == f'?{var}':
                    pred_name = triple['predicate'].split(':')[-1]
                    if pred_name in self.property_to_column:
                        column = self.property_to_column[pred_name]
                        table = self.property_to_table[pred_name]
                        select_cols.append(f'"{table}"."{column}"')
                        col_found = True
                        break

            # 检查对象属性（外键）
            if not col_found:
                for triple in query_info['triples']:
                    if triple['object'] == f'?{var}':
                        pred_name = triple['predicate'].split(':')[-1]
                        for obj_prop in self.object_properties:
                            if obj_prop['predicate'] == pred_name:
                                fk_col = obj_prop['foreign_key']
                                select_cols.append(f'"{main_table}"."{fk_col}"')
                                col_found = True
                                break

        if not select_cols:
            select_cols = [f'"{main_table}".*']

        # 构建WHERE子句
        where_parts = [f'"{main_table}"."ID" IN (<<SUBQUERY_1>>)'] if has_placeholder else []

        # 构建SQL
        sql = f'SELECT {", ".join(select_cols)}\nFROM "{main_table}"'
        if where_parts:
            sql += f'\nWHERE {" AND ".join(where_parts)}'

        return sql
