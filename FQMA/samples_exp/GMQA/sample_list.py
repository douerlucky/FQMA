# ============================================================
# 核心样例 - 5个最有价值的样例（精简版）
# ============================================================

# ============ QueryPlanner - 5个样例 ============
QueryPlannerSamplesList = [
# 样例1：基础3步链（最常见模式）
"""示例1：基础3步依赖链
问题：Dorea，Eubacterium，Bacteroides中哪些微生物群对生猪饲养效率是显著相关的？这些微生物受哪些基因的调控？这些基因的代谢通路有哪些？
子查询列表：
1. [依赖: 无] Dorea，Eubacterium，Bacteroides中哪些微生物群对生猪饲养效率是显著相关的
2. [依赖: 1] 这些微生物受哪些基因的调控
3. [依赖: 2] 这些基因的代谢通路有哪些
""",

# 样例2：带p值和条件（易错点）
"""示例2：带p值条件查询
问题：哪些微生物群关联于生猪饲养效率，在"Fattening, Unmedicated feed formula / Antibiotics and zinc oxide"条件下Pvalue在0.2与0.21之间？这些微生物受哪些基因的调控？这些基因的代谢通路有哪些？
子查询列表：
1. [依赖: 无] 哪些微生物群关联于生猪饲养效率，在"Fattening, Unmedicated feed formula / Antibiotics and zinc oxide"条件下Pvalue在0.2与0.21之间
2. [依赖: 1] 这些微生物受哪些基因的调控
3. [依赖: 2] 这些基因的代谢通路有哪些
""",

# 样例3：食物4步链（新数据库）
"""示例3：食物影响微生物
问题：给ketogenic diet食物导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够减少这些微生物的数量？这些基因的代谢通路是什么？
子查询列表：
1. [依赖: 无] 给ketogenic diet食物导致肠道微生物丰度上升的微生物有哪些
2. [依赖: 1] 哪些基因的表达能够减少这些微生物的数量
3. [依赖: 2] 这些基因的代谢通路是什么
""",

# 样例4：药物影响
"""示例4：药物影响微生物
问题：使用药物Metformin导致肠道微生物丰度上升的微生物有哪些？哪些基因的表达能够增加这些微生物群的数量？这些基因的代谢通路是什么？
子查询列表：
1. [依赖: 无] 使用药物Metformin导致肠道微生物丰度上升的微生物有哪些
2. [依赖: 1] 哪些基因的表达能够增加这些微生物群的数量
3. [依赖: 2] 这些基因的代谢通路是什么
""",

# 样例5：指定通路查询
"""示例5：指定通路查询
问题：Clostridium，Treponema中哪些微生物群对生猪饲养效率是显著相关的？哪些基因的表达能够增加这些微生物群的数量？hsa04060，hsa04062，mmu04010中哪些在这些基因的代谢通路里？
子查询列表：
1. [依赖: 无] Clostridium，Treponema中哪些微生物群对生猪饲养效率是显著相关的
2. [依赖: 1] 哪些基因的表达能够增加这些微生物群的数量
3. [依赖: 2] hsa04060，hsa04062，mmu04010中哪些在这些基因的代谢通路里
""",
"""
示例6（药物效应查询链）：
问题：哪些药物能够增加Bifidobacterium的丰度，这些微生物产生哪些代谢物，相关基因的表达如何调节？
子查询列表：
1. [依赖: 无] 哪些药物能够增加Bifidobacterium的丰度？
2. [依赖: 1] Bifidobacterium产生哪些代谢物？
3. [依赖: 2] 哪些基因的表达能够调节这些代谢物的产生？
"""
]

