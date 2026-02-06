#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
属性到数据库的智能映射系统 - 零硬编码版本
完全基于TTL文件提取信息，由LLM做最终决策
不再使用任何硬编码规则！

修复版本：正确处理TTL中的嵌套方括号
"""

import re
from typing import Dict, Set, List, Tuple, Optional
from collections import defaultdict


class PropertyDatabaseMapper:
    """
    从TTL文件中提取属性和关系的数据库分布信息

    重要：本类只负责收集信息，不做任何硬编码决策！
    所有路由决策都应该交给LLM处理。
    """

    def __init__(self, ttl_files: Dict[str, str]):
        self.ttl_files = ttl_files

        # 属性到数据库的映射（一个属性可能存在于多个数据库）
        self.property_to_databases: Dict[str, Set[str]] = defaultdict(set)

        # 属性类型（从TTL自动提取）
        self.datatype_properties: Dict[str, Set[str]] = defaultdict(set)  # 数据属性
        self.object_properties: Dict[str, Set[str]] = defaultdict(set)  # 对象属性（关系）

        # 属性类型缓存
        self.property_types: Dict[str, str] = {}  # property_name -> 'datatype' or 'object'

        # 映射的详细信息（包含SQL查询、表名等）
        self.property_details: Dict[str, List[Dict]] = defaultdict(list)

        # 解析所有TTL文件
        self._parse_all_ttl_files()

    def _parse_all_ttl_files(self):
        """解析所有TTL文件"""
        print("\n=== 开始解析TTL文件提取属性分布（零硬编码版本）===")
        for db_name, ttl_path in self.ttl_files.items():
            print(f"\n📂 解析 {db_name} 的TTL文件: {ttl_path}")
            self._parse_single_ttl(ttl_path, db_name)
        print("\n=== TTL文件解析完成 ===")
        self._print_mapping_summary()

    def _find_matching_bracket(self, content: str, start_pos: int) -> int:
        """
        找到与start_pos位置的'['匹配的']'位置
        正确处理嵌套的方括号
        """
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

    def _extract_predicate_object_maps(self, content: str) -> List[str]:
        """
        提取所有predicateObjectMap块，正确处理嵌套方括号
        """
        blocks = []
        pattern = r'rr:predicateObjectMap\s*\['

        for match in re.finditer(pattern, content):
            start = match.end() - 1  # 指向'['
            end = self._find_matching_bracket(content, start)
            if end != -1:
                block = content[start + 1:end]
                blocks.append(block)

        return blocks

    def _parse_single_ttl(self, ttl_path: str, db_name: str):
        """解析单个TTL文件，提取属性及其详细信息"""
        try:
            with open(ttl_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取所有映射块（TriplesMap）
            # 匹配从 <#MappingName> 到下一个 <# 或文件结束
            mapping_pattern = r'<#(\w+)>(.*?)(?=<#|\Z)'
            mapping_matches = re.finditer(mapping_pattern, content, re.DOTALL)

            for mapping in mapping_matches:
                mapping_name = mapping.group(1)
                mapping_block = mapping.group(2)

                # 提取SQL查询（如果有）
                sql_query = None
                sql_match = re.search(r'rr:sqlQuery\s*"""(.*?)"""', mapping_block, re.DOTALL)
                if sql_match:
                    sql_query = sql_match.group(1).strip()

                # 提取表名（如果有）
                table_name = None
                table_match = re.search(r'rr:tableName\s+"([^"]+)"', mapping_block)
                if table_match:
                    table_name = table_match.group(1)

                # 使用改进的方法提取所有 predicateObjectMap 块
                pom_blocks = self._extract_predicate_object_maps(mapping_block)

                for block in pom_blocks:
                    # 提取predicate
                    pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', block)
                    if not pred_match:
                        continue

                    predicate = pred_match.group(2)
                    self.property_to_databases[predicate].add(db_name)

                    # 判断属性类型
                    property_type = self._identify_property_type_from_block(block)

                    if property_type == 'datatype':
                        self.datatype_properties[predicate].add(db_name)
                        self.property_types[predicate] = 'datatype'
                    elif property_type == 'object':
                        self.object_properties[predicate].add(db_name)
                        self.property_types[predicate] = 'object'

                    # 保存详细信息
                    detail = {
                        'database': db_name,
                        'mapping_name': mapping_name,
                        'property_type': property_type,
                        'table_name': table_name,
                        'sql_query': sql_query
                    }
                    self.property_details[predicate].append(detail)

            prop_count = len([p for p, dbs in self.property_to_databases.items() if db_name in dbs])
            print(f"  ✅ 提取到 {prop_count} 个属性")

        except Exception as e:
            print(f"  ❌ 解析失败: {e}")
            import traceback
            traceback.print_exc()

    def _identify_property_type_from_block(self, block: str) -> str:
        """
        零硬编码：从TTL块结构自动识别属性类型

        规则（基于R2RML标准）：
        - DatatypeProperty: 包含 rr:column 和 rr:datatype
        - ObjectProperty: 包含 rr:template 和 rr:termType rr:IRI
        """
        has_column = 'rr:column' in block
        has_datatype = 'rr:datatype' in block
        has_template = 'rr:template' in block
        has_iri_term = 'rr:termType rr:IRI' in block

        if has_column and has_datatype:
            return 'datatype'
        elif has_template and has_iri_term:
            return 'object'
        else:
            # 默认按照是否有template判断
            return 'object' if has_template else 'datatype'

    def is_datatype_property(self, property_name: str) -> bool:
        """判断是否为数据属性"""
        return self.property_types.get(property_name) == 'datatype'

    def is_object_property(self, property_name: str) -> bool:
        """判断是否为对象属性（关系）"""
        return self.property_types.get(property_name) == 'object'

    def get_property_databases(self, property_name: str) -> Set[str]:
        """获取属性存在的所有数据库"""
        return self.property_to_databases.get(property_name, set())

    def get_property_details(self, property_name: str) -> List[Dict]:
        """获取属性的详细信息（包括在每个数据库中的映射）"""
        return self.property_details.get(property_name, [])

    def get_property_info_for_llm(self, properties: List[str]) -> str:
        """
        生成供LLM决策使用的属性信息报告

        这是本类最重要的方法！
        它将TTL中提取的信息格式化为LLM可以理解的形式，
        让LLM做出最终的路由决策。
        """
        if not properties:
            return "未检测到任何属性。"

        report_lines = []
        report_lines.append("## 属性数据库分布分析\n")

        for prop in properties:
            databases = self.get_property_databases(prop)
            prop_type = self.property_types.get(prop, '未知')
            details = self.get_property_details(prop)

            report_lines.append(f"### 属性: `{prop}`")
            report_lines.append(
                f"- **类型**: {'数据属性' if prop_type == 'datatype' else '对象属性（关系）' if prop_type == 'object' else '未知'}")
            report_lines.append(f"- **存在于数据库**: {', '.join(sorted(databases)) if databases else '未找到'}")

            if details:
                report_lines.append("- **详细映射**:")
                for detail in details:
                    db = detail['database']
                    mapping = detail['mapping_name']
                    table = detail.get('table_name', '无')
                    sql = detail.get('sql_query', '')

                    report_lines.append(f"  - [{db}] 映射: {mapping}")
                    if table:
                        report_lines.append(f"    表名: {table}")
                    if sql:
                        # 截取SQL的关键部分
                        sql_preview = sql[:150].replace('\n', ' ').strip()
                        if len(sql) > 150:
                            sql_preview += "..."
                        report_lines.append(f"    SQL: {sql_preview}")

            report_lines.append("")

        # 添加多数据库属性的提示
        multi_db_props = [p for p in properties if len(self.get_property_databases(p)) > 1]
        if multi_db_props:
            report_lines.append("### ⚠️ 多数据库属性提示")
            report_lines.append("以下属性存在于多个数据库中，需要根据查询语义选择最合适的数据库：")
            for prop in multi_db_props:
                dbs = self.get_property_databases(prop)
                report_lines.append(f"- `{prop}`: {', '.join(sorted(dbs))}")
            report_lines.append("")

        return "\n".join(report_lines)

    def get_all_properties_summary(self) -> Dict[str, Dict]:
        """获取所有属性的汇总信息（供调试使用）"""
        summary = {}
        for prop, databases in self.property_to_databases.items():
            summary[prop] = {
                'databases': list(databases),
                'type': self.property_types.get(prop, 'unknown'),
                'is_multi_db': len(databases) > 1
            }
        return summary

    def _print_mapping_summary(self):
        """打印映射摘要"""
        print("\n" + "=" * 70)
        print("属性-数据库映射摘要（零硬编码版本）")
        print("=" * 70)

        print(f"\n📊 统计:")
        print(f"  总属性数: {len(self.property_to_databases)}")

        datatype_count = sum(1 for p in self.property_types.values() if p == 'datatype')
        object_count = sum(1 for p in self.property_types.values() if p == 'object')
        print(f"  数据属性 (DatatypeProperty): {datatype_count}")
        print(f"  对象属性 (ObjectProperty): {object_count}")

        # 统计多数据库属性
        multi_db_props = [p for p, dbs in self.property_to_databases.items() if len(dbs) > 1]
        if multi_db_props:
            print(f"\n⚠️ 多数据库属性 ({len(multi_db_props)} 个):")
            for prop in sorted(multi_db_props):
                dbs = self.property_to_databases[prop]
                print(f"  - {prop}: {', '.join(sorted(dbs))}")

        # 按数据库分组显示
        for db_name in sorted(set(db for dbs in self.property_to_databases.values() for db in dbs)):
            props = [p for p, dbs in self.property_to_databases.items() if db_name in dbs]
            if props:
                print(f"\n【{db_name}】包含的属性 ({len(props)} 个):")

                datatype_props = [p for p in props if self.is_datatype_property(p)]
                object_props = [p for p in props if self.is_object_property(p)]

                if datatype_props:
                    print(f"  📝 数据属性 ({len(datatype_props)} 个): {', '.join(sorted(datatype_props)[:10])}")
                    if len(datatype_props) > 10:
                        print(f"     ... 还有 {len(datatype_props) - 10} 个")

                if object_props:
                    print(f"  🔗 对象属性 ({len(object_props)} 个): {', '.join(sorted(object_props)[:10])}")
                    if len(object_props) > 10:
                        print(f"     ... 还有 {len(object_props) - 10} 个")

        print("\n" + "=" * 70)
        print("⚠️ 注意：本类不做任何路由决策，所有决策由LLM完成！")
        print("=" * 70 + "\n")


# 测试代码
if __name__ == "__main__":
    # 测试用的TTL文件路径
    test_ttl_files = {
        'Neo4j': '../data/RODI/rodi_neo4j.ttl',
        'MySQL': '../data/RODI/rodi_mysql.ttl',
        'PostgreSQL': '../data/RODI/rodi_postgre.ttl'
    }

    mapper = PropertyDatabaseMapper(test_ttl_files)

    # 测试：检查 reviews 属性
    print("\n=== 测试 reviews 属性 ===")
    test_props = ['reviews', 'has_authors', 'has_detailed_comments']

    for prop in test_props:
        dbs = mapper.get_property_databases(prop)
        print(f"{prop}: {dbs}")

    print("\n=== LLM信息报告 ===")
    llm_info = mapper.get_property_info_for_llm(test_props)
    print(llm_info)