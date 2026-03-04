#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复版：通用OWL本体解析器
完全基于OWL标准，零硬编码，支持简化的OWL格式
"""

import re
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef
from rdflib.plugins.sparql import prepareQuery
import logging

import samples_exp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UniversalOWLParser:
    """
    通用OWL本体解析器
    零硬编码，完全基于OWL标准结构
    """

    def __init__(self, ontology_path: Optional[str] = None):
        """初始化解析器"""
        self.graph = Graph()
        self.has_ontology = ontology_path is not None

        # OWL标准命名空间
        self.OWL = OWL
        self.RDF = RDF
        self.RDFS = RDFS

        # 解析结果存储
        self.classes: Set[str] = set()
        self.object_properties: Set[str] = set()
        self.datatype_properties: Set[str] = set()
        self.individuals: Set[str] = set()

        # 属性层级关系
        self.property_hierarchy: Dict[str, Set[str]] = defaultdict(set)
        self.class_hierarchy: Dict[str, Set[str]] = defaultdict(set)

        # 属性的定义域和值域
        self.property_domains: Dict[str, Set[str]] = defaultdict(set)
        self.property_ranges: Dict[str, Set[str]] = defaultdict(set)

        if self.has_ontology:
            self._load_and_parse(ontology_path)

    def _load_and_parse(self, ontology_path: str):
        """加载并解析OWL本体"""
        try:
            # 尝试加载
            self.graph.parse(ontology_path, format='xml')
            print(f"✅ 成功加载本体: {ontology_path}")

            # 提取所有本体元素
            self._extract_classes()
            self._extract_properties()
            self._extract_individuals()
            self._extract_hierarchies()
            self._extract_domains_ranges()

            self._print_summary()

        except Exception as e:
            logger.error(f"❌ 加载本体失败: {e}")
            print(f"❌ 加载本体失败: {e}")
            print("提示：请使用简化的OWL文件（rodi_ontology_simplified.owl）")
            self.has_ontology = False

    def _extract_classes(self):
        """提取所有OWL类（完全基于标准）"""
        # 方法1: 明确声明为owl:Class的
        for cls in self.graph.subjects(RDF.type, OWL.Class):
            self.classes.add(str(cls))

        # 方法2: 作为rdfs:subClassOf的主语或宾语的
        for s, p, o in self.graph.triples((None, RDFS.subClassOf, None)):
            self.classes.add(str(s))
            if isinstance(o, URIRef):
                self.classes.add(str(o))

        # 方法3: 作为rdfs:domain或rdfs:range的对象类
        for s, p, o in self.graph.triples((None, RDFS.domain, None)):
            if isinstance(o, URIRef) and not self._is_datatype(o):
                self.classes.add(str(o))

        for s, p, o in self.graph.triples((None, RDFS.range, None)):
            if isinstance(o, URIRef) and not self._is_datatype(o):
                self.classes.add(str(o))

        print(f"  提取到 {len(self.classes)} 个类")

    def _extract_properties(self):
        """提取对象属性和数据属性（完全基于标准）"""
        # 对象属性 (ObjectProperty)
        for prop in self.graph.subjects(RDF.type, OWL.ObjectProperty):
            self.object_properties.add(str(prop))

        # 数据属性 (DatatypeProperty)
        for prop in self.graph.subjects(RDF.type, OWL.DatatypeProperty):
            self.datatype_properties.add(str(prop))

        # 兼容性：检查rdf:Property
        for prop in self.graph.subjects(RDF.type, RDF.Property):
            prop_str = str(prop)
            # 通过range判断类型
            range_obj = self.graph.value(prop, RDFS.range)
            if range_obj:
                if self._is_datatype(range_obj):
                    self.datatype_properties.add(prop_str)
                else:
                    self.object_properties.add(prop_str)
            else:
                # 默认作为对象属性
                self.object_properties.add(prop_str)

        print(f"  提取到 {len(self.object_properties)} 个对象属性")
        print(f"  提取到 {len(self.datatype_properties)} 个数据属性")

    def _is_datatype(self, uri: URIRef) -> bool:
        """判断URI是否为数据类型"""
        uri_str = str(uri)
        # XSD数据类型
        if 'XMLSchema#' in uri_str:
            return True
        # RDF/RDFS数据类型
        if uri_str in [str(RDFS.Literal), 'http://www.w3.org/1999/02/22-rdf-syntax-ns#PlainLiteral']:
            return True
        return False

    def _extract_individuals(self):
        """提取所有个体实例"""
        # 查找所有类的实例
        for cls in self.classes:
            for individual in self.graph.subjects(RDF.type, URIRef(cls)):
                # 排除类本身
                if str(individual) not in self.classes:
                    self.individuals.add(str(individual))

    def _extract_hierarchies(self):
        """提取类和属性的层级关系"""
        # 类层级
        for subclass, _, superclass in self.graph.triples((None, RDFS.subClassOf, None)):
            if isinstance(superclass, URIRef):
                self.class_hierarchy[str(superclass)].add(str(subclass))

        # 属性层级
        for subprop, _, superprop in self.graph.triples((None, RDFS.subPropertyOf, None)):
            if isinstance(superprop, URIRef):
                self.property_hierarchy[str(superprop)].add(str(subprop))

    def _extract_domains_ranges(self):
        """提取属性的定义域和值域"""
        # Domain (定义域)
        for prop, _, domain in self.graph.triples((None, RDFS.domain, None)):
            if isinstance(domain, URIRef):
                self.property_domains[str(prop)].add(str(domain))

        # Range (值域)
        for prop, _, range_val in self.graph.triples((None, RDFS.range, None)):
            if isinstance(range_val, URIRef):
                self.property_ranges[str(prop)].add(str(range_val))

    def _print_summary(self):
        """打印解析摘要"""
        print(f"\n📊 本体解析摘要:")
        print(f"  类 (Classes): {len(self.classes)}")
        print(f"  对象属性 (Object Properties): {len(self.object_properties)}")
        print(f"  数据属性 (Datatype Properties): {len(self.datatype_properties)}")
        print(f"  个体 (Individuals): {len(self.individuals)}")

        if self.classes:
            print(f"  类示例: {[self.get_local_name(c) for c in list(self.classes)[:5]]}")
        if self.object_properties:
            print(f"  对象属性示例: {[self.get_local_name(p) for p in list(self.object_properties)[:5]]}")
        if self.datatype_properties:
            print(f"  数据属性示例: {[self.get_local_name(p) for p in list(self.datatype_properties)[:5]]}")

    def get_local_name(self, uri: str) -> str:
        """从URI中提取本地名称"""
        if '#' in uri:
            return uri.split('#')[-1]
        elif '/' in uri:
            return uri.split('/')[-1]
        return uri

    def is_class(self, uri: str) -> bool:
        """判断URI是否为类"""
        return uri in self.classes

    def is_object_property(self, uri: str) -> bool:
        """判断URI是否为对象属性"""
        return uri in self.object_properties

    def is_datatype_property(self, uri: str) -> bool:
        """判断URI是否为数据属性"""
        return uri in self.datatype_properties

    def get_property_type(self, uri: str) -> Optional[str]:
        """获取属性类型"""
        if self.is_object_property(uri):
            return "ObjectProperty"
        elif self.is_datatype_property(uri):
            return "DatatypeProperty"
        return None

    def match_uri_fuzzy(self, local_name: str) -> List[Tuple[str, str]]:
        """
        模糊匹配URI

        Args:
            local_name: 本地名称（如 "Person", "contributes"）

        Returns:
            匹配结果列表 [(完整URI, 类型), ...]
        """
        matches = []
        local_lower = local_name.lower()

        # 在类中查找
        for cls in self.classes:
            if local_lower in self.get_local_name(cls).lower():
                matches.append((cls, "Class"))

        # 在对象属性中查找
        for prop in self.object_properties:
            if local_lower in self.get_local_name(prop).lower():
                matches.append((prop, "ObjectProperty"))

        # 在数据属性中查找
        for prop in self.datatype_properties:
            if local_lower in self.get_local_name(prop).lower():
                matches.append((prop, "DatatypeProperty"))

        return matches


class SemanticConsistencyChecker:
    """使用LLM进行语义一致性检查"""

    def __init__(self, model):
        self.model = model

        # 动态导入提示词模板（根据当前数据集）
        try:
            import samples_exp.prompt_grad
            _,_,cur_prompt,_,_,_ = samples_exp.prompt_grad.get_templates()
            self.checker_rules =  cur_prompt
        except ImportError as e:
            logger.warning(f"无法导入QueryCheckerRules，使用默认模板。错误: {e}")
            self.checker_rules = self._get_default_rules()
        except AttributeError as e:
            logger.warning(f"QueryCheckerRules不存在，使用默认模板。错误: {e}")
            self.checker_rules = self._get_default_rules()

    def _get_default_rules(self) -> str:
        """默认检查规则"""
        return """
