from langchain.prompts import PromptTemplate
from rdflib import Graph
import importlib
from rdflib import RDF, OWL

# 动态导入提示词模板（根据当前数据集）
from samples_exp.prompt_grad import QueryPlanner_template, SparQLGenerator_template


# ============================================================
# SPARQL清理函数 - 修复LLM输出中的格式问题
# ============================================================
def clean_sparql_output(sparql_text):
    """
    清理LLM生成的SPARQL查询，移除markdown标记和多余内容

    【修复】：不再在遇到 } 时立即停止，而是继续收集 LIMIT/ORDER BY/OFFSET 等子句

    Args:
        sparql_text: LLM生成的原始文本

    Returns:
        清理后的SPARQL查询
    """
    if not sparql_text:
        return ""

    # 移除markdown标记
    sparql_text = sparql_text.replace('```sparql', '')
    sparql_text = sparql_text.replace('```', '')
    sparql_text = sparql_text.strip()

    # 移除示例说明等额外内容，只保留SPARQL
    lines = sparql_text.split('\n')
    cleaned_lines = []
    started = False
    where_closed = False  # 标记WHERE块是否已关闭

    for line in lines:
        stripped = line.strip()

        # 检测SPARQL开始
        if not started and (stripped.startswith('PREFIX') or stripped.startswith('SELECT')):
            started = True

        # 收集SPARQL内容
        if started:
            # 检查是否是SPARQL的有效后续子句
            upper_stripped = stripped.upper()

            # 如果WHERE块已关闭，只收集有效的后续子句
            if where_closed:
                # 有效的后续子句关键词
                valid_suffixes = ['LIMIT', 'ORDER', 'OFFSET', 'GROUP', 'HAVING', 'VALUES']
                is_valid_suffix = any(upper_stripped.startswith(kw) for kw in valid_suffixes)

                # 如果是有效后续子句，继续收集
                if is_valid_suffix:
                    cleaned_lines.append(line)
                # 如果遇到空行，跳过继续检查
                elif not stripped:
                    continue
                # 如果遇到其他内容（如说明文字），停止
                else:
                    break
            else:
                # WHERE块还未关闭，正常收集
                cleaned_lines.append(line)

                # 检测WHERE块结束（括号匹配）
                if stripped == '}' or stripped.endswith('}'):
                    full_text = '\n'.join(cleaned_lines)
                    open_count = full_text.count('{')
                    close_count = full_text.count('}')
                    if open_count == close_count:
                        where_closed = True  # 标记WHERE块已关闭，但不break，继续收集后续子句

    result = '\n'.join(cleaned_lines)

    # 基本验证
    if not result or len(result) < 50:
        print(f"⚠️ 警告：SPARQL可能不完整或过短")
        print(f"原始输入前300字符: {sparql_text[:300]}")
        print(f"清理后长度: {len(result)}")

    if 'SELECT' not in result.upper() and 'ASK' not in result.upper():
        print(f"⚠️ 警告：SPARQL缺少SELECT/ASK子句")

    return result


class QueryPlanner:
    def __init__(self, llm):
        self.llm = llm
        self.plan_prompt = PromptTemplate(
            input_variables=["question"],
            template=QueryPlanner_template
        )

    def decompose_query(self, question):
        """生成带依赖关系的子查询计划"""
        chain = self.plan_prompt | self.llm
        result = chain.invoke({"question": question})
        return result.content

    def parse_subqueries(self, decomposed_text):
        """
        解析分解后的文本，提取子查询及其依赖关系

        返回格式:
        [
            {"id": 1, "question": "子查询1", "dependencies": []},
            {"id": 2, "question": "子查询2", "dependencies": [1]},
            ...
        ]
        """
        subqueries = []
        lines = decomposed_text.strip().split('\n')

        for line in lines:
            if not line.strip():
                continue

            # 处理格式如 "1. [依赖: 无] 查询北京天气"
            if line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                parts = line.split('. ', 1)
                if len(parts) < 2:
                    continue

                id_part, content = parts
                subquery_id = int(id_part)

                # 提取依赖信息
                dep_start = content.find("[依赖:")
                dep_end = content.find("]", dep_start)

                dependencies = []
                if dep_start != -1 and dep_end != -1:
                    dep_str = content[dep_start + 4:dep_end].strip()
                    if dep_str != "无":
                        dependencies = [int(d.strip()) for d in dep_str.split(",")]
                    content = content[:dep_start] + content[dep_end + 1:].strip()

                subqueries.append({
                    "id": subquery_id,
                    "question": content.strip(),
                    "dependencies": dependencies
                })

        return subqueries

    def get_subqueries(self, question):
        """直接获取结构化的子查询及其依赖关系"""
        decomposed_text = self.decompose_query(question)
        print(question)
        print(decomposed_text)
        return self.parse_subqueries(decomposed_text)


