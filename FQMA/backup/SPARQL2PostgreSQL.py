#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用SPARQL到PostgreSQL查询转换器 - 增强版
完全基于TTL文件的R2RML映射，无硬编码，支持任意本体
支持COUNT聚合函数和GROUP BY子句
"""

import re
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict


class SparqlToPostgreSQLConverter:
    """通用的SPARQL到SQL转换器 - 完全由TTL驱动，支持聚合操作"""

    def __init__(self, ttl_file_path: str):
        """
        初始化转换器

        Args:
            ttl_file_path: R2RML映射TTL文件路径
        """
        self.ttl_file_path = ttl_file_path

        # 核心映射数据结构
        self.class_to_table = {}  # RDF类 -> 数据库表
        self.property_to_column = {}  # 数据属性 -> 列名
        self.property_to_table = {}  # 数据属性 -> 所属表
        self.object_properties = []  # 对象属性（关系）列表
        self.table_columns = defaultdict(set)  # 表 -> 列集合

        # 复杂关系映射（从SQL查询中解析的JOIN关系）
        self.complex_relation_mappings = {}  # predicate -> {join_table, source_col, target_col, ...}

        # 解析TTL文件
        self._parse_r2rml_mapping()

    def _parse_r2rml_mapping(self):
        """解析R2RML映射"""
        try:
            with open(self.ttl_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 分割每个映射定义（以<#开头）
            mapping_sections = re.split(r'\n\s*<#', content)

            for section in mapping_sections:
                if not section.strip():
                    continue
                self._parse_mapping_section('<#' + section if not section.startswith('<#') else section)

            print(f"✓ 成功解析R2RML映射:")
            print(f"  - {len(self.class_to_table)} 个类映射")
            print(f"  - {len(self.property_to_column)} 个属性映射")
            print(f"  - {len(self.object_properties)} 个关系映射")
            if self.complex_relation_mappings:
                print(f"  - {len(self.complex_relation_mappings)} 个复杂关系映射")

        except Exception as e:
            print(f"✗ 解析失败: {e}")
            raise

    def _parse_mapping_section(self, section: str):
        """解析单个映射节"""
        # 1. 检查是否有SQL查询（复杂映射）
        sql_match = re.search(r'rr:sqlQuery\s*"""(.*?)"""', section, re.DOTALL)

        if sql_match:
            sql_query = sql_match.group(1).strip()
            # 解析复杂关系映射
            self._parse_complex_mapping(section, sql_query)
        else:
            # 2. 提取表名
            table_name = self._extract_table_name(section)
            if not table_name:
                return

            # 3. 解析类映射 (subjectMap + rr:class)
            self._parse_class_mapping(section, table_name)

            # 4. 解析数据属性 (predicateObjectMap with rr:column)
            self._parse_datatype_properties(section, table_name)

            # 5. 解析对象属性 (predicateObjectMap with rr:template)
            self._parse_object_properties(section, table_name)

    def _parse_complex_mapping(self, section: str, sql_query: str):
        """解析复杂的关系映射（包含SQL JOIN的映射）"""
        # 🔥 【重构】提取所有predicateObjectMap块，分别处理
        pom_blocks = self._extract_predicate_object_maps(section)

        if not pom_blocks:
            return

        # 解析SQL查询中的JOIN信息（所有谓词共享）
        join_info_base = self._parse_sql_join(sql_query)

        # 从SQL查询中提取主表（所有谓词共享）
        from_match = re.search(r'FROM\s+"?(\w+)"?', sql_query, re.IGNORECASE)
        main_table = from_match.group(1) if from_match else None

        # 提取subjectMap（所有谓词共享）
        subject_template_match = re.search(
            r'rr:subjectMap\s*\[\s*rr:template\s*"[^"]*\{(\w+)\}"',
            section
        )
        source_column = subject_template_match.group(1) if subject_template_match else None

        # 🔥 遍历每个predicateObjectMap块
        for pom_block in pom_blocks:
            # 提取谓词
            pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', pom_block)
            if not pred_match:
                continue

            predicate_name = pred_match.group(2)

            # 🔥 检查objectMap类型
            is_datatype_property = bool(re.search(r'rr:column', pom_block))
            is_object_property = bool(re.search(r'rr:template', pom_block))

            # 情况1: 纯数据属性（不是关系）
            if is_datatype_property and not is_object_property:
                # 提取列名
                column_match = re.search(r'rr:column\s+"([^"]+)"', pom_block)
                if column_match and main_table:
                    column_name = column_match.group(1)
                    # 添加到属性映射（不覆盖已有的简单映射）
                    if predicate_name not in self.property_to_column:
                        self.property_to_column[predicate_name] = column_name
                        self.property_to_table[predicate_name] = main_table
                        self.table_columns[main_table].add(column_name)
                continue  # 不加入complex_relation_mappings

            # 情况2: 对象属性（关系）
            if is_object_property and join_info_base:
                # 复制基础JOIN信息
                join_info = join_info_base.copy()
                join_info['predicate'] = predicate_name

                # 提取objectMap中的template来确定目标列
                object_template_match = re.search(
                    r'rr:template\s*"[^"]*\{(\w+)\}"',
                    pom_block
                )
                if object_template_match:
                    join_info['target_column'] = object_template_match.group(1)

                if source_column:
                    join_info['source_column'] = source_column

                self.complex_relation_mappings[predicate_name] = join_info

                # 提取SQL查询中的列别名
                self._extract_sql_columns(sql_query, predicate_name)

    def _parse_sql_join(self, sql_query: str) -> Optional[Dict]:
        """从SQL查询中解析JOIN信息"""
        result = {}

        # 提取主表 (FROM 子句)
        from_match = re.search(r'FROM\s+"?(\w+)"?\s+(\w+)?', sql_query, re.IGNORECASE)
        if from_match:
            result['main_table'] = from_match.group(1)
            result['main_alias'] = from_match.group(2) if from_match.group(2) else from_match.group(1)

        # 🔥 【修复】提取JOIN信息 - 支持LEFT/RIGHT/INNER等JOIN类型
        join_match = re.search(
            r'(?:LEFT\s+|RIGHT\s+|INNER\s+)?JOIN\s+"?(\w+)"?\s+(\w+)?\s+ON\s+(\w+)\."?(\w+)"?\s*=\s*(\w+)\."?(\w+)"?',
            sql_query, re.IGNORECASE
        )
        if join_match:
            result['join_table'] = join_match.group(1)
            result['join_alias'] = join_match.group(2) if join_match.group(2) else join_match.group(1)
            result['left_alias'] = join_match.group(3)
            result['left_col'] = join_match.group(4)
            result['right_alias'] = join_match.group(5)
            result['right_col'] = join_match.group(6)

        # 提取SELECT中的列
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_query, re.IGNORECASE | re.DOTALL)
        if select_match:
            result['select_cols'] = select_match.group(1).strip()

        return result if result else None

    def _extract_sql_columns(self, sql_query: str, predicate_name: str):
        """从SQL查询中提取列别名"""
        # 提取 column AS alias 模式
        alias_pattern = r'(\w+)\."(\w+)"\s+as\s+(\w+)'
        for match in re.finditer(alias_pattern, sql_query, re.IGNORECASE):
            alias = match.group(3)
            # 记录别名到实际表列的映射
            if predicate_name not in self.complex_relation_mappings:
                self.complex_relation_mappings[predicate_name] = {}
            if 'column_aliases' not in self.complex_relation_mappings[predicate_name]:
                self.complex_relation_mappings[predicate_name]['column_aliases'] = {}
            self.complex_relation_mappings[predicate_name]['column_aliases'][alias] = {
                'table_alias': match.group(1),
                'column': match.group(2)
            }

    def _extract_table_name(self, section: str) -> Optional[str]:
        """从映射节中提取表名"""
        # 方法1: 直接的tableName
        match = re.search(r'rr:tableName\s+"([^"]+)"', section)
        if match:
            return match.group(1)

        # 方法2: 从SQL查询中提取
        match = re.search(r'FROM\s+"?(\w+)"?', section, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def _parse_class_mapping(self, section: str, table_name: str):
        """解析RDF类到表的映射"""
        matches = re.finditer(r'rr:class\s+(\w+):(\w+)', section)
        for match in matches:
            class_name = match.group(2)
            self.class_to_table[class_name] = table_name

    def _parse_datatype_properties(self, section: str, table_name: str):
        """解析数据类型属性（映射到列的属性）"""
        # 使用改进的正则表达式来匹配嵌套的方括号
        pom_blocks = self._extract_predicate_object_maps(section)

        for block in pom_blocks:
            # 提取predicate和column
            pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', block)
            col_match = re.search(r'rr:column\s+"([^"]+)"', block)

            if pred_match and col_match:
                predicate_name = pred_match.group(2)
                column_name = col_match.group(1)

                self.property_to_column[predicate_name] = column_name
                self.property_to_table[predicate_name] = table_name
                self.table_columns[table_name].add(column_name)

    def _extract_predicate_object_maps(self, content: str) -> List[str]:
        """提取所有predicateObjectMap块，正确处理嵌套方括号"""
        blocks = []
        pattern = r'rr:predicateObjectMap\s*\['

        for match in re.finditer(pattern, content):
            start = match.end() - 1  # 指向'['
            end = self._find_matching_bracket(content, start)
            if end != -1:
                block = content[start + 1:end]
                blocks.append(block)

        return blocks

    def _find_matching_bracket(self, content: str, start_pos: int) -> int:
        """找到与start_pos位置的'['匹配的']'位置"""
        if start_pos >= len(content) or content[start_pos] != '[':
            return -1

        depth = 0
        for i in range(start_pos, len(content)):
            if content[i] == '[':
                depth += 1
            elif content[i] == ']':
                depth -= 1
                if depth == 0:
                    return i
        return -1

    def _parse_object_properties(self, section: str, table_name: str):
        """解析对象属性（关系）"""
        pom_blocks = self._extract_predicate_object_maps(section)

        for block in pom_blocks:
            # 查找有template的（表示关系）
            pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', block)
            template_match = re.search(r'rr:template\s+"([^"]+)"', block)

            if pred_match and template_match and 'rr:column' not in block:
                predicate_name = pred_match.group(2)
                template = template_match.group(1)

                # 从template提取信息
                # 格式: http://conference#target_class_{column_name}
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
        将SPARQL查询转换为SQL

        Args:
            sparql_query: SPARQL查询字符串

        Returns:
            SQL查询字符串
        """
        try:
            # Step 1: 解析SPARQL
            parsed = self._parse_sparql_query(sparql_query)

            # Step 2: 分析查询图模式，识别主表和JOIN关系
            query_plan = self._analyze_query_pattern(parsed)

            # Step 3: 构建SQL
            sql = self._build_sql(parsed, query_plan)

            return sql

        except Exception as e:
            print(f"✗ 转换失败: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _parse_sparql_query(self, query: str) -> Dict:
        """解析SPARQL查询，支持聚合函数"""
        # 清理
        clean_query = re.sub(r'#.*', '', query)  # 删除注释
        clean_query = ' '.join(clean_query.split())  # 规范化空白

        # 提取SELECT子句（支持聚合函数）
        select_match = re.search(
            r'SELECT\s+(DISTINCT\s+)?(.*?)\s+WHERE',
            clean_query,
            re.IGNORECASE
        )
        if not select_match:
            raise ValueError("无法解析SELECT子句")

        is_distinct = bool(select_match.group(1))
        select_clause = select_match.group(2).strip()

        # 解析SELECT变量和聚合函数
        select_vars = []
        aggregations = []

        # 匹配聚合函数模式: COUNT(?var) AS ?alias 或 (COUNT(?var) AS ?alias)
        agg_pattern = r'\(?\s*(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(?:DISTINCT\s+)?\?(\w+)\s*\)\s*(?:AS\s+\?(\w+))?\s*\)?'
        for match in re.finditer(agg_pattern, select_clause, re.IGNORECASE):
            agg_func = match.group(1).upper()
            var_name = match.group(2)
            alias = match.group(3) if match.group(3) else f"{agg_func.lower()}_{var_name}"
            aggregations.append({
                'function': agg_func,
                'variable': var_name,
                'alias': alias
            })
            select_vars.append(alias)

        # 匹配普通变量
        for match in re.finditer(r'\?(\w+)', select_clause):
            var = match.group(1)
            # 排除已在聚合中出现的变量
            if var not in [a['variable'] for a in aggregations] and var not in [a['alias'] for a in aggregations]:
                if var not in select_vars:
                    select_vars.append(var)

        # 提取WHERE子句
        where_match = re.search(
            r'WHERE\s*\{(.*?)\}',
            clean_query,
            re.DOTALL | re.IGNORECASE
        )
        if not where_match:
            raise ValueError("无法解析WHERE子句")

        where_body = where_match.group(1)

        # 提取GROUP BY子句
        group_by_vars = []
        group_match = re.search(r'GROUP\s+BY\s+(.*?)(?:HAVING|ORDER|LIMIT|$)', clean_query, re.IGNORECASE)
        if group_match:
            group_vars_str = group_match.group(1).strip()
            group_by_vars = [v.strip('?') for v in re.findall(r'\?(\w+)', group_vars_str)]

        # 🔥 【新增】提取BIND表达式
        # BIND(STR(?conference) AS ?conference_id)
        # BIND(?expr AS ?var)
        bind_mappings = {}  # 目标变量 -> 源变量/表达式
        bind_pattern = r'BIND\s*\(\s*(?:STR\s*\(\s*)?\?(\w+)\s*(?:\))?\s+AS\s+\?(\w+)\s*\)'
        for match in re.finditer(bind_pattern, where_body, re.IGNORECASE):
            source_var = match.group(1)
            target_var = match.group(2)
            bind_mappings[target_var] = source_var
            print(f"  🔥 检测到BIND: ?{target_var} <- ?{source_var}")
            where_body = where_body.replace(match.group(0), '')  # 移除BIND

        # 提取FILTER
        filters = []
        filter_pattern = r'FILTER\s*\(((?:[^()]|\([^()]*\))*)\)'
        for match in re.finditer(filter_pattern, where_body, re.DOTALL):
            filters.append(match.group(1).strip())
            where_body = where_body.replace(match.group(0), '')  # 移除FILTER

        # 解析三元组模式
        triples = []
        statements = [s.strip() for s in re.split(r'\s*\.\s*', where_body) if s.strip()]

        for stmt in statements:
            parts = stmt.split(None, 2)  # 最多分3部分
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
            'aggregations': aggregations,
            'group_by': group_by_vars,
            'bind_mappings': bind_mappings  # 🔥 新增
        }

    def _analyze_query_pattern(self, parsed: Dict) -> Dict:
        """
        分析查询模式，确定主表和JOIN策略

        Returns:
            {
                'main_table': 主表名,
                'main_variable': 主变量,
                'joins': [{table, on_column, target_table}, ...],
                'var_to_column': {变量: (表名, 列名)},
                'complex_joins': [{...}],  # 复杂JOIN信息
                'needed_joins': [...]  # 根据查询属性推断需要的额外JOIN
            }
        """
        triples = parsed['triples']

        # 🔥 【新增】收集所有作为subject使用的变量
        # 用于判断对象属性的object变量是否需要JOIN
        # 但要排除"仅作为类型声明subject"的情况
        subject_vars = set()
        type_only_subjects = set()  # 仅在rdf:type中作为subject的变量

        for triple in triples:
            if triple['subject'].startswith('?'):
                subj_var = triple['subject'].strip('?')
                if self._is_type_predicate(triple['predicate']):
                    # 这是类型声明
                    type_only_subjects.add(subj_var)
                else:
                    # 这是实际的属性访问
                    subject_vars.add(subj_var)
                    # 如果之前只在type中出现，现在有实际属性访问，移除type_only标记
                    type_only_subjects.discard(subj_var)

        # 🔥 如果变量在type_only_subjects中，说明只作为类型声明，不算真正的subject使用
        # 不应该触发JOIN
        print(f"  📊 Subject变量分析:")
        print(f"    - 有实际属性访问的subject: {subject_vars}")
        print(f"    - 仅类型声明的subject: {type_only_subjects}")

        # 1. 找到类型声明，确定主表和主变量
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
            raise ValueError("无法确定主表（缺少rdf:type声明）")

        # 2. 构建变量到列的映射
        var_to_column = {}
        var_to_entity_table = {}  # 🔥 新增：变量到实体表的映射（用于属性推断）

        # 主变量映射到ID
        var_to_column[main_variable] = (main_table, 'ID')
        var_to_entity_table[main_variable] = main_table  # 🔥 记录主变量的实体表

        # 3. 分析每个三元组，映射变量
        joins = []
        complex_joins = []
        needed_joins = []  # 🔥 新增：记录根据属性推断需要的JOIN
        needed_joins_set = set()  # 🔥 用于去重JOIN

        for triple in triples:
            if self._is_type_predicate(triple['predicate']):
                continue

            pred_name = triple['predicate'].split(':')[-1]
            subject_var = triple['subject'].strip('?')
            object_var = triple['object'].strip('?') if triple['object'].startswith('?') else None

            # 情况1: 检查是否是复杂关系映射
            if pred_name in self.complex_relation_mappings:
                complex_mapping = self.complex_relation_mappings[pred_name]

                # 🔥 【智能判断】是否需要JOIN（与情况3相同的逻辑）
                need_join = False
                if object_var:
                    # 检查object_var是否作为subject使用
                    if object_var in subject_vars:
                        need_join = True
                        print(f"  ℹ️  {pred_name}(复杂): ?{object_var} 作为subject使用，需要JOIN")
                    else:
                        # 只在SELECT中出现，不需要JOIN
                        print(f"  ℹ️  {pred_name}(复杂): ?{object_var} 仅在SELECT中，使用外键值，不JOIN")

                # 如果需要JOIN，才添加到complex_joins和var_to_column
                if need_join:
                    complex_joins.append({
                        'predicate': pred_name,
                        'subject_var': subject_var,
                        'object_var': object_var,
                        'mapping': complex_mapping
                    })
                    # 如果宾语是变量，将其映射到JOIN表的目标列
                    if object_var and complex_mapping.get('join_table'):
                        join_table = complex_mapping.get('join_table')
                        # 🔥 【新增】记录object_var对应的实体表
                        var_to_entity_table[object_var] = join_table

                        # 找到指向目标实体的列
                        if 'column_aliases' in complex_mapping:
                            for alias, info in complex_mapping['column_aliases'].items():
                                if 'author' in alias.lower() or 'person' in alias.lower():
                                    var_to_column[object_var] = (join_table, info['column'])
                                    break
                        else:
                            # 默认使用右侧列作为目标
                            if complex_mapping.get('right_col'):
                                var_to_column[object_var] = (join_table, complex_mapping['right_col'])
                else:
                    # 🔥 不需要JOIN，直接使用外键列的值
                    # 需要找到存储外键的列
                    # 从complex_mapping的source_column或者left_col获取
                    if object_var:
                        # 外键列通常在主表的某个列中
                        # 例如：Paper表的is_submitted_at列存储Conference_volume的ID
                        # 这个列名通常与谓词名相同
                        fk_column = complex_mapping.get('left_col') or complex_mapping.get('source_column') or pred_name
                        var_to_column[object_var] = (main_table, fk_column)

            # 情况2: 数据属性
            elif pred_name in self.property_to_column:
                column = self.property_to_column[pred_name]
                prop_table = self.property_to_table[pred_name]

                # 🔥 【改进】检查subject_var是否有对应的实体表
                # 如果有，优先使用该实体表（而不是property_to_table的默认映射）
                actual_table = prop_table
                if subject_var in var_to_entity_table:
                    entity_table = var_to_entity_table[subject_var]
                    # 检查entity_table中是否也有这个属性（可能多个表有相同属性）
                    if column in self.table_columns.get(entity_table, set()):
                        # 🔥 强制使用实体表！因为变量已经通过对象属性绑定了
                        actual_table = entity_table
                        prop_table = entity_table  # 更新prop_table以便后续逻辑使用
                    else:
                        # 即使entity_table没有记录这个列，也尝试使用它
                        # （因为TTL解析可能不完整）
                        # 但是要确保这个实体表确实是查询需要的
                        print(f"⚠️  警告: 变量{subject_var}绑定到{entity_table}，但该表未记录列{column}，使用默认表{prop_table}")
                        # 仍然使用entity_table，因为查询逻辑更重要
                        actual_table = entity_table
                        prop_table = entity_table

                # 🔥 【新增】检查属性所属的表是否是主表
                # 如果不是主表，且主表与属性表之间存在外键关系，需要添加JOIN
                if prop_table != main_table:
                    # 检查是否需要JOIN
                    # 查找主表到属性表的外键
                    fk_found = False
                    for obj_prop in self.object_properties:
                        # 检查是否存在从主表到prop_table对应类的关系
                        if obj_prop['source_table'] == main_table:
                            # 找到目标表
                            target_table = None
                            for cls, tbl in self.class_to_table.items():
                                if cls.lower() == obj_prop['target_class'].lower() and tbl == prop_table:
                                    target_table = tbl
                                    fk_found = True
                                    break

                            if fk_found:
                                # 避免重复JOIN
                                join_key = (prop_table, obj_prop['foreign_key'])
                                if join_key not in needed_joins_set:
                                    # 添加JOIN
                                    needed_joins.append({
                                        'table': prop_table,
                                        'on_column': obj_prop['foreign_key'],
                                        'join_type': 'LEFT JOIN',
                                        'predicate_trigger': pred_name  # 记录触发JOIN的谓词
                                    })
                                    needed_joins_set.add(join_key)
                                break

                    # 🔥 【新增】如果没有找到对象属性，检查复杂关系映射
                    if not fk_found:
                        # 遍历所有复杂关系，查找能连接主表和prop_table的映射
                        for rel_pred, rel_mapping in self.complex_relation_mappings.items():
                            # 检查是否有JOIN信息连接主表和prop_table
                            if rel_mapping.get('main_table') == main_table and rel_mapping.get('join_table'):
                                # 直接检查：如果有JOIN prop_table，且prop在prop_table
                                if rel_mapping.get('join_table') == prop_table:
                                    # 避免重复JOIN
                                    join_key = (prop_table, rel_mapping.get('left_col'))
                                    if join_key not in needed_joins_set:
                                        # 使用这个复杂关系的JOIN信息
                                        needed_joins.append({
                                            'table': prop_table,
                                            'on_left_col': rel_mapping.get('left_col', 'ID'),
                                            'on_right_col': rel_mapping.get('right_col'),
                                            'join_type': 'LEFT JOIN',
                                            'from_table': main_table,
                                            'predicate_trigger': pred_name,
                                            'complex_mapping': rel_mapping  # 保留映射信息
                                        })
                                        needed_joins_set.add(join_key)
                                        fk_found = True
                                    break

                if object_var:
                    var_to_column[object_var] = (actual_table, column)

            # 情况3: 简单对象属性（可能需要JOIN）
            else:
                for obj_prop in self.object_properties:
                    if obj_prop['predicate'] == pred_name:
                        # 找到目标表
                        target_class = obj_prop['target_class']
                        target_table = None

                        # 匹配目标类到表
                        for cls, tbl in self.class_to_table.items():
                            if cls.lower() == target_class.lower():
                                target_table = tbl
                                break

                        if target_table and target_table != main_table:
                            # 🔥 【智能判断】是否需要JOIN
                            # 如果object变量在其他三元组中作为subject使用 → 需要JOIN
                            # 如果object变量只在SELECT中出现 → 只要外键值，不JOIN
                            need_join = False
                            if object_var:
                                # 检查object_var是否作为subject使用
                                if object_var in subject_vars:
                                    need_join = True
                                    print(f"  ℹ️  {pred_name}: ?{object_var} 作为subject使用，需要JOIN到{target_table}")
                                else:
                                    # 只在SELECT中出现，不需要JOIN，直接使用外键值
                                    print(f"  ℹ️  {pred_name}: ?{object_var} 仅在SELECT中，使用外键值{obj_prop['foreign_key']}，不JOIN")
                                    # 映射到主表的外键列（而不是目标表的ID）
                                    var_to_column[object_var] = (main_table, obj_prop['foreign_key'])
                                    break

                            if need_join:
                                # 添加JOIN
                                joins.append({
                                    'table': target_table,
                                    'on_column': obj_prop['foreign_key'],
                                    'target_table': main_table
                                })

                                # 如果宾语是变量，映射到目标表的ID
                                if object_var:
                                    var_to_column[object_var] = (target_table, 'ID')
                                    var_to_entity_table[object_var] = target_table  # 🔥 记录实体表

        return {
            'main_table': main_table,
            'main_variable': main_variable,
            'joins': joins,
            'var_to_column': var_to_column,
            'complex_joins': complex_joins,
            'needed_joins': needed_joins  # 🔥 新增返回值
        }

    def _is_type_predicate(self, predicate: str) -> bool:
        """判断是否是类型谓词"""
        return (predicate == 'a' or
                predicate == 'rdf:type' or
                'type' in predicate.lower())

    def _build_sql(self, parsed: Dict, plan: Dict) -> str:
        """构建SQL查询，支持聚合函数"""
        aggregations = parsed.get('aggregations', [])
        group_by = parsed.get('group_by', [])
        has_aggregation = len(aggregations) > 0

        # SELECT子句
        select_items = []

        # 处理聚合函数
        for agg in aggregations:
            agg_var = agg['variable']
            agg_func = agg['function']
            agg_alias = agg['alias']

            # 找到聚合变量对应的列
            if agg_var in plan['var_to_column']:
                table, column = plan['var_to_column'][agg_var]
                select_items.append(f'{agg_func}("{table}"."{column}") AS {agg_alias}')
            else:
                # 检查复杂JOIN中的变量
                found = False
                for cj in plan.get('complex_joins', []):
                    if cj.get('object_var') == agg_var:
                        mapping = cj['mapping']
                        join_table = mapping.get('join_table')

                        # 优先使用target_column（从objectMap template提取的列名）
                        target_col = mapping.get('target_column')
                        if target_col:
                            select_items.append(f'{agg_func}("{join_table}"."{target_col}") AS {agg_alias}')
                            found = True
                            break

                        # 如果没有target_column，尝试从column_aliases找
                        if 'column_aliases' in mapping:
                            for alias, info in mapping['column_aliases'].items():
                                if 'person' in alias.lower() or 'author' in alias.lower():
                                    select_items.append(f'{agg_func}("{join_table}"."{info["column"]}") AS {agg_alias}')
                                    found = True
                                    break

                        # 默认使用Person列（对于has_authors关系）
                        if not found and join_table:
                            select_items.append(f'{agg_func}("{join_table}"."Person") AS {agg_alias}')
                            found = True
                        break

                if not found:
                    # 最后的fallback
                    select_items.append(f'{agg_func}(*) AS {agg_alias}')

        # 处理普通变量
        bind_mappings = parsed.get('bind_mappings', {})

        for var in parsed['select_vars']:
            if var in [a['alias'] for a in aggregations]:
                continue  # 已在聚合中处理

            # 🔥 【新增】检查是否是BIND的目标变量
            source_var = bind_mappings.get(var)
            if source_var:
                # 使用源变量的映射
                print(f"  🔥 应用BIND映射: ?{var} -> ?{source_var}")
                var_to_use = source_var
            else:
                var_to_use = var

            if var_to_use in plan['var_to_column']:
                table, column = plan['var_to_column'][var_to_use]
                select_items.append(f'"{table}"."{column}"')
            else:
                # 尝试推断
                found = False
                for t_var, (table, column) in plan['var_to_column'].items():
                    if var_to_use.lower() in t_var.lower() or t_var.lower() in var_to_use.lower():
                        select_items.append(f'"{table}"."{column}"')
                        found = True
                        break

                if not found:
                    print(f"  ⚠️  警告: 变量 ?{var} 未找到列映射")


        if not select_items:
            select_items = ['*']

        distinct = 'DISTINCT ' if parsed['is_distinct'] and not has_aggregation else ''
        sql_parts = [f"SELECT {distinct}{', '.join(select_items)}"]

        # FROM子句
        sql_parts.append(f'FROM "{plan["main_table"]}"')

        # 🔥 【改进】收集所有需要的JOIN，去重
        all_joins = []
        joins_seen = set()  # (table, left_col, right_col) -> 去重

        # 1. 首先添加needed_joins（根据属性推断的JOIN）
        for nj in plan.get('needed_joins', []):
            if 'complex_mapping' in nj:
                # 使用复杂映射的JOIN信息
                join_table = nj['table']
                from_table = nj['from_table']
                left_col = nj['on_left_col']
                right_col = nj['on_right_col']

                join_key = (join_table, from_table, left_col, right_col)
                if join_key not in joins_seen:
                    all_joins.append({
                        'type': nj["join_type"],
                        'table': join_table,
                        'on': f'"{from_table}"."{left_col}" = "{join_table}"."{right_col}"'
                    })
                    joins_seen.add(join_key)
            else:
                # 简单的外键JOIN
                join_table = nj["table"]
                main_table = plan["main_table"]
                on_col = nj["on_column"]

                join_key = (join_table, main_table, on_col, 'ID')
                if join_key not in joins_seen:
                    all_joins.append({
                        'type': nj["join_type"],
                        'table': join_table,
                        'on': f'"{main_table}"."{on_col}" = "{join_table}"."ID"'
                    })
                    joins_seen.add(join_key)

        # 2. 添加complex_joins（来自复杂关系映射）
        for cj in plan.get('complex_joins', []):
            mapping = cj['mapping']
            if mapping.get('join_table'):
                join_table = mapping['join_table']
                main_table = plan['main_table']
                left_col = mapping.get('left_col', 'ID')
                right_col = mapping.get('right_col', 'Conference_document')

                join_key = (join_table, main_table, left_col, right_col)
                if join_key not in joins_seen:
                    all_joins.append({
                        'type': 'LEFT JOIN',
                        'table': join_table,
                        'on': f'"{main_table}"."{left_col}" = "{join_table}"."{right_col}"'
                    })
                    joins_seen.add(join_key)

        # 3. 添加简单JOIN
        for join in plan['joins']:
            join_table = join["table"]
            target_table = join["target_table"]
            on_col = join["on_column"]

            join_key = (join_table, target_table, on_col, 'ID')
            if join_key not in joins_seen:
                all_joins.append({
                    'type': 'JOIN',
                    'table': join_table,
                    'on': f'"{target_table}"."{on_col}" = "{join_table}"."ID"'
                })
                joins_seen.add(join_key)

        # 生成所有JOIN子句
        for j in all_joins:
            sql_parts.append(f'{j["type"]} "{j["table"]}" ON {j["on"]}')

        # WHERE子句
        where_conditions = self._build_where_conditions(parsed, plan)
        if where_conditions:
            sql_parts.append('WHERE ' + ' AND '.join(where_conditions))

        # GROUP BY子句
        if has_aggregation:
            group_columns = []
            # 如果有明确的GROUP BY变量
            if group_by:
                for var in group_by:
                    if var in plan['var_to_column']:
                        table, column = plan['var_to_column'][var]
                        group_columns.append(f'"{table}"."{column}"')
            else:
                # 自动推断：对所有非聚合的SELECT变量进行GROUP BY
                for var in parsed['select_vars']:
                    if var not in [a['alias'] for a in aggregations]:
                        if var in plan['var_to_column']:
                            table, column = plan['var_to_column'][var]
                            group_columns.append(f'"{table}"."{column}"')

            if group_columns:
                sql_parts.append('GROUP BY ' + ', '.join(group_columns))

        return '\n'.join(sql_parts)

    def _build_where_conditions(self, parsed: Dict, plan: Dict) -> List[str]:
        """构建WHERE条件"""
        conditions = []

        # 处理FILTER
        for filter_expr in parsed['filters']:
            # IN条件
            in_match = re.match(r'\?(\w+)\s+IN\s+\((.*?)\)', filter_expr, re.DOTALL)
            if in_match:
                var = in_match.group(1)
                values = in_match.group(2).strip()

                if var in plan['var_to_column']:
                    table, column = plan['var_to_column'][var]
                    if '<<SUBQUERY' in values:
                        conditions.append(f'"{table}"."{column}" IN ({values})')
                    else:
                        conditions.append(f'"{table}"."{column}" IN ({values})')
                continue

            # 简单比较条件 ?var = value
            compare_match = re.match(r'\?(\w+)\s*=\s*(\d+)', filter_expr)
            if compare_match:
                var = compare_match.group(1)
                value = compare_match.group(2)
                if var in plan['var_to_column']:
                    table, column = plan['var_to_column'][var]
                    conditions.append(f'"{table}"."{column}" = {value}')
                continue

        # 处理三元组中的字面量约束
        for triple in parsed['triples']:
            if self._is_type_predicate(triple['predicate']):
                continue

            # 如果宾语是字面量（不是变量）
            if not triple['object'].startswith('?'):
                pred_name = triple['predicate'].split(':')[-1]
                if pred_name in self.property_to_column:
                    column = self.property_to_column[pred_name]
                    table = self.property_to_table[pred_name]
                    value = triple['object'].strip('"\'')
                    conditions.append(f'"{table}"."{column}" = \'{value}\'')

        return conditions

    def print_mapping_summary(self):
        """打印映射摘要（调试用）"""
        print("\n" + "=" * 70)
        print("R2RML 映射摘要")
        print("=" * 70)

        print("\n【类 -> 表映射】")
        for cls, table in sorted(self.class_to_table.items()):
            print(f"  {cls:30} → {table}")

        print("\n【属性 -> 列映射】")
        for prop, col in sorted(self.property_to_column.items())[:10]:
            table = self.property_to_table[prop]
            print(f"  {prop:30} → {table}.{col}")
        if len(self.property_to_column) > 10:
            print(f"  ... 还有 {len(self.property_to_column) - 10} 个属性")

        print("\n【对象属性（关系）】")
        for rel in self.object_properties:
            print(f"  {rel['predicate']:30} : {rel['source_table']} --[{rel['foreign_key']}]--> {rel['target_class']}")

        print("\n【复杂关系映射】")
        for pred, mapping in self.complex_relation_mappings.items():
            print(f"  {pred}:")
            print(f"    主表: {mapping.get('main_table')}")
            print(f"    JOIN表: {mapping.get('join_table')}")
            print(f"    连接: {mapping.get('left_col')} = {mapping.get('right_col')}")

        print("=" * 70 + "\n")


def main():
    """主测试函数"""
    ttl_file = '../data/RODI/rodi_postgre.ttl'

    print("\n" + "=" * 70)
    print(" 通用SPARQL→SQL转换器 (支持COUNT和GROUP BY)")
    print("=" * 70)

    # 初始化
    converter = SparqlToPostgreSQLConverter(ttl_file)
    converter.print_mapping_summary()

    # 测试: 带COUNT的查询
    print("\n【测试】查询每篇论文的作者数量")
    print("-" * 70)

    sparql = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX conf: <http://conference#>

    SELECT ?paper (COUNT(?person) AS ?author_count)
    WHERE {
      ?paper rdf:type conf:Paper .
      ?paper conf:has_authors ?person .
      ?person rdf:type conf:Person .
      FILTER (?paper IN (0, 600))
    }
    GROUP BY ?paper
    """

    print("SPARQL:")
    print(sparql)
    print("\nSQL:")
    sql = converter.convert(sparql)
    print(sql)

    print("\n" + "=" * 70)
    print("✓ 转换完成！")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()