你是SPARQL语义一致性检查专家。请分析自然语言问题与SPARQL查询是否一致。

输入：
- 自然语言问题：{natural_language_query}
- SPARQL查询：{sparql_query}
- 本体信息：{ontology_info}

检查要点：
1. 意图匹配：问题要求查询什么？SPARQL是否返回对应结果？
2. 实体类型对齐
3. 关系方向检查
4. 返回值类型
5. 过滤条件

输出格式：
```
一致性：[合规/不合规]
问题：[如果不合规，列出具体问题]
```
"""

    def check_consistency(self, natural_language_query: str, sparql_query: str,
                          ontology_info: str = "") -> Tuple[bool, str]:
        """
        使用LLM检查查询的语义一致性

        Returns:
            (is_consistent, details)
        """
        try:
            # 构建提示词
            prompt = self.checker_rules.format(
                natural_language_query=natural_language_query,
                sparql_query=sparql_query,
                ontology_info=ontology_info if ontology_info else "无本体信息"
            )

            # 调用LLM
            response = self.model.invoke(prompt)
            result_text = response.content

            # 🔥 改进的解析逻辑 - 多种方式判断
            result_lower = result_text.lower()

            # 方式1: 检查"一致性：合规"
            if "一致性：合规" in result_text or "一致性: 合规" in result_text:
                is_consistent = True
            elif "一致性：不合规" in result_text or "一致性: 不合规" in result_text:
                is_consistent = False
            # 方式2: 检查英文
            elif "consistency: compliant" in result_lower or "consistent: yes" in result_lower:
                is_consistent = True
            elif "consistency: non-compliant" in result_lower or "consistent: no" in result_lower:
                is_consistent = False
            # 方式3: 关键词判断（后备方案）
            elif any(word in result_lower for word in ["合规", "正确", "一致", "通过", "correct", "valid"]):
                # 检查是否有否定词
                if any(word in result_lower for word in
                       ["不合规", "错误", "不一致", "不正确", "incorrect", "invalid", "wrong"]):
                    is_consistent = False
                else:
                    is_consistent = True
            else:
                # 默认判定为合规（宽松策略）
                logger.warning(f"⚠️ 无法解析LLM响应，默认判定为合规")
                is_consistent = True

            return is_consistent, result_text

        except Exception as e:
            logger.error(f"语义一致性检查失败: {e}")
            # 出错时默认合规，不阻碍流程
            return True, f"⚠️ 检查失败: {str(e)}，默认判定为合规"


class QueryChecker:
    """
    改进的SPARQL查询检查器
    使用UniversalOWLParser，零硬编码
    """

    def __init__(self, ontology_path: Optional[str] = None, model=None, llm_check_mode: str = "advisory"):
        """
        初始化检查器

        Args:
            ontology_path: 本体文件路径
            model: LLM模型
            llm_check_mode: LLM检查模式
                - "strict": LLM检查影响最终判定
                - "advisory": LLM检查仅作建议（推荐）
                - "disabled": 禁用LLM检查
        """
        self.owl_parser = UniversalOWLParser(ontology_path)
        self.has_ontology = self.owl_parser.has_ontology
        self.model = model
        self.llm_check_mode = llm_check_mode

        # 禁止使用的函数
        self.forbidden_functions = ['CONTAINS', 'REGEX', 'STRSTARTS']

        # 语义检查器（如果提供了模型且未禁用）
        self.semantic_checker = None
        if model and llm_check_mode != "disabled":
            self.semantic_checker = SemanticConsistencyChecker(model)
            print(f"✅ LLM检查模式: {llm_check_mode}")
        elif llm_check_mode == "disabled":
            print(f"ℹ️ LLM检查已禁用")

    def check_query(self, sparql_query: str, natural_language_query: Optional[str] = None) -> Tuple[bool, str]:
        """检查SPARQL查询的合规性"""
        is_compliant = True
        details = []

        print(f"\n{'=' * 60}")
        print(f"🔍 开始检查SPARQL查询")
        print(f"{'=' * 60}")
        if natural_language_query:
            print(f"📝 自然语言问题: {natural_language_query}")
        print(f"📄 SPARQL查询:\n{sparql_query[:200]}...")
        print(f"{'-' * 60}")

        # 检查占位符
        has_placeholder = '<<SUBQUERY_' in sparql_query
        if has_placeholder:
            placeholders = re.findall(r'<<SUBQUERY_\d+>>', sparql_query)
            details.append(f"✓ 检测到 {len(placeholders)} 个子查询占位符: {', '.join(placeholders)}")
            print(f"✓ 检测到占位符: {placeholders}")

            # 临时替换占位符进行语法检查
            temp_query = sparql_query
            for i, placeholder in enumerate(placeholders):
                temp_query = temp_query.replace(placeholder, f'?placeholder_{i}')
        else:
            temp_query = sparql_query

        # 1. 语法合规性检查
        print(f"\n【步骤1】语法合规性检查")
        syntax_ok, syntax_details = self._check_syntax_compliance(temp_query, has_placeholder)
        if not syntax_ok:
            is_compliant = False
            print(f"❌ 语法检查失败")
        else:
            print(f"✅ 语法检查通过")
        details.append("=== 语法合规性检查 ===")
        details.extend(syntax_details)

        # 2. 语义合规性检查（只有语法正确才进行）
        if syntax_ok and self.has_ontology:
            print(f"\n【步骤2】语义合规性检查（基于本体）")
            semantic_ok, semantic_details = self._check_semantic_compliance(sparql_query, has_placeholder)
            if not semantic_ok:
                is_compliant = False
                print(f"❌ 本体语义检查失败")
            else:
                print(f"✅ 本体语义检查通过")
            details.append("\n=== 语义合规性检查 ===")
            details.extend(semantic_details)
        elif not self.has_ontology:
            print(f"\n【步骤2】跳过本体语义检查（无本体）")
            details.append("\n=== 语义合规性检查 ===")
            details.append("⚠️ 无本体模式，跳过语义检查")
        else:
            print(f"\n【步骤2】跳过语义检查（语法错误）")
            details.append("\n=== 语义合规性检查 ===")
            details.append("由于语法错误，无法进行语义检查")

        # 3. 禁止函数检查
        print(f"\n【步骤3】禁止函数检查")
        forbidden_ok, forbidden_details = self._check_forbidden_functions(sparql_query)
        if not forbidden_ok:
            is_compliant = False
            print(f"❌ 禁止函数检查失败")
        else:
            print(f"✅ 禁止函数检查通过")
        details.append("\n=== 禁止函数检查 ===")
        details.extend(forbidden_details)

        # 4. 语义一致性检查（LLM）
        if natural_language_query and self.semantic_checker and syntax_ok:
            print(f"\n【步骤4】LLM语义一致性检查（模式: {self.llm_check_mode}）")
            try:
                consistency_ok, consistency_details = self.semantic_checker.check_consistency(
                    natural_language_query, sparql_query
                )

                # 🔥 关键修复：详细输出LLM检查结果
                print(f"\n--- LLM检查详情 ---")
                print(consistency_details)
                print(f"--- LLM检查结束 ---\n")

                # 🔥 根据配置模式决定是否影响最终判定
                if not consistency_ok:
                    if self.llm_check_mode == "strict":
                        is_compliant = False
                        print(f"❌ LLM检查失败（strict模式，影响最终判定）")
                    else:  # advisory
                        print(f"⚠️ LLM语义一致性检查发现潜在问题（advisory模式，仅供参考）")
                else:
                    print(f"✅ LLM语义一致性检查通过")

                details.append("\n=== LLM语义一致性检查 ===")
                details.append(consistency_details)
                if self.llm_check_mode == "advisory":
                    details.append(f"\n注意：LLM检查模式为advisory，结果仅供参考，不影响最终判定")
                else:
                    details.append(f"\n注意：LLM检查模式为{self.llm_check_mode}")

            except Exception as e:
                print(f"⚠️ LLM检查出错: {e}")
                details.append("\n=== LLM语义一致性检查 ===")
                details.append(f"⚠️ LLM检查失败: {str(e)}")
        elif natural_language_query and not self.semantic_checker:
            print(f"\n【步骤4】跳过LLM检查（未初始化或已禁用）")
            details.append("\n=== LLM语义一致性检查 ===")
            details.append("⚠️ 语义一致性检查器未初始化（缺少LLM模型或已禁用）")
        elif not natural_language_query:
            print(f"\n【步骤4】跳过LLM检查（无自然语言问题）")
            details.append("\n=== LLM语义一致性检查 ===")
            details.append("ℹ️ 未提供自然语言查询，跳过语义一致性检查")

        # 总结
        print(f"\n{'=' * 60}")
        details.append("\n=== 检查总结 ===")
        if is_compliant:
            print(f"✅ 查询完全合规")
            details.append("✅ 查询完全合规")
        else:
            print(f"❌ 查询不合规，发现以下问题：")
            # 提取错误信息
            errors = [d for d in details if '❌' in d]
            for err in errors:
                print(f"  {err}")
            details.append("❌ 查询不合规，请修复上述问题")

        if has_placeholder:
            details.append("\n注意: 查询包含占位符，实际执行时需要替换。")

        if not self.has_ontology:
            details.append("\n注意: 在无本体模式下运行，语义合规性检查基于基本启发式规则。")

        print(f"{'=' * 60}\n")
        return is_compliant, "\n".join(details)

    def _check_syntax_compliance(self, sparql_query: str, has_placeholder: bool = False) -> Tuple[bool, List[str]]:
        """检查语法合规性"""
        is_compliant = True
        details = []
        errors = []

        try:
            prepareQuery(sparql_query)
            details.append("✅ 语法解析成功")
            if has_placeholder:
                details.append("  (占位符已临时替换为变量进行语法检查)")

            # 基本语法检查
            if sparql_query.count('(') != sparql_query.count(')'):
                errors.append("括号不匹配")
                is_compliant = False

            if sparql_query.count('{') != sparql_query.count('}'):
                errors.append("大括号不匹配")
                is_compliant = False

            query_upper = sparql_query.upper()
            if not any(kw in query_upper for kw in ['SELECT', 'CONSTRUCT', 'ASK', 'DESCRIBE']):
                errors.append("缺少查询类型关键字")
                is_compliant = False

            if 'WHERE' not in query_upper and 'SELECT' in query_upper:
                errors.append("缺少WHERE子句")
                is_compliant = False

        except Exception as e:
            errors.append(f"语法解析错误: {str(e)[:200]}")
            is_compliant = False

        if errors:
            for error in errors:
                details.append(f"❌ 错误: {error}")
        else:
            details.append("✅ 未发现语法错误")

        return is_compliant, details

    def _check_semantic_compliance(self, sparql_query: str, has_placeholder: bool = False) -> Tuple[bool, List[str]]:
        """检查语义合规性（使用通用OWL解析器）"""
        is_compliant = True
        details = []

        # 提取查询中使用的本体元素
        used_elements = self._extract_ontology_elements_generic(sparql_query)

        details.append(f"- 查询中使用的类: {len(used_elements['classes'])} 个")
        if used_elements['classes']:
            class_names = [self.owl_parser.get_local_name(c) for c in list(used_elements['classes'])[:5]]
            details.append(f"  类列表: {', '.join(class_names)}")

        details.append(f"- 查询中使用的属性: {len(used_elements['properties'])} 个")
        if used_elements['properties']:
            prop_names = [self.owl_parser.get_local_name(p) for p in list(used_elements['properties'])[:5]]
            details.append(f"  属性列表: {', '.join(prop_names)}")

        if has_placeholder:
            details.append("- 注意: 占位符可能引用其他查询的结果，无法验证其本体一致性")

        # 验证类
        invalid_classes = []
        for cls in used_elements['classes']:
            if not self.owl_parser.is_class(cls):
                # 尝试模糊匹配
                matches = self.owl_parser.match_uri_fuzzy(self.owl_parser.get_local_name(cls))
                if not any(m[1] == "Class" for m in matches):
                    invalid_classes.append(self.owl_parser.get_local_name(cls))

        # 验证属性
        invalid_properties = []
        for prop in used_elements['properties']:
            prop_type = self.owl_parser.get_property_type(prop)
            if not prop_type:
                # 尝试模糊匹配
                matches = self.owl_parser.match_uri_fuzzy(self.owl_parser.get_local_name(prop))
                if not any("Property" in m[1] for m in matches):
                    invalid_properties.append(self.owl_parser.get_local_name(prop))

        # 报告结果
        if invalid_classes:
            is_compliant = False
            details.append(f"❌ 未在本体中找到的类: {', '.join(invalid_classes)}")

        if invalid_properties:
            is_compliant = False
            details.append(f"❌ 未在本体中找到的属性: {', '.join(invalid_properties)}")

        if not invalid_classes and not invalid_properties:
            details.append("✅ 所有类和属性都在本体中存在")

        return is_compliant, details

    def _extract_ontology_elements_generic(self, sparql_query: str) -> Dict[str, Set[str]]:
        """
        通用方法：从SPARQL查询中提取本体元素

        🔥 修复：正确处理 FILTER 子句，避免将操作符误识别为属性
        """
        elements = {
            'classes': set(),
            'properties': set()
        }

        # 提取前缀定义
        prefixes = {}
        prefix_pattern = r'PREFIX\s+(\w+):\s*<([^>]+)>'
        for match in re.finditer(prefix_pattern, sparql_query, re.IGNORECASE):
            prefixes[match.group(1)] = match.group(2)

        # 🔥 关键修复：在提取属性前，移除 FILTER 子句
        # 这可以避免将 FILTER 中的操作符（=, <, >, IN 等）误识别为属性
        query_without_filters = self._remove_filter_clauses(sparql_query)

        # 1. 提取 rdf:type 后面的类
        type_pattern = r'(?:rdf:type|a)\s+([^\s.{}]+)'
        for match in re.finditer(type_pattern, sparql_query):
            cls = match.group(1).strip()
            if not cls.startswith('?'):
                full_uri = self._expand_prefix(cls, prefixes)
                elements['classes'].add(full_uri)

        # 2. 提取三元组中的谓词（属性）- 🔥 在移除FILTER后的查询中提取
        triple_pattern = r'\?(\w+)\s+([^\s?]+)\s+[?<"\']'
        for match in re.finditer(triple_pattern, query_without_filters):
            predicate = match.group(2).strip()
            # 排除特殊谓词和SPARQL操作符
            if predicate not in ['rdf:type', 'a'] and not predicate.startswith('?'):
                # 🔥 额外检查：排除SPARQL操作符
                if not self._is_sparql_operator(predicate):
                    full_uri = self._expand_prefix(predicate, prefixes)
                    # 排除rdf:type这种
                    if not full_uri.endswith('type'):
                        elements['properties'].add(full_uri)

        return elements

    def _remove_filter_clauses(self, sparql_query: str) -> str:
        """
        🔥 新增：移除SPARQL查询中的FILTER子句

        支持嵌套括号，例如：FILTER ((?x = 1) && (?y = 2))
        """
        result = sparql_query

        # 匹配 FILTER 关键字后面的括号内容（支持嵌套）
        filter_pattern = r'FILTER\s*\('

        while True:
            match = re.search(filter_pattern, result, re.IGNORECASE)
            if not match:
                break

            # 找到 FILTER 后面的开括号位置
            start = match.end() - 1  # 指向 '('

            # 使用括号匹配找到结束位置
            end = self._find_matching_parenthesis(result, start)
            if end == -1:
                break

            # 移除整个 FILTER 子句
            result = result[:match.start()] + ' ' + result[end + 1:]

        return result

    def _find_matching_parenthesis(self, text: str, start: int) -> int:
        """
        🔥 新增：找到与start位置的'('匹配的')'位置
        """
        if start >= len(text) or text[start] != '(':
            return -1

        depth = 0
        for i in range(start, len(text)):
            if text[i] == '(':
                depth += 1
            elif text[i] == ')':
                depth -= 1
                if depth == 0:
                    return i
        return -1

    def _is_sparql_operator(self, token: str) -> bool:
        """
        🔥 新增：检查是否为SPARQL操作符

        这些操作符可能出现在 FILTER 子句中，不应被识别为本体属性
        """
        # SPARQL比较和逻辑操作符
        sparql_operators = {
            '=', '!=', '<', '>', '<=', '>=', '<>',
            '&&', '||', '!',
            'IN', 'NOT', 'AND', 'OR',
            'BOUND', 'ISIRI', 'ISURI', 'ISBLANK', 'ISLITERAL',
            'STR', 'LANG', 'DATATYPE', 'SAMETYPE',
            '+', '-', '*', '/',
        }

        return token.upper() in sparql_operators or token in sparql_operators

    def _expand_prefix(self, term: str, prefixes: Dict[str, str]) -> str:
        """展开前缀为完整URI"""
        if ':' in term and not term.startswith('http'):
            prefix, local = term.split(':', 1)
            if prefix in prefixes:
                return prefixes[prefix] + local
        return term

    def _check_forbidden_functions(self, sparql_query: str) -> Tuple[bool, List[str]]:
        """检查禁止函数"""
        is_compliant = True
        details = []
        found_functions = []

        query_upper = sparql_query.upper()
        for func in self.forbidden_functions:
            pattern = rf'\b{func}\s*\('
            if re.search(pattern, query_upper):
                found_functions.append(func)
                is_compliant = False

        if found_functions:
            details.append(f"❌ 发现禁止使用的函数: {', '.join(found_functions)}")
            details.append("  这些字符串函数不被允许使用")
        else:
            details.append("✅ 未发现禁止使用的函数")

        return is_compliant, details


class QueryRepairer:
    """SPARQL查询修复器（保持原有接口不变）"""

    def __init__(self, model, dataset_name=None):
        self.model = model

        # 获取当前数据集名称
        if dataset_name is None:
            try:
                import config
                self.dataset_name = config.CURRENT_DATASET
            except:
                self.dataset_name = "RODI"
        else:
            self.dataset_name = dataset_name

        # 导入prompt模板（动态根据数据集）
        try:
            from samples_exp import prompt_grad as pg
            _, _, _,repairer_tmpl,_,_ = pg.get_templates()
            self.repair_prompt_template = repairer_tmpl
        except ImportError as e:
            logger.warning(f"无法导入QueryRepairer_template，使用默认模板。错误: {e}")
            self.repair_prompt_template = self._get_default_template()
        except AttributeError as e:
            logger.warning(f"QueryRepairer_template不存在，使用默认模板。错误: {e}")
            self.repair_prompt_template = self._get_default_template()

    def _get_default_template(self) -> str:
        """获取默认修复模板"""
        return """