class SparQLGenerator:
    def __init__(self, llm, ontology_path=None):
        self.llm = llm
        self.ontology = Graph()
        self.has_ontology = ontology_path is not None

        # 只有当提供了本体路径时才加载本体
        if self.has_ontology:
            try:
                self.ontology.parse(ontology_path)
                print(f"✅ 成功加载本体文件: {ontology_path}")
            except Exception as e:
                print(f"⚠️ 加载本体文件失败: {e}")
                self.has_ontology = False
        else:
            print("ℹ️ 未提供本体文件，将在无本体模式下运行")

        self.sparql_prompt = PromptTemplate(
            input_variables=["sub_question", "ontology", "dependencies"],
            template=SparQLGenerator_template
        )

    def _extract_ontology_info(self):
        """从OWL本体中提取关键信息（类、属性、关系）"""
        if not self.has_ontology:
            # 返回基本的占位符信息
            return {
                "classes": ["MicrobiotaName", "Gene", "KEGGPathway", "FeedEfficiency"],
                "properties": ["microbiota_name", "gene_symbol", "pathway_name", "correlatedwith_feed_efficiency"],
                "example_triples": [
                    "?microbiota rdf:type ont:MicrobiotaName",
                    "?microbiota ont:microbiota_name ?microbiota_name",
                    "?microbiota ont:correlatedwith_feed_efficiency ?feed_efficiency"
                ]
            }

        classes = []
        object_properties = []  # 对象属性
        datatype_properties = []  # 数据属性

        # 提取类信息（简短格式）
        for cls in self.ontology.subjects(RDF.type, OWL.Class):
            cls_name = self._uri_to_short_name(str(cls))
            if cls_name:
                classes.append(cls_name)

        # 提取对象属性（关系）
        for prop in self.ontology.subjects(RDF.type, OWL.ObjectProperty):
            prop_name = self._uri_to_short_name(str(prop))
            if prop_name:
                object_properties.append(prop_name)

        # 提取数据属性
        for prop in self.ontology.subjects(RDF.type, OWL.DatatypeProperty):
            prop_name = self._uri_to_short_name(str(prop))
            if prop_name:
                datatype_properties.append(prop_name)

        # 如果没有明确的对象属性和数据属性，回退到通用属性
        if not object_properties and not datatype_properties:
            for prop in self.ontology.subjects(RDF.type, RDF.Property):
                prop_name = self._uri_to_short_name(str(prop))
                if prop_name:
                    datatype_properties.append(prop_name)

        # 构造清晰的属性说明
        properties_info = []
        if object_properties:
            properties_info.append(f"对象属性（关系）: {', '.join(object_properties)}")
        if datatype_properties:
            properties_info.append(f"数据属性: {', '.join(datatype_properties)}")

        return {
            "classes": classes,
            "properties": "\n".join(properties_info) if properties_info else "无本体属性信息",
            "example_triples": []  # 不再需要示例三元组，已经有完整的谓词映射表
        }

    def _uri_to_short_name(self, uri: str) -> str:
        """将完整的URI转换为简短的名称（提取#或/后的部分）"""
        if '#' in uri:
            return uri.split('#')[-1]
        elif '/' in uri:
            return uri.split('/')[-1]
        return uri

    def generate_sparql(self, sub_question, dependencies=None):
        """生成SPARQL查询，支持依赖关系"""
        ontology_info = self._extract_ontology_info()

        # 构建依赖信息字符串
        dependencies_str = self._format_dependencies(dependencies)

        sparql_query = self.sparql_prompt.format(
            sub_question=sub_question,
            ontology=ontology_info,
            dependencies=dependencies_str
        )

        # 调用LLM生成SPARQL
        result = self.llm.invoke(sparql_query)

        # 🔧 调试：打印LLM原始输出（查看是否包含LIMIT）
        print(f"\n🔍 LLM原始输出:\n{result.content[:800]}")

        # 🔧 清理LLM输出
        cleaned_sparql = clean_sparql_output(result.content)

        # 🔧 添加调试输出 - 打印完整SPARQL
        print(f"\n📝 子问题: {sub_question}")
        print(f"✅ SPARQL长度: {len(cleaned_sparql)} 字符")
        print(f"📄 完整SPARQL:\n{cleaned_sparql}")
        print(f"{'=' * 60}")

        if len(cleaned_sparql) < 100:
            print(f"⚠️ 警告：SPARQL过短，可能生成失败")
            print(f"原始输出前500字符: {result.content[:500]}")

        return cleaned_sparql

    def _format_dependencies(self, dependencies):
        if not dependencies:
            return "无"

        formatted = []
        for dep in dependencies:
            placeholder = f"<<SUBQUERY_{dep['id']}>>"  # 使用实际的子查询ID
            formatted.append(f"依赖子查询 {dep['id']}: {dep['question']} (占位符: {placeholder})")

        return "\n".join(formatted)


