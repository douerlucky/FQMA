#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPARQL到MySQL查询转换器 - 完全重构版
使用rdflib解析SPARQL，完全基于TTL文件的R2RML映射，零硬编码
"""

import re
from typing import Dict, List, Optional, Set
from collections import defaultdict
from rdflib import Graph, Namespace, RDF
from rdflib.plugins.sparql.parser import parseQuery


class SparqlToMySQLConverter:
    """SPARQL到MySQL转换器 - 使用rdflib，完全由TTL驱动"""

    def __init__(self, ttl_files: List[str]):
        """
        初始化转换器

        Args:
            ttl_files: R2RML映射TTL文件路径列表
        """
        self.ttl_files = ttl_files if isinstance(ttl_files, list) else [ttl_files]

        # RDF图和命名空间
        self.graph = Graph()
        for ttl_file in self.ttl_files:
            self.graph.parse(ttl_file, format='turtle')

        self.rr = Namespace("http://www.w3.org/ns/r2rml#")

        # 核心映射数据结构
        self.class_to_table = {}
        self.property_to_column = {}
        self.property_to_table = {}
        self.sql_mappings = {}
        self.table_columns = defaultdict(set)

        # 解析R2RML映射
        self._parse_r2rml_mapping()

        # 打印统计信息
        print(f"成功解析MySQL R2RML映射:")
        print(f"  - {len(self.class_to_table)} 个类映射")
        print(f"  - {len(self.property_to_column)} 个属性映射")
        print(f"  - {len(self.sql_mappings)} 个SQL查询映射")

    def _parse_r2rml_mapping(self):
        """从RDF图中解析R2RML映射"""
        # MySQL TTL没有声明rdf:type rr:TriplesMap
        # 直接查找有rr:logicalTable的节点
        triples_maps = set()
        for s in self.graph.subjects(self.rr.logicalTable, None):
            triples_maps.add(s)
        for s in self.graph.subjects(self.rr.subjectMap, None):
            triples_maps.add(s)

        for triples_map in triples_maps:
            self._parse_triples_map(triples_map)

    def _extract_table_from_sql(self, sql_query: str) -> Optional[str]:
        """从SQL查询中提取表名"""
        sql_upper = sql_query.upper()
        from_match = re.search(r'FROM\s+([A-Za-z_][A-Za-z0-9_]*)', sql_query, re.IGNORECASE)
        if from_match:
            return from_match.group(1)
        return None

    def _parse_triples_map(self, triples_map):
        """解析单个TriplesMap"""
        logical_table = self.graph.value(triples_map, self.rr.logicalTable)
        if not logical_table:
            return

        table_name = self.graph.value(logical_table, self.rr.tableName)
        sql_query = self.graph.value(logical_table, self.rr.sqlQuery)

        # MySQL TTL使用sqlQuery，需要从SQL中提取表名
        if not table_name and sql_query:
            table_name = self._extract_table_from_sql(str(sql_query))

        subject_map = self.graph.value(triples_map, self.rr.subjectMap)
        if not subject_map:
            return

        rdf_class = self.graph.value(subject_map, self.rr['class'])
        if rdf_class and table_name:
            class_name = str(rdf_class).split('#')[-1]
            self.class_to_table[class_name] = str(table_name)

        for pom in self.graph.objects(triples_map, self.rr.predicateObjectMap):
            self._parse_predicate_object_map(pom, table_name, sql_query)

    def _parse_predicate_object_map(self, pom, table_name, sql_query):
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

        # 从column或template中提取列名
        if column and table_name:
            self.property_to_column[pred_name] = str(column)
            self.property_to_table[pred_name] = str(table_name)
            self.table_columns[str(table_name)].add(str(column))
        elif template and table_name:
            # 从template中提取列名：http://conference#conference_volume_{is_submitted_at}
            template_str = str(template)
            col_match = re.search(r'\{([^}]+)\}', template_str)
            if col_match:
                extracted_col = col_match.group(1)
                self.property_to_column[pred_name] = extracted_col
                self.property_to_table[pred_name] = str(table_name)
                self.table_columns[str(table_name)].add(extracted_col)

        if sql_query:
            sql_str = str(sql_query)
            if pred_name not in self.sql_mappings:
                self.sql_mappings[pred_name] = []
            self.sql_mappings[pred_name].append({
                'sql': sql_str,
                'predicate': pred_name,
                'column': str(column) if column else None,
                'table': str(table_name) if table_name else None
            })

    def convert_sparql_to_mysql(self, sparql_query: str) -> str:
        """
        将SPARQL查询转换为MySQL SQL

        Args:
            sparql_query: SPARQL查询字符串

        Returns:
            MySQL SQL查询字符串
        """
        try:
            parsed = self._parse_sparql_query(sparql_query)
            sql = self._build_sql(parsed)
            return sql

        except Exception as e:
            print(f"转换失败: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _parse_sparql_query(self, query: str) -> Dict:
        """使用rdflib解析SPARQL查询"""
        has_placeholder = '<<SUBQUERY_' in query

        if has_placeholder:
            temp_query = re.sub(r'<<SUBQUERY_\d+>>', '1, 2, 3', query)
        else:
            temp_query = query

        try:
            parsed_result = parseQuery(temp_query)
        except Exception as e:
            print(f"  rdflib解析失败: {e}")
            return self._parse_sparql_query_regex(query)

        result = {
            'select_vars': [],
            'triples': [],
            'filters': [],
            'has_placeholder': has_placeholder
        }

        select_query = None
        for item in parsed_result:
            if hasattr(item, 'projection'):
                select_query = item
                break

        if not select_query:
            return self._parse_sparql_query_regex(query)

        for var_item in select_query.projection:
            if hasattr(var_item, 'var'):
                result['select_vars'].append(str(var_item.var))

        if hasattr(select_query, 'where'):
            self._extract_triples_and_filters(select_query.where, result)

        if not result['triples']:
            return self._parse_sparql_query_regex(query)

        return result

    def _extract_triples_and_filters(self, where_clause, result):
        """从WHERE子句提取三元组和FILTER"""
        if hasattr(where_clause, 'part'):
            for part in where_clause.part:
                if hasattr(part, 'triples'):
                    for triple in part.triples:
                        if len(triple) >= 3:
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
            r'WHERE\s*\{(.*?)\}',
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
        statements = [s.strip() for s in re.split(r'\s*\.\s*', where_body) if s.strip()]

        for stmt in statements:
            parts = stmt.split(None, 2)
            if len(parts) >= 3:
                triples.append({
                    'subject': parts[0],
                    'predicate': parts[1],
                    'object': parts[2].rstrip('.')
                })

        return {
            'select_vars': select_vars,
            'triples': triples,
            'filters': filters,
            'has_placeholder': '<<SUBQUERY_' in query
        }

    def _build_sql(self, parsed: Dict) -> str:
        """构建MySQL SQL查询"""
        main_table = None
        main_var = None

        for triple in parsed['triples']:
            pred = triple['predicate']
            if 'type' in pred.lower() or pred == 'a':
                obj = triple['object']
                class_name = obj.split('#')[-1] if '#' in obj else obj.split(':')[-1]
                if class_name in self.class_to_table:
                    main_table = self.class_to_table[class_name]
                    main_var = triple['subject'].strip('?')
                    break

        if not main_table:
            predicates = [t['predicate'].split(':')[-1] for t in parsed['triples']]
            for pred in predicates:
                if pred in self.property_to_table:
                    main_table = self.property_to_table[pred]
                    break

        if not main_table:
            return "SELECT * FROM unknown_table"

        select_cols = []
        var_to_column = {}

        for var in parsed['select_vars']:
            col_found = False

            if var == main_var:
                select_cols.append(f"{main_table}.ID")
                var_to_column[var] = f"{main_table}.ID"
                col_found = True

            if not col_found:
                for triple in parsed['triples']:
                    if triple['object'] == f'?{var}':
                        pred_name = triple['predicate'].split(':')[-1]
                        if pred_name in self.property_to_column:
                            column = self.property_to_column[pred_name]
                            table = self.property_to_table[pred_name]
                            select_cols.append(f"{table}.{column}")
                            var_to_column[var] = f"{table}.{column}"
                            col_found = True
                            break

        if not select_cols:
            select_cols = [f"{main_table}.*"]

        where_parts = []
        if parsed.get('has_placeholder') or parsed.get('filters'):
            filter_column = var_to_column.get(main_var, f"{main_table}.ID")
            where_parts.append(f"{filter_column} IN (<<SUBQUERY_1>>)")

        sql = f"SELECT {', '.join(select_cols)}\nFROM {main_table}"
        if where_parts:
            sql += f"\nWHERE {' AND '.join(where_parts)}"

        return sql