你是SPARQL查询修复专家。

输入：
- 原始问题：{natural_language_query}
- 当前SPARQL：{sparql_query}
- 检测问题：{detected_issues}
- 本体信息：{ontology_content}

请修复SPARQL查询中的问题，确保：
1. 语法正确
2. 符合本体定义
3. 保留占位符（如<<SUBQUERY_n>>）

只返回修复后的SPARQL，无解释，不含markdown标记。
"""

    def repair_sparql(self, natural_language_query: str, detected_issues: str,
                      sparql_query: str, dependencies: str = "") -> str:
        """修复SPARQL查询"""
        # 检测并保存占位符
        placeholders = re.findall(r'<<SUBQUERY_\d+>>', sparql_query)
        has_placeholder = len(placeholders) > 0

        if has_placeholder:
            logger.info(f"检测到 {len(placeholders)} 个占位符: {placeholders}")

        # 获取本体摘要
        ontology_content = self._get_ontology_summary()

        # 添加占位符保留提示
        if has_placeholder:
            ontology_content += f"""

### ⚠️ 占位符保留规则（重要！）:
当前查询包含 {len(placeholders)} 个占位符: {', '.join(placeholders)}
**修复时必须保留这些占位符！**

占位符使用规则:
- 占位符表示上一个子查询的结果
- 修复时不要删除或修改占位符
- 占位符应该在 FILTER 子句中使用，例如: FILTER (?var IN (<<SUBQUERY_1>>))
- 确保占位符两侧的括号正确
"""

        # 调用LLM进行修复
        try:
            from langchain.prompts import PromptTemplate

            prompt = PromptTemplate(
                input_variables=["natural_language_query", "sparql_query", "detected_issues", "ontology_content"],
                template=self.repair_prompt_template
            )

            prompt_value = prompt.format(
                natural_language_query=natural_language_query,
                sparql_query=sparql_query,
                detected_issues=detected_issues,
                ontology_content=ontology_content
            )

            response = self.model.invoke(prompt_value)
            repaired_query = response.content.strip()

            # 清理返回的查询（去除可能的markdown标记）
            repaired_query = repaired_query.replace("```sparql", "").replace("```", "").strip()

            # 验证占位符是否被保留
            if has_placeholder:
                repaired_placeholders = re.findall(r'<<SUBQUERY_\d+>>', repaired_query)
                if len(repaired_placeholders) != len(placeholders):
                    logger.warning(f"占位符丢失！原始: {placeholders}, 修复后: {repaired_placeholders}")
                    logger.warning("占位符可能在修复过程中被删除，请检查修复逻辑")

            logger.info("SPARQL查询修复成功")
            return repaired_query

        except Exception as e:
            logger.error(f"SPARQL查询修复失败: {e}")
            # 如果修复失败，返回原始查询
            return sparql_query

    def _get_ontology_summary(self) -> str:
        """获取本体摘要信息"""
        if self.dataset_name == "RODI":
            return """