def exp_question(question):
    """测试单个问题的转换过程"""
    print(f"\n🔍 正在处理问题: {question}")
    print("=" * 60)

    try:
        from config import model, ontology_path
    except ImportError:
        print("❌ 无法导入配置文件，请检查config.py是否存在")
        return

    # 初始化组件
    query_planner = QueryPlanner(model)
    sparql_generator = SparQLGenerator(model, ontology_path)

    try:
        # 步骤1: 查询分解
        print("\n📋 步骤1: 查询分解")
        print("-" * 30)
        subqueries = query_planner.get_subqueries(question)

        if not subqueries:
            print("❌ 未能分解出子查询")
            return

        print(f"✅ 分解出 {len(subqueries)} 个子查询:")
        for sq in subqueries:
            deps = f"依赖: {sq['dependencies']}" if sq['dependencies'] else "依赖: 无"
            print(f"   {sq['id']}. [{deps}] {sq['question']}")

        # 步骤2: SPARQL生成
        print("\n🔧 步骤2: SPARQL生成")
        print("-" * 30)

        for i, subquery in enumerate(subqueries):
            print(f"\n子查询 {subquery['id']}: {subquery['question']}")
            print(">" * 50)

            # 获取依赖关系
            dependencies = [subqueries[j - 1] for j in subquery["dependencies"]] if subquery["dependencies"] else []

            # 生成SPARQL
            sparql_query = sparql_generator.generate_sparql(
                subquery["question"],
                dependencies
            )

            print("生成的SPARQL查询:")
            print(sparql_query)
            print("<" * 50)

    except Exception as e:
        print(f"❌ 处理过程中出现错误: {str(e)}")
        import traceback
        print("详细错误信息:")
        traceback.print_exc()


def main():
    """
    测试函数：直接测试预设问题
    """
    print("自然语言到SPARQL转换测试")

    # 预设测试问题
    test_questions = [
        "哪些微生物群与生猪饲养效率显著相关？",
        "哪些微生物群关联于生猪饲养效率，在\"Fattening, Unmedicated feed formula / Antibiotics and zinc oxide\"条件下的Pvalue在0.2与0.21之间？",
        "查找在'Fattening, Unmedicated feed formula / Antibiotics and zinc oxide'条件下，与某表型存在关联且 p 值在 0.2 到 0.21 之间的微生物名称及其对应的 p 值。",
        "哪些微生物群关联于生猪饲养效率，在\"Fresh / Fresh+enzyme\"条件下Pvalue=0.19？",
        " Desulfovibrionaceae是否对生猪饲养效率是显著相关的？哪些基因的表达能够增加这些微生物群的数量？",
        "哪些微生物群关联于生猪饲养效率且Pvalue在0.28与0.288之间？",
        "Eubacterium，Treponema bryantii中哪些微生物群对生猪饲养效率是显著相关的？这些微生物产生的代谢物和哪些基因的表达量有关？",
        "给soluble corn fiber食物导致肠道微生物丰度上升的微生物有哪些?",
        "使用药物Metformin导致肠道微生物丰度上升的微生物有哪些？",
        " (genera)Dorea，Eubacterium，Bacteroides中哪些微生物群对生猪饲养效率是显著相关的？这些微生物产生的代谢物和哪些基因的表达量有关？",
        "(genera)Clostridium，Lactobacillus，Oscillibacter中哪些微生物群对生猪饲养效率是显著相关的？哪些基因的表达能够减少这些微生物群的数量？",
        "使用药物Vitamin A导致肠道微生物丰度上升的微生物有哪些？",
        "哪些微生物群关联于生猪饲养效率，在\"Fresh / Fresh+enzyme\"条件下Pvalue=0.19？这些微生物产生的代谢物和哪些基因的表达量有关？hsa04060 Cytokine-cytokine receptor interaction，hsa04061 Viral protein interaction with cytokine and cytokine receptor，hsa04062 Chemokine signaling pathway，hsa01521 EGFR tyrosine kinase inhibitor resistance,mmu01521 EGFR tyrosine kinase inhibitor resistance，hsa04066 HIF-1 signaling pathway,hsa01524 Platinum drug resistance，mmu04152 AMPK signaling pathway,mmu04010 MAPK signaling pathway，mmu00220 Arginine biosynthesis，hsa04659 Th17 cell differentiation,mmu04714 Thermogenesis中哪些在这些基因的代谢通路里？"
        , "给\"sea buckthorn protein\"食物导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够减少这些微生物的数量？"
    ]

    exp_question(test_questions[-1])


if __name__ == "__main__":
    main()