# ============ SparQLGenerator - 5个样例 ============
SparQLGeneratorSamplesList = [
# 样例1：微生物相关（无p值）- 最基础，最容易误判
"""示例1：微生物相关（无p值，注意"显著"不是p值！）
问题：Dorea，Eubacterium，Bacteroides中哪些微生物群对生猪饲养效率是显著相关的
关键：问题说"显著相关"，但没有提到"p值"、"pvalue"等统计术语！
      "显著相关"是口语化，表示"重要的相关"，不是统计显著性！
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?microbiota_name
WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:correlatedwith_feed_efficiency ?efficiency .
  ?efficiency rdf:type ont:FeedEfficiency .
  FILTER (?microbiota_name IN ("Dorea", "Eubacterium", "Bacteroides"))
}}
注意：不查询pvalue，不使用has_phenotype_association！
""",

# 样例2：带p值查询 - 关键区分点
"""示例2：带p值条件查询（与"显著相关"对比）
问题：哪些微生物群关联于生猪饲养效率，在"Fattening, Unmedicated feed formula / Antibiotics and zinc oxide"条件下Pvalue在0.2与0.21之间
关键：问题明确提到"Pvalue在0.2与0.21之间"，这是统计术语！
      必须使用has_phenotype_association + pvalue
对比：如果问题只说"显著相关"而不提"pvalue"，则用correlatedwith_feed_efficiency
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?microbiota_name ?pvalue
WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:has_phenotype_association ?association .
  ?association rdf:type ont:PhenotypeAssociation .
  ?association ont:pvalue ?pvalue .
  ?association ont:condition ?condition .
  FILTER (?pvalue >= 0.2 && ?pvalue <= 0.21)
  FILTER (?condition = "Fattening, Unmedicated feed formula / Antibiotics and zinc oxide")
}}
注意：只有明确提到"pvalue"、"p<"等统计术语时才这样写！
""",

# 样例3：食物增加微生物 - gutmdisorder数据库 ⚠️ 只返回微生物名！
"""示例3：食物增加微生物（关键：只返回微生物名！）
问题：给ketogenic diet食物导致肠道微生物丰度上升的微生物有哪些
⚠️ 最重要：问题问的是"哪些微生物"，所以只返回微生物名，不返回食物名！
对应SQL：Select microbiota_name from gutmdisorder.food_gut_microbiota_change_results
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?microbiota_name
WHERE {{
  ?food rdf:type ont:Food .
  ?food ont:food_name ?food_name .
  ?food ont:increases_microbiota_abundance_by_food ?microbiota .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?food_name = "ketogenic diet")
}}
注意：
1. 只SELECT ?microbiota_name，不SELECT ?food_name
2. 问题是"哪些微生物"，所以主体是微生物
3. 食物只是查询条件，不是返回结果
""",

# 样例4：基因减少微生物 - 方向性
"""示例4：基因减少微生物（注意方向性）
问题：哪些基因的表达能够减少这些微生物的数量
依赖：<<SUBQUERY_1>>返回了微生物名称
关键：
1. 问"哪些基因"，所以gene_symbol是主体，第一列
2. "减少"微生物，用decreases_microbiota_abundance
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?gene_symbol ?microbiota_name
WHERE {{
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:decreases_microbiota_abundance ?microbiota .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?microbiota_name IN (<<SUBQUERY_1>>))
}}
""",

# 样例5：指定通路查询（提取标号！）
"""示例5：查询指定KEGG通路（关键：提取标号！）
问题：hsa04062 Chemokine signaling pathway，hsa01521 EGFR tyrosine kinase inhibitor resistance，mmu04010 MAPK signaling pathway中哪些在这些基因的代谢通路里
依赖：<<SUBQUERY_2>>返回了基因符号
⚠️ 最关键：必须从完整名称中提取标号！
处理步骤：
1. 看到"hsa04062 Chemokine signaling pathway" → 提取"hsa04062"
2. 看到"hsa01521 EGFR tyrosine kinase inhibitor resistance" → 提取"hsa01521"
3. 看到"mmu04010 MAPK signaling pathway" → 提取"mmu04010"
4. 在FILTER中只使用标号

SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT DISTINCT ?pathway_name ?gene_symbol
WHERE {{
  ?gene rdf:type ont:Gene .
  ?gene ont:gene_symbol ?gene_symbol .
  ?gene ont:participates_in_pathway ?pathway .
  ?pathway rdf:type ont:KEGGPathway .
  ?pathway ont:pathway_name ?pathway_name .
  FILTER (?gene_symbol IN (<<SUBQUERY_2>>))
  FILTER (?pathway_name IN ("hsa04062", "hsa01521", "mmu04010"))
}}
注意：FILTER中只用标号，不用完整名称！
数据库中pathway_name字段只存储"hsa04062"这样的标号，不存储完整名称。
""",
"""
    示例6：药物减少微生物丰度查询
问题：哪些药物能够减少Clostridium、Bacteroides的丰度？
SPARQL：
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ont: <http://www.semanticweb.org/ontologies/integrated_gut_microbiota_ontology#>

SELECT ?drug_name ?microbiota_name
WHERE {{
  ?drug rdf:type ont:Drug .
  ?drug ont:drug_name ?drug_name .
  ?drug ont:decreases_microbiota_abundance_by_drug ?microbiota .
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  FILTER (?microbiota_name IN ("Clostridium", "Bacteroides"))
}}
    """
]