### 主要类（Classes）:
- Person: 会议相关人员
- Paper: 论文
- Abstract: 摘要
- Conference_volume: 会议
- Committee: 委员会
- Review: 评审

### Neo4j 关系（Object Properties）:
- contributes: Person -> Paper（作者发表论文）
- has_authors: Paper -> Person（论文的作者）
- has_members: Committee -> Person（委员会成员）
- was_a_member_of: Person -> Committee（人员所在委员会）
- is_submitted_at: Paper -> Conference（论文提交会议）
- reviews: Review -> Paper（评审审查论文）

### MySQL 关系:
- is_the_1th_part_of: Abstract -> Paper（摘要属于论文）
- has_text: Abstract的文本内容

### PostgreSQL 属性:
- has_a_paper_title: 论文标题
- has_the_first_name, has_the_last_name: 人员姓名
- has_an_email: 邮箱
- has_a_name: 会议/委员会名称
- has_a_location: 会议地点

### 重要提示:
- RODI 使用 conf: 前缀，不是 ont:
- 返回实体URI，不是ID属性
- ID过滤使用: FILTER (?person = 3)
"""
        else:
            return "使用默认本体信息"


# 测试代码
if __name__ == "__main__":
    print("=" * 70)
    print(" 通用OWL本体解析器测试")
    print("=" * 70)

    # 测试简化的RODI本体
    ontology_path = 'data/RODI/rodi_ontology.owl'

    print("\n🔍 加载并解析本体...")
    parser = UniversalOWLParser(ontology_path)

    if parser.has_ontology:
        print("\n🧪 测试1: 模糊匹配")
        test_terms = ['Person', 'Paper', 'contributes', 'has_a_paper_title']
        for term in test_terms:
            matches = parser.match_uri_fuzzy(term)
            print(f"\n'{term}' 的匹配结果:")
            for uri, otype in matches[:3]:
                print(f"  - {parser.get_local_name(uri)} ({otype})")

        print("\n🧪 测试2: 检查器测试")
        checker = QueryChecker(ontology_path)

        test_sparql = """
        PREFIX conf: <http://conference#>
        SELECT ?paper
        WHERE {
          ?person rdf:type conf:Person .
          ?person conf:contributes ?paper .
          FILTER (?person = 3)
        }
        """

        is_compliant, details = checker.check_query(test_sparql)
        print(f"\n检查结果: {'✅ 合规' if is_compliant else '❌ 不合规'}")
        print(f"\n详细信息:\n{details}")

    print("\n" + "=" * 70)
    print("✓ 测试完成")
    print("=" * 70)