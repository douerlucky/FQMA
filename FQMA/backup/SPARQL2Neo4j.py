#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPARQL到Neo4j Cypher转换器 - 修复版 v5.0

修复内容：
1. 支持关系属性（pvalue, condition等存储在关系上的属性）
2. 添加 has_phenotype_association 的正确转换
3. 区分节点属性和关系属性
"""

import re
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field


@dataclass
class CypherTemplate:
    """从TTL提取的Cypher查询模板"""
    predicate_uri: str
    predicate_local: str
    cypher_query: str
    match_clause: str
    return_clause: str
    source_var: str
    source_label: str
    relation_type: str
    target_var: str
    target_label: str
    target_filter: str = ""
    # 从RETURN子句提取的属性映射: 变量名 -> 属性名
    return_properties: Dict[str, str] = field(default_factory=dict)
    # 🔥 新增：关系属性集合
    relation_properties: Set[str] = field(default_factory=set)


class SparqlToCypherConverter:
    """
    SPARQL到Cypher转换器 - 修复版

    修复关系属性处理问题
    """

    # 🔥 关系属性列表（从Neo4j数据模型中已知的关系属性）
    KNOWN_RELATION_PROPERTIES = {
        'pvalue', 'condition', 'condition_name',
        'correlation', 'effect_size', 'significance'
    }

    def __init__(self, ttl_file_path: str):
        self.ttl_file_path = ttl_file_path

        # 核心数据结构 - 全部从TTL提取
        self.cypher_templates: Dict[str, CypherTemplate] = {}
        self.class_to_label: Dict[str, str] = {}
        self.property_to_attribute: Dict[str, str] = {}  # SPARQL属性 -> Neo4j属性

        self._parse_ttl()

        # 🔥 手动添加 has_phenotype_association 模板（如果TTL中没有）
        self._ensure_phenotype_association_template()

    def _ensure_phenotype_association_template(self):
        """确保 has_phenotype_association 模板存在"""
        if 'has_phenotype_association' not in self.cypher_templates:
            print("  📌 手动添加模板: has_phenotype_association -> ASSOCIATED_WITH")
            self.cypher_templates['has_phenotype_association'] = CypherTemplate(
                predicate_uri="onto:has_phenotype_association",
                predicate_local="has_phenotype_association",
                cypher_query="""
                    MATCH (m:MicrobiotaName)-[r:ASSOCIATED_WITH]->(p)
                    RETURN m.name as microbiota_name, r.pvalue as pvalue, 
                           r.condition_name as condition
                """,
                match_clause="MATCH (m:MicrobiotaName)-[r:ASSOCIATED_WITH]->(p)",
                return_clause="m.name as microbiota_name, r.pvalue as pvalue, r.condition_name as condition",
                source_var="m",
                source_label="MicrobiotaName",
                relation_type="ASSOCIATED_WITH",
                target_var="p",
                target_label="",  # 目标可以是任何类型
                target_filter="",
                return_properties={'microbiota_name': 'name', 'pvalue': 'pvalue', 'condition': 'condition_name'},
                relation_properties={'pvalue', 'condition', 'condition_name'}  # 关系属性
            )

    def _parse_ttl(self):
        """解析TTL文件"""
        try:
            with open(self.ttl_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析所有映射块
            self._parse_all_sections(content)

            print(f"✓ 成功解析Neo4j映射:")
            print(f"  - {len(self.cypher_templates)} 个Cypher模板: {list(self.cypher_templates.keys())}")
            print(f"  - {len(self.class_to_label)} 个节点类型: {list(self.class_to_label.keys())}")
            print(f"  - {len(self.property_to_attribute)} 个属性映射: {self.property_to_attribute}")

        except Exception as e:
            print(f"✗ 解析TTL失败: {e}")
            import traceback
            traceback.print_exc()

    def _parse_all_sections(self, content: str):
        """解析所有映射块"""
        # 按映射块分割
        sections = re.split(r'\n\s*(?=ex:\w+)', content)

        for section in sections:
            if not section.strip():
                continue
            self._parse_section(section)

    def _parse_section(self, section: str):
        """解析单个映射块"""
        # 1. 提取节点类型映射
        class_match = re.search(r'rr:class\s+(\w+):(\w+)', section)
        if class_match:
            rdf_class = class_match.group(2)
            table_match = re.search(r'rr:tableName\s+"(\w+)"', section)
            if table_match:
                self.class_to_label[rdf_class] = table_match.group(1)

        # 2. 提取数据属性映射（只在没有template的predicateObjectMap中）
        for pom_match in re.finditer(
                r'rr:predicateObjectMap\s*\[\s*rr:predicate\s+(\w+):(\w+)\s*;\s*rr:objectMap\s*\[\s*rr:column\s+"([^"]+)"',
                section, re.DOTALL
        ):
            predicate = pom_match.group(2)
            column = pom_match.group(3)
            if predicate not in self.property_to_attribute:
                self.property_to_attribute[predicate] = column

        # 3. 提取Cypher查询模板
        self._extract_cypher_template(section)

    def _extract_cypher_template(self, section: str):
        """从TTL块中提取Cypher查询模板"""
        sql_match = re.search(r'rr:sqlQuery\s*"""(.*?)"""', section, re.DOTALL)
        if not sql_match:
            return

        cypher_query = sql_match.group(1).strip()

        if not re.search(r'MATCH\s*\(', cypher_query, re.I):
            return

        pred_match = re.search(r'rr:predicate\s+(\w+):(\w+)', section)
        if not pred_match:
            return

        predicate = pred_match.group(2)

        template = self._parse_cypher_template(predicate, cypher_query)
        if template:
            self.cypher_templates[predicate] = template
            print(f"  📌 提取Cypher模板: {predicate} -> {template.relation_type}")

    def _parse_cypher_template(self, predicate: str, cypher: str) -> Optional[CypherTemplate]:
        """解析Cypher查询模板，提取所有元素"""
        # 正向关系模式
        forward_match = re.search(
            r'MATCH\s*\((\w+):(\w+)\)\s*-\s*\[r?:?(\w+)\]\s*->\s*\((\w+):?(\w*)(\{[^}]*\})?\)',
            cypher, re.I
        )

        if forward_match:
            source_var = forward_match.group(1)
            source_label = forward_match.group(2)
            relation_type = forward_match.group(3)
            target_var = forward_match.group(4)
            target_label = forward_match.group(5) or ""
            target_filter = forward_match.group(6) or ""

            # 🔥 关键：从RETURN子句提取属性映射，并识别关系属性
            return_properties, relation_properties = self._extract_return_properties_v2(cypher)

            return_match = re.search(r'RETURN\s+(.+?)(?:$|\n)', cypher, re.I)
            return_clause = return_match.group(1).strip() if return_match else source_var

            return CypherTemplate(
                predicate_uri=f"onto:{predicate}",
                predicate_local=predicate,
                cypher_query=cypher,
                match_clause=forward_match.group(0),
                return_clause=return_clause,
                source_var=source_var,
                source_label=source_label,
                relation_type=relation_type,
                target_var=target_var,
                target_label=target_label,
                target_filter=target_filter,
                return_properties=return_properties,
                relation_properties=relation_properties
            )

        # 反向关系模式
        backward_match = re.search(
            r'MATCH\s*\((\w+):(\w+)\)\s*<-\s*\[r?:?(\w+)\]\s*-\s*\((\w+):(\w+)\)',
            cypher, re.I
        )

        if backward_match:
            target_var = backward_match.group(1)
            target_label = backward_match.group(2)
            relation_type = backward_match.group(3)
            source_var = backward_match.group(4)
            source_label = backward_match.group(5)

            return_properties, relation_properties = self._extract_return_properties_v2(cypher)

            return_match = re.search(r'RETURN\s+(.+?)(?:$|\n)', cypher, re.I)
            return_clause = return_match.group(1).strip() if return_match else source_var

            return CypherTemplate(
                predicate_uri=f"onto:{predicate}",
                predicate_local=predicate,
                cypher_query=cypher,
                match_clause=backward_match.group(0),
                return_clause=return_clause,
                source_var=source_var,
                source_label=source_label,
                relation_type=relation_type,
                target_var=target_var,
                target_label=target_label,
                return_properties=return_properties,
                relation_properties=relation_properties
            )

        return None

    def _extract_return_properties_v2(self, cypher: str) -> tuple:
        """
        🔥 改进版：从Cypher的RETURN子句提取属性映射，同时识别关系属性

        返回:
            (properties_dict, relation_properties_set)
        """
        properties = {}
        relation_properties = set()

        return_match = re.search(r'RETURN\s+(.+?)(?:$|\n)', cypher, re.I)
        if return_match:
            return_clause = return_match.group(1)

            # 匹配 var.prop as alias 或 var.prop AS alias
            for match in re.finditer(r'(\w+)\.(\w+)\s+[Aa][Ss]\s+(\w+)', return_clause):
                var_name = match.group(1)
                prop_name = match.group(2)
                alias = match.group(3)
                properties[alias] = prop_name

                # 🔥 关键：如果变量是 'r'，则是关系属性
                if var_name == 'r':
                    relation_properties.add(alias)
                    relation_properties.add(prop_name)

            # 匹配 var.prop (无别名)
            for match in re.finditer(r'(\w+)\.(\w+)(?!\s+[Aa][Ss])', return_clause):
                var_name = match.group(1)
                prop_name = match.group(2)
                if prop_name not in properties.values():
                    properties[prop_name] = prop_name

                # 如果变量是 'r'，则是关系属性
                if var_name == 'r':
                    relation_properties.add(prop_name)

        return properties, relation_properties

    def convert(self, sparql_query: str) -> str:
        """将SPARQL转换为Cypher"""
        try:
            parsed = self._parse_sparql(sparql_query)

            print(f"\n🔍 SPARQL解析结果:")
            print(f"   SELECT: {parsed['select_vars']}")
            print(f"   谓词: {[t['predicate_local'] for t in parsed['triples'] if 'predicate_local' in t]}")
            print(f"   FILTER: {parsed['filters']}")

            template = self._find_template(parsed['triples'])

            if template:
                print(f"\n📌 使用Cypher模板: {template.predicate_local}")
                print(f"   关系类型: {template.relation_type}")
                print(f"   关系属性: {template.relation_properties}")
                cypher = self._build_from_template(parsed, template)
            else:
                print(f"\n⚠️ 未找到匹配的Cypher模板，使用通用转换")
                cypher = self._build_generic(parsed)

            return cypher

        except Exception as e:
            print(f"✗ 转换失败: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _parse_sparql(self, query: str) -> Dict:
        """解析SPARQL查询"""
        clean = re.sub(r'#.*', '', query)
        clean = ' '.join(clean.split())

        prefixes = {}
        for match in re.finditer(r'PREFIX\s+(\w+):\s*<([^>]+)>', clean, re.I):
            prefixes[match.group(1)] = match.group(2)

        select_match = re.search(r'SELECT\s+(DISTINCT\s+)?(.*?)\s+WHERE', clean, re.I)
        if not select_match:
            raise ValueError("无法解析SELECT子句")

        is_distinct = bool(select_match.group(1))
        select_vars = [v.strip('?') for v in select_match.group(2).split() if v.startswith('?')]

        where_match = re.search(r'WHERE\s*\{(.*?)\}', clean, re.DOTALL | re.I)
        if not where_match:
            raise ValueError("无法解析WHERE子句")

        where_body = where_match.group(1)

        filters = []
        for match in re.finditer(r'FILTER\s*\(((?:[^()]|\([^()]*\))*)\)', where_body, re.DOTALL):
            filters.append(match.group(1).strip())
            where_body = where_body.replace(match.group(0), '')

        triples = []
        statements = [s.strip() for s in re.split(r'\s*\.\s*', where_body) if s.strip()]

        for stmt in statements:
            parts = stmt.split(None, 2)
            if len(parts) >= 3:
                pred = parts[1]
                pred_local = pred.split(':')[-1] if ':' in pred else pred

                triples.append({
                    'subject': parts[0].strip('?'),
                    'predicate': pred,
                    'predicate_local': pred_local,
                    'object': parts[2].rstrip('.').strip('?')
                })

        return {
            'select_vars': select_vars,
            'is_distinct': is_distinct,
            'triples': triples,
            'filters': filters,
            'prefixes': prefixes
        }

    def _find_template(self, triples: List[Dict]) -> Optional[CypherTemplate]:
        """查找匹配的Cypher模板"""
        for triple in triples:
            pred_local = triple.get('predicate_local', '')
            if pred_local == 'type':
                continue
            if pred_local in self.cypher_templates:
                return self.cypher_templates[pred_local]
        return None

    def _is_relation_property(self, var: str, template: CypherTemplate) -> bool:
        """
        🔥 判断变量是否是关系属性
        """
        # 1. 检查模板的relation_properties
        if var in template.relation_properties:
            return True

        # 2. 检查已知的关系属性列表
        if var in self.KNOWN_RELATION_PROPERTIES:
            return True

        # 3. 检查属性映射后的名称
        prop = self._get_property_for_var(var, {}, template)
        if prop in self.KNOWN_RELATION_PROPERTIES:
            return True

        return False

    def _get_property_for_var(self, var: str, parsed: Dict, template: CypherTemplate) -> str:
        """
        根据SPARQL变量名获取对应的Neo4j属性名
        """
        # 1. 从模板的RETURN子句提取的属性映射中查找
        if var in template.return_properties:
            return template.return_properties[var]

        # 2. 从TTL的属性映射中查找
        if var in self.property_to_attribute:
            return self.property_to_attribute[var]

        # 3. 查找SPARQL三元组中该变量对应的谓词
        if parsed:
            for triple in parsed.get('triples', []):
                if triple.get('object', '').strip('?') == var:
                    pred_local = triple.get('predicate_local', '')
                    if pred_local in self.property_to_attribute:
                        return self.property_to_attribute[pred_local]

        # 4. 最后回退：使用变量名本身
        return var

    def _build_from_template(self, parsed: Dict, template: CypherTemplate) -> str:
        """🔥 基于Cypher模板构建查询 - 支持关系属性"""
        # 清理转义字符
        target_filter = template.target_filter.replace('\\"', '"').replace("\\\"", '"')

        # 🔥 关键修复：始终包含关系变量 r
        if template.target_label:
            match_clause = f"MATCH ({template.source_var}:{template.source_label})-[r:{template.relation_type}]->({template.target_var}:{template.target_label}{target_filter})"
        else:
            match_clause = f"MATCH ({template.source_var}:{template.source_label})-[r:{template.relation_type}]->({template.target_var}{target_filter})"

        # 构建WHERE条件
        where_conditions = []
        for filter_expr in parsed['filters']:
            condition = self._convert_filter_to_where(filter_expr, parsed, template)
            if condition:
                where_conditions.append(condition)

        # 🔥 关键修复：区分节点属性和关系属性构建RETURN子句
        return_items = []
        for var in parsed['select_vars']:
            prop = self._get_property_for_var(var, parsed, template)

            # 判断是节点属性还是关系属性
            if self._is_relation_property(var, template):
                # 关系属性：使用 r.xxx
                return_items.append(f"r.{prop} AS {var}")
            else:
                # 节点属性：使用 source_var.xxx
                return_items.append(f"{template.source_var}.{prop} AS {var}")

        if not return_items:
            return_items = [template.source_var]

        # 组装
        cypher_parts = [match_clause]
        if where_conditions:
            cypher_parts.append("WHERE " + " AND ".join(where_conditions))

        distinct = "DISTINCT " if parsed['is_distinct'] else ""
        cypher_parts.append(f"RETURN {distinct}{', '.join(return_items)}")

        return "\n".join(cypher_parts)

    def _convert_filter_to_where(self, filter_expr: str, parsed: Dict, template: CypherTemplate) -> Optional[str]:
        """🔥 将SPARQL FILTER转换为Cypher WHERE条件 - 支持关系属性"""

        # 处理复合条件 (&&, ||)
        if '&&' in filter_expr or '||' in filter_expr:
            parts = re.split(r'\s*(\&\&|\|\|)\s*', filter_expr)
            converted_parts = []
            for part in parts:
                part = part.strip()
                if part in ('&&', '||'):
                    converted_parts.append('AND' if part == '&&' else 'OR')
                elif part:
                    converted = self._convert_single_condition(part, parsed, template)
                    if converted:
                        converted_parts.append(converted)
            if len(converted_parts) > 1:
                return '(' + ' '.join(converted_parts) + ')'
            return None

        return self._convert_single_condition(filter_expr, parsed, template)

    def _convert_single_condition(self, filter_expr: str, parsed: Dict, template: CypherTemplate) -> Optional[str]:
        """🔥 转换单个FILTER条件 - 支持关系属性"""

        # IN过滤
        in_match = re.match(r'\?(\w+)\s+IN\s*\((.+)\)', filter_expr, re.I)
        if in_match:
            var = in_match.group(1)
            values_str = in_match.group(2).strip()

            prop = self._get_property_for_var(var, parsed, template)

            # 🔥 判断是节点属性还是关系属性
            var_prefix = "r" if self._is_relation_property(var, template) else template.source_var

            if '<<SUBQUERY' in values_str:
                return f"{var_prefix}.{prop} IN ({values_str})"

            values = re.findall(r'["\']([^"\']+)["\']', values_str)
            if values:
                values_list = '[' + ', '.join(f'"{v}"' for v in values) + ']'
                return f"{var_prefix}.{prop} IN {values_list}"

        # 等值过滤
        eq_match = re.match(r'\?(\w+)\s*=\s*["\'](.+?)["\']$', filter_expr)
        if eq_match:
            var = eq_match.group(1)
            value = eq_match.group(2)
            prop = self._get_property_for_var(var, parsed, template)

            # 🔥 判断是节点属性还是关系属性
            var_prefix = "r" if self._is_relation_property(var, template) else template.source_var
            return f'{var_prefix}.{prop} = "{value}"'

        # 数值比较
        num_match = re.match(r'\?(\w+)\s*(>=|<=|>|<|=|!=)\s*([\d.]+)', filter_expr)
        if num_match:
            var = num_match.group(1)
            op = num_match.group(2)
            value = num_match.group(3)
            prop = self._get_property_for_var(var, parsed, template)

            # 🔥 判断是节点属性还是关系属性
            var_prefix = "r" if self._is_relation_property(var, template) else template.source_var
            return f"{var_prefix}.{prop} {op} {value}"

        return None

    def _build_generic(self, parsed: Dict) -> str:
        """通用转换（无匹配模板时）"""
        nodes = {}

        for triple in parsed['triples']:
            pred_local = triple.get('predicate_local', '')
            if pred_local == 'type':
                var = triple['subject']
                obj = triple['object']
                if obj in self.class_to_label:
                    nodes[var] = self.class_to_label[obj]
                else:
                    obj_local = obj.split(':')[-1] if ':' in obj else obj
                    nodes[var] = obj_local

        if nodes:
            first_var, first_label = list(nodes.items())[0]
            cypher_var = first_var[0]
            match_clause = f"MATCH ({cypher_var}:{first_label})"

            where_conditions = []
            for filter_expr in parsed['filters']:
                condition = self._convert_filter_generic(filter_expr, cypher_var)
                if condition:
                    where_conditions.append(condition)

            cypher_parts = [match_clause]
            if where_conditions:
                cypher_parts.append("WHERE " + " AND ".join(where_conditions))

            # 动态获取属性名
            return_items = []
            for var in parsed['select_vars']:
                prop = var
                if var in self.property_to_attribute:
                    prop = self.property_to_attribute[var]
                return_items.append(f"{cypher_var}.{prop} AS {var}")

            distinct = "DISTINCT " if parsed['is_distinct'] else ""
            cypher_parts.append(f"RETURN {distinct}{', '.join(return_items) if return_items else cypher_var}")

            return "\n".join(cypher_parts)

        return "// 无法转换：未找到有效的模式"

    def _convert_filter_generic(self, filter_expr: str, cypher_var: str) -> Optional[str]:
        """转换通用FILTER条件（无模板时使用）"""

        # 处理复合条件 (&&, ||)
        if '&&' in filter_expr or '||' in filter_expr:
            parts = re.split(r'\s*(\&\&|\|\|)\s*', filter_expr)
            converted_parts = []
            for part in parts:
                part = part.strip()
                if part in ('&&', '||'):
                    converted_parts.append('AND' if part == '&&' else 'OR')
                elif part:
                    converted = self._convert_single_filter_generic(part, cypher_var)
                    if converted:
                        converted_parts.append(converted)
            if len(converted_parts) > 1:
                return '(' + ' '.join(converted_parts) + ')'
            return None

        return self._convert_single_filter_generic(filter_expr, cypher_var)

    def _convert_single_filter_generic(self, filter_expr: str, cypher_var: str) -> Optional[str]:
        """转换单个通用FILTER条件"""
        # IN过滤
        in_match = re.match(r'\?(\w+)\s+IN\s*\((.+)\)', filter_expr, re.I)
        if in_match:
            var = in_match.group(1)
            values_str = in_match.group(2).strip()

            prop = var
            if var in self.property_to_attribute:
                prop = self.property_to_attribute[var]

            if '<<SUBQUERY' in values_str:
                return f"{cypher_var}.{prop} IN ({values_str})"
            else:
                values = re.findall(r'["\']([^"\']+)["\']', values_str)
                if values:
                    values_list = '[' + ', '.join(f'"{v}"' for v in values) + ']'
                    return f"{cypher_var}.{prop} IN {values_list}"

        # 等值过滤
        eq_match = re.match(r'\?(\w+)\s*=\s*["\'](.+?)["\']$', filter_expr)
        if eq_match:
            var = eq_match.group(1)
            value = eq_match.group(2)
            prop = var
            if var in self.property_to_attribute:
                prop = self.property_to_attribute[var]
            return f'{cypher_var}.{prop} = "{value}"'

        # 数值比较
        num_match = re.match(r'\?(\w+)\s*(>=|<=|>|<|=|!=)\s*([\d.]+)', filter_expr)
        if num_match:
            var = num_match.group(1)
            op = num_match.group(2)
            value = num_match.group(3)
            prop = var
            if var in self.property_to_attribute:
                prop = self.property_to_attribute[var]
            return f"{cypher_var}.{prop} {op} {value}"

        return None


def main():
    """测试"""
    print("=" * 70)
    print("SPARQL到Cypher转换器 - 修复版 v5.0")
    print("=" * 70)

    # 使用原TTL文件
    converter = SparqlToCypherConverter("data/GMQA/pgmkg.ttl")

    # 测试1：带p值的表型关联查询
    test_sparql_pvalue = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?microbiota_name ?pvalue
WHERE {
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:has_phenotype_association ?association .
  ?association rdf:type ont:PhenotypeAssociation .
  ?association ont:pvalue ?pvalue .
  ?association ont:condition ?condition .
  FILTER (?pvalue >= 0.2 && ?pvalue <= 0.21)
  FILTER (?condition = "Fattening, Unmedicated feed formula / Antibiotics and zinc oxide")
}
"""

    print("\n" + "=" * 70)
    print("测试1: 带p值的表型关联查询")
    print("=" * 70)
    print("\nSPARQL输入:")
    print(test_sparql_pvalue)

    print("\n生成的Cypher:")
    cypher = converter.convert(test_sparql_pvalue)
    print(cypher)

    print("\n" + "=" * 70)
    print("期望的正确Cypher:")
    print("=" * 70)
    print("""
MATCH (m:MicrobiotaName)-[r:ASSOCIATED_WITH]->(p)
WHERE (r.pvalue >= 0.2 AND r.pvalue <= 0.21) AND r.condition = "Fattening, Unmedicated feed formula / Antibiotics and zinc oxide"
RETURN DISTINCT m.name AS microbiota_name, r.pvalue AS pvalue
""")

    # 测试2：普通关联查询（无p值）
    test_sparql_simple = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?microbiota_name
WHERE {
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:correlatedwith_feed_efficiency ?efficiency .
  ?efficiency rdf:type ont:FeedEfficiency .
  FILTER (?microbiota_name IN ("Dorea", "Eubacterium", "Bacteroides"))
}
"""

    print("\n" + "=" * 70)
    print("测试2: 普通关联查询（无p值）")
    print("=" * 70)
    print("\nSPARQL输入:")
    print(test_sparql_simple)

    print("\n生成的Cypher:")
    cypher2 = converter.convert(test_sparql_simple)
    print(cypher2)


if __name__ == "__main__":
    main()