# ============ SPARQLRepair - 5个核心修复模式 ============
SPARQLRepairSampleList = [
"""修复1：微生物相关（删除efficiency变量）
错误：SELECT ?microbiota_name ?efficiency
正确：SELECT DISTINCT ?microbiota_name
WHERE {{
  ?microbiota rdf:type ont:MicrobiotaName .
  ?microbiota ont:microbiota_name ?microbiota_name .
  ?microbiota ont:correlatedwith_feed_efficiency ?efficiency .
  ?efficiency rdf:type ont:FeedEfficiency .
}}
关键：efficiency只用于关系，不在SELECT中
""",

"""修复2：区分"显著相关"和"p值"（最常见误判！）
错误场景：问题说"关联性最为显著"，误认为需要p值
错误：SELECT ?microbiota_name ?pvalue
      WHERE {{ ?microbiota ont:has_phenotype_association ?association . }}
正确：SELECT DISTINCT ?microbiota_name
      WHERE {{ ?microbiota ont:correlatedwith_feed_efficiency ?efficiency . }}
关键：
- "显著相关"、"关联性显著"、"最为显著" = 口语化的"重要"
- 只有明确出现"pvalue"、"p<"等统计术语时才用PhenotypeAssociation
""",

"""修复3：食物查询只返回微生物名（重要！）
错误：SELECT ?microbiota_name ?food_name
正确：SELECT ?microbiota_name
关键：
- 问题是"哪些微生物"，所以只返回微生物名
- 食物只是查询条件，不是返回结果
- 对应SQL：Select microbiota_name from gutmdisorder...
""",

"""修复4：变量顺序（基因第一列）
错误：SELECT ?microbiota_name ?gene_symbol
正确：SELECT ?gene_symbol ?microbiota_name
关键：问"哪些基因"，基因是主体，必须第一列
""",

"""修复5：KEGG通路标号提取
错误：FILTER (?pathway_name IN ("hsa04062 Chemokine signaling pathway", "mmu04010 MAPK signaling pathway"))
正确：FILTER (?pathway_name IN ("hsa04062", "mmu04010"))
关键：
- 用户给出完整名称时，必须提取标号（空格前的部分）
- 数据库中只存储标号，不存储完整名称
- hsa04062 Chemokine signaling pathway → hsa04062
- mmu04010 MAPK signaling pathway → mmu04010
""",
"""
                       ### 微生物与表型的显著关联（带p值）：
```sparql
SELECT ?microbiota_name ?pvalue WHERE {{
  ?microbiota ont:has_phenotype_association ?association .
  ?association ont:pvalue ?pvalue .
  FILTER (?pvalue < 0.05)
}}
```""",
]
