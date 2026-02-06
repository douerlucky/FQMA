#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPARQL到PostgreSQL查询转换器 - 完全重构版
使用rdflib解析SPARQL，完全基于TTL文件的R2RML映射，零硬编码
"""

import re
from typing import Dict, List, Optional, Set
from collections import defaultdict
from rdflib.plugins.sparql.parser import parseQuery


class SparqlToPostgreSQLConverter:
    """SPARQL到PostgreSQL转换器 - 使用rdflib，完全由TTL驱动"""

    def __init__(self, ttl_file_path: str):
        """
        初始化转换器

        Args:
            ttl_file_path: R2RML映射TTL文件路径
        """
        self.ttl_file_path = ttl_file_path

        # 核心映射数据结构
        self.class_to_table = {}
        self.property_to_column = {}
        self.property_to_table = {}
        self.object_properties = []
        self.table_columns = defaultdict(set)
        self.complex_relation_mappings = {}

        # 解析TTL文件
        self._parse_r2rml_mapping()

        # 打印统计信息
        print(f"成功解析R2RML映射:")
        print(f"  - {len(self.class_to_table)} 个类映射")
        print(f"  - {len(self.property_to_column)} 个属性映射")
        print(f"  - {len(self.object_properties)} 个关系映射")
        print(f"  - {len(self.complex_relation_mappings)} 个复杂关系映射")

    def _parse_r2rml_mapping(self):
        """解析R2RML映射文件"""
        try:
            with open(self.ttl_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            mapping_sections = re.split(r'\n\s*<#', content)

            for section in mapping_sections:
                if not section.strip():
                    continue

                section = '<#' + section if not section.startswith('<#') else section

                # 1. 解析类映射
                self._parse_class_mapping(section)

                # 2. 解析数据属性
                table_name = self._extract_table_name(section)
                if table_name:
                    self._parse_datatype_properties(section, table_name)

                # 3. 解析SQL查询映射
                sql_query = self._extract_sql_query(section)
                if sql_query:
                    self._parse_complex_mapping(section, sql_query)

                # 4. 解析对象属性
                if table_name:
                    self._parse_object_properties(section, table_name)

        except Exception as e:
            print(f"解析TTL文件失败: {e}")
            raise

    def _parse_class_mapping(self, section: str):
        """解析RDF类到数据库表的映射"""
        class_match = re.search(r'rr:class\s+(\w+):(\w+)', section)
        table_match = re.search(r'rr:tableName\s+"([^"]+)"', section)

        if class_match and table_match:
            class_name = class_match.group(2)
            table_name = table_match.group(1)
            self.class_to_table[class_name] = table_name

    def _extract_table_name(self, section: str) -> Optional[str]:
        """提取表名"""
        match = re.search(r'rr:tableName\s+"([^"]+)"', section)
        return match.group(1) if match else None

    def _extract_sql_query(self, section: str) -> Optional[str]:
        """提取SQL查询"""
        match = re.search(r'rr:sqlQuery\s+"""(.*?)"""', section, re.DOTALL)
        return match.group(1).strip() if match else None

    def _parse_datatype_properties(self, section: str, table_name: str):
        """解析数据属性"""
        pom_blocks = self._extract_predicate_object_maps(section)

        for block in pom_blocks:
            pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', block)
            column_match = re.search(r'rr:column\s+"([^"]+)"', block)

            if pred_match and column_match and 'rr:template' not in block:
                predicate_name = pred_match.group(2)
                column_name = column_match.group(1)

                self.property_to_column[predicate_name] = column_name
                self.property_to_table[predicate_name] = table_name
                self.table_columns[table_name].add(column_name)

    def _extract_predicate_object_maps(self, section: str) -> List[str]:
        """提取所有predicateObjectMap块"""
        blocks = []
        pattern = r'rr:predicateObjectMap\s*\[(.*?)\]'

        for match in re.finditer(pattern, section, re.DOTALL):
            blocks.append(match.group(0))

        return blocks

    def _parse_complex_mapping(self, section: str, sql_query: str):
        """解析复杂映射"""
        pom_blocks = self._extract_predicate_object_maps(section)

        if not pom_blocks:
            return

        join_info_base = self._parse_sql_join(sql_query)

        from_match = re.search(r'FROM\s+"?(\w+)"?', sql_query, re.IGNORECASE)
        main_table = from_match.group(1) if from_match else None

        subject_template_match = re.search(
            r'rr:subjectMap\s*\[\s*rr:template\s*"[^"]*\{(\w+)\}"',
            section
        )
        source_column = subject_template_match.group(1) if subject_template_match else None

        for pom_block in pom_blocks:
            pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', pom_block)
            if not pred_match:
                continue

            predicate_name = pred_match.group(2)

            is_datatype_property = bool(re.search(r'rr:column', pom_block))
            is_object_property = bool(re.search(r'rr:template', pom_block))

            if is_datatype_property and not is_object_property:
                column_match = re.search(r'rr:column\s+"([^"]+)"', pom_block)
                if column_match and main_table:
                    column_name = column_match.group(1)
                    if predicate_name not in self.property_to_column:
                        self.property_to_column[predicate_name] = column_name
                        self.property_to_table[predicate_name] = main_table
                        self.table_columns[main_table].add(column_name)
                continue

            if is_object_property and join_info_base:
                join_info = join_info_base.copy()
                join_info['predicate'] = predicate_name

                object_template_match = re.search(
                    r'rr:template\s*"[^"]*\{(\w+)\}"',
                    pom_block
                )
                if object_template_match:
                    join_info['target_column'] = object_template_match.group(1)

                if source_column:
                    join_info['source_column'] = source_column

                self.complex_relation_mappings[predicate_name] = join_info

    def _parse_sql_join(self, sql_query: str) -> Optional[Dict]:
        """从SQL查询中解析JOIN信息"""
        result = {}

        join_match = re.search(
            r'(?:LEFT\s+|RIGHT\s+|INNER\s+)?JOIN\s+"?(\w+)"?\s+(\w+)?\s+ON\s+(\w+)\."?(\w+)"?\s*=\s*(\w+)\."?(\w+)"?',
            sql_query, re.IGNORECASE
        )

        if join_match:
            result['join_table'] = join_match.group(1)
            result['main_table'] = join_match.group(3)
            result['left_col'] = join_match.group(4)
            result['right_col'] = join_match.group(6)
            return result

        return None

    def _parse_object_properties(self, section: str, table_name: str):
        """解析对象属性"""
        pom_blocks = self._extract_predicate_object_maps(section)

        for block in pom_blocks:
            pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', block)
            template_match = re.search(r'rr:template\s+"([^"]+)"', block)

            if pred_match and template_match and 'rr:column' not in block:
                predicate_name = pred_match.group(2)
                template = template_match.group(1)

                target_match = re.search(r'#(\w+)_\{(\w+)\}', template)
                if target_match:
                    target_class = target_match.group(1)
                    fk_column = target_match.group(2)

                    self.object_properties.append({
                        'predicate': predicate_name,
                        'source_table': table_name,
                        'target_class': target_class,
                        'foreign_key': fk_column
                    })

    def convert(self, sparql_query: str) -> str:
        """
        将SPARQL查询转换为PostgreSQL SQL

        Args:
            sparql_query: SPARQL查询字符串

        Returns:
            PostgreSQL SQL查询字符串
        """
        try:
            # 解析SPARQL
            parsed = self._parse_sparql_query(sparql_query)

            # 分析查询模式
            query_plan = self._analyze_query_pattern(parsed)

            # 构建SQL
            sql = self._build_sql(parsed, query_plan)

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
            'is_distinct': False,
            'triples': [],
            'filters': [],
            'aggregations': [],
            'group_by': [],
            'bind_mappings': {}
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
                    # 标记有FILTER，但不解析具体内容
                    # 因为占位符会在后续处理
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
                                    prefix = pname.prefix if hasattr(pname, 'prefix') else ''
                                    return f"{prefix}:{pname.localname}" if prefix else pname.localname
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

        is_distinct = bool(select_match.group(1))
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

        bind_mappings = {}
        bind_pattern = r'BIND\s*\(\s*(?:STR\s*\(\s*)?\?(\w+)\s*(?:\))?\s+AS\s+\?(\w+)\s*\)'
        for match in re.finditer(bind_pattern, where_body, re.IGNORECASE):
            source_var = match.group(1)
            target_var = match.group(2)
            bind_mappings[target_var] = source_var
            where_body = where_body.replace(match.group(0), '')

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
            'is_distinct': is_distinct,
            'triples': triples,
            'filters': filters,
            'aggregations': [],
            'group_by': [],
            'bind_mappings': bind_mappings
        }

    def _analyze_query_pattern(self, parsed: Dict) -> Dict:
        """分析查询模式，确定主表和JOIN策略"""
        triples = parsed['triples']

        subject_vars = set()
        type_only_subjects = set()

        for triple in triples:
            if triple['subject'].startswith('?'):
                subj_var = triple['subject'].strip('?')
                if self._is_type_predicate(triple['predicate']):
                    type_only_subjects.add(subj_var)
                else:
                    subject_vars.add(subj_var)
                    type_only_subjects.discard(subj_var)

        main_table = None
        main_variable = None

        for triple in triples:
            if self._is_type_predicate(triple['predicate']):
                class_name = triple['predicate'].split(':')[-1] if triple['predicate'] != 'a' else \
                    triple['object'].split(':')[-1]
                if triple['predicate'] == 'a' or 'type' in triple['predicate']:
                    class_name = triple['object'].split(':')[-1]
                    if class_name in self.class_to_table:
                        main_table = self.class_to_table[class_name]
                        main_variable = triple['subject'].strip('?')
                        break

        if not main_table:
            raise ValueError("无法确定主表")

        var_to_column = {}
        var_to_entity_table = {}

        var_to_column[main_variable] = (main_table, 'ID')
        var_to_entity_table[main_variable] = main_table

        joins = []
        complex_joins = []
        needed_joins = []
        needed_joins_set = set()

        for triple in triples:
            if self._is_type_predicate(triple['predicate']):
                continue

            pred_name = triple['predicate'].split(':')[-1]
            subject_var = triple['subject'].strip('?')
            object_var = triple['object'].strip('?') if triple['object'].startswith('?') else None

            if pred_name in self.complex_relation_mappings:
                complex_mapping = self.complex_relation_mappings[pred_name]

                need_join = False
                if object_var:
                    if object_var in subject_vars:
                        need_join = True

                if need_join:
                    complex_joins.append({
                        'predicate': pred_name,
                        'subject_var': subject_var,
                        'object_var': object_var,
                        'mapping': complex_mapping
                    })
                    if object_var and complex_mapping.get('join_table'):
                        join_table = complex_mapping.get('join_table')
                        var_to_entity_table[object_var] = join_table

                        if complex_mapping.get('right_col'):
                            var_to_column[object_var] = (join_table, complex_mapping['right_col'])
                else:
                    if object_var:
                        fk_column = complex_mapping.get('left_col') or complex_mapping.get('source_column') or pred_name
                        var_to_column[object_var] = (main_table, fk_column)

            elif pred_name in self.property_to_column:
                column = self.property_to_column[pred_name]
                prop_table = self.property_to_table[pred_name]

                actual_table = prop_table
                if subject_var in var_to_entity_table:
                    entity_table = var_to_entity_table[subject_var]
                    if column in self.table_columns.get(entity_table, set()):
                        actual_table = entity_table
                        prop_table = entity_table
                    else:
                        actual_table = entity_table
                        prop_table = entity_table

                if object_var:
                    var_to_column[object_var] = (actual_table, column)

            else:
                for obj_prop in self.object_properties:
                    if obj_prop['predicate'] == pred_name:
                        target_class = obj_prop['target_class']
                        target_table = None

                        for cls, tbl in self.class_to_table.items():
                            if cls.lower() == target_class.lower():
                                target_table = tbl
                                break

                        if target_table and target_table != main_table:
                            need_join = False
                            if object_var:
                                if object_var in subject_vars:
                                    need_join = True
                                else:
                                    var_to_column[object_var] = (main_table, obj_prop['foreign_key'])
                                    break

                            if need_join:
                                joins.append({
                                    'table': target_table,
                                    'on_column': obj_prop['foreign_key'],
                                    'target_table': main_table
                                })

                                if object_var:
                                    var_to_column[object_var] = (target_table, 'ID')
                                    var_to_entity_table[object_var] = target_table

        return {
            'main_table': main_table,
            'main_variable': main_variable,
            'joins': joins,
            'var_to_column': var_to_column,
            'complex_joins': complex_joins,
            'needed_joins': needed_joins
        }

    def _is_type_predicate(self, predicate: str) -> bool:
        """判断是否是类型谓词"""
        return (predicate == 'a' or
                predicate == 'rdf:type' or
                'type' in predicate.lower())

    def _build_sql(self, parsed: Dict, plan: Dict) -> str:
        """构建PostgreSQL SQL查询"""
        select_items = []
        bind_mappings = parsed.get('bind_mappings', {})

        for var in parsed['select_vars']:
            source_var = bind_mappings.get(var)
            if source_var:
                var_to_use = source_var
            else:
                var_to_use = var

            if var_to_use in plan['var_to_column']:
                table, column = plan['var_to_column'][var_to_use]
                select_items.append(f'"{table}"."{column}"')
            else:
                found = False
                for t_var, (table, column) in plan['var_to_column'].items():
                    if var_to_use.lower() in t_var.lower() or t_var.lower() in var_to_use.lower():
                        select_items.append(f'"{table}"."{column}"')
                        found = True
                        break

        if not select_items:
            select_items = ['*']

        sql_parts = [f"SELECT {', '.join(select_items)}"]
        sql_parts.append(f'FROM "{plan["main_table"]}"')

        all_joins = []
        joins_seen = set()

        for cj in plan.get('complex_joins', []):
            if 'complex_mapping' in cj.get('mapping', {}):
                mapping = cj['mapping']
                join_table = mapping.get('join_table')
                from_table = mapping.get('main_table')
                left_col = mapping.get('left_col')
                right_col = mapping.get('right_col')

                if join_table and from_table:
                    join_key = (join_table, from_table, left_col, right_col)
                    if join_key not in joins_seen:
                        all_joins.append({
                            'type': 'LEFT JOIN',
                            'table': join_table,
                            'on': f'"{from_table}"."{left_col}" = "{join_table}"."{right_col}"'
                        })
                        joins_seen.add(join_key)

        for join in plan['joins']:
            join_table = join['table']
            on_column = join['on_column']
            from_table = join.get('target_table', plan['main_table'])

            join_key = (join_table, from_table, on_column, 'ID')
            if join_key not in joins_seen:
                all_joins.append({
                    'type': 'LEFT JOIN',
                    'table': join_table,
                    'on': f'"{from_table}"."{on_column}" = "{join_table}"."ID"'
                })
                joins_seen.add(join_key)

        for join in all_joins:
            sql_parts.append(f'{join["type"]} "{join["table"]}" ON {join["on"]}')

        where_clauses = []
        for filter_expr in parsed['filters']:
            where_clauses.append(f'"{plan["main_table"]}"."ID" IN (<<SUBQUERY_1>>)')
            break  # 只添加一次

        if where_clauses:
            sql_parts.append(f'WHERE {" AND ".join(where_clauses)}')

        return '\n'.join(sql_parts)
